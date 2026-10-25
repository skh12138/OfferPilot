import secrets

from fastapi import APIRouter, Request, Response
from offerpilot.api.deps import DB, Current, Write
from offerpilot.api.errors import DomainError
from offerpilot.infrastructure.config import settings
from offerpilot.infrastructure.owned import lock_owner
from offerpilot.modules.identity import service
from offerpilot.modules.identity.models import ModelConsent, SessionToken
from offerpilot.modules.identity.schemas import (
    CSRF,
    ConsentDTO,
    ConsentInput,
    Credentials,
    MessageDTO,
    UserDTO,
)
from sqlalchemy import delete, select

router = APIRouter(tags=["identity"])


@router.get("/auth/csrf", response_model=CSRF)
async def csrf_token(request: Request, response: Response) -> CSRF:
    token = request.cookies.get("op_csrf") or secrets.token_urlsafe(32)
    response.set_cookie(
        "op_csrf",
        token,
        httponly=True,
        secure=settings().environment == "production",
        samesite="lax",
        path="/",
    )
    return CSRF(csrf_token=token)


@router.post("/auth/register", response_model=UserDTO, status_code=201)
async def register(data: Credentials, db: DB, _: Write) -> UserDTO:
    if not settings().allow_registration:
        raise DomainError("registration_disabled", "开放注册未启用", 403)
    return UserDTO.model_validate(await service.register(db, data))


@router.post("/auth/login", response_model=UserDTO)
async def login(
    data: Credentials, request: Request, response: Response, db: DB, _: Write
) -> UserDTO:
    user, token = await service.login(
        db, data, request.client.host if request.client else "unknown"
    )
    response.set_cookie(
        "op_session",
        token,
        max_age=604800,
        httponly=True,
        secure=settings().environment == "production",
        samesite="lax",
        path="/",
    )
    return UserDTO.model_validate(user)


@router.get("/auth/me", response_model=UserDTO)
async def me(user: Current) -> UserDTO:
    return UserDTO.model_validate(user)


@router.post("/auth/logout", response_model=MessageDTO)
async def logout(
    user: Current, db: DB, request: Request, response: Response, _: Write
) -> MessageDTO:
    await db.execute(
        delete(SessionToken).where(
            SessionToken.owner_id == user.id,
            SessionToken.token_hash == service.token_hash(request.cookies.get("op_session", "")),
        )
    )
    await db.commit()
    response.delete_cookie("op_session", path="/")
    return MessageDTO(message="已退出")


@router.get("/me/model-consent", response_model=ConsentDTO)
async def consent(user: Current, db: DB) -> ConsentDTO:
    row = await db.scalar(
        select(ModelConsent)
        .where(ModelConsent.owner_id == user.id)
        .order_by(ModelConsent.version.desc())
        .limit(1)
    )
    return ConsentDTO.model_validate(row) if row else ConsentDTO(granted=False, version=0)


@router.post("/me/model-consent", response_model=ConsentDTO)
async def change_consent(data: ConsentInput, user: Current, db: DB, _: Write) -> ConsentDTO:
    await lock_owner(db, user.id)
    previous = await consent(user, db)
    row = ModelConsent(owner_id=user.id, granted=data.granted, version=previous.version + 1)
    db.add(row)
    if not data.granted:
        from offerpilot.modules.runs.service import cancel_owner_runs

        await cancel_owner_runs(db, user.id)
    await db.commit()
    return ConsentDTO.model_validate(row)
