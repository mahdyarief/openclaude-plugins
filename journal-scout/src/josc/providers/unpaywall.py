from typing import Optional

from ..config import get_polite_email
from ..models import Paper
from ..utils import normalize_doi, parse_year
from .base import ProviderBase

UNPAYWALL_URL = "https://api.unpaywall.org/v2"


class UnpaywallProvider(ProviderBase):
    name = "unpaywall"
    supports_search = False
    # Unpaywall is not a searchable source: it only resolves a known DOI into
    # open-access links, so the aggregator consults it to enrich a record.
    enricher = True

    async def get(self, identifier: str) -> Optional[Paper]:
        doi = normalize_doi(identifier)
        if not doi:
            return None
        data = await self._fetch_json(f"{UNPAYWALL_URL}/{doi}", params={"email": get_polite_email()})
        best = data.get("best_oa_location") or {}
        pdf_url = best.get("url_for_pdf")
        if not pdf_url:
            # ``best_oa_location`` is chosen for the whole record, not for the
            # PDF: it can be a landing page while another location hosts the
            # file, so fall back to any location that actually has a PDF.
            for location in data.get("oa_locations") or []:
                if isinstance(location, dict) and location.get("url_for_pdf"):
                    pdf_url = location["url_for_pdf"]
                    break
        return Paper(
            doi=doi,
            title=data.get("title") or "",
            year=parse_year(data.get("year")),
            venue=data.get("journal_name"),
            pdf_url=pdf_url,
            url=best.get("url_for_landing_page"),
            is_open_access=data.get("is_oa"),
            sources=["unpaywall"],
            ids={"unpaywall": doi},
        )
