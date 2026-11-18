import json

import pytest

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
    assert len(TOOL_NAMES) == 43
    assert "search_exa" in TOOL_NAMES
    assert "slr_import" in TOOL_NAMES
    assert "slr_screen" in TOOL_NAMES
    assert "slr_full_text" in TOOL_NAMES
    assert "slr_appraise" in TOOL_NAMES
    assert "slr_extract" in TOOL_NAMES
    assert "slr_prisma" in TOOL_NAMES
    assert "slr_summary" in TOOL_NAMES
    assert "slr_reset" in TOOL_NAMES
    assert "search_consensus" in TOOL_NAMES
    assert "rotate_consensus_key" in TOOL_NAMES
    assert "search_corpus" in TOOL_NAMES
    assert "identify_paper" in TOOL_NAMES
    assert "search_all" in TOOL_NAMES
    assert "search_author" in TOOL_NAMES
    assert "search_openalex" in TOOL_NAMES
    assert "search_garuda" in TOOL_NAMES
    assert "scival_topic_metrics" in TOOL_NAMES
    assert "get_references" in TOOL_NAMES
    assert "get_related_works" in TOOL_NAMES
    assert "build_citation_network" in TOOL_NAMES
    assert "get_paper_abstract" in TOOL_NAMES
    assert "get_abstracts" in TOOL_NAMES


def test_slr_import_and_prisma():
    from josc.slr import slr_reset, slr_import_records, slr_prisma

    slr_reset()
    res = slr_import_records(
        [
            {"title": "A", "doi": "10.1/x", "year": 2024},
            {"title": "B", "doi": "10.2/y", "year": 2023},
        ]
    )
    assert res["total"] == 2
    assert slr_prisma()["identified"] == 2


def test_slr_screening_and_full_text():
    from josc.slr import (
        slr_reset,
        slr_import_records,
        slr_screening,
        slr_full_text,
        slr_prisma,
    )

    slr_reset()
    slr_import_records([{"title": "A", "doi": "10.1/x"}])
    slr_screening("doi:10_1_x", "include", "S1", "relevant")
    slr_full_text("doi:10_1_x", "exclude", "E1", "no full text")
    p = slr_prisma()
    assert p["screening_decisions"]["include"] == 1
    assert p["full_text_decisions"]["exclude"] == 1
    assert p["included_final"] == 0
    assert "build_research_landscape" in TOOL_NAMES
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


async def test_dispatch_build_research_landscape(monkeypatch):
    import josc.server as server

    async def fake_landscape(query, **kwargs):
        return {"query": query, "nodes": [], "clusters": [], "edges": [], "stats": {"papers": 0}}

    monkeypatch.setattr(server.aggregator, "build_landscape", fake_landscape)

    result = await build_json(
        "build_research_landscape",
        {"query": "deep learning", "n_clusters": 3},
        [SearchProvider(None)],
        None,
    )
    assert result["query"] == "deep learning"
    assert result["stats"]["papers"] == 0


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


async def test_check_watches_tool_is_registered():
    assert "check_watches" in TOOL_NAMES


async def test_check_watches_returns_new_items_per_watch(monkeypatch):
    import josc.server as server

    class FakeWatchStore:
        def __init__(self):
            self.seen = set()
            self.last_results = []

        async def list(self):
            return [
                {
                    "id": "w1",
                    "query": "q",
                    "seen": set(self.seen),
                    "last_results": list(self.last_results),
                }
            ]

        async def get(self, watch_id):
            return {
                "id": watch_id,
                "query": "q",
                "seen": set(self.seen),
                "last_results": list(self.last_results),
            }

        async def mark_seen(self, watch_id, keys, results):
            self.seen |= set(keys)
            self.last_results = list(results)

    fake_store = FakeWatchStore()
    monkeypatch.setattr(server, "_watch_store", lambda: fake_store, raising=False)

    async def fake_search_all(providers, **kwargs):
        return {"results": [{"doi": "10.1/new", "title": "New"}]}

    monkeypatch.setattr(server.aggregator, "search_all", fake_search_all)

    result = await build_json("check_watches", {}, [], None)
    assert result["watches"][0]["checked"] == 1
    assert result["watches"][0]["new"][0]["title"] == "New"


async def test_check_watches_without_store_raises(monkeypatch):
    import josc.server as server
    monkeypatch.setattr(server, "_store", lambda: None, raising=False)
    with pytest.raises(RuntimeError, match="Persistent watch store is not configured"):
        await build_json("check_watches", {}, [], None)


async def test_search_corpus_tool_is_registered():
    assert "search_corpus" in TOOL_NAMES
    schema = next(tool for tool in _tool_list() if tool.name == "search_corpus").inputSchema
    assert schema["required"] == ["query"]


async def test_search_corpus_filters_the_archived_corpus(monkeypatch):
    import josc.server as server

    async def fake_load_corpus(archive, limit=20):
        return [
            {"title": "Deep Learning", "abstract": "neural networks"},
            {"title": "Deep Learning", "abstract": "bayesian inference"},
        ]

    monkeypatch.setattr(server, "load_corpus", fake_load_corpus)
    monkeypatch.setattr(server, "_store", lambda: object(), raising=False)

    result = await build_json("search_corpus", {"query": "deep bayesian"}, [], None)
    assert result["corpus_size"] == 2
    assert len(result["results"]) == 1
    assert result["results"][0]["abstract"] == "bayesian inference"


async def test_search_corpus_without_store_raises(monkeypatch):
    import josc.server as server
    monkeypatch.setattr(server, "_store", lambda: None, raising=False)
    with pytest.raises(RuntimeError, match="Persistent archive store is not configured"):
        await build_json("search_corpus", {"query": "deep"}, [], None)


async def test_rotate_consensus_key_tool_dispatches(monkeypatch):
    import josc.server as server

    calls = {}

    async def fake_rotate(api_key, **kwargs):
        calls["api_key"] = api_key
        return {"rotated": True, "valid": True, "key_hint": "ak_NEW*"}

    monkeypatch.setattr(server.consensus_key, "rotate_consensus_key", fake_rotate)

    result = await build_json("rotate_consensus_key", {"api_key": "ak_NEW"}, [], None)
    assert calls["api_key"] == "ak_NEW"
    assert result["rotated"] is True
    json.dumps(result)


class AbstractLookupProvider(ProviderBase):
    name = "openalex"

    async def get(self, identifier):
        if identifier == "10.1/ok":
            return Paper(doi="10.1/ok", title="T", abstract="The abstract text")
        return None


async def test_dispatch_get_paper_abstract():
    result = await build_json(
        "get_paper_abstract",
        {"doi": "10.1/ok"},
        [AbstractLookupProvider(None)],
        None,
    )
    assert result["abstract"] == "The abstract text"
    assert result["source"] == "openalex"
    assert result["status"] == "found"


async def test_dispatch_get_abstracts_batch():
    result = await build_json(
        "get_abstracts",
        {
            "papers": [
                {"doi": "10.1/ok", "title": "T"},
                {"doi": "10.1/no", "title": "N"},
            ]
        },
        [AbstractLookupProvider(None)],
        None,
    )
    assert [p["doi"] for p in result["papers"]] == ["10.1/ok", "10.1/no"]
    assert result["papers"][0]["abstract"] == "The abstract text"
    assert result["papers"][1]["abstract"] is None
    assert result["summary"] == {"found": 1, "not_found": 1, "existing": 0}


def test_abstract_tools_schemas_advertised():
    names = [t.name for t in _tool_list()]
    assert "get_paper_abstract" in names
    assert "get_abstracts" in names
    single = next(t for t in _tool_list() if t.name == "get_paper_abstract")
    batch = next(t for t in _tool_list() if t.name == "get_abstracts")
    assert "doi" in single.inputSchema["properties"]
    assert "papers" in batch.inputSchema["properties"]


async def test_batch_lookup_tool_is_registered():
    assert "batch_lookup" in TOOL_NAMES
    schema = next(
        tool for tool in _tool_list() if tool.name == "batch_lookup"
    ).inputSchema
    assert "identifiers" in schema["properties"]
    assert schema["required"] == ["identifiers"]


async def test_dispatch_batch_lookup_passes_sources(monkeypatch):
    import josc.server as server

    captured = {}

    async def fake_batch(providers, identifiers, sources=None):
        captured["identifiers"] = identifiers
        captured["sources"] = sources
        return {"papers": [], "counts": {"requested": 0, "resolved": 0}}

    monkeypatch.setattr(server.aggregator, "batch_lookup", fake_batch)
    await build_json(
        "batch_lookup",
        {"identifiers": ["10.1/a"], "sources": ["openalex"]},
        [],
        None,
    )
    assert captured == {"identifiers": ["10.1/a"], "sources": ["openalex"]}


def test_topic_classify_tool_is_registered():
    assert "topic_classify" in TOOL_NAMES
    schema = next(
        tool for tool in _tool_list() if tool.name == "topic_classify"
    ).inputSchema
    assert schema["required"] == ["text"]
    assert schema["properties"]["level"]["enum"] == [
        "topic",
        "subfield",
        "field",
        "domain",
    ]


class TaxonomyProvider(ProviderBase):
    name = "openalex"

    def __init__(self):
        super().__init__(None)
        self.calls = []

    async def classify_topics(self, text, limit=5, level="topic"):
        self.calls.append({"text": text, "limit": limit, "level": level})
        return [{"name": "Machine Learning", "level": level, "score": 0.9}]


async def test_dispatch_topic_classify_uses_openalex_provider():
    provider = TaxonomyProvider()
    result = await build_json(
        "topic_classify",
        {"text": "claims with transformers", "limit": 3, "level": "subfield"},
        [provider],
        None,
    )
    assert provider.calls == [
        {"text": "claims with transformers", "limit": 3, "level": "subfield"}
    ]
    assert result["candidates"][0]["name"] == "Machine Learning"
    assert result["level"] == "subfield"
    assert result["count"] == 1
    json.dumps(result)


async def test_dispatch_topic_classify_reports_missing_provider():
    result = await build_json("topic_classify", {"text": "ai"}, [SearchProvider(None)], None)
    assert result["candidates"] == []
    assert "openalex" in result["error"]


async def test_get_fulltext_tool_is_registered():
    assert "get_fulltext" in TOOL_NAMES
    schema = next(tool for tool in _tool_list() if tool.name == "get_fulltext").inputSchema
    assert "identifier" in schema["properties"]
    assert "max_chars" in schema["properties"]


class FulltextPaperProvider(ProviderBase):
    name = "openalex"

    def __init__(self):
        super().__init__(None)
        self.papers = {}

    async def get(self, identifier):
        return self.papers.get(identifier)


async def test_dispatch_get_fulltext_delegates_to_fulltext_fetch(monkeypatch):
    import josc.server as server

    captured = {}

    async def fake_fetch(providers, identifier, max_chars=20_000):
        captured["providers"] = providers
        captured["identifier"] = identifier
        captured["max_chars"] = max_chars
        return {"status": "found", "full_text": "body", "truncated": False}

    monkeypatch.setattr(server, "fetch_fulltext", fake_fetch)
    provider = FulltextPaperProvider()
    result = await build_json(
        "get_fulltext", {"identifier": "10.1/x", "max_chars": 1234}, [provider], None
    )
    assert result["status"] == "found"
    assert captured["identifier"] == "10.1/x"
    assert captured["max_chars"] == 1234
    assert captured["providers"] == [provider]
