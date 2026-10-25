from datetime import date
from uuid import UUID

from fastapi import APIRouter, Header
from offerpilot.api.deps import DB, Current, Write
from offerpilot.api.errors import DomainError
from offerpilot.api.schemas import Page
from offerpilot.infrastructure.owned import get_owned, lock_owner
from offerpilot.modules.interview import service
from offerpilot.modules.interview.models import AnswerAttempt, AnswerFeedback, ReviewItem
from offerpilot.modules.interview.schemas import (
    AttemptDTO,
    AttemptInput,
    FeedbackDTO,
    ReviewDTO,
    ReviewPatch,
)
from offerpilot.modules.runs.schemas import RunDTO
from offerpilot.modules.runs.service import enqueue, idempotent, remember
from sqlalchemy import select

router = APIRouter(tags=["practice"])


@router.post("/questions/{question_id}/attempts", response_model=AttemptDTO, status_code=201)
async def answer(
    question_id: UUID,
    data: AttemptInput,
    user: Current,
    db: DB,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> AttemptDTO:
    await lock_owner(db, user.id)
    question = await service.valid_question(db, user.id, question_id)
    version = await service.active_version(db, user.id, question.package_version_id)
    old = await idempotent(
        db, user.id, f"answer:{question_id}", idempotency_key, data.model_dump(mode="json")
    )
    if old:
        attempt = await get_owned(db, AnswerAttempt, user.id, old)
    else:
        attempt = AnswerAttempt(owner_id=user.id, question_id=question.id, answer=data.answer)
        db.add(attempt)
        await db.flush()
        remember(
            db,
            user.id,
            f"answer:{question_id}",
            str(idempotency_key),
            data.model_dump(mode="json"),
            attempt.id,
        )
        await db.commit()
    result = AttemptDTO.model_validate(attempt)
    try:
        run = await enqueue(
            db,
            user.id,
            "feedback",
            {"attempt_id": str(attempt.id), "job_version_id": str(version.job_version_id)},
            str(idempotency_key),
            profile_id=version.profile_version_id,
        )
        result.feedback_run_id = run.id
    except DomainError as exc:
        # Answer is already committed. Missing credentials/consent must not erase it.
        await db.rollback()
        result.feedback_error_code = exc.code
    return result


@router.get("/attempts/{attempt_id}", response_model=AttemptDTO)
async def attempt(attempt_id: UUID, user: Current, db: DB) -> AttemptDTO:
    row = await get_owned(db, AnswerAttempt, user.id, attempt_id)
    await service.valid_question(db, user.id, row.question_id)
    return AttemptDTO.model_validate(row)


@router.get("/attempts/{attempt_id}/feedback", response_model=Page[FeedbackDTO])
async def feedback(attempt_id: UUID, user: Current, db: DB) -> Page[FeedbackDTO]:
    row = await get_owned(db, AnswerAttempt, user.id, attempt_id)
    await service.valid_question(db, user.id, row.question_id)
    rows = await db.scalars(
        select(AnswerFeedback)
        .where(AnswerFeedback.owner_id == user.id, AnswerFeedback.attempt_id == row.id)
        .order_by(AnswerFeedback.version.desc())
    )
    return Page(items=[FeedbackDTO.model_validate(r) for r in rows])


@router.post("/attempts/{attempt_id}/feedback-retry", response_model=RunDTO, status_code=202)
async def retry(
    attempt_id: UUID,
    user: Current,
    db: DB,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> RunDTO:
    attempt = await get_owned(db, AnswerAttempt, user.id, attempt_id)
    question = await service.valid_question(db, user.id, attempt.question_id)
    version = await service.active_version(db, user.id, question.package_version_id)
    return RunDTO.model_validate(
        await enqueue(
            db,
            user.id,
            "feedback",
            {"attempt_id": str(attempt.id), "job_version_id": str(version.job_version_id)},
            idempotency_key,
            profile_id=version.profile_version_id,
        )
    )


@router.get("/review-items", response_model=Page[ReviewDTO])
async def reviews(user: Current, db: DB) -> Page[ReviewDTO]:
    rows = await db.scalars(
        select(ReviewItem)
        .where(ReviewItem.owner_id == user.id)
        .order_by(ReviewItem.next_date, ReviewItem.id)
        .limit(100)
    )
    return Page(items=[ReviewDTO.model_validate(r) for r in rows])


@router.patch("/review-items/{item_id}", response_model=ReviewDTO)
async def update(item_id: UUID, data: ReviewPatch, user: Current, db: DB, _: Write) -> ReviewDTO:
    return ReviewDTO.model_validate(
        await service.update_review(db, user.id, item_id, data, date.today())
    )


@router.get("/questions/{question_id}/attempts", response_model=Page[AttemptDTO])
async def attempts(question_id: UUID, user: Current, db: DB) -> Page[AttemptDTO]:
    from offerpilot.modules.runs.models import AgentRun

    await service.valid_question(db, user.id, question_id)
    rows = await db.scalars(
        select(AnswerAttempt)
        .where(AnswerAttempt.owner_id == user.id, AnswerAttempt.question_id == question_id)
        .order_by(AnswerAttempt.created_at.desc())
        .limit(20)
    )
    items: list[AttemptDTO] = []
    for row in rows:
        dto = AttemptDTO.model_validate(row)
        run = await db.scalar(
            select(AgentRun)
            .where(
                AgentRun.owner_id == user.id,
                AgentRun.kind == "feedback",
                AgentRun.inputs["attempt_id"].as_string() == str(row.id),
            )
            .order_by(AgentRun.created_at.desc())
            .limit(1)
        )
        dto.feedback_run_id = run.id if run else None
        items.append(dto)
    return Page(items=items)
