from josc.aggregator import (
    build_citation_network,
    compute_metrics,
    get_citations,
    get_paper,
    get_related,
    get_references,
    search_all,
    search_author,
)
from josc.models import Paper, ProviderError
from josc.network import build_network, node_id
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


class CountingGetProvider(ProviderBase):
    """Records calls so a test can prove a provider was never asked."""

    def __init__(self, name, title, fetcher=None):
        super().__init__(fetcher)
        self.name = name
        self._title = title
        self.calls = []

    async def get(self, identifier):
        self.calls.append(identifier)
        return Paper(doi="10.1/shared", title=self._title, sources=[self.name])


async def test_get_paper_scopes_to_named_source():
    """A bare numeric id belongs to one source; the others must not guess."""
    garuda = CountingGetProvider("garuda", "Garuda record")
    semanticscholar = CountingGetProvider("semanticscholar", "Wrong record")

    result = await get_paper(
        [garuda, semanticscholar], "6420654", sources=["garuda"]
    )

    assert garuda.calls == ["6420654"]
    assert semanticscholar.calls == []
    assert result["paper"]["title"] == "Garuda record"
    assert result["paper"]["sources"] == ["garuda"]


async def test_get_paper_without_sources_still_queries_every_provider():
    garuda = CountingGetProvider("garuda", "Garuda record")
    semanticscholar = CountingGetProvider("semanticscholar", "Other record")

    result = await get_paper([garuda, semanticscholar], "10.1/shared")

    assert garuda.calls == ["10.1/shared"]
    assert semanticscholar.calls == ["10.1/shared"]
    assert set(result["paper"]["sources"]) == {"garuda", "semanticscholar"}


class CountingRelationProvider(ProviderBase):
    """Records calls so a test can prove a provider was never asked."""

    supports_citations = True
    supports_related = True

    def __init__(self, name, fetcher=None):
        super().__init__(fetcher)
        self.name = name
        self.calls = []

    async def citations(self, identifier, limit):
        self.calls.append(identifier)
        return [Paper(doi="10.1/citing", title="Citing", sources=[self.name])]

    async def related(self, identifier, limit):
        self.calls.append(identifier)
        return [Paper(doi="10.1/related", title="Related", sources=[self.name])]


async def test_get_citations_scopes_to_named_source():
    """A bare id must not be broadcast to providers that only guess at it."""
    scopus = CountingRelationProvider("scopus")
    semanticscholar = CountingRelationProvider("semanticscholar")

    result = await get_citations(
        [scopus, semanticscholar], "6420654", limit=10, sources=["scopus"]
    )

    assert scopus.calls == ["6420654"]
    assert semanticscholar.calls == []
    assert len(result["results"]) == 1
    assert result["results"][0]["sources"] == ["scopus"]


async def test_get_related_scopes_to_named_source():
    openalex = CountingRelationProvider("openalex")
    semanticscholar = CountingRelationProvider("semanticscholar")

    result = await get_related(
        [openalex, semanticscholar], "6420654", limit=10, sources=["openalex"]
    )

    assert openalex.calls == ["6420654"]
    assert semanticscholar.calls == []
    assert result["results"][0]["sources"] == ["openalex"]


async def test_get_citations_collects_from_providers():
    outside = OutsideCitationProvider(None)
    result = await get_citations([GoodCitationProvider(None), outside], "10.1/x", limit=10)
    assert outside.called is False
    assert "crossref" not in result["counts"]
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Citing"


class OptOutProvider(ProviderBase):
    name = "optout"
    supports_search = True
    opt_out = True

    async def search(self, query, limit, year_from=None, year_to=None, tech_only=False, offset=0):
        return [Paper(doi="10.1/opt", title="Opt out record", sources=["optout"])]


async def test_search_all_skips_optout_provider_by_default():
    providers = [GoodProvider(None), OptOutProvider(None)]
    result = await search_all(providers, "q", limit_per_source=5)
    assert "optout" not in result["counts"]
    assert all(p["doi"] != "10.1/opt" for p in result["results"])


async def test_search_all_includes_optout_when_explicitly_requested():
    providers = [GoodProvider(None), OptOutProvider(None)]
    result = await search_all(providers, "q", limit_per_source=5, sources=["optout"])
    assert "optout" in result["counts"]
    assert any(p["doi"] == "10.1/opt" for p in result["results"])


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


class TwoHopProvider(ProviderBase):
    """Resolves a seed, its references, and the references of one reference."""

    name = "twohop"
    supports_search = False
    supports_citations = True
    supports_references = True

    def __init__(self):
        super().__init__(None)
        self.reference_calls = []

    async def get(self, identifier):
        return Paper(doi="10.1/seed", title="Seed", year=2020, sources=["twohop"])

    async def references(self, identifier, limit):
        self.reference_calls.append(identifier)
        if identifier == "10.1/seed":
            return [
                Paper(doi="10.1/r1", title="Ref one", sources=["twohop"]),
                Paper(doi="10.1/r2", title="Ref two", sources=["twohop"]),
            ]
        if identifier == "10.1/r1":
            return [Paper(doi="10.1/deep", title="Deep", sources=["twohop"])]
        return []

    async def citations(self, identifier, limit):
        return []


async def test_build_citation_network_fetches_second_hop_references():
    """The seed's references must be expanded, or the graph is a star."""
    provider = TwoHopProvider()

    network = await build_citation_network(
        [provider], "10.1/seed", limit=5, citing_limit=2
    )

    assert "10.1/r1" in provider.reference_calls
    assert "10.1/r2" in provider.reference_calls
    cites = {(e["source"], e["target"]) for e in network["edges"] if e["type"] == "cites"}
    assert ("doi:10.1/r1", "doi:10.1/deep") in cites
    assert network["counts"]["reference_references"] == 2


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
    citing_references = {node_id(paper): refs for paper in citing}

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


class TechOnlyProvider(ProviderBase):
    name = "tech"
    supports_search = True
    supports_tech_only = True

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.calls = []

    async def search(self, query, limit, year_from=None, year_to=None, tech_only=False, offset=0):
        self.calls.append({"tech_only": tech_only})
        return [Paper(doi="10.1/t", title="Tech", sources=["tech"])]


async def test_search_all_forwards_tech_only_to_declaring_providers():
    provider = TechOnlyProvider(None)

    result = await search_all([provider], "q", tech_only=True)

    assert provider.calls == [{"tech_only": True}]
    assert result["filters_applied"] == {"tech": ["tech_only"]}
    assert result["filters_ignored"] == []


async def test_search_all_reports_tech_only_ignored_when_unsupported():
    plain = NoFilterProvider(None)

    result = await search_all([plain], "q", tech_only=True)

    assert result["filters_applied"] == {}
    assert result["filters_ignored"] == ["tech_only"]


async def test_search_all_omits_tech_only_from_report_when_not_requested():
    provider = TechOnlyProvider(None)

    result = await search_all([provider], "q")

    assert result["filters_applied"] == {}
    assert result["filters_ignored"] == []
    assert provider.calls == [{"tech_only": False}]


async def test_search_all_reports_tech_only_alongside_field_filters():
    tech = TechOnlyProvider(None)
    aware = FilterAwareProvider(None)

    result = await search_all([tech, aware], "q", author="Ada", tech_only=True)

    assert result["filters_applied"] == {"tech": ["tech_only"], "filtered": ["author"]}
    assert result["filters_ignored"] == []


class MultiProvider(ProviderBase):
    name = "multi"
    supports_search = True

    def __init__(self, fetcher, papers):
        super().__init__(fetcher)
        self.papers = papers

    async def search(self, query, limit, year_from=None, year_to=None, tech_only=False, offset=0):
        return list(self.papers)


async def test_search_all_sort_relevance_ranks_title_match_above_abstract_match():
    # The abstract-only title sorts alphabetically first, so this fails unless
    # relevance scoring really runs instead of the default title ordering.
    abstract_only = Paper(
        doi="10.1/abs",
        title="A survey of things",
        abstract="A study about data quality in practice.",
        sources=["multi"],
    )
    title_match = Paper(
        doi="10.1/title",
        title="Data quality in practice",
        abstract=None,
        sources=["multi"],
    )
    provider = MultiProvider(None, [abstract_only, title_match])

    result = await search_all([provider], "data quality", sort="relevance")

    assert [paper["doi"] for paper in result["results"]] == ["10.1/title", "10.1/abs"]


async def test_search_all_sort_relevance_ignores_boolean_operators():
    operator_only = Paper(
        doi="10.1/op",
        title="And or not",
        abstract=None,
        sources=["multi"],
    )
    match = Paper(
        doi="10.1/match",
        title="Data quality",
        abstract=None,
        sources=["multi"],
    )
    provider = MultiProvider(None, [operator_only, match])

    result = await search_all([provider], "data AND quality", sort="relevance")

    assert [paper["doi"] for paper in result["results"]] == ["10.1/match", "10.1/op"]


async def test_search_all_filters_by_topic_after_merge():
    """Topic vocabularies differ per provider, so the filter runs locally."""
    provider = MultiProvider(
        None,
        [
            Paper(doi="10.1/ml", title="ML", topics=["Machine Learning"], sources=["multi"]),
            Paper(doi="10.1/db", title="DB", topics=["Databases"], sources=["multi"]),
            Paper(doi="10.1/none", title="No topic", sources=["multi"]),
        ],
    )

    result = await search_all([provider], "q", topic="machine learning")

    assert [paper["doi"] for paper in result["results"]] == ["10.1/ml"]
    # Local filtering is not a provider capability, so it is neither applied
    # nor ignored at the provider level.
    assert result["filters_applied"] == {}
    assert result["filters_ignored"] == []


async def test_search_all_topic_filter_matches_any_topic_case_insensitively():
    provider = MultiProvider(
        None,
        [
            Paper(
                doi="10.1/a",
                title="A",
                topics=["Information Retrieval", "Data Quality"],
                sources=["multi"],
            ),
            Paper(doi="10.1/b", title="B", topics=["Databases"], sources=["multi"]),
        ],
    )

    result = await search_all([provider], "q", topic="data quality")

    assert [paper["doi"] for paper in result["results"]] == ["10.1/a"]


async def test_search_all_without_topic_filter_keeps_every_record():
    provider = MultiProvider(
        None,
        [Paper(doi="10.1/a", title="A", topics=[], sources=["multi"])],
    )

    result = await search_all([provider], "q")

    assert len(result["results"]) == 1
