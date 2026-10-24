import json

from josc.server import TOOL_NAMES, build_json
from josc.models import Paper
from josc.providers.base import ProviderBase


class SearchProvider(ProviderBase):
    name = "openalex"
    supports_search = True

    async def search(self, query, limit, year_from=None, year_to=None, tech_only=False, offset=0):
        return [Paper(doi="10.1/x", title="Hit", sources=["openalex"])]


class AuthorProvider(ProviderBase):
    name = "scopus"
    supports_search = True
    supports_author_search = True

    async def search_author(self, author, limit, year_from=None, year_to=None, offset=0):
        return [Paper(doi="10.2/y", title=f"By {author}", sources=["scopus"])]


def test_tool_names_count():
    assert len(TOOL_NAMES) == 24
    assert "search_all" in TOOL_NAMES
    assert "search_author" in TOOL_NAMES
    assert "search_openalex" in TOOL_NAMES
    assert "scival_topic_metrics" in TOOL_NAMES
    assert "get_references" in TOOL_NAMES
    assert "get_related_works" in TOOL_NAMES
    assert "build_citation_network" in TOOL_NAMES
    assert "compute_metrics" in TOOL_NAMES
    assert "get_citing_papers" not in TOOL_NAMES


async def test_dispatch_search_all():
    result = await build_json("search_all", {"query": "q"}, [SearchProvider(None)], None)
    assert result["results"][0]["title"] == "Hit"


async def test_dispatch_per_source_search():
    result = await build_json("search_openalex", {"query": "q", "count": 3}, [SearchProvider(None)], None)
    assert result["results"][0]["title"] == "Hit"


async def test_dispatch_search_author():
    result = await build_json("search_author", {"author": "Vaswani"}, [AuthorProvider(None)], None)
    assert result["results"][0]["title"] == "By Vaswani"


class AbstractDetailProvider(ProviderBase):
    name = "scopus"

    async def get(self, identifier: str):
        return Paper(doi="10.1145/123", title="Fixture title", sources=["scopus"])


class MissingAbstractProvider(ProviderBase):
    name = "scopus"

    async def get(self, identifier: str):
        return None


async def test_dispatch_get_abstract_details_returns_serializable_dict():
    """Regression: this tool used to return a raw Paper and always errored."""
    provider = AbstractDetailProvider(None)
    result = await build_json("get_abstract_details", {"scopus_id": "7001234"}, [], provider)

    assert result["paper"]["title"] == "Fixture title"
    assert result["paper"]["doi"] == "10.1145/123"
    json.dumps(result)


async def test_dispatch_get_abstract_details_handles_missing_record():
    provider = MissingAbstractProvider(None)
    result = await build_json("get_abstract_details", {"scopus_id": "0"}, [], provider)

    assert result == {"paper": None}
    json.dumps(result)


async def test_dispatch_unknown_tool_raises():
    try:
        await build_json("nope", {}, [], None)
    except ValueError as e:
        assert "Unknown tool" in str(e)
    else:
        raise AssertionError("expected ValueError")
