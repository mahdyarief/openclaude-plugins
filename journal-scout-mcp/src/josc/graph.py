"""Citation-network construction and bibliometric metrics.

The functions here are pure: they take already-fetched :class:`Paper`
records and return plain dicts, so they can be unit-tested without any
network access. Orchestration lives in :mod:`josc.aggregator`.
"""

from __future__ import annotations

from datetime import date
from math import sqrt
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from xml.sax.saxutils import escape, quoteattr

from .models import Paper
from .utils import normalize_doi, normalize_title

_PROVIDER_ID_KEYS = ("scopus", "openalex", "semanticscholar", "crossref")

# Titles shorter than this are too ambiguous to merge two records on; merging
# on "editorial" or "introduction" would fabricate co-citation links.
_MIN_MERGE_TITLE = 12


def _node_id(paper: Paper) -> str:
    """Stable identifier for a node.

    DOI is preferred because every provider exposes it; when absent we fall
    back to a provider id and finally to a normalized title.
    """
    doi = normalize_doi(paper.doi)
    if doi:
        return f"doi:{doi}"
    for key in ("scopus", "openalex", "semanticscholar", "crossref"):
        value = paper.ids.get(key)
        if value:
            return f"{key}:{value}"
    return f"title:{normalize_title(paper.title)}"


def _node(paper: Paper, kind: str, node_id: Optional[str] = None) -> Dict[str, Any]:
    return {
        "id": node_id or _node_id(paper),
        "label": paper.title or paper.doi or "(untitled)",
        "kind": kind,
        "doi": paper.doi,
        "year": paper.year,
        "authors": paper.authors,
        "venue": paper.venue,
        "citation_count": paper.citation_count,
        "url": paper.url,
        "sources": paper.sources,
    }


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


def _add_node(
    nodes: Dict[str, Dict[str, Any]],
    paper: Paper,
    kind: str,
    node_id: Optional[str] = None,
) -> str:
    node_id = node_id or _node_id(paper)
    if node_id not in nodes:
        nodes[node_id] = _node(paper, kind, node_id)
    return node_id


def _add_edge(
    edges: Dict[Tuple[str, str, str], int], source: str, target: str, kind: str, weight: int = 1
) -> None:
    if source == target:
        return
    key = (source, target, kind)
    edges[key] = edges.get(key, 0) + weight


def _record_keys(paper: Paper) -> List[str]:
    """Every identity a record can be recognised by across sources."""
    keys: List[str] = []
    doi = normalize_doi(paper.doi)
    if doi:
        keys.append(f"doi:{doi}")
    title = normalize_title(paper.title)
    if title:
        keys.append(f"title:{title}")
    for name in _PROVIDER_ID_KEYS:
        value = paper.ids.get(name)
        if value:
            keys.append(f"{name}:{value}")
    return keys


def _is_mergeable_key(key: str) -> bool:
    """Whether two records sharing ``key`` may be assumed to be the same work.

    Short titles ("editorial", "introduction") collide across unrelated
    papers, so they identify a node but must not merge two records.
    """
    if not key.startswith("title:"):
        return True
    return len(key[len("title:") :]) >= _MIN_MERGE_TITLE


def _key_rank(key: str) -> Tuple[int, str]:
    """Sort order for choosing a component's canonical name: DOI first."""
    scheme = key.split(":", 1)[0]
    if scheme == "doi":
        return (0, key)
    if scheme in _PROVIDER_ID_KEYS:
        return (1, key)
    if scheme == "title":
        return (2, key)
    return (3, key)


def _canonical_ids(papers: Sequence[Paper]) -> Dict[int, str]:
    """Map ``id(paper)`` to one canonical node id per real work.

    Scopus returns references without DOIs while OpenAlex/Crossref describe
    the same works with one, so counting co-citation on raw ids sees two
    unrelated nodes and the weight never reaches 2. Union-find over DOI, title
    and provider ids collapses those aliases; each component is then named
    after its most authoritative key.
    """
    parent: Dict[str, str] = {}

    def find(key: str) -> str:
        parent.setdefault(key, key)
        root = key
        while parent[root] != root:
            root = parent[root]
        while parent[key] != root:
            parent[key], key = root, parent[key]
        return root

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    anchors: Dict[int, str] = {}
    for paper in papers:
        keys = _record_keys(paper) or [f"record:{id(paper)}"]
        anchor = next((key for key in keys if _is_mergeable_key(key)), keys[0])
        anchors[id(paper)] = anchor
        for key in keys:
            find(key)
            if key is not anchor and _is_mergeable_key(key):
                union(anchor, key)

    members: Dict[str, List[str]] = {}
    for key in parent:
        members.setdefault(find(key), []).append(key)

    canonical_by_key: Dict[str, str] = {}
    for group in members.values():
        canonical = min(group, key=_key_rank)
        for key in group:
            canonical_by_key[key] = canonical

    return {paper_id: canonical_by_key[anchor] for paper_id, anchor in anchors.items()}


def _record_quality(paper: Paper) -> Tuple[int, int, int]:
    return (
        1 if normalize_doi(paper.doi) else 0,
        len(paper.title or ""),
        paper.citation_count or 0,
    )


def _representatives(
    papers: Sequence[Paper], canonical: Dict[int, str]
) -> Dict[str, Paper]:
    """Best-described record for each canonical node id."""
    best: Dict[str, Paper] = {}
    for paper in papers:
        node_id = canonical[id(paper)]
        current = best.get(node_id)
        if current is None or _record_quality(paper) > _record_quality(current):
            best[node_id] = paper
    return best


def build_network(
    seed: Paper,
    references: Sequence[Paper],
    citations: Sequence[Paper],
    citing_references: Optional[Dict[str, Sequence[Paper]]] = None,
    max_nodes: int = 200,
    cocitation_min_weight: int = 2,
    cocitation_max_edges: int = 300,
) -> Dict[str, Any]:
    """Assemble a Connected-Papers-style network around ``seed``.

    Three edge types are produced:

    ``cites``
        Direct citation links (seed -> its references, citing papers -> seed).
    ``coupled``
        Bibliographic coupling between the seed and each citing paper, i.e.
        how many references they share.
    ``cocited``
        Co-citation between reference pairs that appear together in the
        reference lists of the fetched citing papers.
    """
    nodes: Dict[str, Dict[str, Any]] = {}
    edges: Dict[Tuple[str, str, str], int] = {}

    # Every record that takes part in the graph, so one work that providers
    # describe differently (DOI in one list, Scopus id in another) resolves to
    # a single node before any edge is counted.
    citing_lists: List[Sequence[Paper]] = [
        (citing_references or {}).get(_node_id(citing)) or [] for citing in citations
    ]
    participants: List[Paper] = [seed, *references, *citations]
    for refs in citing_lists:
        participants.extend(refs)
    canonical = _canonical_ids(participants)
    representatives = _representatives(participants, canonical)

    seed_id = _add_node(nodes, seed, "seed", canonical[id(seed)])

    seed_ref_ids: Set[str] = set()
    for ref in references:
        if len(nodes) >= max_nodes:
            break
        ref_id = _add_node(nodes, ref, "reference", canonical[id(ref)])
        seed_ref_ids.add(ref_id)
        _add_edge(edges, seed_id, ref_id, "cites")

    for citing in citations:
        if len(nodes) >= max_nodes:
            break
        citing_id = _add_node(nodes, citing, "citation", canonical[id(citing)])
        _add_edge(edges, citing_id, seed_id, "cites")

    if citing_references:
        # Co-citation counts across the reference lists of citing papers.
        # Pairs are counted before any node budget is applied: gating the
        # count on the budget would make the weight-2 threshold unreachable as
        # soon as the first citing paper consumed every remaining node slot.
        cocited: Dict[Tuple[str, str], int] = {}
        for citing, refs in zip(citations, citing_lists):
            citing_id = canonical[id(citing)]
            unique = sorted({canonical[id(ref)] for ref in refs})
            for i, left in enumerate(unique):
                for right in unique[i + 1 :]:
                    cocited[(left, right)] = cocited.get((left, right), 0) + 1
            # Bibliographic coupling: shared references with the seed.
            shared = len(set(unique) & seed_ref_ids)
            if shared:
                _add_edge(edges, citing_id, seed_id, "coupled", shared)

        # Co-citation grows quadratically with reference-list length: a single
        # citing paper with 50 references yields 1,225 pairs. Keep only pairs
        # corroborated by more than one citing paper and cap the total, so the
        # browser is not asked to render thousands of near-noise edges.
        strongest = sorted(
            (
                (pair, weight)
                for pair, weight in cocited.items()
                if weight >= cocitation_min_weight
            ),
            key=lambda item: (-item[1], item[0]),
        )[:cocitation_max_edges]

        # Materialise endpoints only for pairs that survived pruning, and only
        # while the node budget allows. Endpoints are collected in weight order
        # so the strongest pairs get the remaining slots.
        endpoint_ids: List[str] = []
        for (left, right), _ in strongest:
            for ref_id in (left, right):
                if ref_id not in nodes and ref_id not in endpoint_ids:
                    endpoint_ids.append(ref_id)
        remaining = max(0, max_nodes - len(nodes))
        materialised = endpoint_ids[:remaining]
        # Endpoints that were already present (e.g. a seed reference) are valid
        # too; only endpoints dropped by the node budget must suppress the edge.
        kept = set(nodes) | set(materialised)
        for ref_id in materialised:
            paper = representatives.get(ref_id)
            if paper is not None:
                _add_node(nodes, paper, "cocited", ref_id)
        for (left, right), weight in strongest:
            if left in kept and right in kept:
                _add_edge(edges, left, right, "cocited", weight)

    return {
        "seed": seed_id,
        "nodes": list(nodes.values()),
        "edges": [
            {"source": source, "target": target, "type": kind, "weight": weight}
            for (source, target, kind), weight in edges.items()
        ],
        "stats": {
            "nodes": len(nodes),
            "edges": len(edges),
            "references": len(references),
            "citations": len(citations),
            "coupled_edges": sum(1 for _, _, k in edges if k == "coupled"),
            "cocited_edges": sum(1 for _, _, k in edges if k == "cocited"),
        },
    }


def to_graphml(network: Dict[str, Any]) -> str:
    """Serialize a network dict to GraphML for VOSviewer/Gephi import."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns"',
        '         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        '         xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns '
        'http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">',
        '  <key id="label" for="node" attr.name="label" attr.type="string"/>',
        '  <key id="kind" for="node" attr.name="kind" attr.type="string"/>',
        '  <key id="year" for="node" attr.name="year" attr.type="int"/>',
        '  <key id="citations" for="node" attr.name="citations" attr.type="int"/>',
        '  <key id="doi" for="node" attr.name="doi" attr.type="string"/>',
        '  <key id="weight" for="edge" attr.name="weight" attr.type="int"/>',
        '  <key id="type" for="edge" attr.name="type" attr.type="string"/>',
        '  <graph id="citation-network" edgedefault="directed">',
    ]
    for node in network.get("nodes", []):
        lines.append(f"    <node id={quoteattr(str(node['id']))}>")
        lines.append(f'      <data key="label">{escape(str(node.get("label") or ""))}</data>')
        lines.append(f'      <data key="kind">{escape(str(node.get("kind") or ""))}</data>')
        if node.get("year") is not None:
            lines.append(f'      <data key="year">{int(node["year"])}</data>')
        if node.get("citation_count") is not None:
            lines.append(f'      <data key="citations">{int(node["citation_count"])}</data>')
        if node.get("doi"):
            lines.append(f'      <data key="doi">{escape(str(node["doi"]))}</data>')
        lines.append("    </node>")
    for index, edge in enumerate(network.get("edges", [])):
        lines.append(
            f"    <edge id=\"e{index}\" source={quoteattr(str(edge['source']))} "
            f"target={quoteattr(str(edge['target']))}>"
        )
        lines.append(f'      <data key="weight">{int(edge.get("weight") or 1)}</data>')
        lines.append(f'      <data key="type">{escape(str(edge.get("type") or ""))}</data>')
        lines.append("    </edge>")
    lines.append("  </graph>")
    lines.append("</graphml>")
    return "\n".join(lines)
