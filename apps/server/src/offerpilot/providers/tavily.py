import httpx
from offerpilot.providers.base import ContentResult, ProviderError, SearchHit, SearchResult, Usage
from offerpilot.providers.http import post
from pydantic import BaseModel, ConfigDict, ValidationError


class SearchWire(BaseModel):
    model_config = ConfigDict(extra="ignore")
    results: list[SearchHit]
    usage: dict[str, float] | None = None


class Extracted(BaseModel):
    model_config = ConfigDict(extra="ignore")
    url: str
    raw_content: str


class Failed(BaseModel):
    model_config = ConfigDict(extra="ignore")
    url: str
    error: str


class ExtractWire(BaseModel):
    model_config = ConfigDict(extra="ignore")
    results: list[Extracted]
    failed_results: list[Failed] = []
    usage: dict[str, float] | None = None


class TavilySearchProvider:
    def __init__(self, client: httpx.AsyncClient, key: str, *, detailed: bool = False) -> None:
        self.client, self.key = client, key
        self.detailed = detailed

    async def search(self, query: str, max_results: int = 8) -> SearchResult:
        response = await post(
            self.client,
            "https://api.tavily.com/search",
            self.key,
            {
                "query": query,
                "max_results": min(max_results, 8),
                "search_depth": "advanced" if self.detailed else "basic",
                "chunks_per_source": 3,
                "language": "zh",
                "include_answer": False,
                "include_images": False,
                "include_raw_content": False,
                "include_usage": True,
            },
        )
        try:
            data = SearchWire.model_validate_json(response.content)
        except ValidationError as exc:
            raise ProviderError("provider_schema") from exc
        return SearchResult(
            results=data.results, usage=Usage(credits=(data.usage or {}).get("credits"))
        )


class TavilyContentProvider:
    def __init__(self, client: httpx.AsyncClient, key: str) -> None:
        self.client, self.key = client, key

    async def extract(self, urls: list[str]) -> ContentResult:
        if len(urls) > 20:
            raise ProviderError("extract_limit")
        response = await post(
            self.client,
            "https://api.tavily.com/extract",
            self.key,
            {
                "urls": list(urls),
                "extract_depth": "basic",
                "include_images": False,
                "format": "text",
                "include_usage": True,
            },
        )
        try:
            data = ExtractWire.model_validate_json(response.content)
        except ValidationError as exc:
            raise ProviderError("provider_schema") from exc
        # A missing URL is a failure even when the vendor returns HTTP 200.
        texts = {
            r.url: r.raw_content for r in data.results if r.raw_content.strip() and r.url in urls
        }
        failures = {r.url: "content_unavailable" for r in data.failed_results if r.url in urls}
        for url in urls:
            if url not in texts:
                failures[url] = "content_unavailable"
        return ContentResult(
            texts=texts, failures=failures, usage=Usage(credits=(data.usage or {}).get("credits"))
        )
