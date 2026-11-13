import json
from pathlib import Path

import httpx

from josc.providers.crossref import CrossrefProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"


async def test_search_maps_items_to_paper(monkeypatch):
    payload = json.loads((FIXTURES / "crossref_search.json").read_text(encoding="utf-8"))

    def handler(request):
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CrossrefProvider(client)
    try:
        papers = await provider.search("long short-term memory", 5)
        assert len(papers) == 1
        p = papers[0]
        assert p.doi == "10.1162/neco.1997.9.8.1735"
        assert p.title == "Long Short-Term Memory"
        assert p.authors == ["Sepp Hochreiter", "Jürgen Schmidhuber"]
        assert p.venue == "Neural Computation"
        assert p.year == 1997
        assert p.citation_count == 42000
        assert p.abstract == "We propose LSTM."
        assert p.sources == ["crossref"]
        assert p.ids["crossref"] == "10.1162/neco.1997.9.8.1735"
    finally:
        await client.aclose()


async def test_search_sends_offset_for_pagination():
    captured = {}

    def handler(request):
        captured["offset"] = request.url.params.get("offset")
        return httpx.Response(200, json={"message": {"items": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CrossrefProvider(client)
    try:
        await provider.search("lstm", 10, offset=15)
        assert captured["offset"] == "15"
    finally:
        await client.aclose()


async def test_search_author_sends_query_author():
    captured = {}

    def handler(request):
        captured["query.author"] = request.url.params.get("query.author")
        return httpx.Response(200, json={"message": {"items": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CrossrefProvider(client)
    try:
        await provider.search_author("Vaswani", 5)
        assert captured["query.author"] == "Vaswani"
    finally:
        await client.aclose()


async def test_search_by_doi_drops_text_query():
    # Crossref ANDs ``query`` into the relevance ranking, so a doi filter plus
    # a text query returns zero rows for a DOI that does exist. The DOI alone
    # must be sent, with no ``query`` parameter at all.
    captured = {}

    def handler(request):
        if request.url.path != "/works":
            # Record endpoint for the fallback: this DOI is unknown, so the
            # original empty search result stands.
            return httpx.Response(404, json={"status": "error"})
        captured["query"] = request.url.params.get("query")
        captured["filter"] = request.url.params.get("filter")
        return httpx.Response(200, json={"message": {"items": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CrossrefProvider(client)
    try:
        await provider.search("some long natural language title", 5, doi="10.1234/abc")
        assert captured["query"] is None
        assert captured["filter"] == "doi:10.1234/abc"
    finally:
        await client.aclose()


async def test_search_author_by_doi_drops_author_query():
    captured = {}

    def handler(request):
        if request.url.path != "/works":
            return httpx.Response(404, json={"status": "error"})
        captured["query.author"] = request.url.params.get("query.author")
        captured["filter"] = request.url.params.get("filter")
        return httpx.Response(200, json={"message": {"items": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CrossrefProvider(client)
    try:
        await provider.search_author("Vaswani", 5, doi="10.1234/abc")
        assert captured["query.author"] is None
        assert captured["filter"] == "doi:10.1234/abc"
    finally:
        await client.aclose()


def _record_payload(doi="10.1234/abc", title="A Recovered Record", year=2021):
    return {
        "message": {
            "DOI": doi,
            "title": [title],
            "container-title": ["Journal of Testing"],
            "issued": {"date-parts": [[year]]},
            "author": [{"given": "Ada", "family": "Lovelace"}],
            "type": "journal-article",
        }
    }


async def test_search_by_doi_falls_back_to_record_endpoint():
    # The search index can lag behind /works/<doi>; an empty filter result is
    # not proof the DOI is absent.
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/works":
            return httpx.Response(200, json={"message": {"items": []}})
        return httpx.Response(200, json=_record_payload())

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CrossrefProvider(client)
    try:
        papers = await provider.search("anything", 5, doi="10.1234/abc")
        assert calls == ["/works", "/works/10.1234/abc"]
        assert len(papers) == 1
        assert papers[0].doi == "10.1234/abc"
        assert papers[0].title == "A Recovered Record"
        assert papers[0].year == 2021
    finally:
        await client.aclose()


async def test_search_author_by_doi_falls_back_to_record_endpoint():
    def handler(request):
        if request.url.path == "/works":
            return httpx.Response(200, json={"message": {"items": []}})
        return httpx.Response(200, json=_record_payload())

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CrossrefProvider(client)
    try:
        papers = await provider.search_author("Lovelace", 5, doi="10.1234/abc")
        assert len(papers) == 1
        assert papers[0].title == "A Recovered Record"
    finally:
        await client.aclose()


async def test_search_by_doi_does_not_fall_back_when_paginating():
    # A fallback on a later page would re-return the same single record and
    # corrupt pagination semantics.
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"message": {"items": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CrossrefProvider(client)
    try:
        papers = await provider.search("anything", 5, doi="10.1234/abc", offset=5)
        assert papers == []
        assert calls == ["/works"]
    finally:
        await client.aclose()


async def test_search_by_doi_fallback_honors_year_bounds():
    def handler(request):
        if request.url.path == "/works":
            return httpx.Response(200, json={"message": {"items": []}})
        return httpx.Response(200, json=_record_payload(year=2015))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CrossrefProvider(client)
    try:
        papers = await provider.search("anything", 5, doi="10.1234/abc", year_from=2020)
        assert papers == []
    finally:
        await client.aclose()


async def test_search_sends_native_year_filter():
    captured = {}

    def handler(request):
        captured["filter"] = request.url.params.get("filter")
        return httpx.Response(200, json={"message": {"items": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CrossrefProvider(client)
    try:
        await provider.search("lstm", 5, year_from=2018, year_to=2020)
        assert captured["filter"] == "from-pub-date:2018-01-01,until-pub-date:2020-12-31"
    finally:
        await client.aclose()


async def test_search_omits_filter_when_no_year_bounds():
    captured = {"missing": True}

    def handler(request):
        if request.url.params.get("filter") is not None:
            captured["missing"] = False
        return httpx.Response(200, json={"message": {"items": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CrossrefProvider(client)
    try:
        await provider.search("lstm", 5)
        assert captured["missing"] is True
    finally:
        await client.aclose()


async def test_search_author_also_honors_year_filter():
    captured = {}

    def handler(request):
        captured["filter"] = request.url.params.get("filter")
        return httpx.Response(200, json={"message": {"items": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CrossrefProvider(client)
    try:
        await provider.search_author("Vaswani", 5, year_from=2017)
        assert captured["filter"] == "from-pub-date:2017-01-01"
    finally:
        await client.aclose()


async def test_search_parses_retraction_and_subject_fields_already_in_payload():
    # Crossref ships ``update-to`` (retraction notices), ``subject``, ``license``
    # and ``funder``; none of them used to reach the Paper model.
    payload = {
        "message": {
            "items": [
                {
                    "DOI": "10.1/retracted",
                    "type": "journal-article",
                    "title": ["A retracted study"],
                    "subject": ["Computer Science", "Information Systems"],
                    "license": [{"URL": "https://creativecommons.org/licenses/by/4.0/"}],
                    "funder": [{"name": "National Science Foundation"}],
                    "update-to": [
                        {
                            "type": "retraction",
                            "DOI": "10.1/retraction-notice",
                            "label": "Retraction",
                        }
                    ],
                }
            ]
        }
    }

    def handler(request):
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CrossrefProvider(client)
    try:
        paper = (await provider.search("retracted", 5))[0]
        assert paper.is_retracted is True
        assert paper.topics == ["Computer Science", "Information Systems"]
        assert paper.license == "https://creativecommons.org/licenses/by/4.0/"
        assert paper.funders == ["National Science Foundation"]
    finally:
        await client.aclose()


async def test_search_keeps_subtitle_publisher_and_approved_date():
    # BSI standards carry only "Data quality" in ``title``; the part name lives
    # in ``subtitle`` and the only date is ``approved``/``created``. Without
    # these fields four different standards render as identical bare rows.
    payload = {
        "message": {
            "items": [
                {
                    "DOI": "10.3403/30431817",
                    "type": "standard",
                    "title": ["Data quality"],
                    "subtitle": ["Part 82: Data quality assessment: Creating data rules"],
                    "publisher": "BSI British Standards",
                    "issued": {"date-parts": [[None]]},
                    "approved": {"date-parts": [[2022, 7, 31]]},
                    "created": {"date-parts": [[2022, 7, 11]]},
                }
            ]
        }
    }

    def handler(request):
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CrossrefProvider(client)
    try:
        paper = (await provider.search("data quality", 5))[0]
        assert paper.title == (
            "Data quality: Part 82: Data quality assessment: Creating data rules"
        )
        assert paper.venue == "BSI British Standards"
        assert paper.year == 2022
    finally:
        await client.aclose()


async def test_search_drops_container_records_without_title():
    # Crossref returns journal-issue records with ``title: []`` for broad
    # queries; they are not articles and must not reach the result list.
    def handler(request):
        return httpx.Response(
            200,
            json={
                "message": {
                    "items": [
                        {"DOI": "10.1/issue", "type": "journal-issue", "title": []},
                        {"DOI": "10.1/proc", "type": "proceedings", "title": []},
                        {
                            "DOI": "10.1/article",
                            "type": "journal-article",
                            "title": ["A real paper"],
                        },
                    ]
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CrossrefProvider(client)
    try:
        papers = await provider.search("data and information quality", 5)
        assert [p.doi for p in papers] == ["10.1/article"]
    finally:
        await client.aclose()