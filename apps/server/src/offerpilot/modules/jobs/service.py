from datetime import date
from urllib.parse import urlsplit
from uuid import UUID

from offerpilot.api.errors import DomainError
from offerpilot.api.schemas import digest
from offerpilot.infrastructure.owned import check_revision, get_owned, lock_owner
from offerpilot.modules.jobs.models import (
    DuplicateReview,
    Job,
    JobSourceLink,
    JobVerification,
    JobVersion,
    MatchReport,
    TextSnapshot,
)
from offerpilot.modules.jobs.rules import RULE_VERSION, check_eligibility, verify
from offerpilot.modules.jobs.schemas import (
    FieldProvenance,
    JobExtraction,
    JobVersionInput,
    MatchDTO,
    MatchInput,
)
from offerpilot.modules.profiles.schemas import Evidence, Preferences
from offerpilot.modules.profiles.service import confirmed_facts, valid_profile
from offerpilot.providers.urls import canonical_url
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession


def validate_extraction(
    data: JobExtraction, text: str, *, user_review: bool = False
) -> JobExtraction:
    paragraphs = {f"p{i + 1}": line for i, line in enumerate(text.splitlines())}
    fields = data.model_dump(mode="json", exclude={"field_evidence"})
    for name in [
        "title",
        "company",
        "department",
        "source_job_id",
        "batch",
        "cities",
        "work_mode",
        "employment_type",
        "start",
        "deadline",
        "published_date",
        "page_updated_date",
        "salary",
        "responsibilities",
    ]:
        value = fields[name]
        entry = data.field_evidence.get(name)
        if entry:
            if not user_review and entry.source_kind == "user_asserted":
                raise DomainError("invalid_provenance", "模型不能替本人断言字段", 422)
            if not user_review and entry.review_status == "confirmed":
                entry.review_status = "unreviewed"
            if entry.value != value:
                raise DomainError("field_evidence_mismatch", "字段值与证据值不一致", 422)
            if entry.source_kind != "user_asserted" and entry.quote:
                if entry.quote not in paragraphs.get(entry.paragraph_id or "", ""):
                    raise DomainError("invalid_evidence", "字段引文与段落不符", 422)
                entry.evidence_status = "supported"
            elif entry.source_kind == "user_asserted":
                entry.evidence_status = "user_asserted"
            else:
                entry.review_status = "missing" if value is None or value == [] else "unreviewed"
                entry.evidence_status = "unsupported"
        else:
            data.field_evidence[name] = FieldProvenance(
                value=value,
                review_status="missing" if value is None or value == [] else "unreviewed",
                source_kind="user_provided",
            )
    for key, condition in data.conditions.items():
        if (
            key == "days_per_week"
            and isinstance(condition.value, int)
            and not 1 <= condition.value <= 7
        ):
            raise DomainError("invalid_days", "每周天数超出范围", 422)
        if (
            key == "duration_months"
            and isinstance(condition.value, int)
            and not 1 <= condition.value <= 60
        ):
            raise DomainError("invalid_duration", "持续月数超出范围", 422)
        if not user_review and condition.review_status == "confirmed":
            condition.review_status = "unreviewed"
        evidence = condition.evidence
        if evidence and not user_review and evidence.source_kind == "user_asserted":
            raise DomainError("invalid_provenance", "模型不能替本人断言条件", 422)
        if evidence and evidence.source_kind != "user_asserted":
            if evidence.quote not in paragraphs.get(evidence.paragraph_id, ""):
                raise DomainError("invalid_evidence", "条件证据不属于对应段落", 422)
            condition.evidence_status = "supported"
        elif evidence and evidence.source_kind == "user_asserted":
            condition.evidence_status = "user_asserted"
        elif condition.review_status == "confirmed":
            condition.review_status = "unreviewed"
    for requirement in data.requirements:
        if (
            requirement.evidence
            and not user_review
            and requirement.evidence.source_kind == "user_asserted"
        ):
            raise DomainError("invalid_provenance", "模型不能替本人断言要求", 422)
        if (
            requirement.evidence
            and requirement.evidence.source_kind != "user_asserted"
            and requirement.evidence.quote
            not in paragraphs.get(requirement.evidence.paragraph_id, "")
        ):
            raise DomainError("invalid_evidence", "要求证据不属于对应段落", 422)
    return data


async def save_extraction(
    db: AsyncSession, owner: UUID, data: JobExtraction, text: str, url: str | None, kind: str
) -> tuple[Job, bool]:
    data = validate_extraction(data, text)
    if data.classification != "job_detail":
        raise DomainError("not_job_detail", "目录或非职位文本需人工拆分，不创建完整岗位", 422)
    clean = canonical_url(url) if url else None
    board = urlsplit(clean).hostname if clean else None
    source_evidence = data.field_evidence.get("source_job_id")
    identity_id = (
        data.source_job_id
        if source_evidence and source_evidence.evidence_status in {"supported", "user_asserted"}
        else None
    )
    link = None
    if clean:
        identities = [JobSourceLink.canonical_url == clean, JobSourceLink.aliases.contains([clean])]
        if identity_id:
            identities.append(
                (JobSourceLink.board == board) & (JobSourceLink.source_job_id == identity_id)
            )
        link = await db.scalar(
            select(JobSourceLink).where(JobSourceLink.owner_id == owner, or_(*identities))
        )
        if link and identity_id and not link.source_job_id:
            link.source_job_id = identity_id
        if link and clean != link.canonical_url and clean not in link.aliases:
            link.aliases = [*link.aliases, clean]
    job = await get_owned(db, Job, owner, link.job_id) if link else Job(owner_id=owner)
    created = not bool(link)
    if created:
        db.add(job)
        await db.flush()
    previous = await db.get(JobVersion, job.current_version_id) if job.current_version_id else None
    content_hash = digest(text)
    old_snapshot = (
        await db.get(TextSnapshot, previous.snapshot_id)
        if previous and previous.snapshot_id
        else None
    )
    if old_snapshot and old_snapshot.content_hash == content_hash:
        return job, False
    snapshot = TextSnapshot(
        owner_id=owner,
        kind=kind,
        text=text,
        paragraphs={f"p{i + 1}": line for i, line in enumerate(text.splitlines())},
        url=clean,
        content_hash=content_hash,
    )
    db.add(snapshot)
    await db.flush()
    for field in data.field_evidence.values():
        field.snapshot_id = snapshot.id
        field.source_kind = (
            "provider_extracted" if kind == "provider_extracted" else "user_provided"
        )
    for c in data.conditions.values():
        if c.evidence:
            c.evidence.snapshot_id = snapshot.id
    for r in data.requirements:
        if r.evidence:
            r.evidence.snapshot_id = snapshot.id
    version = JobVersion(
        owner_id=owner,
        job_id=job.id,
        snapshot_id=snapshot.id,
        data=data.model_dump(mode="json"),
        reason="首次收录" if created else "来源正文更新",
    )
    db.add(version)
    await db.flush()
    job.current_version_id = version.id
    if not created:
        job.revision += 1
    if clean and not link:
        db.add(
            JobSourceLink(
                owner_id=owner,
                job_id=job.id,
                canonical_url=clean,
                board=board or "",
                source_job_id=identity_id,
            )
        )
    availability, risk, evidence = verify(data, text, date.today())
    db.add(
        JobVerification(
            owner_id=owner,
            job_id=job.id,
            source_status="user_provided" if kind == "user_provided" else "unverified",
            availability_status=availability,
            risk_status=risk,
            evidence=list(evidence),
        )
    )
    await propose_duplicates(db, owner, job, data)
    return job, created


async def propose_duplicates(db: AsyncSession, owner: UUID, job: Job, data: JobExtraction) -> None:
    rows = await db.scalars(
        select(JobVersion)
        .join(Job, Job.current_version_id == JobVersion.id)
        .where(JobVersion.owner_id == owner, Job.id != job.id, Job.merged_into_id.is_(None))
    )
    for row in rows:
        other = JobExtraction.model_validate(row.data)
        if (other.company, other.title, sorted(other.cities), other.department, other.batch) != (
            data.company,
            data.title,
            sorted(data.cities),
            data.department,
            data.batch,
        ):
            continue
        left, right = sorted([job.id, row.job_id], key=str)
        exists = await db.scalar(
            select(DuplicateReview).where(
                DuplicateReview.owner_id == owner,
                DuplicateReview.left_id == left,
                DuplicateReview.right_id == right,
            )
        )
        if not exists:
            db.add(
                DuplicateReview(
                    owner_id=owner,
                    left_id=left,
                    right_id=right,
                    reason=f"公司、标题、城市、部门、批次相同：{data.company} / {data.title} / {data.cities} / {data.department} / {data.batch}；跨来源须用户确认",
                )
            )


async def revise(db: AsyncSession, owner: UUID, job_id: UUID, data: JobVersionInput) -> JobVersion:
    await lock_owner(db, owner)
    job = await get_owned(db, Job, owner, job_id, lock=True)
    check_revision(job.revision, data.expected_revision)
    previous = (
        await get_owned(db, JobVersion, owner, job.current_version_id)
        if job.current_version_id
        else None
    )
    snapshot = (
        await get_owned(db, TextSnapshot, owner, previous.snapshot_id)
        if previous and previous.snapshot_id
        else None
    )
    revised_values = data.data.model_dump(mode="json", exclude={"field_evidence"})
    old_conditions = JobExtraction.model_validate(previous.data).conditions if previous else {}
    for condition_name, condition in data.data.conditions.items():
        old_condition = old_conditions.get(condition_name)
        compared = {"value", "strength", "unrestricted", "unit"}
        if old_condition is None or condition.model_dump(
            include=compared
        ) != old_condition.model_dump(include=compared):
            if condition.value is not None or condition.unrestricted:
                condition.evidence = Evidence(
                    paragraph_id="user", quote=data.reason, source_kind="user_asserted"
                )
                condition.evidence_status = "user_asserted"
    for name, provenance in data.data.field_evidence.items():
        if provenance.value != revised_values.get(name):
            provenance.value = revised_values.get(name)
            provenance.source_kind, provenance.quote, provenance.paragraph_id = (
                "user_asserted",
                None,
                None,
            )
            provenance.explanation = data.reason
            provenance.evidence_status = "user_asserted"
    extraction = validate_extraction(
        data.data, snapshot.text or "" if snapshot else "", user_review=True
    )
    if data.confirm_fields:
        for provenance in extraction.field_evidence.values():
            if provenance.value is not None and provenance.value != []:
                provenance.review_status = "confirmed"
                if provenance.evidence_status != "supported":
                    provenance.source_kind, provenance.evidence_status = (
                        "user_asserted",
                        "user_asserted",
                    )
                    provenance.explanation = data.reason
        for condition in extraction.conditions.values():
            if condition.evidence_status in {
                "supported",
                "user_asserted",
            } and condition.review_status not in {"conflict", "missing"}:
                condition.review_status = "confirmed"
    version = JobVersion(
        owner_id=owner,
        job_id=job_id,
        snapshot_id=previous.snapshot_id if previous else None,
        data=extraction.model_dump(mode="json"),
        reason=data.reason,
    )
    db.add(version)
    await db.flush()
    job.current_version_id, job.revision = version.id, job.revision + 1
    await db.commit()
    return version


async def match(db: AsyncSession, owner: UUID, data: MatchInput) -> MatchDTO:
    job = await get_owned(db, JobVersion, owner, data.job_version_id)
    profile = (
        await valid_profile(db, owner, data.profile_version_id) if data.profile_version_id else None
    )
    preferences = Preferences.model_validate(profile.preferences) if profile else None
    overall, checks = check_eligibility(preferences, JobExtraction.model_validate(job.data))
    facts = await confirmed_facts(db, owner, data.profile_version_id)
    row = MatchReport(
        owner_id=owner,
        job_version_id=job.id,
        profile_version_id=data.profile_version_id,
        rule_version=RULE_VERSION,
        overall=overall,
        checks=[c.model_dump(mode="json") for c in checks],
        fact_ids=[str(f.fact_id) for f in facts],
    )
    db.add(row)
    await db.commit()
    return MatchDTO.model_validate(row)
