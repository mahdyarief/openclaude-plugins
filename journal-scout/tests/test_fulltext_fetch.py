from josc.fulltext_fetch import fetch_fulltext
from josc.models import Paper, ProviderError
from josc.providers.base import ProviderBase


class FakeFetcher:
    def __init__(self, pdf_bytes: bytes = b"", error: Exception | None = None):
        self.pdf_bytes = pdf_bytes
        self.error = error
        self.calls = []

    async def get_bytes(self, url, params=None, headers=None, provider=None):
        self.calls.append(url)
        if self.error is not None:
            raise self.error
        return self.pdf_bytes


class PaperProvider(ProviderBase):
    name = "arxiv"

    def __init__(self, fetcher, paper):
        super().__init__(fetcher)
        self._paper = paper

    async def get(self, identifier: str):
        return self._paper


def _providers(fetcher, paper):
    return [PaperProvider(fetcher, paper), PaperProvider(fetcher, None)]


def _monkey_extraction(monkeypatch, text="FULL TEXT BODY"):
    monkeypatch.setattr(
        "josc.fulltext_fetch.extract_pdf_text_from_bytes", lambda data: text
    )


async def test_fetch_fulltext_extracts_pdf_text(monkeypatch):
    fetcher = FakeFetcher(pdf_bytes=b"%PDF-1.4 fake")
    _monkey_extraction(monkeypatch, "FULL TEXT BODY")
    paper = Paper(
        doi="10.1/x",
        title="T",
        pdf_url="https://repo.example/full.pdf",
        sources=["arxiv"],
    )
    result = await fetch_fulltext(_providers(fetcher, paper), "10.1/x")
    assert result["status"] == "found"
    assert result["full_text"] == "FULL TEXT BODY"
    assert result["truncated"] is False
    assert fetcher.calls == ["https://repo.example/full.pdf"]
    assert result["pdf_url"] == "https://repo.example/full.pdf"


async def test_fetch_fulltext_truncates_oversized_text(monkeypatch):
    fetcher = FakeFetcher(pdf_bytes=b"%PDF-1.4 fake")
    _monkey_extraction(monkeypatch, "x" * 10_000)
    paper = Paper(doi="10.1/x", title="T", pdf_url="https://repo.example/f.pdf")
    result = await fetch_fulltext(_providers(fetcher, paper), "10.1/x", max_chars=1_000)
    assert result["status"] == "found"
    assert result["full_text"] == "x" * 1_000
    assert result["truncated"] is True


async def test_fetch_fulltext_no_pdf_url_reports_no_oa(monkeypatch):
    fetcher = FakeFetcher()
    paper = Paper(doi="10.1/x", title="T", is_open_access=False)
    result = await fetch_fulltext(_providers(fetcher, paper), "10.1/x")
    assert result["status"] == "no_oa"
    assert result["full_text"] is None
    assert fetcher.calls == []


async def test_fetch_fulltext_falls_back_to_arxiv_pdf_url(monkeypatch):
    fetcher = FakeFetcher(pdf_bytes=b"%PDF-1.4 fake")
    _monkey_extraction(monkeypatch)
    paper = Paper(title="T", ids={"arxiv": "2401.12345"}, sources=["arxiv"])
    result = await fetch_fulltext(_providers(fetcher, paper), "2401.12345")
    assert result["status"] == "found"
    assert fetcher.calls == ["https://arxiv.org/pdf/2401.12345"]


async def test_fetch_fulltext_download_error_is_reported(monkeypatch):
    fetcher = FakeFetcher(error=ProviderError("repo", "HTTP 403: forbidden"))
    paper = Paper(doi="10.1/x", title="T", pdf_url="https://repo.example/full.pdf")
    result = await fetch_fulltext(_providers(fetcher, paper), "10.1/x")
    assert result["status"] == "error"
    assert "403" in result["error"]
    assert result["full_text"] is None


async def test_fetch_fulltext_uses_enricher_pdf_url(monkeypatch):
    fetcher = FakeFetcher(pdf_bytes=b"%PDF-1.4 fake")
    _monkey_extraction(monkeypatch)
    paper = Paper(doi="10.1/x", title="T")

    class Enricher(ProviderBase):
        name = "unpaywall"
        enricher = True

        async def get(self, identifier):
            return Paper(
                doi=identifier,
                pdf_url="https://unpaywall.example/oa.pdf",
                is_open_access=True,
            )

    providers = [PaperProvider(fetcher, paper), Enricher(fetcher)]
    result = await fetch_fulltext(providers, "10.1/x")
    assert result["status"] == "found"
    assert result["pdf_url"] == "https://unpaywall.example/oa.pdf"
    assert fetcher.calls == ["https://unpaywall.example/oa.pdf"]


async def test_fetch_fulltext_ignores_enricher_errors(monkeypatch):
    fetcher = FakeFetcher()
    paper = Paper(doi="10.1/x", title="T")

    class BrokenEnricher(ProviderBase):
        name = "unpaywall"
        enricher = True

        async def get(self, identifier):
            raise ProviderError("unpaywall", "HTTP 500: boom")

    result = await fetch_fulltext(
        [PaperProvider(fetcher, paper), BrokenEnricher(fetcher)], "10.1/x"
    )
    assert result["status"] == "no_oa"
    assert fetcher.calls == []


async def test_fetch_fulltext_unknown_paper_reports_not_found():
    fetcher = FakeFetcher()
    result = await fetch_fulltext(_providers(fetcher, None), "10.404/gone")
    assert result["status"] == "not_found"
    assert fetcher.calls == []


async def test_fetch_fulltext_missing_pypdf_extra_is_actionable(monkeypatch):
    def raise_missing(data):
        raise RuntimeError(
            "PDF support requires the optional extra: pip install 'journal-scout[pdf]'"
        )

    monkeypatch.setattr(
        "josc.fulltext_fetch.extract_pdf_text_from_bytes", raise_missing
    )
    fetcher = FakeFetcher(pdf_bytes=b"%PDF-1.4 fake")
    paper = Paper(doi="10.1/x", title="T", pdf_url="https://repo.example/full.pdf")
    result = await fetch_fulltext(_providers(fetcher, paper), "10.1/x")
    assert result["status"] == "error"
    assert "journal-scout[pdf]" in result["error"]
