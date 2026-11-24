"""Corpus-level bibliometric analysis (science mapping) over Paper records.

Everything here is pure: it takes :class:`~josc.models.Paper` records and
returns plain dicts. No network access, no I/O, no third-party dependencies.

The indicators follow the definitions popularised by bibliometrix (Aria &
Cuccurullo, 2017) and VOSviewer, re-implemented from the original papers:

* Annual growth rate, collaboration index (Elango & Rajendran, 2012).
* Bradford's law of scattering (Bradford, 1934).
* Lotka's law of author productivity (Lotka, 1926), K-S test after Pao (1985).
* Co-occurrence, co-citation (Small, 1973) and bibliographic coupling
  (Kessler, 1963) networks, association strength (van Eck & Waltman, 2009).
* Louvain community detection (Blondel et al., 2008).
* Thematic map: Callon centrality and density (Callon et al., 1991;
  Cobo et al., 2011) over the equivalence index.
* Burst detection: Kleinberg's two-state batched automaton (Kleinberg, 2002).
* Reference Publication Year Spectroscopy (Marx et al., 2014).

Authors are identified by normalised name, so homonyms merge and spelling
variants split; callers should say so when they report author-level results.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from itertools import combinations
from math import log, log10, pi, sqrt
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .models import Paper

FIELDS = ("authors", "keywords", "topics", "countries", "institutions", "venue", "references")

# The labels bibliometrix uses for Callon's strategic diagram quadrants.
QUADRANTS = {
    (True, True): "motor",
    (False, True): "niche",
    (False, False): "emerging_or_declining",
    (True, False): "basic",
}


# --------------------------------------------------------------------------
# Field access
# --------------------------------------------------------------------------

def _norm(value: str) -> str:
    return " ".join(str(value).split()).casefold()


def _raw_items(paper: Paper, field: str) -> List[str]:
    if field not in FIELDS:
        raise ValueError(f"Unknown field {field!r}; expected one of {', '.join(FIELDS)}.")
    if field == "venue":
        return [paper.venue] if paper.venue else []
    return [value for value in getattr(paper, field) or [] if value]


class _Vocabulary:
    """Maps normalised keys back to the most frequent original spelling."""

    def __init__(self) -> None:
        self._spellings: Dict[str, Counter] = defaultdict(Counter)

    def add(self, raw: str) -> str:
        key = _norm(raw)
        self._spellings[key][str(raw).strip()] += 1
        return key

    def label(self, key: str) -> str:
        spellings = self._spellings.get(key)
        if not spellings:
            return key
        return max(spellings.items(), key=lambda item: (item[1], item[0]))[0]


def _document_items(
    papers: Sequence[Paper], field: str, vocabulary: Optional[_Vocabulary] = None
) -> List[List[str]]:
    """Per-paper de-duplicated normalised items for ``field``."""
    vocabulary = vocabulary if vocabulary is not None else _Vocabulary()
    documents: List[List[str]] = []
    for paper in papers:
        seen: List[str] = []
        for raw in _raw_items(paper, field):
            key = vocabulary.add(raw)
            if key and key not in seen:
                seen.append(key)
        documents.append(seen)
    return documents


def _citations(paper: Paper) -> int:
    return paper.citation_count or 0


def _round(value: float, digits: int = 3) -> float:
    return round(float(value), digits)


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _quantile(values: Sequence[float], q: float) -> float:
    """Linear-interpolated quantile (R type 7, the R and NumPy default)."""
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


# --------------------------------------------------------------------------
# Descriptive indicators
# --------------------------------------------------------------------------

def annual_production(papers: Iterable[Paper]) -> List[Dict[str, Any]]:
    """Papers and citations per publication year, with gap years filled in."""
    per_year: Dict[int, List[Paper]] = defaultdict(list)
    for paper in papers:
        if paper.year:
            per_year[paper.year].append(paper)
    if not per_year:
        return []
    rows = []
    for year in range(min(per_year), max(per_year) + 1):
        members = per_year.get(year, [])
        rows.append({
            "year": year,
            "papers": len(members),
            "citations": sum(_citations(p) for p in members),
        })
    return rows


def annual_growth_rate(papers: Iterable[Paper]) -> Optional[float]:
    """Compound annual growth rate of output, in percent.

    ``((N_last / N_first) ** (1 / (years - 1)) - 1) * 100``, as bibliometrix
    reports it. ``None`` when the corpus spans a single year or the first
    year is empty (the ratio is undefined).
    """
    rows = annual_production(papers)
    if len(rows) < 2 or rows[0]["papers"] == 0:
        return None
    ratio = rows[-1]["papers"] / rows[0]["papers"]
    return _round((ratio ** (1.0 / (len(rows) - 1)) - 1.0) * 100.0, 2)


def corpus_summary(papers: Sequence[Paper], current_year: Optional[int] = None) -> Dict[str, Any]:
    """The 'Main information' table: size, timespan, impact, collaboration."""
    current_year = current_year or date.today().year
    years = [p.year for p in papers if p.year]
    author_docs = _document_items(papers, "authors")
    authors = Counter(a for doc in author_docs for a in doc)
    single = [doc for doc in author_docs if len(doc) == 1]
    multi = [doc for doc in author_docs if len(doc) > 1]
    single_authors = {doc[0] for doc in single}
    with_countries = [p for p in papers if p.countries]
    international = [p for p in with_countries if len(set(p.countries)) > 1]
    ages = [max(current_year - y, 0) for y in years]
    per_year_citations = [
        _citations(p) / max(current_year - p.year + 1, 1) for p in papers if p.year
    ]
    keyword_docs = _document_items(papers, "keywords")
    references = [r for p in papers for r in p.references]
    types = Counter(p.type for p in papers if p.type)
    open_access = [p for p in papers if p.is_open_access is not None]

    summary: Dict[str, Any] = {
        "documents": len(papers),
        "timespan": [min(years), max(years)] if years else None,
        "sources": len({_norm(p.venue) for p in papers if p.venue}),
        "annual_growth_rate_pct": annual_growth_rate(papers),
        "average_document_age": _round(sum(ages) / len(ages), 2) if ages else None,
        "average_citations_per_document": (
            _round(sum(_citations(p) for p in papers) / len(papers), 2) if papers else 0.0
        ),
        "average_citations_per_year_per_document": (
            _round(sum(per_year_citations) / len(per_year_citations), 3)
            if per_year_citations else None
        ),
        "total_citations": sum(_citations(p) for p in papers),
        "references": len(references),
        "unique_references": len(set(references)),
        "keywords": len({k for doc in keyword_docs for k in doc}),
        "authors": len(authors),
        "author_appearances": sum(authors.values()),
        "authors_of_single_authored_documents": len(single_authors),
        "single_authored_documents": len(single),
        "co_authors_per_document": (
            _round(sum(len(d) for d in author_docs) / len(author_docs), 2) if author_docs else 0.0
        ),
        # Elango & Rajendran: authors of multi-authored docs / multi-authored docs.
        "collaboration_index": (
            _round(sum(len(d) for d in multi) / len(multi), 2) if multi else None
        ),
        "international_co_authorship_pct": (
            _round(100.0 * len(international) / len(with_countries), 2)
            if with_countries else None
        ),
        "open_access_pct": (
            _round(100.0 * sum(1 for p in open_access if p.is_open_access) / len(open_access), 2)
            if open_access else None
        ),
        "document_types": dict(types.most_common()),
        "coverage": {
            "year": len(years),
            "keywords": sum(1 for d in keyword_docs if d),
            "countries": len(with_countries),
            "references": sum(1 for p in papers if p.references),
            "citation_count": sum(1 for p in papers if p.citation_count is not None),
        },
    }
    if years and max(years) >= current_year:
        summary["note"] = (
            f"{current_year} is still in progress, so its output is partial and "
            "depresses the annual growth rate."
        )
    return summary


def top_items(papers: Sequence[Paper], field: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Most frequent values of ``field`` with documents, citations and h-index.

    For ``authors`` it also reports fractionalised counts (each paper split
    evenly among its authors), which removes the bias toward large teams.
    """
    vocabulary = _Vocabulary()
    documents = _document_items(papers, field, vocabulary)
    stats: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"documents": 0, "citations": 0, "fractional": 0.0, "counts": [], "years": []}
    )
    for paper, items in zip(papers, documents):
        for item in items:
            entry = stats[item]
            entry["documents"] += 1
            entry["citations"] += _citations(paper)
            entry["fractional"] += 1.0 / len(items)
            entry["counts"].append(_citations(paper))
            if paper.year:
                entry["years"].append(paper.year)
    ranked = sorted(stats.items(), key=lambda kv: (-kv[1]["documents"], -kv[1]["citations"], kv[0]))
    rows = []
    for key, entry in ranked[: max(limit, 0)]:
        ordered = sorted(entry["counts"], reverse=True)
        h = sum(1 for position, value in enumerate(ordered, start=1) if value >= position)
        row = {
            "name": vocabulary.label(key),
            "documents": entry["documents"],
            "citations": entry["citations"],
            "h_index": h,
            "first_year": min(entry["years"]) if entry["years"] else None,
        }
        if field == "authors":
            row["fractional_documents"] = _round(entry["fractional"], 2)
        rows.append(row)
    return rows


def country_production(papers: Sequence[Paper], limit: int = 20) -> List[Dict[str, Any]]:
    """Documents per country, split into single- and multiple-country papers.

    A paper counts once for every country among its authors (full counting).
    SCP papers have one country, MCP papers more than one; the MCP ratio is
    the usual internationalisation indicator.
    """
    stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"documents": 0, "scp": 0, "mcp": 0, "citations": 0})
    for paper in papers:
        countries = sorted({c.upper() for c in paper.countries if c})
        for country in countries:
            entry = stats[country]
            entry["documents"] += 1
            entry["citations"] += _citations(paper)
            entry["mcp" if len(countries) > 1 else "scp"] += 1
    ranked = sorted(stats.items(), key=lambda kv: (-kv[1]["documents"], kv[0]))
    return [
        {
            "country": country,
            **entry,
            "mcp_ratio": _round(entry["mcp"] / entry["documents"], 3),
        }
        for country, entry in ranked[: max(limit, 0)]
    ]


def country_collaboration(papers: Sequence[Paper], limit: int = 30) -> List[Dict[str, Any]]:
    """Country pairs that co-author, by number of shared papers."""
    pairs: Counter = Counter()
    for paper in papers:
        countries = sorted({c.upper() for c in paper.countries if c})
        pairs.update(combinations(countries, 2))
    return [
        {"from": a, "to": b, "documents": n}
        for (a, b), n in sorted(pairs.items(), key=lambda kv: (-kv[1], kv[0]))[: max(limit, 0)]
    ]


# --------------------------------------------------------------------------
# Bibliometric laws
# --------------------------------------------------------------------------

def bradford_law(papers: Sequence[Paper]) -> Dict[str, Any]:
    """Split sources into three Bradford zones holding a third of papers each.

    Sources are ranked by paper count; zone 1 (the core) is the smallest set
    of top sources whose cumulative output reaches a third of the corpus.
    """
    vocabulary = _Vocabulary()
    counts: Counter = Counter()
    for paper in papers:
        if paper.venue:
            counts[vocabulary.add(paper.venue)] += 1
    total = sum(counts.values())
    if not total:
        return {"sources": [], "zones": [], "core_sources": [], "papers_with_source": 0}
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    rows = []
    cumulative = 0
    for rank, (key, n) in enumerate(ranked, start=1):
        # Zone is decided by where the source *starts* in the cumulative
        # distribution, so the source that crosses a boundary stays in the
        # lower zone, matching bibliometrix.
        start = cumulative
        cumulative += n
        zone = 1 if start < total / 3 else 2 if start < 2 * total / 3 else 3
        rows.append({"rank": rank, "source": vocabulary.label(key), "papers": n,
                     "cumulative": cumulative, "zone": zone})
    zones = []
    for zone in (1, 2, 3):
        members = [r for r in rows if r["zone"] == zone]
        zones.append({"zone": zone, "sources": len(members),
                      "papers": sum(r["papers"] for r in members)})
    core = [z["sources"] for z in zones if z["sources"]]
    multiplier = None
    if len(core) == 3 and core[0] and core[1]:
        multiplier = _round((core[1] / core[0] + core[2] / core[1]) / 2, 2)
    return {
        "papers_with_source": total,
        "zones": zones,
        "bradford_multiplier": multiplier,
        "core_sources": [r for r in rows if r["zone"] == 1],
        "sources": rows,
    }


def lotka_law(papers: Sequence[Paper]) -> Dict[str, Any]:
    """Author productivity distribution against Lotka's inverse-square law.

    Fits ``log10(authors) = log10(C) - beta * log10(documents)`` by least
    squares, and runs a Kolmogorov-Smirnov test of the observed proportions
    against classic Lotka (beta = 2, C = 6 / pi^2). The 0.01 critical value
    is ``1.63 / sqrt(n_authors)``.
    """
    productivity = Counter(a for doc in _document_items(papers, "authors") for a in doc)
    if not productivity:
        return {"distribution": [], "authors": 0}
    distribution = Counter(productivity.values())
    n_authors = sum(distribution.values())
    xs = sorted(distribution)
    classic_c = 6.0 / (pi ** 2)
    rows = []
    cumulative_observed = cumulative_expected = 0.0
    ks = 0.0
    for x in xs:
        observed = distribution[x] / n_authors
        expected = classic_c / (x ** 2)
        cumulative_observed += observed
        cumulative_expected += expected
        ks = max(ks, abs(cumulative_observed - cumulative_expected))
        rows.append({
            "documents_written": x,
            "authors": distribution[x],
            "proportion": _round(observed, 4),
            "lotka_expected": _round(expected, 4),
        })
    result: Dict[str, Any] = {
        "authors": n_authors,
        "distribution": rows,
        "ks_statistic": _round(ks, 4),
        "ks_critical_0_01": _round(1.63 / sqrt(n_authors), 4),
    }
    result["fits_classic_lotka"] = result["ks_statistic"] <= result["ks_critical_0_01"]
    if len(xs) >= 2:
        lx = [log10(x) for x in xs]
        ly = [log10(distribution[x] / n_authors) for x in xs]
        mx, my = sum(lx) / len(lx), sum(ly) / len(ly)
        sxx = sum((a - mx) ** 2 for a in lx)
        sxy = sum((a - mx) * (b - my) for a, b in zip(lx, ly))
        syy = sum((b - my) ** 2 for b in ly)
        slope = sxy / sxx if sxx else 0.0
        result["beta"] = _round(-slope, 3)
        result["constant"] = _round(10 ** (my - slope * mx), 4)
        result["r_squared"] = _round((sxy * sxy) / (sxx * syy), 3) if sxx and syy else None
    else:
        result["note"] = "Every author wrote the same number of documents; no slope to fit."
    return result


# --------------------------------------------------------------------------
# Community detection
# --------------------------------------------------------------------------

def louvain(
    nodes: Sequence[str], edges: Iterable[Tuple[str, str, float]]
) -> Dict[str, int]:
    """Deterministic Louvain modularity clustering of a weighted undirected graph.

    Returns ``{node: community}`` with communities numbered by size
    (largest first). Isolated nodes get their own community.
    """
    adjacency: Dict[Any, Dict[Any, float]] = {n: {} for n in nodes}
    for a, b, w in edges:
        if a == b or a not in adjacency or b not in adjacency or w <= 0:
            continue
        adjacency[a][b] = adjacency[a].get(b, 0.0) + w
        adjacency[b][a] = adjacency[b].get(a, 0.0) + w

    membership: Dict[str, Any] = {n: n for n in nodes}
    order = {n: i for i, n in enumerate(nodes)}
    while True:
        level = _louvain_level(adjacency, order)
        if level is None:
            break
        membership = {n: level[c] for n, c in membership.items()}
        adjacency, order = _aggregate(adjacency, level)

    sizes = Counter(membership.values())
    first_seen: Dict[Any, int] = {}
    for n in nodes:
        first_seen.setdefault(membership[n], len(first_seen))
    ranking = sorted(sizes, key=lambda c: (-sizes[c], first_seen[c]))
    renumber = {c: i for i, c in enumerate(ranking)}
    return {n: renumber[membership[n]] for n in nodes}


def _louvain_level(
    adjacency: Dict[Any, Dict[Any, float]], order: Dict[Any, int]
) -> Optional[Dict[Any, Any]]:
    """One pass of local moves; ``None`` when no node changes community."""
    degree = {
        n: sum(w for m, w in nbrs.items() if m != n) + 2 * nbrs.get(n, 0.0)
        for n, nbrs in adjacency.items()
    }
    m2 = sum(degree.values())
    if m2 <= 0:
        return None
    community = {n: n for n in adjacency}
    total = dict(degree)
    nodes = sorted(adjacency, key=lambda n: order[n])
    moved = False
    for _ in range(100):
        improved = False
        for node in nodes:
            current = community[node]
            k = degree[node]
            links: Dict[Any, float] = defaultdict(float)
            for neighbour, w in adjacency[node].items():
                if neighbour != node:
                    links[community[neighbour]] += w
            total[current] -= k
            best, best_gain = current, links.get(current, 0.0) - total[current] * k / m2
            for candidate in sorted(links, key=lambda c: order[c]):
                gain = links[candidate] - total[candidate] * k / m2
                if gain > best_gain + 1e-12:
                    best, best_gain = candidate, gain
            total[best] += k
            if best != current:
                community[node] = best
                improved = moved = True
        if not improved:
            break
    return community if moved else None


def _aggregate(
    adjacency: Dict[Any, Dict[Any, float]], community: Dict[Any, Any]
) -> Tuple[Dict[Any, Dict[Any, float]], Dict[Any, int]]:
    """Collapse each community into one node, keeping internal weight as a self-loop."""
    merged: Dict[Any, Dict[Any, float]] = defaultdict(lambda: defaultdict(float))
    for node, nbrs in adjacency.items():
        cn = community[node]
        merged[cn]  # keep isolated communities
        for neighbour, w in nbrs.items():
            cm = community[neighbour]
            if neighbour == node:
                merged[cn][cn] += w
            elif cn == cm:
                merged[cn][cn] += w / 2.0
            else:
                merged[cn][cm] += w
    order: Dict[Any, int] = {}
    for node in adjacency:
        order.setdefault(community[node], len(order))
    return {k: dict(v) for k, v in merged.items()}, order


# --------------------------------------------------------------------------
# Networks
# --------------------------------------------------------------------------

def _pair_counts(documents: Sequence[Sequence[str]]) -> Counter:
    pairs: Counter = Counter()
    for items in documents:
        pairs.update(combinations(sorted(set(items)), 2))
    return pairs


def _build_graph(
    occurrences: Counter,
    pairs: Counter,
    label: Callable[[str], str],
    kind: str,
    edge_type: str,
    min_occurrences: int,
    min_edge_weight: int,
    max_nodes: int,
    max_edges: int,
    extra: Optional[Callable[[str], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    keep = [
        key for key, n in sorted(occurrences.items(), key=lambda kv: (-kv[1], kv[0]))
        if n >= min_occurrences
    ][: max(max_nodes, 0)]
    kept = set(keep)
    edges = []
    for (a, b), weight in pairs.items():
        if a in kept and b in kept and weight >= min_edge_weight:
            association = weight / (occurrences[a] * occurrences[b]) if occurrences[a] and occurrences[b] else 0.0
            edges.append({"source": a, "target": b, "weight": weight, "type": edge_type,
                          "association_strength": _round(association, 5)})
    edges.sort(key=lambda e: (-e["weight"], e["source"], e["target"]))
    dropped_edges = max(len(edges) - max_edges, 0)
    communities = louvain(keep, ((e["source"], e["target"], e["weight"]) for e in edges))
    edges = edges[: max(max_edges, 0)]
    degree: Counter = Counter()
    strength: Counter = Counter()
    for e in edges:
        degree[e["source"]] += 1
        degree[e["target"]] += 1
        strength[e["source"]] += e["weight"]
        strength[e["target"]] += e["weight"]
    nodes = []
    for key in keep:
        node = {"id": key, "label": label(key), "kind": kind, "occurrences": occurrences[key],
                "degree": degree[key], "strength": strength[key], "community": communities[key]}
        if extra:
            node.update(extra(key))
        nodes.append(node)
    possible = len(keep) * (len(keep) - 1) / 2
    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "nodes": len(nodes),
            "edges": len(edges),
            "edges_dropped": dropped_edges,
            "communities": len(set(communities.values())),
            "density": _round(len(edges) / possible, 4) if possible else 0.0,
        },
    }


def co_occurrence_network(
    papers: Sequence[Paper],
    field: str = "keywords",
    min_occurrences: int = 2,
    min_edge_weight: int = 1,
    max_nodes: int = 50,
    max_edges: int = 300,
) -> Dict[str, Any]:
    """Undirected network of items that appear together in the same paper.

    ``field='authors'`` gives co-authorship, ``'countries'`` country
    collaboration, ``'keywords'`` co-word analysis, ``'institutions'``
    institutional collaboration. Edge ``weight`` is the number of shared
    papers; ``association_strength`` is VOSviewer's normalised similarity.
    """
    vocabulary = _Vocabulary()
    documents = _document_items(papers, field, vocabulary)
    occurrences = Counter(item for doc in documents for item in doc)
    kinds = {"authors": "co_authorship", "countries": "country_collaboration",
             "institutions": "institution_collaboration"}
    return _build_graph(occurrences, _pair_counts(documents), vocabulary.label,
                        kind=field, edge_type=kinds.get(field, "co_occurrence"),
                        min_occurrences=min_occurrences, min_edge_weight=min_edge_weight,
                        max_nodes=max_nodes, max_edges=max_edges)


def co_citation_network(
    papers: Sequence[Paper],
    labels: Optional[Dict[str, Dict[str, Any]]] = None,
    min_citations: int = 2,
    min_edge_weight: int = 2,
    max_nodes: int = 50,
    max_edges: int = 300,
) -> Dict[str, Any]:
    """Network of cited references that are cited together by corpus papers.

    ``labels`` maps a reference id to metadata (``label``, ``year``,
    ``doi``) resolved by the caller; unresolved references keep their id.
    Node ``occurrences`` is the local citation count within the corpus.
    """
    labels = labels or {}
    documents = [list(dict.fromkeys(p.references)) for p in papers]
    occurrences = Counter(ref for doc in documents for ref in doc)

    def extra(key: str) -> Dict[str, Any]:
        meta = labels.get(key) or {}
        return {k: meta[k] for k in ("year", "doi", "title") if meta.get(k) is not None}

    return _build_graph(occurrences, _pair_counts(documents),
                        lambda key: (labels.get(key) or {}).get("label") or key,
                        kind="reference", edge_type="co_citation",
                        min_occurrences=min_citations, min_edge_weight=min_edge_weight,
                        max_nodes=max_nodes, max_edges=max_edges, extra=extra)


def _paper_key(paper: Paper, index: int) -> str:
    return paper.doi or paper.ids.get("openalex") or f"paper-{index}"


def bibliographic_coupling_network(
    papers: Sequence[Paper],
    min_shared: int = 1,
    max_nodes: int = 50,
    max_edges: int = 300,
) -> Dict[str, Any]:
    """Network of corpus papers linked by the references they share.

    Edge ``weight`` is the number of shared references; ``salton`` is the
    cosine-normalised coupling strength ``shared / sqrt(|R_a| * |R_b|)``.
    The ``max_nodes`` most-cited papers that carry references are kept.
    """
    candidates = [(i, p) for i, p in enumerate(papers) if p.references]
    candidates.sort(key=lambda ip: (-_citations(ip[1]), ip[0]))
    candidates = candidates[: max(max_nodes, 0)]
    keys = {i: _paper_key(p, i) for i, p in candidates}
    refsets = {i: set(p.references) for i, p in candidates}
    edges = []
    for (i, _), (j, _) in combinations(candidates, 2):
        shared = len(refsets[i] & refsets[j])
        if shared >= min_shared:
            edges.append({"source": keys[i], "target": keys[j], "weight": shared,
                          "type": "bibliographic_coupling",
                          "salton": _round(shared / sqrt(len(refsets[i]) * len(refsets[j])), 4)})
    edges.sort(key=lambda e: (-e["weight"], e["source"], e["target"]))
    dropped = max(len(edges) - max_edges, 0)
    communities = louvain([keys[i] for i, _ in candidates],
                          ((e["source"], e["target"], e["weight"]) for e in edges))
    edges = edges[: max(max_edges, 0)]
    degree: Counter = Counter()
    for e in edges:
        degree[e["source"]] += 1
        degree[e["target"]] += 1
    nodes = []
    for i, paper in candidates:
        key = keys[i]
        first = paper.authors[0].split()[-1] if paper.authors else "Anon"
        nodes.append({"id": key, "label": f"{first} ({paper.year or 'n.d.'})", "kind": "paper",
                      "title": paper.title, "year": paper.year, "doi": paper.doi,
                      "citation_count": paper.citation_count, "references": len(refsets[i]),
                      "degree": degree[key], "community": communities[key]})
    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {"nodes": len(nodes), "edges": len(edges), "edges_dropped": dropped,
                  "communities": len(set(communities.values())),
                  "papers_without_references": len(papers) - sum(1 for p in papers if p.references)},
    }


# --------------------------------------------------------------------------
# Thematic map and topic dynamics
# --------------------------------------------------------------------------

def thematic_map(
    papers: Sequence[Paper],
    field: str = "keywords",
    min_occurrences: int = 2,
    max_terms: int = 250,
    terms_per_theme: int = 5,
) -> Dict[str, Any]:
    """Callon strategic diagram of keyword clusters.

    Keywords are clustered with Louvain over the co-occurrence network.
    Links are weighted by the equivalence index ``e_ij = c_ij^2 / (c_i c_j)``.
    Per cluster, centrality = 10 * sum of external link weights (how strongly
    the theme connects to the rest of the field) and density = 100 * internal
    link weight / number of terms (how developed it is internally). Themes are
    placed in quadrants around the median centrality and density.
    """
    vocabulary = _Vocabulary()
    documents = _document_items(papers, field, vocabulary)
    occurrences = Counter(item for doc in documents for item in doc)
    terms = [k for k, n in sorted(occurrences.items(), key=lambda kv: (-kv[1], kv[0]))
             if n >= min_occurrences][: max(max_terms, 0)]
    kept = set(terms)
    equivalence: Dict[Tuple[str, str], float] = {}
    for (a, b), c in _pair_counts(documents).items():
        if a in kept and b in kept:
            equivalence[(a, b)] = c * c / (occurrences[a] * occurrences[b])
    if not equivalence:
        return {"themes": [], "note": "Not enough co-occurring terms to build a thematic map."}
    clusters = louvain(terms, ((a, b, w) for (a, b), w in equivalence.items()))
    members: Dict[int, List[str]] = defaultdict(list)
    for term in terms:
        members[clusters[term]].append(term)
    internal: Counter = Counter()
    external: Counter = Counter()
    for (a, b), w in equivalence.items():
        ca, cb = clusters[a], clusters[b]
        if ca == cb:
            internal[ca] += w
        else:
            external[ca] += w
            external[cb] += w
    term_docs: Dict[str, set] = defaultdict(set)
    for index, doc in enumerate(documents):
        for item in doc:
            if item in kept:
                term_docs[item].add(index)
    themes = []
    for cluster, words in members.items():
        if len(words) < 2:
            continue  # a lone keyword is not a theme
        docs = set().union(*(term_docs[w] for w in words))
        years = [papers[i].year for i in docs if papers[i].year]
        themes.append({
            "cluster": cluster,
            "label": " / ".join(vocabulary.label(w) for w in words[:3]),
            "terms": [{"term": vocabulary.label(w), "occurrences": occurrences[w]}
                      for w in words[:terms_per_theme]],
            "size": len(words),
            "frequency": sum(occurrences[w] for w in words),
            "documents": len(docs),
            "median_year": _median(years) if years else None,
            "centrality": _round(10.0 * external[cluster], 4),
            "density": _round(100.0 * internal[cluster] / len(words), 4),
        })
    if not themes:
        return {"themes": [], "note": "Every cluster held a single term; lower min_occurrences."}
    c_median = _median([t["centrality"] for t in themes])
    d_median = _median([t["density"] for t in themes])
    for theme in themes:
        theme["quadrant"] = QUADRANTS[(theme["centrality"] >= c_median, theme["density"] >= d_median)]
    themes.sort(key=lambda t: (-t["frequency"], t["cluster"]))
    return {
        "field": field,
        "centrality_median": _round(c_median, 4),
        "density_median": _round(d_median, 4),
        "quadrant_meaning": {
            "motor": "high centrality, high density: well-developed and central to the field",
            "niche": "low centrality, high density: well-developed but isolated",
            "emerging_or_declining": "low centrality, low density: marginal, new or fading",
            "basic": "high centrality, low density: transversal, general themes",
        },
        "themes": themes,
    }


def trend_topics(
    papers: Sequence[Paper],
    field: str = "keywords",
    min_frequency: int = 3,
    per_year: int = 3,
) -> Dict[str, Any]:
    """When each term was used: first quartile, median and third quartile year.

    Keeps the ``per_year`` most frequent terms whose median year falls in
    each year, which is how bibliometrix draws its trend-topics chart.
    """
    vocabulary = _Vocabulary()
    documents = _document_items(papers, field, vocabulary)
    years_by_term: Dict[str, List[int]] = defaultdict(list)
    for paper, items in zip(papers, documents):
        if paper.year:
            for item in items:
                years_by_term[item].append(paper.year)
    rows = []
    for term, years in years_by_term.items():
        if len(years) < min_frequency:
            continue
        rows.append({
            "term": vocabulary.label(term),
            "frequency": len(years),
            "year_q1": _round(_quantile(years, 0.25), 1),
            "year_median": _round(_quantile(years, 0.5), 1),
            "year_q3": _round(_quantile(years, 0.75), 1),
        })
    by_year: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_year[int(row["year_median"])].append(row)
    selected = []
    for year in sorted(by_year):
        bucket = sorted(by_year[year], key=lambda r: (-r["frequency"], r["term"]))
        selected.extend(bucket[: max(per_year, 0)])
    return {"field": field, "min_frequency": min_frequency, "terms": selected}


def _kleinberg_batched(
    relevant: Sequence[int], totals: Sequence[int], s: float, gamma: float
) -> List[int]:
    """Viterbi path of Kleinberg's two-state batched burst automaton."""
    n = len(totals)
    r_sum, d_sum = sum(relevant), sum(totals)
    if n == 0 or d_sum == 0 or r_sum == 0 or r_sum == d_sum:
        return [0] * n
    p0 = r_sum / d_sum
    p1 = min(s * p0, 0.9999)
    if p1 <= p0:
        return [0] * n

    def cost(p: float, r: int, d: int) -> float:
        # The binomial coefficient is identical in both states; drop it.
        return -(r * log(p) + (d - r) * log(1.0 - p)) if d else 0.0

    up = gamma * log(n)
    inf = float("inf")
    best = [0.0, inf]
    back: List[Tuple[int, int]] = []
    for r, d in zip(relevant, totals):
        c0, c1 = cost(p0, r, d), cost(p1, r, d)
        from0 = (best[0], 0) if best[0] <= best[1] else (best[1], 1)
        from1 = (best[0] + up, 0) if best[0] + up <= best[1] else (best[1], 1)
        best = [from0[0] + c0, from1[0] + c1]
        back.append((from0[1], from1[1]))
    state = 0 if best[0] <= best[1] else 1
    path = [0] * n
    for t in range(n - 1, -1, -1):
        path[t] = state
        state = back[t][state]
    return path


def burst_detection(
    papers: Sequence[Paper],
    field: str = "keywords",
    min_frequency: int = 3,
    s: float = 2.0,
    gamma: float = 1.0,
    limit: int = 20,
) -> Dict[str, Any]:
    """Terms whose share of yearly output jumped for a sustained period.

    Runs Kleinberg's batched two-state model per term: each year's batch is
    the papers published that year, the 'relevant' ones carry the term. ``s``
    is how much higher the burst rate is than the base rate; ``gamma`` makes
    entering a burst more expensive. Burst ``weight`` is the cost saved by
    the burst state, CiteSpace's burst strength.
    """
    vocabulary = _Vocabulary()
    documents = _document_items(papers, field, vocabulary)
    dated = [(p.year, items) for p, items in zip(papers, documents) if p.year]
    if not dated:
        return {"bursts": [], "note": "No dated papers."}
    first, last = min(y for y, _ in dated), max(y for y, _ in dated)
    years = list(range(first, last + 1))
    totals = Counter(y for y, _ in dated)
    term_years: Dict[str, Counter] = defaultdict(Counter)
    for year, items in dated:
        for item in items:
            term_years[item][year] += 1
    d = [totals[y] for y in years]
    bursts = []
    for term, counts in term_years.items():
        if sum(counts.values()) < min_frequency:
            continue
        r = [counts[y] for y in years]
        path = _kleinberg_batched(r, d, s, gamma)
        p0 = sum(r) / sum(d)
        p1 = min(s * p0, 0.9999)
        t = 0
        while t < len(years):
            if path[t] != 1:
                t += 1
                continue
            start = t
            weight = 0.0
            while t < len(years) and path[t] == 1:
                rt, dt = r[t], d[t]
                if dt:
                    c0 = -(rt * log(p0) + (dt - rt) * log(1 - p0))
                    c1 = -(rt * log(p1) + (dt - rt) * log(1 - p1))
                    weight += c0 - c1
                t += 1
            bursts.append({"term": vocabulary.label(term), "start": years[start],
                           "end": years[t - 1], "weight": _round(weight, 3),
                           "frequency": sum(r)})
    bursts.sort(key=lambda b: (-b["weight"], b["term"]))
    return {"field": field, "s": s, "gamma": gamma, "bursts": bursts[: max(limit, 0)]}


def rpys(reference_years: Dict[int, int], peaks: int = 5) -> Dict[str, Any]:
    """Reference Publication Year Spectroscopy.

    ``reference_years`` maps a cited-reference publication year to how many
    times references from that year are cited by the corpus. Each year's
    deviation is measured from the five-year median centred on it
    (t-2..t+2); positive peaks mark historical roots of the field.
    """
    if not reference_years:
        return {"spectrum": [], "peaks": []}
    first, last = min(reference_years), max(reference_years)
    years = list(range(first, last + 1))
    counts = [reference_years.get(y, 0) for y in years]
    spectrum = []
    for i, year in enumerate(years):
        window = counts[max(i - 2, 0): i + 3]
        median = _median(window)
        spectrum.append({"year": year, "references": counts[i],
                         "median_5y": median, "deviation": _round(counts[i] - median, 1)})
    top = sorted((row for row in spectrum if row["deviation"] > 0),
                 key=lambda row: (-row["deviation"], row["year"]))[: max(peaks, 0)]
    return {"spectrum": spectrum, "peaks": sorted(top, key=lambda row: row["year"])}


def three_field(
    papers: Sequence[Paper],
    left: str = "authors",
    middle: str = "keywords",
    right: str = "venue",
    limit: int = 10,
) -> Dict[str, Any]:
    """Sankey data linking the top items of three fields (three-field plot).

    Keeps the ``limit`` most frequent items per field and counts how many
    papers carry each left-middle and middle-right pair.
    """
    vocabularies = {f: _Vocabulary() for f in (left, middle, right)}
    per_field = {f: _document_items(papers, f, vocabularies[f]) for f in (left, middle, right)}
    tops: Dict[str, List[str]] = {}
    for f, docs in per_field.items():
        counts = Counter(i for doc in docs for i in doc)
        tops[f] = [k for k, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]]
    nodes = []
    for position, f in enumerate((left, middle, right)):
        for key in tops[f]:
            nodes.append({"id": f"{f}:{key}", "label": vocabularies[f].label(key),
                          "field": f, "column": position})
    links: Counter = Counter()
    for index in range(len(papers)):
        for a_field, b_field in ((left, middle), (middle, right)):
            a_items = [i for i in per_field[a_field][index] if i in tops[a_field]]
            b_items = [i for i in per_field[b_field][index] if i in tops[b_field]]
            for a in a_items:
                for b in b_items:
                    links[(f"{a_field}:{a}", f"{b_field}:{b}")] += 1
    return {
        "fields": [left, middle, right],
        "nodes": nodes,
        "links": [{"source": a, "target": b, "value": v}
                  for (a, b), v in sorted(links.items(), key=lambda kv: (-kv[1], kv[0]))],
    }


def to_pajek(network: Dict[str, Any]) -> str:
    """Serialise an undirected network to Pajek ``.net`` (VOSviewer, Gephi, Pajek)."""
    nodes = network.get("nodes", [])
    index = {node["id"]: i for i, node in enumerate(nodes, start=1)}
    lines = [f"*Vertices {len(nodes)}"]
    for node in nodes:
        label = str(node.get("label") or node["id"]).replace('"', "'")
        lines.append(f'{index[node["id"]]} "{label}"')
    lines.append("*Edges")
    for edge in network.get("edges", []):
        if edge["source"] in index and edge["target"] in index:
            lines.append(f'{index[edge["source"]]} {index[edge["target"]]} {edge.get("weight", 1)}')
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# One-call report
# --------------------------------------------------------------------------

ANALYSES = (
    "summary", "annual_production", "sources", "authors", "institutions",
    "countries", "keywords", "bradford", "lotka", "networks", "thematic_map",
    "trend_topics", "bursts", "rpys", "three_field",
)
NETWORKS = (
    "co_authorship", "keyword_co_occurrence", "country_collaboration",
    "institution_collaboration", "co_citation", "bibliographic_coupling",
)
_NETWORK_FIELDS = {
    "co_authorship": "authors",
    "keyword_co_occurrence": "keywords",
    "country_collaboration": "countries",
    "institution_collaboration": "institutions",
}


def reference_label(meta: Dict[str, Any]) -> str:
    """'Surname (Year) Title…' for a resolved cited reference."""
    authors = meta.get("authors") or []
    first = authors[0].split()[-1] if authors else "Anon"
    title = (meta.get("title") or "").strip()
    if len(title) > 60:
        title = title[:57].rstrip() + "…"
    return f"{first} ({meta.get('year') or 'n.d.'}) {title}".strip()


def analyze(
    papers: Sequence[Paper],
    analyses: Optional[Sequence[str]] = None,
    networks: Optional[Sequence[str]] = None,
    keyword_field: str = "keywords",
    top: int = 10,
    max_nodes: int = 50,
    max_edges: int = 300,
    min_occurrences: int = 2,
    reference_meta: Optional[Dict[str, Dict[str, Any]]] = None,
    current_year: Optional[int] = None,
) -> Dict[str, Any]:
    """Run the selected analyses over ``papers`` and collect them in one dict.

    ``reference_meta`` maps a cited-reference id to resolved metadata
    (``title``, ``year``, ``authors``, ``doi``); it feeds co-citation labels
    and RPYS. Analyses that lack the data they need say so under ``notes``
    instead of returning misleading zeros.
    """
    selected = list(analyses or ANALYSES)
    unknown = [a for a in selected if a not in ANALYSES]
    if unknown:
        raise ValueError(f"Unknown analyses {unknown}; expected any of {', '.join(ANALYSES)}.")
    if keyword_field not in ("keywords", "topics"):
        raise ValueError("keyword_field must be 'keywords' or 'topics'.")
    reference_meta = reference_meta or {}
    notes: List[str] = []
    report: Dict[str, Any] = {}
    have_refs = any(p.references for p in papers)
    have_countries = any(p.countries for p in papers)
    have_keywords = any(_raw_items(p, keyword_field) for p in papers)

    if "summary" in selected:
        report["summary"] = corpus_summary(papers, current_year=current_year)
    if "annual_production" in selected:
        report["annual_production"] = annual_production(papers)
    for name, field in (("sources", "venue"), ("authors", "authors"),
                        ("institutions", "institutions"), ("keywords", keyword_field)):
        if name in selected:
            report[f"top_{name}"] = top_items(papers, field, limit=top)
    if "countries" in selected:
        if have_countries:
            report["countries"] = {
                "production": country_production(papers, limit=top * 2),
                "collaboration": country_collaboration(papers, limit=top * 3),
            }
        else:
            notes.append("countries: no country data; it comes from OpenAlex authorships.")
    if "bradford" in selected:
        bradford = bradford_law(papers)
        bradford["sources"] = bradford["sources"][: max(top * 3, 30)]
        report["bradford"] = bradford
    if "lotka" in selected:
        report["lotka"] = lotka_law(papers)
    if "networks" in selected:
        built: Dict[str, Any] = {}
        labels = {k: {**v, "label": reference_label(v)} for k, v in reference_meta.items()}
        for kind in networks or NETWORKS:
            if kind not in NETWORKS:
                raise ValueError(f"Unknown network {kind!r}; expected any of {', '.join(NETWORKS)}.")
            if kind in _NETWORK_FIELDS:
                field = _NETWORK_FIELDS[kind]
                if field == "keywords":
                    field = keyword_field
                built[kind] = co_occurrence_network(
                    papers, field, min_occurrences=min_occurrences,
                    max_nodes=max_nodes, max_edges=max_edges)
            elif not have_refs:
                notes.append(f"{kind}: no reference lists; only OpenAlex records carry them.")
            elif kind == "co_citation":
                built[kind] = co_citation_network(
                    papers, labels=labels, min_citations=min_occurrences,
                    max_nodes=max_nodes, max_edges=max_edges)
            else:
                built[kind] = bibliographic_coupling_network(
                    papers, max_nodes=max_nodes, max_edges=max_edges)
        report["networks"] = built
    keyword_analyses = [a for a in ("thematic_map", "trend_topics", "bursts") if a in selected]
    if keyword_analyses and not have_keywords:
        notes.append(f"{', '.join(keyword_analyses)}: no {keyword_field} on these records; "
                     "try keyword_field='topics'.")
    elif keyword_analyses:
        if "thematic_map" in selected:
            report["thematic_map"] = thematic_map(papers, keyword_field, min_occurrences=min_occurrences)
        if "trend_topics" in selected:
            report["trend_topics"] = trend_topics(papers, keyword_field,
                                                  min_frequency=max(min_occurrences, 2))
        if "bursts" in selected:
            report["bursts"] = burst_detection(papers, keyword_field,
                                               min_frequency=max(min_occurrences, 2), limit=top * 2)
    if "rpys" in selected:
        if not have_refs:
            notes.append("rpys: no reference lists; only OpenAlex records carry them.")
        else:
            years: Counter = Counter()
            cited = Counter(r for p in papers for r in dict.fromkeys(p.references))
            resolved = 0
            for ref, count in cited.items():
                year = (reference_meta.get(ref) or {}).get("year")
                if year:
                    years[int(year)] += count
                    resolved += count
            result = rpys(dict(years))
            total = sum(cited.values())
            result["citations_resolved"] = resolved
            result["citations_total"] = total
            result["coverage_pct"] = _round(100.0 * resolved / total, 1) if total else 0.0
            if total and resolved < total:
                notes.append(
                    f"rpys: years known for {resolved}/{total} cited references (the most "
                    "frequently cited ones), so rare references are under-counted.")
            report["rpys"] = result
    if "three_field" in selected:
        right = "countries" if have_countries else "venue"
        report["three_field"] = three_field(papers, "authors", keyword_field, right, limit=top)
    report["notes"] = notes + [
        "Authors are matched by normalised name: homonyms merge and spelling variants split."
    ]
    return report
