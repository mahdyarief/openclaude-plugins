from typing import Dict, List, Optional, Sequence

from .dedup import same_work
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


def _union(*lists: Sequence[str]) -> List[str]:
    """Order-preserving union, so each provider contributes what it knows."""
    merged: List[str] = []
    for values in lists:
        for value in values:
            if value and value not in merged:
                merged.append(value)
    return merged


def _merge_citation_counts(*maps: Dict[int, int]) -> Dict[int, int]:
    merged: Dict[int, int] = {}
    for mapping in maps:
        for year, count in mapping.items():
            merged[year] = max(merged.get(year, 0), count)
    return merged


def _merge_retracted(a: Optional[bool], b: Optional[bool]) -> Optional[bool]:
    # A retraction notice from any source is authoritative; absence of a flag
    # elsewhere must not clear it.
    if a or b:
        return True
    if a is False or b is False:
        return False
    return None


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
        isbn=_pick_text(preferred.isbn, fallback.isbn),
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
        is_retracted=_merge_retracted(a.is_retracted, b.is_retracted),
        cited_by_percentile=(
            preferred.cited_by_percentile
            if preferred.cited_by_percentile is not None
            else fallback.cited_by_percentile
        ),
        citations_by_year=_merge_citation_counts(a.citations_by_year, b.citations_by_year),
        topics=_union(a.topics, b.topics),
        keywords=_union(a.keywords, b.keywords),
        institutions=_union(a.institutions, b.institutions),
        funders=_union(a.funders, b.funders),
        publication_types=_union(a.publication_types, b.publication_types),
        language=_pick_text(preferred.language, fallback.language),
        license=_pick_text(preferred.license, fallback.license),
        tldr=_pick_text(preferred.tldr, fallback.tldr),
    )


def merge_papers(papers: List[Paper]) -> List[Paper]:
    """Merge records that describe the same work.

    Identical normalized DOIs always merge. Everything else is bucketed by
    normalized title and then filtered through :func:`josc.dedup.same_work`, so
    two unrelated works that happen to share a title stay separate.
    """
    parent = list(range(len(papers)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    by_doi: Dict[str, int] = {}
    for index, paper in enumerate(papers):
        doi = normalize_doi(paper.doi)
        if not doi:
            continue
        if doi in by_doi:
            union(index, by_doi[doi])
        else:
            by_doi[doi] = index

    by_title: Dict[str, List[int]] = {}
    for index, paper in enumerate(papers):
        title = normalize_title(paper.title)
        if not title:
            continue
        for other in by_title.get(title, []):
            if same_work(papers[index], papers[other]):
                union(index, other)
        by_title.setdefault(title, []).append(index)

    groups: Dict[int, List[int]] = {}
    for index in range(len(papers)):
        groups.setdefault(find(index), []).append(index)

    merged: List[Paper] = []
    for indices in groups.values():
        combined = papers[indices[0]]
        for other in indices[1:]:
            combined = merge_two(combined, papers[other])
        merged.append(combined)

    merged.sort(key=lambda p: (-(p.citation_count or 0), -(p.year or 0), p.title or ""))
    return merged
