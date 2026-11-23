"""Tests for verified revision and the revision planner."""

from __future__ import annotations

import pytest

from paperassist.claim_ledger import build_ledger
from paperassist.improvement_loop import (
    VERDICT_BLOCKED,
    VERDICT_IMPROVED,
    VERDICT_UNCHANGED,
    ImprovementError,
    format_verdict,
    revision_plan,
    verify_revision,
)
from paperassist.manuscript_quality import score_manuscript

BASE = r"""\begin{document}
\begin{abstract}
This review examines addressability. We searched six databases. The results show
coding scores highest, and we conclude provenance must be measured.
\end{abstract}
\section{Introduction}
Prior work established a baseline \citep{alpha2020}.% @locator{alpha2020: page=3, quote="baseline improved"}
\section{Method}
We searched Scopus and PubMed with a documented search strategy, applied inclusion
and exclusion criteria, performed extraction, quality appraisal and narrative synthesis.
\section{Results}
The gradient is monotone across classes.
\section{Discussion}
This has consequences for governance and for audit.
\section{Limitations}
The corpus and instrument limit generalisability.
\section{Conclusions}
Coding is the defensible target and provenance must be measured.
\end{document}
"""


def _reports(before_text, after_text):
    before = score_manuscript(before_text)
    after = score_manuscript(after_text)
    return before, after


def test_identical_revision_is_unchanged():
    before, after = _reports(BASE, BASE)
    verdict = verify_revision(before, after)
    assert verdict.verdict == VERDICT_UNCHANGED
    assert verdict.accepted is True
    assert verdict.score_change == 0


def test_unsourced_padding_does_not_count_as_improvement():
    # Four extra narrative sentences dilute the evidence channel, so the score
    # must not rise and the revision must be refused.
    padded = BASE.replace(
        "The gradient is monotone across classes.",
        "The gradient is monotone across classes and it holds for every axis of the rubric. "
        "Each axis separates the classes by at least two points, which suggests the "
        "instrument discriminates rather than merely ranking. The pattern survives the "
        "risk of bias split, so the ordering is not an artefact of study quality.",
    )
    before, after = _reports(BASE, padded)
    verdict = verify_revision(before, after)
    assert verdict.verdict == VERDICT_BLOCKED
    assert verdict.accepted is False


def test_added_sourced_material_improves_score():
    expanded = BASE.replace(
        "The gradient is monotone across classes.",
        "The gradient is monotone across classes \\citep{alpha2020} and it holds for "
        "every axis of the rubric \\citep{beta2021}. Each axis separates the classes "
        "by at least two points \\citep{gamma2022}, which suggests the instrument "
        "discriminates rather than merely ranking \\citep{delta2023}. The ordering "
        "therefore survives the risk of bias split \\citep{epsilon2024}.",
    )
    before, after = _reports(BASE, expanded)
    verdict = verify_revision(before, after)
    assert verdict.verdict == VERDICT_IMPROVED
    assert verdict.accepted is True
    assert verdict.score_change > 0


def test_new_unsupported_assertion_blocks_the_revision():
    worse = BASE.replace(
        "The gradient is monotone across classes.",
        "In total 96.4 percent of the corpus omits the measure entirely.",
    )
    before, after = _reports(BASE, worse)
    verdict = verify_revision(
        before,
        after,
        before_ledger=build_ledger(BASE),
        after_ledger=build_ledger(worse),
    )
    assert verdict.verdict == VERDICT_BLOCKED
    assert verdict.accepted is False
    assert any("unsupported" in regression for regression in verdict.regressions)
    assert verdict.new_unsupported


def test_dropped_section_blocks_the_revision():
    removed = BASE.replace("\\section{Limitations}\nThe corpus and instrument limit generalisability.\n", "")
    before, after = _reports(BASE, removed)
    verdict = verify_revision(before, after)
    assert verdict.verdict == VERDICT_BLOCKED
    assert any("limitations" in regression for regression in verdict.regressions)


def test_missing_citation_blocks_the_revision():
    stripped = BASE.replace("\\citep{alpha2020}", "")
    before, after = _reports(BASE, stripped)
    verdict = verify_revision(
        before,
        after,
        before_ledger=build_ledger(BASE),
        after_ledger=build_ledger(stripped),
    )
    assert verdict.verdict == VERDICT_BLOCKED
    assert any("citation key" in regression for regression in verdict.regressions)


def test_resolved_unsupported_is_reported():
    worse = BASE.replace(
        "The gradient is monotone across classes.",
        "In total 96.4 percent of the corpus omits the measure entirely.",
    )
    before, after = _reports(worse, BASE)
    verdict = verify_revision(
        before,
        after,
        before_ledger=build_ledger(worse),
        after_ledger=build_ledger(BASE),
    )
    assert verdict.resolved_unsupported


def test_regression_is_allowed_when_check_disabled():
    worse = BASE.replace(
        "The gradient is monotone across classes.", "Short."
    )
    before, after = _reports(BASE, worse)
    verdict = verify_revision(before, after, require_not_worse=False)
    assert verdict.verdict in {VERDICT_BLOCKED, "regressed"}


def test_none_report_is_rejected():
    before = score_manuscript(BASE)
    with pytest.raises(ImprovementError):
        verify_revision(before, None)  # type: ignore[arg-type]


def test_invalid_tolerance_is_rejected():
    before, after = _reports(BASE, BASE)
    with pytest.raises(ImprovementError):
        verify_revision(before, after, max_grounding_drop=2)


def test_verdict_serialises_and_is_deterministic():
    before, after = _reports(BASE, BASE)
    first = verify_revision(before, after)
    second = verify_revision(before, after)
    assert first.digest == second.digest
    payload = first.to_dict()
    assert payload["schema"] == "paperassist.revision-verdict/v1"
    assert payload["deltas"]


def test_revision_plan_orders_critical_first():
    sparse = r"""\begin{document}
\section{Introduction}
Text with 91.5 percent unsupported.
\end{document}
"""
    report = score_manuscript(sparse)
    plan = revision_plan(report, limit=5)
    assert plan
    assert plan[0]["severity"] == "critical"
    assert len(plan) <= 5


def test_revision_plan_rejects_bad_limit():
    report = score_manuscript(BASE)
    with pytest.raises(ImprovementError):
        revision_plan(report, limit=0)


def test_verdict_formats_regressions():
    removed = BASE.replace("\\section{Limitations}\nThe corpus and instrument limit generalisability.\n", "")
    before, after = _reports(BASE, removed)
    rendered = format_verdict(verify_revision(before, after))
    assert "Revision verdict" in rendered
    assert "Blocking regressions" in rendered
