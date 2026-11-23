import httpx
import pytest

from josc.providers import openalex as openalex_module
from josc.providers.openalex import OpenAlexProvider


def _provider(handler):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OpenAlexProvider(client), client


async def test_search_sends_api_key_from_config(monkeypatch):
    seen = {}

    def handler(request):
        seen["api_key"] = request.url.params.get("api_key")
        return httpx.Response(200, json={"results": []})

    monkeypatch.setattr(openalex_module, "get_openalex_api_key", lambda: "secret-key")
    provider, client = _provider(handler)
    try:
        await provider.search("ai", 1)
        assert seen["api_key"] == "secret-key"
    finally:
        await client.aclose()


async def test_requests_omit_api_key_when_unset(monkeypatch):
    seen = {}

    def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"results": []})

    monkeypatch.setattr(openalex_module, "get_openalex_api_key", lambda: None)
    provider, client = _provider(handler)
    try:
        await provider.search("ai", 1)
        assert "api_key" not in seen["params"]
    finally:
        await client.aclose()


async def test_get_and_taxonomy_requests_carry_api_key(monkeypatch):
    paths = []

    def handler(request):
        paths.append((request.url.path, request.url.params.get("api_key")))
        if request.url.path == "/topics":
            return httpx.Response(
                200, json={"results": [{"display_name": "Machine Learning"}]}
            )
        return httpx.Response(200, json={"id": "https://openalex.org/W1"})

    monkeypatch.setattr(openalex_module, "get_openalex_api_key", lambda: "k")
    provider, client = _provider(handler)
    try:
        await provider.get("W1")
        await provider.classify_topics("ai")
        assert paths == [("/works/W1", "k"), ("/topics", "k")]
    finally:
        await client.aclose()


async def test_works_fallback_carries_api_key(monkeypatch):
    seen = []

    def handler(request):
        seen.append((request.url.path, request.url.params.get("api_key")))
        if request.url.path == "/topics":
            return httpx.Response(200, json={"results": []})
        return httpx.Response(200, json={"results": []})

    monkeypatch.setattr(openalex_module, "get_openalex_api_key", lambda: "k")
    provider, client = _provider(handler)
    try:
        assert await provider.classify_topics("long free-form research question") == []
        assert seen == [("/topics", "k"), ("/works", "k")]
    finally:
        await client.aclose()


async def test_search_raises_when_openalex_pauses_search(monkeypatch):
    def handler(request):
        return httpx.Response(
            503,
            json={
                "error": "Search is temporarily paused",
                "message": "Try again later.",
            },
        )

    monkeypatch.setattr(openalex_module, "get_openalex_api_key", lambda: None)
    provider, client = _provider(handler)
    try:
        with pytest.raises(Exception) as excinfo:
            await provider.search("ai", 1)
        assert "paused" in str(excinfo.value).lower()
    finally:
        await client.aclose()
