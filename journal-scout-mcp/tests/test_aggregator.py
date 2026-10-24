from josc.aggregator import (
    build_citation_network,
    compute_metrics,
    get_citations,
    get_paper,
    get_references,
    search_all,
    search_author,
)
from josc.graph import _node_id, build_network
from josc.models import Paper, ProviderError
from josc.providers.base import ProviderBase


def _paper(doi, title, year=2020, citations=0, **kwargs):
    return Paper(doi=doi, title=title, year=year, citation_count=citations, **kwargs)


class GoodProvider(ProviderBase):
    name = "good"
    supports_search = True

    async def search(self, query, limit, year_from=None, year_to=None, tech_only=False, offset=0):
        return [Paper(doi="10.1/x", title="Shared", citation_count=3, sources=["good"])]


class BadProvider(ProviderBase):
    name = "bad"
    supports_search = True

    async def search(self, query, limit, year_from=None, year_to=None, tech_only=False, offset=0):
        raise ProviderError("bad", "boom")


class GoodCitationProvider(ProviderBase):
    name = "scopus"
    supports_search = False
    supports_citations = True

    async def citations(self, identifier, limit):
        return [Paper(doi="10.2/y", title="Citing", sources=["scopus"])]


class GoodGetProvider(ProviderBase):
    name = "goodget"
    supports_search = False

    async def get(self, identifier):
        return Paper(doi="10.1/x", title="Shared", year=2020, sources=["goodget"])


class SecondGetProvider(ProviderBase):
    name = "goodget2"
    supports_search = False

    async def get(self, identifier):
        return Paper(doi="10.1/x", title="Shared", sources=["goodget2"])


class OutsideCitationProvider(ProviderBase):
    name = "crossref"
    supports_search = False

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.called = False

    async def citations(self, identifier, limit):
        self.called = True
        return [Paper(doi="10.9/z", title="ShouldNotAppear", sources=["crossref"])]


async def test_search_all_merges_and_reports_partial_failure():
    result = await search_all([GoodProvider(None), BadProvider(None)], "q", limit_per_source=5)
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Shared"
    assert result["errors"] == {"bad": "boom"}
    assert "good" in result["counts"]


async def test_search_all_respects_sources_filter():
    result = await search_all(
        [GoodProvider(None), BadProvider(None)], "q", sources=["good"]
    )
    assert result["errors"] == {}
    assert len(result["results"]) == 1


async def test_get_paper_merges_across_providers():
    result = await get_paper([GoodGetProvider(None), SecondGetProvider(None)], "10.1/x")
    assert result["paper"]["doi"] == "10.1/x"
    assert set(result["paper"]["sources"]) == {"goodget", "goodget2"}


async def test_get_citations_collects_from_providers():
    outside = OutsideCitationProvider(None)
    result = await get_citations([GoodCitationProvider(None), outside], "10.1/x", limit=10)
    assert outside.called is False
    assert "crossref" not in result["counts"]
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Citing"


class NetworkProvider(ProviderBase):
    name = "net"
    supports_search = False
    supports_citations = True
    supports_references = True

    async def get(self, identifier):
        return Paper(doi="10.1/seed", title="Seed", year=2020, sources=["net"])

    async def references(self, identifier, limit):
        if identifier == "10.1/seed":
            return [Paper(doi="10.1/shared", title="Shared ref", sources=["net"])]
        return [
            Paper(doi="10.1/shared", title="Shared ref", sources=["net"]),
            Paper(doi="10.1/other", title="Other ref", sources=["net"]),
        ]

    async def citations(self, identifier, limit):
        return [
            Paper(doi="10.1/citing", title="Citing", sources=["net"]),
            Paper(doi="10.1/citing2", title="Citing two", sources=["net"]),
        ]


class MetricsProvider(ProviderBase):
    name = "metrics"
    supports_search = False
    supports_author_search = True

    async def search_author(self, author, limit, year_from=None, year_to=None, offset=0):
        return [
            Paper(doi="10.1/a", title="A", year=2018, citation_count=20, sources=["metrics"]),
            Paper(doi="10.1/b", title="B", year=2019, citation_count=10, sources=["metrics"]),
        ]


async def test_get_references_routes_on_references_capability():
    result = await get_references([NetworkProvider(None), GoodProvider(None)], "10.1/seed", limit=5)
    assert "net" in result["counts"]
    assert "good" not in result["counts"]
    assert result["results"][0]["doi"] == "10.1/shared"


async def test_build_citation_network_produces_edges_and_stats():
    network = await build_citation_network(
        [NetworkProvider(None)], "10.1/seed", limit=5, citing_limit=2
    )

    assert network["seed"] == "doi:10.1/seed"
    assert network["stats"]["nodes"] >= 3
    types = {edge["type"] for edge in network["edges"]}
    assert "cites" in types
    assert "coupled" in types
    # Co-citation needs corroboration from more than one citing paper.
    assert "cocited" in types
    assert network["seed_paper"]["title"] == "Seed"
    assert network["errors"] == {}


def test_build_network_drops_single_witness_cocitation():
    seed = _paper("10.1/seed", "Seed")
    citing = _paper("10.1/citing", "Citing")
    refs = [_paper("10.1/a", "A"), _paper("10.1/b", "B")]

    network = build_network(seed, [], [citing], {"doi:10.1/citing": refs})

    assert network["stats"]["cocited_edges"] == 0


def test_build_network_caps_cocitation_edges():
    seed = _paper("10.1/seed", "Seed")
    citing = [_paper(f"10.1/c{i}", f"C{i}") for i in range(3)]
    refs = [_paper(f"10.1/r{i}", f"R{i}") for i in range(10)]
    citing_references = {_node_id(paper): refs for paper in citing}

    network = build_network(
        seed,
        [],
        citing,
        citing_references,
        cocitation_max_edges=5,
    )

    assert network["stats"]["cocited_edges"] == 5


async def test_build_citation_network_reports_unresolvable_seed():
    network = await build_citation_network([], "10.1/missing")
    assert "error" in network


async def test_compute_metrics_uses_author_search_results():
    metrics = await compute_metrics([MetricsProvider(None)], author="Someone", limit_per_source=5)
    assert metrics["papers"] == 2
    assert metrics["total_citations"] == 30
    assert metrics["h_index"] == 2
    assert metrics["i10_index"] == 2
    assert metrics["g_index"] == 2


async def test_compute_metrics_requires_author_or_query():
    import pytest

    with pytest.raises(ValueError):
        await compute_metrics([MetricsProvider(None)])


class FilterAwareProvider(ProviderBase):
    name = "filtered"
    supports_search = True
    supports_filters = frozenset({"author"})

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.calls = []

    async def search(
        self,
        query,
        limit,
        year_from=None,
        year_to=None,
        tech_only=False,
        author=None,
        venue=None,
        offset=0,
    ):
        self.calls.append({"author": author, "venue": venue})
        return [Paper(doi="10.1/f", title="Filtered", sources=["filtered"])]


class NoFilterProvider(ProviderBase):
    name = "plain"
    supports_search = True

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.calls = []

    async def search(self, query, limit, year_from=None, year_to=None, tech_only=False, offset=0):
        self.calls.append({})
        return [Paper(doi="10.1/p", title="Plain", sources=["plain"])]


class VenueAuthorProvider(ProviderBase):
    name = "authvenue"
    supports_search = False
    supports_author_search = True
    supports_filters = frozenset({"venue"})

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.calls = []

    async def search_author(
        self, author, limit, year_from=None, year_to=None, venue=None, offset=0
    ):
        self.calls.append({"author": author, "venue": venue})
        return [Paper(doi="10.1/av", title="AV", sources=["authvenue"])]


async def test_search_all_routes_filters_only_to_declaring_providers():
    aware = FilterAwareProvider(None)
    plain = NoFilterProvider(None)

    result = await search_all([aware, plain], "q", author="Ada", venue="JML")

    # Only the declaring provider receives the keyword; the other is still
    # queried, but with its own signature (no author/venue kwargs).
    assert aware.calls == [{"author": "Ada", "venue": None}]
    assert plain.calls == [{}]
    assert result["errors"] == {}
    assert result["filters_applied"] == {"filtered": ["author"]}
    assert result["filters_ignored"] == ["venue"]


async def test_search_all_reports_all_filters_ignored_when_unsupported():
    result = await search_all([NoFilterProvider(None)], "q", author="Ada", venue="JML")

    assert result["filters_applied"] == {}
    assert result["filters_ignored"] == ["author", "venue"]


async def test_search_all_empty_filter_report_when_no_filters_requested():
    result = await search_all([NoFilterProvider(None)], "q")

    assert result["filters_applied"] == {}
    assert result["filters_ignored"] == []


async def test_search_author_forwards_venue_when_supported():
    provider = VenueAuthorProvider(None)

    result = await search_author([provider], "Ada", venue="JML")

    assert provider.calls == [{"author": "Ada", "venue": "JML"}]
    assert result["filters_applied"] == {"authvenue": ["venue"]}
    assert result["filters_ignored"] == []
