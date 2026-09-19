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
    name = "goodcite"
    supports_search = False

    async def citations(self, identifier, limit):
        return [Paper(doi="10.2/y", title="Citing", sources=["goodcite"])]


class GoodGetProvider(ProviderBase):
    name = "goodget"
    supports_search = False

    async def get(self, identifier):
        return Paper(doi="10.1/x", title="Shared", year=2020, sources=["goodget"])


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
    result = await get_paper([GoodGetProvider(None), GoodProvider(None)], "10.1/x")
    assert result["paper"]["doi"] == "10.1/x"
    assert set(result["paper"]["sources"]) == {"good", "goodget"}


async def test_get_citations_collects_from_providers():
    result = await get_citations([GoodCitationProvider(None)], "10.1/x", limit=10)
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Citing"
