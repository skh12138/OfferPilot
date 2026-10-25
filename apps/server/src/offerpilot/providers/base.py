from typing import Protocol

from pydantic import BaseModel, ConfigDict, JsonValue


class ProviderError(Exception):
    def __init__(self, code: str, retryable: bool = False) -> None:
        self.code, self.retryable = code, retryable


class Usage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    credits: float | None = None
    response_model: str | None = None


class SearchHit(BaseModel):
    model_config = ConfigDict(extra="ignore")
    url: str
    title: str
    content: str = ""
    published_date: str | None = None


class SearchResult(BaseModel):
    results: list[SearchHit]
    usage: Usage = Usage()


class ContentResult(BaseModel):
    texts: dict[str, str]
    failures: dict[str, str]
    usage: Usage = Usage()


class Generated(BaseModel):
    data: dict[str, JsonValue]
    usage: Usage


class SearchProvider(Protocol):
    async def search(self, query: str, max_results: int = 8) -> SearchResult: ...


class ContentProvider(Protocol):
    async def extract(self, urls: list[str]) -> ContentResult: ...


class LLMProvider(Protocol):
    async def generate_json(
        self,
        task: str,
        schema: dict[str, JsonValue],
        inputs: dict[str, JsonValue],
        max_tokens: int = 4096,
    ) -> Generated: ...
