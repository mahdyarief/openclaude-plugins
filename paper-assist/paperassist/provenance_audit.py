"""Model-free provenance and claim-faithfulness audit.

PaperAssist never calls a language model. The audit here is therefore purely
deterministic: it checks that every citation in a draft carries a *locator*
(page/line span plus an optional verbatim quote) and that each quoted span can
actually be found in the audited source excerpt that PaperAssist itself
extracted into ``references.json``.

This separates two gaps that earlier versions could not distinguish:

* **anchorless** — a citation key with no locator at all.
* **ungrounded** — a locator whose quote does not occur in the resolved source.

Neither is judged by a model, so the verdict is reproducible and auditable.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

# ``% @locator{key: page=12, lines=40-52, quote="..."}`` — an annotation the
# harness writes next to (or anywhere near) the citation it supports.
_LOCATOR_RE = re.compile(
    r"@locator\{(?P<body>[^}]*)\}", re.IGNORECASE
)
_CITE_RE = re.compile(r"\\(?:cite|citep|citet|citeauthor|citeyear)\*?(?:\[[^\]]*\])*\{([^}]*)\}")

_FIELD_RE = re.compile(r"(?P<name>[A-Za-z_]+)\s*=\s*(?P<value>\"[^\"]*\"|'[^']*'|[^,\s]+)")

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

# One floor for every grounding measure: the quality rubric's anchored-evidence
# ratio and the writing gate's quote-grounded ratio use the same default.
DEFAULT_MIN_ANCHORED = 0.6
DEFAULT_MIN_GROUNDING_RATIO = DEFAULT_MIN_ANCHORED


class ProvenanceAuditError(RuntimeError):
    pass


@dataclass(frozen=True)
class Locator:
    key: str
    page: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    quote: str | None = None
    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "page": self.page,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "quote": self.quote,
            "source": self.source,
        }


@dataclass(frozen=True)
class CitationContext:
    key: str
    span_start: int
    span_end: int
    sentence: str


@dataclass
class ProvenanceReport:
    citations_total: int = 0
    unique_keys: tuple[str, ...] = ()
    anchorless_keys: tuple[str, ...] = ()
    ungrounded_keys: tuple[str, ...] = ()
    unverified_keys: tuple[str, ...] = ()
    locators: tuple[Locator, ...] = ()
    grounded_ratio: float = 0.0
    passed: bool = True
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "paperassist.provenance-audit/v1",
            "citations_total": self.citations_total,
            "unique_keys": list(self.unique_keys),
            "anchorless_keys": list(self.anchorless_keys),
            "ungrounded_keys": list(self.ungrounded_keys),
            "unverified_keys": list(self.unverified_keys),
            "grounded_ratio": round(self.grounded_ratio, 4),
            "passed": self.passed,
            "warnings": list(self.warnings),
            "locators": [locator.to_dict() for locator in self.locators],
        }


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", stripped).strip().casefold()


def extract_locators(text: str) -> tuple[Locator, ...]:
    """Parse ``% @locator{key: ...}`` annotations from a LaTeX draft."""

    locators: list[Locator] = []
    for match in _LOCATOR_RE.finditer(text):
        body = match.group("body")
        if ":" not in body:
            continue
        key, _, rest = body.partition(":")
        key = key.strip()
        if not key:
            continue
        fields: dict[str, str] = {}
        for field_match in _FIELD_RE.finditer(rest):
            value = field_match.group("value")
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            fields[field_match.group("name").lower()] = value.strip()
        line_start: int | None = None
        line_end: int | None = None
        raw_lines = fields.get("lines") or fields.get("line")
        if raw_lines:
            parts = [part.strip() for part in raw_lines.split("-", 1)]
            if parts and parts[0].isdigit():
                line_start = int(parts[0])
                line_end = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else line_start
        locators.append(
            Locator(
                key=key,
                page=fields.get("page") or None,
                line_start=line_start,
                line_end=line_end,
                quote=fields.get("quote") or None,
                source=fields.get("source") or None,
            )
        )
    return tuple(locators)


def load_locators_payload(payload: Mapping[str, Any] | None) -> tuple[Locator, ...]:
    """Accept machine-written locators as an alternative to LaTeX annotations."""

    if not payload:
        return ()
    raw = payload.get("locators")
    if not isinstance(raw, Sequence) or isinstance(raw, str | bytes):
        return ()
    locators: list[Locator] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        line_range = item.get("lines")
        line_start = item.get("line_start")
        line_end = item.get("line_end")
        if isinstance(line_range, str) and "-" in line_range:
            head, _, tail = line_range.partition("-")
            line_start = int(head) if head.strip().isdigit() else line_start
            line_end = int(tail) if tail.strip().isdigit() else line_end
        locators.append(
            Locator(
                key=key,
                page=str(item.get("page")) if item.get("page") is not None else None,
                line_start=int(line_start) if isinstance(line_start, int) else None,
                line_end=int(line_end) if isinstance(line_end, int) else None,
                quote=str(item.get("quote")) if item.get("quote") else None,
                source=str(item.get("source")) if item.get("source") else None,
            )
        )
    return tuple(locators)


def extract_citation_contexts(text: str) -> tuple[CitationContext, ...]:
    """Return every citation key with the sentence that carries it."""

    contexts: list[CitationContext] = []
    for match in _CITE_RE.finditer(text):
        keys = [key.strip() for key in match.group(1).split(",") if key.strip()]
        paragraph_start = text.rfind("\n\n", 0, match.start())
        paragraph_start = 0 if paragraph_start == -1 else paragraph_start + 2
        paragraph_end = text.find("\n\n", match.end())
        if paragraph_end == -1:
            paragraph_end = len(text)
        preamble = text[paragraph_start : match.start()]
        sentence_prefix = _SENTENCE_SPLIT_RE.split(preamble)[-1].strip()
        tail = text[match.end() : paragraph_end]
        sentence_suffix = _SENTENCE_SPLIT_RE.split(tail)[0].strip()
        sentence = " ".join(part for part in (sentence_prefix, sentence_suffix) if part)
        for key in keys:
            contexts.append(
                CitationContext(
                    key=key,
                    span_start=match.start(),
                    span_end=match.end(),
                    sentence=sentence,
                )
            )
    return tuple(contexts)


def _source_excerpts(references_payload: Mapping[str, Any] | None) -> dict[str, str]:
    """Index audited excerpts by citation key when the harness mapped them.

    The bundle stores excerpts keyed by ``source_id``; a ``key_sources`` map in
    the references payload lets a pack bind a citation key to a source id.
    Without that map, every excerpt stays available for global grounding.
    """

    if not references_payload:
        return {}
    bundle = references_payload.get("bundle") or {}
    excerpts = bundle.get("excerpts") if isinstance(bundle, Mapping) else None
    indexed: dict[str, str] = {}
    if isinstance(excerpts, Sequence) and not isinstance(excerpts, str | bytes):
        for excerpt in excerpts:
            if not isinstance(excerpt, Mapping):
                continue
            body = str(excerpt.get("excerpt") or "")
            if not body:
                continue
            source_id = str(excerpt.get("source_id") or "")
            path = str(excerpt.get("path") or "")
            for identifier in (source_id, path, path.rsplit("/", 1)[-1]):
                if identifier:
                    indexed.setdefault(identifier, body)
    key_sources = references_payload.get("key_sources")
    if isinstance(key_sources, Mapping):
        resolved: dict[str, str] = {}
        for key, target_id in key_sources.items():
            matched = indexed.get(str(target_id))
            if matched is not None:
                resolved[str(key)] = matched
        return resolved
    return indexed


def audit(
    text: str,
    *,
    locators: Sequence[Locator] = (),
    references_payload: Mapping[str, Any] | None = None,
    require_locators: bool = True,
    min_grounding_ratio: float = DEFAULT_MIN_GROUNDING_RATIO,
) -> ProvenanceReport:
    """Audit locator coverage and quote grounding without any model call."""

    contexts = extract_citation_contexts(text)
    unique_keys = tuple(sorted({context.key for context in contexts}))
    if not unique_keys:
        return ProvenanceReport(
            citations_total=0,
            unique_keys=(),
            passed=True,
            grounded_ratio=1.0,
        )

    by_key: dict[str, Locator] = {}
    for locator in locators:
        by_key.setdefault(locator.key, locator)

    anchorless = tuple(key for key in unique_keys if key not in by_key)
    excerpts = _source_excerpts(references_payload)

    ungrounded: list[str] = []
    unverified: list[str] = []
    grounded = 0
    for key in unique_keys:
        found = by_key.get(key)
        if found is None or found.quote is None:
            continue
        needle = _normalize(found.quote)
        if not needle:
            continue
        candidates: list[str] = []
        if found.source:
            match = excerpts.get(found.source)
            if match is not None:
                candidates.append(match)
        elif key in excerpts:
            candidates.append(excerpts[key])
        if not candidates and excerpts:
            candidates.extend(excerpts.values())
        if not candidates:
            unverified.append(key)
            continue
        if any(needle in _normalize(candidate) for candidate in candidates):
            grounded += 1
        else:
            ungrounded.append(key)

    locator_bearing = len(unique_keys) - len(anchorless)
    grounded_ratio = (
        grounded / locator_bearing if locator_bearing else (0.0 if anchorless else 1.0)
    )
    warnings: list[str] = []
    if anchorless:
        warnings.append(
            f"{len(anchorless)} citation key(s) have no locator: " + ", ".join(anchorless)
        )
    if ungrounded:
        warnings.append(
            f"{len(ungrounded)} locator quote(s) were not found in the audited source: "
            + ", ".join(sorted(ungrounded))
        )
    if unverified:
        warnings.append(
            f"{len(unverified)} locator quote(s) could not be checked because no source "
            "excerpt was loaded for: " + ", ".join(sorted(unverified))
        )

    passed = True
    if require_locators and anchorless:
        passed = False
    if locator_bearing and grounded_ratio < min_grounding_ratio:
        passed = False

    return ProvenanceReport(
        citations_total=len(contexts),
        unique_keys=unique_keys,
        anchorless_keys=anchorless,
        ungrounded_keys=tuple(sorted(ungrounded)),
        unverified_keys=tuple(sorted(unverified)),
        locators=tuple(locators),
        grounded_ratio=grounded_ratio,
        passed=passed,
        warnings=tuple(warnings),
    )


def report_sha256(report: ProvenanceReport) -> str:
    encoded = json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = [
    "DEFAULT_MIN_ANCHORED",
    "DEFAULT_MIN_GROUNDING_RATIO",
    "CitationContext",
    "Locator",
    "ProvenanceAuditError",
    "ProvenanceReport",
    "audit",
    "extract_citation_contexts",
    "extract_locators",
    "load_locators_payload",
    "report_sha256",
]
