import httpx
import pytest

from journal_scout_mcp.config import get_polite_email


@pytest.fixture
def polite_email():
    return "test@example.com"


class FakeFetcher:
    """Routes every GET to a handler that returns a canned httpx.Response."""

    def __init__(self, handler):
        self._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def _get(self, url, params=None, headers=None):
        return await self._client.get(url, params=params, headers=headers)

    async def get_json(self, url, params=None, headers=None, provider=None):
        r = await self._get(url, params, headers)
        return r.json()

    async def get_text(self, url, params=None, headers=None, provider=None):
        r = await self._get(url, params, headers)
        return r.text

    async def close(self):
        await self._client.aclose()


@pytest.fixture
def make_fetcher():
    def _make(handler):
        return FakeFetcher(handler)

    return _make