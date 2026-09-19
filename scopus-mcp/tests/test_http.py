import httpx
import pytest

from journal_scout_mcp.http import Fetcher
from journal_scout_mcp.models import ProviderError


def _fetcher(handler):
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return Fetcher(client=client)


async def test_get_json_returns_payload():
    def handler(request):
        return httpx.Response(200, json={"ok": True})

    f = _fetcher(handler)
    try:
        assert await f.get_json("https://example.test/x", provider="crossref") == {"ok": True}
    finally:
        await f.close()


async def test_retries_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500, text="boom")
        return httpx.Response(200, json={"ok": True})

    f = _fetcher(handler)
    try:
        assert await f.get_json("https://example.test/x", provider="dblp") == {"ok": True}
        assert calls["n"] == 2
    finally:
        await f.close()


async def test_permanent_500_raises_provider_error():
    def handler(request):
        return httpx.Response(500, text="boom")

    f = _fetcher(handler)
    try:
        with pytest.raises(ProviderError) as exc:
            await f.get_json("https://example.test/x", provider="dblp")
        assert exc.value.provider == "dblp"
    finally:
        await f.close()


async def test_elsevier_entitlement_error_message():
    def handler(request):
        return httpx.Response(
            403, headers={"X-ELS-Status": "ENTITLEMENTS_ERROR"}, text="forbidden"
        )

    f = _fetcher(handler)
    try:
        with pytest.raises(ProviderError) as exc:
            await f.get_json("https://api.elsevier.com/x", provider="scopus")
        assert "ENTITLEMENTS_ERROR" in str(exc.value)
    finally:
        await f.close()


async def test_elsevier_quota_error_message():
    def handler(request):
        return httpx.Response(
            429, headers={"X-ELS-Status": "QUOTA_EXCEEDED"}, text="slow down"
        )

    f = _fetcher(handler)
    try:
        with pytest.raises(ProviderError) as exc:
            await f.get_json("https://api.elsevier.com/x", provider="scopus")
        assert "quota" in str(exc.value).lower()
    finally:
        await f.close()