import csv
import io
import re

from offerpilot.api.errors import DomainError
from offerpilot.infrastructure.db import Session
from offerpilot.infrastructure.owned import get_owned
from offerpilot.modules.jobs.schemas import JobExtraction
from offerpilot.modules.jobs.service import save_extraction, validate_extraction
from offerpilot.modules.profiles.models import Profile, ProfileVersion, ResumeVersion
from offerpilot.modules.profiles.schemas import ParsedFacts
from offerpilot.providers.base import LLMProvider
from offerpilot.worker.context import Context
from offerpilot.worker.queue import guarded
from pydantic import JsonValue
from sqlalchemy import select


def redact(text: str) -> str:
    # Keep paragraph numbering stable, so evidence still locates the original snapshot.
    text = re.sub(r"(?m)^(?:姓名|手机|电话|邮箱|地址|联系方式)[：:].*$", "[联系方式已隐藏]", text)
    return re.sub(r"\S+@\S+|(?<!\d)1[3-9]\d{9}(?!\d)", "[联系方式已隐藏]", text)


async def resume_parse(ctx: Context, llm: LLMProvider) -> dict[str, JsonValue]:
    async with Session() as db:
        if not ctx.run.resume_version_id:
            raise DomainError("invalid_input", "缺少简历版本")
        row = await get_owned(db, ResumeVersion, ctx.run.owner_id, ctx.run.resume_version_id)
        text = row.text or ""

    def validate(raw: dict[str, JsonValue]) -> None:
        result = ParsedFacts.model_validate(raw)
        paragraphs = {f"p{i + 1}": line for i, line in enumerate(text.splitlines())}
        for fact in result.facts:
            if fact.evidence.quote not in paragraphs.get(fact.evidence.paragraph_id, ""):
                raise DomainError("invalid_evidence", "简历引文不匹配")
            if fact.text != fact.evidence.quote:
                raise DomainError("unsupported_claim", "抽取必须保持事实原文，等待人工确认")

    raw = await ctx.generate(
        "extract_facts",
        "resume_parse",
        ParsedFacts,
        {"text": redact(text)},
        llm.generate_json,
        validate,
    )
    parsed = ParsedFacts.model_validate(raw)
    for fact in parsed.facts:
        fact.status = "unconfirmed"
        fact.evidence.source_kind = "resume_text"
        fact.evidence.snapshot_id = ctx.run.resume_version_id
    async with Session() as db:
        await guarded(db, ctx.run.owner_id, ctx.run.id, ctx.token)
        selection = await db.scalar(
            select(Profile).where(Profile.owner_id == ctx.run.owner_id).with_for_update()
        )
        previous = (
            await get_owned(db, ProfileVersion, ctx.run.owner_id, selection.current_version_id)
            if selection and selection.current_version_id
            else None
        )
        profile = ProfileVersion(
            owner_id=ctx.run.owner_id,
            resume_version_id=ctx.run.resume_version_id,
            preferences=dict(previous.preferences) if previous and not previous.unavailable else {},
            facts=[f.model_dump(mode="json") for f in parsed.facts],
            reason="简历解析，待逐条确认",
        )
        db.add(profile)
        await db.flush()
        selection = await db.scalar(
            select(Profile).where(Profile.owner_id == ctx.run.owner_id).with_for_update()
        )
        if selection:
            selection.current_version_id, selection.revision = profile.id, selection.revision + 1
        else:
            db.add(Profile(owner_id=ctx.run.owner_id, current_version_id=profile.id))
        return await ctx.publish(
            db,
            {
                "profile_version_id": str(profile.id),
                "resume_version_id": str(ctx.run.resume_version_id),
            },
        )


async def job_import(ctx: Context, llm: LLMProvider) -> dict[str, JsonValue]:
    text = str(ctx.run.inputs["text"])
    url = str(ctx.run.inputs["url"]) if ctx.run.inputs.get("url") else None
    entries: list[tuple[str, str | None]] = [(text, url)]
    if ctx.run.inputs.get("format") == "csv":
        rows = list(csv.DictReader(io.StringIO(text)))
        if len(rows) > 500:
            raise DomainError("csv_limit", "CSV 最多500行", 422)
        entries = [(row.get("text", ""), row.get("url") or None) for row in rows]
    ids: list[JsonValue] = []
    errors: list[JsonValue] = []
    for index, (body, source) in enumerate(entries):
        try:
            if not body.strip():
                raise DomainError("empty_row", "缺少 text 列")
            key = f"normalize:{index}"

            def validate_job(data: dict[str, JsonValue], body: str = body) -> None:
                validate_extraction(JobExtraction.model_validate(data), body)

            raw = await ctx.generate(
                key,
                "job_normalize",
                JobExtraction,
                {"text": body},
                llm.generate_json,
                validate_job,
            )
            async with Session() as db:
                run = await guarded(db, ctx.run.owner_id, ctx.run.id, ctx.token)
                artifact_key = f"save_job:{index}"
                existing = await ctx.saved(db, artifact_key)
                if existing:
                    ids.append(existing["job_id"])
                    continue
                job, _ = await save_extraction(
                    db,
                    run.owner_id,
                    JobExtraction.model_validate(raw),
                    body,
                    source,
                    "user_provided",
                )
                ctx.save_step(db, artifact_key, {"job_id": str(job.id)})
                await db.commit()
                ids.append(str(job.id))
        except DomainError as exc:
            errors.append({"row": index + 1, "code": exc.code, "message": exc.message})
    async with Session() as db:
        await guarded(db, ctx.run.owner_id, ctx.run.id, ctx.token)
        return await ctx.publish(
            db,
            {"job_ids": ids, "errors": errors},
            partial=bool(errors),
            failed=bool(errors) and not ids,
        )
