import pytest

from josc.importers import SUPPORTED_FORMATS, detect_format, parse_import


RIS = """TY  - JOUR
TI  - First Paper
AU  - Alice Smith
AU  - Bob Jones
PY  - 2020
JO  - Journal A
DO  - https://doi.org/10.1000/ABC
AB  - Abstract one
UR  - https://example.com/1
ER  -

TY  - JOUR
TI  - Second Paper
A1  - Carol White
Y1  - 2019
JF  - Journal B
ER  -
"""

BIBTEX = """@article{one,
  title = {First Paper},
  author = {Alice Smith and Bob Jones},
  year = {2020},
  journal = {Journal A},
  doi = {https://doi.org/10.1000/ABC},
  abstract = {Abstract one},
  url = {https://example.com/1}
}
@book{two,
  title = "Second Book",
  author = "Carol White",
  year = 2019,
  booktitle = "Book Series",
  cites = 12
}
"""

ENDNOTE = """%0 Journal Article
%T First Paper
%A Alice Smith
%A Bob Jones
%D 2020
%J Journal A
%R doi:10.1000/ABC
%X Abstract one
%U https://example.com/1

%0 Journal Article
%T Second Paper
%A Carol White
%D 2019
%J Journal B
"""

CSV = """title,doi,author,year,venue,abstract,url,citation_count
First Paper,https://doi.org/10.1000/ABC,Alice Smith; Bob Jones,2020,Journal A,Abstract one,https://example.com/1,42
Second Paper,10.1000/DEF,Carol White,2019,Journal B,,,7
"""

CIW = """PT J
AU Alice Smith
AU Bob Jones
TI First Paper
SO Journal A
PY 2020
DI https://doi.org/10.1000/ABC
AB Abstract one
UT https://example.com/1
TC 42
ER
"""


def test_supported_formats():
    assert SUPPORTED_FORMATS == ("ris", "bibtex", "enw", "csv", "txt", "ciw")


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("paper.ris", "ris"),
        ("paper.bib", "bibtex"),
        ("paper.bibtex", "bibtex"),
        ("paper.enw", "enw"),
        ("paper.csv", "csv"),
        ("paper.txt", "txt"),
        ("paper.ciw", "ciw"),
        ("C:/data/PAPER.RIS", "ris"),
    ],
)
def test_detect_format_from_filename(filename, expected):
    assert detect_format(filename, "ignored") == expected


def test_filename_extension_wins_over_content():
    assert detect_format("paper.txt", RIS) == "txt"


@pytest.mark.parametrize(
    "content,expected",
    [
        (RIS, "ris"),
        (BIBTEX, "bibtex"),
        (ENDNOTE, "enw"),
        (CSV, "csv"),
        (CIW, "ciw"),
        ("A standalone title\nSecond line", "txt"),
    ],
)
def test_detect_format_from_content(content, expected):
    assert detect_format(None, content) == expected


def test_parse_ris_full_and_multiple_records():
    records = parse_import(RIS)
    assert len(records) == 2
    first = records[0]
    assert first["title"] == "First Paper"
    assert first["authors"] == ["Alice Smith", "Bob Jones"]
    assert first["year"] == 2020
    assert first["venue"] == "Journal A"
    assert first["doi"] == "10.1000/abc"
    assert first["ids"] == {"doi": "10.1000/abc"}
    assert first["abstract"] == "Abstract one"
    assert first["url"] == "https://example.com/1"
    assert first["sources"] == ["import"]
    assert records[1]["title"] == "Second Paper"
    assert records[1]["authors"] == ["Carol White"]
    assert records[1]["year"] == 2019


def test_ris_single_space_spacing():
    content = "TY - JOUR\nTI - Spaced\nAU - A B\nPY - 2001\nER -"
    records = parse_import(content, "ris")
    assert records[0]["title"] == "Spaced"
    assert records[0]["authors"] == ["A B"]


def test_parse_bibtex_full_and_multiple_records():
    records = parse_import(BIBTEX)
    assert len(records) == 2
    first = records[0]
    assert first["title"] == "First Paper"
    assert first["authors"] == ["Alice Smith", "Bob Jones"]
    assert first["year"] == 2020
    assert first["venue"] == "Journal A"
    assert first["doi"] == "10.1000/abc"
    assert first["abstract"] == "Abstract one"
    assert first["url"] == "https://example.com/1"
    second = records[1]
    assert second["title"] == "Second Book"
    assert second["authors"] == ["Carol White"]
    assert second["year"] == 2019
    assert second["venue"] == "Book Series"
    assert second["citation_count"] == 12
    assert "doi" not in second


def test_parse_endnote_full_and_multiple_records():
    records = parse_import(ENDNOTE)
    assert len(records) == 2
    first = records[0]
    assert first["title"] == "First Paper"
    assert first["authors"] == ["Alice Smith", "Bob Jones"]
    assert first["year"] == 2020
    assert first["venue"] == "Journal A"
    assert first["doi"] == "10.1000/abc"
    assert first["abstract"] == "Abstract one"
    assert first["url"] == "https://example.com/1"
    assert records[1]["title"] == "Second Paper"
    assert records[1]["authors"] == ["Carol White"]
    assert records[1]["year"] == 2019


def test_parse_csv_full():
    records = parse_import(CSV)
    assert len(records) == 2
    first = records[0]
    assert first["title"] == "First Paper"
    assert first["authors"] == ["Alice Smith", "Bob Jones"]
    assert first["year"] == 2020
    assert first["venue"] == "Journal A"
    assert first["doi"] == "10.1000/abc"
    assert first["abstract"] == "Abstract one"
    assert first["url"] == "https://example.com/1"
    assert first["citation_count"] == 42
    assert records[1]["citation_count"] == 7


def test_csv_without_header_uses_positional_fields():
    content = "First Paper,Alice Smith; Bob Jones,2020,Journal A,10.1000/abc\n"
    records = parse_import(content, "csv")
    assert records[0]["title"] == "First Paper"
    assert records[0]["authors"] == ["Alice Smith", "Bob Jones"]
    assert records[0]["year"] == 2020
    assert records[0]["venue"] == "Journal A"
    assert records[0]["doi"] == "10.1000/abc"


def test_parse_ciw_full():
    records = parse_import(CIW)
    assert len(records) == 1
    record = records[0]
    assert record["title"] == "First Paper"
    assert record["authors"] == ["Alice Smith", "Bob Jones"]
    assert record["year"] == 2020
    assert record["venue"] == "Journal A"
    assert record["doi"] == "10.1000/abc"
    assert record["abstract"] == "Abstract one"
    assert record["url"] == "https://example.com/1"
    assert record["citation_count"] == 42


def test_parse_plain_txt_single_record():
    records = parse_import("A standalone title\nSecond line")
    assert len(records) == 1
    assert records[0]["title"] == "A standalone title"
    assert records[0]["authors"] == []
    assert records[0]["sources"] == ["import"]
    assert records[0]["ids"] == {}


def test_doi_normalisation_and_numeric_coercion():
    content = "title,doi,year,citation_count\nT,https://doi.org/10.1/ABC,2021,99\n"
    record = parse_import(content, "csv")[0]
    assert record["doi"] == "10.1/abc"
    assert record["ids"]["doi"] == "10.1/abc"
    assert record["year"] == 2021
    assert isinstance(record["year"], int)
    assert record["citation_count"] == 99
    assert isinstance(record["citation_count"], int)


@pytest.mark.parametrize("content", ["", "   ", "\n\t \n"])
def test_empty_content_raises(content):
    with pytest.raises(ValueError, match="Import content is empty"):
        parse_import(content)


def test_unknown_explicit_format_raises():
    with pytest.raises(ValueError, match="Unsupported import format"):
        parse_import("whatever", "xml")


def test_missing_fields_degrade_gracefully():
    records = parse_import("TY  - JOUR\nER  -\n", "ris")
    assert len(records) == 1
    record = records[0]
    assert record["title"] == ""
    assert record["authors"] == []
    assert record["sources"] == ["import"]
    assert record["ids"] == {}
    assert "doi" not in record
    assert "year" not in record
    assert "citation_count" not in record
    assert "venue" not in record
