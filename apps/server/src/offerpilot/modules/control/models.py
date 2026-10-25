from datetime import datetime
from uuid import UUID

from offerpilot.infrastructure.db import Base, Entity
from offerpilot.infrastructure.owned import Owned
from pydantic import JsonValue
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class DeletionRequest(Entity, Base):
    __tablename__ = "deletion_requests"
    owner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="queued")
    run_id: Mapped[UUID | None] = mapped_column()
    target_id: Mapped[UUID | None] = mapped_column()
    profile_ids: Mapped[list[JsonValue]] = mapped_column(JSONB, default=list)
    receipt_hash: Mapped[str | None] = mapped_column(String(64))
    counts: Mapped[dict[str, JsonValue]] = mapped_column(JSONB, default=dict)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExportRequest(Owned, Base):
    __tablename__ = "export_requests"
    status: Mapped[str] = mapped_column(String(30), default="queued")
    format: Mapped[str] = mapped_column(String(10))
    payload: Mapped[dict[str, JsonValue] | None] = mapped_column(JSONB)
    csv_text: Mapped[str | None] = mapped_column()
    run_id: Mapped[UUID | None] = mapped_column(ForeignKey("agent_runs.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
