from uuid import UUID

from offerpilot.api.errors import DomainError
from offerpilot.infrastructure.db import now
from offerpilot.infrastructure.owned import check_revision, get_owned, lock_owner
from offerpilot.modules.applications.models import Application
from offerpilot.modules.applications.rules import transition
from offerpilot.modules.applications.service import append_event
from offerpilot.modules.offers.models import Offer, OfferEvent
from offerpilot.modules.offers.schemas import OfferDTO, OfferEventInput, OfferInput
from offerpilot.modules.runs.service import idempotent, remember
from sqlalchemy.ext.asyncio import AsyncSession


async def create(db: AsyncSession, owner: UUID, data: OfferInput) -> Offer:
    await lock_owner(db, owner)
    app = await get_owned(db, Application, owner, data.application_id, lock=True)
    if not data.notification_confirmed:
        raise DomainError("notification_required", "请确认收到实际口头或书面通知", 422)
    target = app.stage if app.stage in {"offer", "onboarding"} else "offer"
    transition(app.stage, target, "advance", "实际 Offer 通知", evidence="offer")
    values = data.model_dump(exclude={"notification_confirmed", "terms"})
    row = Offer(owner_id=owner, **values, terms=data.terms.model_dump(mode="json"))
    db.add(row)
    await db.flush()
    append_event(
        db,
        app,
        "offer_received",
        target,
        f"收到{data.type}通知",
        data.source,
        now(),
        details={"offer_id": str(row.id)},
    )
    db.add(
        OfferEvent(
            owner_id=owner,
            offer_id=row.id,
            decision="undecided",
            reason="本人记录实际通知",
            previous={},
            data=data.model_dump(mode="json"),
        )
    )
    await db.commit()
    return row


async def event(
    db: AsyncSession, owner: UUID, offer_id: UUID, data: OfferEventInput, key: str | None
) -> Offer:
    await lock_owner(db, owner)
    payload, op = data.model_dump(mode="json"), f"offer:{offer_id}"
    old = await idempotent(db, owner, op, key, payload)
    if old:
        return await get_owned(db, Offer, owner, old)
    row = await get_owned(db, Offer, owner, offer_id, lock=True)
    check_revision(row.revision, data.expected_revision)
    if not data.user_confirmed:
        raise DomainError("confirmation_required", "决定由本人确认", 422)
    previous = OfferDTO.model_validate(row).model_dump(mode="json")
    if data.decision == "accepted":
        app = await get_owned(db, Application, owner, row.application_id, lock=True)
        transition(app.stage, "onboarding", "advance", "本人接受决定", evidence="acceptance")
        append_event(
            db,
            app,
            "offer_accepted",
            "onboarding",
            data.reason,
            "user",
            now(),
            details={"offer_id": str(row.id)},
        )
    row.decision, row.revision = data.decision, row.revision + 1
    if data.type:
        row.type = data.type
    if data.terms:
        row.terms = data.terms.model_dump(mode="json")
    if "reply_deadline" in data.model_fields_set:
        row.reply_deadline = data.reply_deadline
    db.add(
        OfferEvent(
            owner_id=owner,
            offer_id=row.id,
            decision=data.decision,
            reason=data.reason,
            previous=previous,
            data=payload,
        )
    )
    remember(db, owner, op, str(key), payload, row.id)
    await db.commit()
    return row
