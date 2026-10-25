from uuid import UUID

from offerpilot.api.errors import DomainError
from offerpilot.api.schemas import digest
from offerpilot.infrastructure.config import settings
from offerpilot.infrastructure.db import Session
from offerpilot.infrastructure.owned import get_owned
from offerpilot.modules.applications.models import Application
from offerpilot.modules.discovery.service import extraction_permission
from offerpilot.modules.interview.models import (
    AnswerAttempt,
    AnswerFeedback,
    InterviewSource,
    Question,
    ReviewItem,
    StudyPackage,
    StudyPackageVersion,
)
from offerpilot.modules.interview.rules import validate_questions
from offerpilot.modules.interview.schemas import FeedbackPayload, StudyPayload
from offerpilot.modules.interview.service import active_version, store_questions
from offerpilot.modules.jobs.models import JobVersion
from offerpilot.modules.jobs.schemas import JobExtraction
from offerpilot.modules.profiles.service import confirmed_facts
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


async def collect_sources(
    ctx: Context,
    search: SearchProvider,
    content: ContentProvider,
    query: str,
    company: str,
    role: str,
) -> list[InterviewSource]:
    from offerpilot.modules.discovery.schemas import SpecInput
    from offerpilot.modules.discovery.service import search_queries

    search_queries(SpecInput(keywords=query))

    async def call_search() -> tuple[dict[str, JsonValue], Usage]:
        result = await search.search(query, 5)
        return result.model_dump(mode="json"), result.usage

    raw = await ctx.call("interview:search", "search", {"query": query}, call_search)
    hits = SearchResult.model_validate(raw).results
    for hit in hits:
        try:
            url = canonical_url(hit.url)
        except DomainError:
            continue
        evidence: str | None = None
        status = "metadata_only"
        async with Session() as db:
            policy = await extraction_permission(db, url, "interview")
        if policy:
            if settings().app_mode == "live":
                await validate_public_dns(url)

            async def call_content(
                url: str = url, store: bool = bool(policy and policy.store_excerpt)
            ) -> tuple[dict[str, JsonValue], Usage]:
                result = await content.extract([url])
                result.texts = {u: t[:1500] for u, t in result.texts.items()} if store else {}
                return result.model_dump(mode="json"), result.usage

            try:
                from offerpilot.providers.base import ContentResult

                result = ContentResult.model_validate(
                    await ctx.call(
                        "interview:extract:" + digest(url), "content", {"url": url}, call_content
                    )
                )
                evidence = result.texts.get(url)
                status = "excerpt" if evidence else "unreadable"
            except ProviderError:
                status = "unreadable"
        async with Session() as db:
            await guarded(db, ctx.run.owner_id, ctx.run.id, ctx.token)
            row = await db.scalar(
                select(InterviewSource).where(
                    InterviewSource.owner_id == ctx.run.owner_id, InterviewSource.url == url
                )
            )
            if not row:
                row = InterviewSource(
                    owner_id=ctx.run.owner_id,
                    url=url,
                    company=company,
                    role=role,
                    summary=hit.content[:1500],
                    evidence=evidence,
                    independent_group=digest(evidence or hit.content.strip()),
                    content_status=status,
                )
                db.add(row)
            await db.commit()
    async with Session() as db:
        rows = await db.scalars(
            select(InterviewSource)
            .where(
                InterviewSource.owner_id == ctx.run.owner_id,
                InterviewSource.company == company,
                InterviewSource.role == role,
            )
            .limit(20)
        )
        return list(rows)


async def study(
    ctx: Context, llm: LLMProvider, search: SearchProvider, content: ContentProvider
) -> None:
    async with Session() as db:
        job_id = UUID(str(ctx.run.inputs["job_version_id"]))
        job = await get_owned(db, JobVersion, ctx.run.owner_id, job_id)
        job_data = JobExtraction.model_validate(job.data)
        facts = await confirmed_facts(db, ctx.run.owner_id, ctx.run.profile_version_id)
    from offerpilot.modules.profiles.rules import relevant_facts

    facts = relevant_facts(facts, job_data)
    round_context: dict[str, JsonValue] = {}
    reviews_context: list[JsonValue] = []
    weak_topics: list[JsonValue] = []
    async with Session() as db:
        if ctx.run.inputs.get("round_id"):
            from offerpilot.modules.applications.models import AssessmentRound

            rnd = await get_owned(
                db, AssessmentRound, ctx.run.owner_id, UUID(str(ctx.run.inputs["round_id"]))
            )
            if rnd.application_id != ctx.run.application_id:
                raise DomainError("invalid_parent", "考核与申请不一致", 404)
            round_context = {
                "name": rnd.name,
                "type": rnd.type,
                "planned_at": rnd.planned_at.isoformat() if rnd.planned_at else None,
            }
        if ctx.run.application_id:
            from offerpilot.modules.interview.models import InterviewReview

            rows = await db.scalars(
                select(InterviewReview)
                .where(
                    InterviewReview.owner_id == ctx.run.owner_id,
                    InterviewReview.application_id == ctx.run.application_id,
                )
                .order_by(InterviewReview.created_at.desc())
                .limit(3)
            )
            reviews_context = [
                {
                    "questions_asked": r.questions_asked,
                    "explicit_feedback": r.explicit_feedback,
                    "user_inference": r.user_inference,
                    "next_steps": r.next_steps,
                }
                for r in rows
            ]
        weak = await db.scalars(
            select(ReviewItem.topic)
            .where(ReviewItem.owner_id == ctx.run.owner_id, ReviewItem.mastery == "needs_review")
            .limit(10)
        )
        weak_topics = list(weak)
    sources: list[InterviewSource] = []
    limits: list[str] = []
    if ctx.run.inputs.get("include_interview_search", True):
        try:
            sources = await collect_sources(
                ctx,
                search,
                content,
                f"{job_data.company} {job_data.title} 面经",
                job_data.company,
                job_data.title,
            )
        except ProviderError as exc:
            limits.append(f"面经查询失败：{exc.code}；改用目标岗位生成题")
    supported = {str(s.id): s.evidence for s in sources if s.evidence}

    def validate(raw: dict[str, JsonValue]) -> None:
        payload = StudyPayload.model_validate(raw)
        if len(payload.questions) != int(str(ctx.run.inputs.get("count", 8))):
            raise DomainError("question_count", "题量与用户确认不符")
        validate_questions(payload, job_data, facts, supported)

    raw = await ctx.generate(
        "generate_question_batch",
        "study_prepare",
        StudyPayload,
        {
            "job": job.data,
            "round": round_context,
            "previous_reviews": reviews_context,
            "weak_topics": weak_topics,
            "interview_date": ctx.run.inputs.get("interview_date"),
            "facts": [f.model_dump(mode="json") for f in facts],
            "sources": [
                {"source_id": str(s.id), "excerpt": s.evidence, "applicability": s.applicability}
                for s in sources
                if s.evidence
            ],
            "count": ctx.run.inputs.get("count", 8),
        },
        llm.generate_json,
        validate,
        max_tokens=8192,
    )
    payload = StudyPayload.model_validate(raw)
    payload.limitations.extend(limits)
    if not supported:
        payload.limitations.append("未找到可读且相关的面经正文；不声称企业历史真题。")
    async with Session() as db:
        await guarded(db, ctx.run.owner_id, ctx.run.id, ctx.token)
        basis = int(str(ctx.run.inputs["basis_revision"]))
        if ctx.run.application_id:
            app = await get_owned(db, Application, ctx.run.owner_id, ctx.run.application_id)
            if app.basis_revision != basis:
                raise DomainError("basis_changed", "准备基准已更新")
        current_facts = await confirmed_facts(db, ctx.run.owner_id, ctx.run.profile_version_id)
        validate_questions(payload, job_data, current_facts, supported)
        package = StudyPackage(owner_id=ctx.run.owner_id, application_id=ctx.run.application_id)
        db.add(package)
        await db.flush()
        data = payload.model_dump(mode="json")
        version = StudyPackageVersion(
            owner_id=ctx.run.owner_id,
            package_id=package.id,
            job_version_id=job_id,
            profile_version_id=ctx.run.profile_version_id,
            submission_id=UUID(str(ctx.run.inputs["submission_id"]))
            if ctx.run.inputs.get("submission_id")
            else None,
            round_id=UUID(str(ctx.run.inputs["round_id"]))
            if ctx.run.inputs.get("round_id")
            else None,
            basis_revision=basis,
            data=data,
            payload_hash=digest(data),
            model=ctx.run.model,
            prompt_version=ctx.run.prompt_version,
        )
        db.add(version)
        await db.flush()
        await store_questions(db, version, payload)
        package.current_version_id = version.id
        await ctx.publish(
            db,
            {
                "study_package_id": str(package.id),
                "source_count": len(sources),
                "independent_sources": len({s.independent_group for s in sources}),
                "readable_sources": len(supported),
            },
        )


async def feedback(ctx: Context, llm: LLMProvider) -> None:
    async with Session() as db:
        attempt = await get_owned(
            db, AnswerAttempt, ctx.run.owner_id, UUID(str(ctx.run.inputs["attempt_id"]))
        )
        if attempt.answer is None:
            raise DomainError("input_deleted", "回答已删除")
        question = await get_owned(db, Question, ctx.run.owner_id, attempt.question_id)
        version = await active_version(db, ctx.run.owner_id, question.package_version_id)
        facts = await confirmed_facts(db, ctx.run.owner_id, version.profile_version_id)
        answer = attempt.answer

    def validate(raw: dict[str, JsonValue]) -> None:
        payload = FeedbackPayload.model_validate(raw)
        if any(f not in {fact.fact_id for fact in facts} for f in payload.fact_ids):
            raise DomainError("invalid_fact_reference", "反馈引用不受当前事实支持")
        if set(payload.levels) != {
            "correctness",
            "completeness",
            "structure",
            "evidence",
            "relevance",
        }:
            raise DomainError("feedback_dimensions", "反馈维度不完整")

    raw = await ctx.generate(
        "evaluate_by_rubric",
        "feedback",
        FeedbackPayload,
        {
            "question": question.data,
            "answer": answer,
            "facts": [f.model_dump(mode="json") for f in facts],
        },
        llm.generate_json,
        validate,
    )
    async with Session() as db:
        await guarded(db, ctx.run.owner_id, ctx.run.id, ctx.token)
        await active_version(db, ctx.run.owner_id, question.package_version_id)
        attempt = await get_owned(db, AnswerAttempt, ctx.run.owner_id, attempt.id)
        if attempt.answer is None:
            raise DomainError("input_deleted", "回答已删除")
        old = await db.scalar(
            select(AnswerFeedback)
            .where(
                AnswerFeedback.owner_id == ctx.run.owner_id, AnswerFeedback.attempt_id == attempt.id
            )
            .order_by(AnswerFeedback.version.desc())
            .limit(1)
        )
        row = AnswerFeedback(
            owner_id=ctx.run.owner_id,
            attempt_id=attempt.id,
            version=old.version + 1 if old else 1,
            data=raw,
            model=ctx.run.model,
            prompt_version=ctx.run.prompt_version,
        )
        db.add(row)
        await db.flush()
        await ctx.publish(db, {"feedback_id": str(row.id), "attempt_id": str(attempt.id)})
