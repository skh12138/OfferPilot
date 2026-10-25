from uuid import UUID

from fastapi import APIRouter, Header
from offerpilot.api.deps import DB, Current, Write
from offerpilot.api.schemas import Page
from offerpilot.infrastructure.owned import check_revision, get_owned, lock_owner
from offerpilot.modules.profiles import service
from offerpilot.modules.profiles.models import (
    FactRevocation,
    Profile,
    ProfileVersion,
    ResumeVersion,
)
from offerpilot.modules.profiles.schemas import (
    CurrentDTO,
    ProfileDTO,
    ProfileInput,
    ResumeDTO,
    ResumeInput,
    Revoke,
    Selection,
)
from offerpilot.modules.runs.schemas import RunDTO
from offerpilot.modules.runs.service import enqueue
from sqlalchemy import select


def profile_dto(row: ProfileVersion) -> ProfileDTO:
    result = ProfileDTO.model_validate(row)
    if row.unavailable:
        result.facts = []
        result.preferences = type(result.preferences)()
    return result


router = APIRouter(tags=["profiles"])


@router.get("/profiles/current", response_model=CurrentDTO)
async def current(user: Current, db: DB) -> CurrentDTO:
    selection = await db.scalar(select(Profile).where(Profile.owner_id == user.id))
    versions = list(
        await db.scalars(
            select(ProfileVersion)
            .where(ProfileVersion.owner_id == user.id)
            .order_by(ProfileVersion.created_at.desc())
        )
    )
    current_row = next(
        (v for v in versions if selection and v.id == selection.current_version_id), None
    )
    result = CurrentDTO(
        revision=selection.revision if selection else 1,
        current=profile_dto(current_row) if current_row else None,
        versions=[profile_dto(v) for v in versions],
    )
    revoked = list(
        await db.scalars(select(FactRevocation.fact_id).where(FactRevocation.owner_id == user.id))
    )
    for version in result.versions:
        version.revoked_fact_ids = [
            fact_id for fact_id in revoked if fact_id in {f.fact_id for f in version.facts}
        ]
    if result.current:
        result.current.revoked_fact_ids = [
            fact_id for fact_id in revoked if fact_id in {f.fact_id for f in result.current.facts}
        ]
    return result


@router.post("/profile-versions", response_model=ProfileDTO, status_code=201)
async def create_version(data: ProfileInput, user: Current, db: DB, _: Write) -> ProfileDTO:
    return await service.create_version(db, user.id, data)


@router.post("/profiles/current-selection", response_model=CurrentDTO)
async def select_version(data: Selection, user: Current, db: DB, _: Write) -> CurrentDTO:
    await lock_owner(db, user.id)
    await service.valid_profile(db, user.id, data.profile_version_id)
    row = await db.scalar(select(Profile).where(Profile.owner_id == user.id).with_for_update())
    if row:
        check_revision(row.revision, data.expected_revision)
        row.current_version_id, row.revision = data.profile_version_id, row.revision + 1
    else:
        db.add(Profile(owner_id=user.id, current_version_id=data.profile_version_id))
    await db.commit()
    return await current(user, db)


@router.get("/resume-versions", response_model=Page[ResumeDTO])
async def resumes(user: Current, db: DB) -> Page[ResumeDTO]:
    rows = await db.scalars(
        select(ResumeVersion)
        .where(ResumeVersion.owner_id == user.id)
        .order_by(ResumeVersion.created_at.desc())
        .limit(100)
    )
    return Page(
        items=[
            ResumeDTO.model_validate(
                {**{c.name: getattr(r, c.name) for c in r.__table__.columns}, "text": None}
                if r.deleted_at
                else r
            )
            for r in rows
        ]
    )


@router.get("/resume-versions/{resume_id}", response_model=ResumeDTO)
async def resume(resume_id: UUID, user: Current, db: DB) -> ResumeDTO:
    row = await get_owned(db, ResumeVersion, user.id, resume_id)
    dto = ResumeDTO.model_validate(row)
    if row.deleted_at:
        dto.text = None
    return dto


@router.post("/resume-versions", response_model=RunDTO | ResumeDTO, status_code=202)
async def import_resume(
    data: ResumeInput,
    user: Current,
    db: DB,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> RunDTO | ResumeDTO:
    await lock_owner(db, user.id)
    from offerpilot.modules.runs.service import idempotent

    old = await idempotent(
        db, user.id, "resume-import", idempotency_key, data.model_dump(mode="json")
    )
    if old and not data.parse:
        return ResumeDTO.model_validate(await get_owned(db, ResumeVersion, user.id, old))
    if old:
        from offerpilot.modules.runs.models import AgentRun

        return RunDTO.model_validate(await get_owned(db, AgentRun, user.id, old))
    row = ResumeVersion(owner_id=user.id, title=data.title, text=data.text)
    db.add(row)
    await db.flush()
    if not data.parse:
        from offerpilot.modules.runs.service import remember

        remember(
            db, user.id, "resume-import", str(idempotency_key), data.model_dump(mode="json"), row.id
        )
        await db.commit()
        return ResumeDTO.model_validate(row)
    run = await enqueue(
        db,
        user.id,
        "resume_parse",
        {"resume_id": str(row.id)},
        idempotency_key,
        resume_id=row.id,
        commit=False,
    )
    from offerpilot.modules.runs.service import remember

    remember(
        db, user.id, "resume-import", str(idempotency_key), data.model_dump(mode="json"), run.id
    )
    await db.commit()
    return RunDTO.model_validate(run)


@router.post("/profile-versions/{profile_id}/revocations", response_model=ProfileDTO)
async def revoke(profile_id: UUID, data: Revoke, user: Current, db: DB, _: Write) -> ProfileDTO:
    await lock_owner(db, user.id)
    profile = await get_owned(db, ProfileVersion, user.id, profile_id)
    if not any(
        str(data.fact_id) == item.get("fact_id") for item in profile.facts if isinstance(item, dict)
    ):
        from offerpilot.api.errors import DomainError

        raise DomainError("not_found", "事实不存在", 404)
    existing = await db.scalar(
        select(FactRevocation).where(
            FactRevocation.owner_id == user.id, FactRevocation.fact_id == data.fact_id
        )
    )
    if not existing:
        db.add(FactRevocation(owner_id=user.id, fact_id=data.fact_id, reason=data.reason))
    await db.commit()
    return ProfileDTO.model_validate(profile)
