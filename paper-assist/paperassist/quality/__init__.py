"""Deterministic manuscript quality scoring, one module per group of dimensions."""

from .scoring import format_quality_report, score_manuscript

__all__ = ["format_quality_report", "score_manuscript"]
