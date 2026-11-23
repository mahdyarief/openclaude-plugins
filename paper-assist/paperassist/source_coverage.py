"""Audit whether a journal manuscript covers its research source.

A journal paper is not written from nothing. It is distilled from a longer
research source: a thesis chapter, a drafted report, a data appendix. The
journal format drops detail on purpose, but it must not drop a result, a
limitation or a comparison the source established. Nothing in a typeset
manuscript reveals what was left behind, so the loss stays invisible until a
reviewer asks about it.

This module compares the two texts deterministically. It reads the source
headings and the numbers each one asserts, then checks whether the journal
manuscript still carries them. It is a coverage check, not a similarity check:
rewriting is expected and fine, omission is what it looks for. Only numbers are
compared, because prose paraphrases and a number does not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "CoverageError",
    "SectionFinding",
    "SourceSection",
    "SourceCoverage",
    "audit_source_coverage",
    "format_source_coverage",
]


class CoverageError(ValueError):
    """Raised when the coverage audit cannot be performed on its inputs."""


# A heading in Markdown or in LaTeX. The source is usually Markdown, but a
# source that is itself LaTeX should not need a second code path.
_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.MULTILINE)
_TEX_HEADING_RE = re.compile(
    r"\\(?:section|subsection|subsubsection)\*?\s*\{([^{}]*)\}", re.IGNORECASE
)

# Numbers a source asserts: grouped integers, decimals and percentages.
_NUMBER_RE = re.compile(
    r"(?<![\w.])(\d{1,3}(?:\.\d{3})+|\d+(?:[.,]\d+)?\s?%?)(?![\w])"
)

# A bibliography is not an argument section: its numbers are DOIs, volumes,
# page ranges and years, so treating them as assertions produces hundreds of
# phantom gaps. The section is dropped before any comparison runs.
_REFERENCE_SECTION_RE = re.compile(
    r"^(?:referensi|references?|bibliography|daftar\s+pustaka|rujukan|"
    r"literatur|works\s+cited)\b",
    re.IGNORECASE,
)

# Identifiers are not findings either. DOIs, ISBNs, arXiv ids and long opaque
# digit runs would otherwise enter the unaccounted list and drown the handful
# of measurements a reviewer actually needs to check.
_IDENTIFIER_RE = re.compile(
    r"(?:https?://)?(?:dx\.)?doi\.org/\S+"
    r"|\bdoi\s*:\s*\S+"
    r"|\b10\.\d{4,9}/\S+"
    r"|\bISBN[:\s-]*[\dXx][\dXx-]{8,}"
    r"|\barxiv\s*:\s*\d{4}\.\d{4,5}"
    r"|\b\d{9,}\b",
    re.IGNORECASE,
)

_STOPWORDS = frozenset(
    ["a", "an", "the", "of", "and", "or", "for", "to", "in", "on", "at", "by", "with", "from", "as", "is", "are", "was", "were", "be", "dan", "atau", "yang", "untuk", "pada", "dengan", "dari", "ke", "di", "ini", "itu"]
)


@dataclass(frozen=True)
class SourceSection:
    """One titled part of the research source and what it asserts."""

    title: str
    level: int
    numbers: tuple[str, ...]
    words: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "level": self.level,
            "numbers": list(self.numbers),
            "words": self.words,
        }


@dataclass(frozen=True)
class SectionFinding:
    """A source section that did not fully survive into the manuscript."""

    section: str
    status: str
    message: str
    expected_numbers: tuple[str, ...]
    found_numbers: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "section": self.section,
            "status": self.status,
            "message": self.message,
            "expected_numbers": list(self.expected_numbers),
            "found_numbers": list(self.found_numbers),
        }


@dataclass
class SourceCoverage:
    """The result of comparing a source manuscript with a journal manuscript."""

    sections: tuple[SourceSection, ...] = ()
    covered: tuple[str, ...] = ()
    findings: tuple[SectionFinding, ...] = ()
    unaccounted_numbers: tuple[str, ...] = ()
    source_words: int = 0
    manuscript_words: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def missing(self) -> tuple[SectionFinding, ...]:
        return tuple(item for item in self.findings if item.status == "missing")

    @property
    def partial(self) -> tuple[SectionFinding, ...]:
        return tuple(item for item in self.findings if item.status == "partial")

    @property
    def covered_count(self) -> int:
        return len(self.covered)

    @property
    def partial_count(self) -> int:
        return sum(1 for item in self.findings if item.status == "partial")

    @property
    def missing_count(self) -> int:
        return sum(1 for item in self.findings if item.status == "missing")

    @property
    def unaccounted_count(self) -> int:
        return len(self.unaccounted_numbers)

    @property
    def passed(self) -> bool:
        """A manuscript passes when no source section vanished entirely."""

        return self.missing_count == 0 and self.covered_count > 0

    @property
    def coverage_ratio(self) -> float:
        total = self.covered_count + len(self.findings)
        if not total:
            return 1.0
        return (self.covered_count + 0.5 * self.partial_count) / total

    def to_dict(self) -> dict[str, Any]:
        return {
            "sections": [section.to_dict() for section in self.sections],
            "covered": list(self.covered),
            "findings": [finding.to_dict() for finding in self.findings],
            "unaccounted_numbers": list(self.unaccounted_numbers),
            "source_words": self.source_words,
            "manuscript_words": self.manuscript_words,
            "coverage_ratio": round(self.coverage_ratio, 4),
            "passed": self.passed,
            "notes": list(self.notes),
        }


def _normalise(value: str) -> str:
    return " ".join(re.findall(r"[0-9A-Za-z\u00C0-\u024F]+", value.lower()))


def _tokens(value: str) -> list[str]:
    return [word for word in _normalise(value).split() if word not in _STOPWORDS]


def _numbers_in(text: str, *, minimum: float = 10.0) -> tuple[str, ...]:
    """Return the substantial numbers a passage asserts, in order of appearance.

    Small integers are dropped: "three axes" and "section 2" are organisation,
    not findings, and requiring them downstream would bury the real omissions.
    A decimal or a percentage is always kept because both are measurements, and
    they are compared with their sign stripped so "18%" and "18,2%" can still be
    matched across a rewording.
    """

    found: list[str] = []
    text = _IDENTIFIER_RE.sub(" ", text)
    for match in _NUMBER_RE.finditer(text):
        token = " ".join(match.group(1).split())
        key = token.rstrip(" %").replace(",", ".")
        if key in found:
            continue
        if "." not in key and "%" not in token:
            try:
                if float(key) < minimum:
                    continue
            except ValueError:
                continue
        found.append(key)
    return tuple(found)


def _extract_sections(text: str) -> list[tuple[str, int, str]]:
    """Split a source into (title, level, body) triples.

    Markdown headings define the parts when present. Otherwise LaTeX headings
    are used, so a source already in LaTeX is still comparable.
    """

    matches = [
        (match.start(), match.end(), len(match.group(1)), match.group(2).strip())
        for match in _MD_HEADING_RE.finditer(text)
    ]
    if not matches:
        matches = [
            (match.start(), match.end(), 2, match.group(1).strip())
            for match in _TEX_HEADING_RE.finditer(text)
        ]
    sections: list[tuple[str, int, str]] = []
    for index, (_, end, level, title) in enumerate(matches):
        stop = matches[index + 1][0] if index + 1 < len(matches) else len(text)
        sections.append((title, level, text[end:stop]))
    return sections


def _title_survives(title: str, manuscript_tokens: set[str]) -> bool:
    """Decide whether a source heading was carried over in some form.

    A journal rewords its headings, so exact wording is not required. A heading
    counts as surviving when most of its content words appear somewhere in the
    manuscript, or when every distinctive word does.
    """

    tokens = _tokens(title)
    if not tokens:
        return False
    hits = sum(1 for token in tokens if token in manuscript_tokens)
    if hits / len(tokens) >= 0.5:
        return True
    distinctive = [token for token in tokens if len(token) > 5]
    return bool(distinctive) and all(t in manuscript_tokens for t in distinctive)


def audit_source_coverage(
    source_text: str,
    manuscript_text: str,
    *,
    min_section_words: int = 12,
) -> SourceCoverage:
    """Compare a research source against the journal manuscript built from it.

    Returns which source sections survived, which kept their title but lost at
    least one asserted number, and which vanished entirely, plus every source
    number that cannot be found anywhere in the manuscript. The last list is the
    one that catches a dropped result rather than a dropped heading.
    """

    if not source_text.strip():
        raise CoverageError("source text is empty")
    if not manuscript_text.strip():
        raise CoverageError("manuscript text is empty")

    manuscript_tokens = set(_tokens(manuscript_text))
    manuscript_numbers = set(_numbers_in(manuscript_text, minimum=0.0))

    sections: list[SourceSection] = []
    covered: list[str] = []
    findings: list[SectionFinding] = []
    unaccounted: list[str] = []

    for title, level, body in _extract_sections(source_text):
        # Bibliographies hold identifiers and volume/page numbers, not claims
        # about the review, so comparing them measures nothing.
        if _REFERENCE_SECTION_RE.match(title.strip()):
            continue
        words = len(body.split())
        # Skip tiny third-level headings: a stub like "### Examples" asserts no
        # result, so treating it as missing would produce noise.
        if words < min_section_words and level > 2:
            continue
        numbers = _numbers_in(body)
        sections.append(
            SourceSection(title=title, level=level, numbers=numbers, words=words)
        )

        lost = [number for number in numbers if number not in manuscript_numbers]
        for number in lost:
            if number not in unaccounted:
                unaccounted.append(number)

        survives = _title_survives(title, manuscript_tokens)
        if survives and not lost:
            covered.append(title)
            continue
        if survives:
            findings.append(
                SectionFinding(
                    section=title,
                    status="partial",
                    message=(
                        f"'{title}' survives but {len(lost)} asserted "
                        f"number(s) are absent from the manuscript"
                    ),
                    expected_numbers=tuple(numbers),
                    found_numbers=tuple(
                        n for n in numbers if n in manuscript_numbers
                    ),
                )
            )
        else:
            findings.append(
                SectionFinding(
                    section=title,
                    status="missing",
                    message=f"'{title}' does not appear in the manuscript",
                    expected_numbers=tuple(numbers),
                    found_numbers=(),
                )
            )

    notes: list[str] = []
    if not sections:
        notes.append("the source has no headings, so only numbers were compared")

    return SourceCoverage(
        sections=tuple(sections),
        covered=tuple(covered),
        findings=tuple(findings),
        unaccounted_numbers=tuple(unaccounted),
        source_words=len(source_text.split()),
        manuscript_words=len(manuscript_text.split()),
        notes=tuple(notes),
    )


def format_source_coverage(coverage: SourceCoverage) -> str:
    """Render the audit as markdown for a human reviewer."""

    verdict = "PASS" if coverage.passed else "FAIL"
    lines = [
        "# Source coverage",
        "",
        f"- verdict: **{verdict}**",
        f"- coverage ratio: {coverage.coverage_ratio:.1%}",
        f"- sections: {coverage.covered_count} covered, "
        f"{coverage.partial_count} partial, {coverage.missing_count} missing",
        f"- numbers in the source but absent from the manuscript: "
        f"{coverage.unaccounted_count}",
        f"- words: source {coverage.source_words}, manuscript "
        f"{coverage.manuscript_words}",
        "",
    ]
    for note in coverage.notes:
        lines.append(f"> {note}")
    if coverage.notes:
        lines.append("")
    lines += ["## Covered", ""]
    for title in coverage.covered:
        lines.append(f"- {title}")
    lines += ["", "## Needs attention", ""]
    for finding in coverage.findings:
        lines.append(f"- [{finding.status}] {finding.message}")
        if finding.expected_numbers:
            lines.append(
                f"  - expected: {', '.join(finding.expected_numbers)}"
            )
            if finding.found_numbers:
                lines.append(f"  - present: {', '.join(finding.found_numbers)}")
    if coverage.unaccounted_numbers:
        lines += ["", "## Numbers not found in the manuscript", ""]
        for number in coverage.unaccounted_numbers:
            lines.append(f"- {number}")
    lines.append("")
    return "\n".join(lines)
