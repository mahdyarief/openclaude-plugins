from josc.dedup import same_work
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
