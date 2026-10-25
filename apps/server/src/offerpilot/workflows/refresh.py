from offerpilot.api.errors import DomainError
from offerpilot.infrastructure.config import settings
from offerpilot.infrastructure.db import Session
from offerpilot.modules.discovery.service import extraction_permission
from offerpilot.modules.jobs.schemas import JobExtraction
from offerpilot.modules.jobs.service import save_extraction, validate_extraction
from offerpilot.providers.base import ContentProvider, ContentResult, LLMProvider, Usage
from offerpilot.providers.urls import validate_public_dns
from offerpilot.worker.context import Context
from offerpilot.worker.queue import guarded
from pydantic import JsonValue


async def refresh(ctx: Context, llm: LLMProvider, content: ContentProvider) -> None:
    url = str(ctx.run.inputs["url"])
    async with Session() as db:
        policy = await extraction_permission(db, url, "jobs")
    if not policy or not policy.store_text:
        raise DomainError("source_metadata_only", "该来源尚不允许提取和保存正文")
    if settings().app_mode == "live":
        await validate_public_dns(url)

    async def call() -> tuple[dict[str, JsonValue], Usage]:
        result = await content.extract([url])
        return result.model_dump(mode="json"), result.usage

    result = ContentResult.model_validate(
        await ctx.call("refresh:extract", "content", {"url": url}, call)
    )
    text = result.texts.get(url)
    if not text:
        raise DomainError("content_unavailable", "正文暂不可读，不能据此判定岗位关闭")

    def validate(data: dict[str, JsonValue]) -> None:
        validate_extraction(JobExtraction.model_validate(data), text or "")

    raw = await ctx.generate(
        "refresh:normalize",
        "job_normalize",
        JobExtraction,
        {"text": text, "source_kind": "provider_extracted"},
        llm.generate_json,
        validate,
    )
    async with Session() as db:
        await guarded(db, ctx.run.owner_id, ctx.run.id, ctx.token)
        policy = await extraction_permission(db, url, "jobs")
        if not policy or not policy.store_text:
            raise DomainError("source_policy_changed", "来源策略已改变")
        job, _ = await save_extraction(
            db, ctx.run.owner_id, JobExtraction.model_validate(raw), text, url, "provider_extracted"
        )
        await ctx.publish(db, {"job_id": str(job.id)})
