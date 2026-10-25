"""Bounded AI organization of public search evidence; never substitutes for a verified JD."""

from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from offerpilot.api.errors import DomainError
from offerpilot.infrastructure.db import Session
from offerpilot.infrastructure.owned import get_owned
from offerpilot.modules.discovery.models import SearchCandidate, SearchCandidateAnalysis
from offerpilot.modules.discovery.opportunities import (
    IntelligenceBatch,
    IntelligenceDTO,
    check_scope,
    sanitize,
)
from offerpilot.modules.discovery.schemas import SpecInput
from offerpilot.modules.discovery.service import allowed_source
from offerpilot.modules.jobs.models import TextSnapshot
from offerpilot.modules.runs.models import AgentRun
from offerpilot.modules.runs.service import event
from offerpilot.providers.base import LLMProvider, ProviderError
from offerpilot.worker.context import Context
from offerpilot.worker.queue import guarded
from pydantic import JsonValue
from sqlalchemy import select


async def organize_candidates(
    ctx: Context, llm: LLMProvider, source_run_id: UUID, spec: SpecInput
) -> tuple[dict[str, JsonValue], list[JsonValue]]:
    async with Session() as db:
        await get_owned(db, AgentRun, ctx.run.owner_id, source_run_id)
        rows = list(
            await db.scalars(
                select(SearchCandidate)
                .where(
                    SearchCandidate.owner_id == ctx.run.owner_id,
                    SearchCandidate.run_id == source_run_id,
                )
                .order_by(SearchCandidate.created_at, SearchCandidate.id)
                .limit(48)
            )
        )
        contexts: list[dict[str, JsonValue]] = []
        for row in rows:
            policy = await allowed_source(db, row.url, "jobs")
            if policy and (policy.mode == "disabled" or not policy.store_excerpt):
                continue
            text, basis = row.title + "\n" + row.summary[:2400], "search_excerpt"
            if row.job_id and policy and policy.mode == "extract_allowed" and policy.store_text:
                snapshot = await db.scalar(
                    select(TextSnapshot)
                    .where(
                        TextSnapshot.owner_id == ctx.run.owner_id,
                        TextSnapshot.url == row.url,
                        TextSnapshot.text.is_not(None),
                    )
                    .order_by(TextSnapshot.created_at.desc())
                    .limit(1)
                )
                if snapshot and snapshot.text:
                    text, basis = row.title + "\n" + snapshot.text[:4500], "job_text"
            contexts.append(
                {
                    "candidate_id": str(row.id),
                    "title": row.title,
                    "url": row.url,
                    "evidence": text,
                    "basis": basis,
                }
            )
    errors: list[JsonValue] = []
    for offset in range(0, len(contexts), 3):
        batch = contexts[offset : offset + 3]
        expected = {str(item["candidate_id"]) for item in batch}
        step = "organize:" + sha256(",".join(sorted(expected)).encode()).hexdigest()[:20]

        def validate(raw: dict[str, JsonValue], expected: set[str] = expected) -> None:
            result = IntelligenceBatch.model_validate(raw)
            if (
                len(result.items) != len(expected)
                or {str(item.candidate_id) for item in result.items} != expected
            ):
                raise DomainError(
                    "invalid_candidate_reference",
                    "每个输入candidate_id须恰好整理一次，不能增加链接或遗漏",
                )

        try:
            batch_json: list[JsonValue] = [item for item in batch]
            raw = await ctx.generate(
                step,
                "search_organize",
                IntelligenceBatch,
                {
                    "search": spec.model_dump(mode="json"),
                    "candidates": batch_json,
                    "current_date": datetime.now(UTC).date().isoformat(),
                },
                llm.generate_json,
                validate,
                max_tokens=6144,
            )
            by_id = {str(item["candidate_id"]): item for item in batch}
            async with Session() as db:
                run = await guarded(db, ctx.run.owner_id, ctx.run.id, ctx.token)
                for generated in IntelligenceBatch.model_validate(raw).items:
                    source = by_id[str(generated.candidate_id)]
                    candidate = await get_owned(
                        db, SearchCandidate, run.owner_id, generated.candidate_id
                    )
                    policy = await allowed_source(db, candidate.url, "jobs")
                    if policy and (policy.mode == "disabled" or not policy.store_excerpt):
                        continue
                    if source["basis"] == "job_text" and (
                        not policy or policy.mode != "extract_allowed" or not policy.store_text
                    ):
                        continue
                    result = sanitize(generated, str(source["evidence"]))
                    for position in result.opportunities:
                        check_scope(position, spec.cities)
                    dto = IntelligenceDTO(
                        kind=result.kind,
                        opportunities=result.opportunities,
                        note=result.note,
                        basis="job_text" if source["basis"] == "job_text" else "search_excerpt",
                        prompt_version=run.prompt_version,
                    )
                    existing = await db.scalar(
                        select(SearchCandidateAnalysis.id).where(
                            SearchCandidateAnalysis.owner_id == run.owner_id,
                            SearchCandidateAnalysis.candidate_id == candidate.id,
                            SearchCandidateAnalysis.analysis_run_id == run.id,
                        )
                    )
                    if not existing:
                        db.add(
                            SearchCandidateAnalysis(
                                owner_id=run.owner_id,
                                candidate_id=candidate.id,
                                analysis_run_id=run.id,
                                data=dto.model_dump(mode="json"),
                            )
                        )
                    event(
                        db,
                        run,
                        "opportunity_ready",
                        {"candidate_id": str(candidate.id), "count": len(dto.opportunities)},
                    )
                await db.commit()
        except (DomainError, ProviderError) as exc:
            if exc.code in {"budget_exhausted", "run_cancelled", "input_deleted"}:
                raise
            errors.append({"step": step, "code": exc.code})
    async with Session() as db:
        versions = list(
            await db.scalars(
                select(SearchCandidateAnalysis).where(
                    SearchCandidateAnalysis.owner_id == ctx.run.owner_id,
                    SearchCandidateAnalysis.analysis_run_id == ctx.run.id,
                )
            )
        )
    positions = [
        p
        for version in versions
        if version.data
        for p in IntelligenceDTO.model_validate(version.data).opportunities
    ]
    identities = {(p.company, p.title, tuple(p.cities)) for p in positions}
    return {
        "organized_candidates": len(versions),
        "organized_positions": len(positions),
        "unique_opportunities": len(identities),
        "organization_errors": len(errors),
    }, errors


async def organize_existing(ctx: Context, llm: LLMProvider) -> None:
    source_id = UUID(str(ctx.run.inputs["source_search_run_id"]))
    async with Session() as db:
        source = await get_owned(db, AgentRun, ctx.run.owner_id, source_id)
        spec = SpecInput.model_validate(source.result.get("resolved_spec") or source.inputs["spec"])
    counts, errors = await organize_candidates(ctx, llm, source_id, spec)
    async with Session() as db:
        await guarded(db, ctx.run.owner_id, ctx.run.id, ctx.token)
        await ctx.publish(
            db,
            {"source_search_run_id": str(source_id), "counts": counts, "errors": errors},
            partial=bool(errors),
        )
