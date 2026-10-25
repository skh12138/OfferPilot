from uuid import UUID

from offerpilot.api.deps import require_consent
from offerpilot.api.errors import DomainError
from offerpilot.api.schemas import digest
from offerpilot.infrastructure.config import settings
from offerpilot.infrastructure.db import now
from offerpilot.infrastructure.owned import get_owned, lock_owner
from offerpilot.modules.runs.models import (
    TERMINAL,
    AgentRun,
    IdempotencyRecord,
    RunEvent,
    RunStatus,
)
from pydantic import JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def public_search_authorized(kind: str, inputs: dict[str, JsonValue]) -> bool:
    return (
        kind in {"search", "search_parse", "search_organize"}
        and inputs.get("public_info_ai_consent") is True
    )


async def idempotent(
    db: AsyncSession, owner: UUID, operation: str, key: str | None, payload: JsonValue
) -> UUID | None:
    if not key or len(key) > 120:
        raise DomainError("idempotency_required", "需要有效 Idempotency-Key", 422)
    row = await db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.owner_id == owner,
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.key == key,
        )
    )
    if row:
        if row.payload_hash != digest(payload):
            raise DomainError("idempotency_conflict", "相同幂等键对应不同请求")
        return row.result_id
    return None


def remember(
    db: AsyncSession, owner: UUID, operation: str, key: str, payload: JsonValue, result: UUID
) -> None:
    db.add(
        IdempotencyRecord(
            owner_id=owner,
            operation=operation,
            key=key,
            payload_hash=digest(payload),
            result_id=result,
        )
    )


def event(
    db: AsyncSession, run: AgentRun, kind: str, data: dict[str, JsonValue] | None = None
) -> None:
    run.event_seq += 1
    db.add(
        RunEvent(
            owner_id=run.owner_id,
            run_id=run.id,
            seq=run.event_seq,
            event_type=kind,
            data=data or {},
        )
    )


def provider_ready(kind: str) -> None:
    cfg = settings()
    if cfg.app_mode == "live":
        if (
            kind in {"search", "interview_sources", "study", "job_refresh"}
            and not cfg.tavily_api_key.get_secret_value()
        ):
            raise DomainError("provider_not_configured", "尚未配置 Tavily", 503)
        if (
            kind not in {"export", "delete_resume", "delete_account", "interview_sources"}
            and not cfg.deepseek_api_key.get_secret_value()
        ):
            raise DomainError("provider_not_configured", "尚未配置 DeepSeek", 503)


async def enqueue(
    db: AsyncSession,
    owner: UUID,
    kind: str,
    inputs: dict[str, JsonValue],
    key: str | None,
    *,
    profile_id: UUID | None = None,
    resume_id: UUID | None = None,
    application_id: UUID | None = None,
    commit: bool = True,
) -> AgentRun:
    await lock_owner(db, owner)
    payload: dict[str, JsonValue] = {
        "kind": kind,
        "inputs": inputs,
        "profile_id": str(profile_id) if profile_id else None,
        "resume_id": str(resume_id) if resume_id else None,
        "application_id": str(application_id) if application_id else None,
    }
    operation = f"run:{kind}"
    previous = await idempotent(db, owner, operation, key, payload)
    if previous:
        return await get_owned(db, AgentRun, owner, previous)
    provider_ready(kind)
    if kind not in {"export", "delete_resume", "delete_account", "interview_sources"} and not (
        public_search_authorized(kind, inputs)
        and profile_id is None
        and resume_id is None
        and application_id is None
    ):
        await require_consent(db, owner)
    run = AgentRun(
        owner_id=owner,
        kind=kind,
        inputs=inputs,
        profile_version_id=profile_id,
        resume_version_id=resume_id,
        application_id=application_id,
        model=settings().llm_model,
    )
    db.add(run)
    await db.flush()
    remember(db, owner, operation, str(key), payload, run.id)
    if commit:
        await db.commit()
    return run


async def cancel_owner_runs(db: AsyncSession, owner: UUID) -> None:
    rows = await db.scalars(
        select(AgentRun)
        .where(
            AgentRun.owner_id == owner, AgentRun.status.in_([RunStatus.QUEUED, RunStatus.RUNNING])
        )
        .with_for_update()
    )
    for run in rows:
        if run.kind in {"delete_resume", "delete_account"}:
            continue
        run.cancel_requested_at = now()
        if run.status == RunStatus.QUEUED:
            run.status = RunStatus.CANCELLED
            event(db, run, "run_cancelled")


async def cancel(db: AsyncSession, owner: UUID, resource_id: UUID) -> AgentRun:
    await lock_owner(db, owner)
    run = await get_owned(db, AgentRun, owner, resource_id, lock=True)
    if RunStatus(run.status) not in TERMINAL:
        run.cancel_requested_at = now()
        if run.status == RunStatus.QUEUED:
            run.status = RunStatus.CANCELLED
            event(db, run, "run_cancelled")
    await db.commit()
    return run
