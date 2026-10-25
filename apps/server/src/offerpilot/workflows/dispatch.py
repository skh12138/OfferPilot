from offerpilot.api.errors import DomainError
from offerpilot.infrastructure.db import Session
from offerpilot.modules.discovery.schemas import SpecInput
from offerpilot.providers.base import ContentProvider, LLMProvider, SearchProvider
from offerpilot.worker.context import Context
from offerpilot.worker.queue import guarded
from offerpilot.workflows.discovery import search_jobs


async def dispatch(
    ctx: Context, llm: LLMProvider, search: SearchProvider, content: ContentProvider
) -> None:
    if ctx.run.kind == "search":
        await search_jobs(ctx, llm, search, content)
    elif ctx.run.kind == "search_organize":
        from offerpilot.workflows.opportunities import organize_existing

        await organize_existing(ctx, llm)
    elif ctx.run.kind == "search_parse":
        raw = await ctx.generate(
            "parse_scope", "search_parse", SpecInput, ctx.run.inputs, llm.generate_json
        )
        raw["confirmed"] = False
        async with Session() as db:
            await guarded(db, ctx.run.owner_id, ctx.run.id, ctx.token)
            await ctx.publish(db, {"spec": raw})
    elif ctx.run.kind == "material_prepare":
        from offerpilot.workflows.preparation import prepare

        await prepare(ctx, llm)
    elif ctx.run.kind == "study":
        from offerpilot.workflows.interview import study

        await study(ctx, llm, search, content)
    elif ctx.run.kind == "feedback":
        from offerpilot.workflows.interview import feedback

        await feedback(ctx, llm)
    elif ctx.run.kind == "interview_sources":
        from offerpilot.workflows.interview import collect_sources

        rows = await collect_sources(
            ctx,
            search,
            content,
            str(ctx.run.inputs["query"]),
            str(ctx.run.inputs.get("company", "")),
            str(ctx.run.inputs.get("role", "")),
        )
        async with Session() as db:
            await guarded(db, ctx.run.owner_id, ctx.run.id, ctx.token)
            await ctx.publish(db, {"source_ids": [str(s.id) for s in rows]})
    elif ctx.run.kind == "export":
        from offerpilot.modules.control.exporting import export

        await export(ctx)
    elif ctx.run.kind == "delete_resume":
        from offerpilot.modules.control.deletion import delete_resume

        await delete_resume(ctx)
    elif ctx.run.kind == "delete_account":
        from offerpilot.modules.control.deletion import delete_account

        await delete_account(ctx)
    elif ctx.run.kind == "job_refresh":
        from offerpilot.workflows.refresh import refresh

        await refresh(ctx, llm, content)
    else:
        raise DomainError("workflow_version_unavailable", "尚未注册该工作流")
