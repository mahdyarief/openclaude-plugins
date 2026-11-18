from typing import Any, Dict, List, Optional

from .base import ProviderBase

# The provider classes are the single source of truth for source names and
# capabilities; every consumer reads from here instead of repeating lists.
_CLASSES: Optional[List[type]] = None


def _provider_classes() -> List[type]:
    global _CLASSES
    if _CLASSES is None:
        from .scopus import ScopusProvider
        from .arxiv import ArxivProvider
        from .openalex import OpenAlexProvider
        from .crossref import CrossrefProvider
        from .pubmed import PubMedProvider
        from .unpaywall import UnpaywallProvider
        from .opencitations import OpenCitationsProvider
        from .garuda import GarudaProvider
        from .consensus import ConsensusProvider
        from .exa import ExaProvider

        _CLASSES = [
            ScopusProvider,
            ArxivProvider,
            OpenAlexProvider,
            CrossrefProvider,
            PubMedProvider,
            UnpaywallProvider,
            OpenCitationsProvider,
            GarudaProvider,
            ConsensusProvider,
            ExaProvider,
        ]
    return _CLASSES


def provider_names() -> List[str]:
    return [cls.name for cls in _provider_classes()]


def search_provider_names() -> List[str]:
    return [cls.name for cls in _provider_classes() if cls.supports_search]


def build_providers(fetcher: Any, config: Optional[Dict[str, Any]] = None) -> List[ProviderBase]:
    return [cls(fetcher, config) for cls in _provider_classes()]
