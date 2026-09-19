import json
from pathlib import Path

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
