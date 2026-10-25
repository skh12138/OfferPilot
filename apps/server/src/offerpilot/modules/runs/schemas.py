from datetime import datetime
from uuid import UUID

from offerpilot.api.schemas import DTO
from offerpilot.modules.runs.models import RunStatus
from pydantic import JsonValue


class RunDTO(DTO):
    id: UUID
    application_id: UUID | None
    kind: str
    status: RunStatus
    result: dict[str, JsonValue]
    error_code: str | None
    calls_reserved: int
    input_reserved: int
    output_reserved: int
    attempt: int
    created_at: datetime
    completed_at: datetime | None
    cancel_requested_at: datetime | None


class EventDTO(DTO):
    seq: int
    event_type: str
    data: dict[str, JsonValue]
