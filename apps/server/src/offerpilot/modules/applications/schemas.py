from datetime import datetime
from typing import Literal
from uuid import UUID

from offerpilot.api.schemas import DTO, Input, Revision
from pydantic import AwareDatetime, Field

Stage = Literal[
    "interested", "preparing", "submitted", "assessment", "offer", "onboarding", "closed"
]
StatusKind = Literal["received", "screening", "talent_pool", "waiting", "other", "unknown"]


class ApplicationInput(Input):
    title: str = Field(min_length=1, max_length=200)
    company: str = Field(min_length=1, max_length=200)
    job_version_id: UUID | None = None
    profile_version_id: UUID | None = None
    job_url: str | None = None
    apply_url: str | None = None
    progress_url: str | None = None
    navigation_hint: str = Field(default="", max_length=500)
    allow_reapply: bool = False


class ApplicationPatch(Revision):
    company_status_raw: str = Field(default="", max_length=1000)
    company_status_kind: StatusKind = "unknown"
    job_url: str | None = None
    apply_url: str | None = None
    progress_url: str | None = None
    navigation_hint: str = Field(default="", max_length=500)


class ApplicationDTO(DTO):
    id: UUID
    title: str
    company: str
    job_version_id: UUID | None
    profile_version_id: UUID | None
    stage: Stage
    company_status_raw: str
    company_status_kind: StatusKind
    job_url: str | None
    apply_url: str | None
    progress_url: str | None
    navigation_hint: str
    last_checked_at: datetime | None
    revision: int
    basis_revision: int
    basis_submission_id: UUID | None
    is_archived: bool
    onboarding_status: Literal["pending", "joined"]
    created_at: datetime


class EventInput(Revision):
    event_type: Literal["advance", "correction", "reopen", "archive", "note"]
    to_stage: Stage | None = None
    reason: str = Field(min_length=1, max_length=1000)
    source: str = Field(min_length=1, max_length=100)
    happened_at: AwareDatetime
    close_reason: str | None = Field(default=None, max_length=500)
    task_action: Literal["keep", "cancel", "detach"] = "keep"
    is_archived: bool | None = None
    onboarding_status: Literal["pending", "joined"] | None = None
    correction_of_event_id: UUID | None = None


class EventDTO(DTO):
    id: UUID
    event_type: str
    from_stage: str
    to_stage: str
    reason: str
    source: str
    actor: str
    happened_at: datetime
    recorded_at: datetime


class SubmissionInput(Revision):
    actual_submission_confirmed: bool
    submitted_at: AwareDatetime
    channel: str = Field(min_length=1, max_length=100)
    external_application_id: str | None = Field(default=None, max_length=200)
    job_version_id: UUID | None = None
    profile_version_id: UUID | None = None
    material_version_ids: list[UUID] = Field(default_factory=list, max_length=20)
    missing_materials: bool
    correction_of: UUID | None = None
    correction_reason: str | None = Field(default=None, max_length=1000)


class SubmissionDTO(DTO):
    id: UUID
    submitted_at: datetime
    channel: str
    job_version_id: UUID | None
    profile_version_id: UUID | None
    resume_version_id: UUID | None
    material_version_ids: list[UUID]
    missing_materials: bool
    correction_of: UUID | None


class ProgressCheck(Revision):
    checked_at: AwareDatetime
    observed_status: str = Field(max_length=1000)
    changed: bool
    user_confirmed: bool
    company_status_kind: StatusKind = "unknown"


class BasisInput(Revision):
    job_version_id: UUID | None = None
    profile_version_id: UUID | None = None
    submission_id: UUID | None = None
    reason: str = Field(min_length=1, max_length=500)


class RoundInput(Input):
    type: Literal["assessment", "take_home", "technical", "business", "hr", "other"] = "technical"
    name: str = Field(min_length=1, max_length=100)
    order: int = Field(default=1, ge=1, le=100)
    status: Literal[
        "pending",
        "scheduled",
        "completed_waiting_result",
        "passed",
        "failed",
        "cancelled",
        "skipped",
    ] = "scheduled"
    planned_at: AwareDatetime | None = None
    actual_at: AwareDatetime | None = None
    deadline_at: AwareDatetime | None = None
    location: str = Field(default="", max_length=1000)
    reminders_enabled: bool = False


class RoundPatch(RoundInput, Revision):
    reason: str = Field(min_length=1, max_length=500)


class RoundDTO(DTO, RoundInput):
    id: UUID
    application_id: UUID
    revision: int
