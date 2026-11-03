import json
from pathlib import Path

import httpx
import pytest

from josc.config import get_consensus_key
from josc.providers.consensus import ConsensusProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _sample_item(overrides=None):
    item = {
        "title": "The effects of creatine supplementation on cognitive function",
        "abstract": "Background: a systematic review with meta-analysis.",
        "authors": ["Chen Xu", "Si-Yuan Bi"],
        "doi": "10.3389/fnut.2024.1424972",
        "journal_name": "Frontiers in Nutrition",
        "volume": "11",
        "publish_year": 2024,
        "url": "https://consensus.app/papers/xu-bi/54813b2512da51388b5b582d3efdfa9d/",
        "citation_count": 57,
        "study_type": "meta-analysis",
        "takeaway": "Creatine monohydrate supplementation may improve memory.",
        "sjr_best_quartile": 1,
        "study_count": 16,
        "is_preprint": False,
        "institutions": ["Guizhou Normal University"],
        "publish_date": "2024-07-12",
    }
    if overrides:
        item.update(overrides)
    return item


async def test_search_maps_item_to_paper(monkeypatch):
    monkeypatch.setenv("CONSENSUS_API_KEY", "test-key")
    payload = {"results": [_sample_item()], "page": 0, "page_size": 1, "is_end": True}
    captured = {}

    def handler(request):
        captured["params"] = dict(request.url.params)
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ConsensusProvider(client)
    try:
        papers = await provider.search("creatine cognition", 5)
        assert len(papers) == 1
        p = papers[0]
        assert p.doi == "10.3389/fnut.2024.1424972"
        assert p.title == "The effects of creatine supplementation on cognitive function"
        assert p.authors == ["Chen Xu", "Si-Yuan Bi"]
        assert p.venue == "Frontiers in Nutrition"
        assert p.year == 2024
        assert p.citation_count == 57
        assert p.type == "meta-analysis"
        assert p.study_type == "meta-analysis"
        assert p.takeaway == "Creatine monohydrate supplementation may improve memory."
        assert p.study_count == 16
        assert p.sjr_best_quartile == 1
        assert p.is_preprint is False
        assert p.is_open_access is None
        assert p.sources == ["consensus"]
        assert p.ids["consensus"] == "10.3389/fnut.2024.1424972"
        assert "Guizhou Normal University" in p.institutions
    finally:
        await client.aclose()


async def test_search_sends_api_key_and_params(monkeypatch):
    monkeypatch.setenv("CONSENSUS_API_KEY", "test-key")
    captured = {}

    def handler(request):
        captured["params"] = dict(request.url.params)
        captured["key"] = request.headers.get("x-api-key")
        return httpx.Response(200, json={"results": [], "page": 0, "page_size": 10, "is_end": True})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ConsensusProvider(client)
    try:
        await provider.search("graph neural networks", 12, year_from=2020, year_to=2024)
        assert captured["key"] == get_consensus_key()
        assert captured["params"]["query"] == "graph neural networks"
        assert int(captured["params"]["page_size"]) == 12
        assert int(captured["params"]["year_min"]) == 2020
        assert int(captured["params"]["year_max"]) == 2024
    finally:
        await client.aclose()


async def test_search_paginates_until_end(monkeypatch):
    monkeypatch.setenv("CONSENSUS_API_KEY", "test-key")
    pages = [
        {"results": [_sample_item({"doi": f"10.1/{i}"}) for i in range(5)], "page": 0, "page_size": 5, "is_end": False},
        {"results": [_sample_item({"doi": "10.1/9"})], "page": 1, "page_size": 5, "is_end": True},
    ]
    state = {"n": 0}

    def handler(request):
        page = int(request.url.params.get("page", 0))
        state["n"] += 1
        return httpx.Response(200, json=pages[min(page, 1)])

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ConsensusProvider(client)
    try:
        papers = await provider.search("x", 20)
        assert len(papers) == 6
        assert state["n"] == 2
    finally:
        await client.aclose()


async def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("CONSENSUS_API_KEY", raising=False)
    monkeypatch.setattr("josc.config.load_config_file", lambda: {})
    provider = ConsensusProvider(None)
    with pytest.raises(ValueError):
        provider._headers()
