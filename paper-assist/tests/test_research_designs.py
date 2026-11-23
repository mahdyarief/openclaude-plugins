from __future__ import annotations

import json
import re

import pytest

from paperassist.manuscript_quality import score_manuscript
from paperassist.reporting_checks import resolve_paper_type, resolve_research_design
from paperassist.research_designs import (
    DESIGN_FAMILIES,
    DESIGNS,
    RESEARCH_DESIGNS,
    STATISTICS_SIGNALS,
    design_catalogue,
    design_method_brief,
    detect_research_design,
    get_design,
)


def test_registry_is_well_formed():
    assert len(DESIGNS) >= 20
    for design in DESIGNS.values():
        assert design.family in DESIGN_FAMILIES
        assert design.guideline and design.reference
        assert design.method_signals, design.key
        if design.parent is not None:
            assert design.parent in DESIGNS
            assert DESIGNS[design.parent].family == design.family
        for _, pattern in (
            *design.method_signals,
            *design.repro_signals,
            *design.results_signals,
        ):
            re.compile(pattern)
        if design.detect:
            re.compile(design.detect)


def test_aliases_resolve_case_and_separator_insensitively():
    assert get_design("PTK").key == "classroom_action_research"
    assert get_design("penelitian tindakan kelas").key == "classroom_action_research"
    assert get_design("R&D").key == "research_development"
    assert get_design("Scoping-Review").key == "scoping_review"
    assert get_design("review").key == "systematic_review"
    assert get_design("experimental").key == "empirical"
    with pytest.raises(ValueError, match="unknown research_design"):
        get_design("horoscope")


@pytest.mark.parametrize(
    ("text", "family", "expected"),
    [
        ("A systematic review and meta-analysis following PRISMA; the meta-analysis pooled 12 trials.", "review", "meta_analysis"),
        ("An SLR following PRISMA (Preferred Reporting Items for Systematic Reviews and Meta-Analyses).", "review", "systematic_review"),
        ("Penelitian dan pengembangan model ADDIE; angket validasi ahli dan angket respon siswa (kuesioner).", "empirical", "research_development"),
        ("Survei daring dengan kuesioner Likert kepada 300 responden.", "empirical", "survey"),
        ("We conducted a scoping review using the Arksey and O'Malley framework.", "review", "scoping_review"),
        ("Analisis bibliometrik dengan VOSviewer atas data Scopus.", "review", "bibliometric"),
        ("Only inclusion criteria were applied.", "review", "systematic_review"),
        ("A randomised controlled trial reported per CONSORT.", "empirical", "rct"),
        ("Desain kuasi eksperimen dengan nonequivalent control group.", "empirical", "quasi_experiment"),
        ("A cross-sectional study of 400 adults (STROBE).", "empirical", "observational"),
        ("Data dikumpulkan melalui kuesioner; survei daring dengan angket Likert.", "empirical", "survey"),
        ("Penelitian kualitatif dengan wawancara mendalam dan analisis tematik.", "empirical", "qualitative"),
        ("An explanatory sequential mixed methods design.", "empirical", "mixed_methods"),
        ("Following the design science research methodology (DSRM) of Peffers.", "empirical", "design_science"),
        ("Penelitian pengembangan dengan model ADDIE.", "empirical", "research_development"),
        ("Penelitian tindakan kelas ini dilaksanakan dalam dua siklus.", "empirical", "classroom_action_research"),
        ("We fine-tune BERT and compare it with a random forest baseline.", "empirical", "ml_experiment"),
        ("We study the effect of X on Y.", "empirical", "empirical"),
    ],
)
def test_detection_picks_the_most_specific_design(text, family, expected):
    assert detect_research_design(text, family=family) == expected


def test_one_survey_word_is_not_a_survey_design():
    assert detect_research_design("A questionnaire was also collected.", family="empirical") == "empirical"


def test_review_about_machine_learning_stays_a_review():
    text = (
        "This systematic review of deep learning and machine learning studies follows "
        "PRISMA; inclusion criteria were applied to neural network papers."
    )
    design = resolve_research_design("auto", text)
    assert design.family == "review" and design.key == "systematic_review"


def test_paper_type_accepts_a_design_key():
    assert resolve_paper_type("ptk", "x") == "empirical"
    assert resolve_paper_type("scoping_review", "x") == "review"
    assert resolve_research_design(None, "x", paper_type="rct").key == "rct"
    assert resolve_research_design("qualitative", "a systematic review").key == "qualitative"
    with pytest.raises(ValueError):
        resolve_paper_type("horoscope", "x")


def test_catalogue_and_brief_are_serialisable():
    catalogue = design_catalogue()
    assert [item["key"] for item in catalogue] == list(RESEARCH_DESIGNS)
    json.dumps(catalogue)
    brief = design_method_brief(DESIGNS["rct"])
    assert "CONSORT 2025" in brief and "allocation concealment" in brief


QUALITATIVE = r"""\documentclass{article}
\begin{document}
\begin{abstract}
This qualitative study explores how teachers adopt learning platforms. Themes
show that peer support drives adoption, and we conclude with design implications.
\end{abstract}
\section{Introduction}
Context and contribution.
\section{Metode Penelitian}
We used a phenomenological approach. The first author's role as a former teacher
is stated for reflexivity. The setting was three public schools. Twelve teachers
were chosen by purposive sampling until data saturation. Semi-structured
interviews were recorded and transcribed verbatim, then coded with thematic
analysis following Braun and Clarke in NVivo. Trustworthiness was supported by
member checking and triangulation. Ethics approval and informed consent were
obtained; the interview guide is in the appendix.
\section{Results}
Three themes emerged. Theme 1, peer support: ``I only tried it after a colleague
showed me'' (P3). Theme 2 concerns time, as \cite{a} also reported.
\section{Discussion}
Meaning.
\section{Limitations}
Twelve teachers in one district limit transferability of these findings.
\section{Conclusion}
End.
\end{document}
"""


def test_qualitative_study_is_not_asked_for_statistics():
    report = score_manuscript(QUALITATIVE)
    assert report.research_design == "qualitative"
    method = report.dimension("method_rigour")
    assert method.measurements["guideline"].startswith("SRQR")
    assert method.measurements["missing"] == []
    assert set(method.measurements["results_items"]) == {
        "themes or categories",
        "participant quotations",
        "links to prior work",
    }
    assert "statistics" not in method.measurements
    assert not any("results do not report" in f.message for f in method.findings)
    general = score_manuscript(QUALITATIVE, research_design="empirical").dimension("method_rigour")
    assert method.score > general.score


def test_explicit_design_reports_its_own_missing_items():
    report = score_manuscript(QUALITATIVE, research_design="rct")
    method = report.dimension("method_rigour")
    assert report.research_design == "rct" and report.paper_type == "empirical"
    assert "allocation concealment" in method.measurements["missing"]
    assert any("CONSORT 2025" in f.remedy for f in method.findings)


PTK = r"""\documentclass{article}
\begin{document}
\begin{abstract}
Penelitian tindakan kelas ini bertujuan meningkatkan hasil belajar siswa kelas V.
Hasil menunjukkan ketuntasan meningkat dan disimpulkan model efektif.
\end{abstract}
\section{Pendahuluan}
Latar belakang.
\section{Metode Penelitian}
Subjek penelitian adalah 28 siswa kelas V. Penelitian menggunakan model siklus
Kemmis dan McTaggart yang terdiri atas perencanaan, pelaksanaan tindakan,
observasi, dan refleksi. Indikator keberhasilan adalah ketuntasan klasikal 80\%.
Data dikumpulkan dengan tes dan lembar observasi, lalu dianalisis secara deskriptif.
\section{Hasil dan Pembahasan}
Pada pra-siklus ketuntasan 40\%. Pada siklus I ketuntasan 65\%, dan pada siklus II
ketuntasan 85\% sehingga indikator tercapai. Refleksi siklus I menunjukkan kendala waktu.
\section{Kesimpulan}
Model efektif.
\end{document}
"""


def test_classroom_action_research_is_judged_on_its_cycle():
    report = score_manuscript(PTK)
    method = report.dimension("method_rigour")
    assert report.research_design == "classroom_action_research"
    assert method.measurements["missing"] == []
    assert set(method.measurements["results_items"]) == {
        "per-cycle comparison",
        "indicator attainment",
        "reflection outcomes",
    }


def test_prisma_flow_applies_to_scoping_reviews_but_not_bibliometrics():
    assert DESIGNS["scoping_review"].flow == "prisma"
    assert DESIGNS["meta_analysis"].flow == "prisma"
    assert DESIGNS["bibliometric"].flow is None
    assert DESIGNS["empirical"].results_signals == STATISTICS_SIGNALS


def test_research_os_records_the_design(tmp_path):
    from paperassist.research_os import run_research_os

    (tmp_path / "main.tex").write_text(PTK, encoding="utf-8")
    result = run_research_os(tmp_path, {"run_id": "r", "target_path": "main.tex"})
    assert result.quality.research_design == "classroom_action_research"
    checks = json.loads((tmp_path / result.artifacts["reporting_checks"]).read_text("utf-8"))
    assert checks["research_design"]["key"] == "classroom_action_research"
    assert checks["prisma_flow"] is None
    forced = run_research_os(
        tmp_path, {"run_id": "r2", "target_path": "main.tex", "research_design": "scoping"}
    )
    assert forced.quality.paper_type == "review"


def test_design_lookup_tool(tmp_path):
    from mcp_servers.paperassist.server import PaperAssistMcpServer

    server = PaperAssistMcpServer()
    listing = server.design_lookup()
    assert listing["result"]["count"] == len(DESIGNS)
    qualitative = server.design_lookup(category="qualitative")["result"]["designs"]
    assert {item["key"] for item in qualitative} == {"qualitative", "case_study"}
    assert server.design_lookup(query="ptk")["result"]["design"]["key"] == (
        "classroom_action_research"
    )
    (tmp_path / "main.tex").write_text(QUALITATIVE, encoding="utf-8")
    detected = server.design_lookup(manuscript_path="main.tex", workspace=str(tmp_path))
    assert detected["result"]["detected"]["key"] == "qualitative"
    assert "SRQR" in detected["markdown"]


def test_writing_pack_method_brief_follows_the_design(tmp_path):
    from paperassist.writing_pack import WritingPackError, build_writing_pack
    from tests.test_writing_pack_depth import MAIN_TEX, make_workspace

    make_workspace(tmp_path)
    pack = build_writing_pack(
        tmp_path,
        run_id="d",
        payload={"research_design": "survey"},
        target_path="main.tex",
        original_text=MAIN_TEX,
    )
    method = next(task for task in pack.tasks if task.task_id == "section-method")
    assert "CROSS" in method.instructions and "response rate" in method.instructions
    intro = next(task for task in pack.tasks if task.task_id == "section-introduction")
    assert "CROSS" not in intro.instructions
    with pytest.raises(WritingPackError):
        build_writing_pack(
            tmp_path,
            run_id="e",
            payload={"research_design": "horoscope"},
            target_path="main.tex",
            original_text=MAIN_TEX,
        )
