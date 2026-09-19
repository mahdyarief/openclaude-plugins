from journal_scout_mcp.server import TOOL_NAMES, build_json
from journal_scout_mcp.models import Paper
from journal_scout_mcp.providers.base import ProviderBase


class SearchProvider(ProviderBase):
    name = "openalex"
    supports_search = True

    async def search(self, query, limit, year_from=None, year_to=None, tech_only=False):
        return [Paper(doi="10.1/x", title="Hit", sources=["openalex"])]


def test_tool_names_count():
    assert len(TOOL_NAMES) == 17
    assert "search_all" in TOOL_NAMES
    assert "search_openalex" in TOOL_NAMES
    assert "scival_topic_metrics" in TOOL_NAMES
    assert "get_citing_papers" not in TOOL_NAMES


async def test_dispatch_search_all():
    result = await build_json("search_all", {"query": "q"}, [SearchProvider(None)], None)
    assert result["results"][0]["title"] == "Hit"


async def test_dispatch_per_source_search():
    result = await build_json("search_openalex", {"query": "q", "count": 3}, [SearchProvider(None)], None)
    assert result["results"][0]["title"] == "Hit"


async def test_dispatch_unknown_tool_raises():
    try:
        await build_json("nope", {}, [], None)
    except ValueError as e:
        assert "Unknown tool" in str(e)
    else:
        raise AssertionError("expected ValueError")
