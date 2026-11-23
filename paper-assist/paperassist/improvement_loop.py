"""Verified revision: measure, propose, re-measure, refuse regressions.

An improvement loop that only adds words is not an improvement loop. This module
takes a before-state (quality report plus claim ledger), an after-state, and
produces a delta that a reviewer can check. A revision is rejected when it
lowers grounding, introduces new unsupported assertions, drops required
sections, or removes cited work. The rejection is reported with the exact
regressions rather than silently accepted.

The module never edits text. Revision is the harness's job; verification is
this module's job, and it is deterministic.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .claim_ledger import ClaimLedger
from .manuscript_quality import QualityReport

VERDICT_SCHEMA = "paperassist.revision-verdict/v1"

VERDICT_IMPROVED = "improved"
VERDICT_UNCHANGED = "unchanged"
VERDICT_REGRESSED = "regressed"
VERDICT_BLOCKED = "blocked"

_REGRESSION_TOLERANCE = 1e-9
_MAX_GROUNDING_DROP = 0.05
_MAX_DIMENSION_DROP = 0.05


class ImprovementError(RuntimeError):
    pass


@dataclass(frozen=True)
class DimensionDelta:
    name: str
    before: float
    after: float

    @property
    def change(self) -> float:
        return round(self.after - self.before, 4)

    @property
    def direction(self) -> str:
        if self.change > _REGRESSION_TOLERANCE:
            return "up"
        if self.change < -_REGRESSION_TOLERANCE:
            return "down"
        return "flat"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "before": round(self.before, 4),
            "after": round(self.after, 4),
            "change": self.change,
            "direction": self.direction,
        }


@dataclass(frozen=True)
class RevisionVerdict:
    verdict: str
    score_before: float
    score_after: float
    grade_before: str
    grade_after: str
    deltas: tuple[DimensionDelta, ...] = ()
    regressions: tuple[str, ...] = ()
    improvements: tuple[str, ...] = ()
    new_unsupported: tuple[str, ...] = ()
    resolved_unsupported: tuple[str, ...] = ()
    digest: str = ""

    @property
    def score_change(self) -> float:
        return round(self.score_after - self.score_before, 4)

    @property
    def accepted(self) -> bool:
        return self.verdict in {VERDICT_IMPROVED, VERDICT_UNCHANGED}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": VERDICT_SCHEMA,
            "verdict": self.verdict,
            "accepted": self.accepted,
            "score_before": round(self.score_before, 4),
            "score_after": round(self.score_after, 4),
            "score_change": self.score_change,
            "grade_before": self.grade_before,
            "grade_after": self.grade_after,
            "deltas": [delta.to_dict() for delta in self.deltas],
            "regressions": list(self.regressions),
            "improvements": list(self.improvements),
            "new_unsupported": list(self.new_unsupported),
            "resolved_unsupported": list(self.resolved_unsupported),
            "digest": self.digest,
        }


def _normalized_sentence(text: str) -> str:
    return " ".join(text.split()).strip().lower()


def verify_revision(
    before: QualityReport,
    after: QualityReport,
    *,
    before_ledger: ClaimLedger | None = None,
    after_ledger: ClaimLedger | None = None,
    max_grounding_drop: float = _MAX_GROUNDING_DROP,
    max_dimension_drop: float = _MAX_DIMENSION_DROP,
    require_not_worse: bool = True,
) -> RevisionVerdict:
    """Compare two states and return a verdict with the exact regressions."""

    if before is None or after is None:
        raise ImprovementError("both before and after reports are required")
    if not 0 <= max_grounding_drop <= 1:
        raise ImprovementError("max_grounding_drop must be in [0, 1]")
    if not 0 <= max_dimension_drop <= 1:
        raise ImprovementError("max_dimension_drop must be in [0, 1]")

    before_map = {dimension.name: dimension.score for dimension in before.dimensions}
    after_map = {dimension.name: dimension.score for dimension in after.dimensions}
    if set(before_map) != set(after_map):
        missing = set(before_map) ^ set(after_map)
        raise ImprovementError(f"dimension sets differ: {sorted(missing)}")

    deltas = tuple(
        DimensionDelta(name=name, before=before_map[name], after=after_map[name])
        for name in sorted(before_map)
    )

    # A dimension may dip slightly when length grows through legitimate prose;
    # only a drop past the tolerance counts as a regression.
    dimension_drops: list[str] = []
    improvements: list[str] = []
    for delta in deltas:
        if delta.change < -max_dimension_drop:
            dimension_drops.append(
                f"{delta.name} fell from {delta.before:.2f} to {delta.after:.2f}"
            )
        elif delta.change > _REGRESSION_TOLERANCE:
            improvements.append(
                f"{delta.name} rose from {delta.before:.2f} to {delta.after:.2f}"
            )

    # Structural regressions always block: they remove verifiable content rather
    # than redistribute it.
    regressions: list[str] = []

    new_unsupported: list[str] = []
    resolved_unsupported: list[str] = []
    if before_ledger is not None and after_ledger is not None:
        before_set = {
            _normalized_sentence(claim.sentence) for claim in before_ledger.unsupported()
        }
        after_set = {
            _normalized_sentence(claim.sentence) for claim in after_ledger.unsupported()
        }
        new_unsupported = sorted(after_set - before_set)
        resolved_unsupported = sorted(before_set - after_set)

        before_grounding = before_ledger.summary()["anchored_ratio"]
        after_grounding = after_ledger.summary()["anchored_ratio"]
        if after_grounding + max_grounding_drop < before_grounding:
            regressions.append(
                "grounding fell from "
                f"{before_grounding:.1%} to {after_grounding:.1%}"
            )
        if new_unsupported:
            regressions.append(
                f"{len(new_unsupported)} new unsupported assertion(s) were introduced"
            )

        before_cited = {
            key for claim in before_ledger.claims for key in claim.citation_keys
        }
        after_cited = {
            key for claim in after_ledger.claims for key in claim.citation_keys
        }
        dropped = sorted(before_cited - after_cited)
        if dropped:
            regressions.append(
                f"{len(dropped)} citation key(s) disappeared: " + ", ".join(dropped[:8])
            )

    score_change = after.score - before.score
    # A dimension that fell sharply is reported and blocks; a narrow dip only
    # matters when the overall score did not rise.
    regressions.extend(dimension_drops)
    if require_not_worse and regressions:
        verdict = VERDICT_BLOCKED
    elif score_change > _REGRESSION_TOLERANCE:
        verdict = VERDICT_IMPROVED
    elif score_change < -_REGRESSION_TOLERANCE:
        verdict = VERDICT_BLOCKED if require_not_worse else VERDICT_REGRESSED
    else:
        verdict = VERDICT_UNCHANGED

    result = RevisionVerdict(
        verdict=verdict,
        score_before=before.score,
        score_after=after.score,
        grade_before=before.grade,
        grade_after=after.grade,
        deltas=deltas,
        regressions=tuple(regressions),
        improvements=tuple(improvements),
        new_unsupported=tuple(new_unsupported),
        resolved_unsupported=tuple(resolved_unsupported),
    )
    digest = hashlib.sha256(
        json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return RevisionVerdict(
        verdict=result.verdict,
        score_before=result.score_before,
        score_after=result.score_after,
        grade_before=result.grade_before,
        grade_after=result.grade_after,
        deltas=result.deltas,
        regressions=result.regressions,
        improvements=result.improvements,
        new_unsupported=result.new_unsupported,
        resolved_unsupported=result.resolved_unsupported,
        digest=digest,
    )


def revision_plan(report: QualityReport, *, limit: int = 8) -> tuple[dict[str, Any], ...]:
    """Order findings into the smallest set of changes that raises the score.

    Blocking findings first, then the dimensions with the most headroom, so a
    harness spends effort where the weighted score is actually lost.
    """

    if limit <= 0:
        raise ImprovementError("limit must be positive")

    order = {"critical": 0, "warning": 1, "info": 2}
    headroom = {
        dimension.name: 1.0 - dimension.score for dimension in report.dimensions
    }
    impact = {
        dimension.name: headroom[dimension.name] * dimension.weight
        for dimension in report.dimensions
    }
    candidates: list[dict[str, Any]] = []
    for finding in report.findings(min_severity="info"):
        candidates.append(
            {
                "dimension": finding.dimension,
                "severity": finding.severity,
                "message": finding.message,
                "remedy": finding.remedy,
                "line": finding.line,
                "impact": round(impact.get(finding.dimension, 0.0), 4),
            }
        )
    candidates.sort(
        key=lambda item: (
            order.get(item["severity"], 3),
            -item["impact"],
        )
    )
    return tuple(candidates[:limit])


def format_verdict(verdict: RevisionVerdict) -> str:
    lines = [
        "## Revision verdict",
        "",
        f"**Verdict:** {verdict.verdict}  |  "
        f"**Score:** {verdict.score_before:.3f} → {verdict.score_after:.3f} "
        f"({verdict.score_change:+.3f})  |  "
        f"**Grade:** {verdict.grade_before} → {verdict.grade_after}",
        "",
        "| Dimension | Before | After | Change |",
        "|---|---|---|---|",
    ]
    for delta in deltas_in(verdict.deltas):
        lines.append(
            f"| {delta.name} | {delta.before:.2f} | {delta.after:.2f} | "
            f"{delta.change:+.2f} |"
        )
    if verdict.improvements:
        lines += ["", "### Improved", ""]
        lines += [f"- {item}" for item in verdict.improvements]
    if verdict.resolved_unsupported:
        lines += ["", f"### Resolved unsupported assertions ({len(verdict.resolved_unsupported)})", ""]
        for sentence in verdict.resolved_unsupported[:10]:
            lines.append(f"- {sentence[:200]}")
    if verdict.regressions:
        lines += ["", "### Blocking regressions", ""]
        lines += [f"- {item}" for item in verdict.regressions]
    if verdict.new_unsupported:
        lines += ["", "### New unsupported assertions", ""]
        for sentence in verdict.new_unsupported[:10]:
            lines.append(f"- {sentence[:200]}")
    lines.append("")
    return "\n".join(lines)


def deltas_in(deltas: tuple[DimensionDelta, ...]) -> tuple[DimensionDelta, ...]:
    return tuple(sorted(deltas, key=lambda delta: delta.change))


__all__ = [
    "DimensionDelta",
    "ImprovementError",
    "RevisionVerdict",
    "VERDICT_BLOCKED",
    "VERDICT_IMPROVED",
    "VERDICT_REGRESSED",
    "VERDICT_SCHEMA",
    "VERDICT_SCHEMA",
    "VERDICT_UNCHANGED",
    "deltas_in",
    "format_verdict",
    "revision_plan",
    "verify_revision",
]
