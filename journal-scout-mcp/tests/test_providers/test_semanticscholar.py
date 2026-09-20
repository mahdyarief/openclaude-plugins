import json
from pathlib import Path
from urllib.parse import unquote

import httpx

from journal_scout_mcp.providers.semanticscholar import SemanticScholarProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _path_contains(path: str, encoded: str) -> bool:
    """True if the URL path carries ``encoded``, whether httpx kept it
    percent-encoded or left it decoded."""
    return encoded in path or unquote(encoded) in unquote(path)


async def test_search_maps_data_to_paper():
    payload = json.loads((FIXTURES / "semanticscholar_search.json").read_text(encoding="utf-8"))

    def handler(request):
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SemanticScholarProvider(client)
    try:
        papers = await provider.search("attention", 5)
        assert len(papers) == 1
        p = papers[0]
        assert p.doi == "10.5555/3295222.3295349"
        assert p.title == "Attention Is All You Need"
        assert p.year == 2017
        assert p.citation_count == 90000
        assert p.authors == ["Ashish Vaswani", "Noam Shazeer"]
        assert p.pdf_url == "https://example.org/attn.pdf"
        assert p.sources == ["semanticscholar"]
        assert p.ids["semanticscholar"] == "abc123"
        assert p.ids["arxiv"] == "1706.03762"
    finally:
        await client.aclose()


async def test_api_key_header_sent_when_configured(monkeypatch):
    captured = {}

    def handler(request):
        captured["key"] = request.headers.get("x-api-key")
        return httpx.Response(200, json={"data": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SemanticScholarProvider(client)
    monkeypatch.setattr(
        "journal_scout_mcp.providers.semanticscholar.get_semantic_scholar_key",
        lambda: "secret-key",
    )
    try:
        await provider.search("anything", 1)
        assert captured["key"] == "secret-key"
    finally:
        await client.aclose()


async def test_get_prefixes_bare_doi():
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        return httpx.Response(200, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SemanticScholarProvider(client)
    try:
        await provider.get("10.5555/3295222.3295349")
        assert _path_contains(captured["path"], "DOI%3A10.5555")
    finally:
        await client.aclose()


async def test_get_prefixes_arxiv_id():
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        return httpx.Response(200, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SemanticScholarProvider(client)
    try:
        await provider.get("1706.03762")
        assert _path_contains(captured["path"], "ARXIV%3A1706.03762")
    finally:
        await client.aclose()


async def test_get_prefixes_arxiv_id_with_version():
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        return httpx.Response(200, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SemanticScholarProvider(client)
    try:
        await provider.get("1706.03762v5")
        assert _path_contains(captured["path"], "ARXIV%3A1706.03762v5")
    finally:
        await client.aclose()


async def test_get_prefixes_numeric_corpus_id():
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        return httpx.Response(200, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SemanticScholarProvider(client)
    try:
        await provider.get("123456")
        assert _path_contains(captured["path"], "CorpusId%3A123456")
    finally:
        await client.aclose()


async def test_get_passes_through_explicitly_prefixed_identifier():
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        return httpx.Response(200, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SemanticScholarProvider(client)
    try:
        await provider.get("DOI:10.1/x")
        assert _path_contains(captured["path"], "DOI%3A10.1")
    finally:
        await client.aclose()


async def test_citations_prefixes_arxiv_identifier():
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        return httpx.Response(200, json={"data": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SemanticScholarProvider(client)
    try:
        await provider.citations("1706.03762", 3)
        assert _path_contains(captured["path"], "ARXIV%3A1706.03762")
        assert captured["path"].rstrip("/").endswith("citations")
    finally:
        await client.aclose()


async def test_citations_passes_through_explicitly_prefixed_identifier():
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        return httpx.Response(200, json={"data": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SemanticScholarProvider(client)
    try:
        await provider.citations("CorpusId:123456", 3)
        assert _path_contains(captured["path"], "CorpusId%3A123456")
    finally:
        await client.aclose()


async def test_get_normalizes_doi_url_to_same_request_as_bare_doi():
    captured = []

    def handler(request):
        captured.append(request.url.path)
        return httpx.Response(200, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SemanticScholarProvider(client)
    try:
        await provider.get("10.1/x")
        await provider.get("https://doi.org/10.1/x")
        assert len(captured) == 2
        bare, url_form = captured
        assert url_form == bare
        assert _path_contains(bare, "DOI%3A10.1")
    finally:
        await client.aclose()


async def test_get_returns_none_for_unknown_identifier_without_request():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SemanticScholarProvider(client)
    try:
        assert await provider.get("W2949676527") is None
        assert calls == []
    finally:
        await client.aclose()


async def test_get_returns_none_for_scopus_id_without_request():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SemanticScholarProvider(client)
    try:
        assert await provider.get("SCOPUS_ID:85012345678") is None
        assert calls == []
    finally:
        await client.aclose()


async def test_get_passes_through_bare_s2_paper_id():
    paper_id = "9f6a3a1e0d5b1c2a3b4c5d6e7f8a9b0c1d2e3f40"
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        return httpx.Response(200, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SemanticScholarProvider(client)
    try:
        await provider.get(paper_id)
        assert captured["path"].rstrip("/").endswith(f"/paper/{paper_id}")
    finally:
        await client.aclose()


async def test_citations_returns_empty_for_unknown_identifier_without_request():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json={"data": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SemanticScholarProvider(client)
    try:
        assert await provider.citations("W2949676527", 3) == []
        assert calls == []
    finally:
        await client.aclose()
