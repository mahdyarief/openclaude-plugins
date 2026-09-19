import json
from pathlib import Path

import httpx

from journal_scout_mcp.providers.semanticscholar import SemanticScholarProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"


async def test_search_maps_data_to_paper():
    payload = json.loads((FIXTURES / "semanticscholar_search.json").read_text(encoding="utf-8"))

    def handler(request):
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SemanticScholarProvider(client)
    try:
        papers = await provider.search("attention", 5)
        assert len(papers) == 1
        p = papers[0]
        assert p.doi == "10.5555/3295222.3295349"
        assert p.title == "Attention Is All You Need"
        assert p.year == 2017
        assert p.citation_count == 90000
        assert p.authors == ["Ashish Vaswani", "Noam Shazeer"]
        assert p.pdf_url == "https://example.org/attn.pdf"
        assert p.sources == ["semanticscholar"]
        assert p.ids["semanticscholar"] == "abc123"
        assert p.ids["arxiv"] == "1706.03762"
    finally:
        await client.aclose()


async def test_api_key_header_sent_when_configured(monkeypatch):
    captured = {}

    def handler(request):
        captured["key"] = request.headers.get("x-api-key")
        return httpx.Response(200, json={"data": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SemanticScholarProvider(client)
    monkeypatch.setattr(
        "journal_scout_mcp.providers.semanticscholar.get_semantic_scholar_key",
        lambda: "secret-key",
    )
    try:
        await provider.search("anything", 1)
        assert captured["key"] == "secret-key"
    finally:
        await client.aclose()
