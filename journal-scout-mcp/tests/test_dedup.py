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
