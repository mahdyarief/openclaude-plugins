"""Keyword-level research landscape: TF-IDF, deterministic k-means, 2D map.

Pure Python by design so the base install stays light. Papers are clustered on
title/abstract/keyword text; cluster names come from c-TF-IDF terms. Everything
is deterministic (stable ordering, fixed seeding) so the same corpus always
yields the same map.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .models import Paper

_TOKEN = re.compile(r"[a-z][a-z0-9]+")
_STOPWORDS = frozenset(
    """a an and are as at be by for from has have in into is it its of on or
    that the their this to using was were with we our can may also than then
    these those such which while within without between over under more most
    some any not no but if so do does did done study studies paper results
    approach method methods based show shows shown propose proposed""".split()
)


def _tokens(text: Optional[str]) -> List[str]:
    if not text:
        return []
    return [t for t in _TOKEN.findall(text.lower()) if len(t) >= 3 and t not in _STOPWORDS]


def _document_terms(paper: Paper) -> List[str]:
    terms: List[str] = []
    terms.extend(_tokens(paper.title) * 2)
    terms.extend(_tokens(paper.abstract))
    for value in list(paper.keywords) + list(paper.topics):
        terms.extend(_tokens(value) * 2)
    return terms


def _tfidf(docs: Sequence[List[str]]) -> List[Dict[str, float]]:
    n = len(docs)
    df: Counter[str] = Counter()
    for terms in docs:
        df.update(set(terms))

    vectors: List[Dict[str, float]] = []
    for terms in docs:
        counts = Counter(terms)
        vector: Dict[str, float] = {}
        for term, count in counts.items():
            tf = 1.0 + math.log(count)
            idf = math.log((1.0 + n) / (1.0 + df[term])) + 1.0
            vector[term] = tf * idf
        norm = math.sqrt(sum(w * w for w in vector.values()))
        if norm:
            vector = {term: weight / norm for term, weight in vector.items()}
        vectors.append(vector)
    return vectors


def _dot(a: Dict[str, float], b: Dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(weight * b.get(term, 0.0) for term, weight in a.items())


def _mean_vector(vectors: List[Dict[str, float]]) -> Dict[str, float]:
    total: Dict[str, float] = {}
    for vector in vectors:
        for term, weight in vector.items():
            total[term] = total.get(term, 0.0) + weight
    if not vectors:
        return {}
    mean = {term: weight / len(vectors) for term, weight in total.items()}
    norm = math.sqrt(sum(w * w for w in mean.values()))
    return {term: weight / norm for term, weight in mean.items()} if norm else mean


def _assign(vectors: List[Dict[str, float]], centroids: List[Dict[str, float]]) -> List[int]:
    labels: List[int] = []
    for vector in vectors:
        best, best_score = 0, -2.0
        for index, centroid in enumerate(centroids):
            score = _dot(vector, centroid)
            if score > best_score:
                best, best_score = index, score
        labels.append(best)
    return labels


def _kmeans(vectors: List[Dict[str, float]], k: int) -> List[int]:
    n = len(vectors)
    if n == 0:
        return []
    k = max(1, min(k, n))

    centroids: List[Dict[str, float]] = [dict(vectors[0])]
    while len(centroids) < k:
        farthest, farthest_score = 0, 2.0
        for index, vector in enumerate(vectors):
            score = max(_dot(vector, centroid) for centroid in centroids)
            if score < farthest_score:
                farthest, farthest_score = index, score
        centroids.append(dict(vectors[farthest]))

    labels = _assign(vectors, centroids)
    for _ in range(100):
        new_centroids = []
        for cluster in range(k):
            members = [vectors[i] for i in range(n) if labels[i] == cluster]
            new_centroids.append(_mean_vector(members) if members else dict(centroids[cluster]))
        new_labels = _assign(vectors, new_centroids)
        if new_labels == labels:
            centroids = new_centroids
            break
        labels, centroids = new_labels, new_centroids

    used = sorted(set(labels))
    remap = {old: new for new, old in enumerate(used)}
    return [remap[label] for label in labels]


def _ctfidf_label(member_terms: List[List[str]], all_cluster_terms: List[Counter[str]], top_n: int = 3) -> str:
    counts: Counter[str] = Counter()
    for terms in member_terms:
        counts.update(terms)
    if not counts:
        return "unlabeled"

    average_words = sum(sum(counter.values()) for counter in all_cluster_terms) / max(1, len(all_cluster_terms))
    scored = []
    for term, count in counts.items():
        cluster_freq = sum(1 for counter in all_cluster_terms if counter.get(term))
        score = (count / sum(counts.values())) * math.log(1.0 + average_words / max(1, cluster_freq))
        scored.append((score, term))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return ", ".join(term for _, term in scored[:top_n])


def _gram(vectors: List[Dict[str, float]]) -> List[List[float]]:
    return [[_dot(a, b) for b in vectors] for a in vectors]


def _power_iteration(matrix: List[List[float]], iterations: int = 100) -> tuple[List[float], float]:
    n = len(matrix)
    if n == 0:
        return [], 0.0
    vector = [1.0 / math.sqrt(n)] * n
    for _ in range(iterations):
        next_vector = [sum(matrix[i][j] * vector[j] for j in range(n)) for i in range(n)]
        norm = math.sqrt(sum(value * value for value in next_vector))
        if norm < 1e-12:
            return vector, 0.0
        vector = [value / norm for value in next_vector]
    eigenvalue = sum(vector[i] * sum(matrix[i][j] * vector[j] for j in range(n)) for i in range(n))
    return vector, eigenvalue


def _coordinates(vectors: List[Dict[str, float]]) -> List[tuple[float, float]]:
    n = len(vectors)
    if n == 0:
        return []
    if n == 1:
        return [(0.0, 0.0)]

    matrix = _gram(vectors)
    first, lambda_one = _power_iteration(matrix)
    deflated = [
        [matrix[i][j] - lambda_one * first[i] * first[j] for j in range(n)]
        for i in range(n)
    ]
    second, lambda_two = _power_iteration(deflated)

    scale_one = math.sqrt(max(lambda_one, 0.0))
    scale_two = math.sqrt(max(lambda_two, 0.0))
    return [
        (
            round(scale_one * first[i], 6),
            round(scale_two * second[i], 6),
        )
        for i in range(n)
    ]


def _top(counter: Counter[str], limit: int = 5) -> List[str]:
    return [value for value, _ in counter.most_common(limit) if value]


def _node_id(paper: Paper, index: int) -> str:
    if paper.doi:
        return paper.doi
    for key in ("openalex", "semantic_scholar", "pubmed", "scopus"):
        value = paper.ids.get(key) if paper.ids else None
        if value:
            return f"{key}:{value}"
    return f"paper:{index}"


def _default_clusters(n: int) -> int:
    if n <= 1:
        return 1
    return max(2, min(8, int(round(math.sqrt(n)))))


def _edges(vectors: List[Dict[str, float]], labels: List[int], threshold: float = 0.05) -> List[Dict[str, Any]]:
    edges: List[Dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for i, vector in enumerate(vectors):
        best_j, best_score = -1, -1.0
        for j, other in enumerate(vectors):
            if i == j or labels[i] != labels[j]:
                continue
            score = _dot(vector, other)
            if score > best_score:
                best_j, best_score = j, score
        if best_j >= 0 and best_score >= threshold:
            key = (min(i, best_j), max(i, best_j))
            if key not in seen:
                seen.add(key)
                edges.append({"source": i, "target": best_j, "weight": round(best_score, 4)})
    return edges


def build_landscape(papers: Iterable[Paper], n_clusters: Optional[int] = None) -> Dict[str, Any]:
    """Cluster ``papers`` into a keyword-level map.

    Returns ``nodes`` (2D coordinates + cluster id), ``clusters`` (label and
    stats), ``edges`` (nearest neighbours inside a cluster) and ``stats``.
    """
    papers = list(papers)
    if not papers:
        return {"nodes": [], "clusters": [], "edges": [], "stats": {"papers": 0, "clusters": 0, "terms": 0}}

    docs = [_document_terms(paper) for paper in papers]
    vectors = _tfidf(docs)
    k = n_clusters if n_clusters is not None else _default_clusters(len(papers))
    labels = _kmeans(vectors, k)
    coords = _coordinates(vectors)

    cluster_members: Dict[int, List[int]] = {}
    for index, label in enumerate(labels):
        cluster_members.setdefault(label, []).append(index)
    cluster_ids = sorted(cluster_members, key=lambda cid: (-len(cluster_members[cid]), cid))
    ordered = {old: new for new, old in enumerate(cluster_ids)}
    labels = [ordered[label] for label in labels]
    cluster_members = {ordered[cid]: members for cid, members in cluster_members.items()}

    cluster_terms = [Counter(term for index in cluster_members[cid] for term in docs[index]) for cid in sorted(cluster_members)]
    nodes = []
    for index, paper in enumerate(papers):
        x, y = coords[index]
        nodes.append(
            {
                "id": _node_id(paper, index),
                "title": paper.title,
                "year": paper.year,
                "cluster": labels[index],
                "x": x,
                "y": y,
            }
        )

    clusters = []
    for cid in sorted(cluster_members):
        members = cluster_members[cid]
        years = [papers[i].year for i in members if papers[i].year is not None]
        topics = Counter(topic for i in members for topic in papers[i].topics)
        authors = Counter(author for i in members for author in papers[i].authors)
        venues = Counter(papers[i].venue for i in members if papers[i].venue)
        study_types = Counter(
            papers[i].study_type for i in members if papers[i].study_type
        )
        clusters.append(
            {
                "id": cid,
                "label": _ctfidf_label([docs[i] for i in members], cluster_terms),
                "size": len(members),
                "median_year": median(years) if years else 0,
                "top_topics": _top(topics),
                "top_authors": _top(authors),
                "top_venues": _top(venues),
                "study_types": dict(study_types.most_common()),
            }
        )

    return {
        "nodes": nodes,
        "clusters": clusters,
        "edges": _edges(vectors, labels),
        "stats": {"papers": len(papers), "clusters": len(clusters), "terms": len({t for terms in docs for t in terms})},
    }
