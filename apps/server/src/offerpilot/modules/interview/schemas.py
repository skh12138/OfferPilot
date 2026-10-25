from datetime import date, datetime
from typing import Literal
from uuid import UUID

from offerpilot.api.schemas import DTO, Input, Revision
from pydantic import Field


class SourceReference(Input):
    source_id: UUID
    quote: str = Field(min_length=1, max_length=2000)


class QuestionInput(Input):
    topic: str = Field(min_length=1, max_length=200)
    kind: Literal[
        "introduction",
        "project",
        "technical",
        "scenario",
        "coding",
        "behavioral",
        "hr",
        "reverse_question",
    ]
    difficulty: Literal["easy", "medium", "hard"]
    prompt: str = Field(min_length=1, max_length=5000)
    recommendation_reason: str = Field(min_length=1, max_length=2000)
    requirement_ids: list[UUID] = Field(default_factory=list, max_length=30)
    fact_ids: list[UUID] = Field(default_factory=list, max_length=30)
    source_kind: Literal["experience_reported", "generated_for_target", "general_practice"]
    source_refs: list[SourceReference] = Field(default_factory=list, max_length=10)
    inspired_by: list[SourceReference] = Field(default_factory=list, max_length=10)
    rubric: list[str] = Field(min_length=1, max_length=20)
    hints: list[str] = Field(default_factory=list, max_length=10)
    answer_guidance: str = Field(max_length=5000)
    follow_ups: list[str] = Field(default_factory=list, max_length=10)
    quality_flags: list[str] = Field(default_factory=list, max_length=20)


class QuestionDTO(DTO):
    id: UUID
    topic: str
    kind: Literal[
        "introduction",
        "project",
        "technical",
        "scenario",
        "coding",
        "behavioral",
        "hr",
        "reverse_question",
    ]
    difficulty: Literal["easy", "medium", "hard"]
    prompt: str
    recommendation_reason: str
    requirement_ids: list[UUID]
    fact_ids: list[UUID]
    source_kind: Literal["experience_reported", "generated_for_target", "general_practice"]
    source_refs: list[SourceReference]
    inspired_by: list[SourceReference]
    quality_flags: list[str]


class GuidanceDTO(DTO):
    hints: list[str]
    rubric: list[str]
    answer_guidance: str
    follow_ups: list[str]


class Topic(Input):
    topic: str = Field(max_length=200)
    reason: str = Field(max_length=1000)
    requirement_ids: list[UUID] = Field(default_factory=list, max_length=30)


class StudyPayload(Input):
    topics: list[Topic] = Field(min_length=1, max_length=30)
    limitations: list[str] = Field(max_length=30)
    questions: list[QuestionInput] = Field(min_length=5, max_length=15)


class StudyInput(Input):
    application_id: UUID | None = None
    job_version_id: UUID | None = None
    profile_version_id: UUID | None = None
    round_id: UUID | None = None
    count: int = Field(default=8, ge=5, le=15)
    include_interview_search: bool = True
    interview_date: date | None = None


class StudyVersionDTO(DTO):
    id: UUID
    job_version_id: UUID
    profile_version_id: UUID | None
    basis_revision: int
    topics: list[Topic]
    limitations: list[str]
    questions: list[QuestionDTO]
    payload_hash: str
    adopted: bool
    deleted: bool


class StudyDTO(DTO):
    id: UUID
    application_id: UUID | None
    revision: int
    current: StudyVersionDTO | None
    versions: list[StudyVersionDTO]


class StudyEdit(Revision):
    data: StudyPayload
    reason: str = Field(min_length=1, max_length=500)


class AdoptInput(Revision):
    version_id: UUID
    payload_hash: str = Field(min_length=64, max_length=64)
    basis_revision: int


class AttemptInput(Input):
    answer: str = Field(min_length=1, max_length=50000)


class AttemptDTO(DTO):
    id: UUID
    question_id: UUID
    answer: str | None
    created_at: datetime
    feedback_run_id: UUID | None = None
    feedback_error_code: str | None = None


class FeedbackPayload(Input):
    strengths: list[str] = Field(max_length=20)
    issues: list[str] = Field(max_length=20)
    suggested_revision_outline: list[str] = Field(max_length=20)
    follow_up_question: str = Field(max_length=3000)
    topic_observations: list[str] = Field(max_length=20)
    uncertainties: list[str] = Field(max_length=20)
    levels: dict[Literal["correctness", "completeness", "structure", "evidence", "relevance"], str]
    fact_ids: list[UUID] = Field(default_factory=list, max_length=30)


class FeedbackDTO(DTO):
    id: UUID
    version: int
    data: FeedbackPayload
    model: str
    created_at: datetime


class ReviewPatch(Revision):
    mastery: Literal["new", "needs_review", "practicing", "confident"]
    next_date: date | None = None
    user_correction: str = Field(default="", max_length=2000)


class ReviewDTO(DTO):
    id: UUID
    question_id: UUID
    topic: str
    mastery: str
    ai_suggestion: str
    next_date: date
    user_correction: str
    revision: int


class InterviewSourceInput(Input):
    query: str = Field(min_length=1, max_length=500)
    company: str = Field(default="", max_length=200)
    role: str = Field(default="", max_length=200)


class SourceDTO(DTO):
    id: UUID
    url: str
    kind: str
    company: str
    role: str
    publication_date: date | None
    interview_date: date | None
    summary: str
    evidence: str | None
    independent_group: str
    content_status: str
    applicability: str


class InterviewReviewInput(Input):
    application_id: UUID
    round_id: UUID | None = None
    questions_asked: str = Field(default="", max_length=10000)
    user_answers_summary: str = Field(default="", max_length=10000)
    explicit_feedback: str = Field(default="", max_length=5000)
    user_inference: str = Field(default="", max_length=5000)
    next_steps: str = Field(default="", max_length=5000)


class InterviewReviewPatch(InterviewReviewInput, Revision):
    pass


class InterviewReviewDTO(DTO, InterviewReviewInput):
    id: UUID
    revision: int


class ManualSourceInput(Input):
    url: str = Field(max_length=2000)
    company: str = Field(max_length=200)
    role: str = Field(max_length=200)
    text: str = Field(min_length=1, max_length=5000)
    publication_date: date | None = None
    interview_date: date | None = None
    permitted_to_store: bool
