from uuid import UUID

from fastapi import APIRouter
from offerpilot.api.deps import DB, Current, Write
from offerpilot.api.errors import DomainError
from offerpilot.api.schemas import Page
from offerpilot.infrastructure.owned import check_revision, get_owned, lock_owner
from offerpilot.modules.applications.models import Application, AssessmentRound
from offerpilot.modules.interview.models import InterviewReview
from offerpilot.modules.interview.schemas import (
    InterviewReviewDTO,
    InterviewReviewInput,
    InterviewReviewPatch,
)
from sqlalchemy import select

router = APIRouter(tags=["reviews"])


async def validate_parent(data: InterviewReviewInput, user: Current, db: DB) -> None:
    await get_owned(db, Application, user.id, data.application_id)
    if data.round_id:
        rnd = await get_owned(db, AssessmentRound, user.id, data.round_id)
        if rnd.application_id != data.application_id:
            raise DomainError("not_found", "轮次不存在", 404)


@router.post("/interview-reviews", response_model=InterviewReviewDTO, status_code=201)
async def create(data: InterviewReviewInput, user: Current, db: DB, _: Write) -> InterviewReviewDTO:
    await validate_parent(data, user, db)
    row = InterviewReview(owner_id=user.id, **data.model_dump())
    db.add(row)
    await db.commit()
    return InterviewReviewDTO.model_validate(row)


@router.get("/interview-reviews", response_model=Page[InterviewReviewDTO])
async def reviews(user: Current, db: DB) -> Page[InterviewReviewDTO]:
    rows = await db.scalars(
        select(InterviewReview)
        .where(InterviewReview.owner_id == user.id)
        .order_by(InterviewReview.created_at.desc())
        .limit(100)
    )
    return Page(items=[InterviewReviewDTO.model_validate(r) for r in rows])


@router.get("/interview-reviews/{review_id}", response_model=InterviewReviewDTO)
async def review(review_id: UUID, user: Current, db: DB) -> InterviewReviewDTO:
    return InterviewReviewDTO.model_validate(
        await get_owned(db, InterviewReview, user.id, review_id)
    )


@router.patch("/interview-reviews/{review_id}", response_model=InterviewReviewDTO)
async def update(
    review_id: UUID, data: InterviewReviewPatch, user: Current, db: DB, _: Write
) -> InterviewReviewDTO:
    await lock_owner(db, user.id)
    row = await get_owned(db, InterviewReview, user.id, review_id, lock=True)
    check_revision(row.revision, data.expected_revision)
    await validate_parent(data, user, db)
    row.history = [*row.history, InterviewReviewDTO.model_validate(row).model_dump(mode="json")]
    for name, value in data.model_dump(exclude={"expected_revision"}).items():
        setattr(row, name, value)
    row.revision += 1
    await db.commit()
    return InterviewReviewDTO.model_validate(row)
