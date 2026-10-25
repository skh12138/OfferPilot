import asyncio
import random

import httpx
from offerpilot.providers.base import ProviderError
from pydantic import JsonValue


async def post(
    client: httpx.AsyncClient, url: str, key: str, payload: dict[str, JsonValue]
) -> httpx.Response:
    if not key:
        raise ProviderError("provider_not_configured")
    # Per-attempt reservations are performed by the workflow caller, not a hidden retry here.
    try:
        response = await client.post(
            url, headers={"Authorization": f"Bearer {key}"}, json=payload, timeout=60
        )
    except httpx.TimeoutException as exc:
        raise ProviderError("provider_timeout", True) from exc
    except httpx.TransportError as exc:
        raise ProviderError("provider_network", True) from exc
    if response.status_code == 429 or response.status_code >= 500:
        raise ProviderError(f"provider_http_{response.status_code}", True)
    if response.status_code >= 400:
        raise ProviderError(f"provider_http_{response.status_code}")
    return response


async def backoff(attempt: int) -> None:
    await asyncio.sleep(min(2**attempt, 4) + random.uniform(0, 0.3))
