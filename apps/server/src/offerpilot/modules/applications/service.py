from datetime import datetime
from uuid import UUID

from offerpilot.api.errors import DomainError
from offerpilot.infrastructure.db import now
from offerpilot.infrastructure.owned import check_revision, get_owned, lock_owner
from offerpilot.modules.applications.models import (
    Application,
    ApplicationEvent,
    ApplicationSubmission,
    AssessmentRound,
)
from offerpilot.modules.applications.rules import transition
from offerpilot.modules.applications.schemas import (
    ApplicationInput,
    BasisInput,
    EventInput,
    ProgressCheck,
    RoundInput,
    RoundPatch,
    SubmissionInput,
)
from offerpilot.modules.jobs.models import JobVersion
from offerpilot.modules.profiles.service import valid_profile
from offerpilot.modules.runs.service import idempotent, remember
from offerpilot.modules.tasks.models import Task
from offerpilot.providers.urls import canonical_url
from pydantic import JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def append_event(
    db: AsyncSession,
    app: Application,
    kind: str,
    target: str,
    reason: str,
    source: str,
    happened_at: "datetime",
    *,
    details: "dict[str, JsonValue] | None" = None,
) -> ApplicationEvent:
    row = ApplicationEvent(
        owner_id=app.owner_id,
        application_id=app.id,
        event_type=kind,
        from_stage=app.stage,
        to_stage=target,
        reason=reason,
        source=source,
        happened_at=happened_at,
        details=details or {},
    )
    db.add(row)
    app.stage, app.revision = target, app.revision + 1
    return row


async def create(
    db: AsyncSession, owner: UUID, data: ApplicationInput, key: str | None
) -> Application:
    await lock_owner(db, owner)
    payload = data.model_dump(mode="json")
    old = await idempotent(db, owner, "application", key, payload)
    if old:
        return await get_owned(db, Application, owner, old)
    if data.job_version_id:
        job = await get_owned(db, JobVersion, owner, data.job_version_id)
        versions = select(JobVersion.id).where(
            JobVersion.owner_id == owner, JobVersion.job_id == job.job_id
        )
        existing = await db.scalar(
            select(Application).where(
                Application.owner_id == owner,
                Application.job_version_id.in_(versions),
                Application.stage != "closed",
            )
        )
        if existing and not data.allow_reapply:
            raise DomainError(
                "active_application_exists", f"已有活跃申请 {existing.id}；可明确选择再次申请"
            )
    if data.profile_version_id:
        await valid_profile(db, owner, data.profile_version_id)
    values = data.model_dump(exclude={"allow_reapply"})
    for field in ["job_url", "apply_url", "progress_url"]:
        if values[field]:
            values[field] = canonical_url(str(values[field]))
    app = Application(owner_id=owner, **values)
    db.add(app)
    await db.flush()
    remember(db, owner, "application", str(key), payload, app.id)
    await db.commit()
    return app


async def record_event(
    db: AsyncSession, owner: UUID, app_id: UUID, data: EventInput, key: str | None
) -> Application:
    await lock_owner(db, owner)
    payload = data.model_dump(mode="json")
    op = f"event:{app_id}"
    old = await idempotent(db, owner, op, key, payload)
    if old:
        return await get_owned(db, Application, owner, old)
    app = await get_owned(db, Application, owner, app_id, lock=True)
    check_revision(app.revision, data.expected_revision)
    target = data.to_stage or app.stage
    if data.event_type not in {"note", "archive"}:
        transition(app.stage, target, data.event_type, data.reason, close_reason=data.close_reason)
    elif target != app.stage:
        raise DomainError("invalid_event", "备注或归档不能改变阶段")
    if data.correction_of_event_id:
        original = await get_owned(db, ApplicationEvent, owner, data.correction_of_event_id)
        if original.application_id != app_id:
            raise DomainError("not_found", "事件不存在", 404)
    details: dict[str, JsonValue] = {
        "close_reason": data.close_reason,
        "correction_of": str(data.correction_of_event_id) if data.correction_of_event_id else None,
    }
    append_event(
        db,
        app,
        data.event_type,
        target,
        data.reason,
        data.source,
        data.happened_at,
        details=details,
    )
    if data.is_archived is not None:
        app.is_archived = data.is_archived
    if data.onboarding_status:
        if target != "onboarding":
            raise DomainError("invalid_onboarding", "只有已接受阶段可以记录入职")
        app.onboarding_status = data.onboarding_status
    if target == "closed":
        tasks = await db.scalars(
            select(Task)
            .where(
                Task.owner_id == owner,
                Task.application_id == app_id,
                Task.status.notin_(["done", "cancelled"]),
            )
            .with_for_update()
        )
        for task in tasks:
            if data.task_action == "cancel":
                task.status = "cancelled"
            elif data.task_action == "detach":
                task.application_id, task.round_id = None, None
            task.revision += 1
    remember(db, owner, op, str(key), payload, app.id)
    await db.commit()
    return app


async def submit(
    db: AsyncSession, owner: UUID, app_id: UUID, data: SubmissionInput, key: str | None
) -> ApplicationSubmission:
    await lock_owner(db, owner)
    payload, op = data.model_dump(mode="json"), f"submission:{app_id}"
    old = await idempotent(db, owner, op, key, payload)
    if old:
        return await get_owned(db, ApplicationSubmission, owner, old)
    app = await get_owned(db, Application, owner, app_id, lock=True)
    check_revision(app.revision, data.expected_revision)
    if not data.actual_submission_confirmed:
        raise DomainError("actual_confirmation_required", "只有实际外部提交后才能记录", 422)
    if data.correction_of:
        prior = await get_owned(db, ApplicationSubmission, owner, data.correction_of)
        if prior.application_id != app_id or not data.correction_reason:
            raise DomainError("invalid_correction", "须引用本申请原提交并说明原因", 422)
    else:
        transition(app.stage, "submitted", "advance", "本人确认提交", evidence="submission")
    profile = (
        await valid_profile(db, owner, data.profile_version_id) if data.profile_version_id else None
    )
    if not profile and not data.missing_materials:
        raise DomainError("missing_materials", "未知历史材料须明确标记", 422)
    if data.job_version_id:
        await get_owned(db, JobVersion, owner, data.job_version_id)
    if data.material_version_ids:
        from offerpilot.modules.preparation.models import BundleVersion

        for material_id in data.material_version_ids:
            material = await get_owned(db, BundleVersion, owner, material_id)
            if material.application_id != app.id or material.deleted:
                raise DomainError("invalid_material", "材料不可用")
    row = ApplicationSubmission(
        owner_id=owner,
        application_id=app.id,
        submitted_at=data.submitted_at,
        channel=data.channel,
        external_application_id=data.external_application_id,
        job_version_id=data.job_version_id or app.job_version_id,
        profile_version_id=data.profile_version_id,
        resume_version_id=profile.resume_version_id if profile else None,
        material_version_ids=[str(v) for v in data.material_version_ids],
        missing_materials=data.missing_materials
        or ((not profile or not profile.resume_version_id) and not data.material_version_ids),
        correction_of=data.correction_of,
    )
    db.add(row)
    await db.flush()
    append_event(
        db,
        app,
        "submission_correction" if data.correction_of else "actual_submission",
        app.stage if data.correction_of else "submitted",
        data.correction_reason or "本人确认已在外部提交",
        data.channel,
        data.submitted_at,
        details={"submission_id": str(row.id)},
    )
    if not data.correction_of:
        app.profile_version_id = row.profile_version_id
        app.job_version_id = row.job_version_id
        app.basis_submission_id, app.basis_revision = row.id, app.basis_revision + 1
    remember(db, owner, op, str(key), payload, row.id)
    await db.commit()
    return row


async def progress(db: AsyncSession, owner: UUID, app_id: UUID, data: ProgressCheck) -> Application:
    await lock_owner(db, owner)
    app = await get_owned(db, Application, owner, app_id, lock=True)
    check_revision(app.revision, data.expected_revision)
    if not data.user_confirmed:
        raise DomainError("confirmation_required", "请本人确认已经查看官网", 422)
    app.last_checked_at = data.checked_at
    app.company_status_raw, app.company_status_kind = data.observed_status, data.company_status_kind
    append_event(
        db,
        app,
        "progress_check",
        app.stage,
        "已查看：有变化" if data.changed else "已查看：无变化",
        "user_external_check",
        data.checked_at,
    )
    await db.commit()
    return app


async def basis(db: AsyncSession, owner: UUID, app_id: UUID, data: BasisInput) -> Application:
    await lock_owner(db, owner)
    app = await get_owned(db, Application, owner, app_id, lock=True)
    check_revision(app.revision, data.expected_revision)
    if data.submission_id:
        submission = await get_owned(db, ApplicationSubmission, owner, data.submission_id)
        if submission.application_id != app.id:
            raise DomainError("not_found", "提交不存在", 404)
        app.job_version_id, app.profile_version_id = (
            submission.job_version_id,
            submission.profile_version_id,
        )
    else:
        if data.job_version_id:
            await get_owned(db, JobVersion, owner, data.job_version_id)
        if data.profile_version_id:
            await valid_profile(db, owner, data.profile_version_id)
        app.job_version_id, app.profile_version_id = data.job_version_id, data.profile_version_id
    app.basis_submission_id, app.basis_revision = data.submission_id, app.basis_revision + 1
    append_event(db, app, "basis_changed", app.stage, data.reason, "user", now())
    await db.commit()
    return app


async def sync_round_task(db: AsyncSession, row: AssessmentRound) -> None:
    key = f"round:{row.id}:attend"
    task = await db.scalar(
        select(Task)
        .where(Task.owner_id == row.owner_id, Task.business_action_id == key)
        .with_for_update()
    )
    if task:
        task.due_at, task.title = row.planned_at or row.deadline_at, row.name
        task.status = (
            "cancelled"
            if row.status in {"cancelled", "skipped"}
            else "done"
            if row.status in {"completed_waiting_result", "passed", "failed"}
            else "todo"
        )
        task.revision += 1
    elif row.reminders_enabled:
        db.add(
            Task(
                owner_id=row.owner_id,
                application_id=row.application_id,
                round_id=row.id,
                business_action_id=key,
                kind="interview_attend",
                title=row.name,
                due_at=row.planned_at or row.deadline_at,
                deliverable="参加并记录实际结果",
                acceptance="本人确认参加或取消",
            )
        )


async def add_round(
    db: AsyncSession, owner: UUID, app_id: UUID, data: RoundInput
) -> AssessmentRound:
    await lock_owner(db, owner)
    app = await get_owned(db, Application, owner, app_id, lock=True)
    transition(app.stage, "assessment", "advance", "录入实际考核", evidence="round")
    row = AssessmentRound(owner_id=owner, application_id=app.id, **data.model_dump())
    db.add(row)
    await db.flush()
    append_event(
        db,
        app,
        "round_added",
        "assessment",
        data.name,
        "user_notification",
        now(),
        details={"round_id": str(row.id)},
    )
    await sync_round_task(db, row)
    await db.commit()
    return row


async def update_round(
    db: AsyncSession, owner: UUID, round_id: UUID, data: RoundPatch
) -> AssessmentRound:
    await lock_owner(db, owner)
    row = await get_owned(db, AssessmentRound, owner, round_id, lock=True)
    check_revision(row.revision, data.expected_revision)
    app = await get_owned(db, Application, owner, row.application_id, lock=True)
    previous: dict[str, JsonValue] = {
        "status": row.status,
        "planned_at": row.planned_at.isoformat() if row.planned_at else None,
    }
    for name, value in data.model_dump(exclude={"expected_revision", "reason"}).items():
        setattr(row, name, value)
    row.revision += 1
    append_event(
        db,
        app,
        "round_updated",
        app.stage,
        data.reason,
        "user",
        now(),
        details={"round_id": str(row.id), "previous": previous},
    )
    await sync_round_task(db, row)
    await db.commit()
    return row
