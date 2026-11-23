import http.server
import threading

import pytest

from josc import curl_fetch
from josc.config import get_curl_enabled
from josc.fulltext_fetch import fetch_fulltext
from josc.models import ProviderError
from josc.providers.base import ProviderBase

DOI = "10.1007/s44196-026-01490-x"
PDF = f"https://link.springer.com/content/pdf/{DOI}.pdf"


class RefusingFetcher:
    """httpx stand-in that always gets the Springer-style challenge page."""

    def __init__(self):
        self.calls = []

    async def get_json(self, url, params=None, headers=None, provider=None):
        return {"message": {"link": [{"URL": PDF, "content-type": "application/pdf"}]}}

    async def get_bytes(self, url, params=None, headers=None, provider=None, **kwargs):
        self.calls.append(url)
        return b"<!DOCTYPE html><title>Client Challenge</title>"


class NoProvider(ProviderBase):
    name = "openalex"

    async def get(self, identifier):
        return None


@pytest.fixture
def fake_curl(monkeypatch):
    calls = []

    def install(body=b"%PDF-1.7 via curl", error=None):
        async def fake(url, headers=None):
            calls.append((url, headers))
            if error:
                raise ProviderError("curl", error)
            return url, body

        monkeypatch.setattr(curl_fetch, "curl_get", fake)
        monkeypatch.setattr(curl_fetch, "curl_path", lambda: "/usr/bin/curl")
        return calls

    return install


@pytest.fixture
def no_pdf_parse(monkeypatch):
    monkeypatch.setattr("josc.fulltext_fetch.extract_pdf_text_from_bytes", lambda d: "BODY")


def test_command_is_an_argv_list_with_url_after_double_dash():
    cmd = curl_fetch._command("curl", "https://x.test/a.pdf", "out.bin", {"User-Agent": "UA", "Accept": "*/*"})
    assert cmd[0] == "curl"
    assert cmd[-2:] == ["--", "https://x.test/a.pdf"]
    assert ["--user-agent", "UA"] == cmd[cmd.index("--user-agent"):cmd.index("--user-agent") + 2]
    assert "Accept: */*" in cmd
    assert "=https,http" in cmd


async def test_curl_is_tried_first_and_httpx_skipped_on_success(fake_curl, no_pdf_parse):
    calls = fake_curl()
    fetcher = RefusingFetcher()
    result = await fetch_fulltext([NoProvider(fetcher)], DOI, scinet=False, curl=True)
    assert result["status"] == "found"
    assert result["pdf_source"] == "crossref"
    assert result["via"] == "curl"
    assert calls[0][0] == PDF
    assert fetcher.calls == []
    assert "attempts" not in result


async def test_httpx_is_fallback_when_curl_fails(fake_curl, no_pdf_parse):
    fake_curl(error="HTTP 403 via curl")

    class OkFetcher(RefusingFetcher):
        async def get_bytes(self, url, params=None, headers=None, provider=None, **kwargs):
            self.calls.append(url)
            return b"%PDF-1.7 via httpx"

    fetcher = OkFetcher()
    result = await fetch_fulltext([NoProvider(fetcher)], DOI, scinet=False, curl=True)
    assert result["status"] == "found"
    assert result["via"] == "httpx"
    assert fetcher.calls == [PDF]
    assert result["attempts"] == [
        {"source": "crossref", "pdf_url": PDF, "via": "curl", "error": "HTTP 403 via curl"}
    ]


async def test_both_clients_failing_is_recorded(fake_curl):
    fake_curl(error="HTTP 403 via curl")
    result = await fetch_fulltext([NoProvider(RefusingFetcher())], DOI, scinet=False, curl=True)
    assert result["status"] == "error"
    assert [a["via"] for a in result["attempts"]] == ["curl", "httpx"]


async def test_curl_disabled_uses_only_httpx(fake_curl):
    calls = fake_curl()
    result = await fetch_fulltext([NoProvider(RefusingFetcher())], DOI, scinet=False, curl=False)
    assert result["status"] == "error"
    assert calls == []
    assert "did not return a PDF" in result["error"]


def test_curl_config_default_on(monkeypatch):
    monkeypatch.delenv("JOURNAL_SCOUT_CURL", raising=False)
    monkeypatch.setattr("josc.config.load_config_file", lambda: {})
    assert get_curl_enabled() is True
    monkeypatch.setattr("josc.config.load_config_file", lambda: {"curl_fallback": False})
    assert get_curl_enabled() is False


@pytest.mark.skipif(not curl_fetch.curl_path(), reason="curl not installed")
async def test_real_curl_follows_redirect_and_reports_status():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/go":
                self.send_response(302)
                self.send_header("Location", "/file.pdf")
                self.end_headers()
            elif self.path == "/file.pdf":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"%PDF-1.4 local")
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        final_url, body = await curl_fetch.curl_get(f"{base}/go")
        assert body == b"%PDF-1.4 local"
        assert final_url.endswith("/file.pdf")
        with pytest.raises(ProviderError, match="HTTP 404"):
            await curl_fetch.curl_get(f"{base}/missing")
    finally:
        server.shutdown()
