import json
from pathlib import Path

import httpx

from josc.providers.opencitations import OpenCitationsProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _payload(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _router(index=None, meta=None, crossref=None):
    """Serve each OpenCitations/Crossref endpoint from its own fixture."""
    calls = {"index": [], "meta": [], "crossref": []}

    def handler(request):
        url = str(request.url)
        if "api.opencitations.net/index" in url:
            calls["index"].append(url)
            return httpx.Response(200, json=index if index is not None else [])
        if "api.opencitations.net/meta" in url:
            calls["meta"].append(url)
            return httpx.Response(200, json=meta if meta is not None else [])
        if "api.crossref.org" in url:
            calls["crossref"].append(url)
            return httpx.Response(
                200, json=crossref if crossref is not None else {"message": {"items": []}}
            )
        return httpx.Response(404, json={})

    return handler, calls


async def test_references_falls_back_to_crossref_for_unmatched_metadata():
    index = _payload("opencitations_index.json")
    handler, calls = _router(
        index=index,
        meta=_payload("opencitations_meta.json"),
        crossref=_payload("opencitations_crossref.json"),
    )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenCitationsProvider(client)
    try:
        papers = await provider.references("https://doi.org/10.1186/1756-8722-6-59", 10)
    finally:
        await client.aclose()

    assert len(papers) == 1
    paper = papers[0]
    assert paper.doi == "10.1124/dmd.111.040840"
    assert paper.title == "Significant Species Difference In Amide Hydrolysis Of GDC-0834"
    assert paper.authors == ["Lichuan Liu", "Jason S. Halladay"]
    assert paper.year == 2011
    assert paper.venue == "Drug Metabolism and Disposition"
    assert paper.citation_count == 42
    assert paper.sources == ["crossref"]

    assert calls["index"] == [
        "https://api.opencitations.net/index/v2/references/doi:10.1186/1756-8722-6-59"
    ]
    assert calls["meta"], "meta batch should be attempted before the Crossref fallback"
    assert calls["crossref"], "unmatched DOI should be resolved through Crossref"


async def test_citations_maps_meta_record_to_paper():
    index = _payload("opencitations_index.json")
    handler, calls = _router(index=index, meta=_payload("opencitations_meta.json"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenCitationsProvider(client)
    try:
        papers = await provider.citations("doi:10.1124/dmd.111.040840", 10)
    finally:
        await client.aclose()

    assert len(papers) == 1
    paper = papers[0]
    assert paper.doi == "10.1186/1756-8722-6-59"
    assert paper.title == "A trial of something interesting"
    assert paper.authors == ["Doe, Jane", "Roe, Richard"]
    assert paper.year == 2013
    assert paper.venue == "Journal of Hematology & Oncology"
    assert paper.type == "journal article"
    assert paper.sources == ["opencitations"]
    assert paper.ids["opencitations"] == "omid:br/06190834283"
    assert paper.ids["openalex"] == "W2120377900"
    assert calls["index"] == [
        "https://api.opencitations.net/index/v2/citations/doi:10.1124/dmd.111.040840"
    ]
    assert not calls["crossref"], "a fully resolved Meta record needs no Crossref fallback"


async def test_empty_index_result_returns_no_papers():
    handler, calls = _router(index=[])

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenCitationsProvider(client)
    try:
        assert await provider.references("10.1186/1756-8722-6-59", 10) == []
    finally:
        await client.aclose()

    assert calls["meta"] == []
    assert calls["crossref"] == []


async def test_unsupported_identifier_scheme_makes_no_request():
    handler, calls = _router()

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenCitationsProvider(client)
    try:
        assert await provider.references("openalex:W2120377900", 10) == []
        assert await provider.citations("not-an-identifier", 10) == []
    finally:
        await client.aclose()

    assert calls["index"] == []


async def test_limit_truncates_records_before_resolution():
    index = _payload("opencitations_index.json") * 3
    handler, calls = _router(index=index, meta=_payload("opencitations_meta.json"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenCitationsProvider(client)
    try:
        papers = await provider.citations("doi:10.1124/dmd.111.040840", 1)
    finally:
        await client.aclose()

    assert len(papers) == 1
    assert calls["meta"][0].count("__") == 3


def test_split_pids_parses_space_separated_string():
    pids = OpenCitationsProvider._split_pids(
        "omid:br/06190834283 doi:10.1186/1756-8722-6-59 pmid:23958373 openalex:W2120377900"
    )
    assert pids == {
        "omid": "br/06190834283",
        "doi": "10.1186/1756-8722-6-59",
        "pmid": "23958373",
        "openalex": "W2120377900",
    }


def test_pid_normalizes_bare_doi_and_omid():
    assert (
        OpenCitationsProvider._pid("https://doi.org/10.1186/1756-8722-6-59")
        == "doi:10.1186/1756-8722-6-59"
    )
    assert OpenCitationsProvider._pid("omid:br/06101389277") == "omid:br/06101389277"
    assert OpenCitationsProvider._pid("not-a-doi") is None
