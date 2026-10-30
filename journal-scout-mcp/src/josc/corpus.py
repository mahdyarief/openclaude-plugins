"""Build a searchable corpus from the archive of completed searches.

The archive already stores the results of every recorded search, so building a
corpus needs no provider calls. Records are deduplicated by DOI when present and
by normalized title otherwise, matching the identity rule used elsewhere.
"""

from typing import Any, Dict, List

from .utils import normalize_doi, normalize_title


def _paper_key(paper: Dict[str, Any]) -> str:
    doi = normalize_doi(paper.get("doi"))
    if doi:
        return f"doi:{doi}"
    return f"title:{normalize_title(paper.get('title'))}"


async def load_corpus(archive: Any, limit: int = 20) -> List[Dict[str, Any]]:
    corpus: List[Dict[str, Any]] = []
    seen = set()
    for entry in await archive.list_searches(limit=limit):
        stored = await archive.get_search(entry["id"])
        if not stored:
            continue
        for paper in stored.get("results") or []:
            key = _paper_key(paper)
            if key in seen:
                continue
            seen.add(key)
            corpus.append(paper)
    return corpus
