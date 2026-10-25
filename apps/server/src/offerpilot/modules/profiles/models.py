from datetime import datetime
from uuid import UUID

from offerpilot.infrastructure.db import Base
from offerpilot.infrastructure.owned import Owned
from pydantic import JsonValue
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class ResumeVersion(Owned, Base):
    __tablename__ = "resume_versions"
    title: Mapped[str] = mapped_column(String(120))
    text: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("owner_id", "id"),)


class ProfileVersion(Owned, Base):
    __tablename__ = "profile_versions"
    resume_version_id: Mapped[UUID | None] = mapped_column()
    preferences: Mapped[dict[str, JsonValue]] = mapped_column(JSONB, default=dict)
    facts: Mapped[list[JsonValue]] = mapped_column(JSONB, default=list)
    reason: Mapped[str] = mapped_column(String(500))
    unavailable: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (
        UniqueConstraint("owner_id", "id"),
        ForeignKeyConstraint(
            ["owner_id", "resume_version_id"], ["resume_versions.owner_id", "resume_versions.id"]
        ),
    )


class Profile(Owned, Base):
    __tablename__ = "profiles"
    current_version_id: Mapped[UUID | None] = mapped_column()
    revision: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (
        UniqueConstraint("owner_id"),
        ForeignKeyConstraint(
            ["owner_id", "current_version_id"], ["profile_versions.owner_id", "profile_versions.id"]
        ),
    )


class FactRevocation(Owned, Base):
    __tablename__ = "fact_revocations"
    fact_id: Mapped[UUID] = mapped_column()
    reason: Mapped[str] = mapped_column(String(500))
    __table_args__ = (UniqueConstraint("owner_id", "fact_id"),)
