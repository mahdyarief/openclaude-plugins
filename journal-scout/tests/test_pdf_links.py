import httpx
import pytest

from josc import pdf_links
from josc.fulltext_fetch import fetch_fulltext
from josc.http import Fetcher
from josc.models import ProviderError
from josc.providers.base import ProviderBase

DOI = "10.1007/s44196-026-01490-x"
SPRINGER_PDF = f"https://link.springer.com/content/pdf/{DOI}.pdf"
LANDING = f"https://link.springer.com/article/{DOI}"
CROSSREF_MESSAGE = {
    "link": [
        {"URL": LANDING, "content-type": "text/html", "intended-application": "text-mining"},
        {"URL": SPRINGER_PDF, "content-type": "application/pdf", "intended-application": "similarity-checking"},
        {"URL": SPRINGER_PDF, "content-type": "application/pdf", "intended-application": "text-mining"},
        {"URL": "https://api.elsevier.com/x?httpAccept=text/xml", "content-type": "text/xml"},
    ]
}
LANDING_HTML = f"""<html><head>
<meta content="{SPRINGER_PDF}" name="citation_pdf_url"/>
<link rel="alternate" type="application/pdf" href="/content/pdf/alt.pdf">
</head></html>"""


def test_crossref_pdf_links_keeps_only_pdfs_deduped():
    assert pdf_links.crossref_pdf_links(CROSSREF_MESSAGE) == [SPRINGER_PDF]


def test_landing_pdf_links_reads_meta_any_attr_order_and_link_alternate():
    assert pdf_links.landing_pdf_links(LANDING_HTML, LANDING) == [
        SPRINGER_PDF,
        "https://link.springer.com/content/pdf/alt.pdf",
    ]


def test_landing_pdf_links_unescapes_and_resolves_relative():
    page = '<meta name="citation_pdf_url" content="/doi/pdf/1?a=1&amp;b=2">'
    assert pdf_links.landing_pdf_links(page, "https://pub.example/doi/1") == [
        "https://pub.example/doi/pdf/1?a=1&b=2"
    ]


class StageFetcher:
    def __init__(self, crossref=None, page=None, files=None):
        self.crossref = crossref
        self.page = page
        self.files = files or {}
        self.calls = []

    async def get_json(self, url, params=None, headers=None, provider=None):
        self.calls.append(("json", url))
        if self.crossref is None:
            raise ProviderError("crossref", "HTTP 404")
        return {"message": self.crossref}

    async def get_page(self, url, params=None, headers=None, provider=None):
        self.calls.append(("page", url))
        if self.page is None:
            raise ProviderError("landing", "HTTP 404")
        return self.page

    async def get_bytes(self, url, params=None, headers=None, provider=None, **kwargs):
        self.calls.append(("bytes", url))
        if url not in self.files:
            raise ProviderError("fulltext", "Access forbidden (403)")
        return self.files[url]


class NoProvider(ProviderBase):
    name = "openalex"

    async def get(self, identifier):
        return None


@pytest.fixture
def no_pdf_parse(monkeypatch):
    monkeypatch.setattr(
        "josc.fulltext_fetch.extract_pdf_text_from_bytes", lambda data: "BODY"
    )


async def test_crossref_link_downloads_springer_pdf(no_pdf_parse):
    fetcher = StageFetcher(crossref=CROSSREF_MESSAGE, files={SPRINGER_PDF: b"%PDF-1.7"})
    result = await fetch_fulltext([NoProvider(fetcher)], DOI, scinet=False)
    assert result["status"] == "found"
    assert result["pdf_source"] == "crossref"
    assert result["pdf_url"] == SPRINGER_PDF
    assert ("page", f"https://doi.org/{DOI}") not in fetcher.calls


async def test_landing_meta_used_when_crossref_has_no_pdf(no_pdf_parse):
    fetcher = StageFetcher(
        crossref={"link": []},
        page=(LANDING, LANDING_HTML),
        files={SPRINGER_PDF: b"%PDF-1.7"},
    )
    result = await fetch_fulltext([NoProvider(fetcher)], DOI, scinet=False)
    assert result["pdf_source"] == "landing"
    assert result["pdf_url"] == SPRINGER_PDF


async def test_same_url_not_downloaded_twice_across_stages():
    fetcher = StageFetcher(crossref=CROSSREF_MESSAGE, page=(LANDING, LANDING_HTML))
    result = await fetch_fulltext([NoProvider(fetcher)], DOI, scinet=False)
    downloads = [url for kind, url in fetcher.calls if kind == "bytes"]
    assert downloads.count(SPRINGER_PDF) == 1
    assert result["status"] == "error"
    assert [a["source"] for a in result["attempts"]] == ["crossref", "landing"]


async def test_unknown_doi_everywhere_is_not_found():
    result = await fetch_fulltext([NoProvider(StageFetcher())], "10.9999/nope", scinet=False)
    assert result["status"] == "not_found"


async def test_fetcher_get_page_follows_redirects_and_reports_final_url():
    def handler(request):
        if request.url.host == "doi.org":
            return httpx.Response(302, headers={"Location": LANDING})
        return httpx.Response(200, text=LANDING_HTML)

    f = Fetcher(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), cache=None)
    try:
        final_url, page = await f.get_page(f"https://doi.org/{DOI}")
    finally:
        await f.close()
    assert final_url == LANDING
    assert "citation_pdf_url" in page


async def test_fetcher_get_bytes_follows_redirects_when_asked():
    def handler(request):
        if request.url.path == "/pdf":
            return httpx.Response(302, headers={"Location": "https://cdn.example/f.pdf"})
        return httpx.Response(200, content=b"%PDF-1.4")

    f = Fetcher(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), cache=None)
    try:
        assert await f.get_bytes("https://pub.example/pdf", follow_redirects=True) == b"%PDF-1.4"
    finally:
        await f.close()
