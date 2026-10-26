from josc.dedup import same_work
from josc.merge import merge_papers, merge_two
from josc.models import Paper
from josc.providers.crossref import CrossrefProvider


def test_paper_to_dict_exposes_isbn():
    paper = Paper(title="A Book", isbn="978-3-16-148410-0")
    assert paper.to_dict()["isbn"] == "978-3-16-148410-0"


def test_crossref_reads_isbn_from_book_items():
    provider = CrossrefProvider(None)
    paper = provider._to_paper(
        {
            "DOI": "10.1/book",
            "title": ["A Book"],
            "ISBN": ["9783161484100"],
            "type": "book",
        }
    )
    assert paper.isbn == "9783161484100"


def test_same_work_rejects_conflicting_dois():
    a = Paper(doi="10.1/a", title="Same Title")
    b = Paper(doi="10.1/b", title="Same Title")
    assert same_work(a, b) is False


def test_same_work_rejects_conflicting_isbns():
    a = Paper(isbn="9783161484100", title="Same Title")
    b = Paper(isbn="9783161484117", title="Same Title")
    assert same_work(a, b) is False


def test_same_work_rejects_year_gap_greater_than_one():
    a = Paper(title="Same Title", year=2019)
    b = Paper(title="Same Title", year=2022)
    assert same_work(a, b) is False


def test_same_work_accepts_year_gap_of_one():
    a = Paper(title="Same Title", year=2019)
    b = Paper(title="Same Title", year=2020)
    assert same_work(a, b) is True


def test_same_work_matches_when_both_have_no_creators():
    a = Paper(title="Same Title")
    b = Paper(title="Same Title")
    assert same_work(a, b) is True


def test_same_work_rejects_when_only_one_side_has_creators():
    a = Paper(title="Same Title", authors=["Sepp Hochreiter"])
    b = Paper(title="Same Title")
    assert same_work(a, b) is False


def test_same_work_matches_on_last_name_and_first_initial():
    a = Paper(title="Same Title", authors=["Sepp Hochreiter"])
    b = Paper(title="Same Title", authors=["S. Hochreiter", "Jürgen Schmidhuber"])
    assert same_work(a, b) is True


def test_same_work_rejects_disjoint_creator_lists():
    a = Paper(title="Same Title", authors=["Sepp Hochreiter"])
    b = Paper(title="Same Title", authors=["Yann LeCun"])
    assert same_work(a, b) is False


def test_merge_papers_keeps_distinct_works_with_identical_titles():
    papers = [
        Paper(doi="10.1/a", title="Editorial", year=2020, sources=["crossref"]),
        Paper(doi="10.1/b", title="Editorial", year=2020, sources=["scopus"]),
    ]
    merged = merge_papers(papers)
    assert len(merged) == 2


def test_merge_papers_still_folds_matching_doi():
    papers = [
        Paper(doi="10.1/a", title="Editorial", citation_count=1, sources=["crossref"]),
        Paper(doi="10.1/A", title="Editorial", citation_count=9, sources=["scopus"]),
    ]
    merged = merge_papers(papers)
    assert len(merged) == 1
    assert merged[0].citation_count == 9


def test_merge_papers_uses_year_tolerance_within_bucket():
    papers = [
        Paper(title="Untitled", year=2020, authors=["Sepp Hochreiter"]),
        Paper(title="Untitled", year=2021, authors=["S. Hochreiter"]),
        Paper(title="Untitled", year=2024, authors=["Sepp Hochreiter"]),
    ]
    merged = merge_papers(papers)
    assert len(merged) == 2


def test_merge_papers_joins_doi_less_record_to_its_doi_twin():
    papers = [
        Paper(
            doi="10.1/a",
            title="A Paper",
            year=2020,
            sources=["crossref"],
            authors=["Sepp Hochreiter"],
        ),
        Paper(title="A Paper", year=2020, authors=["Sepp Hochreiter"]),
    ]
    merged = merge_papers(papers)
    assert len(merged) == 1
    assert merged[0].doi == "10.1/a"


def test_merge_two_keeps_isbn_from_either_side():
    a = Paper(title="A Book", isbn="9783161484100")
    b = Paper(title="A Book")
    merged = merge_two(a, b)
    assert merged.isbn == "9783161484100"

    reverse = merge_two(b, a)
    assert reverse.isbn == "9783161484100"
