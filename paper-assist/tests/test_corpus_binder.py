"""Tests for deterministic corpus binding and BibTeX generation."""

from __future__ import annotations

import json

import pytest

from paperassist.corpus_binder import (
    CorpusError,
    CorpusSafetyError,
    assign_bibtex_keys,
    bind_corpus,
    enrich_records_with_ris,
    format_binding_report,
    generate_bibtex,
    normalize_doi,
    normalize_title,
    parse_bib_entries,
    parse_ris,
    render_study_catalogue,
)

BIB = """@article{alpha2020,
  title = {A Study of Something Rather Specific},
  doi = {10.1000/alpha},
  year = {2020}
}

@article{beta2021,
  title = {Another Distinct Contribution To The Field},
  year = {2021}
}
"""


@pytest.fixture
def corpus(tmp_path):
    (tmp_path / "pdfs").mkdir()
    (tmp_path / "pdfs" / "r001.pdf").write_bytes(b"%PDF-1.4 alpha")
    (tmp_path / "pdfs" / "r002.pdf").write_bytes(b"%PDF-1.4 beta")
    (tmp_path / "refs.bib").write_text(BIB, encoding="utf-8")
    (tmp_path / "records.json").write_text(
        json.dumps(
            [
                {"id": "r001", "title": "A Study of Something Rather Specific",
                 "doi": "https://doi.org/10.1000/alpha", "year": "2020",
                 "authors": "Alpha, A."},
                {"id": "r002", "title": "Another Distinct Contribution To The Field",
                 "doi": "", "year": "2021", "authors": "Beta, B."},
                {"id": "r003", "title": "Unbound Work With No Source",
                 "doi": "10.9999/missing", "year": "2022"},
            ]
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_normalize_doi_accepts_urls_and_rejects_noise():
    assert normalize_doi("https://doi.org/10.1000/ABC") == "10.1000/abc"
    assert normalize_doi("doi: 10.1000/xyz.") == "10.1000/xyz"
    assert normalize_doi("not-a-doi") == ""
    assert normalize_doi(None) == ""


def test_normalize_title_strips_year_and_punctuation():
    assert normalize_title("2020: A Study, of Things!") == "astudyofthings"
    assert normalize_title("") == ""


def test_parse_bib_entries_reads_title_and_doi():
    entries = parse_bib_entries(BIB)
    assert [entry.key for entry in entries] == ["alpha2020", "beta2021"]
    assert entries[0].fields["doi"] == "10.1000/alpha"
    assert entries[1].fields["title"].startswith("Another")


def test_bind_corpus_matches_by_doi_and_record_id(corpus):
    binding = bind_corpus(
        corpus,
        {
            "records_path": "records.json",
            "fulltext_root": "pdfs",
            "bibliography_path": "refs.bib",
        },
    )
    by_id = {record.record_id: record for record in binding.records}
    assert by_id["r001"].text_path == "r001.pdf"
    assert by_id["r001"].bib_key == "alpha2020"
    assert by_id["r002"].text_path == "r002.pdf"
    assert by_id["r002"].bib_key == "beta2021"
    assert by_id["r003"].bound is False


def test_binding_reports_coverage_and_unmatched_keys(corpus):
    binding = bind_corpus(
        corpus,
        {
            "records_path": "records.json",
            "fulltext_root": "pdfs",
            "bibliography_path": "refs.bib",
        },
    )
    coverage = binding.coverage()
    assert coverage["records"] == 3
    assert coverage["with_full_text"] == 2
    assert coverage["with_bibliography_entry"] == 2
    assert coverage["fully_bound"] == 2
    assert coverage["uncited_records"] == 1
    assert binding.unexplained_bib_keys == ()


def test_binding_digest_is_stable(corpus):
    payload = {
        "records_path": "records.json",
        "fulltext_root": "pdfs",
        "bibliography_path": "refs.bib",
    }
    first = bind_corpus(corpus, payload)
    second = bind_corpus(corpus, payload)
    assert first.digest == second.digest


def test_unmatched_bib_key_is_reported(corpus):
    (corpus / "refs.bib").write_text(
        BIB + "\n@article{ghost1999,\n title={Never Cited Work Here},\n year={1999}\n}\n",
        encoding="utf-8",
    )
    binding = bind_corpus(
        corpus,
        {
            "records_path": "records.json",
            "fulltext_root": "pdfs",
            "bibliography_path": "refs.bib",
        },
    )
    assert binding.unexplained_bib_keys == ("ghost1999",)
    assert binding.coverage()["unmatched_bib_keys"] == 1


def test_generate_bibtex_only_for_unbound_records(corpus):
    binding = bind_corpus(
        corpus,
        {
            "records_path": "records.json",
            "fulltext_root": "pdfs",
            "bibliography_path": "refs.bib",
        },
    )
    records = json.loads((corpus / "records.json").read_text(encoding="utf-8"))
    text, warnings = generate_bibtex(binding, records)
    assert "r003" not in text
    assert "10.9999/missing" in text
    assert "@misc{" in text
    assert warnings and "no author recorded" in warnings[0]


def test_generated_keys_do_not_collide(tmp_path):
    """Records without authors still receive distinct bibliography keys.

    Extraction tables commonly omit author names, which collapses unrelated
    records onto the same ``anon<year>`` stem. Duplicate keys would silently
    drop all but one entry when BibTeX processes the file.
    """

    (tmp_path / "pdfs").mkdir()
    (tmp_path / "refs.bib").write_text(BIB, encoding="utf-8")
    records = [
        {"id": f"r{n:03d}", "title": f"An Unrelated Contribution Number {n}",
         "doi": f"10.1000/item{n}", "year": "2024"}
        for n in range(1, 6)
    ]
    (tmp_path / "records.json").write_text(json.dumps(records), encoding="utf-8")
    binding = bind_corpus(
        tmp_path,
        {
            "records_path": "records.json",
            "fulltext_root": "pdfs",
            "bibliography_path": "refs.bib",
        },
    )
    _, text, _ = assign_bibtex_keys(binding, records)
    keys = [entry.key for entry in parse_bib_entries(text)]
    assert len(keys) == len(records)
    assert len(set(keys)) == len(keys)
    assert not set(keys) & {"alpha2020", "beta2021"}


def test_study_catalogue_cites_every_bound_record(tmp_path):
    """The catalogue makes the whole corpus citable, not only the cited subset."""

    (tmp_path / "pdfs").mkdir()
    (tmp_path / "refs.bib").write_text(BIB, encoding="utf-8")
    records = [
        {"id": f"r{n:03d}", "title": f"Paper Number {n}", "doi": f"10.1000/p{n}",
         "year": "2024", "journal": "Journal of Testing"}
        for n in range(1, 4)
    ]
    (tmp_path / "records.json").write_text(json.dumps(records), encoding="utf-8")
    binding = bind_corpus(
        tmp_path,
        {
            "records_path": "records.json",
            "fulltext_root": "pdfs",
            "bibliography_path": "refs.bib",
        },
    )
    catalogue, warnings = render_study_catalogue(
        binding, records, key_by_id={"r001": "a2024b", "r002": "a2024c", "r003": "a2024d"},
        caption="Included studies",
        label="tab:studies",
    )
    assert warnings == ()
    assert r"\label{tab:studies}" in catalogue
    assert r"\caption{Included studies}" in catalogue
    assert catalogue.count(r"\citep{") == 3
    assert catalogue.count(r"\textit{") == 3


def test_catalogue_uses_fields_present_across_the_corpus(tmp_path):
    """Columns only appear when they carry data in a quarter of the corpus."""

    (tmp_path / "pdfs").mkdir()
    (tmp_path / "refs.bib").write_text(BIB, encoding="utf-8")
    records = [
        {"id": f"r{n:03d}", "title": f"Paper Number {n}", "year": "2024",
         "dataset_n": str(n * 100)}
        for n in range(1, 6)
    ]
    (tmp_path / "records.json").write_text(json.dumps(records), encoding="utf-8")
    binding = bind_corpus(
        tmp_path,
        {
            "records_path": "records.json",
            "fulltext_root": "pdfs",
            "bibliography_path": "refs.bib",
        },
    )
    catalogue, _ = render_study_catalogue(binding, records)
    assert "Dataset N" in catalogue
    assert "Journal" not in catalogue


def test_catalogue_escapes_latex_special_characters(tmp_path):
    (tmp_path / "pdfs").mkdir()
    (tmp_path / "refs.bib").write_text(BIB, encoding="utf-8")
    records = [
        {"id": "r001", "title": "A&B 100% of {data}", "year": "2024"},
    ]
    (tmp_path / "records.json").write_text(json.dumps(records), encoding="utf-8")
    binding = bind_corpus(
        tmp_path,
        {
            "records_path": "records.json",
            "fulltext_root": "pdfs",
            "bibliography_path": "refs.bib",
        },
    )
    catalogue, _ = render_study_catalogue(
        binding, records,
        key_by_id={"r001": "alpha2020"},
        columns=("year",),
    )
    assert "\\&" in catalogue
    assert "\\%" in catalogue
    assert "\\{" in catalogue


RIS = """\
TY  - JOUR
TI  - A robust and interpretable ensemble machine learning model for predicting healthcare insurance fraud
AU  - Ze-Yu Wang
AU  - Xiao-Fang Chen
JO  - Scientific Reports
PY  - 2025
DO  - 10.1038/s41598-024-82062-x
ER  -
TY  - JOUR
TI  - Use of responsible artificial intelligence to predict health insurance claims
AU  - A. N. M. Sajedul Alam
JO  - Exploration of Digital Health Technologies
PY  - 2024
DO  - 10.37349/edht.2024.00009
ER  -
"""


def test_parse_ris_extracts_identity_fields():
    records = parse_ris(RIS)
    assert len(records) == 2
    assert records[0]["authors"] == "Ze-Yu Wang and Xiao-Fang Chen"
    assert records[0]["type"] == "JOUR"
    assert records[0]["year"] == "2025"
    assert records[1]["journal"] == "Exploration of Digital Health Technologies"
    assert records[1]["doi"] == "10.37349/edht.2024.00009"


def test_ris_fills_authors_without_overwriting_extraction_values():
    records = [
        {"id": "r001",
         "title": "A robust and interpretable ensemble machine learning model for predicting healthcare insurance fraud",
         "doi": "10.1038/s41598-024-82062-x", "year": "2023", "journal": "Original Venue"},
    ]
    enriched, filled = enrich_records_with_ris(records, parse_ris(RIS))
    assert filled == 1
    assert enriched[0]["authors"] == "Ze-Yu Wang and Xiao-Fang Chen"
    assert enriched[0]["journal"] == "Original Venue"
    assert enriched[0]["year"] == "2023"


def test_report_lists_full_text_without_citation(corpus):
    binding = bind_corpus(
        corpus,
        {
            "records_path": "records.json",
            "fulltext_root": "pdfs",
            "bibliography_path": "refs.bib",
        },
    )
    report = format_binding_report(binding)
    assert "Corpus binding report" in report
    assert "uncited records: 1" in report


def test_missing_fulltext_root_is_rejected(corpus):
    with pytest.raises(CorpusError):
        bind_corpus(
            corpus,
            {"records_path": "records.json", "fulltext_root": "does-not-exist"},
        )


def test_fulltext_root_cannot_escape_workspace(corpus):
    with pytest.raises((CorpusSafetyError, CorpusError)):
        bind_corpus(
            corpus,
            {"records_path": "records.json", "fulltext_root": str(corpus.parent)},
        )


def test_empty_records_are_rejected(corpus):
    with pytest.raises(CorpusError):
        bind_corpus(corpus, {"records": [], "fulltext_root": "pdfs"})


def test_inline_records_are_accepted(corpus):
    binding = bind_corpus(
        corpus,
        {
            "records": [{"id": "r001", "title": "A Study of Something Rather Specific"}],
            "fulltext_root": "pdfs",
        },
    )
    assert len(binding.records) == 1
    assert binding.records[0].text_path == "r001.pdf"


def test_record_binding_serialises(corpus):
    binding = bind_corpus(
        corpus,
        {
            "records_path": "records.json",
            "fulltext_root": "pdfs",
            "bibliography_path": "refs.bib",
        },
    )
    payload = binding.to_dict()
    assert payload["schema"] == "paperassist.corpus-binding/v1"
    json.dumps(payload)  # must be serialisable


RIS_AFFILIATION = """\
TY  - JOUR
TI  - Claim Adjudication at Scale
AU  - Sr. Software Development Engineer, Adjudication - Rxclaim Application, CVS Health, 2100 E Lake Cook Road, Buffalo Grove Illinois 60047, USA
AU  - Real Author Name
DO  - 10.1000/affil
ER  -
"""


def test_ris_author_field_with_affiliation_is_rejected():
    records = parse_ris(RIS_AFFILIATION)
    assert records[0]["authors"] == "Real Author Name"


def test_replacement_character_is_stripped_from_bibtex(tmp_path):
    (tmp_path / "pdfs").mkdir()
    (tmp_path / "refs.bib").write_text("", encoding="utf-8")
    records = [
        {"id": "r001", "title": "Swedish Summaries \ufffd ICD-10 Coding",
         "doi": "10.1000/bad", "year": "2021"},
    ]
    (tmp_path / "records.json").write_text(json.dumps(records), encoding="utf-8")
    binding = bind_corpus(
        tmp_path,
        {
            "records_path": "records.json",
            "fulltext_root": "pdfs",
            "bibliography_path": "refs.bib",
        },
    )
    _, text, _ = assign_bibtex_keys(binding, records)
    assert "\ufffd" not in text
    assert "ICD-10 Coding" in text
