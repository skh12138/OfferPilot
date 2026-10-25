from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Header, Query
from offerpilot.api.deps import DB, Current, Write
from offerpilot.api.schemas import Page
from offerpilot.infrastructure.db import now
from offerpilot.modules.applications.schemas import RoundDTO
from offerpilot.modules.interview.schemas import ReviewDTO
from offerpilot.modules.offers.schemas import OfferDTO
from offerpilot.modules.tasks import service
from offerpilot.modules.tasks.models import Task
from offerpilot.modules.tasks.schemas import TaskBatch, TaskDTO, TaskInput, TaskPatch
from pydantic import BaseModel
from sqlalchemy import select

router = APIRouter(tags=["tasks"])


@router.get("/tasks", response_model=Page[TaskDTO])
async def tasks(
    user: Current,
    db: DB,
    application_id: UUID | None = None,
    status: str | None = None,
    cursor: UUID | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> Page[TaskDTO]:
    query = select(Task).where(Task.owner_id == user.id).order_by(Task.id)
    if application_id:
        query = query.where(Task.application_id == application_id)
    if status:
        query = query.where(Task.status == status)
    if cursor:
        query = query.where(Task.id > cursor)
    rows = list(await db.scalars(query.limit(limit + 1)))
    return Page(
        items=[service.dto(r, user.timezone) for r in rows[:limit]],
        has_more=len(rows) > limit,
        next_cursor=rows[limit - 1].id if len(rows) > limit else None,
    )


@router.post("/tasks", response_model=TaskDTO, status_code=201)
async def create(data: TaskInput, user: Current, db: DB, _: Write) -> TaskDTO:
    return service.dto(await service.create(db, user.id, data), user.timezone)


@router.patch("/tasks/{task_id}", response_model=TaskDTO)
async def update(task_id: UUID, data: TaskPatch, user: Current, db: DB, _: Write) -> TaskDTO:
    return service.dto(await service.update(db, user.id, task_id, data), user.timezone)


class TodayDTO(BaseModel):
    timezone: str
    tasks: list[TaskDTO]
    next_seven_days: list[TaskDTO]
    overdue: list[TaskDTO]
    pending_confirmation: int
    rounds: list[RoundDTO]
    offer_deadlines: list[OfferDTO]
    review_due: list[ReviewDTO]


@router.get("/dashboard/today", response_model=TodayDTO)
async def today(user: Current, db: DB) -> TodayDTO:
    from zoneinfo import ZoneInfo

    from offerpilot.modules.profiles.models import Profile, ProfileVersion

    day = now().astimezone(ZoneInfo(user.timezone)).date()
    rows = list(
        await db.scalars(
            select(Task)
            .where(Task.owner_id == user.id, Task.status.notin_(["done", "cancelled"]))
            .order_by(Task.due_at.nullslast(), Task.id)
            .limit(500)
        )
    )
    all_tasks = [service.dto(t, user.timezone) for t in rows]

    def task_day(task: TaskDTO) -> "date | None":
        return (
            task.due_at.astimezone(ZoneInfo(user.timezone)).date() if task.due_at else task.due_date
        )

    current = await db.scalar(
        select(ProfileVersion)
        .join(Profile, Profile.current_version_id == ProfileVersion.id)
        .where(Profile.owner_id == user.id)
    )
    pending = (
        sum(isinstance(f, dict) and f.get("status") == "unconfirmed" for f in current.facts)
        if current
        else 0
    )
    from offerpilot.modules.applications.models import AssessmentRound
    from offerpilot.modules.interview.models import ReviewItem
    from offerpilot.modules.offers.models import Offer

    rounds = list(
        await db.scalars(
            select(AssessmentRound).where(
                AssessmentRound.owner_id == user.id,
                AssessmentRound.status.in_(["pending", "scheduled"]),
            )
        )
    )
    upcoming = [
        r
        for r in rounds
        if r.planned_at
        and day
        <= r.planned_at.astimezone(ZoneInfo(user.timezone)).date()
        <= day + timedelta(days=7)
    ]
    offers = await db.scalars(
        select(Offer).where(
            Offer.owner_id == user.id,
            Offer.reply_deadline.is_not(None),
            Offer.reply_deadline <= day + timedelta(days=7),
            Offer.decision.in_(["undecided", "negotiating"]),
        )
    )
    review_due = await db.scalars(
        select(ReviewItem).where(
            ReviewItem.owner_id == user.id, ReviewItem.next_date <= day + timedelta(days=7)
        )
    )
    return TodayDTO(
        timezone=user.timezone,
        rounds=[RoundDTO.model_validate(r) for r in upcoming],
        offer_deadlines=[OfferDTO.model_validate(o) for o in offers],
        review_due=[ReviewDTO.model_validate(r) for r in review_due],
        tasks=[t for t in all_tasks if task_day(t) == day or task_day(t) is None],
        next_seven_days=[
            t
            for t in all_tasks
            if (d := task_day(t)) is not None and day < d <= day + timedelta(days=7)
        ],
        overdue=[t for t in all_tasks if t.overdue],
        pending_confirmation=pending,
    )


@router.post("/tasks/batch", response_model=Page[TaskDTO])
async def batch(
    data: "TaskBatch",
    user: Current,
    db: DB,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> Page[TaskDTO]:
    from offerpilot.infrastructure.owned import get_owned, lock_owner
    from offerpilot.modules.runs.service import idempotent, remember

    await lock_owner(db, user.id)
    payload = data.model_dump(mode="json")
    old = await idempotent(db, user.id, "task-batch", idempotency_key, payload)
    if old:
        rows = [await get_owned(db, Task, user.id, item.id) for item in data.items]
        return Page(items=[service.dto(r, user.timezone) for r in rows])
    rows = []
    for item in data.items:
        patch = TaskPatch.model_validate(item.model_dump(exclude={"id"}))
        rows.append(await service.update(db, user.id, item.id, patch, commit=False))
    remember(db, user.id, "task-batch", str(idempotency_key), payload, rows[0].id)
    await db.commit()
    return Page(items=[service.dto(r, user.timezone) for r in rows])
