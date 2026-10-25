from uuid import UUID

from offerpilot.api.schemas import DTO, Input
from pydantic import Field


class Credentials(Input):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=10, max_length=128)


class UserDTO(DTO):
    id: UUID
    username: str
    is_admin: bool
    timezone: str


class CSRF(DTO):
    csrf_token: str


class ConsentInput(Input):
    granted: bool


class ConsentDTO(DTO):
    granted: bool
    version: int
    scope: str = "resume,materials,study,feedback"


class MessageDTO(DTO):
    message: str
