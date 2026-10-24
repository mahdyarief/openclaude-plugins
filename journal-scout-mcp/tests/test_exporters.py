"""Tests for josc.exporters."""

import json

import pytest

from josc.exporters import FORMATTERS, format_papers


SAMPLE = [
    {
        "doi": "10.1109/5.771073",
        "title": "Long Short-Term Memory",
        "year": 1997,
        "authors": ["Sepp Hochreiter", "Jürgen Schmidhuber"],
        "venue": "Neural Computation",
        "url": "https://doi.org/10.1109/5.771073",
        "pdf_url": None,
        "citation_count": 95000,
        "is_open_access": False,
        "type": "article",
        "sources": ["scopus", "crossref"],
        "ids": {"doi": "10.1109/5.771073"},
        "abstract": None,
    },
    {
        "doi": "10.1038/nature14539",
        "title": "Deep learning.",
        "year": 2015,
        "authors": ["Yann LeCun", "Yoshua Bengio", "Geoffrey Hinton"],
        "venue": "Nature",
        "url": "https://doi.org/10.1038/nature14539",
        "pdf_url": None,
        "citation_count": 50000,
        "is_open_access": False,
        "type": "article",
        "sources": ["openalex"],
        "ids": {"doi": "10.1038/nature14539"},
        "abstract": "Deep learning allows computational models…",
    },
]


def test_supported_formats_are_advertised():
    assert set(FORMATTERS) == {
        "bibtex",
        "ris",
        "csv",
        "json",
        "endnote",
        "isi",
        "csv_header",
        "apa",
        "chicago",
        "harvard",
        "vancouver",
    }


def test_bibtex_emits_one_entry_per_paper():
    out = format_papers(SAMPLE, "bibtex")
    # Two papers = two @article blocks.
    assert out.count("@article{") == 2
    # DOI-derived citation key for the first one.
    assert "@article{10_1109_5_771073," in out
    # Author list joined with ` and ` (BibTeX convention); umlaut becomes
    # the LaTeX `\"` escape, not the raw character.
    assert "Sepp Hochreiter and J{\\\"u}rgen Schmidhuber" in out
    # Each entry closes with `}\n` followed by a blank-line separator before
    # the next @entry.
    assert out.count("}\n") >= 2


def test_bibtex_uses_doi_derived_keys_and_includes_url():
    out = format_papers(SAMPLE, "bibtex")
    # No DOIs -> no DOI-derived keys, but every entry has a url field if url present.
    assert "url    = {https://doi.org/10.1109/5.771073}" in out
    # No year-based fallback should be reached because DOIs are present.
    assert "_1997" not in out and "_2015" not in out


def test_bibtex_falls_back_to_author_year_when_doi_missing():
    papers = [{"title": "X", "authors": ["Ada Lovelace"], "year": 1843}]
    out = format_papers(papers, "bibtex")
    assert "@article{lovelace1843," in out


def test_ris_emits_ty_and_er_per_paper():
    out = format_papers(SAMPLE, "ris")
    assert out.count("TY  - JOUR") == 2
    assert out.count("ER  -") == 2
    # Each author on its own AU line; first paper has 2 authors, second has 3.
    assert out.count("AU  -") == 5
    # Abstract field is only emitted when the paper actually carries one.
    assert "AB  - Deep learning allows computational models" in out
    assert out.count("AB  -") == 1


def test_csv_emits_header_and_one_row_per_paper():
    out = format_papers(SAMPLE, "csv")
    rows = out.strip().splitlines()
    assert rows[0].startswith("title,authors,year,venue,doi")
    assert len(rows) == 1 + len(SAMPLE)
    # List field (authors) flattens to "; " in CSV.
    assert "Sepp Hochreiter; Jürgen Schmidhuber" in rows[1]


def test_csv_empty_input_yields_empty_string():
    assert format_papers([], "csv") == ""


def test_json_round_trips_the_papers_list():
    out = format_papers(SAMPLE, "json")
    parsed = json.loads(out)
    assert parsed == SAMPLE


def test_endnote_emits_tagged_records():
    out = format_papers(SAMPLE, "endnote")
    # One record per paper, each terminated by a blank line.
    assert out.count("%0 Journal Article") == 2
    assert out.endswith("\n\n")
    assert "%A Sepp Hochreiter" in out
    assert "%A Jürgen Schmidhuber" in out
    assert "%T Long Short-Term Memory" in out
    assert "%J Neural Computation" in out
    assert "%D 1997" in out
    assert "%R 10.1109/5.771073" in out
    assert "%U https://doi.org/10.1109/5.771073" in out
    # Abstract only appears when the paper carries one.
    assert out.count("%X ") == 1
    assert "%X Deep learning allows computational models" in out


def test_isi_emits_wos_tagged_records():
    out = format_papers(SAMPLE, "isi")
    assert out.count("PT J") == 2
    assert out.count("ER") == 2
    assert out.count("AU ") == 5
    assert "TI Long Short-Term Memory" in out
    assert "SO Neural Computation" in out
    assert "PY 1997" in out
    assert "DI 10.1109/5.771073" in out
    assert out.endswith("\n\n")


def test_csv_header_has_requested_columns():
    out = format_papers(SAMPLE, "csv_header")
    rows = out.strip().splitlines()
    assert rows[0] == (
        "doi,title,year,authors,venue,citation_count,url,pdf_url,"
        "is_open_access,type,sources,abstract"
    )
    assert len(rows) == 1 + len(SAMPLE)
    assert "Sepp Hochreiter; Jürgen Schmidhuber" in rows[1]


def test_apa_formats_first_author_and_doi():
    out = format_papers(SAMPLE, "apa")
    assert "Hochreiter, S. (1997). Long Short-Term Memory. Neural Computation. https://doi.org/10.1109/5.771073" in out
    assert "LeCun, Y. (2015). Deep learning. Nature. https://doi.org/10.1038/nature14539" in out


def test_chicago_formats_first_author_and_title():
    out = format_papers(SAMPLE, "chicago")
    assert 'Hochreiter, Sepp. "Long Short-Term Memory." Neural Computation (1997).' in out
    assert 'LeCun, Yann. "Deep learning." Nature (2015).' in out


def test_harvard_formats_first_author_and_venue():
    out = format_papers(SAMPLE, "harvard")
    assert "Hochreiter, S. (1997) 'Long Short-Term Memory', Neural Computation." in out
    assert "LeCun, Y. (2015) 'Deep learning', Nature." in out


def test_vancouver_formats_first_author_and_year():
    out = format_papers(SAMPLE, "vancouver")
    assert "Hochreiter S. Long Short-Term Memory. Neural Computation. 1997." in out
    assert "LeCun Y. Deep learning. Nature. 2015." in out


def test_citation_styles_survive_missing_author_and_year():
    papers = [{"title": "Untitled work"}]
    assert format_papers(papers, "apa") == "Anonymous (n.d.). Untitled work.\n"
    assert format_papers(papers, "chicago") == 'Anonymous. "Untitled work." (n.d.).\n'
    assert format_papers(papers, "harvard") == "Anonymous (n.d.) 'Untitled work'.\n"
    assert format_papers(papers, "vancouver") == "Anonymous. Untitled work.\n"


def test_unknown_format_raises_with_supported_list():
    with pytest.raises(ValueError) as exc:
        format_papers(SAMPLE, "yaml")
    msg = str(exc.value)
    assert "yaml" in msg
    for fmt in ("bibtex", "ris", "csv", "json"):
        assert fmt in msg


def test_empty_input_returns_empty_string_for_every_format():
    for fmt in FORMATTERS:
        assert format_papers([], fmt) == ""
