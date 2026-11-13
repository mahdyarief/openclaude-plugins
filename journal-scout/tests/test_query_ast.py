"""Structured field-scoped query compilation.

Every provider is faked here — no test in this module touches the network.
"""

import pytest

from josc.aggregator import search_all
from josc.models import Paper
from josc.providers.base import ProviderBase
from josc.query_ast import (
    Condition,
    FIELD_CAPABILITIES,
    compile_conditions,
    parse_conditions,
)


def _cond(field, value, operator="AND"):
    return {"field": field, "value": value, "operator": operator}


def test_parse_conditions_accepts_dicts_and_drops_blanks():
    parsed = parse_conditions(
        [
            _cond("title", "data quality"),
            _cond("author", "  ", "OR"),
            _cond("abstract", "village"),
        ]
    )

    assert parsed == [
        Condition(field="title", value="data quality", operator="AND"),
        Condition(field="abstract", value="village", operator="AND"),
    ]


def test_parse_conditions_rejects_unknown_field():
    with pytest.raises(ValueError):
        parse_conditions([_cond("banana", "x")])


def test_compile_scopus_scopes_title():
    compiled = compile_conditions(
        [Condition("title", "data quality")], "scopus"
    )

    assert compiled.query == 'TITLE("data quality")'
    assert compiled.honored == ["title"]
    assert compiled.degraded == []


def test_compile_pubmed_scopes_author():
    compiled = compile_conditions([Condition("author", "Smith J")], "pubmed")

    assert compiled.query == '"Smith J"[Author]'
    assert compiled.honored == ["author"]


def test_compile_arxiv_scopes_title():
    compiled = compile_conditions([Condition("title", "deep learning")], "arxiv")

    assert compiled.query == 'ti:"deep learning"'


def test_compile_dblp_scopes_venue():
    compiled = compile_conditions([Condition("venue", "ICIS")], "dblp")

    assert compiled.query == "venue:ICIS"


def test_compile_joins_conditions_with_operators():
    compiled = compile_conditions(
        [
            Condition("title", "data quality"),
            Condition("author", "Smith", "OR"),
            Condition("abstract", "village", "AND"),
        ],
        "scopus",
    )

    assert compiled.query == 'TITLE("data quality") OR AUTH("Smith") AND ABS("village")'


def test_compile_scopus_turns_not_into_and_not():
    compiled = compile_conditions(
        [Condition("title", "quality"), Condition("author", "Smith", "NOT")],
        "scopus",
    )

    assert compiled.query == 'TITLE("quality") AND NOT AUTH("Smith")'


def test_compile_degrades_unsupported_field_to_free_text():
    compiled = compile_conditions(
        [Condition("title", "data quality")], "semanticscholar"
    )

    assert compiled.query == "data quality"
    assert compiled.honored == []
    assert compiled.degraded == ["title"]


def test_compile_mixed_support_reports_both():
    compiled = compile_conditions(
        [Condition("title", "quality"), Condition("venue", "ICIS")], "arxiv"
    )

    assert compiled.query == 'ti:"quality" ICIS'
    assert compiled.honored == ["title"]
    assert compiled.degraded == ["venue"]


def test_field_capabilities_cover_every_searchable_provider():
    assert set(FIELD_CAPABILITIES) == {
        "scopus",
        "pubmed",
        "arxiv",
        "dblp",
        "crossref",
        "openalex",
        "semanticscholar",
        "garuda",
    }
    # The matrix must never claim scoping the compiler cannot emit.
    for provider, fields in FIELD_CAPABILITIES.items():
        assert "all" in fields, provider


class RecordingProvider(ProviderBase):
    supports_search = True

    def __init__(self, name):
        super().__init__(None)
        self.name = name
        self.received = None

    async def search(self, query, limit, **kwargs):
        self.received = query
        return [Paper(doi=None, title=self.name, sources=[self.name])]


@pytest.mark.asyncio
async def test_search_all_compiles_conditions_per_provider():
    scopus = RecordingProvider("scopus")
    scholar = RecordingProvider("semanticscholar")

    result = await search_all(
        [scopus, scholar],
        "",
        conditions=[_cond("title", "data quality")],
    )

    assert scopus.received == 'TITLE("data quality")'
    assert scholar.received == "data quality"
    assert result["query_scoping"]["scopus"] == {
        "honored": ["title"],
        "degraded": [],
    }
    assert result["query_scoping"]["semanticscholar"] == {
        "honored": [],
        "degraded": ["title"],
    }


@pytest.mark.asyncio
async def test_search_all_without_conditions_leaves_scoping_empty():
    provider = RecordingProvider("scopus")

    result = await search_all([provider], "cancer")

    assert result["query_scoping"] == {}
    assert provider.received == "cancer"
