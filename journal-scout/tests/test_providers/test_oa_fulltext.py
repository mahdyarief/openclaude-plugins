import json
from pathlib import Path

import httpx

from josc.aggregator import _enrich
from josc.models import Paper
from josc.providers.unpaywall import UnpaywallProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"


async def test_unpaywall_enricher_sets_pdf_url():
    payload = json.loads((FIXTURES / "unpaywall_lookup.json").read_text(encoding="utf-8"))

    def handler(request):
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = UnpaywallProvider(client)
    try:
        paper = Paper(doi="10.1162/neco.1997.9.8.1735", sources=["crossref"])
        result = await _enrich([provider], paper)
        assert result.pdf_url == "https://example.org/lstm.pdf"
        assert result.is_open_access is True
        assert "unpaywall" in result.sources
    finally:
        await client.aclose()
