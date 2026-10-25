from uuid import UUID

from offerpilot.infrastructure.db import Base, Entity
from offerpilot.infrastructure.owned import Owned
from pydantic import JsonValue
from sqlalchemy import (
    Boolean,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class SourcePolicy(Entity, Base):
    __tablename__ = "source_policies"
    domain: Mapped[str] = mapped_column(String(255), unique=True)
    purpose: Mapped[str] = mapped_column(String(30), default="jobs")
    mode: Mapped[str] = mapped_column(String(30), default="metadata_only")
    store_text: Mapped[bool] = mapped_column(Boolean, default=False)
    store_excerpt: Mapped[bool] = mapped_column(Boolean, default=True)
    official_evidence: Mapped[str | None] = mapped_column(Text)
    usage_basis: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class SearchSpec(Owned, Base):
    __tablename__ = "search_specs"
    keywords: Mapped[str] = mapped_column(String(500))
    raw_keywords: Mapped[str] = mapped_column(String(2000))
    data: Mapped[dict[str, JsonValue]] = mapped_column(JSONB)
    confirmed: Mapped[bool] = mapped_column(Boolean)
    __table_args__ = (UniqueConstraint("owner_id", "id"),)


class SearchRun(Owned, Base):
    __tablename__ = "search_runs"
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), unique=True
    )
    spec_id: Mapped[UUID] = mapped_column()
    spec_snapshot: Mapped[dict[str, JsonValue]] = mapped_column(JSONB)
    __table_args__ = (
        ForeignKeyConstraint(["owner_id", "spec_id"], ["search_specs.owner_id", "search_specs.id"]),
    )


class SearchCandidate(Owned, Base):
    __tablename__ = "search_candidates"
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text)
    query: Mapped[str] = mapped_column(String(1000))
    query_kind: Mapped[str] = mapped_column(String(30), default="user_confirmed")
    status: Mapped[str] = mapped_column(String(40), default="metadata_only")
    error_code: Mapped[str | None] = mapped_column(String(80))
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id"))
    __table_args__ = (UniqueConstraint("run_id", "url"), UniqueConstraint("owner_id", "id"))


class SearchCandidateAnalysis(Owned, Base):
    __tablename__ = "search_candidate_analyses"
    candidate_id: Mapped[UUID] = mapped_column(index=True)
    analysis_run_id: Mapped[UUID] = mapped_column()
    data: Mapped[dict[str, JsonValue]] = mapped_column(JSONB)
    __table_args__ = (
        UniqueConstraint("owner_id", "candidate_id", "analysis_run_id"),
        ForeignKeyConstraint(
            ["owner_id", "candidate_id"], ["search_candidates.owner_id", "search_candidates.id"]
        ),
        ForeignKeyConstraint(
            ["owner_id", "analysis_run_id"], ["agent_runs.owner_id", "agent_runs.id"]
        ),
    )
