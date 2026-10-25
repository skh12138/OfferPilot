from uuid import UUID

from fastapi import APIRouter, Header, Query, Response
from offerpilot.api.deps import DB, Current, Write
from offerpilot.api.schemas import Page
from offerpilot.infrastructure.owned import check_revision, get_owned, lock_owner
from offerpilot.modules.applications import service
from offerpilot.modules.applications.models import (
    Application,
    ApplicationEvent,
    ApplicationSubmission,
    AssessmentRound,
)
from offerpilot.modules.applications.schemas import (
    ApplicationDTO,
    ApplicationInput,
    ApplicationPatch,
    BasisInput,
    EventDTO,
    EventInput,
    ProgressCheck,
    RoundDTO,
    RoundInput,
    RoundPatch,
    SubmissionDTO,
    SubmissionInput,
)
from offerpilot.providers.urls import canonical_url
from sqlalchemy import select

router = APIRouter(tags=["applications"])


@router.post("/applications", response_model=ApplicationDTO, status_code=201)
async def create(
    data: ApplicationInput,
    user: Current,
    db: DB,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> ApplicationDTO:
    return ApplicationDTO.model_validate(await service.create(db, user.id, data, idempotency_key))


@router.get("/applications", response_model=Page[ApplicationDTO])
async def applications(
    user: Current,
    db: DB,
    stage: str | None = None,
    cursor: UUID | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> Page[ApplicationDTO]:
    query = select(Application).where(Application.owner_id == user.id).order_by(Application.id)
    if stage:
        query = query.where(Application.stage == stage)
    if cursor:
        query = query.where(Application.id > cursor)
    rows = list(await db.scalars(query.limit(limit + 1)))
    return Page(
        items=[ApplicationDTO.model_validate(r) for r in rows[:limit]],
        has_more=len(rows) > limit,
        next_cursor=rows[limit - 1].id if len(rows) > limit else None,
    )


@router.get("/applications/{app_id}", response_model=ApplicationDTO)
async def application(app_id: UUID, user: Current, db: DB, response: Response) -> ApplicationDTO:
    row = await get_owned(db, Application, user.id, app_id)
    response.headers["ETag"] = f'"{row.revision}"'
    return ApplicationDTO.model_validate(row)


@router.patch("/applications/{app_id}", response_model=ApplicationDTO)
async def patch(
    app_id: UUID, data: ApplicationPatch, user: Current, db: DB, _: Write
) -> ApplicationDTO:
    await lock_owner(db, user.id)
    row = await get_owned(db, Application, user.id, app_id, lock=True)
    check_revision(row.revision, data.expected_revision)
    for name, value in data.model_dump(exclude={"expected_revision"}).items():
        setattr(row, name, canonical_url(str(value)) if name.endswith("_url") and value else value)
    row.revision += 1
    await db.commit()
    return ApplicationDTO.model_validate(row)


@router.get("/applications/{app_id}/events", response_model=Page[EventDTO])
async def events(app_id: UUID, user: Current, db: DB) -> Page[EventDTO]:
    await get_owned(db, Application, user.id, app_id)
    rows = await db.scalars(
        select(ApplicationEvent)
        .where(ApplicationEvent.owner_id == user.id, ApplicationEvent.application_id == app_id)
        .order_by(ApplicationEvent.recorded_at.desc(), ApplicationEvent.id)
        .limit(100)
    )
    return Page(items=[EventDTO.model_validate(r) for r in rows])


@router.post("/applications/{app_id}/events", response_model=ApplicationDTO)
async def event(
    app_id: UUID,
    data: EventInput,
    user: Current,
    db: DB,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> ApplicationDTO:
    return ApplicationDTO.model_validate(
        await service.record_event(db, user.id, app_id, data, idempotency_key)
    )


@router.get("/applications/{app_id}/submissions", response_model=Page[SubmissionDTO])
async def submissions(app_id: UUID, user: Current, db: DB) -> Page[SubmissionDTO]:
    await get_owned(db, Application, user.id, app_id)
    rows = await db.scalars(
        select(ApplicationSubmission)
        .where(
            ApplicationSubmission.owner_id == user.id,
            ApplicationSubmission.application_id == app_id,
        )
        .order_by(ApplicationSubmission.submitted_at.desc())
    )
    return Page(items=[SubmissionDTO.model_validate(r) for r in rows])


@router.post("/applications/{app_id}/submissions", response_model=SubmissionDTO, status_code=201)
async def submit(
    app_id: UUID,
    data: SubmissionInput,
    user: Current,
    db: DB,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> SubmissionDTO:
    return SubmissionDTO.model_validate(
        await service.submit(db, user.id, app_id, data, idempotency_key)
    )


@router.post("/applications/{app_id}/progress-checks", response_model=ApplicationDTO)
async def progress(
    app_id: UUID, data: ProgressCheck, user: Current, db: DB, _: Write
) -> ApplicationDTO:
    return ApplicationDTO.model_validate(await service.progress(db, user.id, app_id, data))


@router.post("/applications/{app_id}/preparation-basis", response_model=ApplicationDTO)
async def basis(app_id: UUID, data: BasisInput, user: Current, db: DB, _: Write) -> ApplicationDTO:
    return ApplicationDTO.model_validate(await service.basis(db, user.id, app_id, data))


@router.get("/applications/{app_id}/rounds", response_model=Page[RoundDTO])
async def rounds(app_id: UUID, user: Current, db: DB) -> Page[RoundDTO]:
    await get_owned(db, Application, user.id, app_id)
    rows = await db.scalars(
        select(AssessmentRound)
        .where(AssessmentRound.owner_id == user.id, AssessmentRound.application_id == app_id)
        .order_by(AssessmentRound.order, AssessmentRound.id)
    )
    return Page(items=[RoundDTO.model_validate(r) for r in rows])


@router.post("/applications/{app_id}/rounds", response_model=RoundDTO, status_code=201)
async def add_round(app_id: UUID, data: RoundInput, user: Current, db: DB, _: Write) -> RoundDTO:
    return RoundDTO.model_validate(await service.add_round(db, user.id, app_id, data))


@router.patch("/rounds/{round_id}", response_model=RoundDTO)
async def update_round(
    round_id: UUID, data: RoundPatch, user: Current, db: DB, _: Write
) -> RoundDTO:
    return RoundDTO.model_validate(await service.update_round(db, user.id, round_id, data))
