import json
from pathlib import Path

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