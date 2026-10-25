from datetime import date, datetime
from uuid import UUID

from offerpilot.infrastructure.db import Base
from offerpilot.infrastructure.owned import Owned
from pydantic import JsonValue
from sqlalchemy import (
    Date,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class Task(Owned, Base):
    __tablename__ = "tasks"
    application_id: Mapped[UUID | None] = mapped_column()
    round_id: Mapped[UUID | None] = mapped_column()
    bundle_version_id: Mapped[UUID | None] = mapped_column()
    study_version_id: Mapped[UUID | None] = mapped_column()
    business_action_id: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default="todo")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[date | None] = mapped_column(Date)
    deliverable: Mapped[str] = mapped_column(Text, default="")
    acceptance: Mapped[str] = mapped_column(Text, default="")
    history: Mapped[list[JsonValue]] = mapped_column(JSONB, default=list)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "bundle_version_id"], ["bundle_versions.owner_id", "bundle_versions.id"]
        ),
        ForeignKeyConstraint(
            ["owner_id", "study_version_id"],
            ["study_package_versions.owner_id", "study_package_versions.id"],
        ),
        UniqueConstraint("owner_id", "business_action_id"),
        ForeignKeyConstraint(
            ["owner_id", "application_id"], ["applications.owner_id", "applications.id"]
        ),
        ForeignKeyConstraint(
            ["owner_id", "round_id"], ["assessment_rounds.owner_id", "assessment_rounds.id"]
        ),
    )
