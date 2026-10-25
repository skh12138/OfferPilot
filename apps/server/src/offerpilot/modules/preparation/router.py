from uuid import UUID

from fastapi import APIRouter, Header
from offerpilot.api.deps import DB, Current, Write
from offerpilot.api.errors import DomainError
from offerpilot.api.schemas import Page
from offerpilot.infrastructure.owned import check_revision, get_owned, lock_owner
from offerpilot.modules.applications.models import Application, AssessmentRound
from offerpilot.modules.preparation import service
from offerpilot.modules.preparation.models import PreparationBundle
from offerpilot.modules.preparation.schemas import (
    ApprovalDTO,
    ApprovalInput,
    BundleDTO,
    BundleEdit,
    BundleVersionDTO,
    ManualBundleInput,
    PreparationInput,
)
from offerpilot.modules.runs.schemas import RunDTO
from offerpilot.modules.runs.service import enqueue
from sqlalchemy import select

router = APIRouter(tags=["preparation"])


@router.post("/applications/{app_id}/preparation-runs", response_model=RunDTO, status_code=202)
async def generate(
    app_id: UUID,
    data: PreparationInput,
    user: Current,
    db: DB,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> RunDTO:
    await lock_owner(db, user.id)
    app = await get_owned(db, Application, user.id, app_id, lock=True)
    check_revision(app.revision, data.expected_revision)
    if data.round_id:
        rnd = await get_owned(db, AssessmentRound, user.id, data.round_id)
        if rnd.application_id != app.id:
            raise DomainError("invalid_parent", "轮次不属于申请", 404)
    run = await enqueue(
        db,
        user.id,
        "material_prepare",
        {
            "basis_revision": app.basis_revision,
            "round_id": str(data.round_id) if data.round_id else None,
        },
        idempotency_key,
        profile_id=app.profile_version_id,
        application_id=app.id,
    )
    return RunDTO.model_validate(run)


@router.get("/applications/{app_id}/preparation-bundles", response_model=Page[BundleDTO])
async def bundles(app_id: UUID, user: Current, db: DB) -> Page[BundleDTO]:
    await get_owned(db, Application, user.id, app_id)
    rows = await db.scalars(
        select(PreparationBundle)
        .where(PreparationBundle.owner_id == user.id, PreparationBundle.application_id == app_id)
        .order_by(PreparationBundle.created_at.desc())
        .limit(100)
    )
    return Page(items=[await service.detail(db, user.id, r.id) for r in rows])


@router.get("/preparation-bundles/{bundle_id}", response_model=BundleDTO)
async def bundle(bundle_id: UUID, user: Current, db: DB) -> BundleDTO:
    return await service.detail(db, user.id, bundle_id)


@router.post(
    "/preparation-bundles/{bundle_id}/versions", response_model=BundleVersionDTO, status_code=201
)
async def edit(
    bundle_id: UUID, data: BundleEdit, user: Current, db: DB, _: Write
) -> BundleVersionDTO:
    return BundleVersionDTO.model_validate(await service.edit(db, user.id, bundle_id, data))


@router.post("/preparation-bundles/{bundle_id}/approve", response_model=ApprovalDTO)
async def approve(
    bundle_id: UUID,
    data: ApprovalInput,
    user: Current,
    db: DB,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> ApprovalDTO:
    return ApprovalDTO.model_validate(
        await service.approve(db, user.id, bundle_id, data, idempotency_key)
    )


@router.post(
    "/applications/{app_id}/preparation-bundles", response_model=BundleDTO, status_code=201
)
async def manual_bundle(
    app_id: UUID, data: "ManualBundleInput", user: Current, db: DB, _: Write
) -> BundleDTO:
    from offerpilot.api.schemas import digest
    from offerpilot.modules.preparation.models import BundleVersion
    from offerpilot.modules.preparation.rules import validate_claims
    from offerpilot.modules.profiles.service import confirmed_facts

    await lock_owner(db, user.id)
    app = await get_owned(db, Application, user.id, app_id, lock=True)
    check_revision(app.revision, data.expected_revision)
    validate_claims(data.data, await confirmed_facts(db, user.id, app.profile_version_id))
    row = PreparationBundle(owner_id=user.id, application_id=app.id)
    db.add(row)
    await db.flush()
    payload = data.data.model_dump(mode="json")
    version = BundleVersion(
        owner_id=user.id,
        bundle_id=row.id,
        application_id=app.id,
        job_version_id=app.job_version_id,
        profile_version_id=app.profile_version_id,
        basis_revision=app.basis_revision,
        data=payload,
        payload_hash=digest(payload),
        prompt_version="user-authored",
        model="user-authored",
        reason=data.reason,
    )
    db.add(version)
    await db.flush()
    row.current_version_id = version.id
    await db.commit()
    return await service.detail(db, user.id, row.id)
