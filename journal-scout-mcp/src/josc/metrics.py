"""Bibliometric metrics computed from already-fetched paper records.

Every function here is pure: it takes :class:`~josc.models.Paper` records or
plain citation counts and returns numbers. No network access, no I/O.
"""
from __future__ import annotations

from datetime import date
from math import sqrt
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from .models import Paper

def h_index(counts: Sequence[int]) -> int:
    """Largest h such that the top h papers have at least h citations each."""
    ranked = sorted((c for c in counts if c is not None and c > 0), reverse=True)
    h = 0
    for position, value in enumerate(ranked, start=1):
        if value >= position:
            h = position
        else:
            break
    return h


def i10_index(counts: Sequence[int]) -> int:
    """Number of papers cited at least ten times."""
    return sum(1 for c in counts if c is not None and c >= 10)


def g_index(counts: Sequence[int]) -> int:
    """Largest g such that the top g papers together have g^2 citations."""
    ranked = sorted((c for c in counts if c is not None and c > 0), reverse=True)
    total = 0
    g = 0
    for position, value in enumerate(ranked, start=1):
        total += value
        if total >= position * position:
            g = position
    return g


def citation_velocity(
    papers: Iterable[Paper], current_year: Optional[int] = None
) -> Optional[float]:
    """Mean citations per year since the earliest publication year.

    This mirrors the "citation velocity" reported by Publish or Perish:
    total citations divided by the span of years covered by the works.
    """
    papers = list(papers)
    years = [p.year for p in papers if p.year]
    if not years:
        return None
    now = current_year or date.today().year
    span = max(1, now - min(years) + 1)
    total = sum(p.citation_count or 0 for p in papers)
    return round(total / span, 3)


def e_index(counts: Sequence[int]) -> float:
    """e-index: sqrt of the citation tail above the h-core.

    Only the top h counts form the h-core; the surplus of those counts over
    h**2 is the tail measured by the e-index.
    """
    ranked = sorted((c for c in counts if c is not None and c > 0), reverse=True)
    h = h_index(ranked)
    if h == 0:
        return 0.0
    surplus = sum(ranked[:h]) - h * h
    if surplus <= 0:
        return 0.0
    return round(sqrt(surplus), 3)


def awcr(papers: Iterable[Paper], current_year: Optional[int] = None) -> float:
    """Age-Weighted Citation Rate: citations discounted by paper age."""
    now = current_year or date.today().year
    total = 0.0
    for paper in papers:
        if not paper.year:
            continue
        age = max(1, now - paper.year + 1)
        total += (paper.citation_count or 0) / age
    return round(total, 3)


def aw_index(papers: Iterable[Paper], current_year: Optional[int] = None) -> float:
    """AW-index: square root of the age-weighted citation rate."""
    return round(sqrt(awcr(papers, current_year)), 3)


def _unique_authors(papers: Sequence[Paper]) -> Set[str]:
    return {name for paper in papers for name in paper.authors}


def hc_index(
    counts: Sequence[int],
    papers: Sequence[Paper],
    current_year: Optional[int] = None,
    recent_years: int = 5,
) -> int:
    """Contemporary h-index over papers published in the last N years."""
    now = current_year or date.today().year
    recent = [
        count
        for count, paper in zip(counts, papers)
        if paper.year and now - paper.year < recent_years
    ]
    return h_index(recent)


def hI_index(papers: Iterable[Paper]) -> float:
    """Individual h-index (Batista et al., 2006).

    The plain h-index divided by the mean number of authors of the papers
    that make up the h-core.
    """
    ranked = sorted(papers, key=lambda p: p.citation_count or 0, reverse=True)
    h = h_index([p.citation_count or 0 for p in ranked])
    if h == 0:
        return 0.0
    core_authors = [len(p.authors) if p.authors else 1 for p in ranked[:h]]
    return round(h / (sum(core_authors) / h), 3)


def hI_norm(papers: Iterable[Paper]) -> int:
    """Publish-or-Perish's normalised individual h-index.

    Each paper's citation count is divided by its author count first, then
    the h-index is taken over those reduced counts.
    """
    contributions = []
    for paper in papers:
        authors = len(paper.authors) if paper.authors else 1
        contributions.append(int(round((paper.citation_count or 0) / authors)))
    return h_index(contributions)


def hm_index(papers: Iterable[Paper]) -> float:
    """Schreiber's hm-index: fractional paper counts as effective rank.

    Papers are ranked by citation count and each contributes ``1/a`` to the
    effective rank. The hm-index is the largest effective rank at which the
    paper at that position still has at least that many citations.
    """
    ranked = sorted(papers, key=lambda p: p.citation_count or 0, reverse=True)
    effective = 0.0
    hm = 0.0
    for paper in ranked:
        citations = paper.citation_count or 0
        if citations <= 0:
            break
        effective += 1.0 / (len(paper.authors) if paper.authors else 1)
        if citations < effective:
            break
        hm = effective
    return round(hm, 3)


def citations_by_year(papers: Iterable[Paper]) -> List[Dict[str, Any]]:
    """Per-year publication and citation table, newest year last.

    Mirrors Publish or Perish's "citations per year" table: one row per year
    that has at least one paper, with the number of papers published that
    year, the citations those papers have collected, and a running cumulative
    citation total.
    """
    buckets: Dict[int, Dict[str, int]] = {}
    for paper in papers:
        if not paper.year:
            continue
        row = buckets.setdefault(paper.year, {"papers": 0, "citations": 0})
        row["papers"] += 1
        row["citations"] += paper.citation_count or 0

    table: List[Dict[str, Any]] = []
    cumulative = 0
    for year in sorted(buckets):
        row = buckets[year]
        cumulative += row["citations"]
        table.append(
            {
                "year": year,
                "papers": row["papers"],
                "citations": row["citations"],
                "cumulative_citations": cumulative,
            }
        )
    return table


def compute_metrics(
    papers: Iterable[Paper],
    current_year: Optional[int] = None,
    mode: str = "basic",
    recent_years: int = 5,
) -> Dict[str, Any]:
    """Compute Publish-or-Perish style indicators.

    ``mode="basic"`` returns the historical fields plus the e-index and the
    citation ratios. ``mode="extended"`` additionally returns the contemporary
    h-index, author-weighted indices and age-weighted citation rate.
    """
    if mode not in ("basic", "extended"):
        raise ValueError("mode must be 'basic' or 'extended'")
    papers = list(papers)
    now = current_year or date.today().year
    counts = [p.citation_count or 0 for p in papers]
    total_citations = sum(counts)
    total_authors = sum(len(p.authors) for p in papers)
    unique_authors = _unique_authors(papers)
    years = [p.year for p in papers if p.year]
    year_span = max(years) - min(years) + 1 if years else 0
    paper_count = len(papers)

    metrics: Dict[str, Any] = {
        "papers": paper_count,
        "total_citations": total_citations,
        "h_index": h_index(counts),
        "i10_index": i10_index(counts),
        "g_index": g_index(counts),
        "max_citations": max(counts) if counts else 0,
        "mean_citations": round(total_citations / paper_count, 3) if counts else 0.0,
        "citation_velocity": citation_velocity(papers, now),
        "e_index": e_index(counts),
        "cites_year": round(total_citations / max(1, year_span), 3),
        "cites_paper": round(total_citations / max(1, paper_count), 3),
        "cites_author": round(total_citations / max(1, total_authors), 3),
        "papers_author": round(paper_count / max(1, len(unique_authors)), 3),
        "authors_paper": round(total_authors / max(1, paper_count), 3),
        "by_year": citations_by_year(papers),
    }

    if mode == "extended":
        weighted_rate = awcr(papers, now)
        metrics.update(
            {
                "hc_index": hc_index(counts, papers, now, recent_years),
                "hI_index": hI_index(papers),
                "hI_norm": hI_norm(papers),
                "AWCR": weighted_rate,
                "AW_index": round(sqrt(weighted_rate), 3),
                "AWCRpA": (
                    round(weighted_rate / len(unique_authors), 3)
                    if unique_authors
                    else 0.0
                ),
                "hm_index": hm_index(papers),
            }
        )

    return metrics
