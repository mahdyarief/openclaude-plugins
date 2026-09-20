from typing import Any, Dict, List, Optional

from ..models import Paper


class ProviderBase:
    name: str = ""
    supports_search: bool = True

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
    ) -> List[Paper]:
        return []

    async def get(self, identifier: str) -> Optional[Paper]:
        return None

    async def citations(self, identifier: str, limit: int) -> List[Paper]:
        return []