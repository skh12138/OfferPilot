from uuid import UUID

from offerpilot.infrastructure.owned import get_owned
from offerpilot.modules.jobs.models import (
    Job,
    JobPreference,
    JobSourceLink,
    JobVerification,
    JobVersion,
    TextSnapshot,
)
from offerpilot.modules.jobs.schemas import (
    JobDTO,
    SnapshotDTO,
    SourceLinkDTO,
    VerificationDTO,
    VersionDTO,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def detail(db: AsyncSession, owner: UUID, job_id: UUID) -> JobDTO:
    job = await get_owned(db, Job, owner, job_id)
    versions = list(
        await db.scalars(
            select(JobVersion)
            .where(JobVersion.owner_id == owner, JobVersion.job_id == job_id)
            .order_by(JobVersion.created_at.desc(), JobVersion.id)
        )
    )
    snapshot_ids = [v.snapshot_id for v in versions if v.snapshot_id]
    snapshots = await db.scalars(
        select(TextSnapshot).where(
            TextSnapshot.owner_id == owner, TextSnapshot.id.in_(snapshot_ids)
        )
    )
    grouped = (
        select(Job.id)
        .where(Job.owner_id == owner, Job.id == job_id)
        .cte("grouped_jobs", recursive=True)
    )
    grouped = grouped.union(
        select(Job.id).where(Job.owner_id == owner, Job.merged_into_id == grouped.c.id)
    )
    links = await db.scalars(
        select(JobSourceLink).where(
            JobSourceLink.owner_id == owner, JobSourceLink.job_id.in_(select(grouped.c.id))
        )
    )
    verification = await db.scalar(
        select(JobVerification)
        .where(JobVerification.owner_id == owner, JobVerification.job_id == job_id)
        .order_by(JobVerification.checked_at.desc())
        .limit(1)
    )
    pref = await db.scalar(
        select(JobPreference).where(JobPreference.owner_id == owner, JobPreference.job_id == job_id)
    )
    return JobDTO(
        id=job.id,
        revision=job.revision,
        current_version_id=job.current_version_id,
        merged_into_id=job.merged_into_id,
        current=next(
            (VersionDTO.model_validate(v) for v in versions if v.id == job.current_version_id), None
        ),
        versions=[VersionDTO.model_validate(v) for v in versions],
        snapshots=[SnapshotDTO.model_validate(s) for s in snapshots],
        sources=[SourceLinkDTO.model_validate(s) for s in links],
        verification=VerificationDTO.model_validate(verification) if verification else None,
        preference=pref.preference if pref else "unassigned",
    )


async def summaries(db: AsyncSession, owner: UUID, jobs: list[Job]) -> list[JobDTO]:
    versions = {
        v.id: v
        for v in await db.scalars(
            select(JobVersion).where(
                JobVersion.owner_id == owner,
                JobVersion.id.in_([j.current_version_id for j in jobs if j.current_version_id]),
            )
        )
    }
    prefs = {
        p.job_id: p
        for p in await db.scalars(select(JobPreference).where(JobPreference.owner_id == owner))
    }
    verification = {}
    for row in await db.scalars(
        select(JobVerification)
        .where(JobVerification.owner_id == owner)
        .order_by(JobVerification.checked_at.desc(), JobVerification.id)
    ):
        if row.job_id not in verification:
            verification[row.job_id] = row
    result = []
    for job in jobs:
        version = versions.get(job.current_version_id) if job.current_version_id else None
        check = verification.get(job.id)
        result.append(
            JobDTO(
                id=job.id,
                revision=job.revision,
                current_version_id=job.current_version_id,
                current=VersionDTO.model_validate(version) if version else None,
                preference=prefs[job.id].preference if job.id in prefs else "unassigned",
                verification=VerificationDTO.model_validate(check) if check else None,
                merged_into_id=job.merged_into_id,
            )
        )
    return result
