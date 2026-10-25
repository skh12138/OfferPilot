from urllib.parse import urlsplit

from offerpilot.modules.discovery.models import (
    SearchCandidate,
    SearchCandidateAnalysis,
    SourcePolicy,
)
from offerpilot.modules.interview.models import (
    AnswerAttempt,
    AnswerFeedback,
    InterviewSource,
    Question,
    ReviewItem,
    StudyPackageVersion,
)
from offerpilot.modules.runs.models import AgentRun, RunStep
from offerpilot.modules.tasks.models import Task
from pydantic import JsonValue
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession


async def tighten_retention(db: AsyncSession, policy: SourcePolicy) -> None:
    """Purge by structured URL/source/version references, never by matching private body text."""
    if policy.mode == "extract_allowed" and policy.store_text:
        return
    candidates = list(
        await db.scalars(
            select(SearchCandidate).where(
                SearchCandidate.url.like(f"https://{policy.domain}/%")
                | SearchCandidate.url.like(f"http://{policy.domain}/%")
            )
        )
    )
    candidate_ids = [candidate.id for candidate in candidates]
    analyses = await db.scalars(
        select(SearchCandidateAnalysis).where(
            SearchCandidateAnalysis.candidate_id.in_(candidate_ids)
        )
    )
    for analysis in analyses:
        if (
            policy.mode == "disabled"
            or not policy.store_excerpt
            or analysis.data.get("basis") == "job_text"
        ):
            analysis.data = {}
    if policy.mode == "disabled" or not policy.store_excerpt:
        for candidate in candidates:
            candidate.summary = ""
    source_runs = {candidate.run_id for candidate in candidates}
    organizing_runs = list(
        await db.scalars(
            select(AgentRun.id).where(
                AgentRun.kind == "search_organize",
                AgentRun.inputs["source_search_run_id"]
                .as_string()
                .in_([str(run_id) for run_id in source_runs]),
            )
        )
    )
    await db.execute(
        update(RunStep)
        .where(
            RunStep.run_id.in_([*source_runs, *organizing_runs]),
            RunStep.step_key.like("organize:%"),
        )
        .values(result={})
    )
    keys = {f"{kind}:{c.id}" for c in candidates for kind in ["extract", "normalize"]}
    refresh_runs = list(
        await db.scalars(
            select(AgentRun.id).where(
                AgentRun.kind == "job_refresh",
                AgentRun.inputs["url"].as_string().like(f"https://{policy.domain}/%"),
            )
        )
    )
    steps = await db.scalars(
        select(RunStep).where(
            RunStep.step_key.in_(keys)
            | RunStep.run_id.in_(refresh_runs)
            | RunStep.step_key.like("interview:extract:%")
        )
    )
    for step in steps:
        texts = step.result.get("texts")
        if step.step_key in keys or step.run_id in refresh_runs:
            step.result = {}
        elif isinstance(texts, dict) and any(
            urlsplit(url).hostname == policy.domain for url in texts
        ):
            step.result = {}
    source_ids = {
        str(s)
        for s in await db.scalars(
            select(InterviewSource.id).where(
                InterviewSource.url.like(f"https://{policy.domain}/%")
                | InterviewSource.url.like(f"http://{policy.domain}/%")
            )
        )
    }
    from offerpilot.modules.jobs.models import JobVersion, TextSnapshot
    from offerpilot.modules.preparation.models import BundleVersion

    snapshots = list(
        await db.scalars(
            select(TextSnapshot.id).where(
                TextSnapshot.url.like(f"https://{policy.domain}/%")
                | TextSnapshot.url.like(f"http://{policy.domain}/%")
            )
        )
    )
    job_ids = list(
        await db.scalars(select(JobVersion.id).where(JobVersion.snapshot_id.in_(snapshots)))
    )
    bundles = list(
        await db.scalars(select(BundleVersion).where(BundleVersion.job_version_id.in_(job_ids)))
    )
    for bundle in bundles:
        bundle.deleted, bundle.data, bundle.reason = True, {}, "来源策略变更，内容已清理"
    await db.execute(
        update(Task)
        .where(Task.bundle_version_id.in_([b.id for b in bundles]))
        .values(
            status="cancelled",
            title="来源策略变更，内容已清理",
            deliverable="",
            acceptance="",
            history=[],
            revision=Task.revision + 1,
        )
    )
    affected = list(
        await db.scalars(
            select(StudyPackageVersion.id).where(StudyPackageVersion.job_version_id.in_(job_ids))
        )
    )
    from offerpilot.modules.applications.models import Application

    app_ids = select(Application.id).where(Application.job_version_id.in_(job_ids))
    job_runs = list(
        await db.scalars(
            select(AgentRun.id).where(
                AgentRun.application_id.in_(app_ids)
                | AgentRun.inputs["job_version_id"].as_string().in_([str(j) for j in job_ids])
                | AgentRun.result["bundle_id"].as_string().in_([str(b.bundle_id) for b in bundles])
            )
        )
    )
    await db.execute(update(RunStep).where(RunStep.run_id.in_(job_runs)).values(result={}))
    questions = await db.scalars(select(Question).where(Question.data["source_refs"].is_not(None)))
    for q in questions:
        refs: list[JsonValue] = []
        raw_refs = q.data.get("source_refs")
        raw_inspired = q.data.get("inspired_by")
        if isinstance(raw_refs, list):
            refs.extend(raw_refs)
        if isinstance(raw_inspired, list):
            refs.extend(raw_inspired)
        if any(isinstance(ref, dict) and str(ref.get("source_id")) in source_ids for ref in refs):
            affected.append(q.package_version_id)
    if not affected:
        return
    versions = list(
        await db.scalars(select(StudyPackageVersion).where(StudyPackageVersion.id.in_(affected)))
    )
    package_ids = {str(v.package_id) for v in versions}
    question_ids = list(
        await db.scalars(select(Question.id).where(Question.package_version_id.in_(affected)))
    )
    attempt_ids = list(
        await db.scalars(
            select(AnswerAttempt.id).where(AnswerAttempt.question_id.in_(question_ids))
        )
    )
    await db.execute(delete(AnswerFeedback).where(AnswerFeedback.attempt_id.in_(attempt_ids)))
    await db.execute(
        update(AnswerAttempt).where(AnswerAttempt.id.in_(attempt_ids)).values(answer=None)
    )
    await db.execute(delete(ReviewItem).where(ReviewItem.question_id.in_(question_ids)))
    await db.execute(update(Question).where(Question.id.in_(question_ids)).values(data={}))
    for version in versions:
        version.data, version.deleted = {}, True
    await db.execute(
        update(Task)
        .where(Task.study_version_id.in_(affected))
        .values(
            status="cancelled",
            title="来源策略变更，内容已清理",
            deliverable="",
            acceptance="",
            history=[],
            revision=Task.revision + 1,
        )
    )
    run_ids = list(
        await db.scalars(
            select(AgentRun.id).where(
                AgentRun.result["study_package_id"].as_string().in_(package_ids)
            )
        )
    )
    await db.execute(update(RunStep).where(RunStep.run_id.in_(run_ids)).values(result={}))
