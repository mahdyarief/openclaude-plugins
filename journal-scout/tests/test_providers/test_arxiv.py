from pathlib import Path

import httpx

from josc.providers.arxiv import ArxivProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"
ATOM = "{http://www.w3.org/2005/Atom}"


async def test_search_parses_atom_entry():
    xml = (FIXTURES / "arxiv_search.xml").read_text(encoding="utf-8")

    def handler(request):
        return httpx.Response(200, text=xml)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ArxivProvider(client)
    try:
        papers = await provider.search("attention is all you need", 5)
        assert len(papers) == 1
        p = papers[0]
        assert p.title == "Attention Is All You Need"
        assert p.authors == ["Ashish Vaswani", "Noam Shazeer"]
        assert p.year == 2017
        assert p.abstract.startswith("The dominant sequence transduction")
        assert p.pdf_url == "http://arxiv.org/pdf/1706.03762v5"
        assert p.sources == ["arxiv"]
        assert p.ids["arxiv"] == "1706.03762v5"
    finally:
        await client.aclose()


async def test_search_sends_sortby_submitteddate():
    captured = {}

    def handler(request):
        captured["sortBy"] = request.url.params.get("sortBy")
        return httpx.Response(200, text=(FIXTURES / "arxiv_search.xml").read_text(encoding="utf-8"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ArxivProvider(client)
    try:
        await provider.search("attention is all you need", 5)
        assert captured["sortBy"] == "submittedDate"
    finally:
        await client.aclose()


async def test_tech_only_adds_cs_categories_to_query():
    captured = {}

    def handler(request):
        captured["query"] = request.url.params.get("search_query")
        return httpx.Response(200, text=(FIXTURES / "arxiv_search.xml").read_text(encoding="utf-8"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ArxivProvider(client)
    try:
        await provider.search("transformers", 5, tech_only=True)
        assert "cat:cs." in captured["query"]
    finally:
        await client.aclose()


async def test_get_returns_none_for_doi_without_request():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, text=(FIXTURES / "arxiv_search.xml").read_text(encoding="utf-8"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ArxivProvider(client)
    try:
        assert await provider.get("10.1145/3292500.3330701") is None
        assert calls == []
    finally:
        await client.aclose()


async def test_get_returns_none_for_scopus_id_without_request():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, text=(FIXTURES / "arxiv_search.xml").read_text(encoding="utf-8"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ArxivProvider(client)
    try:
        assert await provider.get("SCOPUS_ID:85012345678") is None
        assert calls == []
    finally:
        await client.aclose()


async def test_get_requests_id_list_for_bare_arxiv_id():
    captured = {}

    def handler(request):
        captured["id_list"] = request.url.params.get("id_list")
        return httpx.Response(200, text=(FIXTURES / "arxiv_search.xml").read_text(encoding="utf-8"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ArxivProvider(client)
    try:
        paper = await provider.get("1706.03762")
        assert captured["id_list"] == "1706.03762"
        assert paper is not None
        assert paper.ids["arxiv"] == "1706.03762v5"
    finally:
        await client.aclose()


async def test_get_extracts_id_from_arxiv_abs_url():
    captured = {}

    def handler(request):
        captured["id_list"] = request.url.params.get("id_list")
        return httpx.Response(200, text=(FIXTURES / "arxiv_search.xml").read_text(encoding="utf-8"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ArxivProvider(client)
    try:
        await provider.get("https://arxiv.org/abs/1706.03762")
        assert captured["id_list"] == "1706.03762"
    finally:
        await client.aclose()


async def test_get_extracts_id_from_arxiv_prefixed_identifier():
    captured = {}

    def handler(request):
        captured["id_list"] = request.url.params.get("id_list")
        return httpx.Response(200, text=(FIXTURES / "arxiv_search.xml").read_text(encoding="utf-8"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ArxivProvider(client)
    try:
        await provider.get("ARXIV:1706.03762")
        assert captured["id_list"] == "1706.03762"
    finally:
        await client.aclose()


async def test_search_sends_start_for_pagination():
    captured = {}

    def handler(request):
        captured["start"] = request.url.params.get("start")
        return httpx.Response(200, text=(FIXTURES / "arxiv_search.xml").read_text(encoding="utf-8"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ArxivProvider(client)
    try:
        await provider.search("lstm", 5, offset=15)
        assert captured["start"] == "15"
    finally:
        await client.aclose()


async def test_search_author_uses_au_field_prefix():
    captured = {}
    xml = (FIXTURES / "arxiv_search.xml").read_text(encoding="utf-8")

    def handler(request):
        captured["search_query"] = request.url.params.get("search_query")
        return httpx.Response(200, text=xml)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ArxivProvider(client)
    try:
        await provider.search_author("Yoshua Bengio", 5)
        assert captured["search_query"] == 'au:"Yoshua Bengio"'
    finally:
        await client.aclose()


async def test_search_author_still_honors_offset_and_year():
    captured = {}
    xml = (FIXTURES / "arxiv_search.xml").read_text(encoding="utf-8")

    def handler(request):
        captured["start"] = request.url.params.get("start")
        return httpx.Response(200, text=xml)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ArxivProvider(client)
    try:
        # The fixture is dated 2017, so a 2020 lower bound must drop it.
        kept = await provider.search_author("Yoshua Bengio", 5, year_from=2016, offset=20)
        assert captured["start"] == "20"
        assert len(kept) == 1
        filtered = await provider.search_author("Yoshua Bengio", 5, year_from=2020)
        assert filtered == []
    finally:
        await client.aclose()
