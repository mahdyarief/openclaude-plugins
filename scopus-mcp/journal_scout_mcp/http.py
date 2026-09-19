import asyncio
import time
from typing import Any, Dict, Optional

import httpx

from .models import ProviderError

MAX_BACKOFF_SECONDS = 60
MIN_INTERVALS: Dict[str, float] = {"arxiv": 3.0, "semanticscholar": 1.0}
MAX_RETRIES = 3


class Fetcher:
    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.client = client or httpx.AsyncClient(timeout=30.0)
        self._last_call: Dict[str, float] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def _lock(self, provider: str) -> asyncio.Lock:
        if provider not in self._locks:
            self._locks[provider] = asyncio.Lock()
        return self._locks[provider]

    async def _throttle(self, provider: Optional[str]) -> None:
        if not provider:
            return
        interval = MIN_INTERVALS.get(provider, 0.0)
        if interval <= 0:
            return
        async with self._lock(provider):
            elapsed = time.monotonic() - self._last_call.get(provider, 0.0)
            wait = interval - elapsed
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call[provider] = time.monotonic()

    async def _request(self, url, params, headers, provider):
        backoff = 1.0
        retries = MAX_RETRIES
        last_exc: Optional[Exception] = None
        last_status: Optional[int] = None
        while retries > 0:
            await self._throttle(provider)
            try:
                response = await self.client.get(url, params=params, headers=headers)
            except httpx.HTTPError as e:
                last_exc = e
                retries -= 1
                await asyncio.sleep(min(backoff, MAX_BACKOFF_SECONDS))
                backoff *= 2
                continue

            last_status = response.status_code
            if last_status == 429:
                retries -= 1
                if retries <= 0:
                    break
                els_status = response.headers.get("X-ELS-Status", "")
                if "QUOTA_EXCEEDED" in els_status:
                    raise ProviderError(
                        provider or "unknown",
                        "Elsevier weekly quota exceeded (QUOTA_EXCEEDED). "
                        "Wait for the weekly reset or raise the quota.",
                    )
                await asyncio.sleep(min(backoff, MAX_BACKOFF_SECONDS))
                backoff *= 2
                continue
            if last_status == 403:
                els_status = response.headers.get("X-ELS-Status", "") or ""
                if "ENTITLEMENTS_ERROR" in els_status:
                    raise ProviderError(
                        provider or "unknown",
                        "Elsevier returned ENTITLEMENTS_ERROR: the API key is "
                        "valid, but this institution is not entitled to the "
                        "requested resource. SciVal endpoints need a SciVal "
                        "subscription; Scopus-only tools keep working.",
                    )
                raise ProviderError(
                    provider or "unknown",
                    f"Access forbidden (403). X-ELS-Status: {els_status or 'unknown'}",
                )
            if last_status >= 500:
                retries -= 1
                if retries <= 0:
                    break
                await asyncio.sleep(min(backoff, MAX_BACKOFF_SECONDS))
                backoff *= 2
                continue
            if last_status >= 400:
                raise ProviderError(
                    provider or "unknown", f"HTTP {last_status}: {response.text[:200]}"
                )
            return response

        if last_exc:
            raise ProviderError(provider or "unknown", f"Request failed after retries ({last_exc})")
        raise ProviderError(
            provider or "unknown", f"Request failed after retries (last status={last_status})"
        )

    async def get_json(self, url, params=None, headers=None, provider=None) -> Dict[str, Any]:
        response = await self._request(url, params, headers, provider)
        return response.json()

    async def get_text(self, url, params=None, headers=None, provider=None) -> str:
        response = await self._request(url, params, headers, provider)
        return response.text

    async def close(self) -> None:
        await self.client.aclose()