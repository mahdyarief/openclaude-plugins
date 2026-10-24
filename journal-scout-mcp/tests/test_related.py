"""Related-works routing and OpenAlex hydration.

Every provider is faked here -- no test in this module touches the network.
"""

import httpx

from josc.aggregator import get_related
from josc.models import Paper
from josc.providers.base import ProviderBase
from josc.providers.openalex import OpenAlexProvider

WORK = {
    "id": "https://openalex.org/W123",
    "related_works": [
        "https://openalex.org/W1",
        "https://openalex.org/W2",
        "https://openalex.org/W3",
    ],
}


def _work(work_id):
    return {"id": f"https://openalex.org/{work_id}", "title": work_id}


class RelatedProvider(ProviderBase):
    supports_search = False
    supports_related = True

    def __init__(self, name, doi):
        super().__init__(None)
        self.name = name
        self.doi = doi
        self.calls = []

    async def related(self, identifier, limit):
        self.calls.append((identifier, limit))
        return [Paper(doi=self.doi, title=f"Related by {self.name}", sources=[self.name])]


class NonRelatedProvider(ProviderBase):
    supports_search = False

    async def related(self, identifier, limit):
        raise AssertionError("provider without supports_related must not be called")


async def test_get_related_queries_only_capable_providers():
    first = RelatedProvider("scopus", "10.9/a")
    second = RelatedProvider("openalex", "10.9/b")
    inert = NonRelatedProvider(None)

    result = await get_related([first, second, inert], "10.1/main", limit=5)

    assert first.calls == [("10.1/main", 5)]
    assert second.calls == [("10.1/main", 5)]
    assert result["counts"] == {"scopus": 1, "openalex": 1}
    assert {paper["doi"] for paper in result["results"]} == {"10.9/a", "10.9/b"}
    assert result["errors"] == {}


async def test_provider_without_related_flag_is_never_called():
    result = await get_related([NonRelatedProvider(None)], "10.1/main")

    assert result == {"results": [], "errors": {}, "counts": {}}


async def test_openalex_related_hydrates_batched_filter():
    filters = []

    def handler(request):
        if request.url.path == "/works/W123":
            return httpx.Response(200, json=WORK)
        filters.append(request.url.params.get("filter"))
        return httpx.Response(200, json={"results": [_work("W1"), _work("W2"), _work("W3")]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        papers = await OpenAlexProvider(client).related("W123", 10)
    finally:
        await client.aclose()

    assert filters == ["openalex_id:W1|W2|W3"]
    assert [p.ids["openalex"] for p in papers] == [
        "https://openalex.org/W1",
        "https://openalex.org/W2",
        "https://openalex.org/W3",
    ]
    assert all(p.sources == ["openalex"] for p in papers)


async def test_openalex_related_respects_limit():
    seen = {}

    def handler(request):
        if request.url.path == "/works/W123":
            return httpx.Response(200, json=WORK)
        seen["filter"] = request.url.params.get("filter")
        seen["per-page"] = request.url.params.get("per-page")
        return httpx.Response(200, json={"results": [_work("W1"), _work("W2")]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        papers = await OpenAlexProvider(client).related("W123", 2)
    finally:
        await client.aclose()

    assert seen == {"filter": "openalex_id:W1|W2", "per-page": "2"}
    assert len(papers) == 2


async def test_openalex_related_missing_field_returns_empty():
    paths = []

    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={"id": "https://openalex.org/W123"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        papers = await OpenAlexProvider(client).related("W123", 10)
    finally:
        await client.aclose()

    assert papers == []
    assert paths == ["/works/W123"]


async def test_openalex_related_empty_list_returns_empty():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(
            200, json={"id": "https://openalex.org/W123", "related_works": []}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        papers = await OpenAlexProvider(client).related("W123", 10)
    finally:
        await client.aclose()

    assert papers == []
    assert calls == ["/works/W123"]
