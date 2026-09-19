from typing import List, Optional

from .models import Paper
from .utils import normalize_doi, normalize_title


def dedup_key(paper: Paper) -> str:
    doi = normalize_doi(paper.doi)
    if doi:
        return f"doi:{doi}"
    return f"title:{normalize_title(paper.title)}"


def _pick_text(*values: Optional[str]) -> Optional[str]:
    for value in values:
        if value:
            return value
    return None


def merge_two(a: Paper, b: Paper) -> Paper:
    counts = [c for c in (a.citation_count, b.citation_count) if c is not None]
    sources: List[str] = []
    for source in a.sources + b.sources:
        if source not in sources:
            sources.append(source)
    ids = dict(a.ids)
    ids.update(b.ids)
    return Paper(
        doi=_pick_text(a.doi, b.doi),
        title=_pick_text(a.title, b.title) or "",
        abstract=_pick_text(a.abstract, b.abstract),
        year=a.year or b.year,
        authors=a.authors or b.authors,
        venue=_pick_text(a.venue, b.venue),
        citation_count=max(counts) if counts else None,
        url=_pick_text(a.url, b.url),
        pdf_url=_pick_text(a.pdf_url, b.pdf_url),
        is_open_access=a.is_open_access if a.is_open_access is not None else b.is_open_access,
        type=_pick_text(a.type, b.type),
        sources=sources,
        ids=ids,
    )


def merge_papers(papers: List[Paper]) -> List[Paper]:
    merged: dict[str, Paper] = {}
    for paper in papers:
        key = dedup_key(paper)
        if key in merged:
            merged[key] = merge_two(merged[key], paper)
        else:
            merged[key] = paper
    result = list(merged.values())
    result.sort(key=lambda p: (-(p.citation_count or 0), -(p.year or 0), p.title or ""))
    return result