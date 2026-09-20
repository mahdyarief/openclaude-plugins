from typing import Optional

from ..config import get_polite_email
from ..models import Paper
from ..utils import normalize_doi
from .base import ProviderBase

UNPAYWALL_URL = "https://api.unpaywall.org/v2"


class UnpaywallProvider(ProviderBase):
    name = "unpaywall"
    supports_search = False

    async def get(self, identifier: str) -> Optional[Paper]:
        doi = normalize_doi(identifier)
        if not doi:
            return None
        data = await self._fetch_json(f"{UNPAYWALL_URL}/{doi}", params={"email": get_polite_email()})
        best = data.get("best_oa_location") or {}
        return Paper(
            doi=doi,
            title=data.get("title") or "",
            year=data.get("year"),
            venue=data.get("journal_name"),
            pdf_url=best.get("url_for_pdf"),
            url=best.get("url_for_landing_page"),
            is_open_access=data.get("is_oa"),
            sources=["unpaywall"],
            ids={"unpaywall": doi},
        )