from typing import Any, Dict, List, Optional

from ..models import Paper


class ProviderBase:
    """Common interface every journal source implements.

    Each provider advertises what it can do through the ``supports_*`` flags
    and whether it merely enriches records (``enricher``) instead of acting as
    a primary source. The aggregator routes requests by reading these flags,
    so no source name is hard-coded outside the provider registry.
    """

    name: str = ""
    supports_search: bool = True
    supports_citations: bool = False
    supports_author_search: bool = False
    supports_references: bool = False
    supports_related: bool = False
    # True only when search() actually applies the tech/CS restriction.
    supports_tech_only: bool = False
    # Field names this provider can actually honour in search().
    supports_filters: frozenset[str] = frozenset()
    # An enricher is not queried during a normal fan-out; it is only consulted
    # to augment an already-resolved record (e.g. Unpaywall adds OA links).
    enricher: bool = False
    # A source opted out of the default fan-out (e.g. one behind a bot
    # challenge). It is still reachable when the caller names it explicitly.
    opt_out: bool = False

    def __init__(self, fetcher: Any, config: Optional[Dict[str, Any]] = None):
        self.fetcher = fetcher
        self.config = config or {}

    async def _fetch_json(self, url, params=None, headers=None, provider=None) -> Dict[str, Any]:
        provider = provider or self.name
        if hasattr(self.fetcher, "get_json"):
            return await self.fetcher.get_json(url, params=params, headers=headers, provider=provider)
        response = await self.fetcher.get(url, params=params, headers=headers)
        return response.json()

    async def _fetch_text(self, url, params=None, headers=None, provider=None) -> str:
        provider = provider or self.name
        if hasattr(self.fetcher, "get_text"):
            return await self.fetcher.get_text(url, params=params, headers=headers, provider=provider)
        response = await self.fetcher.get(url, params=params, headers=headers)
        return response.text

    async def search(
        self,
        query: str,
        limit: int,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        tech_only: bool = False,
        author: Optional[str] = None,
        venue: Optional[str] = None,
        offset: int = 0,
    ) -> List[Paper]:
        return []

    async def search_author(
        self,
        author: str,
        limit: int,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        venue: Optional[str] = None,
        offset: int = 0,
    ) -> List[Paper]:
        return []

    async def get(self, identifier: str) -> Optional[Paper]:
        return None

    async def citations(self, identifier: str, limit: int) -> List[Paper]:
        return []

    async def references(self, identifier: str, limit: int) -> List[Paper]:
        return []

    async def related(self, identifier: str, limit: int) -> List[Paper]:
        return []
