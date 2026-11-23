"""Presentation dimensions: formulaic prose, tables and figures, dashes, readability."""

from __future__ import annotations

import re

from ..anti_ai_style import detect_formulaic_phrases, is_uniform_rhythm, sentence_length_cv
from ._base import (
    _ABSTRACT_RE,
    _CAPTION_RE,
    _EM_DASH_RE,
    _EN_DASH_RE,
    _FIGURE_RE,
    _GRAPHICS_RE,
    _LABEL_RE,
    _NON_PROSE_RE,
    _NUMERIC_RANGE_RE,
    _REF_RE,
    _SECTION_RE,
    _TABLE_RE,
    DEFAULT_WEIGHTS,
    Dimension,
    Finding,
    _clamp,
    _count_words,
    _strip_latex,
)

_HEADING_LABEL_RE = re.compile(
    r"\\(?:part|chapter|section|subsection|subsubsection)\*?\s*\{[^{}]*\}\s*"
    r"\\label\s*\{([^{}]*)\}"
)


def _dimension_formulaic_prose(text: str) -> Dimension:
    prose = _NON_PROSE_RE.sub(lambda m: " " * len(m.group(0)), text)
    prose = _ABSTRACT_RE.sub(lambda m: m.group(1), prose)
    prose = _SECTION_RE.sub(lambda m: " " * len(m.group(0)), prose)
    prose = _strip_latex(prose)

    hits = detect_formulaic_phrases(prose)
    rhythm_cv = sentence_length_cv(prose)
    uniform = is_uniform_rhythm(prose)
    findings: list[Finding] = []

    if hits:
        examples = ", ".join(f'“{hit.phrase}”' for hit in hits[:3])
        findings.append(
            Finding(
                dimension="formulaic_prose",
                severity="warning" if len(hits) < 4 else "critical",
                message=(
                    f"{len(hits)} formulaic phrase(s) for editorial review: {examples}"
                ),
                remedy=(
                    "replace only phrases that add no paper-specific meaning; "
                    "retain standard technical terminology"
                ),
            )
        )
    if uniform:
        findings.append(
            Finding(
                dimension="formulaic_prose",
                severity="info",
                message=(
                    "sentence lengths are unusually uniform "
                    f"(coefficient of variation {rhythm_cv:.2f})"
                ),
                remedy=(
                    "review sentence rhythm where it improves readability; "
                    "do not vary sentence length mechanically"
                ),
            )
        )

    score = _clamp(1.0 - min(0.6, len(hits) * 0.12) - (0.08 if uniform else 0.0))
    return Dimension(
        name="formulaic_prose",
        score=score,
        weight=DEFAULT_WEIGHTS["formulaic_prose"],
        measurements={
            "formulaic_phrase_count": len(hits),
            "formulaic_phrases": [hit.to_dict() for hit in hits],
            "sentence_length_cv": round(rhythm_cv, 4),
            "uniform_sentence_rhythm": uniform,
            "is_authorship_detector": False,
        },
        findings=tuple(findings),
    )


def _dimension_tables_figures(text: str, *, asset_root: str | None = None) -> Dimension:
    findings: list[Finding] = []
    tables = len(_TABLE_RE.findall(text))
    figures = len(_FIGURE_RE.findall(text))
    captions = len(_CAPTION_RE.findall(text))
    # A label right after a heading (\chapter{Pendahuluan}\label{ch:...}) marks
    # a cross-reference target for the table of contents, not a float; leaving
    # it unreferenced is harmless and every thesis template does it.
    heading_labels = set(_HEADING_LABEL_RE.findall(text))
    labels = set(_LABEL_RE.findall(text)) - heading_labels
    refs = {
        part.strip()
        for group in _REF_RE.findall(text)
        for part in group.split(",")
        if part.strip()
    }
    floats = tables + figures
    # A label nothing references is a defect whether or not other refs exist.
    unreferenced = sorted(labels - refs)
    for label in unreferenced[:8]:
        findings.append(
            Finding(
                dimension="tables_figures",
                severity="warning",
                message=f"label '{label}' is never referenced in the text",
                remedy="reference every table and figure with \\ref{} where it is discussed",
            )
        )
    if floats and captions < floats:
        findings.append(
            Finding(
                dimension="tables_figures",
                severity="warning",
                message=f"{floats} float(s) but only {captions} caption(s)",
                remedy="give every table and figure a self-contained caption",
            )
        )
    graphics = _GRAPHICS_RE.findall(text)
    missing = 0
    for path in graphics:
        candidates = (path, path + ".pdf", path + ".png", path + ".jpg")
        if not any(_exists(candidate, asset_root) for candidate in candidates):
            missing += 1
    if missing:
        findings.append(
            Finding(
                dimension="tables_figures",
                severity="warning",
                message=(
                    f"{missing} referenced graphic(s) not found relative to "
                    + ("the manuscript folder" if asset_root else "the working directory")
                ),
                remedy="confirm figure files ship with the submission",
            )
        )
    score = 0.0
    if floats:
        score = 0.5 + 0.5 * min(1.0, captions / floats)
        if refs:
            score *= 0.7 + 0.3 * (1 - len(unreferenced) / max(1, len(labels)))
    elif labels:
        score = 0.35
    return Dimension(
        name="tables_figures",
        score=_clamp(score),
        weight=DEFAULT_WEIGHTS["tables_figures"],
        measurements={
            "tables": tables,
            "figures": figures,
            "captions": captions,
            "labels": len(labels),
            "referenced_labels": len(refs & labels),
        },
        findings=tuple(findings),
    )


def _exists(path: str, asset_root: str | None = None) -> bool:
    """Whether a graphic exists, resolved like LaTeX: relative to the manuscript."""

    from pathlib import Path

    try:
        candidate = Path(path)
        if asset_root and not candidate.is_absolute():
            candidate = Path(asset_root) / candidate
        return candidate.exists()
    except (OSError, ValueError):
        return False


def _dimension_prose_style(text: str, *, allow_em_dash: bool = False) -> Dimension:
    """Enforce house prose style: no em dash, en dash only inside numeric ranges."""

    prose = _NON_PROSE_RE.sub(lambda m: " " * len(m.group(0)), text)
    prose = _ABSTRACT_RE.sub(lambda m: m.group(1), prose)
    prose = _SECTION_RE.sub(lambda m: " " * len(m.group(0)), prose)
    prose = _strip_latex(prose)

    findings: list[Finding] = []
    em_dashes = len(_EM_DASH_RE.findall(prose))
    ranges = len(_NUMERIC_RANGE_RE.findall(prose))
    en_dashes = max(0, len(_EN_DASH_RE.findall(prose)) - ranges)

    score = 1.0
    if em_dashes and not allow_em_dash:
        score -= min(0.8, em_dashes * 0.08)
        findings.append(
            Finding(
                dimension="prose_style",
                severity="warning" if em_dashes < 10 else "critical",
                message=f"{em_dashes} em dash(es) in running prose",
                remedy=(
                    "replace each em dash with a comma, a colon, or a full stop; "
                    "house style forbids the em dash"
                ),
            )
        )
    if en_dashes:
        score -= min(0.3, en_dashes * 0.04)
        findings.append(
            Finding(
                dimension="prose_style",
                severity="info",
                message=f"{en_dashes} en dash(es) outside a numeric range",
                remedy="use a hyphen for compounds and keep en dashes for ranges only",
            )
        )
    return Dimension(
        name="prose_style",
        score=_clamp(score),
        weight=DEFAULT_WEIGHTS["prose_style"],
        measurements={
            "em_dashes": em_dashes,
            "en_dashes_outside_ranges": en_dashes,
            "numeric_ranges": ranges,
            "em_dash_allowed": allow_em_dash,
            "prose_words": _count_words(prose),
        },
        findings=tuple(findings),
    )


def _dimension_readability(text: str) -> Dimension:
    sentences = [
        _count_words(s)
        for s in re.split(r"(?<=[.!?])\s+", _strip_latex(text))
        if _count_words(s) > 0
    ]
    findings: list[Finding] = []
    if not sentences:
        return Dimension(
            name="readability",
            score=0.0,
            weight=DEFAULT_WEIGHTS["readability"],
            measurements={"sentences": 0},
        )
    average = sum(sentences) / len(sentences)
    long_ratio = sum(1 for count in sentences if count > 45) / len(sentences)
    score = 1.0
    if average > 32:
        score -= min(0.35, (average - 32) / 60)
        findings.append(
            Finding(
                dimension="readability",
                severity="warning",
                message=f"average sentence length is {average:.1f} words",
                remedy="split sentences above 40 words; one claim per sentence",
            )
        )
    if long_ratio > 0.12:
        score -= min(0.25, long_ratio)
        findings.append(
            Finding(
                dimension="readability",
                severity="info",
                message=f"{long_ratio:.0%} of sentences exceed 45 words",
                remedy="break the longest sentences into claim plus support",
            )
        )
    return Dimension(
        name="readability",
        score=_clamp(score),
        weight=DEFAULT_WEIGHTS["readability"],
        measurements={
            "sentences": len(sentences),
            "average_words": round(average, 2),
            "long_sentence_ratio": round(long_ratio, 4),
        },
        findings=tuple(findings),
    )
