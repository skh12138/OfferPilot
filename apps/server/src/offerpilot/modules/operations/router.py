from datetime import datetime
from uuid import UUID

from fastapi import APIRouter
from offerpilot.api.deps import DB, Admin, Current, Write
from offerpilot.api.errors import DomainError
from offerpilot.api.schemas import Page
from offerpilot.infrastructure.config import settings
from offerpilot.infrastructure.db import now
from offerpilot.infrastructure.owned import check_revision, get_owned
from offerpilot.modules.discovery.models import SourcePolicy
from offerpilot.modules.discovery.schemas import PolicyDTO, PolicyInput, PolicyPatch
from offerpilot.modules.operations import service
from offerpilot.modules.operations.models import FeedbackReport
from offerpilot.modules.operations.schemas import (
    OperationsDTO,
    OverviewDTO,
    ReportDTO,
    ReportInput,
    Resolution,
)
from offerpilot.modules.runs.models import AgentRun, AuditEvent, ProviderCall
from sqlalchemy import func, select

router = APIRouter(tags=["operations"])


@router.post("/feedback-reports", response_model=ReportDTO, status_code=201)
async def report(data: ReportInput, user: Current, db: DB, _: Write) -> ReportDTO:
    if data.shared_excerpt and not data.share_confirmed:
        raise DomainError("sharing_confirmation_required", "请确认主动向运营分享这段内容", 422)
    if data.target_id:
        from offerpilot.modules.applications.models import Application
        from offerpilot.modules.interview.models import Question
        from offerpilot.modules.jobs.models import Job

        if data.target_kind == "job":
            await get_owned(db, Job, user.id, data.target_id)
        elif data.target_kind == "question":
            await get_owned(db, Question, user.id, data.target_id)
        elif data.target_kind == "application":
            await get_owned(db, Application, user.id, data.target_id)
    row = FeedbackReport(owner_id=user.id, **data.model_dump(exclude={"share_confirmed"}))
    db.add(row)
    await db.commit()
    return ReportDTO.model_validate(row)


@router.get("/feedback-reports/mine", response_model=Page[ReportDTO])
async def mine(user: Current, db: DB) -> Page[ReportDTO]:
    rows = await db.scalars(
        select(FeedbackReport)
        .where(FeedbackReport.owner_id == user.id)
        .order_by(FeedbackReport.created_at.desc())
        .limit(100)
    )
    return Page(items=[ReportDTO.model_validate(r) for r in rows])


@router.get("/admin/source-policies", response_model=Page[PolicyDTO])
async def policies(user: Admin, db: DB) -> Page[PolicyDTO]:
    rows = await db.scalars(select(SourcePolicy).order_by(SourcePolicy.domain).limit(100))
    return Page(items=[PolicyDTO.model_validate(r) for r in rows])


@router.post("/admin/source-policies", response_model=PolicyDTO, status_code=201)
async def create_policy(data: PolicyInput, user: Admin, db: DB, _: Write) -> PolicyDTO:
    return PolicyDTO.model_validate(await service.save_policy(db, user.id, data))


@router.patch("/admin/source-policies/{policy_id}", response_model=PolicyDTO)
async def update_policy(
    policy_id: UUID, data: PolicyPatch, user: Admin, db: DB, _: Write
) -> PolicyDTO:
    return PolicyDTO.model_validate(await service.save_policy(db, user.id, data, policy_id))


@router.get("/admin/feedback-reports", response_model=Page[ReportDTO])
async def reports(user: Admin, db: DB) -> Page[ReportDTO]:
    rows = await db.scalars(
        select(FeedbackReport).order_by(FeedbackReport.created_at.desc()).limit(100)
    )
    return Page(items=[ReportDTO.model_validate(r) for r in rows])


@router.post("/admin/feedback-reports/{report_id}/resolution", response_model=ReportDTO)
async def resolve(report_id: UUID, data: Resolution, user: Admin, db: DB, _: Write) -> ReportDTO:
    row = await db.get(FeedbackReport, report_id, with_for_update=True)
    if not row:
        raise DomainError("not_found", "举报不存在", 404)
    check_revision(row.revision, data.expected_revision)
    row.status, row.resolution, row.revision = data.status, data.resolution, row.revision + 1
    db.add(
        AuditEvent(
            owner_id=user.id, action="report_resolved", target_id=row.id, details=data.status
        )
    )
    await db.commit()
    return ReportDTO.model_validate(row)


@router.get("/admin/overview", response_model=OperationsDTO)
async def operations(user: Admin, db: DB) -> OperationsDTO:
    states = (
        await db.execute(select(AgentRun.status, func.count()).group_by(AgentRun.status))
    ).all()
    failures = (
        await db.execute(
            select(AgentRun.error_code, func.count())
            .where(AgentRun.error_code.is_not(None))
            .group_by(AgentRun.error_code)
        )
    ).all()
    unknown = await db.scalar(
        select(func.count())
        .select_from(ProviderCall)
        .where(
            ProviderCall.usage.is_(None) | ProviderCall.usage["input_tokens"].as_string().is_(None)
        )
    )
    reserved = await db.scalar(select(func.count()).select_from(ProviderCall))
    cfg = settings()
    return OperationsDTO(
        providers={
            "search": bool(cfg.tavily_api_key.get_secret_value()),
            "llm": bool(cfg.deepseek_api_key.get_secret_value()),
        },
        queue_states={str(k): v for k, v in states},
        failure_codes={str(k): v for k, v in failures},
        unknown_usage_calls=unknown or 0,
        reserved_calls=reserved or 0,
    )


@router.get("/reports/overview", response_model=OverviewDTO)
async def overview(user: Current, db: DB, from_date: datetime | None = None) -> OverviewDTO:
    from offerpilot.modules.applications.models import Application, ApplicationSubmission
    from offerpilot.modules.interview.models import ReviewItem
    from offerpilot.modules.tasks.models import Task

    query = select(Application).where(Application.owner_id == user.id)
    if from_date:
        query = query.where(Application.created_at >= from_date)
    apps = list(await db.scalars(query))
    stages = {
        stage: sum(a.stage == stage for a in apps)
        for stage in [
            "interested",
            "preparing",
            "submitted",
            "assessment",
            "offer",
            "onboarding",
            "closed",
        ]
    }
    submitted = await db.scalar(
        select(func.count())
        .select_from(ApplicationSubmission)
        .where(
            ApplicationSubmission.owner_id == user.id,
            ApplicationSubmission.application_id.in_([a.id for a in apps]),
            ApplicationSubmission.correction_of.is_(None),
        )
    )
    task_counts = (
        await db.execute(
            select(Task.status, func.count()).where(Task.owner_id == user.id).group_by(Task.status)
        )
    ).all()
    weak = await db.scalars(
        select(ReviewItem.topic)
        .where(ReviewItem.owner_id == user.id, ReviewItem.mastery == "needs_review")
        .distinct()
    )
    return OverviewDTO(
        from_date=from_date,
        to_date=now(),
        sample_size=len(apps),
        stages=stages,
        actual_submissions=submitted or 0,
        waiting_or_unknown=sum(
            a.company_status_kind in {"waiting", "unknown", "talent_pool"} for a in apps
        ),
        task_statuses={str(k): v for k, v in task_counts},
        weak_topics=list(weak),
        note="仅描述本人记录；等待反馈不计作拒绝，不计算录用概率。",
    )
