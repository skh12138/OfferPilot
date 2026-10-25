import hashlib
import json
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)


T = TypeVar("T")


class Page[T](BaseModel):
    items: list[T]
    next_cursor: UUID | None = None
    has_more: bool = False


class Revision(Input):
    expected_revision: int = Field(ge=1)


class IDs(Input):
    ids: list[UUID] = Field(min_length=1, max_length=4)


def digest(data: JsonValue) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
