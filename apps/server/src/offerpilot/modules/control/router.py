import json
import secrets
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Header, Request, Response
from offerpilot.api.deps import DB, Current, Write, current_user
from offerpilot.api.errors import DomainError
from offerpilot.infrastructure.config import settings
from offerpilot.infrastructure.db import now
from offerpilot.infrastructure.owned import get_owned, lock_owner
from offerpilot.modules.control.deletion import request_account_deletion, request_resume_deletion
from offerpilot.modules.control.models import DeletionRequest, ExportRequest
from offerpilot.modules.control.schemas import (
    DeleteAccountInput,
    DeletePreview,
    DeleteResumeInput,
    DeletionDTO,
    ExportDTO,
    ExportInput,
)
from offerpilot.modules.identity.service import token_hash
from offerpilot.modules.interview.models import StudyPackageVersion
from offerpilot.modules.preparation.models import BundleVersion
from offerpilot.modules.profiles.models import ProfileVersion, ResumeVersion
from offerpilot.modules.runs.models import AgentRun, RunStatus
from offerpilot.modules.runs.service import enqueue, idempotent, remember
from pydantic import JsonValue
from sqlalchemy import func, select

router = APIRouter(tags=["data control"])


@router.get("/resume-versions/{resume_id}/deletion-preview", response_model=DeletePreview)
async def preview(resume_id: UUID, user: Current, db: DB) -> DeletePreview:
    await get_owned(db, ResumeVersion, user.id, resume_id)
    profiles = list(
        await db.scalars(select(ProfileVersion).where(ProfileVersion.owner_id == user.id))
    )
    direct = [p for p in profiles if p.resume_version_id == resume_id]
    facts = {
        str(f["fact_id"])
        for p in direct
        for f in p.facts
        if isinstance(f, dict) and f.get("fact_id")
    }
    ids = [
        p.id
        for p in profiles
        if p in direct or any(isinstance(f, dict) and f.get("fact_id") in facts for f in p.facts)
    ]
    materials = await db.scalar(
        select(func.count())
        .select_from(BundleVersion)
        .where(BundleVersion.owner_id == user.id, BundleVersion.profile_version_id.in_(ids))
    )
    studies = await db.scalar(
        select(func.count())
        .select_from(StudyPackageVersion)
        .where(
            StudyPackageVersion.owner_id == user.id, StudyPackageVersion.profile_version_id.in_(ids)
        )
    )
    runs = await db.scalar(
        select(func.count())
        .select_from(AgentRun)
        .where(
            AgentRun.owner_id == user.id,
            AgentRun.status.in_([RunStatus.QUEUED, RunStatus.RUNNING]),
            AgentRun.profile_version_id.in_(ids),
        )
    )
    return DeletePreview(
        resume_id=resume_id,
        profile_versions=len(ids),
        material_versions=materials or 0,
        study_versions=studies or 0,
        active_runs=runs or 0,
        preserved=[
            "申请阶段、发生时间及材料已删除墓碑",
            "独立手工岗位和不依赖该简历的资料",
            "模型服务已接收的数据不能由本应用保证立即删除；备份未配置",
        ],
    )


@router.delete("/resume-versions/{resume_id}", response_model=DeletionDTO, status_code=202)
async def delete_resume(
    resume_id: UUID,
    data: DeleteResumeInput,
    user: Current,
    db: DB,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> DeletionDTO:
    if not data.confirmed:
        raise DomainError("confirmation_required", "请确认删除影响范围", 422)
    return DeletionDTO.model_validate(
        await request_resume_deletion(db, user.id, resume_id, idempotency_key)
    )


@router.delete("/me", response_model=DeletionDTO, status_code=202)
async def delete_account(
    data: DeleteAccountInput,
    user: Current,
    db: DB,
    response: Response,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> DeletionDTO:
    if not data.confirmed:
        raise DomainError("confirmation_required", "请确认删除账户", 422)
    row, receipt = await request_account_deletion(db, user.id, data.password, idempotency_key)
    response.delete_cookie("op_session", path="/")
    result = DeletionDTO.model_validate(row)
    result.receipt = receipt
    return result


@router.get("/deletion-requests/{deletion_id}", response_model=DeletionDTO)
async def deletion(
    deletion_id: UUID,
    request: Request,
    db: DB,
    x_deletion_receipt: str | None = Header(default=None),
) -> DeletionDTO:
    row = await db.get(DeletionRequest, deletion_id)
    if row is None:
        raise DomainError("not_found", "删除请求不存在", 404)
    receipt_ok = bool(
        x_deletion_receipt
        and row.receipt_hash
        and secrets.compare_digest(token_hash(x_deletion_receipt), row.receipt_hash)
    )
    if not receipt_ok:
        try:
            user = await current_user(request, db)
        except DomainError as exc:
            raise DomainError("not_found", "删除请求不存在", 404) from exc
        if row.owner_id != user.id:
            raise DomainError("not_found", "删除请求不存在", 404)
    return DeletionDTO.model_validate(row)


@router.post("/me/exports", response_model=ExportDTO, status_code=202)
async def create_export(
    data: ExportInput,
    user: Current,
    db: DB,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> ExportDTO:
    await lock_owner(db, user.id)
    old = await idempotent(db, user.id, "export", idempotency_key, data.model_dump(mode="json"))
    if old:
        return ExportDTO.model_validate(await get_owned(db, ExportRequest, user.id, old))
    pending = await db.scalar(
        select(DeletionRequest).where(
            DeletionRequest.owner_id == user.id, DeletionRequest.status != "succeeded"
        )
    )
    if pending:
        raise DomainError("deletion_in_progress", "资料清理中，导出暂不可用")
    row = ExportRequest(
        owner_id=user.id, format=data.format, expires_at=now() + timedelta(hours=24)
    )
    db.add(row)
    await db.flush()
    run = await enqueue(
        db, user.id, "export", {"export_id": str(row.id)}, idempotency_key, commit=False
    )
    row.run_id = run.id
    remember(db, user.id, "export", str(idempotency_key), data.model_dump(mode="json"), row.id)
    await db.commit()
    return ExportDTO.model_validate(row)


@router.get("/me/exports/{export_id}", response_model=ExportDTO)
async def export_status(export_id: UUID, user: Current, db: DB) -> ExportDTO:
    return ExportDTO.model_validate(await get_owned(db, ExportRequest, user.id, export_id))


@router.get("/me/exports/{export_id}/download")
async def download(export_id: UUID, user: Current, db: DB) -> Response:
    row = await get_owned(db, ExportRequest, user.id, export_id)
    if row.expires_at <= now() or row.status == "expired":
        raise DomainError("export_expired", "导出已过期", 410)
    if row.status != "succeeded":
        raise DomainError("export_not_ready", "导出尚未生成")
    content = (
        json.dumps(row.payload, ensure_ascii=False)
        if row.format == "json"
        else "\ufeff" + (row.csv_text or "")
    )
    return Response(
        content,
        media_type="application/json" if row.format == "json" else "text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="offerpilot-export.{row.format}"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/deletion-requests/{deletion_id}/retry", response_model=DeletionDTO, status_code=202)
async def retry_deletion(
    deletion_id: UUID,
    request: Request,
    db: DB,
    _: Write,
    x_deletion_receipt: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None),
) -> DeletionDTO:
    from offerpilot.infrastructure.owned import lock_owner
    from offerpilot.modules.runs.service import idempotent, remember

    await deletion(deletion_id, request, db, x_deletion_receipt)
    row = await db.get(DeletionRequest, deletion_id)
    if row is None or row.owner_id is None or row.status == "succeeded":
        raise DomainError("deletion_not_retryable", "删除请求不能重试")
    await lock_owner(db, row.owner_id, allow_disabled=row.kind == "account")
    previous = await get_owned(db, AgentRun, row.owner_id, row.run_id) if row.run_id else None
    if previous and previous.status not in {
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.PARTIAL,
    }:
        raise DomainError("deletion_running", "清理仍在进行中")
    payload: dict[str, JsonValue] = {"deletion_id": str(deletion_id)}
    old = await idempotent(db, row.owner_id, "deletion-retry", idempotency_key, payload)
    if old:
        return DeletionDTO.model_validate(row)
    run = AgentRun(
        owner_id=row.owner_id,
        kind="delete_account" if row.kind == "account" else "delete_resume",
        inputs=payload,
        model=settings().llm_model,
    )
    db.add(run)
    await db.flush()
    row.run_id, row.status = run.id, "queued"
    remember(db, row.owner_id, "deletion-retry", str(idempotency_key), payload, run.id)
    await db.commit()
    return DeletionDTO.model_validate(row)
