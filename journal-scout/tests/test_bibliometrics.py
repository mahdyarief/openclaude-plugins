from math import pi

import pytest

from josc import bibliometrics as bm
from josc.models import Paper


def P(**kw):
    return Paper(**kw)


def test_annual_production_fills_gap_years():
    rows = bm.annual_production([P(year=2020, citation_count=3), P(year=2022), P(year=2022)])
    assert rows == [
        {"year": 2020, "papers": 1, "citations": 3},
        {"year": 2021, "papers": 0, "citations": 0},
        {"year": 2022, "papers": 2, "citations": 0},
    ]


def test_annual_growth_rate_is_compound():
    papers = [P(year=2020)] + [P(year=2022)] * 4
    # (4/1) ** (1/2) - 1 = 100%
    assert bm.annual_growth_rate(papers) == 100.0
    assert bm.annual_growth_rate([P(year=2020)]) is None


def test_corpus_summary_collaboration_indicators():
    papers = [
        P(year=2020, authors=["A"], countries=["ID"], citation_count=4, references=["r1", "r2"]),
        P(year=2021, authors=["A", "B"], countries=["ID", "US"], citation_count=2, references=["r1"]),
        P(year=2021, authors=["B", "C", "D"], countries=["US"], keywords=["ML"]),
    ]
    s = bm.corpus_summary(papers, current_year=2024)
    assert s["documents"] == 3
    assert s["timespan"] == [2020, 2021]
    assert s["authors"] == 4
    assert s["author_appearances"] == 6
    assert s["single_authored_documents"] == 1
    assert s["co_authors_per_document"] == 2.0
    assert s["collaboration_index"] == 2.5  # (2 + 3) / 2 multi-authored docs
    assert s["international_co_authorship_pct"] == pytest.approx(33.33, abs=0.01)
    assert s["references"] == 3 and s["unique_references"] == 2
    assert s["average_citations_per_document"] == 2.0
    assert "note" not in s


def test_corpus_summary_flags_partial_current_year():
    assert "note" in bm.corpus_summary([P(year=2024)], current_year=2024)


def test_top_items_merges_spelling_variants_and_fractionalises():
    papers = [
        P(authors=["Ana Lee", "Bo"], citation_count=10),
        P(authors=["ana  lee"], citation_count=1),
    ]
    rows = bm.top_items(papers, "authors")
    assert rows[0]["name"] in {"Ana Lee", "ana  lee"}
    assert rows[0]["documents"] == 2
    assert rows[0]["fractional_documents"] == 1.5
    assert rows[0]["h_index"] == 1


def test_top_items_rejects_unknown_field():
    with pytest.raises(ValueError):
        bm.top_items([P()], "nope")


def test_country_production_and_collaboration():
    papers = [P(countries=["ID", "US"]), P(countries=["ID"]), P(countries=["us", "ID"])]
    rows = {r["country"]: r for r in bm.country_production(papers)}
    assert rows["ID"]["documents"] == 3 and rows["ID"]["scp"] == 1 and rows["ID"]["mcp"] == 2
    assert bm.country_collaboration(papers) == [{"from": "ID", "to": "US", "documents": 2}]


def test_bradford_zones_split_output_into_thirds():
    papers = [P(venue="Core")] * 6 + [P(venue="Mid1")] * 3 + [P(venue="Mid2")] * 3 \
        + [P(venue=f"Tail{i}") for i in range(6)]
    result = bm.bradford_law(papers)
    zones = {z["zone"]: z for z in result["zones"]}
    assert zones[1] == {"zone": 1, "sources": 1, "papers": 6}
    assert zones[2] == {"zone": 2, "sources": 2, "papers": 6}
    assert zones[3] == {"zone": 3, "sources": 6, "papers": 6}
    assert [s["source"] for s in result["core_sources"]] == ["Core"]
    assert result["bradford_multiplier"] == 2.5


def test_lotka_fits_inverse_square_distribution():
    # 60 authors with 1 paper, 15 with 2, 7 with 3 ... roughly C/x^2.
    papers = []
    counter = 0
    for docs, n_authors in ((1, 60), (2, 15), (3, 7), (4, 4)):
        for _ in range(n_authors):
            counter += 1
            papers.extend(P(authors=[f"a{counter}"]) for _ in range(docs))
    result = bm.lotka_law(papers)
    assert result["authors"] == 86
    assert result["beta"] == pytest.approx(2.0, abs=0.15)
    assert result["fits_classic_lotka"] is True
    first = result["distribution"][0]
    assert first["lotka_expected"] == round(6 / pi ** 2, 4)


def test_louvain_separates_two_cliques_joined_by_one_edge():
    a = ["a1", "a2", "a3", "a4"]
    b = ["b1", "b2", "b3", "b4"]
    edges = [(x, y, 1) for group in (a, b) for i, x in enumerate(group) for y in group[i + 1:]]
    edges.append(("a1", "b1", 1))
    communities = bm.louvain(a + b, edges)
    assert len({communities[n] for n in a}) == 1
    assert len({communities[n] for n in b}) == 1
    assert communities["a1"] != communities["b1"]


def test_louvain_leaves_isolated_nodes_alone():
    assert bm.louvain(["x", "y"], []) == {"x": 0, "y": 1}


def test_co_occurrence_network_counts_shared_papers():
    papers = [
        P(keywords=["Deep Learning", "Vision"]),
        P(keywords=["deep learning", "Vision", "Robots"]),
        P(keywords=["Robots"]),
    ]
    net = bm.co_occurrence_network(papers, "keywords", min_occurrences=2)
    ids = {n["id"] for n in net["nodes"]}
    assert ids == {"deep learning", "vision", "robots"}
    edge = next(e for e in net["edges"] if {e["source"], e["target"]} == {"deep learning", "vision"})
    assert edge["weight"] == 2
    assert edge["association_strength"] == 0.5  # 2 / (2 * 2)


def test_co_authorship_network_edge_type():
    net = bm.co_occurrence_network([P(authors=["A", "B"])] * 2, "authors")
    assert net["edges"][0]["type"] == "co_authorship"


def test_co_citation_uses_resolved_labels():
    papers = [P(references=["W1", "W2"]), P(references=["W1", "W2", "W3"]), P(references=["W3"])]
    net = bm.co_citation_network(papers, labels={"W1": {"label": "Smith (1999)", "year": 1999}})
    labels = {n["id"]: n for n in net["nodes"]}
    assert labels["W1"]["label"] == "Smith (1999)" and labels["W1"]["year"] == 1999
    assert [(e["source"], e["target"], e["weight"]) for e in net["edges"]] == [("W1", "W2", 2)]


def test_bibliographic_coupling_counts_shared_references():
    papers = [
        P(doi="10.1/a", references=["r1", "r2", "r3", "r4"], citation_count=5),
        P(doi="10.1/b", references=["r1", "r2"], citation_count=3),
        P(doi="10.1/c", references=["r9"]),
        P(doi="10.1/d"),
    ]
    net = bm.bibliographic_coupling_network(papers)
    assert net["edges"] == [{"source": "10.1/a", "target": "10.1/b", "weight": 2,
                             "type": "bibliographic_coupling", "salton": round(2 / (8 ** 0.5), 4)}]
    assert net["stats"]["papers_without_references"] == 1


def _two_theme_corpus():
    papers = []
    for _ in range(4):
        papers.append(P(year=2018, keywords=["neural network", "deep learning", "backpropagation"]))
        papers.append(P(year=2022, keywords=["blockchain", "smart contract", "ledger"]))
    papers.append(P(year=2020, keywords=["deep learning", "blockchain"]))
    return papers


def test_thematic_map_finds_two_themes_with_quadrants():
    result = bm.thematic_map(_two_theme_corpus(), min_occurrences=2)
    assert len(result["themes"]) == 2
    labels = [set(t["term"] for t in theme["terms"]) for theme in result["themes"]]
    assert {"neural network", "deep learning", "backpropagation"} in labels
    assert {"blockchain", "smart contract", "ledger"} in labels
    for theme in result["themes"]:
        assert theme["quadrant"] in bm.QUADRANTS.values()
        assert theme["centrality"] > 0 and theme["density"] > 0


def test_thematic_map_handles_sparse_input():
    assert bm.thematic_map([P(keywords=["x"])])["themes"] == []


def test_trend_topics_orders_terms_by_median_year():
    result = bm.trend_topics(_two_theme_corpus(), min_frequency=3, per_year=1)
    years = [t["year_median"] for t in result["terms"]]
    assert years == sorted(years)
    assert result["terms"][0]["year_median"] == 2018.0


def test_burst_detection_flags_sudden_term():
    papers = [P(year=y, keywords=["steady"]) for y in range(2010, 2020) for _ in range(5)]
    papers += [P(year=y, keywords=["steady", "hype"]) for y in (2016, 2017) for _ in range(5)]
    result = bm.burst_detection(papers, min_frequency=3)
    hype = [b for b in result["bursts"] if b["term"] == "hype"]
    assert hype and hype[0]["start"] == 2016 and hype[0]["end"] == 2017
    assert hype[0]["weight"] > 0
    assert not [b for b in result["bursts"] if b["term"] == "steady"]


def test_rpys_finds_peak_against_rolling_median():
    result = bm.rpys({1990: 2, 1991: 2, 1992: 20, 1993: 2, 1994: 2})
    assert [p["year"] for p in result["peaks"]] == [1992]
    assert result["peaks"][0]["deviation"] == 18.0


def test_three_field_links_columns():
    papers = [P(authors=["A"], keywords=["k"], venue="J"), P(authors=["A"], keywords=["k"], venue="J")]
    result = bm.three_field(papers)
    assert {(lk["source"], lk["target"], lk["value"]) for lk in result["links"]} == {
        ("authors:a", "keywords:k", 2), ("keywords:k", "venue:j", 2)}


def test_to_pajek_writes_vertices_and_edges():
    net = {"nodes": [{"id": "a", "label": 'A "x"'}, {"id": "b", "label": "B"}],
           "edges": [{"source": "a", "target": "b", "weight": 3}]}
    assert bm.to_pajek(net) == "*Vertices 2\n1 \"A 'x'\"\n2 \"B\"\n*Edges\n1 2 3\n"
