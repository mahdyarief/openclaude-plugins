"""Participant flow, analysis checks, detection explanations and Method outlines."""

from __future__ import annotations

import json

import pytest

from paperassist.analysis_checks import check_analyses, ngain_category
from paperassist.manuscript_quality import score_manuscript
from paperassist.participant_flow import check_participant_flow
from paperassist.research_designs import DESIGNS, design_method_brief, explain_detection
from paperassist.writing_skeletons import skeleton_document_kind

CONSORT_OK = {
    "assessed_for_eligibility": 120,
    "excluded": 20,
    "excluded_reasons": {"not meeting criteria": 12, "declined": 8},
    "randomised": 100,
    "arms": {
        "intervention": {"allocated": 50, "received": 48, "not_received": 2,
                         "lost_to_follow_up": 3, "analysed": 47, "excluded_from_analysis": 3},
        "control": {"allocated": 50, "received": 50, "not_received": 0,
                    "lost_to_follow_up": 1, "analysed": 49, "excluded_from_analysis": 1},
    },
}


def _failed(flow):
    return {identity.name for identity in flow.identities if not identity.passed}


def test_consort_flow_that_adds_up_passes():
    flow = check_participant_flow([CONSORT_OK])
    assert flow.kind == "consort" and flow.available and flow.passed
    names = {identity.name for identity in flow.identities}
    assert {"enrolment", "excluded_breakdown", "allocation", "intervention.intervention",
            "intervention.analysis", "control.follow_up"} <= names
    assert flow.unchecked == ()


def test_consort_flow_errors_are_named():
    broken = json.loads(json.dumps(CONSORT_OK))
    broken["randomised"] = 98
    broken["arms"]["control"]["analysed"] = 52
    del broken["arms"]["control"]["excluded_from_analysis"]
    flow = check_participant_flow([broken])
    assert _failed(flow) == {"enrolment", "allocation", "control.analysis"}
    analysis = next(i for i in flow.identities if i.name == "control.analysis")
    assert analysis.relation == "<=" and "exceeds" in analysis.describe()


def test_consort_arms_as_list_and_indonesian_keys():
    flow = check_participant_flow([{
        "dinilai_kelayakan": 70, "dieksklusi": 10, "dirandomisasi": 60,
        "kelompok": [{"name": "eksperimen", "dialokasikan": 30, "dianalisis": 30},
                     {"name": "kontrol", "dialokasikan": 30, "dianalisis": 29}],
    }])
    assert flow.passed and "eksperimen.analysis" in {i.name for i in flow.identities}


def test_quasi_experiment_allocation_without_randomisation():
    flow = check_participant_flow(
        [{"assessed": 64, "excluded": 0, "arms": {"eksperimen": {"allocated": 32},
                                                   "kontrol": {"allocated": 30}}}],
        randomised=False,
    )
    assert _failed(flow) == {"allocation"}


def test_strobe_stages_cannot_grow():
    flow = check_participant_flow(
        [{"examined": 500, "eligible": 420, "declined": 20, "included": 400, "analysed": 410}],
        kind="strobe",
    )
    assert flow.kind == "strobe"
    assert _failed(flow) == {"analysed_within_included"}
    assert "participation" in {i.name for i in flow.identities}
    with pytest.raises(ValueError):
        check_participant_flow([{}], kind="prisma")


RCT = r"""\documentclass{article}
\begin{document}
\begin{abstract}
A randomised controlled trial of a reading programme; scores improved and we conclude it works.
\end{abstract}
\section{Introduction}
Context.
\section{Method}
This parallel randomised controlled trial (allocation ratio 1:1) enrolled pupils meeting the
inclusion criteria. The intervention was a reading programme; the primary outcome was a reading
score. A power analysis set the sample size. Computer-generated randomisation with sealed opaque
envelopes ensured allocation concealment; assessors were blinded. Analysis was intention-to-treat
with an independent samples t-test after Shapiro-Wilk and Levene tests.
\section{Results}
Of 120 pupils assessed, 100 were randomised and allocated; 96 were analysed. Baseline
characteristics were similar. The difference was 4.1 points (95\% CI 1.2 to 7.0, p = 0.01,
d = 0.5). No adverse events occurred.
\section{Discussion}
Meaning.
\section{Limitations}
One school district.
\section{Conclusion}
End.
\end{document}
"""


def test_rct_method_dimension_checks_the_participant_flow():
    broken = json.loads(json.dumps(CONSORT_OK))
    broken["randomised"] = 98
    flow = check_participant_flow([broken])
    report = score_manuscript(RCT, participant_flow=flow)
    method = report.dimension("method_rigour")
    assert report.research_design == "rct"
    assert method.measurements["participant_flow"]["kind"] == "consort"
    assert any("CONSORT 2025 flow does not add up at enrolment" in f.message for f in method.findings)
    good = score_manuscript(RCT, participant_flow=check_participant_flow([CONSORT_OK]))
    assert good.dimension("method_rigour").score > method.score
    unsupplied = score_manuscript(RCT).dimension("method_rigour")
    assert any("no CONSORT 2025 flow counts" in f.message for f in unsupplied.findings)
    # The prerequisite tests are reported, so no analysis warning appears.
    assert method.measurements["analysis_checks"]["issues"] == []


def test_research_os_reads_participant_flow(tmp_path):
    from paperassist.research_os import run_research_os

    (tmp_path / "main.tex").write_text(RCT, encoding="utf-8")
    (tmp_path / "flow.json").write_text(json.dumps(CONSORT_OK), encoding="utf-8")
    result = run_research_os(
        tmp_path, {"run_id": "r", "target_path": "main.tex", "participant_flow": "flow.json"}
    )
    checks = json.loads((tmp_path / result.artifacts["reporting_checks"]).read_text("utf-8"))
    assert checks["participant_flow"]["passed"] is True
    assert checks["prisma_flow"] is None
    assert checks["design_detection"]["chosen"] == "rct"
    # A flow document with arms as a list loads as counts, not as study records.
    listed = dict(CONSORT_OK, arms=[dict(v, name=k) for k, v in CONSORT_OK["arms"].items()])
    (tmp_path / "counts.json").write_text(json.dumps(listed), encoding="utf-8")
    again = run_research_os(
        tmp_path, {"run_id": "r2", "target_path": "main.tex", "records_paths": ["counts.json"]}
    )
    checks = json.loads((tmp_path / again.artifacts["reporting_checks"]).read_text("utf-8"))
    assert checks["participant_flow"]["passed"] is True


def test_quality_score_tool_accepts_a_flow_file(tmp_path):
    from mcp_servers.paperassist.server import PaperAssistMcpServer

    (tmp_path / "main.tex").write_text(RCT, encoding="utf-8")
    broken = dict(CONSORT_OK, randomised=90)
    (tmp_path / "flow.json").write_text(json.dumps(broken), encoding="utf-8")
    out = PaperAssistMcpServer().quality_score(
        workspace=str(tmp_path), target_path="main.tex", flow_path="flow.json"
    )
    method = next(d for d in out["report"]["dimensions"] if d["name"] == "method_rigour")
    assert method["measurements"]["participant_flow"]["passed"] is False


@pytest.mark.parametrize(
    ("g", "category"), [(0.71, "high"), (0.7, "medium"), (0.3, "medium"), (0.29, "low")]
)
def test_ngain_category_follows_hake(g, category):
    assert ngain_category(g) == category


def test_ngain_mislabelled_category_is_flagged():
    check = check_analyses(
        "Nilai N-gain kelas eksperimen 0,62 dengan kategori tinggi, sedangkan "
        "kelas kontrol 0,25 (rendah). N-gain dalam persen 75% tergolong tinggi."
    )
    values = check.measurements["n_gain_values"]
    assert [item["value"] for item in values] == [0.62, 0.25, 0.75]
    messages = [issue.message for issue in check.issues]
    assert len(messages) == 1 and "0,62" in messages[0] and "medium" in messages[0]


def test_aiken_without_raters_or_categories_is_flagged():
    vague = check_analyses("Validitas isi dihitung dengan Aiken's V = 0,86.")
    assert any("number of raters" in issue.message for issue in vague.issues)
    stated = check_analyses(
        "Tiga validator menilai setiap butir pada skala Likert 1-5; Aiken's V = 0,86."
    )
    assert stated.issues == ()
    impossible = check_analyses("Tiga validator, skala 5 kategori; Aiken's V sebesar 1,2.")
    assert any("outside 0-1" in issue.message for issue in impossible.issues)


def test_aiken_curly_apostrophe_and_ranges_from_real_articles():
    # Wording taken from published Indonesian R&D articles used for calibration.
    check = check_analyses(
        "Tiga ahli pendidikan matematika menilai pada skala Likert lima kategori. "
        "Hasil analisis menunjukkan bahwa nilai indeks Aiken’s V berkisar antara 0,64 hingga 0,73."
    )
    assert check.measurements["aiken_values"] == [0.64, 0.73]
    assert check.issues == ()


def test_parametric_test_without_prerequisites_is_flagged():
    check = check_analyses(
        "Perbedaan kelas eksperimen dan kelas kontrol diuji dengan uji-t independen."
    )
    messages = " ".join(issue.message for issue in check.issues)
    assert "normality" in messages and "homogeneity" in messages
    paired = check_analyses("A paired samples t-test after a Shapiro-Wilk test.")
    assert paired.issues == ()
    assert check_analyses("Interviews were coded thematically.").applied == ()


def test_qualitative_designs_are_not_given_analysis_checks():
    from tests.test_research_designs import QUALITATIVE

    text = QUALITATIVE.replace("Three themes emerged.", "Three themes emerged; a t-test was not used.")
    method = score_manuscript(text).dimension("method_rigour")
    assert "analysis_checks" not in method.measurements


def test_detection_explains_its_choice():
    strong = explain_detection(
        "Penelitian tindakan kelas ini ... siklus. PTK dilaksanakan dua siklus.", family="empirical"
    )
    assert strong["chosen"] == "classroom_action_research"
    assert strong["confidence"] == "high"
    assert strong["candidates"][0]["key"] == "classroom_action_research"
    assert "penelitian tindakan kelas" in strong["candidates"][0]["matched"]
    weak = explain_detection("We study the effect of X on Y.", family="empirical")
    assert weak["chosen"] == "empirical" and weak["confidence"] == "low"
    below = explain_detection("A questionnaire was also collected.", family="empirical")
    survey = next(item for item in below["candidates"] if item["key"] == "survey")
    assert survey["counted"] is False and survey["min_hits"] == 2


def test_design_lookup_reports_confidence(tmp_path):
    from mcp_servers.paperassist.server import PaperAssistMcpServer

    (tmp_path / "main.tex").write_text(RCT, encoding="utf-8")
    out = PaperAssistMcpServer().design_lookup(manuscript_path="main.tex", workspace=str(tmp_path))
    assert out["result"]["detected"]["key"] == "rct"
    assert out["result"]["confidence"] in ("medium", "high")
    assert "**Detected:** `rct`" in out["markdown"]


def test_every_design_has_a_method_outline_in_brief_and_skeleton():
    for design in DESIGNS.values():
        assert design.method_outline, design.key
        assert "Suggested Method subsections" in design_method_brief(design)
    paper = skeleton_document_kind("T", research_design="rct")
    assert "% Suggested subsections (CONSORT 2025" in paper
    assert "%   - Randomisation and allocation concealment" in paper
    thesis = skeleton_document_kind("T", document_kind="thesis", research_design="ptk")
    method_chapter = thesis.split("\\chapter{Metodologi Penelitian}")[1].split("\\chapter")[0]
    assert "%   - Success indicators" in method_chapter
    assert skeleton_document_kind("T") == skeleton_document_kind("T", research_design="auto")


def test_verified_item_counts_are_in_the_guidelines():
    assert DESIGNS["diagnostic_accuracy"].guideline.startswith("STARD 2015 (30 items")
    assert DESIGNS["prediction_model"].guideline == "TRIPOD+AI (27 items)"
    assert DESIGNS["quasi_experiment"].guideline == "TREND statement (22 items)"
    assert DESIGNS["rct"].flow == DESIGNS["quasi_experiment"].flow == "consort"
    assert DESIGNS["observational"].flow == "strobe"
