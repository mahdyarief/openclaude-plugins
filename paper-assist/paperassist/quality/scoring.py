"""Combine the dimensions into a weighted score, grade and report."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import replace

from ..claim_ledger import ClaimLedger
from ..corpus_binder import CorpusBinding
from ..provenance_audit import DEFAULT_MIN_ANCHORED
from ..reporting_checks import (
    DeclarationCheck,
    FlowCheck,
    ReferenceAudit,
    ReferencePolicy,
    resolve_paper_type,
    resolve_research_design,
)
from ..thesis_checks import ThesisCheck, check_thesis, resolve_document_kind
from ._base import (
    _REFERENCE_ITEM_RE,
    DEFAULT_WEIGHTS,
    Dimension,
    Finding,
    QualityError,
    QualityReport,
    _grade,
)
from .compliance import (
    _dimension_declarations,
    _dimension_references,
    _dimension_thesis_statements,
)
from .grounding import (
    _dimension_citations,
    _dimension_evidence,
    _dimension_provenance,
)
from .method import (
    _dimension_limitations,
    _dimension_method,
)
from .structure import (
    _dimension_abstract,
    _dimension_depth,
    _dimension_structure,
)
from .style import (
    _dimension_formulaic_prose,
    _dimension_prose_style,
    _dimension_readability,
    _dimension_tables_figures,
)

# Words per graded section: an article section, and a thesis chapter, which
# carries several article sections' worth of argument.
DEFAULT_DEPTH_TARGET = 500
THESIS_DEPTH_TARGET = 1500


def _reference_keys(
    text: str,
    bibliography_entries: Sequence[str],
    bibliography_text: str | None,
) -> list[str]:
    keys: list[str] = list(bibliography_entries)
    if bibliography_text:
        for match in _REFERENCE_ITEM_RE.finditer(bibliography_text):
            key = match.group(1).strip()
            if key and key not in keys:
                keys.append(key)
    if not keys:
        for match in _REFERENCE_ITEM_RE.finditer(text):
            key = match.group(1).strip()
            if key not in keys:
                keys.append(key)
    return keys


def thesis_reference_policy(thesis: ThesisCheck | None) -> ReferencePolicy | None:
    """The reference policy the thesis profile sets, if it sets one."""

    from ..thesis_profiles import PROFILES

    if thesis is None or not thesis.profile_id:
        return None
    profile = next((p for p in PROFILES if p.profile_id == thesis.profile_id), None)
    if profile is None or not profile.reference_policy:
        return None
    return ReferencePolicy.from_payload(profile.reference_policy)


def _with_thesis_issues(dimension: Dimension, thesis: ThesisCheck | None, check: str) -> Dimension:
    """``dimension`` with the thesis findings of kind ``check`` added.

    Each warning costs 5% of the dimension score, down to 80%; advice is free.
    """

    if thesis is None:
        return dimension
    issues = [issue for issue in thesis.issues if issue.check == check]
    if not issues:
        return dimension
    warnings = sum(1 for issue in issues if issue.severity != "info")
    extra = tuple(
        Finding(dimension=dimension.name, severity=issue.severity,
                message=issue.message, remedy=issue.remedy)
        for issue in issues
    )
    measurements = dict(dimension.measurements)
    measurements["thesis_" + check] = (
        dict(thesis.citations) if check == "citations" else dict(thesis.floats)
    )
    return replace(
        dimension,
        score=dimension.score * max(0.8, 1 - 0.05 * warnings),
        measurements=measurements,
        findings=dimension.findings + extra,
    )


def score_manuscript(
    text: str,
    *,
    ledger: ClaimLedger | None = None,
    binding: CorpusBinding | None = None,
    bibliography_entries: Sequence[str] = (),
    bibliography_text: str | None = None,
    depth_target: int = DEFAULT_DEPTH_TARGET,
    min_anchored: float = DEFAULT_MIN_ANCHORED,
    allow_em_dash: bool = False,
    weights: Mapping[str, float] | None = None,
    corpus_size: int | None = None,
    paper_type: str | None = "auto",
    research_design: str | None = "auto",
    prisma_flow: FlowCheck | None = None,
    participant_flow: FlowCheck | None = None,
    declarations: DeclarationCheck | None = None,
    reference_audit: ReferenceAudit | None = None,
    locator_checks: Mapping[str, str] | None = None,
    asset_root: str | None = None,
    document_kind: str | None = "auto",
    thesis_profile: str | Mapping[str, object] | None = "auto",
    thesis: ThesisCheck | None = None,
    thesis_stage: str | None = "auto",
) -> QualityReport:
    """Score a manuscript across fourteen deterministic dimensions.

    ``paper_type`` selects the reporting standard: ``review`` (PRISMA 2020 /
    PRISMA-S signals and flow arithmetic) or ``empirical`` (design, data,
    analysis, statistics); ``auto`` decides from the corpus and the text.
    ``research_design`` narrows that to a specific design and its reporting
    guideline (``rct`` -> CONSORT 2025, ``qualitative`` -> SRQR/COREQ,
    ``classroom_action_research`` -> the PTK cycle, ...); ``auto`` picks the
    most specific design the manuscript names. See
    :mod:`paperassist.research_designs`.
    ``participant_flow`` is the CONSORT or STROBE count check from
    :mod:`paperassist.participant_flow`, used when the design has that flow.
    ``declarations``, ``reference_audit``, ``prisma_flow`` and
    ``locator_checks`` come from :mod:`paperassist.reporting_checks`; when a
    caller omits them, declarations are detected from the text and the other
    checks are reported as not measured.

    ``document_kind`` is ``article``, ``thesis`` or ``auto``. A thesis is
    judged on its front matter (approval page, originality statement,
    abstracts) instead of journal declarations, on Chapter 1 and on whether
    its research questions, objectives and conclusions line up; chapters are
    held to a longer depth target, and the layout is compared with
    ``thesis_profile`` (a profile id, ``auto`` to detect one, or a ready
    :class:`~paperassist.thesis_checks.ThesisCheck` passed as ``thesis``).
    ``thesis_stage`` is ``proposal`` (Chapters 1-3: no results, conclusion,
    abstract or limitations expected; the method is judged as a plan),
    ``final`` or ``auto``.

    ``corpus_size`` is how many studies the manuscript had to synthesise. A
    binding supplies it when one exists; a caller holding extraction records
    without bound full texts passes it directly, because a review's reporting
    floor follows the corpus it claims, not the files it happens to have.
    """

    if not isinstance(text, str) or not text.strip():
        raise QualityError("manuscript text is empty")
    if depth_target <= 0:
        raise QualityError("depth_target must be positive")
    if not 0 < min_anchored <= 1:
        raise QualityError("min_anchored must be in (0, 1]")

    active_weights = dict(DEFAULT_WEIGHTS)
    if weights:
        unknown = set(weights) - set(DEFAULT_WEIGHTS)
        if unknown:
            raise QualityError(f"unknown quality dimensions: {sorted(unknown)}")
        active_weights.update({key: float(value) for key, value in weights.items()})
    total_weight = sum(active_weights.values())
    if total_weight <= 0:
        raise QualityError("weights must sum to a positive value")

    reference_keys = _reference_keys(text, bibliography_entries, bibliography_text)

    if ledger is None:
        from ..claim_ledger import build_ledger

        ledger = build_ledger(text)

    if corpus_size is None:
        corpus_size = len(binding.records) if binding else 0
    if corpus_size < 0:
        raise QualityError("corpus_size must not be negative")
    try:
        resolved_type = resolve_paper_type(paper_type, text, study_count=corpus_size)
        design = resolve_research_design(
            research_design, text, study_count=corpus_size, paper_type=paper_type
        )
    except ValueError as exc:
        raise QualityError(str(exc)) from exc
    try:
        kind = resolve_document_kind(document_kind, text)
        if kind == "thesis" and thesis is None:
            thesis = check_thesis(text, profile=thesis_profile, stage=thesis_stage)
    except ValueError as exc:
        raise QualityError(str(exc)) from exc
    is_thesis = kind == "thesis"
    proposal = is_thesis and thesis is not None and thesis.stage == "proposal"
    if is_thesis and depth_target == DEFAULT_DEPTH_TARGET:
        depth_target = THESIS_DEPTH_TARGET
    if declarations is None:
        from ..reporting_checks import check_declarations

        declarations = check_declarations(text, paper_type=resolved_type)
    if reference_audit is None and bibliography_text:
        from ..corpus_binder import parse_bib_entries
        from ..reporting_checks import audit_references, cited_keys

        cited = cited_keys(text)
        reference_audit = audit_references(
            parse_bib_entries(bibliography_text),
            cited_keys=cited,
            policy=thesis_reference_policy(thesis) if is_thesis else None,
        )

    dimensions = (
        _dimension_structure(
            text, depth_target=depth_target, thesis=thesis if is_thesis else None
        ),
        _dimension_abstract(text, thesis=is_thesis, required=not proposal),
        _dimension_depth(
            text, depth_target=depth_target, corpus_size=corpus_size
        ),
        _dimension_citations(ledger, binding, reference_keys=reference_keys),
        _dimension_provenance(
            ledger, min_anchored=min_anchored, locator_checks=locator_checks
        ),
        _dimension_evidence(ledger, binding),
        _dimension_method(
            text,
            paper_type=resolved_type,
            flow=prisma_flow if design.flow == "prisma" else participant_flow,
            design=design,
            planned=proposal,
        ),
        _dimension_limitations(text, thesis=is_thesis, required=not proposal),
        _dimension_thesis_statements(thesis, declarations)
        if is_thesis and thesis is not None
        else _dimension_declarations(declarations),
        _with_thesis_issues(_dimension_references(reference_audit), thesis, "citations"),
        _dimension_prose_style(text, allow_em_dash=allow_em_dash),
        _with_thesis_issues(
            _dimension_tables_figures(text, asset_root=asset_root), thesis, "floats"
        ),
        _dimension_readability(text),
        _dimension_formulaic_prose(text),
    )

    weighted = sum(
        dimension.score * active_weights[dimension.name] for dimension in dimensions
    )
    score = weighted / total_weight
    grade, recommendation = _grade(score)
    worst = tuple(
        dimension.name
        for dimension in sorted(dimensions, key=lambda d: d.score)[:3]
        if dimension.score < 0.7
    )

    report = QualityReport(
        dimensions=dimensions,
        paper_type=resolved_type,
        research_design=design.key,
        document_kind=kind,
        score=score,
        grade=grade,
        recommendation=recommendation,
        worst_dimensions=worst,
        source_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )
    digest = hashlib.sha256(
        json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return QualityReport(
        dimensions=report.dimensions,
        paper_type=report.paper_type,
        research_design=report.research_design,
        document_kind=report.document_kind,
        score=report.score,
        grade=report.grade,
        recommendation=report.recommendation,
        worst_dimensions=report.worst_dimensions,
        digest=digest,
        source_sha256=report.source_sha256,
    )


def format_quality_report(report: QualityReport) -> str:
    lines = [
        "## Manuscript quality report",
        "",
        f"**Score:** {report.score:.3f}  |  **Grade:** {report.grade}  |  "
        f"**Recommendation:** {report.recommendation}  |  "
        f"**Paper type:** {report.paper_type}"
        + (f"  |  **Design:** {report.research_design}" if report.research_design else "")
        + ("  |  **Document:** thesis" if report.document_kind == "thesis" else ""),
        "",
        "| Dimension | Score | Weight |",
        "|---|---|---|",
    ]
    for dimension in sorted(report.dimensions, key=lambda d: d.score):
        lines.append(
            f"| {dimension.name} | {dimension.score:.2f} | {dimension.weight:.2f} |"
        )
    critical = report.findings(min_severity="critical")
    warnings = report.findings(min_severity="warning")
    if critical:
        lines += ["", "### Blocking findings", ""]
        for finding in critical:
            location = f" (line {finding.line})" if finding.line else ""
            lines.append(
                f"- [{finding.dimension}] {finding.message}{location} — {finding.remedy}"
            )
    remaining = [finding for finding in warnings if finding not in critical]
    if remaining:
        lines += ["", "### Warnings", ""]
        for finding in remaining[:15]:
            lines.append(
                f"- [{finding.dimension}] {finding.message} — {finding.remedy}"
            )
        if len(remaining) > 15:
            lines.append(f"- and {len(remaining) - 15} more")
    lines.append("")
    return "\n".join(lines)
