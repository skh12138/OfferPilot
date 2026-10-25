from uuid import UUID

from offerpilot.api.errors import DomainError
from offerpilot.api.schemas import digest
from offerpilot.infrastructure.owned import check_revision, get_owned, lock_owner
from offerpilot.modules.applications.models import Application
from offerpilot.modules.preparation.models import BundleApproval, BundleVersion, PreparationBundle
from offerpilot.modules.preparation.rules import validate_claims
from offerpilot.modules.preparation.schemas import (
    ApprovalInput,
    BundleDTO,
    BundleEdit,
    BundlePayload,
    BundleVersionDTO,
)
from offerpilot.modules.profiles.service import confirmed_facts, valid_profile
from offerpilot.modules.runs.service import idempotent, remember
from offerpilot.modules.tasks.models import Task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def detail(db: AsyncSession, owner: UUID, bundle_id: UUID) -> BundleDTO:
    bundle = await get_owned(db, PreparationBundle, owner, bundle_id)
    rows = list(
        await db.scalars(
            select(BundleVersion)
            .where(BundleVersion.owner_id == owner, BundleVersion.bundle_id == bundle.id)
            .order_by(BundleVersion.created_at.desc(), BundleVersion.id)
        )
    )
    versions = [
        BundleVersionDTO.model_validate(
            {**{c.name: getattr(r, c.name) for c in r.__table__.columns}, "data": None}
            if r.deleted
            else r
        )
        for r in rows
    ]
    return BundleDTO(
        id=bundle.id,
        application_id=bundle.application_id,
        revision=bundle.revision,
        current=next((v for v in versions if v.id == bundle.current_version_id), None),
        versions=versions,
    )


async def validate_basis(db: AsyncSession, owner: UUID, version: BundleVersion) -> Application:
    app = await get_owned(db, Application, owner, version.application_id, lock=True)
    if version.deleted:
        raise DomainError("input_deleted", "材料已删除")
    if app.basis_revision != version.basis_revision:
        raise DomainError("basis_changed", "准备基准已改变，旧草稿不能审批")
    if version.profile_version_id:
        await valid_profile(db, owner, version.profile_version_id)
    if version.job_version_id:
        from offerpilot.modules.jobs.models import JobVersion

        job = await get_owned(db, JobVersion, owner, version.job_version_id)
        if job.data.get("classification") != "job_detail":
            raise DomainError("source_content_unavailable", "材料引用的岗位正文已不可用")
    facts = await confirmed_facts(db, owner, version.profile_version_id)
    validate_claims(BundlePayload.model_validate(version.data), facts)
    return app


async def edit(db: AsyncSession, owner: UUID, bundle_id: UUID, data: BundleEdit) -> BundleVersion:
    await lock_owner(db, owner)
    bundle = await get_owned(db, PreparationBundle, owner, bundle_id, lock=True)
    check_revision(bundle.revision, data.expected_revision)
    previous = (
        await get_owned(db, BundleVersion, owner, bundle.current_version_id)
        if bundle.current_version_id
        else None
    )
    if not previous:
        raise DomainError("not_found", "材料版本不存在", 404)
    await validate_basis(db, owner, previous)
    validate_claims(data.data, await confirmed_facts(db, owner, previous.profile_version_id))
    payload = data.data.model_dump(mode="json")
    row = BundleVersion(
        owner_id=owner,
        bundle_id=bundle.id,
        application_id=bundle.application_id,
        job_version_id=previous.job_version_id,
        profile_version_id=previous.profile_version_id,
        round_id=previous.round_id,
        basis_revision=previous.basis_revision,
        data=payload,
        payload_hash=digest(payload),
        prompt_version=previous.prompt_version,
        model=previous.model,
        reason=data.reason,
    )
    db.add(row)
    await db.flush()
    bundle.current_version_id, bundle.revision = row.id, bundle.revision + 1
    await db.commit()
    return row


async def approve(
    db: AsyncSession, owner: UUID, bundle_id: UUID, data: ApprovalInput, key: str | None
) -> BundleApproval:
    await lock_owner(db, owner)
    payload, op = data.model_dump(mode="json"), f"approve:{bundle_id}"
    old = await idempotent(db, owner, op, key, payload)
    if old:
        return await get_owned(db, BundleApproval, owner, old)
    bundle = await get_owned(db, PreparationBundle, owner, bundle_id, lock=True)
    check_revision(bundle.revision, data.expected_revision)
    version = await get_owned(db, BundleVersion, owner, data.version_id)
    if version.bundle_id != bundle.id or bundle.current_version_id != version.id:
        raise DomainError("draft_changed", "请审核当前新版本")
    await validate_basis(db, owner, version)
    if (
        data.payload_hash != version.payload_hash
        or version.payload_hash != digest(version.data)
        or data.basis_revision != version.basis_revision
    ):
        raise DomainError("approval_mismatch", "审核内容或准备基准已变化")
    existing = await db.scalar(
        select(BundleApproval).where(
            BundleApproval.owner_id == owner,
            BundleApproval.bundle_version_id == version.id,
            BundleApproval.payload_hash == version.payload_hash,
            BundleApproval.scope == data.scope,
        )
    )
    if existing:
        remember(db, owner, op, str(key), payload, existing.id)
        await db.commit()
        return existing
    approval = BundleApproval(
        owner_id=owner,
        bundle_version_id=version.id,
        payload_hash=version.payload_hash,
        basis_revision=version.basis_revision,
        scope=data.scope,
    )
    db.add(approval)
    if "tasks" in data.scope:
        content = BundlePayload.model_validate(version.data)
        for index, proposal in enumerate(content.tasks):
            action = f"bundle:{version.id}:task:{index}"
            task = await db.scalar(
                select(Task).where(Task.owner_id == owner, Task.business_action_id == action)
            )
            if not task:
                db.add(
                    Task(
                        owner_id=owner,
                        application_id=bundle.application_id,
                        business_action_id=action,
                        bundle_version_id=version.id,
                        kind="prepare_material",
                        title=proposal.title,
                        deliverable=proposal.deliverable,
                        acceptance=proposal.acceptance,
                    )
                )
    await db.flush()
    remember(db, owner, op, str(key), payload, approval.id)
    await db.commit()
    return approval
