from typing import Literal
from uuid import UUID

from offerpilot.api.schemas import DTO, Input, Revision
from pydantic import Field


class Claim(Input):
    text: str = Field(min_length=1, max_length=3000)
    fact_ids: list[UUID] = Field(min_length=1, max_length=20)
    quotes: list[str] = Field(min_length=1, max_length=20)


class ProposedTask(Input):
    title: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=1000)
    deliverable: str = Field(min_length=1, max_length=3000)
    acceptance: str = Field(min_length=1, max_length=3000)
    priority: Literal["normal", "high"] = "normal"
    requirement_ids: list[UUID] = []
    fact_ids: list[UUID] = []


class BundlePayload(Input):
    claims: list[Claim] = Field(max_length=30)
    gaps: list[str] = Field(max_length=30)
    tasks: list[ProposedTask] = Field(max_length=30)
    introduction: str = Field(max_length=5000)
    contact_draft: str = Field(max_length=5000)


class PreparationInput(Input):
    expected_revision: int = Field(ge=1)
    round_id: UUID | None = None


class BundleVersionDTO(DTO):
    id: UUID
    data: BundlePayload | None
    payload_hash: str
    basis_revision: int
    profile_version_id: UUID | None
    job_version_id: UUID | None
    deleted: bool
    reason: str


class BundleDTO(DTO):
    id: UUID
    application_id: UUID
    revision: int
    current: BundleVersionDTO | None
    versions: list[BundleVersionDTO]


class BundleEdit(Revision):
    data: BundlePayload
    reason: str = Field(min_length=1, max_length=500)


class ApprovalInput(Revision):
    version_id: UUID
    payload_hash: str = Field(min_length=64, max_length=64)
    basis_revision: int = Field(ge=1)
    scope: Literal["tasks", "materials", "tasks,materials"] = "tasks,materials"


class ApprovalDTO(DTO):
    id: UUID
    bundle_version_id: UUID
    scope: str


class ManualBundleInput(Revision):
    data: BundlePayload
    reason: str = Field(min_length=1, max_length=500)
