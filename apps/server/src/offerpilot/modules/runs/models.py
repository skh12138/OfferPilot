from datetime import datetime
from enum import StrEnum
from uuid import UUID

from offerpilot.infrastructure.db import Base
from offerpilot.infrastructure.owned import Owned
from pydantic import JsonValue
from sqlalchemy import (
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


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL = {RunStatus.SUCCEEDED, RunStatus.PARTIAL, RunStatus.FAILED, RunStatus.CANCELLED}


class AgentRun(Owned, Base):
    __tablename__ = "agent_runs"
    kind: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default=RunStatus.QUEUED, index=True)
    inputs: Mapped[dict[str, JsonValue]] = mapped_column(JSONB)
    result: Mapped[dict[str, JsonValue]] = mapped_column(JSONB, default=dict)
    profile_version_id: Mapped[UUID | None] = mapped_column()
    resume_version_id: Mapped[UUID | None] = mapped_column()
    application_id: Mapped[UUID | None] = mapped_column()
    workflow_version: Mapped[str] = mapped_column(String(40), default="p0-v1")
    prompt_version: Mapped[str] = mapped_column(String(40), default="2026-10-23.6")
    schema_version: Mapped[str] = mapped_column(String(20), default="v1")
    rule_version: Mapped[str] = mapped_column(String(20), default="eligibility-v1")
    model: Mapped[str] = mapped_column(String(80))
    lease_token: Mapped[UUID | None] = mapped_column()
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(String(100))
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    calls_reserved: Mapped[int] = mapped_column(Integer, default=0)
    input_reserved: Mapped[int] = mapped_column(Integer, default=0)
    output_reserved: Mapped[int] = mapped_column(Integer, default=0)
    event_seq: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(80))
    retry_of: Mapped[UUID | None] = mapped_column(ForeignKey("agent_runs.id"))
    __table_args__ = (
        UniqueConstraint("owner_id", "id"),
        ForeignKeyConstraint(
            ["owner_id", "profile_version_id"], ["profile_versions.owner_id", "profile_versions.id"]
        ),
        ForeignKeyConstraint(
            ["owner_id", "resume_version_id"], ["resume_versions.owner_id", "resume_versions.id"]
        ),
        ForeignKeyConstraint(
            ["owner_id", "application_id"], ["applications.owner_id", "applications.id"]
        ),
    )


class RunStep(Owned, Base):
    __tablename__ = "run_steps"
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    step_key: Mapped[str] = mapped_column(String(150))
    input_hash: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict[str, JsonValue]] = mapped_column(JSONB)
    __table_args__ = (UniqueConstraint("run_id", "step_key", "input_hash"),)


class RunEvent(Owned, Base):
    __tablename__ = "run_events"
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(40))
    data: Mapped[dict[str, JsonValue]] = mapped_column(JSONB, default=dict)
    __table_args__ = (UniqueConstraint("run_id", "seq"),)


class ProviderCall(Owned, Base):
    __tablename__ = "provider_calls"
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    step_key: Mapped[str] = mapped_column(String(150))
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str | None] = mapped_column(String(80))
    response_model: Mapped[str | None] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(40))
    parameters: Mapped[dict[str, JsonValue]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="reserved")
    usage: Mapped[dict[str, JsonValue] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(80))
    duration_ms: Mapped[int | None] = mapped_column(Integer)


class IdempotencyRecord(Owned, Base):
    __tablename__ = "idempotency_records"
    operation: Mapped[str] = mapped_column(String(120))
    key: Mapped[str] = mapped_column(String(120))
    payload_hash: Mapped[str] = mapped_column(String(64))
    result_id: Mapped[UUID] = mapped_column()
    __table_args__ = (UniqueConstraint("owner_id", "operation", "key"),)


class AuditEvent(Owned, Base):
    __tablename__ = "audit_events"
    action: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[UUID | None] = mapped_column()
    details: Mapped[str] = mapped_column(Text, default="")
