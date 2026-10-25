from uuid import UUID

from fastapi import APIRouter, Header
from offerpilot.api.deps import DB, Current, Write
from offerpilot.api.schemas import Page
from offerpilot.infrastructure.owned import lock_owner
from offerpilot.modules.interview import service
from offerpilot.modules.interview.models import InterviewSource, StudyPackage
from offerpilot.modules.interview.schemas import (
    AdoptInput,
    GuidanceDTO,
    InterviewSourceInput,
    ManualSourceInput,
    QuestionDTO,
    QuestionInput,
    SourceDTO,
    StudyDTO,
    StudyEdit,
    StudyInput,
)
from offerpilot.modules.runs.schemas import RunDTO
from offerpilot.modules.runs.service import enqueue
from sqlalchemy import select

router = APIRouter(tags=["interview"])


@router.post("/study-package-runs", response_model=RunDTO, status_code=202)
async def prepare(
    data: StudyInput,
    user: Current,
    db: DB,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> RunDTO:
    await lock_owner(db, user.id)
    job, profile, basis, submission = await service.resolve_basis(db, user.id, data)
    inputs = data.model_dump(mode="json") | {
        "job_version_id": str(job),
        "basis_revision": basis,
        "submission_id": str(submission) if submission else None,
    }
    run = await enqueue(
        db,
        user.id,
        "study",
        inputs,
        idempotency_key,
        profile_id=profile,
        application_id=data.application_id,
    )
    return RunDTO.model_validate(run)


@router.get("/study-packages", response_model=Page[StudyDTO])
async def packages(user: Current, db: DB, application_id: UUID | None = None) -> Page[StudyDTO]:
    query = (
        select(StudyPackage)
        .where(StudyPackage.owner_id == user.id)
        .order_by(StudyPackage.created_at.desc())
    )
    if application_id:
        query = query.where(StudyPackage.application_id == application_id)
    rows = await db.scalars(query.limit(100))
    return Page(items=[await service.detail(db, user.id, row.id) for row in rows])


@router.get("/study-packages/{package_id}", response_model=StudyDTO)
async def package(package_id: UUID, user: Current, db: DB) -> StudyDTO:
    return await service.detail(db, user.id, package_id)


@router.post("/study-packages/{package_id}/versions", response_model=StudyDTO, status_code=201)
async def edit(package_id: UUID, data: StudyEdit, user: Current, db: DB, _: Write) -> StudyDTO:
    await service.edit(db, user.id, package_id, data)
    return await service.detail(db, user.id, package_id)


@router.post("/study-packages/{package_id}/adopt", response_model=StudyDTO)
async def adopt(
    package_id: UUID,
    data: AdoptInput,
    user: Current,
    db: DB,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> StudyDTO:
    return await service.adopt(db, user.id, package_id, data, idempotency_key)


@router.get("/questions/{question_id}", response_model=QuestionDTO)
async def question(question_id: UUID, user: Current, db: DB) -> QuestionDTO:
    return service.question_dto(await service.valid_question(db, user.id, question_id))


@router.get("/questions/{question_id}/guidance", response_model=GuidanceDTO)
async def guidance(question_id: UUID, user: Current, db: DB) -> GuidanceDTO:
    row = await service.valid_question(db, user.id, question_id)
    payload = QuestionInput.model_validate(row.data)
    return GuidanceDTO(
        hints=payload.hints,
        rubric=payload.rubric,
        answer_guidance=payload.answer_guidance,
        follow_ups=payload.follow_ups,
    )


@router.post("/interview-source-runs", response_model=RunDTO, status_code=202)
async def source_search(
    data: InterviewSourceInput,
    user: Current,
    db: DB,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> RunDTO:
    return RunDTO.model_validate(
        await enqueue(
            db, user.id, "interview_sources", data.model_dump(mode="json"), idempotency_key
        )
    )


@router.get("/interview-sources", response_model=Page[SourceDTO])
async def sources(user: Current, db: DB) -> Page[SourceDTO]:
    rows = await db.scalars(
        select(InterviewSource)
        .where(InterviewSource.owner_id == user.id)
        .order_by(InterviewSource.created_at.desc())
        .limit(100)
    )
    return Page(items=[SourceDTO.model_validate(r) for r in rows])


@router.post("/interview-sources", response_model=SourceDTO, status_code=201)
async def manual_source(data: "ManualSourceInput", user: Current, db: DB, _: Write) -> SourceDTO:
    from offerpilot.api.errors import DomainError
    from offerpilot.api.schemas import digest
    from offerpilot.providers.urls import canonical_url

    if not data.permitted_to_store:
        raise DomainError("permission_required", "请确认有权保存所补充的文本", 422)
    url = canonical_url(data.url)
    existing = await db.scalar(
        select(InterviewSource).where(
            InterviewSource.owner_id == user.id, InterviewSource.url == url
        )
    )
    if existing:
        raise DomainError("source_exists", "来源已存在，不能覆盖旧快照")
    row = InterviewSource(
        owner_id=user.id,
        url=url,
        kind="user_review",
        company=data.company,
        role=data.role,
        summary=data.text[:500],
        evidence=data.text,
        publication_date=data.publication_date,
        interview_date=data.interview_date,
        content_status="user_provided",
        independent_group=digest(data.text),
        applicability="用户提供的私有材料，未经独立核实，不跨用户复用",
    )
    db.add(row)
    await db.commit()
    return SourceDTO.model_validate(row)
