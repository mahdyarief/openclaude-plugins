"""Tests for deterministic manuscript quality scoring."""

from __future__ import annotations

import json

import pytest

from paperassist.claim_ledger import build_ledger
from paperassist.corpus_binder import CorpusBinding, RecordBinding
from paperassist.manuscript_quality import (
    DEFAULT_WEIGHTS,
    GRADE_BANDS,
    QualityError,
    format_quality_report,
    score_manuscript,
)
from paperassist.provenance_audit import Locator

GOOD = r"""\documentclass{article}
\begin{document}
\begin{abstract}
This review examines whether claims are addressable. We searched six databases up
to 2026 and applied PRISMA screening to 265 records. The results show that coding
tasks score highest, and we conclude that provenance must be reported.
\end{abstract}
\section{Introduction}
Prior work established the baseline \citep{alpha2020} with a locator.% @locator{alpha2020: page=3, quote="the baseline improved"}
The field now needs a measure of addressability.
\section{Method}
We searched Scopus, PubMed, Web of Science, IEEE, Scholar and Garuda using a
documented search strategy. Inclusion and exclusion criteria were applied during
screening, extraction followed a fixed form, quality appraisal used a risk of bias
instrument, and synthesis was narrative. The protocol was registered and PRISMA
reporting was used, with a search date of November 2026 and data availability noted.
\section{Results}
\begin{table}[htbp]
\caption{Scores per class.}
\label{tab:scores}
\begin{tabular}{lr}
\toprule
Class & Score \\
\midrule
A & 11 \\
\bottomrule
\end{tabular}
\end{table}
Table \ref{tab:scores} reports the scores.
\section{Discussion}
The pattern suggests a gradient rather than a binary split, and this has practical
consequences for governance.
\section{Limitations}
This review is limited by its corpus, by the extraction instrument, and by the
absence of a second coder for every record; generalisability beyond the setting is
therefore qualified.
\section{Conclusions}
Coding is the most defensible target and provenance must be measured directly.
\end{document}
"""


def test_dimensions_cover_every_weight():
    report = score_manuscript(GOOD)
    names = {dimension.name for dimension in report.dimensions}
    assert names == set(DEFAULT_WEIGHTS)


def test_good_manuscript_scores_higher_than_empty_skeleton():
    sparse = r"""\begin{document}
\section{Introduction}
A short note.
\end{document}
"""
    good = score_manuscript(GOOD)
    poor = score_manuscript(sparse)
    assert good.score > poor.score
    assert good.grade <= poor.grade  # A < C lexicographically


def test_missing_sections_are_blocking_findings():
    sparse = r"""\begin{document}
\section{Introduction}
Text.
\end{document}
"""
    report = score_manuscript(sparse)
    critical = [f.message for f in report.findings(min_severity="critical")]
    assert any("missing required section" in message for message in critical)


def test_em_dash_is_flagged_and_penalised():
    with_dash = GOOD.replace(
        "The pattern suggests a gradient",
        "The pattern --- a clear one --- suggests a gradient",
    )
    base = score_manuscript(GOOD)
    dashed = score_manuscript(with_dash)
    style = dashed.dimension("prose_style")
    assert style.measurements["em_dashes"] == 2
    assert style.score < 1.0
    assert dashed.score < base.score
    assert any("em dash" in f.message for f in style.findings)


def test_em_dash_can_be_allowed_explicitly():
    with_dash = GOOD.replace(
        "The pattern suggests a gradient",
        "The pattern --- a clear one --- suggests a gradient",
    )
    report = score_manuscript(with_dash, allow_em_dash=True)
    assert report.dimension("prose_style").score == 1.0


def test_numeric_en_dash_range_is_allowed():
    text = GOOD.replace("up\nto 2026", "up\nto 2026").replace(
        "of November 2026", "of November 2026"
    )
    text = text.replace(
        "The field now needs", "Ranges run 2015--2026 across the field. The field now needs"
    )
    report = score_manuscript(text)
    style = report.dimension("prose_style")
    assert style.measurements["numeric_ranges"] >= 1
    assert style.measurements["en_dashes_outside_ranges"] == 0


def test_unsupported_assertions_lower_provenance():
    text = GOOD.replace(
        "The field now needs a measure of addressability.",
        "In total 96.4 percent of studies omit the measure entirely.",
    )
    report = score_manuscript(text)
    assert report.dimension("provenance").measurements["unsupported"] >= 1
    assert report.dimension("provenance").score < 1.0


def test_binding_drives_citation_coverage():
    binding = CorpusBinding(
        records=tuple(
            RecordBinding(record_id=f"r{i}", title=f"T{i}", doi=f"10.1/{i}", year="2024")
            for i in range(10)
        )
    )
    report = score_manuscript(
        GOOD,
        ledger=build_ledger(GOOD),
        binding=binding,
        bibliography_entries=["alpha2020"],
    )
    citations = report.dimension("citations")
    assert citations.measurements["corpus_records"] == 10
    assert citations.measurements["corpus_coverage"] == 0.0
    assert any("extracted records" in f.message for f in citations.findings)


def test_abstract_dimension_detects_missing_environment():
    text = GOOD.replace("\\begin{abstract}", "").replace("\\end{abstract}", "")
    report = score_manuscript(text)
    assert report.dimension("abstract").score == 0.0


def test_method_rigour_counts_signals():
    report = score_manuscript(GOOD)
    method = report.dimension("method_rigour")
    assert method.score > 0.6
    assert "search strategy" in method.measurements["signals"]


def test_method_rigour_recognises_affixed_indonesian_screening():
    """peN- mutation of 'saring' must not read as a missing screening process."""
    method_text = (
        r"\section{Metode}"
        "\nPencarian basis data mengikuti protokol PRISMA. Kriteria inklusi dan "
        "kriteria eksklusi diterapkan melalui penyaringan judul dan abstrak, lalu "
        "ekstraksi data, penilaian kualitas, dan sintesis tematik.\n"
        r"\section{Hasil}"
        "\nHasil kajian menunjukkan temuan utama.\n"
    )
    report = score_manuscript(method_text)
    method = report.dimension("method_rigour")
    assert "screening process" in method.measurements["signals"]
    assert "screening process" not in method.measurements["missing"]


def test_limitations_absent_is_penalised():
    text = GOOD.replace("\\section{Limitations}", "\\section{Notes}")
    report = score_manuscript(text)
    assert report.dimension("limitations").score < 0.5


def test_table_labels_must_be_referenced(tmp_path, monkeypatch):
    text = GOOD.replace("Table \\ref{tab:scores} reports the scores.", "The table reports scores.")
    report = score_manuscript(text)
    findings = [f.message for f in report.dimension("tables_figures").findings]
    assert any("never referenced" in message for message in findings)


def test_empty_input_is_rejected():
    with pytest.raises(QualityError):
        score_manuscript("   ")


def test_invalid_weights_are_rejected():
    with pytest.raises(QualityError):
        score_manuscript(GOOD, weights={"nonsense": 1.0})


def test_invalid_min_anchored_is_rejected():
    with pytest.raises(QualityError):
        score_manuscript(GOOD, min_anchored=0)


def test_grade_bands_are_descending():
    thresholds = [threshold for _, threshold in GRADE_BANDS]
    assert thresholds == sorted(thresholds, reverse=True)


def test_report_serialises_and_is_deterministic():
    first = score_manuscript(GOOD)
    second = score_manuscript(GOOD)
    assert first.digest == second.digest
    payload = first.to_dict()
    assert payload["schema"] == "paperassist.manuscript-quality/v1"
    json.dumps(payload)


def test_report_formats_findings():
    sparse = r"""\begin{document}
\section{Introduction}
Text.
\end{document}
"""
    rendered = format_quality_report(score_manuscript(sparse))
    assert "Manuscript quality report" in rendered
    assert "Blocking findings" in rendered


def test_locators_raise_provenance_via_ledger():
    locators = [Locator(key="alpha2020", page="3", quote="the baseline improved")]
    ledger = build_ledger(GOOD, locators=locators)
    report = score_manuscript(GOOD, ledger=ledger)
    provenance = report.dimension("provenance")
    assert provenance.measurements["grounded"] >= 1


TABLE_PLACEHOLDER = r"""\begin{document}
\section{Introduction}
Prior work established the baseline.
\section{Results}
\begin{table}[htbp]
\caption{Reported metrics.}
\label{tab:metrics}
\begin{tabular}{lcr}
\toprule
Study & F1 & AUC \\
\midrule
S1 & 0.81 & 0.77 \\
S2 & --- & --- \\
\bottomrule
\end{tabular}
\end{table}
Table \ref{tab:metrics} reports the metrics.
\section{Discussion}
The pattern is stable.
\section{Limitations}
The corpus is small.
\section{Conclusion}
Provenance must be reported.
\end{document}
"""


def test_table_placeholder_is_not_an_em_dash():
    report = score_manuscript(TABLE_PLACEHOLDER)
    style = report.dimension("prose_style")
    assert style.measurements["em_dashes"] == 0
    assert style.score == 1.0


def test_em_dash_in_running_prose_still_fails():
    text = TABLE_PLACEHOLDER.replace(
        "The pattern is stable.", "The pattern is stable --- and it replicates."
    )
    style = score_manuscript(text).dimension("prose_style")
    assert style.measurements["em_dashes"] == 1
    assert style.score < 1.0


def test_synthesis_must_scale_with_the_corpus():
    binding = CorpusBinding(
        records=tuple(
            RecordBinding(record_id=f"r{i}", title=f"T{i}", doi=f"10.1/{i}", year="2024")
            for i in range(108)
        )
    )
    short = score_manuscript(GOOD, binding=binding)
    depth = short.dimension("depth")
    assert depth.measurements["corpus_records"] == 108
    assert depth.measurements["synthesis_target"] == 108 * 25
    assert depth.score < 1.0
    assert any("included studies" in f.message for f in depth.findings)


def test_formulaic_prose_is_flagged_without_claiming_authorship():
    text = GOOD.replace(
        "The field now needs a measure of addressability.",
        "Tidak dapat dipungkiri bahwa hal ini memainkan peran penting. "
        "Perlu diingat bahwa topik ini sangat penting.",
    )
    report = score_manuscript(text)
    dimension = report.dimension("formulaic_prose")
    assert dimension is not None
    assert dimension.measurements["formulaic_phrase_count"] >= 3
    assert dimension.measurements["is_authorship_detector"] is False
    assert dimension.score < 1.0


def test_formulaic_prose_keeps_ordinary_academic_terms():
    text = GOOD.replace(
        "The field now needs a measure of addressability.",
        "Literatur menunjukkan hasil yang signifikan dan metode ini penting "
        "bagi penelitian lanjutan.",
    )
    dimension = score_manuscript(text).dimension("formulaic_prose")
    assert dimension.measurements["formulaic_phrases"] == []
    assert dimension.score == 1.0


def test_uniform_sentence_rhythm_is_an_informational_signal():
    uniform = " ".join(["Data ini menunjukkan pola yang sama."] * 8)
    text = f"\\begin{{document}}\n{uniform}\n\\end{{document}}\n"
    dimension = score_manuscript(text).dimension("formulaic_prose")
    assert dimension.measurements["formulaic_phrase_count"] == 0
    assert dimension.measurements["uniform_sentence_rhythm"] is True
    assert all(f.severity == "info" for f in dimension.findings)


def test_corpus_floor_does_not_reward_a_short_review():
    large = CorpusBinding(
        records=tuple(
            RecordBinding(record_id=f"r{i}", title=f"T{i}", doi=f"10.1/{i}", year="2024")
            for i in range(108)
        )
    )
    small = CorpusBinding(
        records=tuple(
            RecordBinding(record_id=f"r{i}", title=f"T{i}", doi=f"10.1/{i}", year="2024")
            for i in range(2)
        )
    )
    same_text = GOOD
    assert (
        score_manuscript(same_text, binding=large).dimension("depth").score
        <= score_manuscript(same_text, binding=small).dimension("depth").score
    )
