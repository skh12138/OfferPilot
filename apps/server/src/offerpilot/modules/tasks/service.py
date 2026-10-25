from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from offerpilot.api.errors import DomainError
from offerpilot.infrastructure.db import now
from offerpilot.infrastructure.owned import check_revision, get_owned, lock_owner
from offerpilot.modules.applications.models import Application, AssessmentRound
from offerpilot.modules.tasks.models import Task
from offerpilot.modules.tasks.schemas import TaskDTO, TaskInput, TaskPatch
from sqlalchemy.ext.asyncio import AsyncSession


def dto(row: Task, tz: str = "Asia/Shanghai") -> TaskDTO:
    result = TaskDTO.model_validate(row)
    result.overdue = row.status not in {"done", "cancelled"} and (
        (row.due_at is not None and row.due_at < now())
        or (row.due_date is not None and row.due_date < now().astimezone(ZoneInfo(tz)).date())
    )
    return result


async def validate_links(db: AsyncSession, owner: UUID, data: TaskInput) -> None:
    if data.application_id:
        await get_owned(db, Application, owner, data.application_id)
    if data.round_id:
        row = await get_owned(db, AssessmentRound, owner, data.round_id)
        if data.application_id != row.application_id:
            raise DomainError("invalid_parent", "轮次与申请不一致", 422)


async def create(db: AsyncSession, owner: UUID, data: TaskInput) -> Task:
    await lock_owner(db, owner)
    await validate_links(db, owner, data)
    row = Task(owner_id=owner, business_action_id=f"manual:{uuid4()}", **data.model_dump())
    db.add(row)
    await db.commit()
    return row


async def update(
    db: AsyncSession, owner: UUID, resource: UUID, data: TaskPatch, *, commit: bool = True
) -> Task:
    await lock_owner(db, owner)
    await validate_links(db, owner, data)
    row = await get_owned(db, Task, owner, resource, lock=True)
    check_revision(row.revision, data.expected_revision)
    row.history = [
        *row.history,
        dto(row).model_dump(mode="json") | {"changed_at": now().isoformat()},
    ]
    for field, value in data.model_dump(exclude={"expected_revision"}).items():
        setattr(row, field, value)
    row.revision += 1
    if commit:
        await db.commit()
    return row
