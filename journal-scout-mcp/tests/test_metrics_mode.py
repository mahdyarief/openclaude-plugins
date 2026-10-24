"""Tests for the metrics ``mode`` parameter (basic vs extended)."""

import pytest

from josc.aggregator import compute_metrics
from josc.graph import compute_metrics as graph_metrics
from josc.models import Paper
from josc.providers.base import ProviderBase

EXTENDED_ONLY = {
    "hc_index",
    "hI_index",
    "hI_norm",
    "AWCR",
    "AW_index",
    "AWCRpA",
    "hm_index",
}


class MetricsProvider(ProviderBase):
    name = "fake"
    supports_search = True

    async def search(self, query, limit, year_from=None, year_to=None, tech_only=False, offset=0):
        return [
            Paper(doi="10.1/a", title="One", year=2021, citation_count=12,
                  authors=["Alice", "Bob"], sources=["fake"]),
            Paper(doi="10.1/b", title="Two", year=2019, citation_count=4,
                  authors=["Bob", "Carol"], sources=["fake"]),
        ]


def test_extended_is_superset_of_basic():
    papers = [
        Paper(doi="10.1/a", title="A", year=2020, citation_count=10,
              authors=["A", "B"], sources=["x"]),
        Paper(doi="10.1/b", title="B", year=2018, citation_count=25,
              authors=["B"], sources=["x"]),
    ]
    basic = graph_metrics(papers, mode="basic")
    extended = graph_metrics(papers, mode="extended")
    assert EXTENDED_ONLY <= set(extended)
    assert not (EXTENDED_ONLY & set(basic))
    assert set(basic) <= set(extended)


def test_bogus_mode_raises():
    with pytest.raises(ValueError, match="mode must be"):
        graph_metrics([], mode="bogus")


async def test_aggregator_forwards_extended_mode():
    result = await compute_metrics([MetricsProvider(None)], query="q", mode="extended")
    assert "hm_index" in result
    assert EXTENDED_ONLY <= set(result)


async def test_aggregator_defaults_to_basic():
    result = await compute_metrics([MetricsProvider(None)], query="q")
    assert "hm_index" not in result


def test_http_metrics_forwards_mode(monkeypatch):
    from starlette.testclient import TestClient

    import josc.api as api

    calls = {}

    async def fake_compute(providers, author=None, query=None, limit_per_source=50,
                           year_from=None, year_to=None, sources=None, mode="basic"):
        calls["mode"] = mode
        return {"papers": 0}

    monkeypatch.setattr(api.aggregator, "compute_metrics", fake_compute)
    monkeypatch.setitem(api._state, "providers", [])
    client = TestClient(api.app)
    response = client.get("/api/metrics", params={"query": "q", "mode": "extended"})
    assert response.status_code == 200
    assert calls["mode"] == "extended"
