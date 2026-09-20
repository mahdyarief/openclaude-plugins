import json
from pathlib import Path

import httpx

from journal_scout_mcp.providers.dblp import DblpProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"


async def test_search_maps_hits_to_paper():
    payload = json.loads((FIXTURES / "dblp_search.json").read_text(encoding="utf-8"))

    def handler(request):
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = DblpProvider(client)
    try:
        papers = await provider.search("attention is all you need", 5)
        assert len(papers) == 1
        p = papers[0]
        assert p.doi == "10.5555/3295222.3295349"
        assert p.title == "Attention is All you Need"
        assert p.authors == ["Ashish Vaswani", "Noam Shazeer"]
        assert p.venue == "NIPS"
        assert p.year == 2017
        assert p.sources == ["dblp"]
        assert p.ids["dblp"] == "10.5555/3295222.3295349"
    finally:
        await client.aclose()


async def test_search_filters_by_year_range():
    payload = json.loads((FIXTURES / "dblp_search.json").read_text(encoding="utf-8"))

    def handler(request):
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = DblpProvider(client)
    try:
        # The fixture hit is dated 2017.
        assert len(await provider.search("q", 5, year_from=2010, year_to=2020)) == 1
        assert len(await provider.search("q", 5, year_from=2018)) == 0
        assert len(await provider.search("q", 5, year_to=2010)) == 0
    finally:
        await client.aclose()