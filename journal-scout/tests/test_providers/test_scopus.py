import json
from pathlib import Path
from urllib.parse import unquote

import httpx

from josc.http import Fetcher
from josc.models import ProviderError
from josc.providers.scopus import ScopusProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"


async def test_search_maps_entries_to_paper(monkeypatch):
    payload = json.loads((FIXTURES / "scopus_search.json").read_text(encoding="utf-8"))

    def handler(request):
        assert "X-ELS-APIKey" in request.headers
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        papers = await provider.search("intrusion detection", 5)
        assert len(papers) == 1
        p = papers[0]
        assert p.doi == "10.1109/access.2023.1234567"
        assert p.title == "Deep Learning for Network Intrusion Detection"
        assert p.year == 2023
        assert p.citation_count == 42
        assert p.venue == "IEEE Access"
        assert p.sources == ["scopus"]
        assert p.ids["scopus"] == "SCOPUS_ID:85012345678"
    finally:
        await client.aclose()


async def test_search_parses_open_access_and_author_count():
    # Scopus search entries already carry ``openaccess`` and ``author-count``;
    # they were ignored, so the UI could not show OA status for Scopus hits.
    payload = {
        "search-results": {
            "entry": [
                {
                    "dc:identifier": "SCOPUS_ID:1",
                    "dc:title": "Paper",
                    "prism:doi": "10.1/x",
                    "openaccess": "1",
                    "openaccessFlag": True,
                    "author-count": "3",
                    "subtypeDescription": "Article",
                }
            ]
        }
    }

    def handler(request):
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        paper = (await provider.search("paper", 5))[0]
        assert paper.is_open_access is True
    finally:
        await client.aclose()


async def test_tech_only_adds_subjarea():
    captured = {}

    def handler(request):
        captured["query"] = request.url.params.get("query")
        return httpx.Response(200, json={"search-results": {"entry": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        await provider.search("networks", 5, tech_only=True)
        assert "SUBJAREA(COMP)" in captured["query"]
    finally:
        await client.aclose()


def test_scopus_provider_has_detail_helpers():
    from josc.providers.scopus import ScopusProvider
    assert hasattr(ScopusProvider, "get_author")
    assert hasattr(ScopusProvider, "get_quota_status")


async def test_search_sends_start_for_pagination():
    captured = {}

    def handler(request):
        captured["start"] = request.url.params.get("start")
        return httpx.Response(200, json={"search-results": {"entry": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        await provider.search("networks", 10, offset=20)
        assert captured["start"] == "20"
    finally:
        await client.aclose()


async def test_abstract_endpoint_collects_all_authors():
    # The abstracts-retrieval endpoint exposes a full author array; every
    # co-author must survive, not just the first (dc:creator).
    def handler(request):
        return httpx.Response(
            200,
            json={
                "abstracts-retrieval-response": {
                    "coredata": {
                        "dc:title": "X",
                        "prism:doi": "10.1/x",
                        "author": [
                            {"authname": "Sepp Hochreiter"},
                            {"authname": "Jürgen Schmidhuber"},
                        ],
                    }
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        paper = await provider.get("10.1/x")
        assert paper.authors == ["Sepp Hochreiter", "Jürgen Schmidhuber"]
    finally:
        await client.aclose()


async def test_abstract_endpoint_flattens_dict_dc_creator():
    # Real Elsevier abstract retrieval nests the author list inside a *dict*
    # dc:creator with ce:-prefixed keys; those names must be flattened, not
    # leaked as a raw dict.
    def handler(request):
        return httpx.Response(
            200,
            json={
                "abstracts-retrieval-response": {
                    "coredata": {
                        "dc:title": "X",
                        "prism:doi": "10.1/x",
                        "dc:creator": {
                            "author": [
                                {
                                    "ce:given-name": "Zaizhang",
                                    "ce:surname": "Wu",
                                    "@auid": "60648216000",
                                    "preferred-name": {
                                        "ce:given-name": "Zaizhang",
                                        "ce:surname": "Wu",
                                    },
                                },
                                {"ce:given-name": "Mei", "ce:surname": "Chen"},
                            ]
                        },
                    }
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        paper = await provider.get("10.1/x")
        assert paper.authors == ["Zaizhang Wu", "Mei Chen"]
    finally:
        await client.aclose()


async def test_get_degrades_to_default_view_when_full_is_unauthorized():
    # ``view=FULL`` carries the abstract but a key without that entitlement
    # answers 401; get() must fall back to the default view, not error out.
    views = []

    def handler(request):
        views.append(request.url.params.get("view"))
        if request.url.params.get("view") == "FULL":
            return httpx.Response(
                401,
                json={"service-error": {"status": {"statusCode": "AUTHORIZATION_ERROR"}}},
            )
        return httpx.Response(
            200,
            json={
                "abstracts-retrieval-response": {
                    "coredata": {
                        "dc:title": "Fallback title",
                        "prism:doi": "10.1/x",
                        "dc:creator": "Ada Lovelace",
                    }
                }
            },
        )

    # The real Fetcher is what raises ProviderError on 401 (a raw client
    # would just return the error body), so drive the provider through it.
    fetcher = Fetcher(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), cache=None
    )
    provider = ScopusProvider(fetcher, {"api_key": "test-key"})
    try:
        paper = await provider.get("10.1/x")
        assert views == ["FULL", None]
        assert paper.title == "Fallback title"
        assert paper.authors == ["Ada Lovelace"]
    finally:
        await fetcher.close()


async def test_get_routes_doi_to_doi_endpoint():
    captured = {}

    def handler(request):
        captured["path"] = unquote(request.url.path)
        return httpx.Response(
            200,
            json={
                "abstracts-retrieval-response": {
                    "coredata": {"dc:title": "X", "prism:doi": "10.1/x"}
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        paper = await provider.get("10.1145/3292500.3330701")
        assert "/abstract/doi/" in captured["path"]
        assert "3292500.3330701" in captured["path"]
        assert paper is not None
    finally:
        await client.aclose()


async def test_get_routes_scopus_id_to_scopus_id_endpoint():
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        return httpx.Response(200, json={"abstracts-retrieval-response": {"coredata": {}}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        await provider.get("SCOPUS_ID:85012345678")
        assert captured["path"].endswith("/abstract/scopus_id/85012345678")
    finally:
        await client.aclose()


async def test_get_returns_none_for_unsupported_identifier():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        assert await provider.get("2301.12345") is None
        assert calls == []
    finally:
        await client.aclose()


async def test_citations_resolves_doi_to_scopus_id_before_ref_query():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if "/abstract/doi/" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "abstracts-retrieval-response": {
                        "coredata": {"dc:identifier": "SCOPUS_ID:85099999999"}
                    }
                },
            )
        return httpx.Response(200, json={"search-results": {"entry": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        assert await provider.citations("10.1145/3292500.3330701", 5) == []
        # ``REF()`` only accepts the numeric id, so a DOI is resolved through
        # abstract retrieval first.
        assert "/abstract/doi/10.1145/3292500.3330701" in calls[0]
        assert "REF(85099999999)" in unquote(calls[1])
    finally:
        await client.aclose()


async def test_citations_returns_empty_when_doi_cannot_be_resolved():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json={"abstracts-retrieval-response": {"coredata": {}}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        assert await provider.citations("10.1145/3292500.3330701", 5) == []
        assert len(calls) == 1
        assert "/search/scopus" not in calls[0]
    finally:
        await client.aclose()


async def test_citations_uses_scopus_id_for_ref_query():
    captured = {}

    def handler(request):
        captured["query"] = request.url.params.get("query")
        return httpx.Response(200, json={"search-results": {"entry": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        await provider.citations("SCOPUS_ID:85012345678", 5)
        assert captured["query"] == "REF(85012345678)"
    finally:
        await client.aclose()


async def test_search_author_uses_auth_clause():
    captured = {}

    def handler(request):
        captured["query"] = request.url.params.get("query")
        return httpx.Response(200, json={"search-results": {"entry": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        await provider.search_author("Vaswani", 5)
        # Scopus has no ``AU()`` field; ``AUTH()`` is the author-name clause.
        assert captured["query"] == "AUTH(Vaswani)"
    finally:
        await client.aclose()


async def test_search_author_keeps_full_name_inside_auth_clause():
    captured = {}

    def handler(request):
        captured["query"] = request.url.params.get("query")
        return httpx.Response(200, json={"search-results": {"entry": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        await provider.search_author("Harzing, Anne-Wil", 5)
        assert captured["query"] == "AUTH(Harzing, Anne-Wil)"
    finally:
        await client.aclose()


async def test_references_reports_missing_ref_entitlement_clearly():
    # A key without the ``view=REF`` entitlement answers 401 with a raw
    # service-error body. The graph UI shows that string verbatim, so it has to
    # become an actionable sentence instead of an HTTP dump.
    def handler(request):
        return httpx.Response(
            401,
            json={
                "service-error": {
                    "status": {
                        "statusCode": "AUTHORIZATION_ERROR",
                        "statusText": "The requestor is not authorized to access "
                        "the requested view or fields of the resource",
                    }
                }
            },
        )

    fetcher = Fetcher(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), cache=None
    )
    provider = ScopusProvider(fetcher, {"api_key": "test-key"})
    try:
        try:
            await provider.references("10.1/x", 5)
        except ProviderError as exc:
            message = exc.message
        else:
            raise AssertionError("expected ProviderError")
        assert "view=REF" in message
        assert "entitlement" in message.lower()
        assert "service-error" not in message
        assert "AUTHORIZATION_ERROR" not in message
    finally:
        await fetcher.close()


async def test_references_stops_retrying_after_entitlement_failure():
    # A citation graph calls references() once per citing paper and once per
    # seed reference. Once the key is known to lack view=REF, every further
    # call must fail locally instead of burning the quota on a guaranteed 401.
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(
            401,
            json={"service-error": {"status": {"statusCode": "AUTHORIZATION_ERROR"}}},
        )

    fetcher = Fetcher(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), cache=None
    )
    provider = ScopusProvider(fetcher, {"api_key": "test-key"})
    try:
        for _ in range(3):
            try:
                await provider.references("10.1/x", 5)
            except ProviderError:
                pass
        assert len(calls) == 1
    finally:
        await fetcher.close()


async def test_search_paginates_in_chunks_of_25():
    # The API key's service level rejects count > 25, so a larger limit has
    # to be split into successive ``start`` windows.
    calls = []

    def handler(request):
        start = int(request.url.params.get("start") or 0)
        count = int(request.url.params.get("count") or 0)
        calls.append((start, count))
        entries = [
            {"dc:identifier": f"SCOPUS_ID:{start + i}", "dc:title": f"Paper {start + i}"}
            for i in range(count)
        ]
        return httpx.Response(200, json={"search-results": {"entry": entries}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        papers = await provider.search("networks", 60)
        assert calls == [(0, 25), (25, 25), (50, 10)]
        assert len(papers) == 60
    finally:
        await client.aclose()
