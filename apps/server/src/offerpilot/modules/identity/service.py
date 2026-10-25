import hashlib
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from offerpilot.api.errors import DomainError
from offerpilot.infrastructure.db import now
from offerpilot.modules.identity.models import LoginFailure, SessionToken, User
from offerpilot.modules.identity.schemas import Credentials
from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash("synthetic-timing-placeholder")


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def register(db: AsyncSession, data: Credentials, admin: bool = False) -> User:
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:name))"), {"name": data.username.lower()}
    )
    if await db.scalar(select(User).where(User.username == data.username.lower())):
        raise DomainError("username_unavailable", "用户名不可用")
    user = User(
        username=data.username.lower(), password_hash=hasher.hash(data.password), is_admin=admin
    )
    db.add(user)
    await db.commit()
    return user


async def login(db: AsyncSession, data: Credentials, ip: str) -> tuple[User, str]:
    account, source = token_hash(data.username.lower()), token_hash(ip)
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": source})
    failures = await db.scalar(
        select(func.count())
        .select_from(LoginFailure)
        .where(
            or_(LoginFailure.account_key == account, LoginFailure.ip_key == source),
            LoginFailure.created_at > now() - timedelta(minutes=15),
        )
    )
    if failures and failures >= 10:
        raise DomainError("login_rate_limited", "尝试过多，请稍后再试", 429)
    user = await db.scalar(
        select(User).where(User.username == data.username.lower(), User.disabled.is_(False))
    )
    valid: bool
    try:
        valid = hasher.verify(user.password_hash if user else DUMMY_HASH, data.password)
    except VerificationError:
        valid = False
    if not user or not valid:
        db.add(LoginFailure(account_key=account, ip_key=source))
        await db.commit()
        raise DomainError("invalid_credentials", "用户名或密码错误", 401)
    token = secrets.token_urlsafe(48)
    db.add(
        SessionToken(
            owner_id=user.id, token_hash=token_hash(token), expires_at=now() + timedelta(days=7)
        )
    )
    await db.execute(delete(LoginFailure).where(LoginFailure.account_key == account))
    await db.commit()
    return user, token
