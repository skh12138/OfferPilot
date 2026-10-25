from datetime import date
from decimal import Decimal
from uuid import UUID

from offerpilot.infrastructure.db import Base
from offerpilot.infrastructure.owned import Owned
from pydantic import JsonValue
from sqlalchemy import Date, ForeignKey, ForeignKeyConstraint, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class Offer(Owned, Base):
    __tablename__ = "offers"
    application_id: Mapped[UUID] = mapped_column()
    type: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(1000))
    salary_minimum: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    salary_maximum: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    salary_unit: Mapped[str] = mapped_column(String(20))
    salary_raw: Mapped[str] = mapped_column(String(1000))
    terms: Mapped[dict[str, JsonValue]] = mapped_column(JSONB)
    reply_deadline: Mapped[date | None] = mapped_column(Date)
    decision: Mapped[str] = mapped_column(String(30), default="undecided")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "application_id"], ["applications.owner_id", "applications.id"]
        ),
    )


class OfferEvent(Owned, Base):
    __tablename__ = "offer_events"
    offer_id: Mapped[UUID] = mapped_column(ForeignKey("offers.id"))
    decision: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text)
    previous: Mapped[dict[str, JsonValue]] = mapped_column(JSONB)
    data: Mapped[dict[str, JsonValue]] = mapped_column(JSONB)
