import httpx
import pytest

from josc.http import Fetcher
from josc.models import ProviderError


def _fetcher(handler):
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return Fetcher(client=client)


async def test_get_bytes_returns_raw_body_and_caches_it():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, content=b"%PDF-1.4 fake")

    f = _fetcher(handler)
    try:
        first = await f.get_bytes("https://example.test/paper.pdf", provider="fulltext")
        second = await f.get_bytes("https://example.test/paper.pdf", provider="fulltext")
        assert first == second == b"%PDF-1.4 fake"
        assert calls["n"] == 1
    finally:
        await f.close()


async def test_get_json_returns_payload():
    def handler(request):
        return httpx.Response(200, json={"ok": True})

    f = _fetcher(handler)
    try:
        assert await f.get_json("https://example.test/x", provider="crossref") == {
            "ok": True
        }
    finally:
        await f.close()


async def test_get_json_html_202_reports_bot_challenge():
    def handler(request):
        return httpx.Response(
            202,
            headers={"content-type": "text/html"},
            text="<!doctype html><html><title>Making sure you&#39;re not a bot!</title>",
        )

    f = _fetcher(handler)
    try:
        with pytest.raises(ProviderError) as exc:
            await f.get_json("https://example.test/search", provider="example")
        assert "bot challenge" in str(exc.value)
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
        assert await f.get_json("https://example.test/x", provider="crossref") == {
            "ok": True
        }
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
        assert await f.get_json(
            "https://export.arxiv.org/api/query", provider="crossref"
        ) == {"ok": True}
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


async def test_retry_after_header_is_honoured(monkeypatch):
    calls = {"n": 0}
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr("josc.http.asyncio.sleep", fake_sleep)

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "7"})
        return httpx.Response(200, json={"ok": True})

    f = _fetcher(handler)
    try:
        assert await f.get_json("https://example.test/x", provider="unpaywall") == {
            "ok": True
        }
        assert sleeps == [7.0]
    finally:
        await f.close()


async def test_garuda_403_retries_as_transient(monkeypatch):
    calls = {"n": 0}
    delays = []

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(403, text="temporary gateway block")
        return httpx.Response(200, json={"ok": True})

    async def no_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("josc.http.asyncio.sleep", no_sleep)
    f = _fetcher(handler)
    try:
        assert await f.get_json("https://example.test/search", provider="garuda") == {
            "ok": True
        }
        assert calls["n"] == 2
        assert delays == [1.0]
    finally:
        await f.close()


async def test_other_provider_403_is_not_retried(monkeypatch):
    calls = {"n": 0}
    delays = []

    def handler(request):
        calls["n"] += 1
        return httpx.Response(403, text="forbidden")

    async def no_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("josc.http.asyncio.sleep", no_sleep)
    f = _fetcher(handler)
    try:
        with pytest.raises(ProviderError, match="Access forbidden"):
            await f.get_json("https://example.test/search", provider="scopus")
        assert calls["n"] == 1
        assert delays == []
    finally:
        await f.close()


async def test_permanent_500_raises_provider_error():
    def handler(request):
        return httpx.Response(500, text="boom")

    f = _fetcher(handler)
    try:
        with pytest.raises(ProviderError) as exc:
            await f.get_json("https://example.test/x", provider="example")
        assert exc.value.provider == "example"
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


async def test_exhausted_429_keeps_the_upstream_reason():
    def handler(request):
        return httpx.Response(
            429,
            json={"detail": "You've used 100% of your free usage this month"},
        )

    f = _fetcher(handler)
    try:
        with pytest.raises(ProviderError) as exc:
            await f.get_json(
                "https://api.consensus.app/v1/search", provider="consensus"
            )
        message = str(exc.value)
        assert "429" in message
        assert "100% of your free usage" in message
    finally:
        await f.close()


async def test_repeated_query_is_served_from_cache_without_second_call():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json={"ok": True})

    f = _fetcher(handler)
    try:
        first = await f.get_json(
            "https://example.test/x", params={"q": "a"}, provider="crossref"
        )
        second = await f.get_json(
            "https://example.test/x", params={"q": "a"}, provider="crossref"
        )
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
        await f.get_json(
            "https://example.test/x", params={"q": "a"}, provider="crossref"
        )
        # Different params and a different provider are distinct cache keys.
        await f.get_json(
            "https://example.test/x", params={"q": "b"}, provider="crossref"
        )
        await f.get_json(
            "https://example.test/x", params={"q": "a"}, provider="openalex"
        )
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
