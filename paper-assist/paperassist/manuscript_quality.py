"""Deterministic manuscript quality scoring.

Reviewers reject manuscripts for a small set of recurring, measurable reasons:
the abstract does not state results, the method section does not describe the
search or sampling, no limitations are discussed, claims are not traceable, and
the reference list is thinner than the evidence corpus. This module converts
those reasons into dimensions computed directly from the LaTeX source, the
claim ledger and the corpus binding.

Scoring is intentionally conservative: each dimension returns a value in
``[0, 1]`` with the raw measurements that produced it, so a reader can contest
the weighting rather than the facts. Nothing here calls a model.
"""

from __future__ import annotations

# The implementation lives in the ``quality`` package, one module per group of
# dimensions; this module keeps the public import path stable.
from .quality._base import (
    DEFAULT_WEIGHTS,
    GRADE_BANDS,
    GRADE_SCHEMA,
    QUALITY_SCHEMA,
    Dimension,
    Finding,
    QualityError,
    QualityReport,
)
from .quality.scoring import format_quality_report, score_manuscript

__all__ = [
    "DEFAULT_WEIGHTS",
    "Dimension",
    "Finding",
    "GRADE_BANDS",
    "GRADE_SCHEMA",
    "QUALITY_SCHEMA",
    "QualityError",
    "QualityReport",
    "format_quality_report",
    "score_manuscript",
]
