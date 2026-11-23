"""Tests for the source-coverage audit."""

import pytest

from paperassist.source_coverage import (
    CoverageError,
    audit_source_coverage,
    format_source_coverage,
)

SOURCE = """\
# Pendahuluan
Klaim ditolak pada tingkat 24% dengan waktu siklus 47 hari pada tahun 2019.

## Pertanyaan riset
Kajian menjawab RQ-B tentang provenance normatif dan RQ-C tentang kelas tugas.

# Metode
Pencarian mengekstraksi 108 studi dan mencatat 265 rekaman awal.

# Hasil
Median ukuran data adalah 22039 baris pada 32 studi.
Peringkat kelayakan menempatkan koding diagnosis di 11,1 dari 12.

# Diskusi
Bukti efektivitas tertinggi terkumpul pada kelas koding sebesar 65 studi.
"""

MANUSCRIPT = r"""\documentclass{article}
\begin{document}
\section{Pendahuluan}
Klaim ditolak pada tingkat 24% dengan waktu siklus 47 hari pada tahun 2019.
\section{Pertanyaan riset}
Kajian menjawab RQ-B tentang provenance normatif dan RQ-C tentang kelas tugas.
\section{Metode}
Pencarian mengekstraksi 108 studi dari 265 rekaman awal.
\section{Hasil}
Median ukuran data adalah 22039 baris pada 32 studi, dengan skor 11,1 dari 12.
\section{Diskusi}
Bukti efektivitas tertinggi terkumpul pada 65 studi.
\end{document}
"""


def test_all_sections_covered_when_numbers_survive():
    result = audit_source_coverage(SOURCE, MANUSCRIPT)
    assert result.covered_count == 5
    assert result.missing_count == 0
    assert result.unaccounted_count == 0
    assert result.passed


def test_missing_number_marks_section_partial():
    # The section survives by name but the result it asserts is gone, which is
    # the omission a reviewer is most likely to catch.
    manuscript = MANUSCRIPT.replace(", dengan skor 11,1 dari 12", "")
    result = audit_source_coverage(SOURCE, manuscript)
    assert any(f.section == "Hasil" for f in result.partial)
    assert "11.1" in result.unaccounted_numbers
    assert "12" in result.unaccounted_numbers


def test_dropped_section_is_reported_missing():
    manuscript = MANUSCRIPT.replace(
        r"\section{Metode}"
        + "\n"
        + "Pencarian mengekstraksi 108 studi dari 265 rekaman awal.",
        "",
    )
    result = audit_source_coverage(SOURCE, manuscript)
    assert any(f.section == "Metode" for f in result.missing)
    assert not result.passed


def test_rewritten_heading_still_counts_as_covered():
    """A journal rewords headings; rewording with shared content words is fine."""
    manuscript = MANUSCRIPT.replace(
        r"\section{Pertanyaan riset}", r"\section{Rumusan pertanyaan riset}"
    )
    result = audit_source_coverage(SOURCE, manuscript)
    assert not any(f.section == "Pertanyaan riset" for f in result.findings)


def test_small_organisation_numbers_are_ignored():
    """Stub sections and section numbers must not become findings."""
    source = "# Hasil\nBagian 2 membahas 3 hal.\n"
    manuscript = "# Hasil\nBagian ini membahas topik utama.\n"
    result = audit_source_coverage(source, manuscript)
    assert result.unaccounted_count == 0


def test_empty_inputs_are_rejected():
    with pytest.raises(CoverageError):
        audit_source_coverage("", MANUSCRIPT)
    with pytest.raises(CoverageError):
        audit_source_coverage(SOURCE, "   ")


def test_report_is_markdown():
    report = format_source_coverage(audit_source_coverage(SOURCE, MANUSCRIPT))
    assert "Source coverage" in report
    assert "Covered" in report
    assert report.endswith("\n")


def test_bibliography_section_is_not_treated_as_content():
    """Volume and page numbers in a reference list are not asserted findings."""
    source = SOURCE + "\n# Referensi\n1. Smith, J. (2020). Title. Journal, 12(3), 445-467. doi:10.1000/xyz\n"
    manuscript = MANUSCRIPT.replace(
        r"\end{document}", "\\section{Referensi}\nSmith 2020.\n\\end{document}"
    )
    result = audit_source_coverage(source, manuscript)
    assert not any(f.section == "Referensi" for f in result.findings)
    assert "467" not in result.unaccounted_numbers


def test_identifier_digits_are_not_asserted_numbers():
    """DOIs and long opaque ids must not flood the unaccounted list."""
    source = "# Hasil\nOkurasi 0,91 dicapai; data pada 10.1109/abcd.2021.9432100.\n"
    manuscript = "# Hasil\nOkurasi dicapai pada kohort besar.\n"
    result = audit_source_coverage(source, manuscript)
    assert "0.91" in result.unaccounted_numbers
    assert not any(n.startswith("10.1109") for n in result.unaccounted_numbers)
    assert "9432100" not in result.unaccounted_numbers


def test_latex_source_is_supported():
    source = (
        "\\section{Results}\n"
        "The model reached 0,91 AUC over 41200 claims in the cohort.\n"
    )
    manuscript = (
        "\\section{Results}\n"
        "The model reached 0,91 AUC over 41200 claims.\n"
    )
    result = audit_source_coverage(source, manuscript)
    assert result.missing_count == 0
