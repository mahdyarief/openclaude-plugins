from pathlib import Path

import pytest

from josc import scinet
from josc.config import get_scinet_enabled
from josc.fulltext_fetch import fetch_fulltext
from josc.models import Paper, ProviderError
from josc.providers.base import ProviderBase

FIXTURE = (Path(__file__).parent / "fixtures" / "scinet_article.html").read_text(
    encoding="utf-8"
)
STORAGE_URL = (
    "https://sci-net.xyz/storage/2024/11647718/"
    "ee19509e32dba63a639d65f7b9707b992201d97506a422962f4e406887d39708/"
    "Dense-Text-Retrieval-Based-on-Pretrained-Language-Models-A-Survey.pdf"
)


class RoutingFetcher:
    """Serves text/bytes per URL; unknown URLs raise like a 404."""

    def __init__(self, pages=None, files=None):
        self.pages = pages or {}
        self.files = files or {}
        self.calls = []

    async def get_text(self, url, params=None, headers=None, provider=None):
        self.calls.append(("text", url, provider))
        if url not in self.pages:
            raise ProviderError(provider or "x", "HTTP 404: missing")
        return self.pages[url]

    async def get_bytes(self, url, params=None, headers=None, provider=None, **kwargs):
        self.calls.append(("bytes", url, provider))
        value = self.files.get(url)
        if value is None:
            raise ProviderError(provider or "x", "HTTP 403: forbidden")
        return value


class OneProvider(ProviderBase):
    name = "openalex"

    def __init__(self, fetcher, paper):
        super().__init__(fetcher)
        self._paper = paper

    async def get(self, identifier):
        return self._paper


@pytest.fixture
def no_pdf_parse(monkeypatch):
    monkeypatch.setattr(
        "josc.fulltext_fetch.extract_pdf_text_from_bytes", lambda data: "SURVEY BODY"
    )


def test_extract_pdf_url_reads_iframe_and_drops_fragment():
    assert scinet.extract_pdf_url(FIXTURE) == STORAGE_URL


def test_extract_pdf_url_none_without_iframe():
    assert scinet.extract_pdf_url("<html><body>requested</body></html>") is None
    assert scinet.extract_pdf_url("Found. Redirecting to /") is None


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("10.1145/3637870", "10.1145/3637870"),
        ("https://doi.org/10.1145/3637870", "10.1145/3637870"),
        ("doi:10.1145/3637870", "10.1145/3637870"),
        ("2401.12345", None),
        ("", None),
    ],
)
def test_normalize_doi(raw, expected):
    assert scinet.normalize_doi(raw) == expected


async def test_find_pdf_url_swallows_http_errors():
    assert await scinet.find_pdf_url(RoutingFetcher(), "10.1145/3637870") is None


async def test_fulltext_falls_back_to_scinet_when_oa_link_fails(no_pdf_parse):
    fetcher = RoutingFetcher(
        pages={"https://sci-net.xyz/10.1145/3637870": FIXTURE},
        files={
            "https://dl.acm.org/doi/pdf/10.1145/3637870": b"<html>challenge</html>",
            STORAGE_URL: b"%PDF-1.7 real",
        },
    )
    paper = Paper(
        doi="10.1145/3637870",
        title="Dense Text Retrieval",
        pdf_url="https://dl.acm.org/doi/pdf/10.1145/3637870",
    )
    result = await fetch_fulltext([OneProvider(fetcher, paper)], "10.1145/3637870", scinet=True)
    assert result["status"] == "found"
    assert result["pdf_source"] == "scinet"
    assert result["pdf_url"] == STORAGE_URL
    assert result["full_text"] == "SURVEY BODY"
    assert "did not return a PDF" in result["attempts"][0]["error"]


async def test_fulltext_prefers_oa_and_skips_scinet(no_pdf_parse):
    fetcher = RoutingFetcher(files={"https://oa.example/p.pdf": b"%PDF-1.4"})
    paper = Paper(doi="10.1145/3637870", pdf_url="https://oa.example/p.pdf")
    result = await fetch_fulltext([OneProvider(fetcher, paper)], "10.1145/3637870", scinet=True)
    assert result["pdf_source"] == "open_access"
    assert not any(call[2] == "scinet" for call in fetcher.calls)


async def test_fulltext_scinet_disabled_keeps_no_oa():
    fetcher = RoutingFetcher(pages={"https://sci-net.xyz/10.1016/x": FIXTURE})
    paper = Paper(doi="10.1016/x")
    result = await fetch_fulltext([OneProvider(fetcher, paper)], "10.1016/x", scinet=False)
    assert result["status"] == "no_oa"
    assert fetcher.calls == []


async def test_fulltext_scinet_works_for_doi_no_provider_knows(no_pdf_parse):
    fetcher = RoutingFetcher(
        pages={"https://sci-net.xyz/10.1145/3637870": FIXTURE},
        files={STORAGE_URL: b"%PDF-1.7"},
    )
    result = await fetch_fulltext([OneProvider(fetcher, None)], "10.1145/3637870", scinet=True)
    assert result["status"] == "found"
    assert result["pdf_source"] == "scinet"
    assert result["paper"]["doi"] == "10.1145/3637870"


async def test_fulltext_scinet_miss_reports_no_oa():
    fetcher = RoutingFetcher(pages={"https://sci-net.xyz/10.1/x": "Found. Redirecting"})
    result = await fetch_fulltext([OneProvider(fetcher, Paper(doi="10.1/x"))], "10.1/x", scinet=True)
    assert result["status"] == "no_oa"


def test_scinet_config_flag(monkeypatch):
    monkeypatch.setattr("josc.config.load_config_file", lambda: {})
    monkeypatch.delenv("JOURNAL_SCOUT_SCINET", raising=False)
    assert get_scinet_enabled() is False
    monkeypatch.setenv("JOURNAL_SCOUT_SCINET", "1")
    assert get_scinet_enabled() is True
    monkeypatch.setenv("JOURNAL_SCOUT_SCINET", "off")
    assert get_scinet_enabled() is False
    monkeypatch.delenv("JOURNAL_SCOUT_SCINET")
    monkeypatch.setattr("josc.config.load_config_file", lambda: {"scinet_fallback": True})
    assert get_scinet_enabled() is True


ACM_URL = "https://dl.acm.org/doi/pdf/10.1145/3711896.3736570?download=true"


async def test_fulltext_tries_acm_download_endpoint(no_pdf_parse):
    fetcher = RoutingFetcher(files={ACM_URL: b"%PDF-1.7 acm"})
    paper = Paper(doi="10.1145/3711896.3736570")
    result = await fetch_fulltext(
        [OneProvider(fetcher, paper)], "10.1145/3711896.3736570", scinet=False
    )
    assert result["status"] == "found"
    assert result["pdf_source"] == "acm"
    assert result["pdf_url"] == ACM_URL


async def test_fulltext_acm_used_when_oa_link_errors(no_pdf_parse):
    fetcher = RoutingFetcher(files={ACM_URL: b"%PDF-1.7 acm"})
    paper = Paper(doi="10.1145/3711896.3736570", pdf_url="https://broken.example/x.pdf")
    result = await fetch_fulltext(
        [OneProvider(fetcher, paper)], "10.1145/3711896.3736570", scinet=False
    )
    assert result["pdf_source"] == "acm"
    assert result["attempts"][0]["source"] == "open_access"


async def test_fulltext_acm_blocked_falls_through_to_scinet(no_pdf_parse):
    fetcher = RoutingFetcher(
        pages={"https://sci-net.xyz/10.1145/3637870": FIXTURE},
        files={STORAGE_URL: b"%PDF-1.7"},
    )
    result = await fetch_fulltext([OneProvider(fetcher, None)], "10.1145/3637870", scinet=True)
    assert result["pdf_source"] == "scinet"
    assert [a["source"] for a in result["attempts"]] == ["acm"]


async def test_fulltext_non_acm_doi_has_no_publisher_route():
    fetcher = RoutingFetcher()
    result = await fetch_fulltext([OneProvider(fetcher, None)], "10.1016/x", scinet=False)
    assert result["status"] == "not_found"


@pytest.mark.parametrize(
    "doi, expected",
    [
        ("10.1056/aidbp2500144", ("nejm_ai", "https://ai.nejm.org/doi/pdf/10.1056/AIdbp2500144")),
        ("10.1056/AIoa2400001", ("nejm_ai", "https://ai.nejm.org/doi/pdf/10.1056/AIoa2400001")),
        ("10.1145/3637870", ("acm", "https://dl.acm.org/doi/pdf/10.1145/3637870?download=true")),
        ("10.7717/peerj-cs.906", ("peerj", "https://peerj.com/articles/cs-906.pdf")),
        ("10.7717/peerj.1000", ("peerj", "https://peerj.com/articles/1000.pdf")),
        ("10.1056/NEJMoa2034577", None),
        ("10.1016/x", None),
    ],
)
def test_publisher_candidate_routes(doi, expected):
    from josc.fulltext_fetch import _publisher_candidate

    assert _publisher_candidate(doi) == expected


async def test_fulltext_tries_nejm_ai_endpoint(no_pdf_parse):
    url = "https://ai.nejm.org/doi/pdf/10.1056/AIdbp2500144"
    fetcher = RoutingFetcher(files={url: b"%PDF-1.7 nejm"})
    result = await fetch_fulltext(
        [OneProvider(fetcher, None)], "10.1056/aidbp2500144", scinet=False
    )
    assert result["status"] == "found"
    assert result["pdf_source"] == "nejm_ai"
    assert result["pdf_url"] == url
