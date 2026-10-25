from pathlib import Path

import httpx

from josc.providers.garuda import GarudaProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _fixture() -> str:
    return (FIXTURES / "garuda_search.html").read_text(encoding="utf-8")


def _provider(captured: dict | None = None) -> tuple[GarudaProvider, httpx.AsyncClient]:
    html = _fixture()

    def handler(request):
        if captured is not None:
            captured["params"] = dict(request.url.params)
        return httpx.Response(200, text=html)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return GarudaProvider(client), client


async def test_search_parses_article_items():
    provider, client = _provider()
    try:
        papers = await provider.search("machine learning", 10)
        assert len(papers) == 10

        first = papers[0]
        assert first.title.startswith("PERBANDINGAN PERFORMA PREDIKSI")
        assert first.authors == ["Rina Mamase", "Ruli S. Sinukun"]
        assert first.venue == "Jurnal Technopreneur (JTech)"
        assert first.year == 2018
        assert first.url == "https://garuda.kemdiktisaintek.go.id/documents/detail/842734"
        assert first.sources == ["garuda"]
    finally:
        await client.aclose()


async def test_search_strips_dangling_hyphen_from_authors():
    provider, client = _provider()
    try:
        papers = await provider.search("machine learning", 10)
        for paper in papers:
            for author in paper.authors:
                assert not author.endswith(" -"), f"dangling hyphen in {author!r}"
    finally:
        await client.aclose()


async def test_search_leaves_no_separator_residue_in_venue():
    provider, client = _provider()
    try:
        papers = await provider.search("machine learning", 10)
        for paper in papers:
            venue = paper.venue or ""
            assert " : " not in venue, venue
            assert not venue.endswith(" ,"), venue
    finally:
        await client.aclose()


async def test_search_sends_query_and_page_params():
    captured = {}
    provider, client = _provider(captured)
    try:
        await provider.search("graphene", 10)
        assert captured["params"].get("q") == "graphene"
        assert captured["params"].get("page") == "1"
    finally:
        await client.aclose()


async def test_search_honors_limit():
    provider, client = _provider()
    try:
        papers = await provider.search("machine learning", 3)
        assert len(papers) == 3
    finally:
        await client.aclose()


async def test_search_honors_offset():
    provider, client = _provider()
    try:
        papers = await provider.search("machine learning", 10, offset=8)
        assert len(papers) == 2
    finally:
        await client.aclose()


async def test_search_filters_by_year_from():
    provider, client = _provider()
    try:
        # Newest record in the fixture is 2021; 2020 must drop the older ones.
        papers = await provider.search("machine learning", 10, year_from=2020)
        assert papers, "expected at least one record from 2020 onward"
        assert all(p.year >= 2020 for p in papers)
    finally:
        await client.aclose()


async def test_search_filters_by_year_to():
    provider, client = _provider()
    try:
        papers = await provider.search("machine learning", 10, year_to=2016)
        assert papers, "expected at least one record from 2016 or earlier"
        assert all(p.year <= 2016 for p in papers)
    finally:
        await client.aclose()


async def test_search_tech_only_is_not_claimed():
    # Garuda indexes every discipline, so the provider must not advertise a
    # tech/CS restriction it cannot actually apply.
    assert GarudaProvider.supports_tech_only is False


async def test_get_returns_none_without_request():
    calls = []
    provider, client = _provider()
    provider.fetcher = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: calls.append(str(request.url)))
    )
    try:
        assert await provider.get("10.1/abc") is None
        assert calls == []
    finally:
        await client.aclose()
        await provider.fetcher.aclose()


def _detail_provider(captured: dict | None = None):
    html = (FIXTURES / "garuda_detail.html").read_text(encoding="utf-8")

    def handler(request):
        if captured is not None:
            captured["url"] = str(request.url)
        return httpx.Response(200, text=html)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return GarudaProvider(client), client


async def test_get_parses_detail_page():
    captured = {}
    provider, client = _detail_provider(captured)
    try:
        paper = await provider.get("6420654")

        assert paper is not None
        assert paper.title.startswith("NLP, Machine Learning Optimizing")
        assert paper.authors == [
            "Fahmi Setiawan",
            "Izhar Fradila",
            "Alwi Pernando",
            "Supina Batubara",
        ]
        assert paper.year == 2024
        assert paper.venue == (
            "The Journal of Information Technology, Computer Science, "
            "and Electrical Engineering"
        )
        assert paper.abstract and paper.abstract.startswith("This research aims to optimize")
        assert paper.pdf_url == (
            "https://ysmk.org/ejournal/index.php/jitcse/article/download/25/33"
        )
        assert paper.ids["garuda"] == "6420654"
        assert paper.sources == ["garuda"]
        assert captured["url"].endswith("/documents/detail/6420654")
    finally:
        await client.aclose()
