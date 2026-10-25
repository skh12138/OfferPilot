from datetime import datetime
from typing import Literal
from uuid import UUID

from offerpilot.api.schemas import DTO, Input, Revision
from pydantic import Field


class ReportInput(Input):
    target_kind: Literal["job", "question", "application", "other"]
    target_id: UUID | None = None
    message: str = Field(min_length=1, max_length=5000)
    shared_excerpt: str = Field(default="", max_length=3000)
    share_confirmed: bool = False


class ReportDTO(DTO):
    id: UUID
    target_kind: str
    target_id: UUID | None
    message: str
    shared_excerpt: str
    status: str
    resolution: str
    revision: int
    created_at: datetime


class Resolution(Revision):
    status: Literal["in_review", "resolved", "rejected"]
    resolution: str = Field(min_length=1, max_length=3000)


class OperationsDTO(DTO):
    providers: dict[str, bool]
    queue_states: dict[str, int]
    failure_codes: dict[str, int]
    unknown_usage_calls: int
    reserved_calls: int


class OverviewDTO(DTO):
    from_date: datetime | None
    to_date: datetime
    sample_size: int
    stages: dict[str, int]
    actual_submissions: int
    waiting_or_unknown: int
    task_statuses: dict[str, int]
    weak_topics: list[str]
    note: str
