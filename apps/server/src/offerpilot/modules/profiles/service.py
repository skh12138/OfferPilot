from uuid import UUID

from offerpilot.api.errors import DomainError
from offerpilot.infrastructure.owned import get_owned, lock_owner
from offerpilot.modules.profiles.models import (
    FactRevocation,
    Profile,
    ProfileVersion,
    ResumeVersion,
)
from offerpilot.modules.profiles.schemas import Fact, ProfileDTO, ProfileInput
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def valid_profile(db: AsyncSession, owner: UUID, profile_id: UUID) -> ProfileVersion:
    row = await get_owned(db, ProfileVersion, owner, profile_id)
    if row.unavailable:
        raise DomainError("input_deleted", "资料已删除，不能继续引用")
    if row.resume_version_id:
        resume = await get_owned(db, ResumeVersion, owner, row.resume_version_id)
        if resume.deleted_at:
            raise DomainError("input_deleted", "简历已删除")
    return row


async def confirmed_facts(db: AsyncSession, owner: UUID, profile_id: UUID | None) -> list[Fact]:
    if not profile_id:
        return []
    profile = await valid_profile(db, owner, profile_id)
    revoked = set(
        await db.scalars(select(FactRevocation.fact_id).where(FactRevocation.owner_id == owner))
    )
    return [
        fact
        for item in profile.facts
        if (fact := Fact.model_validate(item)).status == "user_confirmed"
        and fact.fact_id not in revoked
    ]


async def create_version(db: AsyncSession, owner: UUID, data: ProfileInput) -> ProfileDTO:
    await lock_owner(db, owner)
    text: str | None = None
    if data.resume_version_id:
        resume = await get_owned(db, ResumeVersion, owner, data.resume_version_id)
        if resume.deleted_at:
            raise DomainError("input_deleted", "简历已删除")
        text = resume.text
    existing = list(
        await db.scalars(select(ProfileVersion).where(ProfileVersion.owner_id == owner))
    )
    historical = {
        f.fact_id: f for row in existing for f in (Fact.model_validate(x) for x in row.facts)
    }
    if len({f.fact_id for f in data.facts}) != len(data.facts):
        raise DomainError("duplicate_fact", "事实 ID 重复", 422)
    for fact in data.facts:
        if fact.evidence.source_kind != "user_asserted":
            paragraphs = {f"p{i + 1}": line for i, line in enumerate((text or "").splitlines())}
            if fact.evidence.quote not in paragraphs.get(fact.evidence.paragraph_id, ""):
                raise DomainError("invalid_evidence", "事实引文与简历段落不符", 422)
        if fact.fact_id in historical and historical[fact.fact_id].text != fact.text:
            raise DomainError("fact_identity_changed", "修改事实正文时请使用新的事实 ID", 422)
    confirmed_before = {
        Fact.model_validate(f).fact_id
        for p in existing
        for f in p.facts
        if Fact.model_validate(f).status == "user_confirmed"
    }
    revoked = set(
        await db.scalars(select(FactRevocation.fact_id).where(FactRevocation.owner_id == owner))
    )
    for fact in data.facts:
        if fact.status == "disputed" or (
            fact.status != "user_confirmed" and fact.fact_id in confirmed_before
        ):
            if fact.fact_id not in revoked:
                db.add(
                    FactRevocation(
                        owner_id=owner,
                        fact_id=fact.fact_id,
                        reason="本人将事实改为 " + fact.status + "，旧版本禁止新引用",
                    )
                )
                revoked.add(fact.fact_id)
    row = ProfileVersion(
        owner_id=owner,
        resume_version_id=data.resume_version_id,
        preferences=data.preferences.model_dump(mode="json"),
        facts=[f.model_dump(mode="json") for f in data.facts],
        reason=data.reason,
    )
    db.add(row)
    await db.flush()
    current = await db.scalar(select(Profile).where(Profile.owner_id == owner).with_for_update())
    if not current:
        current = Profile(owner_id=owner, current_version_id=row.id)
        db.add(current)
    else:
        current.current_version_id = row.id
        current.revision += 1
    await db.commit()
    return ProfileDTO.model_validate(row)
