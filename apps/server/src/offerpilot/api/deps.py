import secrets
from typing import Annotated

from fastapi import Depends, Request
from offerpilot.api.errors import DomainError
from offerpilot.infrastructure.config import settings
from offerpilot.infrastructure.db import now, session
from offerpilot.modules.identity.models import ModelConsent, SessionToken, User
from offerpilot.modules.identity.service import token_hash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

DB = Annotated[AsyncSession, Depends(session)]


async def csrf(request: Request) -> None:
    if request.headers.get("origin") != settings().public_origin:
        raise DomainError("origin_rejected", "请求来源不受信任", 403)
    header, cookie = request.headers.get("x-csrf-token", ""), request.cookies.get("op_csrf", "")
    if not header or not cookie or not secrets.compare_digest(header, cookie):
        raise DomainError("csrf_rejected", "请刷新页面后重试", 403)


async def current_user(request: Request, db: DB) -> User:
    token = request.cookies.get("op_session")
    if not token:
        raise DomainError("unauthenticated", "请先登录", 401)
    user = await db.scalar(
        select(User)
        .join(SessionToken, SessionToken.owner_id == User.id)
        .where(
            SessionToken.token_hash == token_hash(token),
            SessionToken.expires_at > now(),
            User.disabled.is_(False),
        )
    )
    if user is None:
        raise DomainError("unauthenticated", "登录已失效", 401)
    return user


Current = Annotated[User, Depends(current_user)]
Write = Annotated[None, Depends(csrf)]


async def admin_user(user: Current) -> User:
    if not user.is_admin:
        raise DomainError("forbidden", "需要运营权限", 403)
    return user


Admin = Annotated[User, Depends(admin_user)]


async def require_consent(db: AsyncSession, owner_id: object) -> None:
    consent = await db.scalar(
        select(ModelConsent)
        .where(ModelConsent.owner_id == owner_id)
        .order_by(ModelConsent.version.desc())
        .limit(1)
    )
    if not consent or not consent.granted:
        raise DomainError("model_consent_required", "请先授权必要资料的外部模型处理", 409)
