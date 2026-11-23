"""Boolean-operator translation and result sorting.

Every provider is faked here — no test in this module touches the network.
"""

import pytest

from josc.aggregator import search_all
from josc.models import Paper
from josc.providers.base import ProviderBase
from josc.query import detect_operators, operator_report, translate_query


class RecordingProvider(ProviderBase):
    """Records the query it received and returns preset papers."""

    supports_search = True

    def __init__(self, name="crossref", papers=None):
        super().__init__(None)
        self.name = name
        self.papers = papers or []
        self.received = None

    async def search(self, query, limit, **kwargs):
        self.received = query
        return list(self.papers)


def _paper(doi, title, year=2020, citations=0):
    return Paper(
        doi=doi, title=title, year=year, citation_count=citations, sources=["crossref"]
    )


def test_detect_operators_finds_tokens_in_canonical_order():
    assert detect_operators("a NOT b OR c AND d") == ["AND", "OR", "NOT"]


def test_detect_operators_ignores_lowercase_and_substrings():
    assert detect_operators("candy order android") == []
    assert detect_operators("a and b") == []


def test_detect_operators_dedupes():
    assert detect_operators("a AND b AND c") == ["AND"]


def test_translate_crossref_drops_and_keeps_or_not():
    assert translate_query("a AND b OR c NOT d", "crossref") == "a b OR c NOT d"


def test_translate_openalex_drops_all_operators():
    assert translate_query("a AND b OR c NOT d", "openalex") == "a b c d"


def test_translate_scopus_converts_not_to_and_not():
    assert translate_query("a NOT b", "scopus") == "a AND NOT b"
    assert translate_query("a AND NOT b", "scopus") == "a AND NOT b"


def test_translate_unknown_provider_returns_unchanged():
    assert translate_query("a AND b", "unpaywall") == "a AND b"


def test_operator_report_warns_per_unsupported_pair():
    report = operator_report(["crossref", "openalex"], "a AND b OR c")

    assert report["requested"] == ["AND", "OR"]
    # crossref lacks AND (1), openalex lacks both (2).
    assert len(report["warnings"]) == 3
    messages = [warning["message"] for warning in report["warnings"]]
    assert (
        "crossref does not support AND; the operator will be ignored for this source."
        in messages
    )
    assert {warning["source"] for warning in report["warnings"]} == {
        "crossref",
        "openalex",
    }


def test_operator_report_empty_without_operators():
    assert operator_report(["crossref"], "plain query") == {
        "requested": [],
        "warnings": [],
    }


def test_operator_report_ignores_unknown_providers():
    assert operator_report(["unpaywall"], "a AND b")["warnings"] == []


@pytest.mark.asyncio
async def test_search_all_sends_translated_query_and_reports():
    provider = RecordingProvider("crossref")

    result = await search_all([provider], "a AND b OR c")

    assert provider.received == "a b OR c"
    assert result["query_translated"] == {"crossref": "a b OR c"}
    assert result["query_warnings"] == [
        {
            "source": "crossref",
            "operator": "AND",
            "message": (
                "crossref does not support AND; "
                "the operator will be ignored for this source."
            ),
        }
    ]


@pytest.mark.asyncio
async def test_search_all_sorts_citations_desc_none_last():
    provider = RecordingProvider(
        papers=[
            _paper("10.1/a", "A", citations=1),
            _paper("10.1/b", "B", citations=5),
            _paper("10.1/c", "C", citations=None),
            _paper("10.1/d", "D", citations=3),
        ]
    )

    result = await search_all([provider], "q", sort="citations")

    assert [p["title"] for p in result["results"]] == ["B", "D", "A", "C"]


@pytest.mark.asyncio
async def test_search_all_sorts_citations_asc_none_last():
    provider = RecordingProvider(
        papers=[
            _paper("10.1/a", "A", citations=1),
            _paper("10.1/b", "B", citations=5),
            _paper("10.1/c", "C", citations=None),
        ]
    )

    result = await search_all([provider], "q", sort="citations", order="asc")

    assert [p["title"] for p in result["results"]] == ["A", "B", "C"]


@pytest.mark.asyncio
async def test_search_all_sorts_by_year_and_title():
    provider = RecordingProvider(
        papers=[
            _paper("10.1/a", "Beta", year=2019),
            _paper("10.1/b", "Alpha", year=2021),
            _paper("10.1/c", "Gamma", year=None),
        ]
    )

    by_year = await search_all([provider], "q", sort="year", order="asc")
    assert [p["title"] for p in by_year["results"]] == ["Beta", "Alpha", "Gamma"]

    by_title = await search_all([provider], "q", sort="title", order="asc")
    assert [p["title"] for p in by_title["results"]] == ["Alpha", "Beta", "Gamma"]


@pytest.mark.asyncio
async def test_search_all_unknown_sort_is_noop():
    provider = RecordingProvider(
        papers=[
            _paper("10.1/a", "A", citations=1),
            _paper("10.1/b", "B", citations=5),
            _paper("10.1/c", "C", citations=3),
        ]
    )

    result = await search_all([provider], "q", sort="bogus")

    # merge_papers' default ordering is citations desc.
    assert [p["title"] for p in result["results"]] == ["B", "C", "A"]
