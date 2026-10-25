import secrets
from uuid import UUID

from argon2.exceptions import VerificationError
from offerpilot.api.errors import DomainError
from offerpilot.infrastructure.db import Base, Session, now
from offerpilot.infrastructure.owned import get_owned, lock_owner
from offerpilot.modules.control.models import DeletionRequest, ExportRequest
from offerpilot.modules.identity.models import SessionToken, User
from offerpilot.modules.identity.service import hasher, token_hash
from offerpilot.modules.profiles.models import FactRevocation, ProfileVersion, ResumeVersion
from offerpilot.modules.runs.models import AgentRun, RunStatus, RunStep
from offerpilot.modules.runs.service import enqueue, event, idempotent, remember
from offerpilot.worker.context import Context
from offerpilot.worker.queue import guarded
from pydantic import JsonValue
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession


async def request_resume_deletion(
    db: AsyncSession, owner: UUID, resume_id: UUID, key: str | None
) -> DeletionRequest:
    await lock_owner(db, owner)
    payload: dict[str, JsonValue] = {"resume_id": str(resume_id)}
    old = await idempotent(db, owner, "delete-resume", key, payload)
    if old:
        row = await db.get(DeletionRequest, old)
        if row:
            return row
    resume = await get_owned(db, ResumeVersion, owner, resume_id, lock=True)
    resume.deleted_at = now()
    profiles = list(
        await db.scalars(select(ProfileVersion).where(ProfileVersion.owner_id == owner))
    )
    direct = [p for p in profiles if p.resume_version_id == resume_id]
    fact_ids = {
        str(f["fact_id"])
        for p in direct
        for f in p.facts
        if isinstance(f, dict) and f.get("fact_id")
    }
    affected = [
        p
        for p in profiles
        if p in direct or any(isinstance(f, dict) and f.get("fact_id") in fact_ids for f in p.facts)
    ]
    for profile in affected:
        profile.unavailable = True
    existing = set(
        await db.scalars(select(FactRevocation.fact_id).where(FactRevocation.owner_id == owner))
    )
    for fact_id in fact_ids:
        if UUID(fact_id) not in existing:
            db.add(FactRevocation(owner_id=owner, fact_id=UUID(fact_id), reason="关联资料已删除"))
    ids = [p.id for p in affected]
    runs = await db.scalars(
        select(AgentRun)
        .where(
            AgentRun.owner_id == owner,
            AgentRun.status.in_([RunStatus.QUEUED, RunStatus.RUNNING]),
            or_(
                AgentRun.resume_version_id == resume_id,
                AgentRun.profile_version_id.in_(ids),
                AgentRun.kind == "export",
            ),
        )
        .with_for_update()
    )
    for run in runs:
        run.cancel_requested_at = now()
        if run.status == RunStatus.QUEUED:
            run.status = RunStatus.CANCELLED
            event(db, run, "run_cancelled")
    await db.execute(
        update(ExportRequest)
        .where(ExportRequest.owner_id == owner)
        .values(status="expired", payload=None, csv_text=None, expires_at=now())
    )
    deletion = DeletionRequest(
        owner_id=owner, kind="resume", target_id=resume_id, profile_ids=[str(p) for p in ids]
    )
    db.add(deletion)
    await db.flush()
    run = await enqueue(
        db, owner, "delete_resume", {"deletion_id": str(deletion.id)}, str(key), commit=False
    )
    deletion.run_id = run.id
    remember(db, owner, "delete-resume", str(key), payload, deletion.id)
    await db.commit()
    return deletion


async def request_account_deletion(
    db: AsyncSession, owner: UUID, password: str, key: str | None
) -> tuple[DeletionRequest, str]:
    user = await lock_owner(db, owner)
    valid: bool
    try:
        valid = hasher.verify(user.password_hash, password)
    except VerificationError:
        valid = False
    if not valid:
        raise DomainError("invalid_credentials", "密码验证失败", 401)
    from offerpilot.modules.runs.service import cancel_owner_runs

    await cancel_owner_runs(db, owner)
    receipt = secrets.token_urlsafe(48)
    deletion = DeletionRequest(owner_id=owner, kind="account", receipt_hash=token_hash(receipt))
    db.add(deletion)
    await db.flush()
    run = await enqueue(
        db, owner, "delete_account", {"deletion_id": str(deletion.id)}, key, commit=False
    )
    deletion.run_id = run.id
    user.disabled = True
    await db.execute(delete(SessionToken).where(SessionToken.owner_id == owner))
    await db.commit()
    return deletion, receipt


async def delete_resume(ctx: Context) -> None:
    from offerpilot.modules.applications.models import Application, ApplicationEvent
    from offerpilot.modules.interview.models import (
        AnswerAttempt,
        AnswerFeedback,
        Question,
        ReviewItem,
        StudyPackageVersion,
    )
    from offerpilot.modules.jobs.models import MatchReport
    from offerpilot.modules.preparation.models import BundleVersion
    from offerpilot.modules.tasks.models import Task

    async with Session() as db:
        await guarded(db, ctx.run.owner_id, ctx.run.id, ctx.token, validate_inputs=False)
        deletion = await db.get(
            DeletionRequest, UUID(str(ctx.run.inputs["deletion_id"])), with_for_update=True
        )
        if not deletion or deletion.owner_id != ctx.run.owner_id:
            raise DomainError("not_found", "删除请求不存在", 404)
        ids = [UUID(str(p)) for p in deletion.profile_ids]
        resume = (
            await get_owned(db, ResumeVersion, ctx.run.owner_id, deletion.target_id)
            if deletion.target_id
            else None
        )
        if resume:
            resume.text, resume.title = None, "资料已删除"
        await db.execute(
            update(ProfileVersion)
            .where(ProfileVersion.owner_id == ctx.run.owner_id, ProfileVersion.id.in_(ids))
            .values(facts=[], preferences={}, unavailable=True, reason="资料已删除")
        )
        await db.execute(
            update(MatchReport)
            .where(
                MatchReport.owner_id == ctx.run.owner_id, MatchReport.profile_version_id.in_(ids)
            )
            .values(checks=[], fact_ids=[], overall="unknown")
        )
        bundle_ids = list(
            await db.scalars(
                select(BundleVersion.id).where(
                    BundleVersion.owner_id == ctx.run.owner_id,
                    BundleVersion.profile_version_id.in_(ids),
                )
            )
        )
        await db.execute(
            update(BundleVersion)
            .where(BundleVersion.id.in_(bundle_ids))
            .values(data={}, deleted=True, reason="资料已删除")
        )
        study_ids = list(
            await db.scalars(
                select(StudyPackageVersion.id).where(
                    StudyPackageVersion.owner_id == ctx.run.owner_id,
                    StudyPackageVersion.profile_version_id.in_(ids),
                )
            )
        )
        question_ids = list(
            await db.scalars(
                select(Question.id).where(
                    Question.owner_id == ctx.run.owner_id,
                    Question.package_version_id.in_(study_ids),
                )
            )
        )
        attempt_ids = list(
            await db.scalars(
                select(AnswerAttempt.id).where(
                    AnswerAttempt.owner_id == ctx.run.owner_id,
                    AnswerAttempt.question_id.in_(question_ids),
                )
            )
        )
        await db.execute(
            delete(AnswerFeedback).where(
                AnswerFeedback.owner_id == ctx.run.owner_id,
                AnswerFeedback.attempt_id.in_(attempt_ids),
            )
        )
        await db.execute(
            update(AnswerAttempt)
            .where(AnswerAttempt.owner_id == ctx.run.owner_id, AnswerAttempt.id.in_(attempt_ids))
            .values(answer=None)
        )
        await db.execute(
            delete(ReviewItem).where(
                ReviewItem.owner_id == ctx.run.owner_id, ReviewItem.question_id.in_(question_ids)
            )
        )
        await db.execute(
            update(Question)
            .where(Question.owner_id == ctx.run.owner_id, Question.id.in_(question_ids))
            .values(data={})
        )
        await db.execute(
            update(StudyPackageVersion)
            .where(
                StudyPackageVersion.owner_id == ctx.run.owner_id,
                StudyPackageVersion.id.in_(study_ids),
            )
            .values(data={}, deleted=True)
        )
        await db.execute(
            update(Task)
            .where(
                Task.owner_id == ctx.run.owner_id,
                or_(Task.bundle_version_id.in_(bundle_ids), Task.study_version_id.in_(study_ids)),
            )
            .values(
                title="资料已删除",
                deliverable="",
                acceptance="",
                history=[],
                status="cancelled",
                revision=Task.revision + 1,
            )
        )
        apps = list(
            await db.scalars(
                select(Application).where(
                    Application.owner_id == ctx.run.owner_id,
                    Application.profile_version_id.in_(ids),
                )
            )
        )
        for app in apps:
            app.profile_version_id, app.basis_revision, app.revision = (
                None,
                app.basis_revision + 1,
                app.revision + 1,
            )
        await db.execute(
            update(ApplicationEvent)
            .where(
                ApplicationEvent.owner_id == ctx.run.owner_id,
                ApplicationEvent.application_id.in_([a.id for a in apps]),
            )
            .values(reason="当时材料已删除", details={})
        )
        runs = list(
            await db.scalars(
                select(AgentRun)
                .where(
                    AgentRun.owner_id == ctx.run.owner_id,
                    or_(
                        AgentRun.profile_version_id.in_(ids),
                        AgentRun.resume_version_id == deletion.target_id,
                    ),
                )
                .with_for_update()
            )
        )
        for run in runs:
            run.inputs, run.result = {}, {}
        await db.execute(
            update(RunStep)
            .where(RunStep.owner_id == ctx.run.owner_id, RunStep.run_id.in_([r.id for r in runs]))
            .values(result={})
        )
        deletion.status, deletion.completed_at = "succeeded", now()
        deletion.counts = {
            "profile_versions": len(ids),
            "material_versions": len(bundle_ids),
            "study_versions": len(study_ids),
            "answers": len(attempt_ids),
        }
        await ctx.publish(db, {"deletion_id": str(deletion.id), "status": "succeeded"})


async def delete_account(ctx: Context) -> None:
    # This is the only disabled-account worker operation. All ordinary sessions are revoked already.
    async with Session() as db:
        await guarded(db, ctx.run.owner_id, ctx.run.id, ctx.token, validate_inputs=False)
        request = await db.get(
            DeletionRequest, UUID(str(ctx.run.inputs["deletion_id"])), with_for_update=True
        )
        if request is None or request.owner_id != ctx.run.owner_id:
            raise DomainError("not_found", "删除请求不存在", 404)
        from offerpilot.modules.jobs.models import Job

        await db.execute(
            update(Job)
            .where(Job.owner_id == ctx.run.owner_id)
            .values(current_version_id=None, merged_into_id=None)
        )
        from offerpilot.modules.profiles.models import Profile

        await db.execute(
            update(Profile)
            .where(Profile.owner_id == ctx.run.owner_id)
            .values(current_version_id=None)
        )
        # Explicit FK graph, reverse dependency order. Never search arbitrary text for identifiers.
        for table in reversed(Base.metadata.sorted_tables):
            if table.name in {"users", "deletion_requests"} or "owner_id" not in table.c:
                continue
            await db.execute(delete(table).where(table.c.owner_id == ctx.run.owner_id))
        await db.execute(
            delete(DeletionRequest).where(
                DeletionRequest.owner_id == ctx.run.owner_id, DeletionRequest.id != request.id
            )
        )
        request.owner_id, request.status, request.completed_at, request.run_id = (
            None,
            "succeeded",
            now(),
            None,
        )
        request.target_id, request.profile_ids = None, []
        await db.flush()
        await db.execute(delete(User).where(User.id == ctx.run.owner_id))
        await db.commit()
