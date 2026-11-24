import json

import pytest

import josc.aggregator as aggregator
from josc.aggregator import bibliometric_analysis
from josc.models import Paper


def _corpus():
    papers = []
    for i in range(4):
        papers.append(Paper(doi=f"10.1/ml{i}", title=f"ML {i}", year=2018 + i, venue="J ML",
                            authors=["Ana", "Budi"], countries=["ID", "US"], citation_count=10 - i,
                            keywords=["deep learning", "vision"],
                            references=["https://openalex.org/W1", "https://openalex.org/W2"],
                            sources=["openalex"]))
        papers.append(Paper(doi=f"10.1/bc{i}", title=f"BC {i}", year=2019 + i, venue=f"J BC{i % 2}",
                            authors=["Citra"], countries=["ID"], citation_count=i,
                            keywords=["blockchain", "ledger"],
                            references=["https://openalex.org/W3"], sources=["openalex"]))
    return papers


class FakeOpenAlex:
    name = "openalex"

    def __init__(self):
        self.asked = []

    async def get_many(self, ids):
        self.asked.append(list(ids))
        year = {"https://openalex.org/W1": 1998, "https://openalex.org/W2": 2005}
        return [Paper(title=f"Ref {i}", year=year[i], authors=["Grace Hopper"], ids={"openalex": i})
                for i in ids if i in year]


@pytest.fixture
def fake_search(monkeypatch):
    calls = {}

    async def search_all(providers, query, **kwargs):
        calls["query"] = query
        calls["kwargs"] = kwargs
        return {"results": [p.to_dict() for p in _corpus()], "errors": {}, "counts": {"openalex": 8},
                "query_warnings": []}

    monkeypatch.setattr(aggregator, "search_all", search_all)
    return calls


async def test_full_report_from_query(fake_search):
    provider = FakeOpenAlex()
    report = await bibliometric_analysis([provider], query="ml", resolve_references=10)
    assert fake_search["query"] == "ml"
    assert report["documents"] == 8
    assert report["summary"]["international_co_authorship_pct"] == 50.0
    assert report["top_authors"][0]["name"] == "Ana"
    assert report["bradford"]["zones"][0]["sources"] == 1
    assert set(report["networks"]) == {
        "co_authorship", "keyword_co_occurrence", "country_collaboration",
        "institution_collaboration", "co_citation", "bibliographic_coupling"}
    labels = {n["id"]: n["label"] for n in report["networks"]["co_citation"]["nodes"]}
    assert labels["https://openalex.org/W1"].startswith("Hopper (1998)")
    assert len(report["thematic_map"]["themes"]) == 2
    assert report["rpys"]["citations_resolved"] == 8
    assert report["rpys"]["coverage_pct"] == pytest.approx(66.7)
    assert report["references_resolved"] == 2
    assert provider.asked[0][0] in {"https://openalex.org/W1", "https://openalex.org/W2", "https://openalex.org/W3"}
    json.dumps(report)  # must be serialisable for the MCP transport


async def test_report_from_supplied_paper_dicts_without_search(monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("must not search when papers are supplied")

    monkeypatch.setattr(aggregator, "search_all", boom)
    dicts = [p.to_dict() for p in _corpus()]
    dicts[0]["retraction"] = {"reasons": []}
    dicts[0]["unexpected"] = 1
    report = await bibliometric_analysis([], papers=dicts, analyses=["summary", "lotka"])
    assert report["documents"] == 8
    assert set(report) >= {"summary", "lotka"}
    assert "networks" not in report


async def test_reference_analyses_explain_missing_data():
    papers = [Paper(title="x", year=2020, authors=["A"], keywords=["k"])] * 3
    report = await bibliometric_analysis([], papers=papers, analyses=["rpys", "networks"],
                                         networks=["co_citation"])
    assert "rpys" not in report
    assert any("rpys" in n for n in report["notes"])
    assert any("co_citation" in n for n in report["notes"])


async def test_graph_export_returns_single_network():
    out = await bibliometric_analysis([], papers=_corpus(), graph_network="co_authorship",
                                      graph_format="pajek")
    assert out["format"] == "pajek"
    assert out["pajek"].startswith("*Vertices 3")
    gml = await bibliometric_analysis([], papers=_corpus(), graph_network="keyword_co_occurrence",
                                      graph_format="graphml")
    assert 'edgedefault="undirected"' in gml["graphml"]


async def test_budget_trims_networks():
    papers = [Paper(title=str(i), year=2020, keywords=[f"k{j}" for j in range(i % 7, i % 7 + 12)],
                    authors=[f"a{i}", f"a{i + 1}"]) for i in range(120)]
    report = await bibliometric_analysis([], papers=papers, analyses=["networks"],
                                         max_nodes=80, max_chars=6_000)
    assert len(json.dumps(report)) <= 6_000 or all(
        len(n["nodes"]) <= 10 for n in report["networks"].values())
    assert any("trimmed" in n for n in report["notes"])


async def test_requires_query_or_papers():
    with pytest.raises(ValueError):
        await bibliometric_analysis([])
