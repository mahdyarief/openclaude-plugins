from xml.etree import ElementTree

from josc.metrics import (
    awcr,
    citation_velocity,
    citations_by_year,
    compute_metrics,
    e_index,
    g_index,
    h_index,
    hc_index,
    hI_index,
    hI_norm,
    hm_index,
    i10_index,
)
from josc.models import Paper
from josc.network import build_network, to_graphml


def _paper(doi, title, year=2020, citations=0, **kwargs):
    return Paper(doi=doi, title=title, year=year, citation_count=citations, **kwargs)


def test_h_index_uses_ranked_citation_counts():
    assert h_index([10, 8, 5, 4, 3]) == 4
    assert h_index([1, 1, 1]) == 1
    assert h_index([]) == 0
    assert h_index([0, 0]) == 0


def test_h_index_ignores_none_values():
    assert h_index([None, 5, 4, 3]) == 3


def test_i10_counts_papers_with_at_least_ten_citations():
    assert i10_index([10, 9, 11, 0, None]) == 2


def test_g_index_accounts_for_cumulative_citations():
    # 20 + 10 + 5 = 35 >= 9, so g = 3; 20 + 10 = 30 >= 4 too.
    assert g_index([20, 10, 5]) == 3
    assert g_index([3, 2, 1]) == 2
    assert g_index([]) == 0


def test_citation_velocity_divides_total_by_year_span():
    papers = [_paper("10.1/a", "A", year=2018, citations=10)]
    assert citation_velocity(papers, current_year=2020) == 3.333
    assert citation_velocity([], current_year=2020) is None
    assert citation_velocity([_paper("10.1/b", "B", year=None)], current_year=2020) is None


def test_compute_metrics_returns_full_summary():
    papers = [
        _paper("10.1/a", "A", year=2018, citations=20),
        _paper("10.1/b", "B", year=2019, citations=10),
        _paper("10.1/c", "C", year=2020, citations=5),
    ]
    metrics = compute_metrics(papers, current_year=2020)
    assert metrics["papers"] == 3
    assert metrics["total_citations"] == 35
    assert metrics["h_index"] == 3
    assert metrics["i10_index"] == 2
    assert metrics["g_index"] == 3
    assert metrics["max_citations"] == 20
    assert metrics["mean_citations"] == 11.667
    assert metrics["citation_velocity"] == 11.667


def test_compute_metrics_handles_empty_input():
    metrics = compute_metrics([], current_year=2020)
    assert metrics["papers"] == 0
    assert metrics["total_citations"] == 0
    assert metrics["h_index"] == 0
    assert metrics["citation_velocity"] is None
    assert metrics["e_index"] == 0.0
    assert metrics["cites_year"] == 0.0
    assert metrics["cites_paper"] == 0.0
    assert metrics["authors_paper"] == 0.0


def test_citations_by_year_aggregates_and_accumulates():
    papers = [
        _paper("10.1/a", "A", year=2018, citations=20),
        _paper("10.1/b", "B", year=2019, citations=10),
        _paper("10.1/c", "C", year=2019, citations=5),
        _paper("10.1/d", "D", year=None, citations=99),  # no year -> skipped
    ]
    table = citations_by_year(papers)
    assert table == [
        {"year": 2018, "papers": 1, "citations": 20, "cumulative_citations": 20},
        {"year": 2019, "papers": 2, "citations": 15, "cumulative_citations": 35},
    ]
    assert citations_by_year([]) == []


def test_compute_metrics_includes_by_year():
    papers = [
        _paper("10.1/a", "A", year=2018, citations=20),
        _paper("10.1/b", "B", year=2019, citations=10),
    ]
    metrics = compute_metrics(papers, current_year=2020)
    assert metrics["by_year"] == [
        {"year": 2018, "papers": 1, "citations": 20, "cumulative_citations": 20},
        {"year": 2019, "papers": 1, "citations": 10, "cumulative_citations": 30},
    ]


def test_e_index_measures_tail_above_h_core():
    # h = 3, top-3 sum = 35, tail = 35 - 9 = 26, sqrt(26) = 5.099
    assert e_index([20, 10, 5]) == 5.099
    assert e_index([10, 10, 10, 10]) == 4.899
    assert e_index([]) == 0.0
    # Flat h-core has no tail above h**2.
    assert e_index([1, 1, 1]) == 0.0
    assert e_index([0, 0]) == 0.0


def test_awcr_discounts_citations_by_paper_age():
    papers = [
        _paper("10.1/a", "A", year=2018, citations=10),  # 10 / 3
        _paper("10.1/b", "B", year=2020, citations=5),  # 5 / 1
        _paper("10.1/c", "C", year=None, citations=100),  # skipped
    ]
    assert awcr(papers, current_year=2020) == 8.333


def test_hc_index_uses_only_recent_window():
    counts = [5, 10, 20, 50]
    papers = [
        _paper("10.1/a", "A", year=2020, citations=5),
        _paper("10.1/b", "B", year=2016, citations=10),
        _paper("10.1/c", "C", year=2015, citations=20),
        _paper("10.1/d", "D", year=None, citations=50),
    ]
    # 2020 and 2016 are inside the 5-year window; 2015 and unknown are not.
    assert hc_index(counts, papers, current_year=2020, recent_years=5) == 2


def test_hI_index_divides_h_by_mean_authors_of_core():
    papers = [
        _paper("10.1/a", "A", citations=10, authors=["A", "B"]),
        _paper("10.1/b", "B", citations=8, authors=["A", "C"]),
        _paper("10.1/c", "C", citations=6, authors=["A", "B", "C", "D"]),
    ]
    # h = 3; mean authors in the h-core = (2 + 2 + 4) / 3 = 2.667
    # hI (Batista) = 3 / 2.667 = 1.125
    assert hI_index(papers) == 1.125


def test_hI_norm_takes_h_index_of_author_share():
    papers = [
        _paper("10.1/a", "A", citations=10, authors=["A", "B"]),
        _paper("10.1/b", "B", citations=8, authors=["A", "C"]),
        _paper("10.1/c", "C", citations=6, authors=["A", "B", "C", "D"]),
    ]
    # Reduced counts: 5, 4, 2 (rounded) -> h-index = 2.
    assert hI_norm(papers) == 2


def test_hm_index_uses_fractional_effective_rank():
    papers = [
        _paper("10.1/a", "A", citations=40, authors=["A", "B", "C", "D"]),
        _paper("10.1/b", "B", citations=30, authors=["A", "B"]),
        _paper("10.1/c", "C", citations=20, authors=["A"]),
    ]
    # Effective ranks: 0.25, 0.75, 1.75; each citation count clears its rank,
    # so hm = 1.75.
    assert hm_index(papers) == 1.75


def test_extended_metrics_are_a_superset_of_basic():
    papers = [
        _paper("10.1/a", "A", year=2018, citations=20, authors=["A", "B"]),
        _paper("10.1/b", "B", year=2019, citations=10, authors=["A"]),
        _paper("10.1/c", "C", year=2020, citations=5, authors=["A", "C"]),
    ]
    basic = compute_metrics(papers, current_year=2020)
    extended = compute_metrics(papers, current_year=2020, mode="extended")

    assert set(basic) <= set(extended)
    for key, value in basic.items():
        assert extended[key] == value
    for key in (
        "hc_index",
        "hI_index",
        "hI_norm",
        "AWCR",
        "AW_index",
        "AWCRpA",
        "hm_index",
    ):
        assert key in extended
    assert extended["AWCR"] == awcr(papers, current_year=2020)
    assert extended["AW_index"] == round(awcr(papers, current_year=2020) ** 0.5, 3)


def test_compute_metrics_rejects_unknown_mode():
    import pytest

    with pytest.raises(ValueError):
        compute_metrics([], current_year=2020, mode="nope")


def test_build_network_creates_direct_citation_edges():
    seed = _paper("10.1/seed", "Seed")
    references = [_paper("10.1/r1", "Ref one"), _paper("10.1/r2", "Ref two")]
    citations = [_paper("10.1/c1", "Citing one")]

    network = build_network(seed, references, citations)

    assert network["seed"] == "doi:10.1/seed"
    assert network["stats"]["nodes"] == 4
    cites = [e for e in network["edges"] if e["type"] == "cites"]
    assert {"source": "doi:10.1/seed", "target": "doi:10.1/r1", "type": "cites", "weight": 1} in cites
    assert {"source": "doi:10.1/c1", "target": "doi:10.1/seed", "type": "cites", "weight": 1} in cites


def test_build_network_derives_coupling_and_cocitation_edges():
    seed = _paper("10.1/seed", "Seed")
    shared = _paper("10.1/shared", "Shared ref")
    other = _paper("10.1/other", "Other ref")
    citing_a = _paper("10.1/ca", "Citing A")
    citing_b = _paper("10.1/cb", "Citing B")

    network = build_network(
        seed,
        [shared],
        [citing_a, citing_b],
        citing_references={
            "doi:10.1/ca": [shared, other],
            "doi:10.1/cb": [shared, other],
        },
    )

    coupled = [e for e in network["edges"] if e["type"] == "coupled"]
    assert len(coupled) == 2
    assert all(e["weight"] == 1 for e in coupled)

    cocited = [e for e in network["edges"] if e["type"] == "cocited"]
    assert len(cocited) == 1
    assert cocited[0]["weight"] == 2
    assert {cocited[0]["source"], cocited[0]["target"]} == {"doi:10.1/shared", "doi:10.1/other"}


def test_cocitation_is_counted_beyond_the_node_budget():
    # Counting used to stop once max_nodes was reached: the seed's references
    # plus the citing papers fill the budget, the first citing paper's
    # references take the last two slots, and the second citing paper is never
    # seen -- so no pair can reach the weight-2 threshold.
    seed = _paper("10.1/seed", "Seed")
    references = [_paper(f"10.1/r{i}", f"Ref {i}") for i in range(5)]
    shared_a = _paper("10.1/shared-a", "Shared A")
    shared_b = _paper("10.1/shared-b", "Shared B")
    citing_a = _paper("10.1/ca", "Citing A")
    citing_b = _paper("10.1/cb", "Citing B")

    network = build_network(
        seed,
        references,
        [citing_a, citing_b],
        citing_references={
            "doi:10.1/ca": [shared_a, shared_b],
            "doi:10.1/cb": [shared_a, shared_b],
        },
        max_nodes=10,
    )

    cocited = [e for e in network["edges"] if e["type"] == "cocited"]
    assert len(cocited) == 1
    assert cocited[0]["weight"] == 2
    assert {cocited[0]["source"], cocited[0]["target"]} == {
        "doi:10.1/shared-a",
        "doi:10.1/shared-b",
    }
    assert network["stats"]["nodes"] <= 10


def test_same_work_from_different_providers_is_one_node():
    # Scopus omits the DOI; Crossref has it. Both describe the same work, so
    # co-citation must count them as one reference, not two.
    seed = _paper("10.1/seed", "Seed")
    citing_a = _paper("10.1/ca", "Citing A")
    citing_b = _paper("10.1/cb", "Citing B")

    title_one = "A shared reference work"
    title_two = "Another shared reference work"

    scopus_one = Paper(title=title_one, ids={"scopus": "85071168537"})
    scopus_two = Paper(title=title_two, ids={"scopus": "85071168538"})
    doi_one = Paper(doi="10.1/shared-one", title=title_one)
    doi_two = Paper(doi="10.1/shared-two", title=title_two)

    network = build_network(
        seed,
        [],
        [citing_a, citing_b],
        citing_references={
            "doi:10.1/ca": [scopus_one, scopus_two],
            "doi:10.1/cb": [doi_one, doi_two],
        },
    )

    # seed + 2 citing + 2 merged reference works
    assert network["stats"]["nodes"] == 5
    cocited = [e for e in network["edges"] if e["type"] == "cocited"]
    assert len(cocited) == 1
    assert cocited[0]["weight"] == 2
    assert {cocited[0]["source"], cocited[0]["target"]} == {
        "doi:10.1/shared-one",
        "doi:10.1/shared-two",
    }


def test_build_network_respects_max_nodes():
    seed = _paper("10.1/seed", "Seed")
    references = [_paper(f"10.1/r{i}", f"Ref {i}") for i in range(10)]
    network = build_network(seed, references, [], max_nodes=4)
    assert network["stats"]["nodes"] == 4


def test_node_id_falls_back_to_provider_id_then_title():
    no_doi = Paper(title="Some Title", ids={"openalex": "W123"})
    network = build_network(no_doi, [], [])
    assert network["seed"] == "openalex:W123"

    title_only = Paper(title="  Some   Title  ")
    network = build_network(title_only, [], [])
    assert network["seed"] == "title:some title"


def test_nodes_carry_metadata_for_the_detail_panel():
    seed = Paper(
        doi="10.1/seed",
        title="Seed",
        abstract="Seed abstract",
        pdf_url="https://example.org/seed.pdf",
        is_open_access=True,
        type="journal-article",
    )

    network = build_network(seed, [], [])

    node = network["nodes"][0]
    assert node["abstract"] == "Seed abstract"
    assert node["pdf_url"] == "https://example.org/seed.pdf"
    assert node["is_open_access"] is True
    assert node["type"] == "journal-article"


def test_nodes_carry_degree_metrics():
    seed = _paper("10.1/seed", "Seed")
    references = [_paper("10.1/r1", "R1"), _paper("10.1/r2", "R2")]
    citations = [_paper("10.1/c1", "C1")]

    network = build_network(seed, references, citations)

    nodes = {node["id"]: node for node in network["nodes"]}
    assert nodes["doi:10.1/seed"]["out_degree"] == 2
    assert nodes["doi:10.1/seed"]["in_degree"] == 1
    assert nodes["doi:10.1/r1"]["in_degree"] == 1
    assert nodes["doi:10.1/r1"]["out_degree"] == 0
    assert nodes["doi:10.1/c1"]["out_degree"] == 1
    assert nodes["doi:10.1/c1"]["degree"] == 1


def test_assign_communities_separates_disconnected_clusters():
    from josc.network import _assign_communities

    nodes = {f"n{i}": {"id": f"n{i}"} for i in range(4)}
    edges = [
        {"source": "n0", "target": "n1", "type": "cocited", "weight": 2},
        {"source": "n2", "target": "n3", "type": "cocited", "weight": 2},
    ]

    _assign_communities(nodes, edges)

    assert nodes["n0"]["community"] == nodes["n1"]["community"]
    assert nodes["n2"]["community"] == nodes["n3"]["community"]
    assert nodes["n0"]["community"] != nodes["n2"]["community"]
    assert {nodes["n0"]["community"], nodes["n2"]["community"]} == {0, 1}


def test_network_reports_community_count_in_stats():
    seed = _paper("10.1/seed", "Seed")
    network = build_network(seed, [_paper("10.1/r1", "R1")], [])

    assert network["stats"]["communities"] == 1
    assert all("community" in node for node in network["nodes"])


def test_build_network_links_seed_references_to_their_own_references():
    seed = _paper("10.1/seed", "Seed")
    ref = _paper("10.1/r1", "Ref one")
    older_a = _paper("10.1/older-a", "Older A")
    older_b = _paper("10.1/older-b", "Older B")

    network = build_network(
        seed,
        [ref],
        [],
        reference_references={"doi:10.1/r1": [older_a, older_b]},
    )

    cites = {(e["source"], e["target"]) for e in network["edges"] if e["type"] == "cites"}
    assert ("doi:10.1/r1", "doi:10.1/older-a") in cites
    assert ("doi:10.1/r1", "doi:10.1/older-b") in cites
    assert ("doi:10.1/seed", "doi:10.1/r1") in cites

    node_ids = {node["id"] for node in network["nodes"]}
    assert {"doi:10.1/older-a", "doi:10.1/older-b"} <= node_ids


def test_second_hop_nodes_respect_the_node_budget():
    seed = _paper("10.1/seed", "Seed")
    refs = [_paper(f"10.1/r{i}", f"Ref {i}") for i in range(3)]
    deeper = [_paper(f"10.1/d{i}", f"Deep {i}") for i in range(10)]

    network = build_network(
        seed,
        refs,
        [],
        reference_references={f"doi:10.1/r{i}": deeper for i in range(3)},
        max_nodes=6,
    )

    assert network["stats"]["nodes"] <= 6


def test_to_graphml_is_valid_xml_with_nodes_and_edges():
    seed = _paper("10.1/seed", "Seed & <Friends>", year=2020, citations=7)
    network = build_network(seed, [_paper("10.1/r1", "Ref")], [])
    xml = to_graphml(network)

    root = ElementTree.fromstring(xml)
    ns = {"g": "http://graphml.graphdrawing.org/xmlns"}
    nodes = root.findall(".//g:node", ns)
    edges = root.findall(".//g:edge", ns)
    assert len(nodes) == 2
    assert len(edges) == 1
    labels = [d.text for d in root.findall(".//g:data[@key='label']", ns)]
    assert "Seed & <Friends>" in labels
