import json
from pathlib import Path
from urllib.parse import unquote

import httpx

from journal_scout_mcp.providers.scopus import ScopusProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"


async def test_search_maps_entries_to_paper(monkeypatch):
    payload = json.loads((FIXTURES / "scopus_search.json").read_text(encoding="utf-8"))

    def handler(request):
        assert "X-ELS-APIKey" in request.headers
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        papers = await provider.search("intrusion detection", 5)
        assert len(papers) == 1
        p = papers[0]
        assert p.doi == "10.1109/access.2023.1234567"
        assert p.title == "Deep Learning for Network Intrusion Detection"
        assert p.year == 2023
        assert p.citation_count == 42
        assert p.venue == "IEEE Access"
        assert p.sources == ["scopus"]
        assert p.ids["scopus"] == "SCOPUS_ID:85012345678"
    finally:
        await client.aclose()


async def test_tech_only_adds_subjarea():
    captured = {}

    def handler(request):
        captured["query"] = request.url.params.get("query")
        return httpx.Response(200, json={"search-results": {"entry": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        await provider.search("networks", 5, tech_only=True)
        assert "SUBJAREA(COMP)" in captured["query"]
    finally:
        await client.aclose()


def test_scopus_provider_has_detail_helpers():
    from journal_scout_mcp.providers.scopus import ScopusProvider
    assert hasattr(ScopusProvider, "get_author")
    assert hasattr(ScopusProvider, "get_quota_status")


async def test_get_routes_doi_to_doi_endpoint():
    captured = {}

    def handler(request):
        captured["path"] = unquote(request.url.path)
        return httpx.Response(
            200,
            json={
                "abstracts-retrieval-response": {
                    "coredata": {"dc:title": "X", "prism:doi": "10.1/x"}
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        paper = await provider.get("10.1145/3292500.3330701")
        assert "/abstract/doi/" in captured["path"]
        assert "3292500.3330701" in captured["path"]
        assert paper is not None
    finally:
        await client.aclose()


async def test_get_routes_scopus_id_to_scopus_id_endpoint():
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        return httpx.Response(200, json={"abstracts-retrieval-response": {"coredata": {}}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        await provider.get("SCOPUS_ID:85012345678")
        assert captured["path"].endswith("/abstract/scopus_id/85012345678")
    finally:
        await client.aclose()


async def test_get_returns_none_for_unsupported_identifier():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        assert await provider.get("2301.12345") is None
        assert calls == []
    finally:
        await client.aclose()


async def test_citations_returns_empty_for_doi_without_request():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json={"search-results": {"entry": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        assert await provider.citations("10.1145/3292500.3330701", 5) == []
        assert calls == []
    finally:
        await client.aclose()


async def test_citations_uses_scopus_id_for_ref_query():
    captured = {}

    def handler(request):
        captured["query"] = request.url.params.get("query")
        return httpx.Response(200, json={"search-results": {"entry": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        await provider.citations("SCOPUS_ID:85012345678", 5)
        assert captured["query"] == "REF(85012345678)"
    finally:
        await client.aclose()
