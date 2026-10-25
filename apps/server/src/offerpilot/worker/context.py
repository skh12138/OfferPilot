from collections.abc import Awaitable, Callable
from time import monotonic
from uuid import UUID

from offerpilot.api.deps import require_consent
from offerpilot.api.errors import DomainError
from offerpilot.api.schemas import digest
from offerpilot.infrastructure.config import settings
from offerpilot.infrastructure.db import Session, now
from offerpilot.modules.runs.models import AgentRun, ProviderCall, RunStep
from offerpilot.modules.runs.service import event
from offerpilot.providers.base import Generated, ProviderError, Usage
from offerpilot.providers.http import backoff
from offerpilot.worker.queue import guarded
from pydantic import BaseModel, JsonValue, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class Context:
    def __init__(self, run: AgentRun, token: UUID) -> None:
        self.run, self.token = run, token

    async def cached(self, key: str, input_hash: str) -> dict[str, JsonValue] | None:
        async with Session() as db:
            await guarded(db, self.run.owner_id, self.run.id, self.token)
            run_ids = [self.run.id]
            if self.run.retry_of:
                run_ids.append(self.run.retry_of)
            row = await db.scalar(
                select(RunStep)
                .where(
                    RunStep.owner_id == self.run.owner_id,
                    RunStep.run_id.in_(run_ids),
                    RunStep.step_key == key,
                    RunStep.input_hash == input_hash,
                )
                .order_by(RunStep.created_at)
                .limit(1)
            )
            return row.result if row else None

    async def call(
        self,
        key: str,
        provider: str,
        inputs: dict[str, JsonValue],
        invoke: Callable[[], Awaitable[tuple[dict[str, JsonValue], Usage]]],
        output_tokens: int = 0,
    ) -> dict[str, JsonValue]:
        hashed = digest(
            {
                "inputs": inputs,
                "provider": provider,
                "max_output_tokens": output_tokens,
                "workflow": self.run.workflow_version,
                "prompt": self.run.prompt_version,
                "schema": self.run.schema_version,
                "model": self.run.model,
                "profile": str(self.run.profile_version_id),
            }
        )
        cached = await self.cached(key, hashed)
        if cached is not None:
            return cached
        for attempt in range(3):
            async with Session() as db:
                run = await guarded(db, self.run.owner_id, self.run.id, self.token)
                if provider == "llm":
                    from offerpilot.modules.runs.service import public_search_authorized

                    if not (
                        public_search_authorized(run.kind, run.inputs)
                        and run.profile_version_id is None
                        and run.resume_version_id is None
                        and run.application_id is None
                    ):
                        await require_consent(db, run.owner_id)
                estimate = len(str(inputs).encode()) if provider == "llm" else 0
                cfg = settings()
                if (
                    run.calls_reserved >= cfg.run_max_calls
                    or run.input_reserved + estimate > cfg.run_input_tokens
                    or run.output_reserved + output_tokens > cfg.run_output_tokens
                    or (
                        run.started_at
                        and (now() - run.started_at).total_seconds() > cfg.run_timeout_seconds
                    )
                ):
                    raise DomainError("budget_exhausted", "达到运行预算或时限")
                run.calls_reserved += 1
                run.input_reserved += estimate
                run.output_reserved += output_tokens
                call = ProviderCall(
                    owner_id=run.owner_id,
                    run_id=run.id,
                    step_key=key,
                    provider=provider,
                    model=run.model if provider == "llm" else None,
                    prompt_version=run.prompt_version,
                    parameters={
                        "max_tokens": output_tokens,
                        "temperature": 0.1,
                        "thinking": "disabled",
                    },
                )
                db.add(call)
                event(db, run, "step_started", {"step": key})
                await db.commit()
                call_id = call.id
            start = monotonic()
            failure: ProviderError | None = None
            try:
                result, usage = await invoke()
            except ProviderError as exc:
                result, usage, failure = {}, Usage(), exc
            async with Session() as db:
                saved_call = await db.get(ProviderCall, call_id)
                if saved_call:
                    saved_call.status = "failed" if failure else "completed"
                    saved_call.usage = usage.model_dump(mode="json")
                    saved_call.response_model = usage.response_model
                    saved_call.error_code = failure.code if failure else None
                    saved_call.duration_ms = int((monotonic() - start) * 1000)
                    await db.commit()
                # Even a known successful vendor response cannot publish after lease loss or deletion.
                run = await guarded(db, self.run.owner_id, self.run.id, self.token)
                if not failure:
                    # Unknown usage keeps the reservation; never call it zero consumption.
                    if usage.input_tokens is not None:
                        run.input_reserved += usage.input_tokens - estimate
                    if usage.output_tokens is not None:
                        run.output_reserved += usage.output_tokens - output_tokens
                    db.add(
                        RunStep(
                            owner_id=run.owner_id,
                            run_id=run.id,
                            step_key=key,
                            input_hash=hashed,
                            result=result,
                        )
                    )
                    event(db, run, "step_completed", {"step": key})
                    await db.commit()
                    return result
                event(db, run, "warning", {"step": key, "code": failure.code})
                await db.commit()
            if not failure.retryable or attempt == 2:
                raise failure
            await backoff(attempt)
        raise ProviderError("unreachable")

    async def generate(
        self,
        key: str,
        task: str,
        schema: type[BaseModel],
        inputs: dict[str, JsonValue],
        generate: Callable[
            [str, dict[str, JsonValue], dict[str, JsonValue], int], Awaitable[Generated]
        ],
        validate: Callable[[dict[str, JsonValue]], object] | None = None,
        max_tokens: int = 4096,
    ) -> dict[str, JsonValue]:
        from offerpilot.providers.deepseek import SYSTEM, TASK_RULES, prepare_inputs

        inputs = prepare_inputs(task, inputs)
        for repair in range(2):
            call_inputs = dict(inputs)

            async def invoke(
                call_inputs: dict[str, JsonValue] = call_inputs,
            ) -> tuple[dict[str, JsonValue], Usage]:
                value = await generate(task, schema.model_json_schema(), call_inputs, max_tokens)
                return value.data, value.usage

            metadata: dict[str, JsonValue] = {
                "inputs": inputs,
                "schema": schema.model_json_schema(),
                "prompt_version": self.run.prompt_version,
                "system_instructions": SYSTEM + TASK_RULES.get(task, ""),
            }
            try:
                raw = await self.call(
                    key + (":repair" if repair else ""), "llm", metadata, invoke, max_tokens
                )
            except ProviderError as exc:
                if repair == 0 and exc.code in {
                    "model_invalid_json",
                    "model_empty",
                    "model_truncated",
                }:
                    inputs = {
                        **inputs,
                        "repair_instruction": "上次输出为空、截断或不是json，请按Schema重试一次。",
                    }
                    continue
                raise
            try:
                normalized = schema.model_validate(raw).model_dump(mode="json")
                if validate:
                    validate(normalized)
                return normalized
            except (ValidationError, DomainError) as exc:
                if repair:
                    raise DomainError(
                        "model_semantic_invalid", "结构或事实校验失败；可手工编辑后重试", 422
                    ) from exc
                inputs = {
                    **inputs,
                    "repair_instruction": "上次结构或证据不满足 Schema，请重新生成，不能补造事实。",
                    "validation_errors": (
                        [{"code": exc.code}]
                        if isinstance(exc, DomainError)
                        else [
                            {"path": ".".join(str(part) for part in e["loc"]), "code": e["type"]}
                            for e in exc.errors()[:10]
                        ]
                    ),
                }
        raise ProviderError("unreachable")

    async def saved(self, db: "AsyncSession", key: str) -> dict[str, JsonValue] | None:
        row = await db.scalar(
            select(RunStep).where(RunStep.run_id == self.run.id, RunStep.step_key == key)
        )
        return row.result if row else None

    def save_step(self, db: "AsyncSession", key: str, result: dict[str, JsonValue]) -> None:
        db.add(
            RunStep(
                owner_id=self.run.owner_id,
                run_id=self.run.id,
                step_key=key,
                input_hash=digest(
                    {"run_id": str(self.run.id), "workflow": self.run.workflow_version}
                ),
                result=result,
            )
        )

    async def publish(
        self,
        db: "AsyncSession",
        result: dict[str, JsonValue],
        *,
        partial: bool = False,
        failed: bool = False,
    ) -> dict[str, JsonValue]:
        from offerpilot.modules.runs.models import RunStatus

        run = await guarded(db, self.run.owner_id, self.run.id, self.token)
        run.result = result
        run.status = (
            RunStatus.FAILED if failed else RunStatus.PARTIAL if partial else RunStatus.SUCCEEDED
        )
        run.completed_at = now()
        event(db, run, "run_failed" if failed else "run_completed", {"status": run.status})
        await db.commit()
        return result
