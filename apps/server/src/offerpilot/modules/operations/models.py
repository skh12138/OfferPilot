from uuid import UUID

from offerpilot.infrastructure.db import Base
from offerpilot.infrastructure.owned import Owned
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class FeedbackReport(Owned, Base):
    __tablename__ = "feedback_reports"
    target_kind: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[UUID | None] = mapped_column()
    message: Mapped[str] = mapped_column(Text)
    shared_excerpt: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="open")
    resolution: Mapped[str] = mapped_column(Text, default="")
    revision: Mapped[int] = mapped_column(Integer, default=1)
