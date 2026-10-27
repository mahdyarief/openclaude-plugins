import json

from josc.server import TOOL_NAMES, _tool_list, build_json
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
    assert len(TOOL_NAMES) == 26
    assert "identify_paper" in TOOL_NAMES
    assert "search_all" in TOOL_NAMES
    assert "search_author" in TOOL_NAMES
    assert "search_openalex" in TOOL_NAMES
    assert "search_garuda" in TOOL_NAMES
    assert "scival_topic_metrics" in TOOL_NAMES
    assert "get_references" in TOOL_NAMES
    assert "get_related_works" in TOOL_NAMES
    assert "build_citation_network" in TOOL_NAMES
    assert "compute_metrics" in TOOL_NAMES
    assert "get_citing_papers" not in TOOL_NAMES


async def test_dispatch_search_all():
    result = await build_json("search_all", {"query": "q"}, [SearchProvider(None)], None)
    assert result["results"][0]["title"] == "Hit"


def test_search_all_schema_advertises_topic_filter():
    schema = next(tool for tool in _tool_list() if tool.name == "search_all").inputSchema
    assert "topic" in schema["properties"]


def test_search_all_schema_advertises_conditions():
    schema = next(tool for tool in _tool_list() if tool.name == "search_all").inputSchema
    conditions = schema["properties"]["conditions"]
    assert conditions["type"] == "array"
    item = conditions["items"]
    assert set(item["properties"]) == {"field", "value", "operator"}
    assert sorted(item["properties"]["field"]["enum"]) == [
        "abstract",
        "all",
        "author",
        "title",
        "venue",
    ]
    assert item["required"] == ["field", "value"]


class ScopingProvider(ProviderBase):
    name = "scopus"
    supports_search = True

    def __init__(self):
        super().__init__(None)
        self.received = None

    async def search(self, query, limit, **kwargs):
        self.received = query
        return [Paper(doi="10.1/s", title="Scoped", sources=["scopus"])]


async def test_dispatch_search_all_forwards_conditions_without_query():
    provider = ScopingProvider()

    result = await build_json(
        "search_all",
        {
            "conditions": [
                {"field": "title", "value": "data quality", "operator": "AND"}
            ]
        },
        [provider],
        None,
    )

    assert provider.received == 'TITLE("data quality")'
    assert result["query_scoping"]["scopus"] == {
        "honored": ["title"],
        "degraded": [],
    }


class TopicProvider(ProviderBase):
    name = "openalex"
    supports_search = True

    async def search(self, query, limit, year_from=None, year_to=None, tech_only=False, offset=0):
        return [
            Paper(
                doi="10.1/ml",
                title="ML paper",
                topics=["Machine Learning"],
                sources=["openalex"],
            )
        ]


async def test_dispatch_search_all_forwards_topic_filter():
    result = await build_json(
        "search_all",
        {"query": "q", "topic": "machine learning"},
        [TopicProvider(None)],
        None,
    )
    assert [paper["doi"] for paper in result["results"]] == ["10.1/ml"]

    filtered_out = await build_json(
        "search_all",
        {"query": "q", "topic": "databases"},
        [TopicProvider(None)],
        None,
    )
    assert filtered_out["results"] == []


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


class NetworkSeedProvider(ProviderBase):
    name = "openalex"
    supports_search = False
    supports_references = True

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.reference_calls = []

    async def get(self, identifier):
        return Paper(doi="10.1/seed", title="Seed", year=2020, sources=["openalex"])

    async def references(self, identifier, limit):
        self.reference_calls.append(identifier)
        if identifier == "10.1/seed":
            return [Paper(doi="10.1/r1", title="Ref one", year=2019, sources=["openalex"])]
        return [Paper(doi="10.1/deep", title="Deep ref", year=2018, sources=["openalex"])]

    async def citations(self, identifier, limit):
        return []


async def test_dispatch_build_citation_network_forwards_reference_limit():
    """The MCP schema exposes reference_limit; the dispatcher must honour it."""
    provider = NetworkSeedProvider(None)

    network = await build_json(
        "build_citation_network",
        {"identifier": "10.1/seed", "reference_limit": 0},
        [provider],
        None,
    )

    assert provider.reference_calls == ["10.1/seed"]
    assert network["counts"]["reference_references"] == 0
    assert network["stats"]["nodes"] == 2


async def test_identify_paper_tool_is_registered():
    assert "identify_paper" in TOOL_NAMES
    schema = next(tool for tool in _tool_list() if tool.name == "identify_paper").inputSchema
    assert schema["required"] == ["path"]


async def test_identify_paper_dispatches_through_recognize(monkeypatch):
    import josc.server as server

    monkeypatch.setattr(server, "extract_pdf_text", lambda path: "doi 10.1/x")

    async def fake_get_paper(providers, identifier, sources=None):
        return {"paper": {"title": "Resolved"}, "errors": {}}

    monkeypatch.setattr(server.aggregator, "get_paper", fake_get_paper)

    result = await build_json("identify_paper", {"path": "x.pdf"}, [], None)
    assert result["identifier"] == "10.1/x"
    assert result["paper"]["title"] == "Resolved"
