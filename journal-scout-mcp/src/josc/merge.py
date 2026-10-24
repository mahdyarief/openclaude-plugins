from typing import Dict, List, Optional, Sequence

from .models import Paper
from .utils import normalize_doi, normalize_title

# Sources ranked by how authoritative they are for bibliographic metadata.
# When two sources disagree on a field, the higher-ranked one wins, so the
# merge no longer depends on the arbitrary order results arrive in.
PROVIDER_PRIORITY: Sequence[str] = (
    "scopus",
    "crossref",
    "openalex",
    "semanticscholar",
    "dblp",
    "arxiv",
    "opencitations",
    "unpaywall",
)


def dedup_key(paper: Paper) -> str:
    doi = normalize_doi(paper.doi)
    if doi:
        return f"doi:{doi}"
    return f"title:{normalize_title(paper.title)}"


def _author_token(authors: Sequence[str]) -> str:
    """Normalized first-author name, used as a weak secondary merge key."""
    return normalize_title(authors[0]) if authors else ""


def _match_keys(paper: Paper) -> List[tuple]:
    """Every identity a record can be recognised by, strongest first.

    A DOI is authoritative. When it is missing, records are matched by
    ``(title, year)`` and — failing a year — by ``(title, first author)``, so a
    DOI-less record still folds into its better-described twin instead of
    showing up as a duplicate.
    """
    keys: List[tuple] = []
    doi = normalize_doi(paper.doi)
    if doi:
        keys.append(("doi", doi))
    title = normalize_title(paper.title)
    if title and paper.year is not None:
        keys.append(("title", title, paper.year))
    author = _author_token(paper.authors)
    if title and author:
        keys.append(("author", title, author))
    return keys


def _priority(sources: Sequence[str]) -> int:
    rank = len(PROVIDER_PRIORITY)
    for source in sources:
        if source in PROVIDER_PRIORITY:
            rank = min(rank, PROVIDER_PRIORITY.index(source))
    return rank


def _ranked(a: Paper, b: Paper) -> "tuple[Paper, Paper]":
    return (a, b) if _priority(a.sources) <= _priority(b.sources) else (b, a)


def _pick_text(preferred: Optional[str], fallback: Optional[str]) -> Optional[str]:
    return preferred or fallback or None


def _merge_authors(a: Paper, b: Paper) -> List[str]:
    """Union both author lists, preserving order and dropping duplicates."""
    merged: List[str] = []
    seen: set[str] = set()
    for name in a.authors + b.authors:
        key = normalize_title(name)
        if key and key not in seen:
            seen.add(key)
            merged.append(name)
    return merged


def _longest(*values: Optional[str]) -> Optional[str]:
    present = [value for value in values if value]
    return max(present, key=len) if present else None


def merge_two(a: Paper, b: Paper) -> Paper:
    preferred, fallback = _ranked(a, b)
    counts = [c for c in (a.citation_count, b.citation_count) if c is not None]
    sources: List[str] = []
    for source in a.sources + b.sources:
        if source not in sources:
            sources.append(source)
    ids = dict(a.ids)
    ids.update(b.ids)
    return Paper(
        doi=normalize_doi(_pick_text(a.doi, b.doi)),
        title=_pick_text(preferred.title, fallback.title) or "",
        abstract=_longest(a.abstract, b.abstract),
        year=preferred.year or fallback.year,
        authors=_merge_authors(a, b),
        venue=_pick_text(preferred.venue, fallback.venue),
        citation_count=max(counts) if counts else None,
        url=_pick_text(preferred.url, fallback.url),
        pdf_url=_pick_text(preferred.pdf_url, fallback.pdf_url),
        is_open_access=a.is_open_access if a.is_open_access is not None else b.is_open_access,
        type=_pick_text(preferred.type, fallback.type),
        sources=sources,
        ids=ids,
    )


def merge_papers(papers: List[Paper]) -> List[Paper]:
    """Merge duplicates keyed by DOI, falling back to ``(title, year)``.

    Records that share *any* identity are folded together, so a DOI-less
    record joins its DOI-bearing twin instead of showing up as a duplicate.
    """
    clusters: List[Optional[Paper]] = []
    index: Dict[tuple, int] = {}
    for paper in papers:
        keys = _match_keys(paper)
        targets = sorted({index[key] for key in keys if key in index})
        if not targets:
            idx = len(clusters)
            clusters.append(paper)
        else:
            idx = targets[0]
            merged = clusters[idx]
            for other in targets[1:]:
                merged = merge_two(merged, clusters[other])
                for key, value in list(index.items()):
                    if value == other:
                        index[key] = idx
                clusters[other] = None
            clusters[idx] = merge_two(merged, paper)
        for key in keys:
            index[key] = idx
    result = [c for c in clusters if c is not None]
    result.sort(key=lambda p: (-(p.citation_count or 0), -(p.year or 0), p.title or ""))
    return result
