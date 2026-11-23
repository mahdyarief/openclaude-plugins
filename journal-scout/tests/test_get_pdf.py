import json
from pathlib import Path

import pytest

from josc import pdf_save, pdf_tool
from josc.api import pdf_routes
from josc.fulltext_fetch import fetch_pdf
from josc.models import Paper, ProviderError
from josc.providers.base import ProviderBase

DOI = "10.1016/j.cosrev.2026.101054"
PDF_URL = "https://oa.example/paper.pdf"
PDF = b"%PDF-1.7 tiny"


class BytesFetcher:
    def __init__(self, files):
        self.files = files
        self.calls = []

    async def get_bytes(self, url, params=None, headers=None, provider=None, **kwargs):
        self.calls.append(url)
        if url not in self.files:
            raise ProviderError("fulltext", "HTTP 403")
        return self.files[url]


class OneProvider(ProviderBase):
    name = "openalex"

    def __init__(self, fetcher, paper):
        super().__init__(fetcher)
        self._paper = paper

    async def get(self, identifier):
        return self._paper


def _providers(files=None, paper=None):
    fetcher = BytesFetcher({PDF_URL: PDF} if files is None else files)
    paper = paper or Paper(doi=DOI, title="T", pdf_url=PDF_URL)
    return [OneProvider(fetcher, paper)], fetcher


@pytest.fixture(autouse=True)
def _fresh_cache(monkeypatch):
    pdf_save.clear_cache()
    monkeypatch.delenv("JOSC_PDF_DIR", raising=False)
    monkeypatch.delenv("JOSC_PUBLIC_URL", raising=False)
    yield
    pdf_save.clear_cache()


# --- naming -----------------------------------------------------------------


@pytest.mark.parametrize(
    "identifier, requested, expected",
    [
        (DOI, None, "10.1016_j.cosrev.2026.101054.pdf"),
        ("2401.12345", None, "2401.12345.pdf"),
        (DOI, "my paper.PDF", "my_paper.pdf"),
        (DOI, "../../etc/passwd", "passwd.pdf"),
        (DOI, "..", "paper.pdf"),
    ],
)
def test_pdf_filename_is_safe(identifier, requested, expected):
    assert pdf_save.pdf_filename(identifier, requested) == expected


# --- fetch_pdf ----------------------------------------------------------------


async def test_fetch_pdf_returns_bytes_without_parsing(monkeypatch):
    def boom(data):
        raise AssertionError("fetch_pdf must not parse the PDF")

    monkeypatch.setattr("josc.fulltext_fetch.extract_pdf_text_from_bytes", boom)
    providers, _ = _providers()
    result = await fetch_pdf(providers, DOI, scinet=False, curl=False)
    assert result["status"] == "found"
    assert result["pdf_bytes"] == PDF
    assert result["size"] == len(PDF)
    assert result["pdf_source"] == "open_access"


async def test_fetch_pdf_rejects_html_and_reports_no_oa_when_nothing_left():
    providers, _ = _providers(files={PDF_URL: b"<html>challenge</html>"})
    result = await fetch_pdf(providers, DOI, scinet=False, curl=False)
    assert result["status"] == "error"
    assert "pdf_bytes" not in result


# --- stdio: save to the client's folder ----------------------------------------


def test_root_paths_reads_file_uris(tmp_path):
    uri = tmp_path.as_uri()
    assert pdf_tool.root_paths([uri, "https://not-a-file"]) == [tmp_path]


async def test_stdio_saves_into_client_root_source_pdf(tmp_path):
    providers, _ = _providers()
    payload = await pdf_tool.get_pdf(
        {"identifier": DOI, "scinet": False, "curl": False},
        providers,
        "stdio",
        root_uris=[tmp_path.as_uri()],
    )
    target = tmp_path / "source" / "pdf" / "10.1016_j.cosrev.2026.101054.pdf"
    assert payload["delivery"] == "saved"
    assert Path(payload["path"]) == target.resolve()
    assert target.read_bytes() == PDF
    assert "pdf_bytes" not in payload
    json.dumps(payload)  # tool results must be JSON-serialisable


async def test_stdio_relative_save_dir_and_cwd_fallback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    providers, _ = _providers()
    payload = await pdf_tool.get_pdf(
        {"identifier": DOI, "save_dir": "refs", "filename": "x.pdf", "curl": False, "scinet": False},
        providers,
        "stdio",
    )
    assert Path(payload["path"]) == (tmp_path / "refs" / "x.pdf").resolve()


async def test_stdio_josc_pdf_dir_used_as_is(tmp_path, monkeypatch):
    monkeypatch.setenv("JOSC_PDF_DIR", str(tmp_path / "pdfs"))
    providers, _ = _providers()
    payload = await pdf_tool.get_pdf(
        {"identifier": DOI, "curl": False, "scinet": False}, providers, "stdio"
    )
    assert Path(payload["path"]).parent == (tmp_path / "pdfs").resolve()


async def test_not_found_writes_nothing(tmp_path):
    providers, _ = _providers(files={})
    payload = await pdf_tool.get_pdf(
        {"identifier": DOI, "curl": False, "scinet": False},
        providers,
        "stdio",
        root_uris=[tmp_path.as_uri()],
    )
    assert payload["status"] == "error"
    assert not (tmp_path / "source").exists()


# --- http: hand the client a download link -------------------------------------


async def test_http_returns_download_link_and_caches_bytes():
    providers, _ = _providers()
    payload = await pdf_tool.get_pdf(
        {"identifier": DOI, "curl": False, "scinet": False},
        providers,
        "http",
        base_url="https://journal.example",
    )
    assert payload["delivery"] == "download"
    assert payload["download_url"].startswith("https://journal.example/api/pdf?identifier=10.1016")
    assert payload["save_path"] == "source/pdf/10.1016_j.cosrev.2026.101054.pdf"
    assert payload["command"].startswith('mkdir -p "source/pdf" && curl -fsSL -o')
    assert pdf_save.recall(DOI)["pdf_bytes"] == PDF


async def test_http_without_public_url_says_so():
    providers, _ = _providers()
    payload = await pdf_tool.get_pdf(
        {"identifier": DOI, "curl": False, "scinet": False}, providers, "http", base_url=None
    )
    assert payload["delivery"] == "unavailable"
    assert "JOSC_PUBLIC_URL" in payload["error"]


@pytest.mark.parametrize(
    "headers, env, expected",
    [
        ({"host": "journal.example", "cf-visitor": '{"scheme":"https"}', "x-forwarded-proto": "http"}, None, "https://journal.example"),
        ({"host": "a.test", "x-forwarded-proto": "https"}, None, "https://a.test"),
        ({"host": "127.0.0.1:8080"}, None, "http://127.0.0.1:8080"),
        ({"host": "ignored"}, "https://pinned.example/", "https://pinned.example"),
        ({}, None, None),
    ],
)
def test_public_base_url(headers, env, expected, monkeypatch):
    if env:
        monkeypatch.setenv("JOSC_PUBLIC_URL", env)
    assert pdf_tool.public_base_url(headers) == expected


# --- /api/pdf -------------------------------------------------------------------


class _QueryParams(dict):
    def getlist(self, key):
        value = self.get(key)
        return [] if value is None else [value]


class _Request:
    def __init__(self, **params):
        self.query_params = _QueryParams(params)


async def test_api_pdf_serves_cached_bytes_as_attachment(monkeypatch):
    pdf_save.remember(DOI, {"status": "found", "pdf_bytes": PDF, "pdf_source": "scinet"})
    monkeypatch.setattr(pdf_routes, "_providers", lambda: [])
    response = await pdf_routes.pdf_download(_Request(identifier=DOI, filename="a.pdf"))
    assert response.status_code == 200
    assert response.body == PDF
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == 'attachment; filename="a.pdf"'
    assert response.headers["x-pdf-source"] == "scinet"


async def test_api_pdf_headers_carry_percent_encoded_title(monkeypatch):
    pdf_save.remember(
        DOI,
        {
            "status": "found",
            "pdf_bytes": PDF,
            "pdf_source": "crossref",
            "via": "curl",
            "pdf_url": "https://x.test/a b.pdf",
            "paper": {"title": "Résumé: a – survey"},
        },
    )
    monkeypatch.setattr(pdf_routes, "_providers", lambda: [])
    response = await pdf_routes.pdf_download(_Request(identifier=DOI))
    from urllib.parse import unquote

    assert unquote(response.headers["x-paper-title"]) == "Résumé: a – survey"
    assert response.headers["x-pdf-via"] == "curl"
    assert response.headers["x-pdf-url"] == "https://x.test/a%20b.pdf"


async def test_api_pdf_fetches_on_demand(monkeypatch):
    providers, fetcher = _providers()
    monkeypatch.setattr(pdf_routes, "_providers", lambda: providers)
    response = await pdf_routes.pdf_download(_Request(identifier=DOI, curl="false", scinet="false"))
    assert response.status_code == 200
    assert response.body == PDF
    assert fetcher.calls == [PDF_URL]


async def test_api_pdf_missing_paper_is_json_404(monkeypatch):
    providers, _ = _providers(files={}, paper=None)

    class Nobody(ProviderBase):
        name = "openalex"

        async def get(self, identifier):
            return None

    monkeypatch.setattr(pdf_routes, "_providers", lambda: [Nobody(providers[0].fetcher)])
    response = await pdf_routes.pdf_download(_Request(identifier="not-a-doi"))
    assert response.status_code == 404
    assert json.loads(response.body)["status"] == "not_found"


async def test_api_pdf_requires_identifier():
    response = await pdf_routes.pdf_download(_Request())
    assert response.status_code == 400


def test_get_pdf_tool_is_registered():
    from josc.server import TOOL_NAMES, _tool_list

    assert "get_pdf" in TOOL_NAMES
    schema = next(t for t in _tool_list() if t.name == "get_pdf").inputSchema
    assert {"identifier", "save_dir", "filename", "scinet", "curl"} <= set(schema["properties"])
