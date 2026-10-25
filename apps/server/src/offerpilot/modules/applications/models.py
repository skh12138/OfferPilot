from datetime import datetime
from uuid import UUID

from offerpilot.infrastructure.db import Base, now
from offerpilot.infrastructure.owned import Owned
from pydantic import JsonValue
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class Application(Owned, Base):
    __tablename__ = "applications"
    title: Mapped[str] = mapped_column(String(200))
    company: Mapped[str] = mapped_column(String(200))
    job_version_id: Mapped[UUID | None] = mapped_column()
    profile_version_id: Mapped[UUID | None] = mapped_column()
    stage: Mapped[str] = mapped_column(String(30), default="interested")
    company_status_raw: Mapped[str] = mapped_column(String(1000), default="")
    company_status_kind: Mapped[str] = mapped_column(String(30), default="unknown")
    job_url: Mapped[str | None] = mapped_column(Text)
    apply_url: Mapped[str | None] = mapped_column(Text)
    progress_url: Mapped[str | None] = mapped_column(Text)
    navigation_hint: Mapped[str] = mapped_column(String(500), default="")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    basis_revision: Mapped[int] = mapped_column(Integer, default=1)
    basis_submission_id: Mapped[UUID | None] = mapped_column()
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarding_status: Mapped[str] = mapped_column(String(20), default="pending")
    __table_args__ = (
        UniqueConstraint("owner_id", "id"),
        ForeignKeyConstraint(
            ["owner_id", "job_version_id"], ["job_versions.owner_id", "job_versions.id"]
        ),
        ForeignKeyConstraint(
            ["owner_id", "profile_version_id"], ["profile_versions.owner_id", "profile_versions.id"]
        ),
    )


class ApplicationSubmission(Owned, Base):
    __tablename__ = "application_submissions"
    application_id: Mapped[UUID] = mapped_column()
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    channel: Mapped[str] = mapped_column(String(100))
    external_application_id: Mapped[str | None] = mapped_column(String(200))
    job_version_id: Mapped[UUID | None] = mapped_column()
    profile_version_id: Mapped[UUID | None] = mapped_column()
    resume_version_id: Mapped[UUID | None] = mapped_column()
    material_version_ids: Mapped[list[JsonValue]] = mapped_column(JSONB, default=list)
    missing_materials: Mapped[bool] = mapped_column(Boolean)
    correction_of: Mapped[UUID | None] = mapped_column(ForeignKey("application_submissions.id"))
    __table_args__ = (
        UniqueConstraint("owner_id", "id"),
        ForeignKeyConstraint(
            ["owner_id", "application_id"], ["applications.owner_id", "applications.id"]
        ),
        ForeignKeyConstraint(
            ["owner_id", "job_version_id"], ["job_versions.owner_id", "job_versions.id"]
        ),
        ForeignKeyConstraint(
            ["owner_id", "profile_version_id"], ["profile_versions.owner_id", "profile_versions.id"]
        ),
        ForeignKeyConstraint(
            ["owner_id", "resume_version_id"], ["resume_versions.owner_id", "resume_versions.id"]
        ),
    )


class ApplicationEvent(Owned, Base):
    __tablename__ = "application_events"
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"))
    event_type: Mapped[str] = mapped_column(String(40))
    from_stage: Mapped[str] = mapped_column(String(30))
    to_stage: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(String(1000))
    source: Mapped[str] = mapped_column(String(100))
    actor: Mapped[str] = mapped_column(String(40), default="user")
    happened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    details: Mapped[dict[str, JsonValue]] = mapped_column(JSONB, default=dict)


class AssessmentRound(Owned, Base):
    __tablename__ = "assessment_rounds"
    application_id: Mapped[UUID] = mapped_column()
    type: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(100))
    order: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40))
    planned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location: Mapped[str] = mapped_column(String(1000), default="")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (
        UniqueConstraint("owner_id", "id"),
        ForeignKeyConstraint(
            ["owner_id", "application_id"], ["applications.owner_id", "applications.id"]
        ),
    )
