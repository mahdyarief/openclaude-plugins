from journal_scout_mcp.aggregator import get_citations, get_paper, search_all
from journal_scout_mcp.models import Paper, ProviderError
from journal_scout_mcp.providers.base import ProviderBase


class GoodProvider(ProviderBase):
    name = "good"
    supports_search = True

    async def search(self, query, limit, year_from=None, year_to=None, tech_only=False):
        return [Paper(doi="10.1/x", title="Shared", citation_count=3, sources=["good"])]


class BadProvider(ProviderBase):
    name = "bad"
    supports_search = True

    async def search(self, query, limit, year_from=None, year_to=None, tech_only=False):
        raise ProviderError("bad", "boom")


class GoodCitationProvider(ProviderBase):
    name = "scopus"
    supports_search = False

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
