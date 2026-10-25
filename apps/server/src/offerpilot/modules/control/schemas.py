from datetime import datetime
from typing import Literal
from uuid import UUID

from offerpilot.api.schemas import DTO, Input
from pydantic import Field


class DeleteResumeInput(Input):
    confirmed: bool


class DeleteAccountInput(Input):
    password: str = Field(min_length=1, max_length=128)
    confirmed: bool


class DeletionDTO(DTO):
    id: UUID
    kind: str
    status: str
    run_id: UUID | None
    counts: dict[str, int]
    completed_at: datetime | None
    receipt: str | None = None


class DeletePreview(DTO):
    resume_id: UUID
    profile_versions: int
    material_versions: int
    study_versions: int
    active_runs: int
    preserved: list[str]


class ExportInput(Input):
    format: Literal["json", "csv"] = "json"


class ExportDTO(DTO):
    id: UUID
    status: str
    format: str
    expires_at: datetime
    run_id: UUID | None
