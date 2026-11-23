"""Checks on the quantitative analyses common in Indonesian education research.

Reviewers of SINTA-indexed journals and thesis examiners reject the same three
slips again and again. Each check here is arithmetic or a presence test over
the manuscript text, never a judgement on the study:

* **N-gain** (Hake 1998): ``g = (post - pre) / (max - pre)``, categorised high
  for ``g > 0.7``, medium for ``0.3 <= g <= 0.7`` and low for ``g < 0.3``. A
  reported value whose stated category disagrees with those bounds is flagged,
  as is a value outside ``[0, 1]`` (or ``[0, 100]`` for a percentage).
* **Aiken's V** (Aiken 1985): ``V = sum(r - lo) / (n * (c - 1))`` lies in
  ``[0, 1]``. Its critical value depends on the number of raters ``n`` and of
  rating categories ``c``, so a manuscript that uses V must state both; the
  check asks for them instead of applying one fixed cut-off.
* **Prerequisite tests**: a t-test, ANOVA or ANCOVA assumes normality, and the
  between-group tests also homogeneity of variance. A manuscript that runs
  one without reporting the assumption test (Shapiro-Wilk, Kolmogorov-Smirnov,
  Lilliefors; Levene, Bartlett) or a robust alternative (Welch) is flagged.

Patterns accept English and Indonesian wording and decimal commas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

NGAIN_HIGH = 0.7
NGAIN_LOW = 0.3

_CATEGORY = {
    "tinggi": "high",
    "high": "high",
    "sedang": "medium",
    "medium": "medium",
    "moderate": "medium",
    "rendah": "low",
    "low": "low",
}

# Word-bounded: "domain gain" or "can gain" is not an N-gain.
_NGAIN_RE = re.compile(r"\bn[- ]?gain\b|normali[sz]ed gain|gain ternormalisasi", re.IGNORECASE)
_VALUE_CATEGORY_RE = re.compile(
    r"(?<![\d.,])(\d{1,3}(?:[.,]\d+)?)\s*(%|persen|percent)?"
    r"[^.\d;]{0,40}?\b(tinggi|sedang|rendah|high|medium|moderate|low)\b",
    re.IGNORECASE,
)
# The coefficient, not any author named Aiken in the reference list.
_AIKEN_RE = re.compile(
    r"aiken[’'`]?s?\s*v\b|indeks\s+(?:validitas\s+)?aiken|aiken[’'`]?s?\s+index"
    r"|(?:validitas isi|content validity)[^.]{0,80}aiken",
    re.IGNORECASE,
)
# Authors type "Aiken's", "Aiken’s" (curly apostrophe) or "Aiken"; values come
# singly ("V = 0,86") or as a range ("berkisar antara 0,64 hingga 0,73").
_AIKEN_VALUE_RE = re.compile(
    r"(?:aiken[’'`]?s?\s*v|\bv)\s*(?:=|sebesar|of|bernilai|value of)\s*(-?\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
_AIKEN_RANGE_RE = re.compile(
    r"aiken[^.]{0,80}?(?:berkisar antara|berkisar|ranged? from|range from|antara|between)\s*"
    r"(-?\d+(?:[.,]\d+)?)\s*(?:hingga|sampai|to|and|dan|-|–)\s*(-?\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
_NUMBER_WORDS = r"\d+|dua|tiga|empat|lima|enam|tujuh|delapan|sembilan|sepuluh|two|three|four|five|six|seven|eight|nine|ten"
_RATERS_RE = re.compile(
    rf"(?:{_NUMBER_WORDS})\s+(?:orang\s+)?(?:validator|ahli|pakar|expert|rater|penilai|judge)"
    rf"|(?:validator|rater|penilai|ahli)\s*\(?\s*n\s*=\s*\d+",
    re.IGNORECASE,
)
_CATEGORIES_RE = re.compile(
    rf"(?:skala|scale|likert|kategori penilaian|rating categories)[^.]{{0,40}}?(?:{_NUMBER_WORDS})"
    rf"|(?:{_NUMBER_WORDS})[- ](?:point|poin|skala|level|tingkat|kategori)",
    re.IGNORECASE,
)

_PARAMETRIC_RE = re.compile(
    r"\bt-?tests?\b|\buji[- ]t\b|\bpaired[- ]samples?\b|\bindependent[- ]samples?\b"
    r"|\banova\b|\bancova\b|\bmanova\b|\bt\s*\(\s*\d+\s*\)\s*=",
    re.IGNORECASE,
)
_BETWEEN_RE = re.compile(
    r"\bindependent[- ]samples?\b|\bindependent t\b|\buji[- ]t (?:dua sampel )?(?:independen|tidak berpasangan)"
    r"|\banova\b|\bancova\b|\bmanova\b|\bunpaired\b|kelas (?:eksperimen|kontrol)|control group|kelompok kontrol",
    re.IGNORECASE,
)
_NORMALITY_RE = re.compile(
    r"normalit|shapiro|kolmogorov|lilliefors|anderson[- ]darling|q-?q plot|normally distributed"
    r"|berdistribusi normal|skewness|kemencengan",
    re.IGNORECASE,
)
_HOMOGENEITY_RE = re.compile(
    r"homogen|levene|bartlett|brown[- ]forsythe|welch|equal variances?|kesamaan varians"
    r"|homosc?edastic|homosk?edastic|heterosc?edastic",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AnalysisIssue:
    check: str
    severity: str
    message: str
    remedy: str

    def to_dict(self) -> dict[str, str]:
        return {
            "check": self.check,
            "severity": self.severity,
            "message": self.message,
            "remedy": self.remedy,
        }


@dataclass(frozen=True)
class AnalysisCheck:
    applied: tuple[str, ...] = ()
    measurements: dict[str, Any] = field(default_factory=dict)
    issues: tuple[AnalysisIssue, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "applied": list(self.applied),
            "measurements": dict(self.measurements),
            "issues": [issue.to_dict() for issue in self.issues],
        }


def _number(raw: str) -> float:
    return float(raw.replace(",", "."))


def ngain_category(g: float) -> str:
    """Hake's category for a normalised gain ``g`` in ``[0, 1]``."""

    if g > NGAIN_HIGH:
        return "high"
    if g >= NGAIN_LOW:
        return "medium"
    return "low"


def _check_ngain(text: str) -> tuple[dict[str, Any], list[AnalysisIssue]]:
    values: list[dict[str, Any]] = []
    issues: list[AnalysisIssue] = []
    seen: set[int] = set()
    for mention in _NGAIN_RE.finditer(text):
        window_start = mention.end()
        window = text[window_start : window_start + 240]
        for match in _VALUE_CATEGORY_RE.finditer(window):
            position = window_start + match.start()
            if position in seen:
                continue
            seen.add(position)
            raw, percent, word = match.group(1), match.group(2), match.group(3).lower()
            value = _number(raw)
            if percent:
                value /= 100
            elif value > 1 and "," not in raw and "." not in raw:
                # A bare integer next to a category ("kelas 7 ... tinggi") is not a gain.
                continue
            stated = _CATEGORY[word]
            item: dict[str, Any] = {"value": round(value, 4), "stated": stated}
            if not 0 <= value <= 1:
                issues.append(
                    AnalysisIssue(
                        check="n_gain",
                        severity="warning",
                        message=f"N-gain {raw}{percent or ''} lies outside 0-1 (0-100%)",
                        remedy="recompute g = (post - pre) / (max - pre); it cannot exceed 1",
                    )
                )
                item["expected"] = None
            else:
                expected = ngain_category(value)
                item["expected"] = expected
                if expected != stated:
                    issues.append(
                        AnalysisIssue(
                            check="n_gain",
                            severity="warning",
                            message=(
                                f"N-gain {raw}{percent or ''} is called {word}, but Hake's "
                                f"bounds make it {expected}"
                            ),
                            remedy=(
                                "use Hake (1998): high g > 0.7, medium 0.3 <= g <= 0.7, "
                                "low g < 0.3, or cite the scale you used instead"
                            ),
                        )
                    )
            values.append(item)
    return {"n_gain_values": values}, issues


def _check_aiken(text: str) -> tuple[dict[str, Any], list[AnalysisIssue]]:
    issues: list[AnalysisIssue] = []
    values = [_number(match.group(1)) for match in _AIKEN_VALUE_RE.finditer(text)]
    for match in _AIKEN_RANGE_RE.finditer(text):
        values += [_number(match.group(1)), _number(match.group(2))]
    for value in values:
        if not 0 <= value <= 1:
            issues.append(
                AnalysisIssue(
                    check="aiken_v",
                    severity="warning",
                    message=f"Aiken's V = {value} lies outside 0-1",
                    remedy="recompute V = sum(r - lo) / (n * (c - 1))",
                )
            )
    raters = bool(_RATERS_RE.search(text))
    categories = bool(_CATEGORIES_RE.search(text))
    missing = [name for name, ok in (("number of raters", raters),
                                     ("number of rating categories", categories)) if not ok]
    if missing:
        issues.append(
            AnalysisIssue(
                check="aiken_v",
                severity="warning",
                message="Aiken's V is used without stating the " + " and the ".join(missing),
                remedy=(
                    "state how many validators rated each item and on how many categories; "
                    "the critical value of V depends on both (Aiken 1985)"
                ),
            )
        )
    return {"aiken_values": values, "aiken_raters_stated": raters,
            "aiken_categories_stated": categories}, issues


def _check_prerequisites(text: str) -> tuple[dict[str, Any], list[AnalysisIssue]]:
    issues: list[AnalysisIssue] = []
    normality = bool(_NORMALITY_RE.search(text))
    between = bool(_BETWEEN_RE.search(text))
    homogeneity = bool(_HOMOGENEITY_RE.search(text))
    if not normality:
        issues.append(
            AnalysisIssue(
                check="prerequisites",
                severity="warning",
                message="a parametric test is used but no normality test is reported",
                remedy=(
                    "report a normality test (Shapiro-Wilk for small samples, "
                    "Kolmogorov-Smirnov/Lilliefors) or use a non-parametric test"
                ),
            )
        )
    if between and not homogeneity:
        issues.append(
            AnalysisIssue(
                check="prerequisites",
                severity="warning",
                message="groups are compared but no homogeneity-of-variance test is reported",
                remedy="report Levene's test, or use Welch's test, which does not assume it",
            )
        )
    return {
        "parametric_test": True,
        "between_groups": between,
        "normality_reported": normality,
        "homogeneity_reported": homogeneity,
    }, issues


def check_analyses(text: str) -> AnalysisCheck:
    """Run every analysis check whose subject the manuscript mentions."""

    applied: list[str] = []
    measurements: dict[str, Any] = {}
    issues: list[AnalysisIssue] = []
    if _NGAIN_RE.search(text):
        applied.append("n_gain")
        found, problems = _check_ngain(text)
        measurements.update(found)
        issues += problems
    if _AIKEN_RE.search(text):
        applied.append("aiken_v")
        found, problems = _check_aiken(text)
        measurements.update(found)
        issues += problems
    if _PARAMETRIC_RE.search(text):
        applied.append("prerequisites")
        found, problems = _check_prerequisites(text)
        measurements.update(found)
        issues += problems
    return AnalysisCheck(applied=tuple(applied), measurements=measurements, issues=tuple(issues))


__all__ = [
    "NGAIN_HIGH",
    "NGAIN_LOW",
    "AnalysisCheck",
    "AnalysisIssue",
    "check_analyses",
    "ngain_category",
]
