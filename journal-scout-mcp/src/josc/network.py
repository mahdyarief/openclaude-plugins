"""Citation-network assembly and GraphML serialization.

Every function here is pure: it takes already-fetched :class:`~josc.models.Paper`
records and returns plain dicts. No network access, no I/O.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from xml.sax.saxutils import escape, quoteattr

from .models import Paper
from .utils import normalize_doi, normalize_title

_PROVIDER_ID_KEYS = ("scopus", "openalex", "semanticscholar", "crossref")

# Titles shorter than this are too ambiguous to merge two records on; merging
# on "editorial" or "introduction" would fabricate co-citation links.
_MIN_MERGE_TITLE = 12

def node_id(paper: Paper) -> str:
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

def _node(paper: Paper, kind: str, explicit_id: Optional[str] = None) -> Dict[str, Any]:
    return {
        "id": explicit_id or node_id(paper),
        "label": paper.title or paper.doi or "(untitled)",
        "kind": kind,
        "doi": paper.doi,
        "year": paper.year,
        "authors": paper.authors,
        "venue": paper.venue,
        "citation_count": paper.citation_count,
        "url": paper.url,
        "abstract": paper.abstract,
        "pdf_url": paper.pdf_url,
        "is_open_access": paper.is_open_access,
        "type": paper.type,
        "sources": paper.sources,
    }

def _add_node(
    nodes: Dict[str, Dict[str, Any]],
    paper: Paper,
    kind: str,
    explicit_id: Optional[str] = None,
) -> str:
    resolved = explicit_id or node_id(paper)
    if resolved not in nodes:
        nodes[resolved] = _node(paper, kind, resolved)
    return resolved


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


def _assign_communities(
    nodes: Dict[str, Dict[str, Any]],
    edges: Sequence[Dict[str, Any]],
    max_iterations: int = 20,
) -> int:
    """Label-propagation clustering; writes ``community`` on every node.

    Citation graphs are sparse and unweighted enough that label propagation
    gives useful research clusters cheaply. Ties prefer the node's current
    label so a two-node edge cannot oscillate forever, and labels are
    renumbered by first appearance to keep the output deterministic.
    Returns the number of distinct communities found.
    """
    adjacency: Dict[str, List[Tuple[str, int]]] = {node_id: [] for node_id in nodes}
    for edge in edges:
        source, target = edge["source"], edge["target"]
        weight = edge.get("weight") or 1
        if source in adjacency and target in adjacency:
            adjacency[source].append((target, weight))
            adjacency[target].append((source, weight))

    labels: Dict[str, str] = {node_id: node_id for node_id in nodes}
    for _ in range(max_iterations):
        changed = False
        for node_id in nodes:
            scores: Dict[str, int] = {}
            for neighbour, weight in adjacency[node_id]:
                label = labels[neighbour]
                scores[label] = scores.get(label, 0) + weight
            if not scores:
                continue
            best = max(
                scores.items(),
                key=lambda item: (item[1], item[0] == labels[node_id], item[0]),
            )[0]
            if best != labels[node_id]:
                labels[node_id] = best
                changed = True
        if not changed:
            break

    renumbered: Dict[str, int] = {}
    for node_id in nodes:
        label = labels[node_id]
        if label not in renumbered:
            renumbered[label] = len(renumbered)
        nodes[node_id]["community"] = renumbered[label]
    return len(renumbered)


def build_network(
    seed: Paper,
    references: Sequence[Paper],
    citations: Sequence[Paper],
    citing_references: Optional[Dict[str, Sequence[Paper]]] = None,
    max_nodes: int = 200,
    cocitation_min_weight: int = 2,
    cocitation_max_edges: int = 300,
    reference_references: Optional[Dict[str, Sequence[Paper]]] = None,
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
        (citing_references or {}).get(node_id(citing)) or [] for citing in citations
    ]
    # Second hop: the references of the seed's own references. Fetching these
    # is what turns a star into a chain (A -> B -> C); without them every
    # non-seed node can only ever touch the seed.
    second_hop_lists: List[Sequence[Paper]] = [
        (reference_references or {}).get(node_id(ref)) or [] for ref in references
    ]
    participants: List[Paper] = [seed, *references, *citations]
    for refs in citing_lists:
        participants.extend(refs)
    for refs in second_hop_lists:
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

    if reference_references:
        # Second-hop citation links: ref -> its own references. This is what
        # creates paths that do not pass through the seed.
        for ref, refs in zip(references, second_hop_lists):
            if not refs:
                continue
            ref_id = canonical[id(ref)]
            if ref_id not in nodes:
                continue
            for deeper in refs:
                deeper_id = canonical[id(deeper)]
                if deeper_id == ref_id:
                    continue
                if deeper_id not in nodes:
                    if len(nodes) >= max_nodes:
                        continue
                    _add_node(nodes, deeper, "reference", deeper_id)
                _add_edge(edges, ref_id, deeper_id, "cites")

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

    edge_list = [
        {"source": source, "target": target, "type": kind, "weight": weight}
        for (source, target, kind), weight in edges.items()
    ]

    in_degree: Dict[str, int] = {node_id: 0 for node_id in nodes}
    out_degree: Dict[str, int] = {node_id: 0 for node_id in nodes}
    for edge in edge_list:
        if edge["source"] in out_degree:
            out_degree[edge["source"]] += 1
        if edge["target"] in in_degree:
            in_degree[edge["target"]] += 1
    for nid, node in nodes.items():
        node["in_degree"] = in_degree[nid]
        node["out_degree"] = out_degree[nid]
        node["degree"] = in_degree[nid] + out_degree[nid]

    communities = _assign_communities(nodes, edge_list)

    return {
        "seed": seed_id,
        "nodes": list(nodes.values()),
        "edges": edge_list,
        "stats": {
            "nodes": len(nodes),
            "edges": len(edges),
            "references": len(references),
            "citations": len(citations),
            "coupled_edges": sum(1 for _, _, k in edges if k == "coupled"),
            "cocited_edges": sum(1 for _, _, k in edges if k == "cocited"),
            "communities": communities,
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
