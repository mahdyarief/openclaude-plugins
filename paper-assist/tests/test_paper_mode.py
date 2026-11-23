from __future__ import annotations

import json

import pytest

from paperassist.manuscript_quality import DEFAULT_WEIGHTS, score_manuscript
from paperassist.protected_blocks import PROTECTED_END, PROTECTED_START, extract_protected_blocks
from paperassist.research_os import run_research_os
from paperassist.writing import WritingEngine, WritingSafetyError
from paperassist.writing_pack import ACCEPTANCE_RULES, skeleton_document

EMPIRICAL = r"""\documentclass{article}
\begin{document}
\begin{abstract}
This paper proposes a classifier. We show it improves accuracy on a held-out set
and conclude that it is practical.
\end{abstract}
\section{Pendahuluan}
Introduction text about the problem and the contribution.
\section{Metode}
We use a research design with a public dataset of 1200 samples, an implementation
pipeline, accuracy as the evaluation metric, statistical analysis with a t-test,
a logistic regression baseline for comparison, and validation on a test set.
Hyperparameters and the random seed are listed; code is on github.com/x/y.
\section{Hasil dan Pembahasan}
Accuracy is 0.91 (SD 0.02, 95\% confidence interval 0.89--0.93, n = 300),
p < 0.01 against the baseline. The gain suggests the features generalise.
\subsection{Keterbatasan}
The dataset covers one language and one domain, so external validity is limited;
the labels come from a single annotator, which limits construct validity.
\section{Kesimpulan}
The classifier is practical for the studied setting.
\end{document}
"""


def test_combined_results_and_discussion_heading_counts_as_both():
    report = score_manuscript(EMPIRICAL, paper_type="empirical")
    structure = report.dimension("structure")
    missing = [f.message for f in structure.findings if "missing" in f.message]
    assert missing == []


def test_limitations_subsection_counts_as_a_dedicated_statement():
    report = score_manuscript(EMPIRICAL, paper_type="empirical")
    assert report.dimension("limitations").measurements["section_present"] is True


def test_empirical_paper_is_not_judged_on_search_strategy():
    report = score_manuscript(EMPIRICAL)
    assert report.paper_type == "empirical"
    method = report.dimension("method_rigour")
    assert "search strategy" not in method.measurements["missing"]
    assert set(method.measurements["statistics"]) == {
        "uncertainty",
        "significance or effect",
        "sample size",
    }
    review_view = score_manuscript(EMPIRICAL, paper_type="review").dimension("method_rigour")
    assert method.score > review_view.score


def test_declarations_dimension_and_weights():
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9
    report = score_manuscript(EMPIRICAL)
    missing = report.dimension("declarations").measurements["missing"]
    assert "ai_use" in missing and "competing_interests" in missing
    declared = EMPIRICAL.replace(
        r"\end{document}",
        "\\section*{Declarations}\nCompeting interests: none. Funding: none received. "
        "Data availability: the data are available at Zenodo. Use of generative AI: "
        "no generative AI tools were used.\n\\end{document}",
    )
    assert score_manuscript(declared).dimension("declarations").score == 1.0


def test_figure_paths_resolve_against_the_manuscript_folder(tmp_path):
    (tmp_path / "fig.png").write_bytes(b"x")
    text = EMPIRICAL.replace(
        r"\section{Kesimpulan}",
        "\\begin{figure}\\includegraphics{fig.png}\\caption{c}\\label{f}\\end{figure}\n"
        "Figure \\ref{f}.\n\\section{Kesimpulan}",
    )
    found = score_manuscript(text, asset_root=str(tmp_path)).dimension("tables_figures")
    assert not any("not found" in f.message for f in found.findings)


PROTECTED = (
    f"{PROTECTED_START}\n"
    "\\section{Results}\nAccuracy is 91.2\\% (Table~\\ref{tab:main}).\n"
    "\\begin{table}\\caption{Main}\\label{tab:main}\\end{table}\n"
    f"{PROTECTED_END}"
)


def _draft(prose: str) -> str:
    return (
        "\\documentclass{article}\n\\begin{document}\n"
        f"{PROTECTED}\n\\section{{Discussion}}\n{prose}\n\\end{{document}}\n"
    )


def _validate(prose: str) -> None:
    text = _draft(prose)
    WritingEngine._validate_candidate(
        text,
        protected_blocks=extract_protected_blocks(text),
        bibliography_keys=frozenset(),
    )


def test_discussion_may_restate_protected_numbers():
    _validate("The accuracy of 91.2\\% shows the features transfer.")
    _validate("The method can outperform the baseline, as Table~\\ref{tab:main} shows.")


def test_discussion_cannot_introduce_new_numbers():
    with pytest.raises(WritingSafetyError, match="experimental claim"):
        _validate("The accuracy of 95.0\\% shows the features transfer.")
    with pytest.raises(WritingSafetyError, match="experimental claim"):
        _validate("Our method is state-of-the-art.")


def test_assistant_residue_is_rejected():
    with pytest.raises(WritingSafetyError, match="narration"):
        _validate("As an AI language model, I cannot run experiments.")
    with pytest.raises(WritingSafetyError, match="narration"):
        _validate("Berikut adalah revisi yang telah diperbaiki.")


def test_skeleton_has_discussion_limitations_and_protected_declarations():
    skeleton = skeleton_document("T")
    assert "\\section{Discussion}" in skeleton
    assert "\\section{Limitations}" in skeleton
    blocks = extract_protected_blocks(skeleton)
    assert len(blocks) == 2 and "Declarations" in blocks[1]
    assert any("Declarations block" in rule for rule in ACCEPTANCE_RULES)


def test_paper_pack_skips_author_owned_sections(tmp_path):
    from paperassist.writing_pack import build_writing_pack
    from tests.test_writing_pack_depth import MAIN_TEX, make_workspace

    make_workspace(tmp_path)
    pack = build_writing_pack(
        tmp_path, run_id="p", payload={}, target_path="main.tex", original_text=MAIN_TEX
    )
    ids = [task.task_id for task in pack.tasks]
    assert "section-discussion" in ids and "section-limitations" in ids
    assert "section-results" not in ids and "section-experimental-setup" not in ids


REVIEW = r"""\documentclass{article}
\begin{document}
\begin{abstract}This systematic review follows PRISMA.\end{abstract}
\section{Introduction} Context.
\section{Methods} We searched Scopus. Inclusion criteria applied.
\section{Results} Forty studies were included \cite{a}. % @locator{a: page=2, quote="a quote that is not in the paper"}
\section{Discussion} Meaning.
\section{Conclusion} End.
\end{document}
"""


def test_research_os_checks_flow_and_locator_quotes(tmp_path):
    (tmp_path / "main.tex").write_text(REVIEW, encoding="utf-8")
    (tmp_path / "refs.bib").write_text(
        "@article{a, title={Graph retrieval at scale}, year={2024}, doi={10.1234/abc}}\n",
        encoding="utf-8",
    )
    (tmp_path / "flow.json").write_text(
        json.dumps({"records_identified": 100, "duplicates_removed": 10, "records_screened": 95}),
        encoding="utf-8",
    )
    (tmp_path / "records.json").write_text(
        json.dumps([{"id": "s1", "title": "Graph retrieval at scale", "doi": "10.1234/abc"}]),
        encoding="utf-8",
    )
    full = tmp_path / "fulltext"
    full.mkdir()
    (full / "s1.txt").write_text("The paper says something else.", encoding="utf-8")
    result = run_research_os(
        tmp_path,
        {
            "run_id": "r",
            "target_path": "main.tex",
            "records_path": "records.json",
            "records_paths": ["flow.json"],
            "fulltext_root": "fulltext",
            "bibliography_path": "refs.bib",
        },
    )
    quality = result.quality
    assert quality.paper_type == "review"
    method = quality.dimension("method_rigour")
    assert any("does not add up at identification" in f.message for f in method.findings)
    provenance = quality.dimension("provenance")
    assert provenance.measurements["locator_quotes_not_found"] == ["a"]
    checks = json.loads((tmp_path / result.artifacts["reporting_checks"]).read_text("utf-8"))
    assert checks["prisma_flow"]["passed"] is False
