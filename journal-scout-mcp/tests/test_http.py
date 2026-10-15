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


async def test_get_json_non_json_body_raises_provider_error():
    def handler(request):
        return httpx.Response(
            200, headers={"content-type": "text/plain"}, text="not json"
        )

    f = _fetcher(handler)
    try:
        with pytest.raises(ProviderError) as exc:
            await f.get_json("https://example.test/x", provider="crossref")
        assert exc.value.provider == "crossref"
        assert "not json" in str(exc.value)
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


async def test_retries_406_then_succeeds():
    # arXiv signals its rate limit with 406, so it must be retried like 429.
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(406)
        return httpx.Response(200, json={"ok": True})

    f = _fetcher(handler)
    try:
        assert await f.get_json("https://export.arxiv.org/api/query", provider="crossref") == {"ok": True}
        assert calls["n"] == 2
    finally:
        await f.close()


async def test_persistent_406_raises_provider_error():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(406)

    f = _fetcher(handler)
    try:
        with pytest.raises(ProviderError) as exc:
            await f.get_json("https://export.arxiv.org/api/query", provider="crossref")
        assert exc.value.provider == "crossref"
        assert calls["n"] == 3
    finally:
        await f.close()


async def test_get_json_html_body_reports_bot_challenge():
    def handler(request):
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<!doctype html><html><title>Making sure you're not a bot!</title>",
        )

    f = _fetcher(handler)
    try:
        with pytest.raises(ProviderError) as exc:
            await f.get_json("https://dblp.org/search/publ/api", provider="dblp")
        assert "HTML" in str(exc.value)
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


async def test_repeated_query_is_served_from_cache_without_second_call():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json={"ok": True})

    f = _fetcher(handler)
    try:
        first = await f.get_json("https://example.test/x", params={"q": "a"}, provider="crossref")
        second = await f.get_json("https://example.test/x", params={"q": "a"}, provider="crossref")
        assert first == second == {"ok": True}
        # The upstream must be hit exactly once thanks to the cache.
        assert calls["n"] == 1
    finally:
        await f.close()


async def test_cache_is_keyed_by_params_and_provider():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json={"n": calls["n"]})

    f = _fetcher(handler)
    try:
        await f.get_json("https://example.test/x", params={"q": "a"}, provider="crossref")
        # Different params and a different provider are distinct cache keys.
        await f.get_json("https://example.test/x", params={"q": "b"}, provider="crossref")
        await f.get_json("https://example.test/x", params={"q": "a"}, provider="openalex")
        assert calls["n"] == 3
    finally:
        await f.close()


async def test_cache_disabled_when_none_still_works():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    f = Fetcher(client=client, cache=None)
    try:
        await f.get_json("https://example.test/x", provider="crossref")
        await f.get_json("https://example.test/x", provider="crossref")
        assert calls["n"] == 2
    finally:
        await f.close()