from uuid import UUID

from fastapi import APIRouter, Header
from offerpilot.api.deps import DB, Current, Write
from offerpilot.api.errors import DomainError
from offerpilot.api.schemas import Page
from offerpilot.infrastructure.owned import get_owned, lock_owner
from offerpilot.modules.discovery.models import (
    SearchCandidate,
    SearchCandidateAnalysis,
    SearchRun,
    SearchSpec,
)
from offerpilot.modules.discovery.opportunities import IntelligenceDTO
from offerpilot.modules.discovery.schemas import (
    CandidateDTO,
    NaturalSearchInput,
    OrganizeInput,
    ParseSpec,
    SearchInput,
    SpecDTO,
    SpecInput,
)
from offerpilot.modules.discovery.service import search_queries, validate_public_query
from offerpilot.modules.runs.models import AgentRun
from offerpilot.modules.runs.schemas import RunDTO
from offerpilot.modules.runs.service import enqueue
from sqlalchemy import select

router = APIRouter(tags=["discovery"])


@router.post("/search-specs/parse", response_model=RunDTO, status_code=202)
async def parse(
    data: ParseSpec,
    user: Current,
    db: DB,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> RunDTO:
    validate_public_query(data.text)
    return RunDTO.model_validate(
        await enqueue(db, user.id, "search_parse", data.model_dump(mode="json"), idempotency_key)
    )


@router.post("/search-specs", response_model=SpecDTO, status_code=201)
async def create(data: SpecInput, user: Current, db: DB, _: Write) -> SpecDTO:
    search_queries(data)
    row = SearchSpec(
        owner_id=user.id,
        keywords=data.keywords,
        raw_keywords=data.raw_keywords or data.keywords,
        data=data.model_dump(mode="json"),
        confirmed=data.confirmed,
    )
    db.add(row)
    await db.commit()
    return SpecDTO.model_validate(row)


@router.get("/search-specs", response_model=Page[SpecDTO])
async def specs(user: Current, db: DB) -> Page[SpecDTO]:
    rows = await db.scalars(
        select(SearchSpec)
        .where(SearchSpec.owner_id == user.id)
        .order_by(SearchSpec.created_at.desc())
        .limit(100)
    )
    return Page(items=[SpecDTO.model_validate(row) for row in rows])


@router.get("/search-specs/{spec_id}", response_model=SpecDTO)
async def spec(spec_id: UUID, user: Current, db: DB) -> SpecDTO:
    return SpecDTO.model_validate(await get_owned(db, SearchSpec, user.id, spec_id))


@router.post("/search-runs", response_model=RunDTO, status_code=202)
async def search(
    data: SearchInput,
    user: Current,
    db: DB,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> RunDTO:
    await lock_owner(db, user.id)
    spec = await get_owned(db, SearchSpec, user.id, data.spec_id)
    if not spec.confirmed:
        raise DomainError("search_unconfirmed", "请先确认搜索条件")
    run = await enqueue(
        db,
        user.id,
        "search",
        {
            "spec": spec.data,
            "spec_id": str(spec.id),
            "public_info_ai_consent": data.public_info_ai_consent,
        },
        idempotency_key,
        commit=False,
    )
    record = await db.scalar(select(SearchRun).where(SearchRun.run_id == run.id))
    if not record:
        db.add(SearchRun(owner_id=user.id, run_id=run.id, spec_id=spec.id, spec_snapshot=spec.data))
    await db.commit()
    return RunDTO.model_validate(run)


@router.post("/search-runs/natural", response_model=RunDTO, status_code=202)
async def natural_search(
    data: NaturalSearchInput,
    user: Current,
    db: DB,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> RunDTO:
    validate_public_query(data.text)
    spec_data = SpecInput(
        keywords=data.text,
        raw_keywords=data.text,
        confirmed=True,
        natural_language=True,
        max_queries=data.max_queries,
        max_results=data.max_results,
        max_extracts=data.max_extracts,
    )
    await lock_owner(db, user.id)
    run = await enqueue(
        db,
        user.id,
        "search",
        {
            "spec": spec_data.model_dump(mode="json"),
            "public_info_ai_consent": data.public_info_ai_consent,
        },
        idempotency_key,
        commit=False,
    )
    exists = await db.scalar(select(SearchRun).where(SearchRun.run_id == run.id))
    if not exists:
        spec = SearchSpec(
            owner_id=user.id,
            keywords=data.text,
            raw_keywords=data.text,
            confirmed=True,
            data=spec_data.model_dump(mode="json"),
        )
        db.add(spec)
        await db.flush()
        db.add(
            SearchRun(
                owner_id=user.id,
                run_id=run.id,
                spec_id=spec.id,
                spec_snapshot=spec_data.model_dump(mode="json"),
            )
        )
    await db.commit()
    return RunDTO.model_validate(run)


@router.post("/search-runs/{run_id}/organize", response_model=RunDTO, status_code=202)
async def organize_existing(
    run_id: UUID,
    data: OrganizeInput,
    user: Current,
    db: DB,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> RunDTO:
    original = await get_owned(db, AgentRun, user.id, run_id)
    if original.kind != "search" or original.status in {"queued", "running"}:
        raise DomainError("search_not_finished", "请等本次搜索结束后再重新整理")
    run = await enqueue(
        db,
        user.id,
        "search_organize",
        {
            "source_search_run_id": str(run_id),
            "public_info_ai_consent": data.public_info_ai_consent,
        },
        idempotency_key,
        commit=False,
    )
    run.result = {**run.result, "source_search_run_id": str(run_id)}
    await db.commit()
    return RunDTO.model_validate(run)


@router.get("/search-runs/{run_id}", response_model=RunDTO)
async def result(run_id: UUID, user: Current, db: DB) -> RunDTO:
    return RunDTO.model_validate(await get_owned(db, AgentRun, user.id, run_id))


@router.get("/search-runs/{run_id}/candidates", response_model=Page[CandidateDTO])
async def candidates(run_id: UUID, user: Current, db: DB) -> Page[CandidateDTO]:
    await get_owned(db, AgentRun, user.id, run_id)
    rows = await db.scalars(
        select(SearchCandidate)
        .where(SearchCandidate.owner_id == user.id, SearchCandidate.run_id == run_id)
        .order_by(SearchCandidate.id)
        .limit(100)
    )
    candidates_list = list(rows)
    analyses = await db.scalars(
        select(SearchCandidateAnalysis)
        .where(
            SearchCandidateAnalysis.owner_id == user.id,
            SearchCandidateAnalysis.candidate_id.in_([r.id for r in candidates_list]),
        )
        .order_by(SearchCandidateAnalysis.created_at.desc(), SearchCandidateAnalysis.id)
    )
    latest: dict[UUID, SearchCandidateAnalysis] = {}
    for analysis in analyses:
        latest.setdefault(analysis.candidate_id, analysis)
    output = []
    for candidate in candidates_list:
        dto = CandidateDTO.model_validate(candidate)
        current_analysis = latest.get(candidate.id)
        if current_analysis and current_analysis.data:
            dto.intelligence = IntelligenceDTO.model_validate(current_analysis.data)
        output.append(dto)
    return Page(items=output)
