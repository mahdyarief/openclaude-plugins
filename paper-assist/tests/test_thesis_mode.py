"""Thesis mode across Research OS: detection, front matter, Chapter 1,
alignment, layout, scoring and the MCP tools."""

from __future__ import annotations

import json

import pytest

from paperassist.manuscript_quality import score_manuscript
from paperassist.thesis_checks import (
    check_layout,
    check_thesis,
    required_front_matter,
    resolve_document_kind,
)
from paperassist.thesis_profiles import thesis_profile
from paperassist.writing_skeletons import skeleton_document_kind

PROSE = (
    "Penelitian ini menguji model pembelajaran mesin untuk deteksi fraud klaim "
    "asuransi kesehatan pada data klaim rumah sakit. Hasil pengujian menunjukkan "
    "bahwa model gradient boosting mencapai F1 0,81 pada data uji, lebih tinggi "
    "dari regresi logistik (Wang et al. 2025). "
)


def _thesis(*, questions: int = 3, objectives: int = 3, conclusions: int = 3,
            front: bool = True, limitations: bool = True, preamble: str | None = None) -> str:
    items = lambda n, word: "\\begin{enumerate}\n" + "".join(  # noqa: E731
        f"\\item {word} ke-{i + 1} tentang deteksi fraud klaim?\n" for i in range(n)
    ) + "\\end{enumerate}\n"
    front_pages = (
        "\\chapter*{Lembar Pengesahan}\nDisetujui oleh pembimbing.\n"
        "\\chapter*{Pernyataan Keaslian}\nSaya menyatakan tesis ini asli.\n"
        "\\chapter*{Kata Pengantar}\nPuji syukur.\n"
    ) if front else ""
    closing_limits = (
        "Keterbatasan penelitian ini adalah data yang terbatas pada satu rumah sakit. "
        if limitations else ""
    )
    head = preamble or (
        "\\documentclass[12pt,a4paper]{report}\n"
        "\\usepackage[indonesian]{babel}\n"
        "\\usepackage[a4paper,left=4cm,top=3cm,right=2.5cm,bottom=2.5cm]{geometry}\n"
        "\\usepackage{setspace}\n\\onehalfspacing\n"
    )
    return (
        head
        + "\\begin{document}\n\\begin{titlepage}\nTESIS\n\\maketitle\n\\end{titlepage}\n"
        + front_pages
        + "\\chapter*{Abstrak}\n" + "Tujuan penelitian ini adalah mendeteksi fraud klaim. "
        "Metode eksperimen dengan data klaim 2020-2024 dari basis data rumah sakit. Hasil "
        "menunjukkan F1 0,81. Kesimpulan: model layak dipakai. " * 4
        + "\n\nKata kunci: fraud, klaim, pembelajaran mesin\n"
        + "\n\\chapter*{Abstract}\nThis study detects claim fraud. The method is an "
        "experiment on claims from 2020-2024; results show F1 0.81.\n\n"
        "Keywords: fraud, claims, machine learning\n"
        "\\tableofcontents\n\\listoftables\n\\listoffigures\n"
        "\\chapter{Pendahuluan}\\label{ch:pendahuluan}\n"
        "\\section{Latar Belakang}\n" + PROSE * 6
        + "\\section{Rumusan Masalah}\n" + items(questions, "Bagaimana pertanyaan")
        + "\\section{Tujuan Penelitian}\n" + items(objectives, "Tujuan")
        + "\\section{Manfaat Penelitian}\n" + PROSE
        + "\\section{Batasan Masalah}\nPenelitian dibatasi pada klaim rawat inap.\n"
        + "\\section{Sistematika Penulisan}\nBab II membahas tinjauan pustaka.\n"
        "\\chapter{Tinjauan Pustaka}\\label{ch:tinjauan}\n" + PROSE * 10
        + "\\chapter{Metodologi Penelitian}\\label{ch:metodologi}\n" + PROSE * 10
        + "\\chapter{Hasil dan Pembahasan}\\label{ch:hasil}\n" + PROSE * 10
        + "\\chapter{Kesimpulan dan Saran}\\label{ch:kesimpulan}\n"
        "\\section{Kesimpulan}\n" + items(conclusions, "Kesimpulan")
        + "\\section{Saran}\n" + closing_limits + "Penelitian lanjutan perlu data lebih luas.\n"
        "\\bibliographystyle{apalike}\n\\bibliography{references}\n\\end{document}\n"
    )


ARTICLE = (
    "\\documentclass{article}\n\\begin{document}\n\\begin{abstract}A study.\\end{abstract}\n"
    "\\section{Introduction}Text.\\section{Method}Text.\\end{document}\n"
)


def test_document_kind_is_detected():
    assert resolve_document_kind("auto", _thesis()) == "thesis"
    assert resolve_document_kind("auto", ARTICLE) == "article"
    assert resolve_document_kind("skripsi", ARTICLE) == "thesis"
    assert resolve_document_kind("paper", _thesis()) == "article"
    with pytest.raises(ValueError):
        resolve_document_kind("poster", ARTICLE)


def test_complete_thesis_passes_every_check():
    check = check_thesis(_thesis(), profile="id-thesis-generic")
    assert check.front_matter_missing == ()
    assert all(check.chapter_one[name] for name in ("background", "problem_statement",
                                                     "objectives", "scope", "outline"))
    assert (check.research_questions, check.objectives, check.conclusion_points) == (3, 3, 3)
    assert check.layout == ()
    assert [i for i in check.issues if i.check != "length"] == []


def test_missing_front_matter_and_misaligned_questions_are_named():
    check = check_thesis(_thesis(front=False, objectives=2, conclusions=1),
                         profile="id-thesis-generic")
    assert set(check.front_matter_missing) == {"approval_page", "originality_statement",
                                               "preface"}
    messages = " ".join(issue.message for issue in check.issues)
    assert "3 research questions but 2 objectives" in messages
    assert "answers 1 points for 3 research questions" in messages


def test_layout_is_compared_with_the_profile():
    plain = "\\documentclass{report}\n\\begin{document}\n\\end{document}\n"
    issues = {item["item"] for item in check_layout(plain, thesis_profile("id-thesis-generic"))}
    assert {"font size", "paper size", "line spacing", "left margin"} <= issues
    spread = (
        "\\documentclass[12pt,a4paper]{report}\n\\linespread{1.3}\n"
        "\\usepackage[left=40mm,right=2.5cm,top=3cm,bottom=2.5cm]{geometry}\n\\begin{document}"
    )
    assert check_layout(spread, thesis_profile("id-thesis-generic")) == []


def test_profile_front_matter_maps_to_items():
    telkom = required_front_matter(thesis_profile("id-telkom-tesis"), indonesian=True)
    assert {"title_page", "approval_page", "originality_statement", "preface",
            "abstract", "abstract_english", "table_of_contents"} <= set(telkom)


def test_thesis_score_uses_thesis_rules():
    report = score_manuscript(_thesis(front=False, objectives=2),
                              thesis_profile="id-thesis-generic")
    assert report.document_kind == "thesis"
    assert report.to_dict()["document_kind"] == "thesis"
    structure = report.dimension("structure")
    assert "method" in structure.measurements["present_sections"]
    assert structure.measurements["thesis"]["alignment"]["objectives"] == 2
    declarations = report.dimension("declarations")
    messages = [f.message for f in declarations.findings]
    assert any("approval page" in m for m in messages)
    assert not any("competing interests" in m or "funding" in m for m in messages)
    assert report.dimension("abstract").measurements["words"] > 50
    assert report.dimension("depth").measurements["depth_target"] == 1500
    assert report.dimension("limitations").measurements["section_present"] is True
    labels = [f.message for f in report.dimension("tables_figures").findings]
    assert not any("ch:" in m for m in labels)
    complete = score_manuscript(_thesis(), thesis_profile="id-thesis-generic")
    assert complete.dimension("declarations").score == 1.0
    assert complete.dimension("structure").score > structure.score


def test_article_mode_is_unchanged_for_articles():
    report = score_manuscript(ARTICLE)
    assert report.document_kind == "article"
    assert "thesis" not in report.dimension("structure").measurements
    forced = score_manuscript(_thesis(), document_kind="article")
    assert any("competing interests" in f.message
               for f in forced.dimension("declarations").findings)


def test_thesis_skeleton_carries_front_matter_and_outlines():
    skeleton = skeleton_document_kind("Judul", document_kind="thesis")
    for page in ("Lembar Pengesahan", "Pernyataan Keaslian", "Kata Pengantar", "Abstract"):
        assert f"\\chapter*{{{page}}}" in skeleton
    assert "%   - Rumusan Masalah" in skeleton and "%   - Keterbatasan Penelitian" in skeleton
    check = check_thesis(skeleton, profile="id-thesis-generic")
    assert {"approval_page", "originality_statement", "abstract_english"} <= set(
        check.front_matter_present
    )
    telkom = skeleton_document_kind("Judul", document_kind="thesis",
                                    thesis_profile_id="id-telkom-tesis")
    assert "left=4cm" in telkom and "\\onehalfspacing" in telkom
    assert check_layout(telkom, thesis_profile("id-telkom-tesis")) == []


def test_research_os_reports_thesis_checks(tmp_path):
    from paperassist.research_os import run_research_os

    (tmp_path / "main.tex").write_text(_thesis(conclusions=2), encoding="utf-8")
    result = run_research_os(
        tmp_path,
        {"run_id": "t", "target_path": "main.tex", "thesis_profile": "id-thesis-generic"},
    )
    checks = json.loads((tmp_path / result.artifacts["reporting_checks"]).read_text("utf-8"))
    assert checks["document_kind"] == "thesis"
    assert checks["thesis"]["alignment"]["conclusion_points"] == 2
    assert checks["thesis"]["front_matter"]["missing"] == []
    article = run_research_os(
        tmp_path, {"run_id": "a", "target_path": "main.tex", "document_kind": "article"}
    )
    checks = json.loads((tmp_path / article.artifacts["reporting_checks"]).read_text("utf-8"))
    assert checks["document_kind"] == "article" and checks["thesis"] is None


def test_mcp_quality_score_accepts_thesis_arguments(tmp_path):
    from mcp_servers.paperassist.server import PaperAssistMcpServer

    (tmp_path / "main.tex").write_text(_thesis(front=False), encoding="utf-8")
    out = PaperAssistMcpServer().quality_score(
        workspace=str(tmp_path), target_path="main.tex", thesis_profile="id-thesis-generic"
    )
    assert out["document_kind"] == "thesis"
    assert "**Document:** thesis" in out["markdown"]
    server = PaperAssistMcpServer()
    research = server.research_os(
        workspace=str(tmp_path), run_id="m", target_path="main.tex",
        document_kind="thesis", required_front_matter=["approval_page"],
    )
    assert research["status"] == "ok"


def _proposal() -> str:
    """Chapters 1-3 of the thesis fixture, as submitted for seminar proposal."""

    full = _thesis(front=False)
    cut = full.index("\\chapter{Hasil dan Pembahasan}")
    start = full.index("\\chapter*{Abstrak}")
    toc = full.index("\\tableofcontents")
    # No abstract: proposals are usually submitted without one.
    body = full[:start] + "\\chapter*{Lembar Persetujuan}\nDisetujui.\n" + full[toc:cut]
    return body + "\\bibliography{references}\n\\end{document}\n"


def test_stage_is_detected_and_proposal_needs_less_front_matter():
    from paperassist.thesis_checks import resolve_thesis_stage

    assert resolve_thesis_stage("auto", _proposal()) == "proposal"
    assert resolve_thesis_stage("auto", _thesis()) == "final"
    assert resolve_thesis_stage("seminar hasil", _proposal()) == "final"
    check = check_thesis(_proposal(), profile="id-thesis-generic")
    assert check.stage == "proposal"
    assert check.front_matter_required == ("title_page", "approval_page", "table_of_contents")
    assert check.front_matter_missing == ()
    with pytest.raises(ValueError):
        resolve_thesis_stage("draft-ish", _proposal())


def test_proposal_is_not_penalised_for_results_it_cannot_have():
    proposal = score_manuscript(_proposal(), thesis_profile="id-thesis-generic")
    structure = proposal.dimension("structure")
    assert structure.measurements["required_sections"] == ["introduction", "related", "method"]
    assert not any("missing required section" in f.message for f in structure.findings)
    assert proposal.dimension("abstract").score == 1.0
    assert proposal.dimension("limitations").score == 1.0
    assert proposal.dimension("method_rigour").measurements.get("planned") is True
    as_final = score_manuscript(_proposal(), thesis_profile="id-thesis-generic",
                                thesis_stage="final")
    assert as_final.score < proposal.score


def test_proposal_writing_pack_has_three_chapters():
    from paperassist.writing_tasks import build_tasks

    skeleton = skeleton_document_kind("Judul", document_kind="thesis", thesis_stage="proposal")
    assert "\\chapter{Metodologi Penelitian}" in skeleton
    assert "\\chapter{Hasil dan Pembahasan}" not in skeleton
    assert "\\chapter*{Lembar Persetujuan}" in skeleton
    assert "Jadwal Penelitian" in skeleton
    assert check_thesis(skeleton).stage == "proposal"
    tasks = build_tasks({"document_kind": "thesis", "thesis_stage": "proposal",
                         "phases": ["init", "refine"]}, target="main.tex",
                        allowed_keys=["wang2025"], reference_count=1)
    ids = {task.task_id for task in tasks}
    assert "refine-metodologi-penelitian" in ids
    assert not any("hasil" in task_id for task_id in ids)
