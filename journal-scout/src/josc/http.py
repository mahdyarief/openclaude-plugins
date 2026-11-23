import asyncio
import json
import time
from typing import Any, Dict, Optional, Tuple

import httpx

from .cache import TTLCache
from .models import ProviderError

MAX_BACKOFF_SECONDS = 60
MIN_INTERVALS: Dict[str, float] = {
    "arxiv": 3.0,
    # OpenCitations allows 180 requests/minute per IP.
    "opencitations": 0.34,
}
MAX_RETRIES = 3

# Sentinel distinguishing "caller said nothing" (use the default cache) from an
# explicit ``cache=None`` (caching deliberately disabled, e.g. a TTL of zero).
_CACHE_UNSET: Any = object()


class Fetcher:
    def __init__(
        self,
        client: Optional[httpx.AsyncClient] = None,
        cache: Optional[TTLCache] = _CACHE_UNSET,
    ):
        self.client = client or httpx.AsyncClient(timeout=30.0)
        # A single cache is shared by every provider, so a repeated query
        # against any source is served locally instead of burning the upstream
        # quota. ``cache=None`` turns caching off entirely.
        self.cache = TTLCache() if cache is _CACHE_UNSET else cache
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

    def _cache_key(self, url, params, provider) -> Optional[Tuple]:
        if self.cache is None:
            return None
        items = tuple(sorted((params or {}).items()))
        return (provider, url, items)

    async def _request(self, url, params, headers, provider, follow_redirects=False):
        backoff = 1.0
        retries = MAX_RETRIES
        last_exc: Optional[Exception] = None
        last_status: Optional[int] = None
        last_body = ""
        while retries > 0:
            await self._throttle(provider)
            try:
                extra = {"follow_redirects": True} if follow_redirects else {}
                response = await self.client.get(
                    url, params=params, headers=headers, **extra
                )
            except httpx.HTTPError as e:
                last_exc = e
                retries -= 1
                await asyncio.sleep(min(backoff, MAX_BACKOFF_SECONDS))
                backoff *= 2
                continue

            last_status = response.status_code
            last_body = response.text[:200]
            # arXiv signals its per-IP rate limit with 406 rather than 429;
            # retrying matters because _throttle() re-applies the provider
            # interval before the next attempt.
            if last_status in (406, 429):
                els_status = response.headers.get("X-ELS-Status", "")
                if "QUOTA_EXCEEDED" in els_status:
                    raise ProviderError(
                        provider or "unknown",
                        "Elsevier weekly quota exceeded (QUOTA_EXCEEDED). "
                        "Wait for the weekly reset or raise the quota.",
                    )
                retries -= 1
                if retries <= 0:
                    break
                retry_after = response.headers.get("Retry-After")
                delay = backoff
                if retry_after:
                    try:
                        delay = max(delay, float(retry_after))
                    except ValueError:
                        pass
                await asyncio.sleep(min(delay, MAX_BACKOFF_SECONDS))
                backoff *= 2
                continue
            if last_status == 403:
                if provider == "garuda":
                    retries -= 1
                    if retries <= 0:
                        break
                    await asyncio.sleep(min(backoff, MAX_BACKOFF_SECONDS))
                    backoff *= 2
                    continue
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
            raise ProviderError(
                provider or "unknown", f"Request failed after retries ({last_exc})"
            )
        detail = f": {last_body}" if last_body else ""
        raise ProviderError(
            provider or "unknown",
            f"Request failed after retries (last status={last_status}){detail}",
        )

    @staticmethod
    def _parse_json(response, provider) -> Dict[str, Any]:
        try:
            return response.json()
        except json.JSONDecodeError as e:
            body = response.text[:200]
            if body.lstrip().startswith("<"):
                raise ProviderError(
                    provider or "unknown",
                    f"Expected JSON but got an HTML page (the endpoint may be "
                    f"behind a bot challenge): {body}",
                ) from e
            raise ProviderError(
                provider or "unknown", f"Expected JSON but got: {body}"
            ) from e

    async def get_json(
        self, url, params=None, headers=None, provider=None
    ) -> Dict[str, Any]:
        key = self._cache_key(url, params, provider)
        if key is not None:
            cached = self.cache.get(key)
            if cached is not None:
                return cached
        response = await self._request(url, params, headers, provider)
        payload = self._parse_json(response, provider)
        if key is not None:
            self.cache.set(key, payload)
        return payload

    async def get_text(self, url, params=None, headers=None, provider=None) -> str:
        key = self._cache_key(url, params, provider)
        if key is not None:
            cached = self.cache.get(key)
            if cached is not None:
                return cached
        response = await self._request(url, params, headers, provider)
        text = response.text
        if key is not None:
            self.cache.set(key, text)
        return text

    async def get_bytes(
        self, url, params=None, headers=None, provider=None, follow_redirects=False
    ) -> bytes:
        key = self._cache_key(url, params, provider)
        if key is not None:
            cached = self.cache.get(key)
            if cached is not None:
                return cached
        response = await self._request(
            url, params, headers, provider, follow_redirects=follow_redirects
        )
        content = response.content
        if key is not None:
            self.cache.set(key, content)
        return content

    async def get_page(
        self, url, params=None, headers=None, provider=None
    ) -> Tuple[str, str]:
        """Follow redirects and return ``(final_url, html)``.

        The final URL matters when the page links resources relatively, e.g. a
        DOI resolved through doi.org to a publisher landing page.
        """
        key = self._cache_key(("page", url), params, provider)
        if key is not None:
            cached = self.cache.get(key)
            if cached is not None:
                return cached
        response = await self._request(
            url, params, headers, provider, follow_redirects=True
        )
        page = (str(response.url), response.text)
        if key is not None:
            self.cache.set(key, page)
        return page

    async def close(self) -> None:
        await self.client.aclose()
