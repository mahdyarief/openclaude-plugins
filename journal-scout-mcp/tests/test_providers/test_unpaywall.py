import json
from pathlib import Path

import httpx

from journal_scout_mcp.providers.unpaywall import UnpaywallProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"


async def test_get_maps_open_access_location():
    payload = json.loads((FIXTURES / "unpaywall_lookup.json").read_text(encoding="utf-8"))

    def handler(request):
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = UnpaywallProvider(client)
    try:
        p = await provider.get("10.1162/neco.1997.9.8.1735")
        assert p.is_open_access is True
        assert p.pdf_url == "https://example.org/lstm.pdf"
        assert p.url == "https://example.org/lstm"
        assert p.venue == "Neural Computation"
        assert p.year == 1997
        assert p.sources == ["unpaywall"]
    finally:
        await client.aclose()


async def test_get_empty_doi_returns_none():
    provider = UnpaywallProvider(None)
    assert await provider.get("") is None