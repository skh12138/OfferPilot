from uuid import UUID

from fastapi import APIRouter, Header, Query, Response
from offerpilot.api.deps import DB, Current, Write
from offerpilot.api.schemas import IDs, Page
from offerpilot.infrastructure.owned import get_owned, lock_owner
from offerpilot.modules.jobs import repository, service
from offerpilot.modules.jobs.models import Job, JobPreference, MatchReport
from offerpilot.modules.jobs.schemas import (
    JobDTO,
    JobImport,
    JobVersionInput,
    MatchDTO,
    MatchInput,
    PreferenceInput,
    VersionDTO,
)
from offerpilot.modules.runs.models import AgentRun
from offerpilot.modules.runs.schemas import RunDTO
from offerpilot.modules.runs.service import enqueue
from offerpilot.providers.urls import canonical_url
from sqlalchemy import select

router = APIRouter(tags=["jobs"])


@router.post("/job-imports", response_model=RunDTO, status_code=202)
async def import_job(
    data: JobImport,
    user: Current,
    db: DB,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> RunDTO:
    if data.url:
        data.url = canonical_url(data.url)
    return RunDTO.model_validate(
        await enqueue(db, user.id, "job_import", data.model_dump(mode="json"), idempotency_key)
    )


@router.get("/job-imports/{run_id}", response_model=RunDTO)
async def import_status(run_id: UUID, user: Current, db: DB) -> RunDTO:
    return RunDTO.model_validate(await get_owned(db, AgentRun, user.id, run_id))


@router.get("/jobs", response_model=Page[JobDTO])
async def jobs(
    user: Current,
    db: DB,
    q: str = "",
    preference: str | None = None,
    risk: str | None = None,
    eligibility: str | None = None,
    cursor: UUID | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> Page[JobDTO]:
    from offerpilot.modules.jobs.rules import check_eligibility, skill_tokens
    from offerpilot.modules.profiles.models import Profile, ProfileVersion
    from offerpilot.modules.profiles.schemas import Preferences
    from offerpilot.modules.profiles.service import confirmed_facts

    rows = list(
        await db.scalars(select(Job).where(Job.owner_id == user.id, Job.merged_into_id.is_(None)))
    )
    items = await repository.summaries(db, user.id, rows)
    profile = await db.scalar(
        select(ProfileVersion)
        .join(Profile, Profile.current_version_id == ProfileVersion.id)
        .where(Profile.owner_id == user.id, ProfileVersion.unavailable.is_(False))
    )
    prefs = Preferences.model_validate(profile.preferences) if profile else None
    facts = await confirmed_facts(db, user.id, profile.id) if profile else []
    covered = skill_tokens(" ".join(f.text for f in facts))

    def ranking(job: JobDTO) -> tuple[int, int, int, str, str]:
        data = job.current.data if job.current else None
        cities = set(prefs.cities) & set(data.cities) if prefs and data else set()
        skills = (
            set(s.lower() for r in data.requirements for s in r.skills) & covered if data else set()
        )
        job.ranking_reasons = [
            f"个人意向：{job.preference}",
            f"城市偏好命中：{'、'.join(sorted(cities)) or '暂无明确命中'}",
            f"已确认事实覆盖 {len(skills)} 个技能词；未知项不代表零能力",
        ]
        job.eligibility = check_eligibility(prefs, data)[0] if data else "unknown"
        return (
            {"priority": 0, "interested": 1, "unassigned": 2, "paused": 3, "excluded": 4}.get(
                job.preference, 1
            ),
            -len(cities),
            -len(skills),
            data.deadline.isoformat() if data and data.deadline else "9999-12-31",
            str(job.id),
        )

    items.sort(key=ranking)
    if q:
        items = [
            j
            for j in items
            if j.current
            and q.lower()
            in f"{j.current.data.title} {j.current.data.company} {' '.join(j.current.data.cities)}".lower()
        ]
    if preference:
        items = [j for j in items if j.preference == preference]
    if risk:
        items = [j for j in items if j.verification and j.verification.risk_status == risk]
    else:
        items = [
            j for j in items if not j.verification or j.verification.risk_status != "high_risk_flag"
        ]
    if eligibility:
        items = [j for j in items if j.eligibility == eligibility]
    if cursor:
        position = next((i for i, j in enumerate(items) if j.id == cursor), -1)
        items = items[position + 1 :] if position >= 0 else []
    return Page(
        items=items[:limit],
        has_more=len(items) > limit,
        next_cursor=items[limit - 1].id if len(items) > limit else None,
    )


@router.get("/jobs/{job_id}", response_model=JobDTO)
async def job(job_id: UUID, user: Current, db: DB, response: Response) -> JobDTO:
    result = await repository.detail(db, user.id, job_id)
    response.headers["ETag"] = f'"{result.revision}"'
    return result


@router.post("/jobs/compare", response_model=list[JobDTO])
async def compare(data: IDs, user: Current, db: DB, _: Write) -> list[JobDTO]:
    return [await repository.detail(db, user.id, job_id) for job_id in data.ids]


@router.post("/jobs/{job_id}/versions", response_model=VersionDTO, status_code=201)
async def revise(
    job_id: UUID, data: JobVersionInput, user: Current, db: DB, _: Write
) -> VersionDTO:
    return VersionDTO.model_validate(await service.revise(db, user.id, job_id, data))


@router.put("/jobs/{job_id}/preference", response_model=JobDTO)
async def preference(
    job_id: UUID, data: PreferenceInput, user: Current, db: DB, _: Write
) -> JobDTO:
    await lock_owner(db, user.id)
    if data.preference == "excluded" and not data.reason.strip():
        from offerpilot.api.errors import DomainError

        raise DomainError("reason_required", "排除岗位请记录原因", 422)
    await get_owned(db, Job, user.id, job_id)
    row = await db.scalar(
        select(JobPreference).where(
            JobPreference.owner_id == user.id, JobPreference.job_id == job_id
        )
    )
    if row:
        row.preference, row.reason = data.preference, data.reason
    else:
        db.add(
            JobPreference(
                owner_id=user.id, job_id=job_id, preference=data.preference, reason=data.reason
            )
        )
    await db.commit()
    return await repository.detail(db, user.id, job_id)


@router.post("/matches", response_model=MatchDTO, status_code=201)
async def match(data: MatchInput, user: Current, db: DB, _: Write) -> MatchDTO:
    return await service.match(db, user.id, data)


@router.get("/matches/{report_id}", response_model=MatchDTO)
async def report(report_id: UUID, user: Current, db: DB) -> MatchDTO:
    row = await get_owned(db, MatchReport, user.id, report_id)
    if row.profile_version_id:
        from offerpilot.modules.profiles.service import valid_profile

        await valid_profile(db, user.id, row.profile_version_id)
    return MatchDTO.model_validate(row)


@router.post("/jobs/{job_id}/refresh", response_model=RunDTO, status_code=202)
async def refresh(
    job_id: UUID,
    user: Current,
    db: DB,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> RunDTO:
    from offerpilot.modules.jobs.models import JobSourceLink

    await get_owned(db, Job, user.id, job_id)
    source = await db.scalar(
        select(JobSourceLink).where(
            JobSourceLink.owner_id == user.id, JobSourceLink.job_id == job_id
        )
    )
    if source is None:
        from offerpilot.api.errors import DomainError

        raise DomainError("source_required", "手工岗位未保存来源链接，无法重新提取", 422)
    return RunDTO.model_validate(
        await enqueue(
            db,
            user.id,
            "job_refresh",
            {"job_id": str(job_id), "url": source.canonical_url},
            idempotency_key,
        )
    )
