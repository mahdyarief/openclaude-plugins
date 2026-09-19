from journal_scout_mcp.merge import dedup_key, merge_papers, merge_two
from journal_scout_mcp.models import Paper


def test_dedup_key_prefers_doi():
    p = Paper(doi="https://doi.org/10.1/AbC", title="Whatever")
    assert dedup_key(p) == "doi:10.1/abc"


def test_dedup_key_falls_back_to_title():
    p = Paper(title="Attention Is All You Need!")
    assert dedup_key(p) == "title:attention is all you need"


def test_merge_two_takes_max_citations_and_unions_sources():
    a = Paper(doi="10.1/x", title="Paper", citation_count=5, sources=["scopus"], ids={"scopus": "1"})
    b = Paper(doi="10.1/x", title="Paper", citation_count=9, abstract="abs", sources=["openalex"], ids={"openalex": "W1"})
    merged = merge_two(a, b)
    assert merged.citation_count == 9
    assert merged.abstract == "abs"
    assert set(merged.sources) == {"scopus", "openalex"}
    assert merged.ids == {"scopus": "1", "openalex": "W1"}


def test_merge_papers_dedups_and_sorts():
    papers = [
        Paper(doi="10.1/a", title="A", citation_count=1, sources=["scopus"]),
        Paper(doi="10.1/b", title="B", citation_count=10, sources=["openalex"]),
        Paper(doi="10.1/a", title="A", citation_count=4, sources=["crossref"]),
    ]
    merged = merge_papers(papers)
    assert len(merged) == 2
    assert merged[0].title == "B"
    assert merged[1].citation_count == 4