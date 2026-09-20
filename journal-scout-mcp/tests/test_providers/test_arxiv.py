from pathlib import Path

import httpx

from journal_scout_mcp.providers.arxiv import ArxivProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"
ATOM = "{http://www.w3.org/2005/Atom}"


async def test_search_parses_atom_entry():
    xml = (FIXTURES / "arxiv_search.xml").read_text(encoding="utf-8")

    def handler(request):
        return httpx.Response(200, text=xml)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ArxivProvider(client)
    try:
        papers = await provider.search("attention is all you need", 5)
        assert len(papers) == 1
        p = papers[0]
        assert p.title == "Attention Is All You Need"
        assert p.authors == ["Ashish Vaswani", "Noam Shazeer"]
        assert p.year == 2017
        assert p.abstract.startswith("The dominant sequence transduction")
        assert p.pdf_url == "http://arxiv.org/pdf/1706.03762v5"
        assert p.sources == ["arxiv"]
        assert p.ids["arxiv"] == "1706.03762v5"
    finally:
        await client.aclose()


async def test_search_sends_sortby_submitteddate():
    captured = {}

    def handler(request):
        captured["sortBy"] = request.url.params.get("sortBy")
        return httpx.Response(200, text=(FIXTURES / "arxiv_search.xml").read_text(encoding="utf-8"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ArxivProvider(client)
    try:
        await provider.search("attention is all you need", 5)
        assert captured["sortBy"] == "submittedDate"
    finally:
        await client.aclose()


async def test_tech_only_adds_cs_categories_to_query():
    captured = {}

    def handler(request):
        captured["query"] = request.url.params.get("search_query")
        return httpx.Response(200, text=(FIXTURES / "arxiv_search.xml").read_text(encoding="utf-8"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ArxivProvider(client)
    try:
        await provider.search("transformers", 5, tech_only=True)
        assert "cat:cs." in captured["query"]
    finally:
        await client.aclose()
