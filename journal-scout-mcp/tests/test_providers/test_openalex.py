import json
from pathlib import Path
from urllib.parse import unquote

import httpx

from journal_scout_mcp.providers.openalex import OpenAlexProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"


async def test_search_reconstructs_abstract_and_maps_fields():
    payload = json.loads((FIXTURES / "openalex_search.json").read_text(encoding="utf-8"))

    def handler(request):
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAlexProvider(client)
    try:
        papers = await provider.search("long short-term memory", 5)
        assert len(papers) == 1
        p = papers[0]
        assert p.doi == "10.1162/neco.1997.9.8.1735"
        assert p.title == "Long Short-Term Memory"
        assert p.year == 1997
        assert p.citation_count == 42000
        assert p.authors == ["Sepp Hochreiter", "Jürgen Schmidhuber"]
        assert p.venue == "Neural Computation"
        assert p.abstract == "We propose LSTM"
        assert p.is_open_access is True
        assert p.pdf_url == "https://example.org/lstm.pdf"
        assert p.sources == ["openalex"]
        assert p.ids["openalex"] == "https://openalex.org/W2963403868"
    finally:
        await client.aclose()


async def test_get_normalizes_doi_url_to_same_request_as_bare_doi():
    captured = []

    def handler(request):
        captured.append(request.url.path)
        return httpx.Response(200, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAlexProvider(client)
    try:
        await provider.get("10.1/x")
        await provider.get("https://doi.org/10.1/x")
        assert len(captured) == 2
        bare, url_form = captured
        assert url_form == bare
        assert "doi:10.1/x" in unquote(bare)
    finally:
        await client.aclose()


async def test_citations_normalizes_doi_url_to_same_request_as_bare_doi():
    captured = []

    def handler(request):
        captured.append(dict(request.url.params))
        return httpx.Response(200, json={"results": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAlexProvider(client)
    try:
        await provider.citations("10.1/x", 3)
        await provider.citations("https://doi.org/10.1/x", 3)
        assert len(captured) == 2
        bare, url_form = captured
        assert url_form["filter"] == bare["filter"]
        assert bare["filter"] == "cites:doi:10.1/x"
    finally:
        await client.aclose()