from josc.merge import (
    _merge_authors,
    dedup_key,
    merge_papers,
    merge_two,
)
from josc.models import Paper


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


def test_merge_prefers_higher_ranked_source_not_argument_order():
    # Even when the weaker source is passed first, scopus (rank 0) must win.
    arxiv = Paper(doi="10.1/x", title="arxiv title", venue="preprint", sources=["arxiv"])
    scopus = Paper(doi="10.1/x", title="scopus title", venue="IEEE Access", sources=["scopus"])
    merged = merge_two(arxiv, scopus)
    assert merged.title == "scopus title"
    assert merged.venue == "IEEE Access"


def test_merge_unions_authors_without_duplicates():
    a = Paper(doi="10.1/x", title="P", authors=["Sepp Hochreiter"], sources=["openalex"])
    b = Paper(doi="10.1/x", title="P", authors=["Sepp Hochreiter", "Jürgen Schmidhuber"], sources=["crossref"])
    merged = merge_two(a, b)
    assert merged.authors == ["Sepp Hochreiter", "Jürgen Schmidhuber"]


def test_merge_authors_dedups_case_and_punctuation():
    authors = _merge_authors(
        Paper(authors=["Ashish Vaswani"]),
        Paper(authors=["ashish vaswani.", "Noam Shazeer"]),
    )
    assert authors == ["Ashish Vaswani", "Noam Shazeer"]


def test_merge_prefers_longest_abstract():
    a = Paper(doi="10.1/x", title="P", abstract="short", sources=["scopus"])
    b = Paper(doi="10.1/x", title="P", abstract="a much longer abstract body", sources=["openalex"])
    assert merge_two(a, b).abstract == "a much longer abstract body"


def test_merge_keeps_enrichment_fields_from_whichever_source_has_them():
    # Enrichment fields arrive from different providers: a retraction flag and a
    # percentile only from OpenAlex, topics and keywords only from PubMed. The
    # merge must not drop the one that the preferred record lacks.
    preferred = Paper(
        doi="10.1/x",
        title="P",
        sources=["scopus"],
        is_retracted=False,
        topics=["Scopus Subject"],
    )
    fallback = Paper(
        doi="10.1/x",
        title="P",
        sources=["openalex"],
        is_retracted=True,
        cited_by_percentile=97,
        keywords=["governance"],
        language="en",
    )
    merged = merge_two(preferred, fallback)
    assert merged.cited_by_percentile == 97
    assert merged.keywords == ["governance"]
    assert merged.language == "en"


def test_merge_unions_topics_and_keeps_true_retraction_flag():
    a = Paper(doi="10.1/x", title="P", sources=["crossref"], is_retracted=False, topics=["Computer Science"])
    b = Paper(doi="10.1/x", title="P", sources=["openalex"], is_retracted=True, topics=["Machine Learning"])
    merged = merge_two(a, b)
    assert merged.is_retracted is True
    assert merged.topics == ["Computer Science", "Machine Learning"]


def test_merge_folds_doiless_record_into_its_doi_twin_by_title_author():
    # The arxiv copy lacks a DOI but shares title+first author with the
    # DOI-bearing record, so it must fold in instead of appearing twice.
    with_doi = Paper(doi="10.1/x", title="Attention Is All You Need", year=2017, authors=["Ashish Vaswani"], sources=["crossref"])
    without_doi = Paper(title="Attention Is All You Need", authors=["Ashish Vaswani"], sources=["arxiv"])
    merged = merge_papers([with_doi, without_doi])
    assert len(merged) == 1
    assert set(merged[0].sources) == {"crossref", "arxiv"}
    assert merged[0].doi == "10.1/x"


def test_merge_folds_doiless_records_by_title_author_without_year():
    # No year on either side: the (title, first-author) fallback still merges.
    a = Paper(title="Deep Residual Learning", authors=["Kaiming He"], sources=["arxiv"])
    b = Paper(title="Deep Residual Learning", authors=["Kaiming He"], sources=["dblp"])
    merged = merge_papers([a, b])
    assert len(merged) == 1
    assert set(merged[0].sources) == {"arxiv", "dblp"}
