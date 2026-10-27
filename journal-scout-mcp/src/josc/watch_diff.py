"""Pure helpers for saved-search watches.

A watch stores the query that produced a result set and remembers which papers
it has already reported. Nothing here touches storage or the network, so the
diff and feed behaviour can be tested in isolation.
"""

import hashlib
import json
from typing import Any, Dict, List, Optional, Sequence, Set
from xml.sax.saxutils import escape

from .utils import normalize_doi, normalize_title


def watch_fingerprint(
    query: str,
    author: Optional[str],
    sources: Optional[List[str]],
    filters: Optional[Dict[str, Any]],
) -> str:
    """Return a stable identity for one watch definition."""
    payload = {
        "query": query or "",
        "author": author or "",
        "sources": sorted(sources or []),
        "filters": filters or {},
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _paper_key(paper: Dict[str, Any]) -> str:
    doi = normalize_doi(paper.get("doi"))
    if doi:
        return f"doi:{doi}"
    return f"title:{normalize_title(paper.get('title'))}"


def result_keys(results: Sequence[Dict[str, Any]]) -> Set[str]:
    """Return the identity keys for a batch of paper dicts."""
    return {_paper_key(paper) for paper in results}


def diff_results(
    previous: Set[str], current: Sequence[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Return the papers in ``current`` whose keys are not in ``previous``."""
    return [paper for paper in current if _paper_key(paper) not in previous]


def render_rss(title: str, link: str, items: Sequence[Dict[str, Any]]) -> str:
    """Render a minimal RSS 2.0 document for a watch result set."""
    entries: List[str] = []
    for paper in items:
        paper_title = escape(paper.get("title") or "(untitled)")
        paper_link = escape(paper.get("url") or link)
        entries.append(
            "<item>"
            f"<title>{paper_title}</title>"
            f"<link>{paper_link}</link>"
            f"<guid>{paper_link}</guid>"
            "</item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel>'
        f"<title>{escape(title)}</title>"
        f"<link>{escape(link)}</link>"
        "<description>Saved-search watch results</description>"
        + "".join(entries)
        + "</channel></rss>"
    )
