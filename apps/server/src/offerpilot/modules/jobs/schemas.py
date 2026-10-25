from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from offerpilot.api.schemas import DTO, Input, Revision
from offerpilot.modules.profiles.schemas import Evidence
from pydantic import Field, JsonValue, model_validator


class Condition(Input):
    value: str | int | list[str] | None = None
    strength: Literal["hard", "preferred", "negotiable"] = "hard"
    review_status: Literal["confirmed", "unreviewed", "conflict", "missing"] = "missing"
    evidence_status: Literal["supported", "unsupported", "user_asserted"] = "unsupported"
    unrestricted: bool = False
    unit: str | None = None
    evidence: Evidence | None = None


class Requirement(Input):
    requirement_id: UUID
    text: str = Field(min_length=1, max_length=3000)
    skills: list[str] = Field(default_factory=list, max_length=20)
    strength: Literal["hard", "preferred", "negotiable"] = "hard"
    evidence: Evidence | None = None


class Salary(Input):
    minimum: Decimal | None = Field(default=None, ge=0)
    maximum: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="CNY", max_length=10)
    unit: Literal["day", "month", "year", "hour", "unknown"] = "unknown"
    raw: str = Field(default="", max_length=500)


class FieldProvenance(Input):
    value: JsonValue
    review_status: Literal["confirmed", "unreviewed", "conflict", "missing"] = "unreviewed"
    evidence_status: Literal["supported", "unsupported", "user_asserted"] = "unsupported"
    source_kind: Literal["user_provided", "provider_extracted", "user_asserted"]
    snapshot_id: UUID | None = None
    paragraph_id: str | None = None
    quote: str | None = Field(default=None, max_length=5000)
    explanation: str | None = Field(default=None, max_length=1000)


class JobExtraction(Input):
    field_evidence: dict[str, FieldProvenance] = Field(default_factory=dict)
    classification: Literal["job_detail", "job_list", "non_job", "unknown"] = "unknown"
    title: str = Field(min_length=1, max_length=200)
    company: str = Field(default="待核实", max_length=200)
    department: str | None = Field(default=None, max_length=200)
    source_job_id: str | None = Field(default=None, max_length=200)
    batch: str | None = Field(default=None, max_length=100)
    cities: list[str] = Field(default_factory=list, max_length=20)
    work_mode: Literal["onsite", "remote", "hybrid", "unknown"] = "unknown"
    employment_type: Literal["internship", "graduate", "experienced", "unknown"] = "unknown"
    conditions: dict[
        Literal[
            "days_per_week",
            "duration_months",
            "graduation_year",
            "cities",
            "work_mode",
            "education",
        ],
        Condition,
    ] = Field(default_factory=dict)
    start: date | None = None
    deadline: date | None = None
    published_date: date | None = None
    page_updated_date: date | None = None
    salary: Salary = Salary()
    requirements: list[Requirement] = Field(default_factory=list, max_length=100)
    responsibilities: list[str] = Field(default_factory=list, max_length=100)
    conflicts: list[str] = Field(default_factory=list, max_length=50)
    missing_fields: list[str] = Field(default_factory=list, max_length=50)


class JobImport(Input):
    text: str = Field(min_length=1, max_length=5242880)
    url: str | None = Field(default=None, max_length=2000)
    format: Literal["text", "csv"] = "text"

    @model_validator(mode="after")
    def input_size(self) -> "JobImport":
        if self.format == "text" and len(self.text) > 50000:
            raise ValueError("纯文本最多50000字符")
        if self.format == "csv" and len(self.text.encode()) > 5242880:
            raise ValueError("CSV最多5MB")
        return self


class JobVersionInput(Input):
    expected_revision: int = Field(ge=1)
    data: JobExtraction
    reason: str = Field(min_length=1, max_length=500)
    confirm_fields: bool = False


class VersionDTO(DTO):
    id: UUID
    job_id: UUID
    snapshot_id: UUID | None
    data: JobExtraction
    reason: str
    created_at: datetime


class SnapshotDTO(DTO):
    id: UUID
    kind: str
    text: str | None
    paragraphs: dict[str, str]
    url: str | None
    created_at: datetime


class SourceLinkDTO(DTO):
    id: UUID
    aliases: list[str] = []
    canonical_url: str
    board: str
    source_job_id: str | None


class VerificationDTO(DTO):
    source_status: str
    availability_status: str
    risk_status: str
    evidence: list[str]
    method: str
    checked_at: datetime


class JobDTO(DTO):
    id: UUID
    revision: int
    current_version_id: UUID | None
    current: VersionDTO | None = None
    versions: list[VersionDTO] = []
    snapshots: list[SnapshotDTO] = []
    sources: list[SourceLinkDTO] = []
    verification: VerificationDTO | None = None
    preference: str = "unassigned"
    eligibility: Literal["pass", "fail", "unknown"] = "unknown"
    ranking_reasons: list[str] = []
    merged_into_id: UUID | None = None


class PreferenceInput(Input):
    preference: Literal["interested", "priority", "paused", "excluded"]
    reason: str = Field(default="", max_length=500)


class MatchInput(Input):
    job_version_id: UUID
    profile_version_id: UUID | None = None


class Check(DTO):
    key: str
    status: Literal["pass", "fail", "unknown"]
    reason: str
    evidence: str | None = None


class MatchDTO(DTO):
    id: UUID
    job_version_id: UUID
    profile_version_id: UUID | None
    rule_version: str
    overall: Literal["pass", "fail", "unknown"]
    checks: list[Check]
    fact_ids: list[UUID] = []


class DuplicateDTO(DTO):
    id: UUID
    left_id: UUID
    right_id: UUID
    reason: str
    decision: str | None
    revision: int


class DuplicateDecision(Revision):
    decision: Literal["merge", "keep_separate"]
    reason: str = Field(min_length=1, max_length=500)


class MergeDTO(DTO):
    id: UUID
    source_id: UUID
    target_id: UUID
    undone: bool
