"""HTTP API for josc-web.

Split out of the former ``josc/api.py`` monolith. The package re-exports every
name the tests and ``josc.api:app`` entry point rely on, so ``from josc import
api`` keeps working unchanged.

Module map:

* :mod:`.state`             - process state, cache plumbing, request helpers
* :mod:`.responses`         - JSON error mapping and cache/store statistics
* :mod:`.history`           - best-effort search recording
* :mod:`.search_routes`     - search, author search, paper, citations, network
* :mod:`.discovery_routes`  - metrics (JSON/CSV/report) and GraphML export
* :mod:`.library_routes`    - paper export/import, merge, search and workspace archives
* :mod:`.cache_routes`      - cache clear/info, split, duplicate, replay
* :mod:`.app`               - Starlette assembly, lifespan, CORS, ``start()``
"""

from __future__ import annotations

# Tests monkeypatch ``api.aggregator.<fn>``, so the package re-exports the same
# module object the route modules call into. Patching it mutates the shared
# module, which is what makes those patches take effect.
from .. import aggregator

from .app import SPAStaticFiles, app, lifespan, routes, start
from .library_routes import (
    _papers_from_body,
    export,
    import_external,
    merge,
    quota,
    search_export,
    search_import,
    workspace_export,
    workspace_import,
)
from .cache_routes import (
    cache_clear,
    cache_info,
    search_delete,
    search_duplicate,
    search_replay,
    search_split,
)
from .discovery_routes import (
    _metrics_payload,
    graphml_export,
    metrics,
    metrics_export,
    metrics_report,
)
from .history import _remember
from .responses import _cache_stats, _error, _store_stats
from .search_routes import (
    citations,
    health,
    network,
    paper,
    references,
    related,
    search,
    search_author,
    searches,
)
from .state import (
    OfflineMiss,
    _cached,
    _flag,
    _identifier,
    _int,
    _providers,
    _sources,
    _state,
    _store,
    _text,
    setup_state,
    teardown_state,
)

__all__ = [
    "SPAStaticFiles",
    "OfflineMiss",
    "_cache_stats",
    "_cached",
    "_error",
    "_flag",
    "_identifier",
    "_int",
    "_metrics_payload",
    "_papers_from_body",
    "_providers",
    "_remember",
    "_sources",
    "_state",
    "_store",
    "_store_stats",
    "_text",
    "app",
    "cache_clear",
    "cache_info",
    "citations",
    "export",
    "graphml_export",
    "health",
    "import_external",
    "lifespan",
    "merge",
    "metrics",
    "metrics_export",
    "metrics_report",
    "network",
    "paper",
    "quota",
    "references",
    "related",
    "routes",
    "search",
    "search_author",
    "search_delete",
    "search_duplicate",
    "search_export",
    "search_import",
    "search_replay",
    "search_split",
    "searches",
    "setup_state",
    "start",
    "teardown_state",
    "workspace_export",
    "workspace_import",
]
