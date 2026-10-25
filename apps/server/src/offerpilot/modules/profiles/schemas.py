from datetime import date, datetime
from typing import Literal
from uuid import UUID

from offerpilot.api.schemas import DTO, Input, Revision
from pydantic import Field


class Evidence(Input):
    snapshot_id: UUID | None = None
    paragraph_id: str = Field(max_length=40)
    quote: str = Field(min_length=1, max_length=5000)
    source_kind: Literal["resume_text", "user_asserted", "user_provided", "provider_extracted"]


class Fact(Input):
    fact_id: UUID
    text: str = Field(min_length=1, max_length=3000)
    status: Literal["user_confirmed", "unconfirmed", "planned", "disputed"] = "unconfirmed"
    evidence: Evidence


class Preferences(Input):
    target_roles: list[str] = Field(default_factory=list, max_length=10)
    cities: list[str] = Field(default_factory=list, max_length=10)
    education: Literal["secondary", "associate", "bachelor", "master", "doctor"] | None = None
    graduation_year: int | None = Field(default=None, ge=2000, le=2100)
    days_per_week: int | None = Field(default=None, ge=1, le=7)
    duration_months: int | None = Field(default=None, ge=1, le=60)
    start_date: date | None = None
    work_mode_is_hard: bool = False
    work_mode: Literal["onsite", "remote", "hybrid"] | None = None
    notes: str = Field(default="", max_length=2000)


class ResumeInput(Input):
    parse: bool = True
    title: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=50000)


class ResumeDTO(DTO):
    id: UUID
    title: str
    text: str | None
    deleted_at: datetime | None
    created_at: datetime


class ProfileInput(Input):
    resume_version_id: UUID | None = None
    preferences: Preferences = Preferences()
    facts: list[Fact] = Field(default_factory=list, max_length=200)
    reason: str = Field(min_length=1, max_length=500)


class ProfileDTO(DTO):
    revoked_fact_ids: list[UUID] = []
    id: UUID
    resume_version_id: UUID | None
    preferences: Preferences
    facts: list[Fact]
    reason: str
    unavailable: bool
    created_at: datetime


class CurrentDTO(DTO):
    revision: int
    current: ProfileDTO | None
    versions: list[ProfileDTO]


class Selection(Revision):
    profile_version_id: UUID


class Revoke(Input):
    fact_id: UUID
    reason: str = Field(min_length=1, max_length=500)


class ParsedFacts(Input):
    facts: list[Fact] = Field(max_length=200)
