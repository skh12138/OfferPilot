from uuid import UUID

from offerpilot.infrastructure.db import Base
from offerpilot.infrastructure.owned import Owned
from pydantic import JsonValue
from sqlalchemy import Boolean, ForeignKey, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class PreparationBundle(Owned, Base):
    __tablename__ = "preparation_bundles"
    application_id: Mapped[UUID] = mapped_column()
    current_version_id: Mapped[UUID | None] = mapped_column()
    revision: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (
        UniqueConstraint("owner_id", "id"),
        ForeignKeyConstraint(
            ["owner_id", "application_id"], ["applications.owner_id", "applications.id"]
        ),
    )


class BundleVersion(Owned, Base):
    __tablename__ = "bundle_versions"
    bundle_id: Mapped[UUID] = mapped_column()
    application_id: Mapped[UUID] = mapped_column()
    job_version_id: Mapped[UUID | None] = mapped_column()
    profile_version_id: Mapped[UUID | None] = mapped_column()
    round_id: Mapped[UUID | None] = mapped_column()
    basis_revision: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict[str, JsonValue]] = mapped_column(JSONB)
    payload_hash: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str] = mapped_column(String(500))
    __table_args__ = (
        UniqueConstraint("owner_id", "id"),
        ForeignKeyConstraint(
            ["owner_id", "bundle_id"], ["preparation_bundles.owner_id", "preparation_bundles.id"]
        ),
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
            ["owner_id", "round_id"], ["assessment_rounds.owner_id", "assessment_rounds.id"]
        ),
    )


class BundleApproval(Owned, Base):
    __tablename__ = "bundle_approvals"
    bundle_version_id: Mapped[UUID] = mapped_column(ForeignKey("bundle_versions.id"))
    payload_hash: Mapped[str] = mapped_column(String(64))
    basis_revision: Mapped[int] = mapped_column(Integer)
    scope: Mapped[str] = mapped_column(String(80))
    __table_args__ = (UniqueConstraint("owner_id", "bundle_version_id", "payload_hash", "scope"),)
