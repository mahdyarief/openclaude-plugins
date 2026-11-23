"""Shared constants, result types and LaTeX section parsing for quality scoring."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

QUALITY_SCHEMA = "paperassist.manuscript-quality/v1"


GRADE_SCHEMA = "paperassist.quality-grade/v1"


# Weights sum to 1.0. Provenance and evidence carry the largest share because
# they are the dimensions a reviewer cannot verify without the underlying data.
# Declarations and references are what an editor checks before sending a paper
# to review (ICMJE/COPE disclosure, publisher declarations, reference quality).
DEFAULT_WEIGHTS: dict[str, float] = {
    "structure": 0.07,
    "abstract": 0.09,
    "depth": 0.08,
    "citations": 0.09,
    "provenance": 0.18,
    "evidence": 0.13,
    "method_rigour": 0.12,
    "limitations": 0.05,
    "declarations": 0.04,
    "references": 0.04,
    "prose_style": 0.03,
    "tables_figures": 0.03,
    "readability": 0.03,
    "formulaic_prose": 0.02,
}


GRADE_BANDS: tuple[tuple[str, float], ...] = (
    ("A", 0.85),
    ("B", 0.72),
    ("C", 0.58),
    ("D", 0.40),
    ("E", 0.0),
)


_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "abstract": ("abstract", "abstrak"),
    "introduction": ("introduction", "pendahuluan"),
    "related": (
        "related work",
        "literature",
        "tinjauan",
        "state of the art",
        "landasan teori",
        "kajian teori",
        "kajian pustaka",
        "theoretical framework",
    ),
    "method": (
        "method",
        "metode",
        # "Metodologi Penelitian", the usual BAB III title, contains neither
        # "metode" nor "methodology".
        "metodologi",
        "materials and methods",
        "methodology",
        "experimental setup",
        "experimental design",
        "experiment setup",
        "research design",
        "desain penelitian",
        "rancangan penelitian",
    ),
    "results": ("result", "hasil", "findings", "temuan", "pengujian"),
    "discussion": ("discussion", "pembahasan", "diskusi"),
    "conclusion": ("conclusion", "kesimpulan", "simpulan", "penutup", "closing"),
    "limitations": ("limitation", "keterbatasan", "threats to validity"),
    "background": ("background", "latar belakang"),
}


_SECTION_RE = re.compile(
    r"\\(part|chapter|section|subsection|subsubsection)\*?\s*\{([^{}]*)\}"
)


_ABSTRACT_RE = re.compile(
    r"\\begin\{abstract\}(.*?)\\end\{abstract\}", re.DOTALL | re.IGNORECASE
)


# A tabular is the body of a table float, not a float of its own. Counting it
# alongside ``table`` would double every table in the manuscript and then
# report a caption shortage that does not exist.
_TABLE_RE = re.compile(r"\\begin\{(table\*?|longtable)\}", re.IGNORECASE)


_FIGURE_RE = re.compile(r"\\begin\{figure\*?\}", re.IGNORECASE)


_CAPTION_RE = re.compile(r"\\caption\s*\{")


_LABEL_RE = re.compile(r"\\label\s*\{([^{}]*)\}")


_REF_RE = re.compile(r"\\(?:ref|eqref|autoref|cref|Cref)\s*\{([^{}]*)\}")


_GRAPHICS_RE = re.compile(r"\\includegraphics\s*(?:\[[^\]]*\])?\s*\{([^{}]*)\}")


_BIBLIOGRAPHY_RE = re.compile(
    r"\\(?:bibliography|addbibresource)\s*(?:\[[^\]]*\])?\s*\{([^{}]*)\}"
)


_WORD_RE = re.compile(r"[A-Za-z\u00C0-\u024F0-9'’\-]+")


# House style rules apply to running prose only. A table cell that marks a
# missing value as ``---`` is not a dash in a sentence, and counting it as one
# would penalise every manuscript that uses the conventional placeholder.
_NON_PROSE_RE = re.compile(
    r"\\begin\{(?:tabular\*?|table\*?|longtable|verbatim|lstlisting|equation\*?|"
    r"align\*?|displaymath)\}.*?\\end\{(?:tabular\*?|table\*?|longtable|verbatim|"
    r"lstlisting|equation\*?|align\*?|displaymath)\}",
    re.DOTALL | re.IGNORECASE,
)


# House style forbids the em dash in running prose. A LaTeX em dash is ``---``
# or ``\textemdash{}``; the literal character is also caught.
_EM_DASH_RE = re.compile(r"(?<!-)---(?!-)|\\textemdash\b|\u2014")


_EN_DASH_RE = re.compile(r"(?<!-)--(?!-)|\u2013|\\textendash\b")


# An en dash between digits is a numeric range, which is allowed.
_NUMERIC_RANGE_RE = re.compile(r"(?<=\d)\s*(?:--|\\textendash\b|\u2013)\s*(?=\d)")


_REFERENCE_ITEM_RE = re.compile(r"\\bibitem(?:\[[^\]]*\])?\{([^{}]*)\}")


class QualityError(RuntimeError):
    pass


@dataclass(frozen=True)
class Finding:
    """A single actionable defect with a location and a remedy."""

    dimension: str
    severity: str
    message: str
    remedy: str
    line: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "severity": self.severity,
            "message": self.message,
            "remedy": self.remedy,
            "line": self.line,
        }


@dataclass(frozen=True)
class Dimension:
    name: str
    score: float
    weight: float
    measurements: Mapping[str, Any] = field(default_factory=dict)
    findings: tuple[Finding, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": round(self.score, 4),
            "weight": self.weight,
            "measurements": dict(self.measurements),
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass(frozen=True)
class QualityReport:
    dimensions: tuple[Dimension, ...] = ()
    paper_type: str = "review"
    research_design: str = ""
    document_kind: str = "article"
    score: float = 0.0
    grade: str = "E"
    recommendation: str = "reject"
    worst_dimensions: tuple[str, ...] = ()
    digest: str = ""
    source_sha256: str = ""

    def dimension(self, name: str) -> Dimension | None:
        for dimension in self.dimensions:
            if dimension.name == name:
                return dimension
        return None

    def findings(self, *, min_severity: str = "info") -> tuple[Finding, ...]:
        order = {"info": 0, "warning": 1, "critical": 2}
        floor = order.get(min_severity, 0)
        selected = [
            finding
            for dimension in self.dimensions
            for finding in dimension.findings
            if order.get(finding.severity, 0) >= floor
        ]
        return tuple(
            sorted(
                selected,
                key=lambda f: (-order.get(f.severity, 0), f.dimension, f.line or 0),
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": QUALITY_SCHEMA,
            "grade_schema": GRADE_SCHEMA,
            "digest": self.digest,
            "source_sha256": self.source_sha256,
            "paper_type": self.paper_type,
            "research_design": self.research_design,
            "document_kind": self.document_kind,
            "score": round(self.score, 4),
            "grade": self.grade,
            "recommendation": self.recommendation,
            "worst_dimensions": list(self.worst_dimensions),
            "dimensions": [dimension.to_dict() for dimension in self.dimensions],
        }


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _count_words(text: str) -> int:
    return len(_WORD_RE.findall(text))


def _strip_latex(text: str) -> str:
    text = re.sub(r"(?<!\\)%.*$", " ", text, flags=re.M)
    text = re.sub(r"\\[a-zA-Z@]+\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})?", " ", text)
    text = re.sub(r"[{}$&_^~]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _section_kinds(title: str) -> tuple[str, ...]:
    """Every kind a heading names.

    A combined heading is common: "Hasil dan Pembahasan" is the standard
    Indonesian journal section and "Results and Discussion" its English twin.
    Returning only the first match would report a discussion as missing from
    every such paper.
    """

    lowered = title.lower()
    return tuple(
        candidate
        for candidate, aliases in _SECTION_ALIASES.items()
        if any(alias in lowered for alias in aliases)
    )


def _section_kind(title: str) -> str | None:
    kinds = _section_kinds(title)
    return kinds[0] if kinds else None


def _heading_body(text: str, kind: str) -> str:
    """Body under any heading level that names ``kind``, up to the next heading.

    Used where a subsection is a legitimate home, such as a Limitations
    subsection inside the Discussion.
    """

    headings = list(_SECTION_RE.finditer(text))
    parts: list[str] = []
    for index, match in enumerate(headings):
        if kind not in _section_kinds(match.group(2).strip()):
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        parts.append(text[match.end():end])
    return _without_floats("\n".join(parts))


def _section_bodies(text: str) -> dict[str, str]:
    """Map a section kind to its body text, concatenating duplicates.

    A subsection belongs to the section it sits in. Ending a section's body at
    the next heading would drop every paragraph written under a subsection,
    so analysis would count for nothing precisely where it is most detailed.
    Only a heading that opens a different recognised kind ends the current body.

    A table float is not running prose. A catalogue of studies sits inside
    whatever section precedes it, and counting its rows as analysis would let a
    reference list inflate the depth score of a review that argues nothing. The
    same applies to an appendix, which is not one of the paper's argument
    sections even when its title contains a recognised word.
    """

    entries = list(_SECTION_RE.finditer(text))
    bodies: dict[str, list[str]] = {}
    current: tuple[str, ...] = ()
    start = 0
    # In a thesis a \section is a subsection of its \chapter: "3.1 Data" sits
    # inside "BAB III Metodologi" and must not cut the chapter's body short.
    nested_levels: tuple[str, ...] = ("subsection", "subsubsection")
    if any(match.group(1).lower() == "chapter" for match in entries):
        nested_levels = ("section", "subsection", "subsubsection")

    def close(end: int) -> None:
        for kind in current:
            bodies.setdefault(kind, []).append(text[start:end])

    for match in entries:
        # A subsection heading never closes the section around it, even when its
        # title happens to contain a word such as "limitations": that paragraph
        # still argues the discussion it sits in.
        if match.group(1).lower() in nested_levels:
            continue
        kinds = _section_kinds(match.group(2).strip())
        # An unrecognised top-level heading opens a new part of the document,
        # so it closes the section before it. Otherwise an appendix would be
        # counted as the conclusion's own prose.
        close(match.start())
        current = kinds
        start = match.end()
    close(len(text))
    return {
        kind: _without_floats("\n".join(parts)) for kind, parts in bodies.items()
    }


def _without_floats(text: str) -> str:
    """Remove table and figure environments, keeping paragraph text.

    The body of a section is what its author argues. Tabular rows and figure
    captions are evidence placed inside it, and counting their cells as prose
    would reward a paper for the size of its appendix rather than its analysis.
    """

    return re.sub(
        r"\\begin\{(table\*?|longtable|figure\*?|tabular\*?)\}.*?"
        r"\\end\{\1\}",
        " ",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )


def _grade(score: float) -> tuple[str, str]:
    grade = "E"
    for label, threshold in GRADE_BANDS:
        if score >= threshold:
            grade = label
            break
    if score >= GRADE_BANDS[0][1]:
        recommendation = "accept"
    elif score >= GRADE_BANDS[1][1]:
        recommendation = "minor revision"
    elif score >= GRADE_BANDS[2][1]:
        recommendation = "major revision"
    else:
        recommendation = "reject"
    return grade, recommendation
