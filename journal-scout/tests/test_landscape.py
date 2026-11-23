import math

from josc.landscape import build_landscape
from josc.models import Paper


def _paper(doi, title, abstract="", year=2020, topics=None, authors=None, venue=None, citations=0, study_type=None):
    return Paper(
        doi=doi,
        title=title,
        abstract=abstract,
        year=year,
        topics=topics or [],
        authors=authors or [],
        venue=venue,
        citation_count=citations,
        study_type=study_type,
    )


def _ml_corpus():
    return [
        _paper(
            "10.1/ml1",
            "Deep neural networks for image classification",
            "convolutional neural network training on image data",
            topics=["Machine Learning"],
            authors=["Alice"],
            venue="NeurIPS",
            year=2019,
        ),
        _paper(
            "10.1/ml2",
            "Transformer models for natural language",
            "attention based neural network language model",
            topics=["Machine Learning"],
            authors=["Bob"],
            venue="ACL",
            year=2021,
        ),
        _paper(
            "10.1/ml3",
            "Gradient descent optimization in deep learning",
            "neural network optimization and gradient descent",
            topics=["Machine Learning"],
            authors=["Alice"],
            venue="ICML",
            year=2022,
        ),
    ]


def _db_corpus():
    return [
        _paper(
            "10.1/db1",
            "Query optimization for relational databases",
            "sql query planner and database index selection",
            topics=["Databases"],
            authors=["Carol"],
            venue="SIGMOD",
            year=2018,
        ),
        _paper(
            "10.1/db2",
            "Indexing strategies for database systems",
            "database index structures and query performance",
            topics=["Databases"],
            authors=["Dave"],
            venue="VLDB",
            year=2020,
        ),
        _paper(
            "10.1/db3",
            "Transaction processing in SQL databases",
            "database transaction isolation and sql execution",
            topics=["Databases"],
            authors=["Carol"],
            venue="SIGMOD",
            year=2023,
        ),
    ]


def test_build_landscape_groups_similar_papers():
    result = build_landscape(_ml_corpus() + _db_corpus(), n_clusters=2)

    assert len(result["clusters"]) == 2
    assert len(result["nodes"]) == 6

    by_title = {node["title"]: node for node in result["nodes"]}
    ml_clusters = {
        by_title["Deep neural networks for image classification"]["cluster"],
        by_title["Transformer models for natural language"]["cluster"],
        by_title["Gradient descent optimization in deep learning"]["cluster"],
    }
    db_clusters = {
        by_title["Query optimization for relational databases"]["cluster"],
        by_title["Indexing strategies for database systems"]["cluster"],
        by_title["Transaction processing in SQL databases"]["cluster"],
    }
    assert len(ml_clusters) == 1
    assert len(db_clusters) == 1
    assert ml_clusters != db_clusters


def test_build_landscape_returns_finite_coordinates():
    result = build_landscape(_ml_corpus() + _db_corpus(), n_clusters=2)

    for node in result["nodes"]:
        assert math.isfinite(node["x"])
        assert math.isfinite(node["y"])


def test_build_landscape_labels_clusters_with_terms():
    result = build_landscape(_ml_corpus() + _db_corpus(), n_clusters=2)

    labels = [cluster["label"] for cluster in result["clusters"]]
    assert all(label.strip() for label in labels)
    assert len(set(labels)) == 2


def test_build_landscape_cluster_stats():
    result = build_landscape(_ml_corpus() + _db_corpus(), n_clusters=2)

    for cluster in result["clusters"]:
        assert cluster["size"] > 0
        assert isinstance(cluster["median_year"], (int, float))
        assert cluster["top_topics"]
        assert cluster["top_authors"]
        assert cluster["top_venues"]


def test_build_landscape_is_deterministic():
    corpus = _ml_corpus() + _db_corpus()
    first = build_landscape(corpus, n_clusters=2)
    second = build_landscape(corpus, n_clusters=2)

    first_assignment = {node["id"]: node["cluster"] for node in first["nodes"]}
    second_assignment = {node["id"]: node["cluster"] for node in second["nodes"]}
    assert first_assignment == second_assignment
    assert [c["label"] for c in first["clusters"]] == [c["label"] for c in second["clusters"]]


def test_build_landscape_handles_empty_input():
    result = build_landscape([], n_clusters=2)

    assert result["nodes"] == []
    assert result["clusters"] == []
    assert result["stats"]["papers"] == 0


def test_build_landscape_handles_single_paper():
    result = build_landscape(_ml_corpus()[:1], n_clusters=5)

    assert len(result["clusters"]) == 1
    assert len(result["nodes"]) == 1
    assert result["nodes"][0]["cluster"] == 0


def test_build_landscape_caps_clusters_to_paper_count():
    result = build_landscape(_ml_corpus()[:2], n_clusters=10)

    assert len(result["clusters"]) == 2
    assert len(result["nodes"]) == 2


def test_build_landscape_includes_edges_and_stats():
    result = build_landscape(_ml_corpus() + _db_corpus(), n_clusters=2)

    assert "edges" in result
    assert result["stats"]["papers"] == 6
    assert result["stats"]["clusters"] == 2


def test_build_landscape_summarizes_study_types():
    corpus = [
        _paper("10.1/a", "A trial", "rct study", year=2020, topics=["Med"],
               study_type="rct"),
        _paper("10.1/b", "B trial", "rct study", year=2021, topics=["Med"],
               study_type="rct"),
        _paper("10.1/c", "C review", "review study", year=2019, topics=["Med"],
               study_type="meta-analysis"),
    ]
    result = build_landscape(corpus, n_clusters=1)
    cluster = result["clusters"][0]
    assert cluster["study_types"]["rct"] == 2
    assert cluster["study_types"]["meta-analysis"] == 1
