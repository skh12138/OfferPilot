"""Public search intelligence is separate from verified JD facts and eligibility rules."""

import re
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from offerpilot.api.schemas import Input
from pydantic import Field


class DifficultyPrediction(Input):
    level: Literal["easy", "medium", "hard", "unknown"] = "unknown"
    reason: str = Field(default="信息不足，暂无法判断", max_length=600)
    preparation: list[str] = Field(default_factory=list, max_length=5)


class Opportunity(Input):
    title: str = Field(min_length=1, max_length=250)
    company: str | None = Field(default=None, max_length=200)
    cities: list[str] = Field(default_factory=list, max_length=10)
    salary: str | None = Field(default=None, max_length=200)
    education: str | None = Field(default=None, max_length=200)
    attendance: str | None = Field(default=None, max_length=200)
    deadline: str | None = Field(default=None, max_length=200)
    responsibilities: list[str] = Field(default_factory=list, max_length=5)
    requirements: list[str] = Field(default_factory=list, max_length=7)
    relevance: Literal["high", "possible", "low"] = "possible"
    relevance_reason: str = Field(default="", max_length=500)
    difficulty: DifficultyPrediction = DifficultyPrediction()


class CandidateIntelligence(Input):
    candidate_id: UUID
    kind: Literal["position", "listing", "irrelevant", "unclear"]
    opportunities: list[Opportunity] = Field(default_factory=list, max_length=3)
    note: str = Field(default="", max_length=500)


class IntelligenceBatch(Input):
    items: list[CandidateIntelligence] = Field(max_length=4)


class IntelligenceDTO(Input):
    kind: Literal["position", "listing", "irrelevant", "unclear"]
    opportunities: list[Opportunity]
    note: str
    basis: Literal["job_text", "search_excerpt"]
    prompt_version: str


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()


def check_scope(position: Opportunity, cities: list[str]) -> None:
    # City fields may contain districts (杭州余杭区), which are within the requested city.
    matches = any(
        wanted in actual or actual in wanted for wanted in cities for actual in position.cities
    )
    city_evidence = [city for city in position.cities if not re.fullmatch(r".{1,3}[区县]", city)]
    if cities and city_evidence and not matches:
        position.relevance = "low"
        position.relevance_reason = (
            "来源显示地点为" + "、".join(position.cities) + "，与你输入的城市不同，请核实。"
        )
    graduating = re.search(r"(20\d{2})\s*届", position.title)
    if graduating and int(graduating[1]) < datetime.now(UTC).year - 1:
        position.relevance = "low"
        position.relevance_reason = (
            "来源标题包含较早的" + graduating[0] + "招聘信息，可能已不适用，请到原站核实。"
        )


def sanitize(item: CandidateIntelligence, evidence: str) -> CandidateIntelligence:
    """Only source-supported strings become facts; difficulty remains explicitly a prediction."""
    original = compact(evidence)

    def supported(value: str | None) -> bool:
        return bool(value and compact(value) in original)

    positions: list[Opportunity] = []
    if item.kind == "irrelevant":
        return item.model_copy(update={"opportunities": []})
    for raw in item.opportunities:
        if not supported(raw.title):
            continue
        position = raw.model_copy(deep=True)
        for field in ["company", "salary", "education", "attendance", "deadline"]:
            if not supported(getattr(position, field)):
                setattr(position, field, None)
        position.cities = [city for city in position.cities if supported(city)]
        position.requirements = [text for text in position.requirements if supported(text)]
        position.responsibilities = [text for text in position.responsibilities if supported(text)]
        # A generic directory is not a specific vacancy just because the target mentions a role.
        if item.kind == "listing" and not position.company:
            continue
        if re.search(r"招聘信息$|职位列表$|岗位大全$|搜索结果$", position.title):
            continue
        positions.append(position)
    return item.model_copy(update={"opportunities": positions})
