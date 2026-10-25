from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from offerpilot.api.schemas import DTO, Input, Revision
from pydantic import Field

Decision = Literal["undecided", "negotiating", "accepted", "declined", "expired", "withdrawn"]


class Terms(Input):
    city: str | None = Field(default=None, max_length=200)
    responsibilities: str | None = Field(default=None, max_length=3000)
    start_date: date | None = None
    duration_months: int | None = Field(default=None, ge=1, le=60)
    days_per_week: int | None = Field(default=None, ge=1, le=7)
    mentoring: str | None = Field(default=None, max_length=1000)
    benefits: str | None = Field(default=None, max_length=2000)
    expiration_clause: str | None = Field(default=None, max_length=2000)
    notes: str = Field(default="", max_length=2000)


class OfferInput(Input):
    application_id: UUID
    notification_confirmed: bool
    type: Literal["oral", "written"]
    source: str = Field(min_length=1, max_length=1000)
    salary_minimum: Decimal | None = Field(default=None, ge=0)
    salary_maximum: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="CNY", max_length=10)
    salary_unit: Literal["day", "month", "year", "hour", "unknown"] = "unknown"
    salary_raw: str = Field(default="", max_length=1000)
    terms: Terms = Terms()
    reply_deadline: date | None = None


class OfferDTO(DTO):
    id: UUID
    application_id: UUID
    type: str
    source: str
    salary_minimum: Decimal | None
    salary_maximum: Decimal | None
    currency: str
    salary_unit: str
    salary_raw: str
    terms: Terms
    reply_deadline: date | None
    decision: Decision
    revision: int


class OfferEventInput(Revision):
    decision: Decision
    reason: str = Field(min_length=1, max_length=2000)
    user_confirmed: bool
    type: Literal["oral", "written"] | None = None
    terms: Terms | None = None
    reply_deadline: date | None = None


class OfferEventDTO(DTO):
    id: UUID
    offer_id: UUID
    decision: str
    reason: str
