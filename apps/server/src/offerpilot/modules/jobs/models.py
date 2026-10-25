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


class TextSnapshot(Owned, Base):
    __tablename__ = "text_snapshots"
    kind: Mapped[str] = mapped_column(String(40))
    text: Mapped[str | None] = mapped_column(Text)
    paragraphs: Mapped[dict[str, JsonValue]] = mapped_column(JSONB)
    url: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint("owner_id", "id"),)


class Job(Owned, Base):
    __tablename__ = "jobs"
    current_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("job_versions.id", use_alter=True, name="fk_jobs_current_version")
    )
    revision: Mapped[int] = mapped_column(Integer, default=1)
    merged_into_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id"))
    __table_args__ = (UniqueConstraint("owner_id", "id"),)


class JobVersion(Owned, Base):
    __tablename__ = "job_versions"
    job_id: Mapped[UUID] = mapped_column()
    snapshot_id: Mapped[UUID | None] = mapped_column()
    data: Mapped[dict[str, JsonValue]] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(String(500))
    __table_args__ = (
        UniqueConstraint("owner_id", "id"),
        ForeignKeyConstraint(["owner_id", "job_id"], ["jobs.owner_id", "jobs.id"]),
        ForeignKeyConstraint(
            ["owner_id", "snapshot_id"], ["text_snapshots.owner_id", "text_snapshots.id"]
        ),
    )


class JobSourceLink(Owned, Base):
    __tablename__ = "job_source_links"
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id"))
    aliases: Mapped[list[JsonValue]] = mapped_column(JSONB, default=list)
    canonical_url: Mapped[str] = mapped_column(Text)
    board: Mapped[str] = mapped_column(String(255))
    source_job_id: Mapped[str | None] = mapped_column(String(200))
    __table_args__ = (
        UniqueConstraint("owner_id", "canonical_url"),
        UniqueConstraint("owner_id", "board", "source_job_id"),
    )


class JobVerification(Owned, Base):
    __tablename__ = "job_verifications"
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id"))
    source_status: Mapped[str] = mapped_column(String(40))
    availability_status: Mapped[str] = mapped_column(String(40))
    risk_status: Mapped[str] = mapped_column(String(40))
    evidence: Mapped[list[JsonValue]] = mapped_column(JSONB)
    method: Mapped[str] = mapped_column(String(100), default="rules-v1")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class JobPreference(Owned, Base):
    __tablename__ = "job_preferences"
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id"))
    preference: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(500))
    __table_args__ = (UniqueConstraint("owner_id", "job_id"),)


class DuplicateReview(Owned, Base):
    __tablename__ = "duplicate_reviews"
    left_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id"))
    right_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id"))
    reason: Mapped[str] = mapped_column(String(1000))
    decision: Mapped[str | None] = mapped_column(String(30))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (UniqueConstraint("owner_id", "left_id", "right_id"),)


class JobMergeEvent(Owned, Base):
    __tablename__ = "job_merge_events"
    source_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id"))
    target_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id"))
    reason: Mapped[str] = mapped_column(String(500))
    undone: Mapped[bool] = mapped_column(Boolean, default=False)


class MatchReport(Owned, Base):
    __tablename__ = "match_reports"
    job_version_id: Mapped[UUID] = mapped_column()
    profile_version_id: Mapped[UUID | None] = mapped_column()
    rule_version: Mapped[str] = mapped_column(String(40))
    overall: Mapped[str] = mapped_column(String(10))
    checks: Mapped[list[JsonValue]] = mapped_column(JSONB)
    fact_ids: Mapped[list[JsonValue]] = mapped_column(JSONB, default=list)
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "job_version_id"], ["job_versions.owner_id", "job_versions.id"]
        ),
        ForeignKeyConstraint(
            ["owner_id", "profile_version_id"], ["profile_versions.owner_id", "profile_versions.id"]
        ),
    )
