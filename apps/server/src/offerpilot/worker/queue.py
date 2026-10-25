from datetime import timedelta
from uuid import UUID, uuid4

from offerpilot.api.errors import DomainError
from offerpilot.infrastructure.config import settings
from offerpilot.infrastructure.db import Session, now
from offerpilot.infrastructure.owned import get_owned, lock_owner
from offerpilot.modules.runs.models import AgentRun, RunStatus
from offerpilot.modules.runs.service import event
from sqlalchemy import or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession


class LeaseLost(Exception):
    pass


async def claim(worker_id: str) -> tuple[UUID, UUID] | None:
    cfg = settings()
    async with Session() as db:
        # Serialize capacity decisions across processes; queue row locks alone cannot enforce caps.
        await db.execute(text("SELECT pg_advisory_xact_lock(73910201)"))
        active = list(
            await db.scalars(
                select(AgentRun).where(
                    AgentRun.status == RunStatus.RUNNING, AgentRun.lease_expires_at > now()
                )
            )
        )
        if len(active) >= cfg.global_run_concurrency:
            return None
        candidates = await db.scalars(
            select(AgentRun)
            .where(
                or_(
                    AgentRun.status == RunStatus.QUEUED,
                    (AgentRun.status == RunStatus.RUNNING) & (AgentRun.lease_expires_at < now()),
                )
            )
            .order_by(AgentRun.created_at, AgentRun.id)
            .with_for_update(skip_locked=True)
            .limit(100)
        )
        for run in candidates:
            if sum(r.owner_id == run.owner_id for r in active) >= cfg.user_run_concurrency:
                continue
            if run.cancel_requested_at:
                run.status = RunStatus.CANCELLED
                event(db, run, "run_cancelled")
                continue
            if run.attempt >= 3:
                run.status, run.error_code = RunStatus.FAILED, "attempts_exhausted"
                event(db, run, "run_failed", {"code": run.error_code})
                continue
            from offerpilot.modules.runs.models import ProviderCall

            await db.execute(
                update(ProviderCall)
                .where(ProviderCall.run_id == run.id, ProviderCall.status == "reserved")
                .values(status="unknown")
            )
            token = uuid4()
            run.status, run.lease_token, run.worker_id = RunStatus.RUNNING, token, worker_id
            run.lease_expires_at, run.attempt = now() + timedelta(seconds=120), run.attempt + 1
            run.started_at = run.started_at or now()
            event(db, run, "run_started", {"attempt": run.attempt})
            await db.commit()
            return run.id, token
        await db.commit()
    return None


async def guarded(
    db: AsyncSession, owner: UUID, run_id: UUID, token: UUID, *, validate_inputs: bool = True
) -> AgentRun:
    snapshot = await get_owned(db, AgentRun, owner, run_id)
    await lock_owner(db, owner, allow_disabled=snapshot.kind == "delete_account")
    run = await get_owned(db, AgentRun, owner, run_id, lock=True)
    if (
        run.status != RunStatus.RUNNING
        or run.lease_token != token
        or not run.lease_expires_at
        or run.lease_expires_at <= now()
    ):
        raise LeaseLost()
    if run.cancel_requested_at:
        raise DomainError("run_cancelled", "运行已取消")
    from offerpilot.providers.deepseek import PROMPT_VERSION

    if run.prompt_version != PROMPT_VERSION:
        raise DomainError("prompt_version_unavailable", "旧 Prompt 版本不可恢复，请显式创建新运行")
    if run.workflow_version != "p0-v1":
        raise DomainError("workflow_version_unavailable", "旧工作流版本不可执行")
    if run.application_id and run.inputs.get("basis_revision"):
        from offerpilot.modules.applications.models import Application

        app = await get_owned(db, Application, owner, run.application_id)
        if app.basis_revision != int(str(run.inputs["basis_revision"])):
            raise DomainError("basis_changed", "准备基准已改变，停止后续调用")
    if validate_inputs and run.kind in {"material_prepare", "study", "feedback"}:
        job_id = (
            UUID(str(run.inputs["job_version_id"])) if run.inputs.get("job_version_id") else None
        )
        if run.application_id:
            from offerpilot.modules.applications.models import Application

            basis_app = await get_owned(db, Application, owner, run.application_id)
            job_id = job_id or basis_app.job_version_id
        if job_id:
            from offerpilot.modules.jobs.models import JobVersion

            job = await get_owned(db, JobVersion, owner, job_id, lock=True)
            if job.data.get("classification") != "job_detail":
                raise DomainError("source_content_unavailable", "岗位正文已失效或被来源策略清理")
    if validate_inputs and run.kind not in {"delete_resume", "delete_account"}:
        if run.profile_version_id:
            from offerpilot.modules.profiles.service import valid_profile

            await valid_profile(db, owner, run.profile_version_id)
        if run.resume_version_id:
            from offerpilot.modules.profiles.models import ResumeVersion

            resume = await get_owned(db, ResumeVersion, owner, run.resume_version_id)
            if resume.deleted_at:
                raise DomainError("input_deleted", "简历已删除")
    return run


async def heartbeat(run_id: UUID, token: UUID) -> bool:
    async with Session() as db:
        row = await db.scalar(
            select(AgentRun)
            .where(
                AgentRun.id == run_id,
                AgentRun.lease_token == token,
                AgentRun.status == RunStatus.RUNNING,
            )
            .with_for_update()
        )
        if not row or not row.lease_expires_at or row.lease_expires_at <= now():
            return False
        row.lease_expires_at = now() + timedelta(seconds=120)
        await db.commit()
        return True
