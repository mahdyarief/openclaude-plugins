"""Structure, abstract and depth dimensions: is the paper complete and substantive?"""

from __future__ import annotations

import re
from typing import Any

from ..thesis_checks import ThesisCheck
from ._base import (
    _ABSTRACT_RE,
    DEFAULT_WEIGHTS,
    Dimension,
    Finding,
    _clamp,
    _count_words,
    _section_bodies,
    _strip_latex,
)

# Analytic prose a review needs per included study before it can report what
# each one contributed. Twenty five words is roughly two substantive sentences:
# enough for a design, a method and a reported result, which is the minimum a
# synthesis entry carries. Used only when the corpus size is known.
_STUDY_WORDS = 25


# Thesis checks that cost the structure score: Chapter 1, research questions
# against objectives and conclusions, their trace through the chapters, and
# the two abstracts.
_STRUCTURAL_CHECKS = ("chapter_one", "alignment", "trace", "abstract")


def _dimension_structure(
    text: str, *, depth_target: int, thesis: ThesisCheck | None = None
) -> Dimension:
    bodies = _section_bodies(text)
    required: tuple[str, ...] = ("introduction", "method", "results", "discussion", "conclusion")
    if thesis is not None and thesis.stage == "proposal":
        # A proposal is Chapters 1-3: the problem, the literature and the plan.
        required = ("introduction", "related", "method")
    present = [name for name in required if name in bodies]
    findings: list[Finding] = []
    for name in required:
        if name not in bodies:
            findings.append(
                Finding(
                    dimension="structure",
                    severity="critical",
                    message=f"missing required section: {name}",
                    remedy=f"add a {name} section with its own content, not a pointer",
                )
            )
    word_counts = {
        name: _count_words(_strip_latex(body)) for name, body in bodies.items()
    }
    thin = [
        name
        for name, count in word_counts.items()
        if name in required and count < depth_target // 3
    ]
    for name in thin:
        findings.append(
            Finding(
                dimension="structure",
                severity="warning",
                message=f"section '{name}' is thin ({word_counts[name]} words)",
                remedy=(
                    f"expand '{name}' to at least {depth_target // 3} words "
                    "with concrete content"
                ),
            )
        )
    score = len(present) / len(required)
    if thin:
        score *= 0.85
    measurements: dict[str, Any] = {
        "required_sections": list(required),
        "present_sections": present,
        "section_words": word_counts,
    }
    if thesis is not None:
        # Chapter 1 elements and question-objective-conclusion alignment cost a
        # little each; layout and length against the campus profile are advice.
        structural = [
            i for i in thesis.issues
            if i.check in _STRUCTURAL_CHECKS and i.severity != "info"
        ]
        score *= max(0.7, 1 - 0.05 * len(structural))
        findings.extend(
            Finding(
                dimension="structure",
                severity=issue.severity,
                message=issue.message,
                remedy=issue.remedy,
            )
            for issue in thesis.issues
            if issue.check in (*_STRUCTURAL_CHECKS, "layout", "length")
        )
        measurements["thesis"] = {
            key: value
            for key, value in thesis.to_dict().items()
            if key in ("profile_id", "stage", "chapters", "chapter_one", "alignment",
                       "trace", "abstracts", "layout_mismatches", "words", "word_range")
        }
    return Dimension(
        name="structure",
        score=_clamp(score),
        weight=DEFAULT_WEIGHTS["structure"],
        measurements=measurements,
        findings=tuple(findings),
    )


_ABSTRACT_HEADING_RE = re.compile(
    r"\\(?:chapter|section)\*?\s*\{\s*(?:abstrak|abstract|intisari|ringkasan)\s*\}",
    re.IGNORECASE,
)
_NEXT_HEADING_RE = re.compile(
    r"\\(?:part|chapter|section|tableofcontents|listoffigures|listoftables|mainmatter)\b"
)


def _abstract_body(text: str) -> str | None:
    """The abstract: its environment, or the first chapter or section titled
    Abstrak/Abstract/Intisari (thesis front matter) when the environment is
    missing or holds only comments."""

    match = _ABSTRACT_RE.search(text)
    if match and _strip_latex(match.group(1)):
        return match.group(1)
    # A thesis carries an Abstrak and an Abstract; the first one with prose
    # is the abstract, an empty placeholder page is not.
    first: str | None = None
    for heading in _ABSTRACT_HEADING_RE.finditer(text):
        rest = text[heading.end():]
        stop = _NEXT_HEADING_RE.search(rest)
        body = rest[: stop.start()] if stop else rest
        if _strip_latex(body):
            return body
        first = body if first is None else first
    if match:
        return match.group(1)
    return first


def _dimension_abstract(
    text: str, *, thesis: bool = False, required: bool = True
) -> Dimension:
    body_text = _abstract_body(text)
    findings: list[Finding] = []
    if not required and (body_text is None or not _strip_latex(body_text)):
        # A thesis proposal is usually submitted without an abstract.
        return Dimension(
            name="abstract",
            score=1.0,
            weight=DEFAULT_WEIGHTS["abstract"],
            measurements={"words": 0, "sections_covered": [], "required": False},
        )
    if body_text is None:
        findings.append(
            Finding(
                dimension="abstract",
                severity="critical",
                message="no abstract environment found",
                remedy=(
                    "wrap the summary in \\begin{abstract}...\\end{abstract}"
                    + (", or open a \\chapter*{Abstrak}" if thesis else "")
                ),
            )
        )
        return Dimension(
            name="abstract",
            score=0.0,
            weight=DEFAULT_WEIGHTS["abstract"],
            measurements={"words": 0, "sections_covered": []},
            findings=tuple(findings),
        )

    body = body_text
    words = _count_words(_strip_latex(body))
    lowered = body.lower()
    checks = {
        "objective": r"tujuan|kajian ini|this (?:study|review|paper)|we (?:review|examine|map)",
        "scope": r"studi|records|articles|basis data|database|rentang|20\d\d",
        "method": (
            r"prisma|scoping|sistemati|systematic|pencarian|search|metode|method"
            r"|pendekatan|approach|eksperimen|experiment|survei|survey|wawancara|interview"
        ),
        "result": r"hasil|menunjukkan|menemukan|found|show|reveal|score|skor",
        "conclusion": r"kesimpulan|rekomendasi|recommend|menyimpulkan|conclude",
    }
    covered = [name for name, pattern in checks.items() if re.search(pattern, lowered)]
    score = len(covered) / len(checks)
    if words < 120:
        score *= 0.7
        findings.append(
            Finding(
                dimension="abstract",
                severity="warning",
                message=f"abstract is short ({words} words)",
                remedy=(
                    "state objective, scope, method, results and conclusion in "
                    "about 150-250 words"
                ),
            )
        )
    # A thesis abstract may fill a page; campus guides cap it near 500 words.
    if words > (600 if thesis else 400):
        findings.append(
            Finding(
                dimension="abstract",
                severity="warning",
                message=f"abstract is long ({words} words)",
                remedy=(
                    "keep it to one page, as campus guides ask"
                    if thesis
                    else "move detail into the body; editors often trim abstracts over 300 words"
                ),
            )
        )
    for name in checks:
        if name not in covered:
            findings.append(
                Finding(
                    dimension="abstract",
                    severity="warning" if name == "result" else "info",
                    message=f"abstract does not state {name}",
                    remedy=f"add one sentence covering {name}",
                )
            )
    return Dimension(
        name="abstract",
        score=_clamp(score),
        weight=DEFAULT_WEIGHTS["abstract"],
        measurements={"words": words, "sections_covered": covered},
        findings=tuple(findings),
    )


def _dimension_depth(
    text: str, *, depth_target: int, corpus_size: int = 0
) -> Dimension:
    bodies = _section_bodies(text)
    words = {name: _count_words(_strip_latex(body)) for name, body in bodies.items()}
    findings: list[Finding] = []
    thin = sorted(
        (name for name, count in words.items() if count < depth_target),
        key=lambda name: words[name],
    )
    for name in thin[:6]:
        findings.append(
            Finding(
                dimension="depth",
                severity="warning",
                message=f"section '{name}' has {words[name]} words, target is {depth_target}",
                remedy="add analysis rather than restating; each paragraph should carry a claim",
            )
        )
    graded = [
        name
        for name in words
        if name in {"introduction", "method", "results", "discussion", "conclusion"}
    ]
    if not graded:
        return Dimension(
            name="depth",
            score=0.0,
            weight=DEFAULT_WEIGHTS["depth"],
            measurements={"section_words": words},
            findings=tuple(findings),
        )
    ratio = sum(min(1.0, words[name] / depth_target) for name in graded) / len(graded)

    # A review earns its length by synthesising its corpus. Below a floor of
    # analysis per included study the prose cannot carry a per-study finding, and
    # a hundred-study review that fits in a handful of pages has not reported
    # what it read. The floor is a judgement about reporting, not about writing
    # style, so it is stated here as a constant rather than tuned per project.
    measurements: dict[str, Any] = {
        "section_words": words,
        "depth_target": depth_target,
        "total_words": sum(words.values()),
    }
    if corpus_size > 0:
        synthesised = sum(words[name] for name in graded)
        required = max(depth_target * len(graded), _STUDY_WORDS * corpus_size)
        ratio = min(ratio, min(1.0, synthesised / required))
        measurements.update(
            {
                "corpus_records": corpus_size,
                "synthesis_words": synthesised,
                "synthesis_target": required,
            }
        )
        if synthesised < required:
            findings.append(
                Finding(
                    dimension="depth",
                    severity="critical" if synthesised < required * 0.5 else "warning",
                    message=(
                        f"analytic sections carry {synthesised} words for {corpus_size} "
                        f"included studies; the floor is about {required}"
                    ),
                    remedy=(
                        "report what each study contributed: characteristics, method, "
                        "reported performance and limitations; aggregate counts alone "
                        "do not account for the corpus"
                    ),
                )
            )
    return Dimension(
        name="depth",
        score=_clamp(ratio),
        weight=DEFAULT_WEIGHTS["depth"],
        measurements=measurements,
        findings=tuple(findings),
    )
