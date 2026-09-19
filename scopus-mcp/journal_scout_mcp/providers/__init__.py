from typing import Any, Dict, List, Optional

from .base import ProviderBase

PROVIDER_NAMES: List[str] = [
    "scopus",
    "arxiv",
    "openalex",
    "semanticscholar",
    "crossref",
    "dblp",
    "unpaywall",
]


def build_providers(fetcher: Any, config: Optional[Dict[str, Any]] = None) -> List[ProviderBase]:
    from .scopus import ScopusProvider
    from .arxiv import ArxivProvider
    from .openalex import OpenAlexProvider
    from .semanticscholar import SemanticScholarProvider
    from .crossref import CrossrefProvider
    from .dblp import DblpProvider
    from .unpaywall import UnpaywallProvider

    classes = [
        ScopusProvider,
        ArxivProvider,
        OpenAlexProvider,
        SemanticScholarProvider,
        CrossrefProvider,
        DblpProvider,
        UnpaywallProvider,
    ]
    return [cls(fetcher, config) for cls in classes]