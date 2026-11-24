import httpx

from josc.providers.arxiv import ArxivProvider
from josc.providers.openalex import OpenAlexProvider


def _work(work_id, doi, title):
    return {
        "id": f"https://openalex.org/{work_id}",
        "doi": doi,
        "title": title,
        "publication_year": 2020,
        "authorships": [],
    }


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_openalex_get_many_uses_one_filtered_request():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["filter"] = request.url.params.get("filter")
        return httpx.Response(
            200,
            json={
                "results": [
                    _work("W1", "https://doi.org/10.1/a", "A"),
                    _work("W2", "https://doi.org/10.1/b", "B"),
                ]
            },
        )

    client = _client(handler)
    provider = OpenAlexProvider(client)
    try:
        papers = await provider.get_many(["10.1/a", "10.1/b"])
        assert [p.doi for p in papers] == ["10.1/a", "10.1/b"]
        assert seen["filter"] == "doi:10.1/a|10.1/b"
        assert seen["url"].startswith("https://api.openalex.org/works")
    finally:
        await client.aclose()


async def test_openalex_get_many_routes_w_ids_by_openalex_filter():
    seen = {}

    def handler(request):
        seen["filter"] = request.url.params.get("filter")
        return httpx.Response(200, json={"results": [_work("W1", None, "A")]})

    client = _client(handler)
    provider = OpenAlexProvider(client)
    try:
        papers = await provider.get_many(["W1"])
        assert len(papers) == 1
        assert seen["filter"] == "openalex:W1"
    finally:
        await client.aclose()


async def test_openalex_get_many_returns_empty_for_no_usable_ids():
    def handler(request):
        raise AssertionError("no request should be made for unusable ids")

    client = _client(handler)
    provider = OpenAlexProvider(client)
    try:
        assert await provider.get_many(["not-an-id"]) == []
    finally:
        await client.aclose()


def _atom_entry(raw_id, title):
    return f"""<entry xmlns="http://www.w3.org/2005/Atom">
      <id>http://arxiv.org/abs/{raw_id}</id><title>{title}</title>
      <summary>abstract</summary><published>2020-01-01T00:00:00Z</published>
      <author><name>Author</name></author>
      <link title="pdf" href="https://arxiv.org/pdf/{raw_id}" type="application/pdf"/>
    </entry>"""


async def test_arxiv_get_many_uses_id_list_batch():
    seen = {}

    def handler(request):
        seen["id_list"] = request.url.params.get("id_list")
        feed = (
            "<feed xmlns='http://www.w3.org/2005/Atom'>"
            + "".join(
                _atom_entry(aid, f"Title {aid}") for aid in seen["id_list"].split(",")
            )
            + "</feed>"
        )
        return httpx.Response(200, text=feed)

    client = _client(handler)
    provider = ArxivProvider(client)
    try:
        papers = await provider.get_many(["2401.12345", "arxiv:2401.00001"])
        assert seen["id_list"] == "2401.12345,2401.00001"
        assert [p.ids.get("arxiv") for p in papers] == ["2401.12345", "2401.00001"]
    finally:
        await client.aclose()


async def test_openalex_get_many_chunks_long_id_lists():
    filters = []

    def handler(request):
        value = request.url.params.get("filter")
        filters.append(value)
        ids = value[len("openalex:"):].split("|")
        return httpx.Response(200, json={"results": [_work(i, None, i) for i in ids]})

    client = _client(handler)
    provider = OpenAlexProvider(client)
    try:
        ids = [f"W{n}" for n in range(1, 121)]
        papers = await provider.get_many(ids)
        assert len(papers) == 120
        assert len(filters) == 3
        assert all(f.count("openalex:") == 1 for f in filters)
    finally:
        await client.aclose()


def test_openalex_to_paper_reads_countries_and_references():
    paper = OpenAlexProvider._to_paper({
        "id": "https://openalex.org/W9",
        "title": "T",
        "authorships": [
            {"author": {"display_name": "A"}, "countries": ["id"],
             "institutions": [{"display_name": "UI", "country_code": "ID"}]},
            {"author": {"display_name": "B"}, "countries": [],
             "institutions": [{"display_name": "MIT", "country_code": "US"}]},
        ],
        "referenced_works": ["https://openalex.org/W1", "https://openalex.org/W2"],
    })
    assert paper.countries == ["ID", "US"]
    assert paper.references == ["https://openalex.org/W1", "https://openalex.org/W2"]
