import asyncio

from josc.abstracts import enrich_abstracts, resolve_abstract
from josc.models import Paper, ProviderError
from josc.providers.base import ProviderBase


class StaticProvider(ProviderBase):
    """Provider whose lookups are scripted by the test, keyed by identifier."""

    def __init__(self, name, records=None, error=None, search_records=None):
        super().__init__(fetcher=None, config={})
        self.name = name
        self.records = records or {}
        self.error = error
        self.search_records = search_records or []
        self.calls = []

    async def get(self, identifier):
        self.calls.append(("get", identifier))
        if self.error:
            raise self.error
        return self.records.get(identifier)

    async def search(self, query, limit, year_from=None, year_to=None, **kwargs):
        self.calls.append(("search", query))
        return self.search_records[:limit]


class PlainProvider(ProviderBase):
    """No ``get`` override: must be skipped by the resolver."""

    name = "plain"


async def test_resolve_abstract_returns_text_from_first_available_source():
    found = StaticProvider(
        "openalex",
        records={"10.1/x": Paper(title="T", abstract="From OpenAlex")},
    )
    empty = StaticProvider("crossref", records={"10.1/x": Paper(title="T")})

    result = await resolve_abstract([found, empty], doi="10.1/x")

    assert result["abstract"] == "From OpenAlex"
    assert result["source"] == "openalex"
    assert result["status"] == "found"


async def test_resolve_abstract_reports_not_found_without_inventing_text():
    empty = StaticProvider("crossref", records={"10.1/x": Paper(title="T")})

    result = await resolve_abstract([empty], doi="10.1/x")

    assert result["abstract"] is None
    assert result["source"] is None
    assert result["status"] == "not_found"


async def test_resolve_abstract_keeps_going_after_a_provider_error():
    broken = StaticProvider("scopus", error=ProviderError("scopus", "boom"))
    working = StaticProvider(
        "pubmed",
        records={"10.1/x": Paper(title="T", abstract="From PubMed")},
    )

    result = await resolve_abstract([broken, working], doi="10.1/x")

    assert result["abstract"] == "From PubMed"
    assert result["source"] == "pubmed"
    assert "scopus" in result["errors"]


async def test_resolve_abstract_falls_back_to_title_search_without_doi():
    searcher = StaticProvider(
        "semanticscholar",
        search_records=[Paper(title="A paper", abstract="Found by title")],
    )

    result = await resolve_abstract([searcher], title="A paper")

    assert result["abstract"] == "Found by title"
    assert result["source"] == "semanticscholar"


async def test_resolve_abstract_skips_providers_without_a_lookup():
    plain = PlainProvider(None)
    working = StaticProvider(
        "crossref",
        records={"10.1/x": Paper(title="T", abstract="Text")},
    )

    result = await resolve_abstract([plain, working], doi="10.1/x")

    assert result["abstract"] == "Text"
    assert plain.name not in result["attempted"]


async def test_resolve_abstract_ignores_blank_abstracts():
    blank = StaticProvider("crossref", records={"10.1/x": Paper(title="T", abstract="   ")})
    real = StaticProvider(
        "openalex",
        records={"10.1/x": Paper(title="T", abstract="Real text")},
    )

    result = await resolve_abstract([blank, real], doi="10.1/x")

    assert result["abstract"] == "Real text"
    assert result["source"] == "openalex"


async def test_enrich_abstracts_keeps_order_and_marks_existing():
    provider = StaticProvider(
        "openalex",
        records={"10.2/y": Paper(title="Y", abstract="Fetched")},
    )
    papers = [
        {"doi": "10.1/x", "title": "X", "abstract": "Already here"},
        {"doi": "10.2/y", "title": "Y", "abstract": None},
        {"doi": "10.3/z", "title": "Z"},
    ]

    result = await enrich_abstracts([provider], papers)

    by_doi = {p["doi"]: p for p in result["papers"]}
    assert [p["doi"] for p in result["papers"]] == ["10.1/x", "10.2/y", "10.3/z"]
    assert by_doi["10.1/x"]["abstract"] == "Already here"
    assert by_doi["10.1/x"]["status"] == "existing"
    assert by_doi["10.2/y"]["abstract"] == "Fetched"
    assert by_doi["10.3/z"]["status"] == "not_found"
    assert result["summary"] == {"found": 1, "not_found": 1, "existing": 1}


async def test_enrich_abstracts_does_not_mutate_input():
    provider = StaticProvider(
        "openalex", records={"10.2/y": Paper(title="Y", abstract="Fetched")}
    )
    papers = [{"doi": "10.2/y", "title": "Y", "abstract": None}]

    await enrich_abstracts([provider], papers)

    assert papers[0]["abstract"] is None


async def test_resolve_abstract_times_out_slow_provider():
    class SlowProvider(ProviderBase):
        name = "slow"

        async def get(self, identifier):
            await asyncio.sleep(1)
            return Paper(title="T", abstract="too late")

    result = await resolve_abstract([SlowProvider(None)], doi="10.1/x", timeout=0.05)

    assert result["status"] == "not_found"
    assert "slow" in result["errors"]


async def test_resolve_abstract_does_not_borrow_a_different_papers_abstract():
    provider = StaticProvider(
        "searchable",
        records={"10.1/x": Paper(doi="10.9/other", title="Other", abstract="Wrong paper")},
        search_records=[Paper(doi="10.8/unrelated", title="Unrelated", abstract="Also wrong")],
    )

    result = await resolve_abstract([provider], doi="10.1/x", title="Wanted paper")

    assert result["status"] == "not_found"
    assert result["abstract"] is None


async def test_resolve_abstract_matches_identifier_from_ids_map():
    provider = StaticProvider(
        "pubmed",
        records={"pmid:123": Paper(title="T", abstract="By PMID")},
    )

    result = await resolve_abstract(
        [provider], paper={"doi": "10.1/x", "ids": {"pmid": "pmid:123"}}
    )

    assert result["abstract"] == "By PMID"
    assert result["source"] == "pubmed"


async def test_resolve_abstract_normalizes_doi_given_as_identifier():
    provider = StaticProvider(
        "openalex",
        records={"10.1/x": Paper(doi="10.9/other", title="T", abstract="Wrong")},
    )

    result = await resolve_abstract([provider], paper={"identifier": "https://doi.org/10.1/x"})

    assert result["status"] == "not_found"
    assert result["abstract"] is None
