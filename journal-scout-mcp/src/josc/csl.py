"""Map a paper dict to a CSL-JSON item.

This is not a full CSL implementation. It supports the elements needed to
render a journal-article reference list: author, issued, title,
container-title, DOI, volume, issue, page and URL. Styles that rely on
conditional ``cs:choose`` trees or nested ``cs:names`` substitution are out of
scope and will render incorrectly.
"""

from typing import Any, Dict, Sequence

from .utils import normalize_doi, normalize_title


class CSLStyleError(ValueError):
    """Raised when a citation style specification is invalid."""


def _split_name(name: str) -> Dict[str, str]:
    parts = (name or "").strip().split()
    if not parts:
        return {"family": "", "given": ""}
    if len(parts) == 1:
        return {"family": parts[0], "given": ""}
    return {"family": parts[-1], "given": " ".join(parts[:-1])}


def paper_to_csl(paper: Dict[str, Any]) -> Dict[str, Any]:
    doi = normalize_doi(paper.get("doi"))
    title = paper.get("title") or ""
    item: Dict[str, Any] = {
        "type": "article-journal",
        "id": doi or normalize_title(title),
        "title": title,
    }
    if doi:
        item["DOI"] = doi
    if paper.get("venue"):
        item["container-title"] = paper["venue"]
    if paper.get("url"):
        item["URL"] = paper["url"]
    year = paper.get("year")
    if year is not None:
        item["issued"] = {"date-parts": [[int(year)]]}
    authors: Sequence[str] = paper.get("authors") or []
    if authors:
        item["author"] = [_split_name(name) for name in authors]
    return item
