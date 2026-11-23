"""Cross-chapter thesis checks: research-question trace, abstracts, floats,
citation style, reference minimums and DSR detection."""

from __future__ import annotations

from types import SimpleNamespace

from paperassist.quality.compliance import _dimension_references
from paperassist.reporting_checks import ReferencePolicy, audit_references
from paperassist.research_designs import detect_research_design, detection_text
from paperassist.thesis_extras import (
    abstract_limits,
    check_abstracts,
    check_citation_style,
    check_floats,
    style_family,
    trace_research_questions,
)

QUESTIONS = [
    "Bagaimana merancang arsitektur harness verifikasi kode ICD?",
    "Seberapa besar akurasi pengodean otomatis dibanding koder manusia?",
]


def _chapters(method: str, results: str, conclusion: str) -> str:
    return (
        "\\chapter{Pendahuluan}\nLatar.\n"
        f"\\chapter{{Metodologi Penelitian}}\n{method}\n"
        f"\\chapter{{Hasil dan Pembahasan}}\n{results}\n"
        f"\\chapter{{Kesimpulan dan Saran}}\n{conclusion}\n"
    )


def test_trace_follows_each_question_by_words_or_label():
    text = _chapters(
        "\\section{Perancangan Arsitektur}\nArsitektur harness verifikasi disusun berlapis.\n"
        "\\section{Pengukuran}\nAkurasi pengodean otomatis dibanding koder manusia.\n",
        "\\section{Hasil RQ1}\nKomponen tersusun.\n\\section{Akurasi}\nAkurasi pengodean otomatis 0,82.\n",
        "\\section{Kesimpulan}\n\\begin{enumerate}\\item Arsitektur harness verifikasi tersusun."
        "\\item Akurasi pengodean otomatis mendekati koder manusia.\\end{enumerate}\n",
    )
    rows, issues = trace_research_questions(text, QUESTIONS, stage="final")
    assert rows[0]["method"] == "Perancangan Arsitektur"
    assert rows[0]["results"] == "Hasil RQ1"  # matched by its label
    assert rows[1]["method"] == "Pengukuran"
    assert rows[1]["conclusion"] == "Kesimpulan"
    assert issues == []


def test_trace_names_a_question_no_chapter_addresses():
    text = _chapters(
        "\\section{Perancangan Arsitektur}\nArsitektur harness verifikasi disusun.\n",
        "\\section{Komponen}\nArsitektur harness verifikasi berjalan.\n",
        "\\section{Kesimpulan}\nArsitektur harness verifikasi tersusun.\n",
    )
    rows, issues = trace_research_questions(text, QUESTIONS, stage="final")
    assert rows[1]["method"] is None and rows[1]["conclusion"] is None
    messages = [message for _, message, _ in issues]
    assert "research question 2 is not traced to the method chapter" in messages
    assert "research question 2 is not traced to the conclusion" in messages
    # A proposal is traced to its method chapter only.
    _, proposal_issues = trace_research_questions(text, QUESTIONS, stage="proposal")
    assert all("method chapter" in message for _, message, _ in proposal_issues)


def test_abstract_limits_come_from_the_profile_wording():
    assert abstract_limits("masing-masing maksimum 500 kata, 5 alinea") == (500, 5)
    assert abstract_limits("maksimum sekitar 500 kata") == (500, None)
    assert abstract_limits("Single abstract, usually <= 350 words.") == (350, None)


def test_abstracts_are_compared_with_each_other_and_the_limit():
    text = (
        "\\chapter*{Abstrak}\n" + "Akurasi pengodean mencapai 0,82 pada 1.500 rekam medis. " * 60
        + "\n\nKata kunci: ICD, pengodean, harness, verifikasi\n"
        "\\chapter*{Abstract}\nCoding accuracy reached 0.85 on 1,500 records.\n\n"
        "Keywords: ICD, coding, harness\n\\tableofcontents\n"
    )
    summary, issues = check_abstracts(text, layout="maksimum 500 kata")
    messages = " | ".join(message for _, message, _ in issues)
    assert "the guide allows 500" in messages
    assert "4 keywords but the English abstract 3" in messages
    assert "different numbers" in messages
    assert summary["numbers_only_in_id"] == ["0.82"]
    assert summary["numbers_only_in_en"] == ["0.85"]  # 1.500 and 1,500 agree


def test_floats_caption_placement_numbering_and_late_reference():
    text = (
        "\\counterwithout{figure}{chapter}\n"
        "\\begin{table}\\begin{tabular}{ll}a&b\\end{tabular}\\caption{T}\\label{tab:a}\\end{table}\n"
        "\\begin{figure}\\caption{F}\\includegraphics{x}\\label{fig:a}\\end{figure}\n"
        "Lihat Tabel~\\ref{tab:a} dan Gambar~\\ref{fig:a}.\n"
        "\\begin{figure}\\includegraphics{y}\\caption{G}\\label{fig:b}\\end{figure}\n"
    )
    summary, issues = check_floats("Gambar~\\ref{fig:b} di bawah.\n" + text)
    messages = [message for _, message, _ in issues]
    assert "tab:a: caption is below the table" in messages
    assert "fig:a: caption is above the figure" in messages
    assert summary["referenced_after"] == ["tab:a", "fig:a"]
    assert summary["numbered_through"] == ["figure"]


def test_citation_style_against_the_guide():
    assert style_family("APA (rujuk www.apa.org); gaya author-year") == "author-year"
    assert style_family("IEEE numeric") == "numeric"
    numeric_bib = "\\bibliographystyle{IEEEtran}\n\\begin{document}Teks \\cite{a}.\\end{document}"
    _, issues = check_citation_style(numeric_bib, expected="APA author-year")
    assert issues and "is numeric; the guide asks for author-year" in issues[0][1]
    mixed = ("\\begin{document}Menurut [1] dan [2, 3], sedangkan (Smith, 2020) serta "
             "Wang et al. (2021) berbeda.\\end{document}")
    summary, issues = check_citation_style(mixed)
    assert summary["typed_numeric"] == 2 and summary["typed_author_year"] == 2
    assert "mix numeric" in issues[0][1]
    clean = "\\bibliographystyle{apalike}\n\\begin{document}Teks \\cite{a}.\\end{document}"
    assert check_citation_style(clean, expected="APA")[1] == []


def test_reference_minimum_from_the_policy():
    entries = [SimpleNamespace(key=f"k{i}", entry_type="article", fields={"year": "2024"})
               for i in range(10)]
    policy = ReferencePolicy.from_payload({"min_entries": 40, "reference_year": 2026})
    dimension = _dimension_references(audit_references(entries, policy=policy))
    assert any("at least 40" in finding.message for finding in dimension.findings)
    assert dimension.score < 1.0
    relaxed = _dimension_references(audit_references(entries, policy=ReferencePolicy(reference_year=2026)))
    assert relaxed.score == 1.0


def test_design_science_outranks_the_technique_it_builds_with():
    text = (
        "Penelitian ini memakai design science research (DSRM, Peffers) untuk membangun "
        "harness verifikasi berbasis large language model. LLM dipakai sebagai komponen; "
        "fine-tuning LLM tidak dilakukan. Machine learning dan LLM lain dibandingkan."
    )
    assert detect_research_design(text, family="empirical") == "design_science"
    once = "Kami melatih LLM dengan fine-tuning; deep learning, mengikuti Hevner."
    assert detect_research_design(once, family="empirical") == "ml_experiment"


def test_detection_reads_a_late_method_chapter():
    text = (
        "\\chapter{Pendahuluan}\n" + "Latar belakang pengodean klinis. " * 800
        + "\\chapter{Metodologi Penelitian}\nPenelitian ini mengikuti design science "
        "research methodology (DSRM) dari Peffers.\n\\chapter{Hasil}\nHasil.\n"
    )
    assert "design science" in detection_text(text)
    assert detect_research_design(text, family="empirical") == "design_science"
