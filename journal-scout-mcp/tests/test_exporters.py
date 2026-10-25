"""Tests for josc.exporters."""

import json

import pytest

from josc.exporters import (
    FORMATTERS,
    format_metrics_csv,
    format_papers,
    format_search_report,
)


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
        "mla",
        "csiro",
        "csv_bom",
        "xls",
        "csv_plain",
        "xls_plain",
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


def test_metrics_csv_emits_scalar_section_and_by_year_table():
    metrics = {
        "papers": 3,
        "total_citations": 35,
        "h_index": 3,
        "i10_index": 2,
        "citation_velocity": None,
        "by_year": [
            {"year": 2018, "papers": 1, "citations": 20, "cumulative_citations": 20},
            {"year": 2019, "papers": 2, "citations": 15, "cumulative_citations": 35},
        ],
    }
    out = format_metrics_csv(metrics)
    rows = out.strip().splitlines()
    assert rows[0] == "Metric,Value"
    assert "Papers,3" in rows
    assert "Total citations,35" in rows
    assert "Citation velocity," in rows
    assert "Year,Papers,Citations,Cumulative citations" in rows
    assert "2018,1,20,20" in rows
    assert "2019,2,15,35" in rows


def test_metrics_csv_without_by_year_has_no_table_section():
    out = format_metrics_csv({"papers": 1, "total_citations": 5})
    assert "Year,Papers,Citations,Cumulative citations" not in out
    assert out.startswith("Metric,Value\n")


def test_metrics_csv_labels_extended_keys_with_their_real_names():
    # compute_metrics emits these keys in camel case; the formatter must read
    # the same spelling or the rows silently vanish from extended reports.
    metrics = {
        "papers": 2,
        "hc_index": 1,
        "hI_index": 1.5,
        "hI_norm": 0.75,
        "hm_index": 1.25,
        "AWCR": 4.5,
        "AW_index": 2.121,
        "AWCRpA": 2.25,
    }
    out = format_metrics_csv(metrics)
    rows = out.splitlines()
    assert "Contemporary h-index,1" in rows
    assert "hI-index,1.5" in rows
    assert "hI-norm,0.75" in rows
    assert "hm-index,1.25" in rows
    assert "AWCR,4.5" in rows
    assert "AW-index,2.121" in rows
    assert "AWCR per author,2.25" in rows


def test_metrics_csv_round_trips_a_real_extended_metrics_payload():
    # End-to-end guard: the labels must cover every key compute_metrics emits.
    from josc.graph import compute_metrics
    from josc.models import Paper

    papers = [
        Paper(doi="10.1/a", title="A", year=2018, citation_count=20, authors=["A", "B"]),
        Paper(doi="10.1/b", title="B", year=2019, citation_count=10, authors=["A"]),
        Paper(doi="10.1/c", title="C", year=2020, citation_count=5, authors=["A", "C"]),
    ]
    metrics = compute_metrics(papers, current_year=2020, mode="extended")
    rows = format_metrics_csv(metrics).splitlines()

    assert "AWCR," in "\n".join(rows)
    assert "AW-index," in "\n".join(rows)
    assert "AWCR per author," in "\n".join(rows)
    assert "Contemporary h-index," in "\n".join(rows)
    # The by-year table is appended for the same payload.
    assert "Year,Papers,Citations,Cumulative citations" in rows
    assert "2018,1,20,20" in rows


def test_mla_and_csiro_are_registered_and_format_a_known_paper():
    assert "mla" in FORMATTERS
    assert "csiro" in FORMATTERS

    mla = format_papers(SAMPLE[:1], "mla")
    assert 'Hochreiter, Sepp, and Jürgen Schmidhuber.' in mla
    assert '"Long Short-Term Memory."' in mla
    assert "Neural Computation, 1997." in mla
    assert "https://doi.org/10.1109/5.771073" in mla
    assert mla.endswith("\n")

    csiro = format_papers(SAMPLE[:1], "csiro")
    assert "Hochreiter, S. & Schmidhuber, J. (1997)." in csiro
    assert "Long Short-Term Memory." in csiro
    assert "Neural Computation." in csiro
    assert "doi:10.1109/5.771073" in csiro
    assert csiro.endswith("\n")


def test_mla_and_csiro_handle_three_authors_and_empty_input():
    three = format_papers(SAMPLE[1:2], "mla")
    assert "LeCun, Yann, et al." in three
    assert format_papers([], "mla") == ""
    assert format_papers([], "csiro") == ""


def test_csv_bom_prefixes_the_csv_output():
    plain = format_papers(SAMPLE, "csv")
    bom = format_papers(SAMPLE, "csv_bom")
    assert bom.startswith("\ufeff")
    assert bom[1:] == plain
    assert format_papers([], "csv_bom") == ""


def test_xls_is_spreadsheetml_with_escaped_cells():
    papers = [
        {
            "title": "Tom & Jerry <Rules>",
            "authors": ["A B"],
            "year": 2020,
            "venue": "V",
            "doi": "10.1/x",
            "citation_count": 3,
            "url": "https://example.org",
        },
        {
            "title": "Second",
            "authors": ["C D"],
            "year": 2021,
            "venue": "W",
            "doi": "10.1/y",
            "citation_count": 1,
            "url": "https://example.org/y",
        },
    ]
    out = format_papers(papers, "xls")
    assert out.startswith(
        '<?xml version="1.0"?>\n<?mso-application progid="Excel.Sheet"?>'
    )
    assert 'ss:Name="Papers"' in out
    assert "Tom &amp; Jerry &lt;Rules&gt;" in out
    assert out.count("<Row>") == 3
    assert format_papers([], "xls") == ""


def test_search_report_basic_vs_extended_and_deterministic():
    payload = {
        "papers": 2,
        "metrics": {
            "papers": 2,
            "total_citations": 35,
            "h_index": 2,
            "e_index": 4.5,
            "hc_index": 1,
            "AWCR": 7.5,
            "by_year": [
                {"year": 2018, "papers": 1, "citations": 20, "cumulative_citations": 20},
                {"year": 2019, "papers": 1, "citations": 15, "cumulative_citations": 35},
            ],
        },
        "authors": ["Alice A", "Bob B"],
    }

    basic = format_search_report(payload, "basic")
    extended = format_search_report(payload, "extended")

    assert basic.startswith("Search Report\n")
    assert "papers: 2" in basic
    assert "Citations by year" in basic
    assert "2018  1  20  20" in basic
    assert "Contemporary h-index" not in basic
    assert "Contemporary h-index: 1" in extended
    assert "AWCR: 7.5" in extended
    assert "Alice A" in extended
    assert basic != extended
    assert format_search_report(payload, "bogus") == basic
    assert format_search_report(payload) == format_search_report(payload)
    assert format_search_report({}) == ""


def test_csv_plain_omits_header_but_keeps_one_row_per_paper():
    out = format_papers(SAMPLE, "csv_plain")
    rows = out.strip().splitlines()
    assert len(rows) == 2
    assert not rows[0].startswith("title")
    assert "Sepp Hochreiter; Jürgen Schmidhuber" in rows[0]


def test_csv_still_emits_header_after_plain_variant_added():
    rows = format_papers(SAMPLE, "csv").strip().splitlines()
    assert rows[0].startswith("title")


def test_xls_plain_omits_header_row_but_keeps_paper_titles():
    out = format_papers(SAMPLE, "xls_plain")
    assert ">Title<" not in out
    assert ">Long Short-Term Memory<" in out
    assert out.count("<Row>") == len(SAMPLE)
    # Existing xls formatter is unchanged and still emits the header row.
    assert ">Title<" in format_papers(SAMPLE, "xls")


def test_plain_exporters_return_empty_string_for_empty_input():
    assert format_papers([], "csv_plain") == ""
    assert format_papers([], "xls_plain") == ""


def test_plain_exporters_are_registered():
    assert "csv_plain" in FORMATTERS
    assert "xls_plain" in FORMATTERS
