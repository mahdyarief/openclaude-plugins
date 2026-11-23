"""Regression cases from calibrating design detection on real papers.

Each text paraphrases the wording that misled detection in a published paper;
none is copied from one.
"""

from __future__ import annotations

import pytest

from paperassist.analysis_checks import check_analyses
from paperassist.reporting_checks import resolve_research_design
from paperassist.research_designs import detection_text, explain_detection


def _design(text: str) -> str:
    return resolve_research_design("auto", text).key


@pytest.mark.parametrize(
    "text",
    [
        "Retrieval-Augmented Generation for Large Language Models: A Survey. In this survey, "
        "we review retrievers, generators and augmentation methods.",
        "Agentic AI for Complex Goals: A Comprehensive Survey. This survey thoroughly explores "
        "foundations and applications of agentic systems.",
        "Towards Faithful Model Explanation in NLP: A Survey. This survey categorises more than "
        "100 methods.",
    ],
)
def test_computer_science_literature_surveys_are_reviews(text):
    assert _design(text) == "narrative_review"


def test_a_questionnaire_survey_is_not_a_literature_survey():
    text = (
        "This survey examines job satisfaction among nurses. 300 respondents completed a "
        "Likert questionnaire distributed online; the survey study design follows CROSS."
    )
    assert resolve_research_design("auto", text).family == "empirical"


def test_a_brief_background_survey_does_not_make_a_review():
    text = (
        "We fine-tune a transformer model and evaluate it against baselines. Table 2 gives a "
        "brief survey of explanation methods; it is not meant to be a systematic survey."
    )
    assert _design(text) == "ml_experiment"


def test_designs_named_only_in_the_reference_list_do_not_count():
    body = "We fine-tune BERT on discharge summaries and compare it with a baseline model.\n" * 40
    text = body + "References\nBurns E. Systematic review of discharge coding accuracy. 2012.\n"
    assert "Systematic review" not in detection_text(text)
    assert _design(text) == "ml_experiment"


def test_ptk_in_a_student_number_is_not_classroom_action_research():
    text = "Disusun oleh A. Hanifa 23/525636/PTK/15370. Model deep learning untuk prediksi ICD-10."
    assert _design(text) != "classroom_action_research"
    assert _design("Penelitian ini adalah PTK dua siklus.") == "classroom_action_research"


def test_a_denied_meta_analysis_stays_a_systematic_review():
    text = (
        "This systematic review followed PRISMA with predefined inclusion criteria. A "
        "meta-analysis was not conducted because of heterogeneity; findings are reported "
        "with Synthesis Without Meta-analysis (SWiM). A metaanalysis was not feasible."
    )
    assert _design(text) == "systematic_review"


def test_a_denied_systematic_review_is_not_one():
    text = (
        "This is a structured curated review rather than an exhaustive systematic review; "
        "the protocol defines the corpus and its inclusion criteria."
    )
    assert _design(text) == "narrative_review"


def test_scoping_review_selected_with_prisma_stays_a_scoping_review():
    text = (
        "A Scoping Review: factors behind pending claims. The design is a scoping review. "
        "Articles were selected with PRISMA and inclusion criteria; Figure 1 is the PRISMA "
        "flow diagram."
    )
    explanation = explain_detection(text, family="review")
    assert explanation["chosen"] == "scoping_review"
    assert explanation["confidence"] == "high"


def test_sugiyono_textbook_title_is_not_an_rnd_design():
    text = (
        "Penelitian kualitatif dengan wawancara mendalam (Sugiyono, Metode Penelitian "
        "Kuantitatif, Kualitatif, dan R&D, 2013)."
    )
    hits = {item["key"]: item["counted"] for item in explain_detection(text, family="empirical")["candidates"]}
    assert "research_development" not in hits
    assert _design(text) == "qualitative"


def test_analysis_checks_ignore_lookalikes():
    assert check_analyses("Each domain gain was small; agents can gain context.").applied == ()
    assert check_analyses("Aiken WM. Organizational change. MIS Quarterly 1991.").applied == ()
    homoscedastic = check_analyses(
        "One-sided t-tests assuming homoscedastic variance; Shapiro-Wilk showed normality."
    )
    assert homoscedastic.issues == ()


# ----------------------------------------------------------------- new designs
# Paraphrased from the openings of methodological essays, editorials and
# benchmark papers in a thesis reference corpus.


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("RESEARCH ESSAY\nDesign Science in Information Systems Research\nTwo paradigms "
         "characterize much of the research in IS: behavioral science and design science.",
         "methodological_paper"),
        ("A Guide to Conducting a Standalone Systematic Literature Review\nMany scholars "
         "are not trained in systematic reviews; this guide explains eight steps.",
         "methodological_paper"),
        ("This paper develops a design science research methodology for producing and "
         "presenting design science research in information systems.",
         "methodological_paper"),
        ("Guest Editorial\nAnalyzing the past to prepare for the future: writing a "
         "literature review.", "position_paper"),
        ("EDITORIAL OPEN\nAutomating the overburdened clinical coding system: challenges "
         "and next steps.", "position_paper"),
    ],
)
def test_conceptual_papers_are_recognised_by_their_label(text, expected):
    design = resolve_research_design("auto", text)
    assert design.family == "conceptual" and design.key == expected


def test_labels_that_are_not_article_types_are_ignored():
    text = (
        "Editorial Board: J. Smith. From the viewpoint of hospitals, coding is costly. "
        "We fine-tune BERT on discharge summaries and compare it with a CNN baseline."
    )
    assert resolve_research_design("auto", text).family == "empirical"


def test_conceptual_papers_are_scored_without_a_method_section():
    from paperassist.manuscript_quality import score_manuscript

    essay = r"""\documentclass{article}
\begin{document}
\begin{abstract}
RESEARCH ESSAY. We present a framework for rigour.
\end{abstract}
RESEARCH ESSAY
\section{Introduction}
Existing guidance has a gap (Hevner et al. 2004).
\section{Framework}
The framework has three stages, illustrated with an example case; we justify each
stage and state its scope and limitations. Researchers should apply it; implications follow.
\end{document}
"""
    method = score_manuscript(essay).dimension("method_rigour")
    assert method.measurements["research_design"] == "methodological_paper"
    assert not any(f.message == "no method section" for f in method.findings)
    assert method.score > 0.5


@pytest.mark.parametrize(
    "text",
    [
        "InsClaimBench: An End-to-End Benchmark for Claim Adjudication\nWe introduce "
        "InsClaimBench, an end-to-end benchmark for evaluating insurance claim adjudication.",
        "T2ER: A Chinese Benchmark for Text-to-Executable-Rule Generation\nHence, we propose "
        "T2ER, a benchmark that converts rules. We release our dataset on GitHub.",
    ],
)
def test_benchmark_papers_outrank_the_ml_experiment(text):
    text += " We fine-tune transformer baselines and report F1 and accuracy." * 3
    assert _design(text) == "dataset_benchmark"


def test_using_a_benchmark_dataset_is_not_releasing_one():
    text = (
        "A label attention network for ICD coding. We evaluate on the MIMIC-III benchmark "
        "dataset; codes present in the dataset are frequent. We fine-tune BERT baselines "
        "and report micro-F1 and AUC with a transformer model."
    )
    assert _design(text) == "ml_experiment"


def test_others_reviews_and_adverbs_do_not_change_the_design():
    text = (
        "Comparative analysis of ML architectures for fraud detection. A 2025 systematic "
        "review by du Preez et al. surveyed 137 studies; recent systematic review evidence "
        "shows label scarcity. We train XGBoost and a neural network baseline."
    )
    assert resolve_research_design("auto", text).family == "empirical"
    policy = "The learned policy is qualitatively different from a hand-coded baseline."
    assert _design(policy) != "qualitative"


def test_survey_title_with_review_label_is_a_review():
    text = (
        "Review\nA survey of automated ICD coding: development, challenges and applications\n"
        "In this survey, we review the history of the task; this survey aims to provide a reference."
    )
    assert _design(text) == "narrative_review"
