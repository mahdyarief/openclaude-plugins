from josc.aggregator import batch_lookup
from josc.models import Paper, ProviderError
from josc.providers.base import ProviderBase


class BatchProvider(ProviderBase):
    name = "openalex"

    def __init__(self, papers, batches=None):
        super().__init__(None)
        self._papers = {key.lower(): value for key, value in papers.items()}
        self.batch_calls = []
        self.get_calls = []
        if batches is not None:
            self.get_many = self._get_many_impl

    async def _get_many_impl(self, identifiers):
        self.batch_calls.append(list(identifiers))
        return [
            self._papers[identifier.lower()]
            for identifier in identifiers
            if identifier.lower() in self._papers
        ]

    async def get(self, identifier):
        self.get_calls.append(identifier)
        return self._papers.get(identifier.lower())


class BrokenProvider(ProviderBase):
    name = "crossref"

    async def get(self, identifier):
        raise ProviderError("crossref", "HTTP 500: boom")


async def test_batch_lookup_uses_single_batch_call():
    papers = {
        "10.1/a": Paper(doi="10.1/a", title="A"),
        "10.1/b": Paper(doi="10.1/b", title="B"),
    }
    provider = BatchProvider(papers, batches=True)
    result = await batch_lookup([provider], ["10.1/a", "10.1/b"])
    assert provider.batch_calls == [["10.1/a", "10.1/b"]]
    assert provider.get_calls == []
    assert [p["title"] for p in result["papers"]] == ["A", "B"]
    assert result["counts"] == {"requested": 2, "resolved": 2}
    assert result["not_found"] == []
    assert result["errors"] == {}


async def test_batch_lookup_falls_back_to_per_identifier_get():
    papers = {"10.1/a": Paper(doi="10.1/a", title="A")}
    provider = BatchProvider(papers)
    result = await batch_lookup([provider], ["10.1/a"])
    assert provider.get_calls == ["10.1/a"]
    assert provider.batch_calls == []
    assert result["papers"][0]["title"] == "A"


async def test_batch_lookup_reports_missing_and_errors():
    provider = BatchProvider({"10.1/a": Paper(doi="10.1/a", title="A")}, batches=True)
    result = await batch_lookup(
        [provider, BrokenProvider(None)], ["10.1/a", "10.1/missing"]
    )
    assert len(result["papers"]) == 1
    assert result["not_found"] == ["10.1/missing"]
    assert result["errors"]["crossref"] == "HTTP 500: boom"
    assert result["counts"] == {"requested": 2, "resolved": 1}


async def test_batch_lookup_preserves_request_order_and_dedups():
    papers = {
        "10.1/b": Paper(doi="10.1/b", title="B"),
        "10.1/a": Paper(doi="10.1/a", title="A"),
    }
    provider = BatchProvider(papers, batches=True)
    result = await batch_lookup([provider], ["10.1/b", "10.1/a", "10.1/b"])
    assert [p["title"] for p in result["papers"]] == ["B", "A"]
    assert provider.batch_calls == [["10.1/b", "10.1/a"]]


async def test_batch_lookup_skips_enrichers_and_honours_sources():
    papers = {"10.1/a": Paper(doi="10.1/a", title="A")}
    lookup = BatchProvider(papers)
    other = BatchProvider(papers)
    other.name = "arxiv"
    enricher = BatchProvider(papers)
    enricher.name = "unpaywall"
    enricher.enricher = True
    result = await batch_lookup(
        [lookup, other, enricher], ["10.1/a"], sources=["arxiv"]
    )
    assert lookup.get_calls == []
    assert other.get_calls == ["10.1/a"]
    assert result["counts"]["resolved"] == 1


async def test_batch_lookup_matches_identifiers_case_insensitively():
    papers = {"10.1/abc": Paper(doi="10.1/ABC", title="A")}
    provider = BatchProvider(papers, batches=True)
    result = await batch_lookup([provider], ["10.1/ABC"])
    assert result["papers"][0]["title"] == "A"
    assert result["counts"]["resolved"] == 1
