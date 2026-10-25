from uuid import UUID

from fastapi import APIRouter, Header
from offerpilot.api.deps import DB, Current, Write
from offerpilot.api.schemas import IDs, Page
from offerpilot.infrastructure.owned import get_owned
from offerpilot.modules.offers import service
from offerpilot.modules.offers.models import Offer, OfferEvent
from offerpilot.modules.offers.schemas import OfferDTO, OfferEventDTO, OfferEventInput, OfferInput
from sqlalchemy import select

router = APIRouter(tags=["offers"])


@router.post("/offers", response_model=OfferDTO, status_code=201)
async def create(data: OfferInput, user: Current, db: DB, _: Write) -> OfferDTO:
    return OfferDTO.model_validate(await service.create(db, user.id, data))


@router.get("/offers", response_model=Page[OfferDTO])
async def offers(user: Current, db: DB) -> Page[OfferDTO]:
    rows = await db.scalars(
        select(Offer).where(Offer.owner_id == user.id).order_by(Offer.created_at.desc()).limit(100)
    )
    return Page(items=[OfferDTO.model_validate(r) for r in rows])


@router.get("/offers/{offer_id}", response_model=OfferDTO)
async def offer(offer_id: UUID, user: Current, db: DB) -> OfferDTO:
    return OfferDTO.model_validate(await get_owned(db, Offer, user.id, offer_id))


@router.post("/offers/{offer_id}/events", response_model=OfferDTO)
async def event(
    offer_id: UUID,
    data: OfferEventInput,
    user: Current,
    db: DB,
    _: Write,
    idempotency_key: str | None = Header(default=None),
) -> OfferDTO:
    return OfferDTO.model_validate(
        await service.event(db, user.id, offer_id, data, idempotency_key)
    )


@router.get("/offers/{offer_id}/events", response_model=Page[OfferEventDTO])
async def events(offer_id: UUID, user: Current, db: DB) -> Page[OfferEventDTO]:
    await get_owned(db, Offer, user.id, offer_id)
    rows = await db.scalars(
        select(OfferEvent)
        .where(OfferEvent.owner_id == user.id, OfferEvent.offer_id == offer_id)
        .order_by(OfferEvent.created_at)
    )
    return Page(items=[OfferEventDTO.model_validate(r) for r in rows])


@router.post("/offers/compare", response_model=list[OfferDTO])
async def compare(data: IDs, user: Current, db: DB, _: Write) -> list[OfferDTO]:
    return [
        OfferDTO.model_validate(await get_owned(db, Offer, user.id, offer_id))
        for offer_id in data.ids
    ]
