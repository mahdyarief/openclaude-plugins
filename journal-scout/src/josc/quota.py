from typing import Any, Dict

# Static documented limits. No provider exposes a queryable quota endpoint,
# so used/remaining/reset stay None and this module never touches the network.
_LIMITS: Dict[str, Dict[str, str]] = {
    "scopus": {
        "limit": "Weekly quota, tracked via X-RateLimit-* / X-ELS-Status headers",
        "notes": "Elsevier exposes no quota endpoint; a 429 with QUOTA_EXCEEDED means the weekly quota is spent.",
    },
    "openalex": {
        "limit": "100,000 requests/day (polite pool)",
        "notes": "Include a polite mailto in the request to use the polite pool.",
    },
    "semanticscholar": {
        "limit": "1 request/second shared pool",
        "notes": "An API key raises the shared rate limit.",
    },
    "crossref": {
        "limit": "Polite pool, no hard cap",
        "notes": "Include a polite mailto to use the polite pool.",
    },
    "pubmed": {
        "limit": "3 requests/second without a key, 10 with",
        "notes": "An NCBI API key raises the rate limit to 10 requests/second.",
    },
    "arxiv": {
        "limit": "1 request per 3 seconds",
        "notes": "arXiv asks clients to space requests and avoid bulk scraping.",
    },
    "dblp": {
        "limit": "Best effort, no published quota",
        "notes": "No published quota; throttle conservatively.",
    },
    "opencitations": {
        "limit": "180 requests/minute",
        "notes": "Shared rate limit across all OpenCitations APIs.",
    },
    "unpaywall": {
        "limit": "100,000 requests/day",
        "notes": "Requires an email parameter on every request.",
    },
}

_UNDOCUMENTED = {
    "limit": "Not documented",
    "notes": "No published rate limit for this source.",
}


def _entry(name: str) -> Dict[str, Any]:
    info = _LIMITS.get(name, _UNDOCUMENTED)
    return {
        "source": name,
        "limit": info["limit"],
        "used": None,
        "remaining": None,
        "reset": None,
        "notes": info["notes"],
    }


def quota_report(providers: list) -> Dict[str, Any]:
    sources: Dict[str, Any] = {}
    for provider in providers:
        name = getattr(provider, "name", None)
        if not isinstance(name, str) or not name:
            continue
        sources[name] = _entry(name)
    return {"sources": sources}
