"""Route handlers exercised directly with a minimal fake Request.

The handlers under test do not touch the network, so calling them directly
avoids spinning up the Starlette app (whose lifespan tries to reach Turso).
"""

import base64

import pytest

from josc import api


class QueryParams(dict):
    """Dict that also answers ``getlist`` the way Starlette's QueryParams does."""

    def getlist(self, key):
        value = self.get(key)
        return [] if value is None else [value]


class FakeRequest:
    def __init__(self, body=None, path_params=None, query_params=None):
        self._body = body
        self.path_params = path_params or {}
        self.query_params = QueryParams(query_params or {})

    async def json(self):
        if self._body is None:
            raise ValueError("no body")
        return self._body


def _body(response):
    import json

    return json.loads(response.body.decode())


async def test_merge_route_deduplicates_by_doi():
    req = FakeRequest(
        body={
            "papers": [
                {"doi": "10.1/a", "title": "A", "year": 2020, "citation_count": 5},
                {"doi": "10.1/A", "title": "A extended", "year": 2020, "citation_count": 9},
                {"doi": "10.1/b", "title": "B", "year": 2021},
            ]
        }
    )
    response = await api.merge(req)

    assert response.status_code == 200
    payload = _body(response)
    assert payload["input_count"] == 3
    assert payload["merged_count"] == 2
    assert payload["results"][0]["doi"].lower() == "10.1/a"


async def test_merge_route_ignores_unknown_paper_keys():
    req = FakeRequest(
        body={"papers": [{"doi": "10.1/a", "title": "A", "provider_extra": "x"}]}
    )
    response = await api.merge(req)

    assert response.status_code == 200
    assert _body(response)["merged_count"] == 1


async def test_merge_route_rejects_non_object_body():
    response = await api.merge(FakeRequest(body=["not", "an", "object"]))
    assert response.status_code >= 400


async def test_merge_route_rejects_missing_papers():
    response = await api.merge(FakeRequest(body={}))
    assert response.status_code >= 400


async def test_merge_route_rejects_non_object_entries():
    response = await api.merge(FakeRequest(body={"papers": ["nope"]}))
    assert response.status_code >= 400


class FakeStore:
    def __init__(self, row=None, search_id="new-id"):
        self.row = row
        self.search_id = search_id
        self.imported = None

    async def get_search(self, search_id):
        return self.row

    async def import_search(self, archive, **kwargs):
        self.imported = (archive, kwargs)
        return self.search_id


@pytest.fixture
def with_store(monkeypatch):
    def _install(store):
        monkeypatch.setitem(api._state, "store", store)
        return store

    return _install


async def test_search_export_returns_archive(with_store):
    store = with_store(
        FakeStore(
            row={
                "id": "abc",
                "query": "graphene",
                "author": None,
                "sources": ["arxiv"],
                "filters": None,
                "result_count": 1,
                "created_at": 100.0,
                "results": [{"doi": "10.1/a"}],
            }
        )
    )
    req = FakeRequest(path_params={"search_id": "abc"})
    response = await api.search_export(req)

    assert response.status_code == 200
    payload = _body(response)
    assert payload["format"] == "josc-search-archive"
    assert payload["version"] == 1
    assert payload["results"] == [{"doi": "10.1/a"}]
    assert store.row is not None


async def test_search_export_404_when_missing(with_store):
    with_store(FakeStore(row=None))
    req = FakeRequest(path_params={"search_id": "nope"})
    response = await api.search_export(req)
    assert response.status_code == 404


async def test_search_export_without_store_errors(monkeypatch):
    monkeypatch.setitem(api._state, "store", None)
    req = FakeRequest(path_params={"search_id": "abc"})
    response = await api.search_export(req)
    assert response.status_code >= 400


async def test_search_import_persists_archive(with_store):
    store = with_store(FakeStore())
    req = FakeRequest(
        body={
            "format": "josc-search-archive",
            "version": 1,
            "query": "graphene",
            "sources": ["arxiv"],
            "results": [{"doi": "10.1/a"}],
        }
    )
    response = await api.search_import(req)

    assert response.status_code == 200
    payload = _body(response)
    assert payload["id"] == "new-id"
    assert payload["result_count"] == 1
    archive, kwargs = store.imported
    assert archive["query"] == "graphene"
    assert kwargs["results"] == [{"doi": "10.1/a"}]
    assert kwargs["result_count"] == 1


async def test_search_import_rejects_missing_results(with_store):
    with_store(FakeStore())
    response = await api.search_import(FakeRequest(body={"query": "x"}))
    assert response.status_code >= 400


async def test_search_import_rejects_non_string_query(with_store):
    with_store(FakeStore())
    response = await api.search_import(
        FakeRequest(body={"query": 5, "results": []})
    )
    assert response.status_code >= 400


class FakeProvider:
    def __init__(self, name, clear_result=0):
        self.name = name
        self.fetcher = type(
            "Fetcher", (), {"cache": type("Cache", (), {"clear": lambda _self, prefix=None: clear_result})()}
        )()


class FakeSplitStore:
    def __init__(self, ids=None, error=None):
        self.ids = ids or []
        self.error = error
        self.calls = []

    async def split_search(self, search_id, size):
        self.calls.append((search_id, size))
        if self.error:
            raise self.error
        return self.ids


@pytest.fixture
def with_providers(monkeypatch):
    def _install(providers):
        monkeypatch.setitem(api._state, "providers", providers)
        return providers

    return _install


async def test_quota_route_reports_all_providers(with_providers):
    with_providers([FakeProvider("arxiv"), FakeProvider("scopus")])
    response = await api.quota(FakeRequest())

    assert response.status_code == 200
    sources = _body(response)["sources"]
    assert set(sources) == {"arxiv", "scopus"}
    assert sources["arxiv"]["source"] == "arxiv"


async def test_import_route_detects_ris():
    content = "TY  - JOUR\nTI  - Graphene\nAU  - Novoselov, K\nPY  - 2004\nER  - \n"
    response = await api.import_external(FakeRequest(body={"content": content}))

    assert response.status_code == 200
    payload = _body(response)
    assert payload["format"] == "ris"
    assert payload["count"] == 1
    assert payload["papers"][0]["title"] == "Graphene"


async def test_import_route_rejects_non_string_content():
    response = await api.import_external(FakeRequest(body={"content": 5}))
    assert response.status_code >= 400


async def test_import_route_rejects_empty_content():
    response = await api.import_external(FakeRequest(body={"content": "   "}))
    assert response.status_code >= 400


async def test_cache_clear_route_clears_ttl_and_store(with_providers, with_store):
    with_providers([FakeProvider("arxiv", clear_result=4)])
    store = with_store(FakeStore())
    store.clear = lambda prefix=None: _async_value(3)

    response = await api.cache_clear(FakeRequest(body={"prefix": "search"}))

    assert response.status_code == 200
    assert _body(response)["cleared"] == 7


async def _async_value(value):
    return value


async def test_search_split_route_returns_ids(with_store):
    store = with_store(FakeSplitStore(ids=["a", "b"]))
    req = FakeRequest(body={"size": 2}, path_params={"search_id": "abc"})
    response = await api.search_split(req)

    assert response.status_code == 200
    assert _body(response) == {"ids": ["a", "b"], "count": 2}
    assert store.calls == [("abc", 2)]


async def test_search_split_route_without_store_errors(monkeypatch):
    monkeypatch.setitem(api._state, "store", None)
    response = await api.search_split(FakeRequest(body={"size": 2}, path_params={"search_id": "x"}))
    assert response.status_code >= 400


async def test_search_split_route_rejects_bad_size(with_store):
    with_store(FakeSplitStore(ids=["a"]))
    response = await api.search_split(FakeRequest(body={"size": "nope"}, path_params={"search_id": "x"}))
    assert response.status_code >= 400


async def test_search_delete_route_reports_deleted(with_store):
    store = with_store(FakeStore())
    store.deleted = None

    async def delete_search(search_id):
        store.deleted = search_id
        return True

    store.delete_search = delete_search

    response = await api.search_delete(FakeRequest(path_params={"search_id": "abc"}))

    assert response.status_code == 200
    assert store.deleted == "abc"
    assert _body(response) == {"id": "abc", "deleted": True}


async def test_search_delete_route_404_when_missing(with_store):
    store = with_store(FakeStore())

    async def delete_search(search_id):
        return False

    store.delete_search = delete_search

    response = await api.search_delete(FakeRequest(path_params={"search_id": "nope"}))

    assert response.status_code == 404
    assert _body(response)["error"] == "Search not found."


async def test_search_delete_route_without_store_errors(monkeypatch):
    monkeypatch.setitem(api._state, "store", None)

    response = await api.search_delete(FakeRequest(path_params={"search_id": "abc"}))

    assert response.status_code >= 400


async def test_metrics_report_route_renders_text(monkeypatch):
    async def fake_payload(_request):
        return {"papers": 2, "total_citations": 10, "metrics": {"h_index": 3}}

    monkeypatch.setattr(api.discovery_routes, "_metrics_payload", fake_payload)
    req = FakeRequest(query_params={"mode": "basic"})
    response = await api.metrics_report(req)

    assert response.status_code == 200
    assert b"Search Report" in response.body


async def test_citations_save_flag_records_history(monkeypatch, with_providers):
    recorded = {}

    async def fake_citations(providers, identifier, limit=20, sources=None):
        return {"results": [{"title": "C"}], "errors": {}}

    async def fake_remember(**kwargs):
        recorded.update(kwargs)

    monkeypatch.setattr(api.aggregator, "get_citations", fake_citations)
    monkeypatch.setattr(api.history, "_remember", fake_remember)
    with_providers([FakeProvider("opencitations")])

    req = FakeRequest(query_params={"identifier": "10.1/a", "save": "true"})
    response = await api.citations(req)

    assert response.status_code == 200
    assert recorded["query"] == "citations:10.1/a"


async def test_citations_route_passes_source_to_aggregator(monkeypatch, with_providers):
    seen = {}

    async def fake_get_citations(providers, identifier, limit=20, sources=None):
        seen["identifier"] = identifier
        seen["sources"] = sources
        return {"results": [], "errors": {}, "counts": {}}

    monkeypatch.setattr(api.aggregator, "get_citations", fake_get_citations)
    with_providers([FakeProvider("scopus")])

    req = FakeRequest(query_params={"identifier": "6420654", "source": "scopus"})
    response = await api.citations(req)

    assert response.status_code == 200
    assert seen == {"identifier": "6420654", "sources": ["scopus"]}


async def test_search_route_passes_topic_filter_to_aggregator(
    monkeypatch, with_providers
):
    seen = {}

    async def fake_search(providers, query, **kwargs):
        seen.update(kwargs)
        return {"results": [], "errors": {}, "counts": {}}

    monkeypatch.setattr(api.aggregator, "search_all", fake_search)
    with_providers([FakeProvider("openalex")])

    req = FakeRequest(query_params={"query": "q", "topic": "machine learning"})
    response = await api.search(req)

    assert response.status_code == 200
    assert seen["topic"] == "machine learning"


async def test_search_route_fingerprint_includes_topic(monkeypatch, with_providers):
    seen = []

    async def fake_search(providers, query, **kwargs):
        return {"results": [], "errors": {}, "counts": {}}

    async def fake_remember(**kwargs):
        seen.append(kwargs["fingerprint"])

    monkeypatch.setattr(api.aggregator, "search_all", fake_search)
    monkeypatch.setattr(api.history, "_remember", fake_remember)
    with_providers([FakeProvider("openalex")])

    await api.search(FakeRequest(query_params={"query": "q"}))
    await api.search(FakeRequest(query_params={"query": "q", "topic": "databases"}))

    assert seen[0] != seen[1]


async def test_search_route_records_history_with_a_fingerprint(
    monkeypatch, with_providers
):
    recorded = {}

    async def fake_search(providers, query, **kwargs):
        return {"results": [{"title": "A"}], "errors": {}, "counts": {}}

    async def fake_remember(**kwargs):
        recorded.update(kwargs)

    monkeypatch.setattr(api.aggregator, "search_all", fake_search)
    monkeypatch.setattr(api.history, "_remember", fake_remember)
    with_providers([FakeProvider("garuda")])

    req = FakeRequest(query_params={"query": "machine learning", "source": "garuda"})
    response = await api.search(req)

    assert response.status_code == 200
    expected = api.history.search_fingerprint(
        query="machine learning", sources=["garuda"]
    )
    assert recorded["fingerprint"] == expected
    assert recorded["query"] == "machine learning"
    assert recorded["sources"] == ["garuda"]


async def test_search_route_passes_author_and_venue_to_aggregator(
    monkeypatch, with_providers
):
    seen = {}

    async def fake_search(providers, query, **kwargs):
        seen.update(kwargs)
        return {"results": [], "errors": {}, "counts": {}}

    monkeypatch.setattr(api.aggregator, "search_all", fake_search)
    with_providers([FakeProvider("scopus")])

    req = FakeRequest(
        query_params={"query": "q", "author": "Smith J", "venue": "ICIS"}
    )
    response = await api.search(req)

    assert response.status_code == 200
    assert seen["author"] == "Smith J"
    assert seen["venue"] == "ICIS"


async def test_search_route_parses_conditions_json(monkeypatch, with_providers):
    seen = {}

    async def fake_search(providers, query, **kwargs):
        seen.update(kwargs)
        return {"results": [], "errors": {}, "counts": {}}

    monkeypatch.setattr(api.aggregator, "search_all", fake_search)
    with_providers([FakeProvider("scopus")])

    req = FakeRequest(
        query_params={
            "query": "",
            "conditions": '[{"field":"title","value":"data quality","operator":"AND"}]',
        }
    )
    response = await api.search(req)

    assert response.status_code == 200
    assert seen["conditions"] == [
        {"field": "title", "value": "data quality", "operator": "AND"}
    ]


async def test_search_route_rejects_invalid_conditions_json(
    monkeypatch, with_providers
):
    async def fake_search(providers, query, **kwargs):
        return {"results": [], "errors": {}, "counts": {}}

    monkeypatch.setattr(api.aggregator, "search_all", fake_search)
    with_providers([FakeProvider("scopus")])

    req = FakeRequest(query_params={"query": "q", "conditions": "not-json"})
    response = await api.search(req)

    assert response.status_code >= 400


async def test_health_exposes_supports_filters(with_providers):
    class FilterProvider(FakeProvider):
        supports_filters = frozenset({"author", "venue"})

    with_providers([FilterProvider("scopus")])
    response = await api.health(FakeRequest())

    assert response.status_code == 200
    caps = _body(response)["capabilities"]["scopus"]
    assert sorted(caps["filters"]) == ["author", "venue"]


async def test_search_route_fingerprint_differs_for_different_filters(
    monkeypatch, with_providers
):
    seen = []

    async def fake_search(providers, query, **kwargs):
        return {"results": [], "errors": {}, "counts": {}}

    async def fake_remember(**kwargs):
        seen.append(kwargs["fingerprint"])

    monkeypatch.setattr(api.aggregator, "search_all", fake_search)
    monkeypatch.setattr(api.history, "_remember", fake_remember)
    with_providers([FakeProvider("garuda")])

    await api.search(FakeRequest(query_params={"query": "ml", "source": "garuda"}))
    await api.search(
        FakeRequest(query_params={"query": "ml", "source": "garuda", "year_from": "2020"})
    )

    assert len(seen) == 2
    assert seen[0] != seen[1]


async def test_related_route_passes_source_to_aggregator(monkeypatch, with_providers):
    seen = {}

    async def fake_get_related(providers, identifier, limit=20, sources=None):
        seen["identifier"] = identifier
        seen["sources"] = sources
        return {"results": [], "errors": {}, "counts": {}}

    monkeypatch.setattr(api.aggregator, "get_related", fake_get_related)
    with_providers([FakeProvider("openalex")])

    req = FakeRequest(query_params={"identifier": "W123", "source": "openalex"})
    response = await api.related(req)

    assert response.status_code == 200
    assert seen == {"identifier": "W123", "sources": ["openalex"]}


async def test_paper_route_passes_source_to_aggregator(monkeypatch, with_providers):
    seen = {}

    async def fake_get_paper(providers, identifier, sources=None):
        seen["identifier"] = identifier
        seen["sources"] = sources
        return {"paper": {"title": "Garuda record"}, "errors": {}}

    monkeypatch.setattr(api.aggregator, "get_paper", fake_get_paper)
    with_providers([FakeProvider("garuda")])

    req = FakeRequest(query_params={"identifier": "6420654", "source": "garuda"})
    response = await api.paper(req)

    assert response.status_code == 200
    assert seen == {"identifier": "6420654", "sources": ["garuda"]}


async def test_identify_route_resolves_uploaded_pdf(monkeypatch):
    monkeypatch.setattr(
        api.recognize_routes,
        "extract_pdf_text_from_bytes",
        lambda data: "doi 10.1/x",
    )

    async def fake_get_paper(providers, identifier, sources=None):
        return {"paper": {"title": "Resolved"}, "errors": {}}

    monkeypatch.setattr(api.aggregator, "get_paper", fake_get_paper)

    req = FakeRequest(body={"pdf_base64": base64.b64encode(b"%PDF-1.4").decode()})
    response = await api.identify(req)

    assert response.status_code == 200
    payload = _body(response)
    assert payload["identifier"] == "10.1/x"
    assert payload["paper"]["title"] == "Resolved"


async def test_identify_route_rejects_missing_pdf_base64():
    response = await api.identify(FakeRequest(body={}))

    assert response.status_code == 400
    assert "pdf_base64" in _body(response)["error"]


async def test_identify_route_rejects_invalid_base64():
    response = await api.identify(FakeRequest(body={"pdf_base64": "not base64!!"}))

    assert response.status_code == 400
    assert "base64" in _body(response)["error"]
