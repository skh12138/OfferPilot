from datetime import date
from uuid import UUID

from offerpilot.infrastructure.db import Base
from offerpilot.infrastructure.owned import Owned
from pydantic import JsonValue
from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class InterviewSource(Owned, Base):
    __tablename__ = "interview_sources"
    url: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(30), default="experience")
    company: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(200))
    round_name: Mapped[str | None] = mapped_column(String(100))
    publication_date: Mapped[date | None] = mapped_column(Date)
    interview_date: Mapped[date | None] = mapped_column(Date)
    summary: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str | None] = mapped_column(Text)
    independent_group: Mapped[str] = mapped_column(String(64))
    content_status: Mapped[str] = mapped_column(String(40))
    applicability: Mapped[str] = mapped_column(
        String(1000), default="作者自述，未经独立核实；年份/部门可能不同"
    )
    __table_args__ = (UniqueConstraint("owner_id", "url"), UniqueConstraint("owner_id", "id"))


class StudyPackage(Owned, Base):
    __tablename__ = "study_packages"
    application_id: Mapped[UUID | None] = mapped_column(ForeignKey("applications.id"))
    current_version_id: Mapped[UUID | None] = mapped_column()
    revision: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (UniqueConstraint("owner_id", "id"),)


class StudyPackageVersion(Owned, Base):
    __tablename__ = "study_package_versions"
    package_id: Mapped[UUID] = mapped_column(ForeignKey("study_packages.id"))
    job_version_id: Mapped[UUID] = mapped_column()
    profile_version_id: Mapped[UUID | None] = mapped_column()
    submission_id: Mapped[UUID | None] = mapped_column(ForeignKey("application_submissions.id"))
    round_id: Mapped[UUID | None] = mapped_column(ForeignKey("assessment_rounds.id"))
    basis_revision: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict[str, JsonValue]] = mapped_column(JSONB)
    payload_hash: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(40))
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    adopted: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (
        UniqueConstraint("owner_id", "id"),
        ForeignKeyConstraint(
            ["owner_id", "job_version_id"], ["job_versions.owner_id", "job_versions.id"]
        ),
        ForeignKeyConstraint(
            ["owner_id", "profile_version_id"], ["profile_versions.owner_id", "profile_versions.id"]
        ),
    )


class Question(Owned, Base):
    __tablename__ = "questions"
    package_version_id: Mapped[UUID] = mapped_column()
    data: Mapped[dict[str, JsonValue]] = mapped_column(JSONB)
    __table_args__ = (
        UniqueConstraint("owner_id", "id"),
        ForeignKeyConstraint(
            ["owner_id", "package_version_id"],
            ["study_package_versions.owner_id", "study_package_versions.id"],
        ),
    )


class AnswerAttempt(Owned, Base):
    __tablename__ = "answer_attempts"
    question_id: Mapped[UUID] = mapped_column()
    answer: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        UniqueConstraint("owner_id", "id"),
        ForeignKeyConstraint(["owner_id", "question_id"], ["questions.owner_id", "questions.id"]),
    )


class AnswerFeedback(Owned, Base):
    __tablename__ = "answer_feedback"
    attempt_id: Mapped[UUID] = mapped_column()
    version: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict[str, JsonValue]] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(40))
    __table_args__ = (
        UniqueConstraint("owner_id", "attempt_id", "version"),
        ForeignKeyConstraint(
            ["owner_id", "attempt_id"], ["answer_attempts.owner_id", "answer_attempts.id"]
        ),
    )


class ReviewItem(Owned, Base):
    __tablename__ = "review_items"
    question_id: Mapped[UUID] = mapped_column(ForeignKey("questions.id"))
    topic: Mapped[str] = mapped_column(String(200))
    mastery: Mapped[str] = mapped_column(String(30), default="new")
    ai_suggestion: Mapped[str] = mapped_column(String(30), default="needs_review")
    next_date: Mapped[date] = mapped_column(Date)
    user_correction: Mapped[str] = mapped_column(String(2000), default="")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (UniqueConstraint("owner_id", "question_id"),)


class InterviewReview(Owned, Base):
    __tablename__ = "interview_reviews"
    application_id: Mapped[UUID] = mapped_column()
    round_id: Mapped[UUID | None] = mapped_column()
    questions_asked: Mapped[str] = mapped_column(Text)
    user_answers_summary: Mapped[str] = mapped_column(Text)
    explicit_feedback: Mapped[str] = mapped_column(Text)
    user_inference: Mapped[str] = mapped_column(Text)
    next_steps: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    history: Mapped[list[JsonValue]] = mapped_column(JSONB, default=list)
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "application_id"], ["applications.owner_id", "applications.id"]
        ),
        ForeignKeyConstraint(
            ["owner_id", "round_id"], ["assessment_rounds.owner_id", "assessment_rounds.id"]
        ),
    )
