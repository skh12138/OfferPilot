from typing import TypeVar
from uuid import UUID

from offerpilot.api.errors import DomainError
from offerpilot.infrastructure.db import Base, Entity
from offerpilot.modules.identity.models import User
from sqlalchemy import ForeignKey, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column


class Owned(Entity):
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


T = TypeVar("T", bound=Base)


async def get_owned[T: Base](
    db: AsyncSession, model: type[T], owner_id: UUID, resource_id: UUID, *, lock: bool = False
) -> T:
    # Every private model has owner_id and id; this boundary builds columns from metadata.
    table = model.__table__
    query = select(model).where(table.c.owner_id == owner_id, table.c.id == resource_id)
    if lock:
        query = query.with_for_update()
    obj = await db.scalar(query)
    if obj is None:
        raise DomainError("not_found", "资源不存在", 404)
    return obj


async def lock_owner(db: AsyncSession, owner_id: UUID, *, allow_disabled: bool = False) -> User:
    user = await db.scalar(
        select(User)
        .where(User.id == owner_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None or (user.disabled and not allow_disabled):
        raise DomainError("account_unavailable", "账户不可用", 401)
    return user


def check_revision(actual: int, expected: int) -> None:
    if actual != expected:
        raise DomainError("revision_conflict", "内容已更新，请刷新后重试", 412)
