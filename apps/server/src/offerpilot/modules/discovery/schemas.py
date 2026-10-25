from datetime import datetime
from typing import Literal
from uuid import UUID

from offerpilot.api.schemas import DTO, Input, Revision
from offerpilot.modules.discovery.opportunities import IntelligenceDTO
from pydantic import Field


class SpecInput(Input):
    keywords: str = Field(min_length=1, max_length=500)
    cities: list[str] = Field(default_factory=list, max_length=10)
    days_per_week: int | None = Field(default=None, ge=1, le=7)
    employment_type: Literal["internship", "graduate", "experienced", "unknown"] = "internship"
    max_queries: int = Field(default=2, ge=1, le=6)
    max_results: int = Field(default=8, ge=1, le=8)
    max_extracts: int = Field(default=10, ge=0, le=20)
    confirmed: bool = False
    raw_keywords: str = Field(default="", max_length=2000)
    natural_language: bool = False


class SpecDTO(DTO):
    id: UUID
    keywords: str
    raw_keywords: str
    data: SpecInput
    confirmed: bool
    created_at: datetime


class ParseSpec(Input):
    text: str = Field(min_length=1, max_length=2000)
    public_info_ai_consent: bool = False


class SearchInput(Input):
    spec_id: UUID
    public_info_ai_consent: bool = False


class NaturalSearchInput(Input):
    text: str = Field(min_length=1, max_length=500)
    max_queries: int = Field(default=3, ge=1, le=6)
    max_results: int = Field(default=8, ge=1, le=8)
    max_extracts: int = Field(default=6, ge=0, le=20)
    public_info_ai_consent: bool = False


class OrganizeInput(Input):
    public_info_ai_consent: bool = False


class CandidateDTO(DTO):
    id: UUID
    url: str
    title: str
    summary: str
    query: str
    query_kind: str
    status: str
    error_code: str | None
    job_id: UUID | None
    created_at: datetime
    intelligence: IntelligenceDTO | None = None


class PolicyInput(Input):
    domain: str = Field(min_length=3, max_length=255, pattern=r"^[a-z0-9.-]+$")
    purpose: Literal["jobs", "interview", "knowledge"] = "jobs"
    mode: Literal["metadata_only", "extract_allowed", "disabled"] = "metadata_only"
    store_text: bool = False
    store_excerpt: bool = True
    official_evidence: str | None = Field(default=None, max_length=2000)
    usage_basis: str = Field(min_length=1, max_length=2000)


class PolicyPatch(PolicyInput, Revision):
    pass


class PolicyDTO(DTO, PolicyInput):
    id: UUID
    revision: int
