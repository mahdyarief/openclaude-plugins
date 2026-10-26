"""Field-filter routing: affiliation / issn / orcid / doi.

Every provider is faked here — no test in this module touches the network.
"""

import pytest

from josc.aggregator import search_all
from josc.models import Paper
from josc.providers.base import ProviderBase
from josc.providers.crossref import CrossrefProvider
from josc.providers.openalex import OpenAlexProvider
from josc.providers.pubmed import PubMedProvider
from josc.providers.scopus import ScopusProvider

ALL_FOUR = ("affiliation", "issn", "orcid", "doi")
VALUES = {
    "affiliation": "MIT",
    "issn": "1234-5678",
    "orcid": "0000-0002-1825-0097",
    "doi": "10.1/x",
}


class RecordingProvider(ProviderBase):
    """Declares ``supports_filters`` and records the kwargs its search got."""

    supports_search = True

    def __init__(self, name="recorder", declared=()):
        super().__init__(None)
        self.name = name
        self.supports_filters = frozenset(declared)
        self.received = None

    async def search(self, query, limit, **kwargs):
        self.received = kwargs
        return [Paper(doi=None, title=f"{self.name}", sources=[self.name])]


@pytest.mark.asyncio
async def test_all_four_filters_routed_to_supporting_provider():
    provider = RecordingProvider("all", ALL_FOUR)

    result = await search_all([provider], "q", **VALUES)

    for field, value in VALUES.items():
        assert provider.received[field] == value
    assert sorted(result["filters_applied"]["all"]) == sorted(ALL_FOUR)
    assert result["filters_ignored"] == []


@pytest.mark.asyncio
async def test_unsupported_filters_reported_ignored():
    provider = RecordingProvider("none", ())

    result = await search_all([provider], "q", **VALUES)

    assert sorted(result["filters_ignored"]) == sorted(ALL_FOUR)
    assert result["filters_applied"] == {}
    # The base search kwargs (year bounds, offset, tech_only) are always sent;
    # what matters is that no field filter reached the provider.
    assert not set(ALL_FOUR) & set(provider.received)


@pytest.mark.asyncio
async def test_partial_support_splits_correctly():
    journals = RecordingProvider("journals", ("issn", "doi"))
    orgs = RecordingProvider("orgs", ("affiliation",))

    result = await search_all([journals, orgs], "q", **VALUES)

    assert sorted(result["filters_applied"]["journals"]) == ["doi", "issn"]
    assert result["filters_applied"]["orgs"] == ["affiliation"]
    assert journals.received["issn"] == VALUES["issn"]
    assert journals.received["doi"] == VALUES["doi"]
    assert "affiliation" not in journals.received
    assert orgs.received["affiliation"] == VALUES["affiliation"]
    assert "issn" not in orgs.received
    assert "doi" not in orgs.received
    # ``orcid`` reached nobody, so it is the only ignored field.
    assert result["filters_ignored"] == ["orcid"]


def test_openalex_filter_strings():
    # ``_filters`` is an instance method, hence the real provider instance.
    provider = OpenAlexProvider(None)
    filters = provider._filters(
        None,
        None,
        False,
        affiliation="Massachusetts Institute of Technology, Cambridge, MA",
        issn="1234-5678",
        orcid="0000-0002-1825-0097",
        doi="https://doi.org/10.1/x",
    )

    assert any(f.startswith("raw_affiliation_strings.search:") for f in filters)
    assert "primary_location.source.issn:1234-5678" in filters
    assert "authorships.author.orcid:0000-0002-1825-0097" in filters
    assert "doi:10.1/x" in filters
    affiliation_clause = next(
        f for f in filters if f.startswith("raw_affiliation_strings.search:")
    )
    assert "," not in affiliation_clause


@pytest.mark.asyncio
async def test_crossref_merges_filter_params(monkeypatch):
    provider = CrossrefProvider(None)
    captured = {}

    async def fake_fetch_json(url, params=None, headers=None, provider_name=None):
        # A DOI search may follow the empty search result with a direct
        # /works/<doi> lookup, which carries no filter. Only the first call
        # is the search request this test is about.
        captured.setdefault("params", params)
        return {"message": {"items": []}}

    monkeypatch.setattr(provider, "_fetch_json", fake_fetch_json)

    await provider.search("q", 5, year_from=2020, issn="1234-5678", doi="10.1/x")

    filter_value = captured["params"]["filter"]
    assert "from-pub-date:2020-01-01" in filter_value
    assert "issn:1234-5678" in filter_value
    assert "doi:10.1/x" in filter_value


@pytest.mark.asyncio
async def test_scopus_query_clauses(monkeypatch):
    provider = ScopusProvider(None, {"api_key": "test-key"})
    captured = {}

    async def fake_search_query(query, limit, offset):
        captured["query"] = query
        return []

    monkeypatch.setattr(provider, "_search_query", fake_search_query)

    await provider.search(
        "cancer",
        5,
        affiliation="MIT",
        issn="1234-5678",
        orcid="0000-0002-1825-0097",
        doi="10.1/x",
    )

    query = captured["query"]
    assert "AFFIL(" in query
    assert "ISSN(" in query
    assert "ORCID(" in query
    assert "DOI(" in query


def test_pubmed_term_clauses():
    term = PubMedProvider._build_term(
        "cancer",
        None,
        None,
        affiliation="MIT",
        issn="1234-5678",
        orcid="0000",
        doi="10.1/x",
    )

    assert "[AD]" in term
    assert "[IS]" in term
    assert "[AID]" in term
    assert "[DOI]" in term
