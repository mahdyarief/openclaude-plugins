"""Method rigour and limitations, judged against the research design's reporting standard."""

from __future__ import annotations

import re
from typing import Any

from ..analysis_checks import check_analyses
from ..reporting_checks import (
    FlowCheck,
)
from ..research_designs import DESIGNS, STATISTICS_SIGNALS, ResearchDesign
from ._base import (
    DEFAULT_WEIGHTS,
    Dimension,
    Finding,
    _clamp,
    _count_words,
    _heading_body,
    _section_bodies,
    _strip_latex,
)

# Signal tables live in the research-design registry; these names keep the
# general review and empirical tables addressable for callers and tests.
_REVIEW_METHOD_SIGNALS = DESIGNS["systematic_review"].method_signals
_REVIEW_REPRO_SIGNALS = DESIGNS["systematic_review"].repro_signals
_EMPIRICAL_METHOD_SIGNALS = DESIGNS["empirical"].method_signals
_EMPIRICAL_REPRO_SIGNALS = DESIGNS["empirical"].repro_signals
_STATISTICS_SIGNALS = STATISTICS_SIGNALS
# Designs whose analyses are numeric enough for the N-gain, Aiken's V and
# prerequisite-test checks; qualitative designs are never asked for them.
_QUANTITATIVE_CATEGORIES = (
    "quantitative",
    "mixed methods",
    "design and development",
    "action research",
)


_FLOW_LABELS = {"prisma": "PRISMA 2020", "consort": "CONSORT 2025", "strobe": "STROBE"}
_FLOW_HINTS = {
    "prisma": (
        "pass the flow document (e.g. prisma_flow.json with identified, "
        "duplicates_removed, screened, excluded_screening, sought, "
        "not_retrieved, assessed, excluded_fulltext, included)"
    ),
    "consort": (
        "pass the participant flow (e.g. participant_flow.json with assessed, "
        "excluded, randomised and arms: {name: {allocated, received, not_received, "
        "lost_to_follow_up, analysed, excluded_from_analysis}})"
    ),
    "strobe": (
        "pass the participant flow (e.g. participant_flow.json with "
        "potentially_eligible, examined, eligible, included, followed_up, analysed)"
    ),
}


def _flow_findings(
    flow: FlowCheck | None, kind: str = "prisma"
) -> tuple[float, list[Finding]]:
    """Flow-diagram arithmetic (PRISMA, CONSORT or STROBE) as a score part and findings."""

    label = _FLOW_LABELS.get(kind, kind.upper())
    if flow is None or not flow.available:
        return 0.5, [
            Finding(
                dimension="method_rigour",
                severity="info",
                message=f"no {label} flow counts supplied; flow arithmetic not checked",
                remedy=_FLOW_HINTS.get(kind, "pass the flow counts"),
            )
        ]
    findings = [
        Finding(
            dimension="method_rigour",
            severity="critical",
            message=f"{label} flow does not add up at {identity.describe()}",
            remedy="correct the flow counts so every stage follows from the one before",
        )
        for identity in flow.identities
        if not identity.passed
    ]
    if flow.unchecked:
        findings.append(
            Finding(
                dimension="method_rigour",
                severity="info",
                message=f"{label} flow stages not checkable: " + ", ".join(flow.unchecked),
                remedy=f"report every count of the {label} flow diagram",
            )
        )
    if not flow.identities:
        return 0.5, findings
    passed = sum(1 for identity in flow.identities if identity.passed)
    return passed / len(flow.identities), findings


def _dimension_method(
    text: str,
    *,
    paper_type: str = "review",
    flow: FlowCheck | None = None,
    design: ResearchDesign | None = None,
    planned: bool = False,
) -> Dimension:
    """Method rigour: 0.6 method items + 0.2 reproducibility + 0.2 results/flow.

    ``planned`` is a thesis proposal: the method describes a study not yet run,
    so the score is the method and reproducibility items alone.

    ``design`` selects the reporting standard (see
    :mod:`paperassist.research_designs`); without one, ``paper_type`` selects
    the general systematic-review or empirical standard.
    """

    if design is None:
        design = DESIGNS[
            {"review": "systematic_review", "conceptual": "position_paper"}.get(paper_type, "empirical")
        ]
    bodies = _section_bodies(text)
    method = bodies.get("method", "")
    if design.family == "conceptual":
        # An essay or editorial has no Method section; its argument is the text.
        method = text
        bodies = {**bodies, "results": text}
    lowered = _strip_latex(method).lower()
    findings: list[Finding] = []
    base: dict[str, Any] = {
        "paper_type": design.family,
        "research_design": design.key,
        "guideline": design.guideline,
    }
    if not method:
        findings.append(
            Finding(
                dimension="method_rigour",
                severity="critical",
                message="no method section",
                remedy="describe the procedure so another team could repeat it",
            )
        )
        return Dimension(
            name="method_rigour",
            score=0.0,
            weight=DEFAULT_WEIGHTS["method_rigour"],
            measurements={**base, "signals": [], "repro": []},
            findings=tuple(findings),
        )
    method_signals, repro_signals = design.method_signals, design.repro_signals
    covered = [name for name, pattern in method_signals if re.search(pattern, lowered)]
    missing = [name for name, _ in method_signals if name not in covered]
    for name in missing:
        findings.append(
            Finding(
                dimension="method_rigour",
                severity="warning",
                message=f"method does not describe: {name}",
                remedy=f"add the {name}, as {design.guideline} asks",
            )
        )
    whole = _strip_latex(text).lower()
    repro = [name for name, pattern in repro_signals if re.search(pattern, whole)]
    measurements: dict[str, Any] = {
        **base,
        "signals": covered,
        "missing": missing,
        "repro": repro,
    }
    if planned:
        third = 1.0
        measurements["planned"] = True
    elif design.flow == "prisma":
        third, flow_notes = _flow_findings(flow)
        findings.extend(flow_notes)
        measurements["prisma_flow"] = flow.to_dict() if flow else None
    else:
        results_signals = design.results_signals or STATISTICS_SIGNALS
        # The raw body keeps \pm and quotation marks that some signals need.
        raw_results = bodies.get("results", "")
        results = (_strip_latex(raw_results) + "\n" + raw_results).lower()
        reported = [name for name, pattern in results_signals if re.search(pattern, results)]
        measurements["results_items"] = reported
        if results_signals == STATISTICS_SIGNALS:
            measurements["statistics"] = reported
        if raw_results.strip() and len(reported) < len(results_signals):
            absent = [name for name, _ in results_signals if name not in reported]
            remedy = (
                "report variability (SD/CI), effect size or test result, and "
                "sample size beside each headline number"
                if set(absent) <= {name for name, _ in STATISTICS_SIGNALS}
                else f"report these in the results, as {design.guideline} expects"
            )
            findings.append(
                Finding(
                    dimension="method_rigour",
                    severity="warning",
                    message="results do not report: " + ", ".join(absent),
                    remedy=remedy,
                )
            )
        third = len(reported) / len(results_signals) if raw_results.strip() else 0.0
        if design.flow in ("consort", "strobe"):
            # Half the results part is the reported items, half the participant
            # flow adding up; unsupplied counts score neutral, as for PRISMA.
            flow_part, flow_notes = _flow_findings(flow, design.flow)
            findings.extend(flow_notes)
            measurements["participant_flow"] = flow.to_dict() if flow else None
            third = 0.5 * third + 0.5 * flow_part
    if design.family == "empirical" and design.category in _QUANTITATIVE_CATEGORIES:
        # Advisory: these issues are reported but do not move the score.
        analyses = check_analyses(_strip_latex(text))
        if analyses.applied:
            measurements["analysis_checks"] = analyses.to_dict()
            findings.extend(
                Finding(
                    dimension="method_rigour",
                    severity=issue.severity,
                    message=issue.message,
                    remedy=issue.remedy,
                )
                for issue in analyses.issues
            )
    if design.notes:
        measurements["notes"] = design.notes
    score = (
        0.6 * (len(covered) / len(method_signals))
        + 0.2 * (len(repro) / len(repro_signals) if repro_signals else 1.0)
        + 0.2 * third
    )
    return Dimension(
        name="method_rigour",
        score=_clamp(score),
        weight=DEFAULT_WEIGHTS["method_rigour"],
        measurements=measurements,
        findings=tuple(findings),
    )


def _dimension_limitations(
    text: str, *, thesis: bool = False, required: bool = True
) -> Dimension:
    if not required:
        # A thesis proposal states its scope (Batasan Masalah), not the
        # limitations of a study it has yet to run.
        return Dimension(
            name="limitations",
            score=1.0,
            weight=DEFAULT_WEIGHTS["limitations"],
            measurements={"required": False},
        )
    bodies = _section_bodies(text)
    lowered = text.lower()
    findings: list[Finding] = []
    present = "limitations" in bodies
    if not present:
        # A Limitations subsection inside the Discussion is a dedicated,
        # findable statement too, and is common in journal templates.
        nested = _heading_body(text, "limitations")
        if nested.strip():
            bodies = {**bodies, "limitations": nested}
            present = True
    if not present and thesis:
        # A thesis states its limitations in the closing chapter, often in
        # the Saran paragraphs rather than under a heading of their own.
        closing = _strip_latex(bodies.get("conclusion", ""))
        sentences = [
            sentence
            for sentence in re.split(r"(?<=[.!?])\s+", closing)
            if re.search(r"keterbatasan|terbatas pada|limitation|limited to", sentence, re.I)
        ]
        if sentences:
            bodies = {**bodies, "limitations": " ".join(sentences)}
            present = True
    if not present:
        findings.append(
            Finding(
                dimension="limitations",
                severity="warning",
                message="no limitations section and no explicit limitation statement",
                remedy=(
                    "add a limitations section covering corpus, method and "
                    "generalisability"
                ),
            )
        )
    has_threats = bool(
        re.search(r"threats? to validity|validitas|keterbatasan|limitation", lowered)
    )
    score = 0.0
    if present:
        body = _strip_latex(bodies["limitations"])
        score = 0.6 + 0.4 * min(1.0, _count_words(body) / 150)
    elif has_threats:
        score = 0.45
    return Dimension(
        name="limitations",
        score=_clamp(score),
        weight=DEFAULT_WEIGHTS["limitations"],
        measurements={"section_present": present, "explicit_statement": has_threats},
        findings=tuple(findings),
    )
