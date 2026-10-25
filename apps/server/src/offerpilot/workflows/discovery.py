from offerpilot.api.errors import DomainError
from offerpilot.infrastructure.config import settings
from offerpilot.infrastructure.db import Session
from offerpilot.modules.discovery.models import SearchCandidate, SourcePolicy
from offerpilot.modules.discovery.schemas import SpecInput
from offerpilot.modules.discovery.service import (
    allowed_source,
    extraction_permission,
    preserve_scope,
    search_queries,
)
from offerpilot.modules.jobs.schemas import JobExtraction
from offerpilot.modules.jobs.service import save_extraction, validate_extraction
from offerpilot.providers.base import (
    ContentProvider,
    LLMProvider,
    ProviderError,
    SearchProvider,
    SearchResult,
    Usage,
)
from offerpilot.providers.urls import canonical_url, validate_public_dns
from offerpilot.worker.context import Context
from offerpilot.worker.queue import guarded
from pydantic import JsonValue
from sqlalchemy import select


async def search_jobs(
    ctx: Context, llm: LLMProvider, search: SearchProvider, content: ContentProvider
) -> None:
    spec = SpecInput.model_validate(ctx.run.inputs["spec"])
    if not spec.confirmed:
        raise DomainError("search_unconfirmed", "搜索条件尚未确认")
    if spec.natural_language:
        raw_scope = await ctx.generate(
            "parse_scope", "search_parse", SpecInput, {"text": spec.keywords}, llm.generate_json
        )
        spec = preserve_scope(spec, SpecInput.model_validate(raw_scope))
    queries = search_queries(spec)
    counts: dict[str, JsonValue] = {
        key: 0
        for key in [
            "raw_links",
            "unique_urls",
            "extracted_pages",
            "new_jobs",
            "updated_jobs",
            "duplicate_links",
            "rejected_non_job",
            "partial_candidates",
            "errors",
        ]
    }
    errors: list[JsonValue] = []
    requests_ok = 0
    seen: set[str] = set()
    for index, query in enumerate(queries):
        try:

            async def call_search(query: str = query) -> tuple[dict[str, JsonValue], Usage]:
                result = await search.search(query, spec.max_results)
                return result.model_dump(mode="json"), result.usage

            raw = await ctx.call(
                f"search:q{index:02}",
                "search",
                {"query": query, "max_results": spec.max_results},
                call_search,
            )
            response = SearchResult.model_validate(raw)
            requests_ok += 1
            for hit in response.results:
                counts["raw_links"] = int(str(counts["raw_links"])) + 1
                try:
                    url = canonical_url(hit.url)
                except DomainError:
                    errors.append({"code": "invalid_candidate_url"})
                    continue
                if url in seen:
                    counts["duplicate_links"] = int(str(counts["duplicate_links"])) + 1
                    continue
                seen.add(url)
                async with Session() as db:
                    run = await guarded(db, ctx.run.owner_id, ctx.run.id, ctx.token)
                    policy = await allowed_source(db, url, "jobs")
                    if policy and policy.mode == "disabled":
                        continue
                    row = await db.scalar(
                        select(SearchCandidate).where(
                            SearchCandidate.run_id == run.id, SearchCandidate.url == url
                        )
                    )
                    if not row:
                        row = SearchCandidate(
                            owner_id=run.owner_id,
                            run_id=run.id,
                            url=url,
                            title=hit.title[:500],
                            summary=hit.content[:5000]
                            if not policy or policy.store_excerpt
                            else "",
                            query=query,
                        )
                        db.add(row)
                        await db.commit()
                counts["unique_urls"] = int(str(counts["unique_urls"])) + 1
        except ProviderError as exc:
            errors.append({"query_index": index, "code": exc.code})
    async with Session() as db:
        candidates = list(
            await db.scalars(
                select(SearchCandidate)
                .where(SearchCandidate.run_id == ctx.run.id)
                .order_by(SearchCandidate.id)
            )
        )
    for index, candidate in enumerate(candidates):
        if candidate.job_id:
            continue
        try:
            async with Session() as db:
                await guarded(db, ctx.run.owner_id, ctx.run.id, ctx.token)
                policy = await extraction_permission(db, candidate.url, "jobs")
            if not policy or index >= spec.max_extracts:
                counts["partial_candidates"] = int(str(counts["partial_candidates"])) + 1
                continue

            if settings().app_mode == "live":
                await validate_public_dns(candidate.url)

            async def call_content(
                url: str = candidate.url, policy: SourcePolicy | None = policy
            ) -> tuple[dict[str, JsonValue], Usage]:
                result = await content.extract([url])
                # store_text=false: retain only allowed excerpts, never hide a full text in steps.
                if not policy or not policy.store_text:
                    result.texts = (
                        {u: t[:1500] for u, t in result.texts.items()}
                        if policy and policy.store_excerpt
                        else {}
                    )
                return result.model_dump(mode="json"), result.usage

            from offerpilot.providers.base import ContentResult

            extracted = ContentResult.model_validate(
                await ctx.call(
                    f"extract:{candidate.id}", "content", {"url": candidate.url}, call_content
                )
            )
            body = extracted.texts.get(candidate.url)
            if not body:
                raise ProviderError("content_unavailable")
            counts["extracted_pages"] = int(str(counts["extracted_pages"])) + 1
            if not policy.store_text:
                raise ProviderError("excerpt_only")

            def validate(raw: dict[str, JsonValue], body: str | None = body) -> None:
                validate_extraction(JobExtraction.model_validate(raw), body or "")

            raw = await ctx.generate(
                f"normalize:{candidate.id}",
                "job_normalize",
                JobExtraction,
                {"text": body, "source_kind": "provider_extracted"},
                llm.generate_json,
                validate,
            )
            job_data = JobExtraction.model_validate(raw)
            async with Session() as db:
                run = await guarded(db, ctx.run.owner_id, ctx.run.id, ctx.token)
                # Policy may have been disabled while the remote request was in flight.
                permission = await extraction_permission(db, candidate.url, "jobs")
                if permission is None or not permission.store_text:
                    raise DomainError("source_policy_changed", "来源策略已变更")
                row = await db.get(SearchCandidate, candidate.id)
                if row is None:
                    raise DomainError("input_deleted", "候选已删除")
                if job_data.classification == "job_detail":
                    job, created = await save_extraction(
                        db, run.owner_id, job_data, body, candidate.url, "provider_extracted"
                    )
                    row.job_id, row.status = job.id, "job_saved"
                    field = "new_jobs" if created else "updated_jobs"
                    counts[field] = int(str(counts[field])) + 1
                    from offerpilot.modules.runs.service import event

                    event(db, run, "candidate_saved", {"job_id": str(job.id)})
                else:
                    row.status = job_data.classification
                    counts["rejected_non_job"] = int(str(counts["rejected_non_job"])) + 1
                run.result = {"counts": dict(counts), "errors": list(errors)}
                await db.commit()
        except (ProviderError, DomainError) as exc:
            if isinstance(exc, DomainError) and exc.code in {
                "budget_exhausted",
                "run_cancelled",
                "input_deleted",
            }:
                raise
            errors.append({"candidate_id": str(candidate.id), "code": exc.code})
            counts["partial_candidates"] = int(str(counts["partial_candidates"])) + 1
            async with Session() as db:
                await guarded(db, ctx.run.owner_id, ctx.run.id, ctx.token)
                row = await db.get(SearchCandidate, candidate.id)
                if row:
                    row.status, row.error_code = "partial", exc.code
                await db.commit()
    counts["errors"] = len(errors)
    if requests_ok:
        async with Session() as db:
            run = await guarded(db, ctx.run.owner_id, ctx.run.id, ctx.token)
            run.result = {
                "counts": dict(counts),
                "errors": list(errors),
                "queries": list(queries),
                "resolved_spec": spec.model_dump(mode="json"),
            }
            await db.commit()
    from offerpilot.workflows.opportunities import organize_candidates

    organization, organization_errors = await organize_candidates(ctx, llm, ctx.run.id, spec)
    counts.update(organization)
    errors.extend(organization_errors)
    counts["errors"] = len(errors)
    async with Session() as db:
        await guarded(db, ctx.run.owner_id, ctx.run.id, ctx.token)
        await ctx.publish(
            db,
            {
                "counts": counts,
                "errors": errors,
                "queries": list(queries),
                "resolved_spec": spec.model_dump(mode="json"),
                "counting_note": "raw_links 含重复；unique_urls 为去重线索；岗位/失败为处理结果，风险与资格另算",
            },
            partial=bool(errors) and requests_ok > 0,
            failed=requests_ok == 0,
        )
