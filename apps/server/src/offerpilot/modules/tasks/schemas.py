from datetime import date
from typing import Literal
from uuid import UUID

from offerpilot.api.schemas import DTO, Input, Revision
from pydantic import AwareDatetime, Field

TaskStatus = Literal["todo", "in_progress", "waiting_external", "done", "cancelled"]
TaskKind = Literal[
    "verify_info",
    "prepare_material",
    "submit_application",
    "check_progress",
    "assessment",
    "interview_prepare",
    "interview_attend",
    "review_interview",
    "practice",
    "offer_decision",
    "onboarding",
    "other",
]


class TaskInput(Input):
    title: str = Field(min_length=1, max_length=200)
    kind: TaskKind = "other"
    application_id: UUID | None = None
    round_id: UUID | None = None
    due_at: AwareDatetime | None = None
    due_date: date | None = None
    deliverable: str = Field(default="", max_length=3000)
    acceptance: str = Field(default="", max_length=3000)


class TaskPatch(TaskInput, Revision):
    status: TaskStatus


class TaskDTO(DTO, TaskInput):
    id: UUID
    status: TaskStatus
    revision: int
    overdue: bool = False


class TaskPatchWithID(TaskPatch):
    id: UUID


class TaskBatch(Input):
    items: list[TaskPatchWithID] = Field(min_length=1, max_length=100)
