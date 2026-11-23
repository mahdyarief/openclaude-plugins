"""Two-channel claim ledger: sourced substance beside model narrative.

A manuscript produced with an AI harness has two kinds of content that must not
be mixed: statements the evidence supports, and prose the model contributed for
flow. When both are written in the same voice, a reader cannot tell which is
which, and a reviewer cannot audit either. This module splits a LaTeX document
into sentence-level records, assigns each sentence to exactly one channel, and
attaches provenance in a PROV-O-shaped form.

Channels
--------
``evidence``
    The sentence carries a factual assertion that is anchored: to a locator
    (``% @locator{key: page=.., quote=".."}``), to a citation, or to a value
    that appears in an ingested data record. Sub-statuses are ``grounded``
    (locator with an excerpt), ``attributed`` (citation, no locator),
    ``derived`` (value traceable to a data record) and ``unsupported`` (a
    quantitative assertion with no anchor at all).
``narrative``
    The sentence makes no verifiable factual assertion. It is the model's
    connective prose. It is kept, separated, and labelled rather than trusted.

The ledger is deterministic: identical input text and identical evidence
inputs produce identical output, byte for byte. No model is called.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .provenance_audit import Locator, extract_locators, load_locators_payload

LEDGER_SCHEMA = "paperassist.claim-ledger/v1"
CLAIM_SCHEMA = "paperassist.claim/v1"

CHANNEL_EVIDENCE = "evidence"
CHANNEL_NARRATIVE = "narrative"

STATUS_GROUNDED = "grounded"
STATUS_ATTRIBUTED = "attributed"
STATUS_DERIVED = "derived"
STATUS_UNSUPPORTED = "unsupported"
STATUS_NARRATIVE = "narrative"

EVIDENCE_STATUSES = frozenset(
    {STATUS_GROUNDED, STATUS_ATTRIBUTED, STATUS_DERIVED, STATUS_UNSUPPORTED}
)
ANCHORED_STATUSES = frozenset({STATUS_GROUNDED, STATUS_ATTRIBUTED, STATUS_DERIVED})

# Numeric evidence task wording reused by the writing pack; the ledger uses the
# same notion of a quantitative assertion so both agree on what needs a source.
_QUANT_UNIT = (
    r"%|\\%|persen|studi|rekaman|artikel|jurnal|pasien|kasus|klaim|sampel|"
    r"responden|partisipan|rekam|dokumen|kode|entri|baris|unit|puluh|ratus|ribu|juta"
)

_CITE_RE = re.compile(r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\]\s*){0,2}\{([^{}]*)\}")
_ANCHOR_OPAQUE_RE = re.compile(
    r"\\(?:ref|eqref|label|cite[a-zA-Z*]*|bibliography|bibliographystyle|"
    r"includegraphics|input|include|url|href|footnote|footnotetext)"
    r"\s*(?:\[[^\]]*\]\s*)*\{[^{}]*\}"
)
_LOCATOR_RE = re.compile(r"%\s*@locator\{[^}]*\}", re.IGNORECASE)
# Structural commands that emit no prose; they must not become sentences.
_INLINE_FORMAT_RE = re.compile(
    r"\\(?:emph|textbf|textit|textsc|texttt|textrm|textsf|textnormal|underline|"
    r"mathrm|mathit|mathbf|text)\s*\{([^{}]*)\}"
)
_STRUCTURAL_RE = re.compile(
    r"\\(?:maketitle|begin|end|centering|caption|label|vspace|hspace|clearpage|"
    r"newpage|bibliographystyle|bibliography|printbibliography|pagebreak|"
    r"tableofcontents|appendix|small|large|normalsize|footnotesize|bfseries)"
    r"\s*(?:\[[^\]]*\])?\s*(?:\{[^{}]*\})?"
)
_MATH_RE = re.compile(r"(?<!\\)\$(?:[^$\\]|\\.)+?(?<!\\)\$")
_DISPLAY_MATH_RE = re.compile(
    r"\\begin\{(?:equation|align|gather|multline|eqnarray)\*?\}.*?"
    r"\\end\{(?:equation|align|gather|multline|eqnarray)\*?\}",
    re.DOTALL,
)
_VERBATIM_RE = re.compile(
    r"\\begin\{(verbatim|lstlisting|minted)\}.*?\\end\{\1\}", re.DOTALL
)
_COMMENT_RE = re.compile(r"(?<!\\)%.*$", re.M)
_PARAGRAPH_BREAK_RE = re.compile(r"\n[ \t]*\n")
_SECTION_RE = re.compile(
    r"\\(part|chapter|section|subsection|subsubsection|paragraph)\*?\s*\{([^{}]*)\}"
)
_TABLE_ENV_RE = re.compile(
    r"\\begin\{(table|figure|tabular|longtable|table\*|figure\*)\*?\}.*?"
    r"\\end\{\1\*?\}",
    re.DOTALL,
)
_CAPTION_RE = re.compile(r"\\caption\{")
_PROTECTED_RE = re.compile(
    r"%\s*PAPERASSIST-PROTECTED-EXPERIMENT-(?:START|END)"
)

# A decimal number in either the dot or the comma convention.
_DECIMAL_RE = re.compile(r"(?<![\d.])\d+[.,]\d+(?![\d])")
_PERCENT_RE = re.compile(r"(?<![\d.])\d+(?:[.,]\d+)?\s*(?:\\?%|persen\b)", re.IGNORECASE)
_COUNT_RE = re.compile(
    rf"(?<![\w.\-])\d+(?:[.,]\d+)?\s+(?:{_QUANT_UNIT})\b", re.IGNORECASE
)
# Any other bare number followed by a noun is still a measurable assertion:
# "42 claims", "7 sources", "3 cohorts". Identifiers such as ``ICD-10`` are
# excluded by requiring whitespace before the number. A word that merely
# follows a number is not a unit: in "52 di antaranya" the number counts
# nothing, and reading "di" as the noun would fabricate a quantity to verify.
_FUNCTION_WORD_RE = re.compile(
    r"^(?:di|ke|dari|dan|atau|yang|pada|untuk|dengan|dalam|ini|itu|juga|saja|"
    r"telah|tidak|bukan|hanya|lebih|kurang|antara|antaranya|studi|dalamnya|"
    r"the|of|and|or|to|in|on|at|for|with|by|from|as|is|are|was|were|be|been|"
    r"that|this|these|those|which|who|whom|its|their|our|we|they|it|a|an|"
    r"more|less|than|about|approximately|are|were|has|have|had)$",
    re.IGNORECASE,
)
_GENERIC_QUANT_RE = re.compile(
    r"(?<![\w.\-])(\d+(?:[.,]\d+)?)\s+([A-Za-z\u00C0-\u024F]{2,})"
)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
# Universal claims are assertions about the whole corpus; they need support
# even when they mention no number ("no study reports X", "the first review").
# The bare quantifiers "seluruh", "semua" and "setiap" only assert something
# about a corpus when a corpus noun follows them: "setiap keputusan" scopes an
# argument, while "setiap studi" makes a checkable claim about the literature.
_CORPUS_NOUN = (
    r"(?:studi|penelitian|literatur|kajian|artikel|makalah|rekaman|laporan|"
    r"publikasi|sumber|naskah|dokumen|kasus|uji|dataset|"
    r"study|studies|work|works|paper|papers|review|reviews|author|authors|"
    r"record|records|article|articles|report|reports|publication|publications|"
    r"source|sources|manuscript|manuscripts|document|documents|case|cases|"
    r"trial|trials|dataset|datasets)"
)
_UNIVERSAL_RE = re.compile(
    rf"\b(?:"
    rf"tidak (?:satu pun|ada|seorang pun)(?: {_CORPUS_NOUN})?|"
    rf"belum (?:ada|pernah)|"
    rf"(?:seluruh|semua|setiap) {_CORPUS_NOUN}|"
    rf"tidak ada {_CORPUS_NOUN}|"
    rf"none of(?: the)?(?: {_CORPUS_NOUN})?|"
    rf"no {_CORPUS_NOUN}|all {_CORPUS_NOUN}|every {_CORPUS_NOUN}|"
    rf"the first|pertama kali|satu-satunya|only {_CORPUS_NOUN}"
    rf")\b",
    re.IGNORECASE,
)
# A denial of inference ("this is not evidence that all studies ...") states a
# limitation on what the data can support. Reading its scope word as a corpus
# assertion would demand evidence for a sentence that explicitly declines to
# make one. The negation must sit next to the scope word, because "no study
# reports X" is a claim while "this is not an estimate over all literature" is a
# denial that happens to name the literature.
_CAVEAT_PREFIX_RE = re.compile(
    r"\b(?:\w+\s+){0,3}(?:bukan|tidak(?:lah)?|bukanlah|not|never|selain|kecuali)\b",
    re.IGNORECASE,
)


def _universal_is_denied(sentence: str) -> bool:
    """True when a universal-claim phrase is wrapped in a negation.

    A sentence like "the ranking is not an estimate over the whole literature"
    names a universal scope only to reject it. Matching the whole sentence but not
    the proximity to the negation would flag a denial as an unsupported claim.
    """

    match = _UNIVERSAL_RE.search(sentence)
    if not match:
        return False
    start = max(0, match.start() - 40)
    return bool(_CAVEAT_PREFIX_RE.search(sentence[start:match.start() + 1]))


_CAVEAT_RE = re.compile(
    r"\bbukan (?:bukti|berarti|jaminan)\b|\bnot (?:evidence|proof)\b|"
    r"\b(?:does|do) not (?:mean|imply)\b",
    re.IGNORECASE,
)
_ABBREVIATIONS = frozenset(
    {
        "al", "etc", "e.g", "i.e", "cf", "vs", "no", "vol", "pp", "p", "fig",
        "figs", "eq", "eqs", "sec", "tab", "dr", "prof",
    }
)


class LedgerError(RuntimeError):
    pass


@dataclass(frozen=True)
class Claim:
    """One sentence of the manuscript with its channel and provenance."""

    claim_id: str
    sentence: str
    section: str
    line_start: int
    line_end: int
    channel: str
    status: str
    citation_keys: tuple[str, ...] = ()
    locator_keys: tuple[str, ...] = ()
    quantities: tuple[str, ...] = ()
    evidence_refs: tuple[Mapping[str, Any], ...] = ()
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": CLAIM_SCHEMA,
            "claim_id": self.claim_id,
            "section": self.section,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "channel": self.channel,
            "status": self.status,
            "sentence": self.sentence,
            "citation_keys": list(self.citation_keys),
            "locator_keys": list(self.locator_keys),
            "quantities": list(self.quantities),
            "evidence_refs": [dict(ref) for ref in self.evidence_refs],
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class ClaimLedger:
    claims: tuple[Claim, ...] = ()
    source_sha256: str = ""
    locator_sha256: str = ""
    digest: str = ""

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {
            STATUS_GROUNDED: 0,
            STATUS_ATTRIBUTED: 0,
            STATUS_DERIVED: 0,
            STATUS_UNSUPPORTED: 0,
            STATUS_NARRATIVE: 0,
        }
        for claim in self.claims:
            counts[claim.status] = counts.get(claim.status, 0) + 1
        evidence_count = len(self.claims) - counts[STATUS_NARRATIVE]
        anchored = (
            counts[STATUS_GROUNDED] + counts[STATUS_ATTRIBUTED] + counts[STATUS_DERIVED]
        )
        return {
            "claims": len(self.claims),
            "evidence_channel": evidence_count,
            "narrative_channel": counts[STATUS_NARRATIVE],
            "grounded": counts[STATUS_GROUNDED],
            "attributed": counts[STATUS_ATTRIBUTED],
            "derived": counts[STATUS_DERIVED],
            "unsupported": counts[STATUS_UNSUPPORTED],
            "anchored_ratio": round(anchored / evidence_count, 4)
            if evidence_count
            else 1.0,
            "narrative_ratio": round(counts[STATUS_NARRATIVE] / len(self.claims), 4)
            if self.claims
            else 0.0,
        }

    def unsupported(self) -> tuple[Claim, ...]:
        return tuple(c for c in self.claims if c.status == STATUS_UNSUPPORTED)

    def by_channel(self, channel: str) -> tuple[Claim, ...]:
        return tuple(c for c in self.claims if c.channel == channel)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": LEDGER_SCHEMA,
            "digest": self.digest,
            "source_sha256": self.source_sha256,
            "locator_sha256": self.locator_sha256,
            "summary": self.summary(),
            "claims": [claim.to_dict() for claim in self.claims],
        }

    def to_jsonl(self, channel: str | None = None) -> str:
        selected = self.claims if channel is None else self.by_channel(channel)
        return "".join(
            json.dumps(claim.to_dict(), ensure_ascii=False, sort_keys=True) + "\n"
            for claim in selected
        )


def _stable_id(*parts: Any) -> str:
    digest = hashlib.sha256(
        "\x1f".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()
    return f"c-{digest[:16]}"


def _strip_inline_commands(text: str) -> str:
    """Remove commands whose arguments are not part of the running prose."""

    return _ANCHOR_OPAQUE_RE.sub(" ", text)


def _strip_structural(text: str) -> str:
    # Inline formatting wraps prose; keep the words, drop the wrapper. The
    # replacement is padded to the original width so sentence offsets stay
    # absolute positions in the source text.
    def unwrap(match: re.Match[str]) -> str:
        inner = match.group(1)
        return inner + " " * (len(match.group(0)) - len(inner))

    text = _INLINE_FORMAT_RE.sub(unwrap, text)
    return _STRUCTURAL_RE.sub(lambda m: " " * len(m.group(0)), text)


def _paragraph_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Split ``text[start:end]`` into paragraph spans separated by blank lines."""

    spans: list[tuple[int, int]] = []
    base = max(0, start)
    limit = min(len(text), end)
    block_start = base
    # Scanning with pos/endpos keeps match offsets absolute; slicing instead
    # would make them relative to a window that the loop is already moving.
    for match in _PARAGRAPH_BREAK_RE.finditer(text, base, limit):
        cut = match.start()
        if cut > block_start:
            spans.append((block_start, cut))
        block_start = match.end()
    if block_start < limit:
        spans.append((block_start, limit))
    return spans


def _split_sentences(text: str) -> list[tuple[str, int, int]]:
    """Segment prose into sentences with absolute start and end offsets.

    Offsets are positions in ``text`` so a caller can map a sentence back to
    the source block and to a line number, and can attach a trailing annotation
    to the sentence it follows.
    """

    protected: list[str] = []

    def stash(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        # Pad to the original width so sentence offsets stay absolute.
        return f"\x00{len(protected) - 1}\x00".ljust(
            len(match.group(0)), "\x00"
        )

    work = _MATH_RE.sub(stash, text)
    work = _strip_structural(work)

    sentences: list[tuple[str, int, int]] = []
    current: list[str] = []
    start = 0
    index = 0
    length = len(work)
    while index < length:
        char = work[index]
        current.append(char)
        if char in ".!?":
            rest = work[index + 1 :]
            if rest[:1].isspace() or index + 1 >= length:
                # Look back for an abbreviation immediately before the stop.
                tail = "".join(current[:-1])
                word_match = re.search(r"([A-Za-z.]+)$", tail)
                token = word_match.group(1) if word_match else ""
                word = token.lower()
                # A single initial ("J. Smith") is an abbreviation; a lone
                # letter after more text ("Indonesia.") is not.
                initial = len(token) == 1 and token.isupper() and char == "."
                abbreviated = word in _ABBREVIATIONS or initial
                decimal = (
                    char == "."
                    and index + 1 < length
                    and work[index + 1].isdigit()
                )
                if not abbreviated and not decimal:
                    sentences.append(("".join(current), start, index + 1))
                    current = []
                    start = index + 1
        index += 1
    if current:
        sentences.append(("".join(current), start, length))

    restored: list[tuple[str, int, int]] = []
    for sentence, begin, end in sentences:
        expanded = re.sub(
            r"\x00(\d+)\x00", lambda m: protected[int(m.group(1))], sentence
        )
        cleaned = _clean(expanded)
        if not cleaned:
            continue
        lead = len(sentence) - len(sentence.lstrip())
        trailing = len(sentence) - len(sentence.rstrip())
        restored.append((cleaned, begin + lead, end - trailing))
    return restored


def _clean(sentence: str) -> str:
    sentence = sentence.replace("\x00", "")
    sentence = re.sub(r"\s+", " ", sentence).strip()
    sentence = re.sub(r"^[\s\-–—]+", "", sentence)
    return sentence


def _quantities(sentence: str) -> tuple[str, ...]:
    """Return quantitative spans that assert a measurable fact."""

    work = _LOCATOR_RE.sub(" ", sentence)
    work = _ANCHOR_OPAQUE_RE.sub(" ", work)
    work = _YEAR_RE.sub(" ", work)
    # The same digits are matched by several patterns at once: "40,8\%" is both
    # a percentage and a decimal. Keeping every match would count that quantity
    # twice, and the bare copy would be judged as a plain decimal, which no
    # recorded proportion can confirm. Keep the widest span at each position and
    # discard anything lying inside it.
    spans: list[tuple[int, int, str]] = []
    for pattern in (_PERCENT_RE, _DECIMAL_RE, _COUNT_RE):
        for match in pattern.finditer(work):
            token = match.group(0).strip()
            if token:
                spans.append((match.start(), match.end(), token))
    for match in _GENERIC_QUANT_RE.finditer(work):
        if _FUNCTION_WORD_RE.match(match.group(2)):
            continue
        token = match.group(0).strip()
        if token:
            spans.append((match.start(), match.end(), token))
    spans.sort(key=lambda span: (span[0], -(span[1] - span[0])))
    found: list[str] = []
    covered_until = -1
    for start, end, token in spans:
        if start < covered_until:
            continue
        if token not in found:
            found.append(token)
        covered_until = max(covered_until, end)
    return tuple(found)


def _section_map(lines: Sequence[str]) -> list[str]:
    """Assign a section title to every line, in document order."""

    labels: list[str] = []
    current = "Front matter"
    for line in lines:
        match = _SECTION_RE.search(line)
        if match:
            current = match.group(2).strip() or current
        labels.append(current)
    return labels


def _line_of_offsets(text: str) -> list[int]:
    offsets = [0]
    for line in text.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def _offset_to_line(offsets: Sequence[int], position: int) -> int:
    low, high = 0, len(offsets) - 1
    while low < high:
        mid = (low + high) // 2
        if offsets[mid] <= position:
            low = mid + 1
        else:
            high = mid
    return low


# Derived numbers carry the kind of quantity they represent. Without that
# distinction a rubric score of 15 would confirm a claim of "15 days", and a
# count of 24 would confirm "24%".
_UNIT_RAW = "r:"
_UNIT_COUNT_ONLY = "n:"
_UNIT_VALUE = "v:"
_UNIT_PERCENT = "p:"
_UNIT_FIELD = "f:"



def _record_value_index(
    records: Iterable[Mapping[str, Any]],
) -> tuple[frozenset[str], frozenset[str]]:
    """Collect numeric values, record ids and defensible aggregates.

    A review reports numbers that appear nowhere as a literal cell: "108
    studies" is a corpus size, "63 studies" is how many records share a
    category, "58,3%" is that category over its own corpus, and "11,10" is a
    mean within a group.

    Every number is registered under the kind of quantity it can support, so
    that a claim cannot borrow an unrelated number that shares its digits. A
    measured cell or list length is unitless and therefore only confirms a bare
    number, which is why a rubric score of 15 cannot confirm "15 days". Counts
    confirm numbers stated with a unit ("87 records"). Proportions confirm only
    percentages, and are computed against the row count of the file they came
    from, never a pooled total across files.
    """

    values: set[str] = set()
    ids: set[str] = set()

    def as_number(value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str) and re.fullmatch(r"-?\d+(?:[.,]\d+)?", value.strip()):
            return float(value.strip().replace(",", "."))
        return None

    named: dict[str, set[float]] = {}

    def register_named(field: str, number: float) -> None:
        named.setdefault(field.strip().lower(), set()).add(float(number))

    def register(prefix: str, number: float) -> None:
        if number != number or number in (float("inf"), float("-inf")):
            return
        if float(number).is_integer():
            values.add(f"{prefix}{int(number)}")
        for rendered in (f"{number:g}", f"{number:.2f}", f"{number:.1f}"):
            values.add(f"{prefix}{rendered}")
            values.add(f"{prefix}{rendered.replace('.', ',')}")

    def leaves(node: Any) -> Iterator[float]:
        if isinstance(node, Mapping):
            for value in node.values():
                yield from leaves(value)
        elif isinstance(node, Sequence) and not isinstance(node, (str, bytes)):
            for item in node:
                yield from leaves(item)
            yield float(len(node))
        elif isinstance(node, bool):
            return
        elif isinstance(node, (int, float)):
            yield float(node)
        elif isinstance(node, str):
            number = as_number(node)
            if number is not None:
                yield number

    def collect_ids(node: Any) -> None:
        if isinstance(node, Mapping):
            for value in node.values():
                collect_ids(value)
        elif isinstance(node, Sequence) and not isinstance(node, (str, bytes)):
            for item in node:
                collect_ids(item)
        elif isinstance(node, str) and re.fullmatch(r"[A-Za-z]?\d[\w-]*", node.strip()):
            ids.add(node.strip())

    groups: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        if isinstance(record, Mapping):
            groups.setdefault(str(record.get("_source", "")), []).append(record)

    def collect_named(node: Any, field: str) -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                collect_named(value, str(key))
        elif isinstance(node, Sequence) and not isinstance(node, (str, bytes)):
            for item in node:
                collect_named(item, field)
        else:
            number = as_number(node)
            if number is not None:
                register_named(field, number)

    for group in groups.values():
        for record in group:
            for number in leaves(record):
                register(_UNIT_RAW, number)
            collect_named(record, "")
            collect_ids(record)

    for group in groups.values():
        # A count document states corpus totals directly; its numeric fields
        # are counts, not measurements, so they are registered as counts.
        if all(record.get("_counts") for record in group):
            for record in group:
                numbers = [n for n in leaves(record)]
                totals = [
                    as_number(value)
                    for field, value in record.items()
                    if not str(field).startswith("_")
                    and (str(field).endswith("_total") or str(field) == "total")
                ]
                denominators = [total for total in totals if total]
                for number in numbers:
                    register(_UNIT_COUNT_ONLY, number)
                    # A count document that names its own denominator supports
                    # the proportion of each count over it.
                    for total in denominators:
                        if 0 < number <= total:
                            register(_UNIT_PERCENT, number / total * 100)
            continue

        counts: set[int] = set()
        field_values: dict[str, dict[str, int]] = {}
        field_elements: dict[str, dict[str, int]] = {}
        numeric_fields: dict[str, list[float]] = {}
        # How many records report a field at all, and how many of those give a
        # single number, are themselves reportable: "84 studies state a dataset
        # size, but only 57 give one figure" is a finding about reporting
        # completeness, not a guess.
        field_stated: dict[str, int] = {}
        field_parsed: dict[str, int] = {}

        for record in group:
            for field, value in record.items():
                name = str(field)
                if name.startswith("_") or isinstance(value, Mapping):
                    continue
                if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                    stated = False
                    bucket = field_elements.setdefault(name, {})
                    for item in value:
                        label = str(item).strip()
                        if label:
                            bucket[label] = bucket.get(label, 0) + 1
                            stated = True
                    if stated:
                        field_stated[name] = field_stated.get(name, 0) + 1
                else:
                    parsed = as_number(value)
                    if parsed is not None:
                        numeric_fields.setdefault(name, []).append(parsed)
                        field_stated[name] = field_stated.get(name, 0) + 1
                        field_parsed[name] = field_parsed.get(name, 0) + 1
                    elif isinstance(value, str) and value.strip():
                        bucket = field_values.setdefault(name, {})
                        label = value.strip()
                        bucket[label] = bucket.get(label, 0) + 1
                        field_stated[name] = field_stated.get(name, 0) + 1

        for bucket in list(field_values.values()) + list(field_elements.values()):
            counts.update(bucket.values())
        counts.add(len(group))
        counts.update(field_stated.values())
        counts.update(field_parsed.values())

        # A rubric reports how many studies reached each score: "75 studies
        # scored 3 on rule computability" is an aggregate of the records, not a
        # free-floating integer. Only scales are counted this way; a field with
        # one value per record has no distribution to report.
        for numbers in numeric_fields.values():
            if not 1 < len(set(numbers)) <= 40:
                continue
            tally: dict[float, int] = {}
            for number in numbers:
                tally[number] = tally.get(number, 0) + 1
            counts.update(tally.values())

        # A mean is only meaningful inside a grouping that partitions the
        # corpus. A field unique per record, or holding one value, names the
        # record rather than a group of them.
        for field, bucket in field_values.items():
            if not 1 < len(bucket) <= 40:
                continue
            for member in bucket:
                for numeric_field in numeric_fields:
                    raw_subset = [
                        as_number(record.get(numeric_field))
                        for record in group
                        if isinstance(group_label := record.get(field), str)
                        and group_label.strip() == member
                    ]
                    subset = [value for value in raw_subset if value is not None]
                    if subset:
                        register(_UNIT_VALUE, sum(subset) / len(subset))

        for numbers in numeric_fields.values():
            register(_UNIT_VALUE, sum(numbers) / len(numbers))

        # Differences are deliberately not registered: over a dense set of
        # counts almost any integer becomes reachable by subtraction, and a
        # wrong number would pass as derived.
        for count in sorted(counts):
            register(_UNIT_COUNT_ONLY, count)
            register(_UNIT_PERCENT, count / len(group) * 100)

    # A counted noun ("42 claims") is confirmed by the data field that bears
    # that same name, not by any number that happens to equal it. Registering
    # these as plain counts would let a rubric field named "total" confirm an
    # unrelated "15 hari", which is the laundering this model exists to stop.
    for field, named_numbers in named.items():
        if not field:
            continue
        for number in named_numbers:
            if float(number).is_integer():
                values.add(f"{_UNIT_FIELD}{field}:{int(number)}")
            values.add(f"{_UNIT_FIELD}{field}:{number:g}")
            values.add(f"{_UNIT_FIELD}{field}:{number:.2f}")
            values.add(f"{_UNIT_FIELD}{field}:{number:.1f}")

    return frozenset(values), frozenset(ids)


def _quantity_noun(quantity: str) -> str:
    words = re.findall(r"[A-Za-zÀ-ɏ]{3,}", quantity)
    return words[-1].lower() if words else ""


def _field_matches_noun(field: str, noun: str) -> bool:
    cleaned = re.sub(r"[^a-z0-9]+", "", field.lower())
    base = re.sub(r"[^a-z0-9]+", "", noun)
    if not cleaned or not base:
        return False
    return cleaned == base or cleaned.rstrip("s") == base.rstrip("s")


def _quantity_units(quantity: str) -> tuple[str, ...]:
    """Return the kinds of derived number that may confirm this quantity.

    A percentage may only be confirmed by a derived proportion. A number
    carrying a unit word ("87 rekaman", "15 hari") asserts a count or a
    measurement, never a raw cell or a mean, so a rubric score of 15 cannot
    confirm "15 hari". A bare number may be either.
    """

    if "%" in quantity or re.search(r"\bpersen\b", quantity, re.IGNORECASE):
        return (_UNIT_PERCENT,)
    digits = re.sub(r"[^\d.,]", "", quantity)
    # A decimal is a measurement, so a mean or a recorded value can confirm it;
    # a whole number attached to a noun is a count of things.
    if re.search(r"\d[.,]\d", digits):
        return (_UNIT_VALUE, _UNIT_RAW)
    if re.search(r"[A-Za-zÀ-ɏ]", re.sub(r"^[^\d]*", "", quantity)):
        return (_UNIT_COUNT_ONLY,)
    return (_UNIT_COUNT_ONLY, _UNIT_RAW, _UNIT_VALUE)


def _quantity_confirmed(
    quantity: str, values: frozenset[str], ids: frozenset[str]
) -> bool:
    # A span such as "81 dari 108" states two counts; concatenating their
    # digits would invent a third number that matches nothing.
    parts = re.findall(r"\d+(?:[.,]\d+)?", quantity)
    if len(parts) > 1:
        units = _quantity_units(quantity)
        return all(
            _quantity_matches(part, units, values) for part in parts
        )
    return _quantity_matches(quantity, _quantity_units(quantity), values)


def _quantity_matches(
    quantity: str, units: tuple[str, ...], values: frozenset[str]
) -> bool:
    digits = re.sub(r"[^\d.,]", "", quantity)
    if not digits:
        return False
    candidates = {digits, digits.replace(",", "."), digits.replace(".", ",")}
    stripped = digits.rstrip(".,")
    candidates.update({stripped, stripped.replace(",", "."), stripped.replace(".", ",")})
    for unit in units:
        for candidate in candidates:
            if f"{unit}{candidate}" in values:
                return True
    # A counted noun resolves to a data field of the same name, allowing for
    # plural and stemming differences ("claims" against a "claims" field).
    noun = _quantity_noun(quantity)
    if noun:
        for value in values:
            if not value.startswith(_UNIT_FIELD):
                continue
            field, _, digits = value[len(_UNIT_FIELD) :].rpartition(":")
            if digits in candidates and _field_matches_noun(field, noun):
                return True
    for unit in units:
        for candidate in candidates:
            try:
                number = float(candidate.replace(",", "."))
            except ValueError:
                continue
            for value in values:
                if not value.startswith(unit):
                    continue
                try:
                    if abs(float(value[len(unit) :].replace(",", ".")) - number) < 1e-9:
                        return True
                except ValueError:
                    continue
    return False


def _locators_by_key(locators: Sequence[Locator]) -> dict[str, Locator]:
    mapping: dict[str, Locator] = {}
    for locator in locators:
        mapping.setdefault(locator.key, locator)
    return mapping


def _locators_after(
    segment: str, locators: Sequence[Locator]
) -> list[Locator]:
    """Return the locators annotated in ``segment`` (the gap after a sentence)."""

    if not segment or not locators:
        return []
    known = {locator.key for locator in locators}
    return [locator for locator in extract_locators(segment) if locator.key in known]


def _citation_keys(sentence: str) -> tuple[str, ...]:
    keys: list[str] = []
    for match in _CITE_RE.finditer(sentence):
        for key in match.group(1).split(","):
            key = key.strip()
            if key and key not in keys:
                keys.append(key)
    return tuple(keys)


def build_ledger(
    manuscript: str,
    *,
    locators: Sequence[Locator] | None = None,
    records: Sequence[Mapping[str, Any]] = (),
) -> ClaimLedger:
    """Classify every sentence of ``manuscript`` into evidence or narrative."""

    if not isinstance(manuscript, str):
        raise LedgerError("manuscript must be text")

    original = manuscript
    source_sha = hashlib.sha256(original.encode("utf-8")).hexdigest()

    # Only the document body carries prose. Blanking the preamble in place keeps
    # every offset aligned with the original text.
    body_start = manuscript.find("\\begin{document}")
    if body_start >= 0:
        body_start += len("\\begin{document}")
    else:
        body_start = 0
    body_end = manuscript.find("\\end{document}")
    if body_end < 0:
        body_end = len(manuscript)

    # Remove regions that carry no runnable prose before segmentation.
    work = _VERBATIM_RE.sub(lambda m: " " * len(m.group(0)), manuscript)
    work = _DISPLAY_MATH_RE.sub(lambda m: " " * len(m.group(0)), work)
    work = _TABLE_ENV_RE.sub(lambda m: " " * len(m.group(0)), work)
    # Comments are blanked, except locator annotations, which carry evidence
    # and must survive so the sentence they follow can inherit them.
    # A locator lives inside a comment, so the comment is blanked while its
    # width is preserved; the locator itself is re-read from the original text
    # by ``_locators_after``.
    work = _COMMENT_RE.sub(lambda m: " " * len(m.group(0)), work)

    # An empty default would silently drop every locator annotation already
    # present in the document; the caller asking for a ledger wants those.
    if locators is None:
        locators = extract_locators(original)

    lines = work.splitlines()
    section_labels = _section_map(lines)
    offsets = _line_of_offsets(work)
    locator_index = _locators_by_key(locators)
    values, ids = _record_value_index(records)

    claims: list[Claim] = []
    seen: set[str] = set()
    # A paragraph is the unit of segmentation: a blank line separates them, and
    # a locator comment annotates the paragraph it closes.
    for block_start, block_end in _paragraph_spans(work, body_start, body_end):
        block_text = work[block_start:block_end]
        # Headings label a paragraph; they are not part of its prose.
        block_text = _SECTION_RE.sub(
            lambda m: " " * len(m.group(0)), block_text
        )
        if not block_text.strip():
            continue
        segments = _split_sentences(block_text)
        for order, (sentence, begin, end) in enumerate(segments):
            key = re.sub(r"\s+", " ", sentence).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            position = block_start + begin

            # A locator annotates the sentence it follows, so read the gap
            # between this sentence and the next one from the untouched text.
            # The last segment's gap must reach the end of the original span,
            # not of the trimmed block, or a trailing locator is cut off.
            gap_end = (
                segments[order + 1][1]
                if order + 1 < len(segments)
                else block_end - block_start
            )
            gap = original[block_start + end : block_start + gap_end]
            local_locators = _locators_after(gap, locators)

            line_index = max(
                0, min(len(section_labels) - 1, _offset_to_line(offsets, position) - 1)
            )
            section = section_labels[line_index] if section_labels else "Body"
            line_start = line_index + 1
            line_end = line_start + sentence.count("\n")

            keys = _citation_keys(sentence)
            locator_keys = tuple(sorted({loc.key for loc in local_locators}))
            quantities = _quantities(sentence)
            universal = (
                bool(_UNIVERSAL_RE.search(sentence))
                and not _CAVEAT_RE.search(sentence)
                and not _universal_is_denied(sentence)
            )

            confirmed: list[str] = []
            unconfirmed: list[str] = []
            for quantity in quantities:
                if _quantity_confirmed(quantity, values, ids):
                    confirmed.append(quantity)
                else:
                    unconfirmed.append(quantity)

            reasons: list[str] = []
            evidence_refs: list[dict[str, Any]] = []

            if locator_keys:
                status = STATUS_GROUNDED
                for loc_key in locator_keys:
                    locator = locator_index[loc_key]
                    evidence_refs.append(
                        {
                            "relation": "wasDerivedFrom",
                            "kind": "locator",
                            "key": loc_key,
                            "page": locator.page,
                            "quote": locator.quote,
                            "source": locator.source,
                        }
                    )
                reasons.append("locator anchors the assertion to an excerpt")
            elif keys:
                status = STATUS_ATTRIBUTED
                for cite_key in keys:
                    evidence_refs.append(
                        {
                            "relation": "wasAttributedTo",
                            "kind": "citation",
                            "key": cite_key,
                            "anchored": cite_key in locator_index,
                        }
                    )
                if any(key not in locator_index for key in keys):
                    reasons.append("citation present but no verbatim excerpt loaded")
                reasons.append("citation attributes the assertion to prior work")
            # Derived means every number in the sentence traces back to the
            # data. One confirmed figure beside one invented figure would
            # otherwise launder the invented one.
            elif quantities and confirmed and not unconfirmed:
                status = STATUS_DERIVED
                for quantity in confirmed:
                    evidence_refs.append(
                        {
                            "relation": "wasDerivedFrom",
                            "kind": "data_record",
                            "value": quantity,
                        }
                    )
                reasons.append("value matches an ingested data record")
            elif quantities and unconfirmed:
                status = STATUS_UNSUPPORTED
                reasons.append(
                    "quantitative assertion without a locator, citation or data record"
                )
            elif universal:
                status = STATUS_UNSUPPORTED
                reasons.append(
                    "universal claim about the corpus without a locator or citation"
                )
            else:
                status = STATUS_NARRATIVE
                reasons.append("no verifiable factual assertion")

            channel = (
                CHANNEL_NARRATIVE if status == STATUS_NARRATIVE else CHANNEL_EVIDENCE
            )
            claims.append(
                Claim(
                    claim_id=_stable_id(source_sha, section, sentence),
                    sentence=sentence,
                    section=section,
                    line_start=line_start,
                    line_end=line_end,
                    channel=channel,
                    status=status,
                    citation_keys=keys,
                    locator_keys=locator_keys,
                    quantities=tuple(quantities),
                    evidence_refs=tuple(evidence_refs),
                    reasons=tuple(reasons),
                )
            )

    ledger = ClaimLedger(claims=tuple(claims), source_sha256=source_sha)
    locator_sha = hashlib.sha256(
        json.dumps(
            [
                {
                    "key": locator.key,
                    "page": locator.page,
                    "quote": locator.quote,
                    "source": locator.source,
                }
                for locator in locators
            ],
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    digest = hashlib.sha256(
        json.dumps(
            {
                "source_sha256": source_sha,
                "locator_sha256": locator_sha,
                "claims": [claim.claim_id for claim in claims],
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return ClaimLedger(
        claims=ledger.claims,
        source_sha256=source_sha,
        locator_sha256=locator_sha,
        digest=digest,
    )


def ledger_from_payload(
    manuscript: str,
    payload: Mapping[str, Any],
    *,
    locators: Sequence[Locator] | None = None,
    records: Sequence[Mapping[str, Any]] | None = None,
) -> ClaimLedger:
    """Build a ledger from a payload that mirrors the writing-pack keys."""

    if locators is None:
        if payload.get("locators") is not None:
            locators = load_locators_payload({"locators": payload.get("locators")})
        elif payload.get("locators_payload") is not None:
            locators = load_locators_payload(payload.get("locators_payload"))
        else:
            locators = extract_locators(manuscript)
    if records is None:
        raw = payload.get("records")
        records = (
            [r for r in raw if isinstance(r, Mapping)]
            if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes))
            else []
        )
    return build_ledger(manuscript, locators=locators, records=records)


def format_ledger_report(ledger: ClaimLedger) -> str:
    summary = ledger.summary()
    lines = [
        "## Claim ledger",
        "",
        "| Channel | Status | Count |",
        "|---|---|---|",
        f"| evidence | grounded | {summary['grounded']} |",
        f"| evidence | attributed | {summary['attributed']} |",
        f"| evidence | derived | {summary['derived']} |",
        f"| evidence | unsupported | {summary['unsupported']} |",
        f"| narrative | narrative | {summary['narrative_channel']} |",
        "",
        f"- anchored ratio within evidence channel: {summary['anchored_ratio']:.1%}",
        f"- narrative share of the document: {summary['narrative_ratio']:.1%}",
    ]
    unsupported = ledger.unsupported()
    if unsupported:
        lines.append("")
        lines.append("### Unsupported quantitative assertions")
        lines.append("")
        for claim in unsupported[:25]:
            location = f"{claim.section} (line {claim.line_start})"
            excerpt = claim.sentence
            if len(excerpt) > 220:
                excerpt = excerpt[:217] + "..."
            lines.append(f"- {location}: {excerpt}")
        if len(unsupported) > 25:
            lines.append(f"- and {len(unsupported) - 25} more")
    lines.append("")
    return "\n".join(lines)


__all__ = [
    "CHANNEL_EVIDENCE",
    "CHANNEL_NARRATIVE",
    "CLAIM_SCHEMA",
    "Claim",
    "ClaimLedger",
    "LEDGER_SCHEMA",
    "LedgerError",
    "STATUS_ATTRIBUTED",
    "STATUS_DERIVED",
    "STATUS_GROUNDED",
    "STATUS_NARRATIVE",
    "STATUS_UNSUPPORTED",
    "build_ledger",
    "format_ledger_report",
    "ledger_from_payload",
]
