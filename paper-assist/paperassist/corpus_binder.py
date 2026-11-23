"""Deterministic binding of study records to source files and bibliography keys.

A review can extract hundreds of records and still cite a dozen of them. That
gap is usually invisible: nothing in the pipeline compares the size of the
evidence corpus with the size of the reference list. This module makes the gap
measurable. It binds each extracted record to a local full text and to a
bibliography entry using only structural signals (DOI, title, record id), then
reports exactly which records are bound, which are unbound and why.

Nothing here reads meaning from the text and no model is involved, so the same
inputs always produce the same binding report. The module is domain-agnostic:
it classifies by identifier shape and file form, never by topic.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .path_safety import UnsafePathError, reject_symlink_components

BINDING_SCHEMA = "paperassist.corpus-binding/v1"

STRATEGY_DOI = "doi"
STRATEGY_TITLE = "title"
STRATEGY_RECORD_ID = "record_id"

STRATEGY_ORDER = (STRATEGY_DOI, STRATEGY_TITLE, STRATEGY_RECORD_ID)

# A normalized title must be at least this long before an exact match is
# trusted; short strings collide across unrelated works.
_MIN_TITLE_CHARS = 24

_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)
_DOI_SHAPE = re.compile(r"^10\.\d{4,9}/\S+$")
_NON_ALNUM = re.compile(r"[^0-9a-z]+")
_LEADING_YEAR = re.compile(r"^(?:19|20)\d{2}[\s._-]*")
_BIB_KEY = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,", re.IGNORECASE)
_BIB_FIELD = re.compile(r"(\w+)\s*=\s*\{((?:[^{}]|\{[^{}]*\})*)\}", re.DOTALL)


class CorpusError(RuntimeError):
    pass


class CorpusSafetyError(CorpusError):
    pass


def normalize_doi(value: object) -> str:
    """Return a canonical DOI or an empty string when the value is unusable."""

    text = str(value or "").strip()
    if not text:
        return ""
    text = _DOI_PREFIX.sub("", text).strip()
    text = text.rstrip(".,;)")
    lowered = text.lower()
    return lowered if _DOI_SHAPE.match(lowered) else ""


def normalize_title(value: object) -> str:
    """Collapse a title to a comparison key of letters and digits."""

    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = _LEADING_YEAR.sub("", text)
    return _NON_ALNUM.sub("", text)


def _title_is_reliable(normalized: str) -> bool:
    return len(normalized) >= _MIN_TITLE_CHARS


@dataclass(frozen=True)
class BibEntry:
    key: str
    entry_type: str
    fields: Mapping[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "entry_type": self.entry_type, "fields": dict(self.fields)}


@dataclass(frozen=True)
class RecordBinding:
    """One extracted record and the sources it could be bound to."""

    record_id: str
    title: str
    doi: str
    year: str
    text_path: str | None = None
    text_sha256: str | None = None
    bib_key: str | None = None
    strategy: str | None = None
    problems: tuple[str, ...] = ()

    @property
    def bound(self) -> bool:
        return self.text_path is not None or self.bib_key is not None

    @property
    def fully_bound(self) -> bool:
        return self.text_path is not None and self.bib_key is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "title": self.title,
            "doi": self.doi,
            "year": self.year,
            "text_path": self.text_path,
            "text_sha256": self.text_sha256,
            "bib_key": self.bib_key,
            "strategy": self.strategy,
            "problems": list(self.problems),
            "bound": self.bound,
            "fully_bound": self.fully_bound,
        }


@dataclass(frozen=True)
class CorpusBinding:
    records: tuple[RecordBinding, ...] = ()
    bibliography_keys: tuple[str, ...] = ()
    unexplained_bib_keys: tuple[str, ...] = ()
    digest: str = ""

    def coverage(self) -> dict[str, Any]:
        total = len(self.records)
        with_text = sum(1 for record in self.records if record.text_path)
        with_bib = sum(1 for record in self.records if record.bib_key)
        fully = sum(1 for record in self.records if record.fully_bound)
        return {
            "records": total,
            "with_full_text": with_text,
            "with_bibliography_entry": with_bib,
            "fully_bound": fully,
            "text_coverage": round(with_text / total, 4) if total else 0.0,
            "bibliography_coverage": round(with_bib / total, 4) if total else 0.0,
            "uncited_records": total - with_bib,
            "unmatched_bib_keys": len(self.unexplained_bib_keys),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": BINDING_SCHEMA,
            "digest": self.digest,
            "coverage": self.coverage(),
            "bibliography_keys": list(self.bibliography_keys),
            "unmatched_bib_keys": list(self.unexplained_bib_keys),
            "records": [record.to_dict() for record in self.records],
        }


def parse_bib_entries(text: str) -> tuple[BibEntry, ...]:
    """Parse the field subset needed for binding without a full BibTeX parser."""

    entries: list[BibEntry] = []
    for match in re.finditer(r"@(\w+)\s*\{", text):
        entry_type = match.group(1).lower()
        if entry_type in {"comment", "string", "preamble"}:
            continue
        start = match.end() - 1
        depth = 0
        end = -1
        for index in range(start, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    end = index
                    break
        if end < 0:
            continue
        body = text[start + 1 : end]
        key_match = re.match(r"\s*([^,\s]+)\s*,", body)
        if not key_match:
            continue
        fields = {
            name.lower(): value.strip()
            for name, value in _BIB_FIELD.findall(body[key_match.end() :])
        }
        entries.append(BibEntry(key=key_match.group(1), entry_type=entry_type, fields=fields))
    return tuple(entries)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise CorpusError(f"cannot read bibliography: {path}") from exc


def _resolve_pdf_root(workspace: Path, raw: str | Path) -> Path:
    supplied = Path(str(raw)).expanduser()
    lexical = supplied if supplied.is_absolute() else workspace / supplied
    try:
        lexical = reject_symlink_components(lexical, anchor=workspace)
    except UnsafePathError as exc:
        raise CorpusSafetyError(f"full-text root is unsafe: {raw} ({exc})") from exc
    if not lexical.exists() or not lexical.is_dir():
        raise CorpusError(f"full-text root is not a directory: {raw}")
    resolved = lexical.resolve()
    if not resolved.is_relative_to(workspace):
        raise CorpusSafetyError(f"full-text root escapes the workspace: {raw}")
    return resolved


def _resolve_file(workspace: Path, raw: str | Path, *, what: str) -> Path:
    supplied = Path(str(raw)).expanduser()
    lexical = supplied if supplied.is_absolute() else workspace / supplied
    try:
        lexical = reject_symlink_components(lexical, anchor=workspace)
    except UnsafePathError as exc:
        raise CorpusSafetyError(f"{what} is unsafe: {raw} ({exc})") from exc
    if not lexical.is_file():
        raise CorpusError(f"{what} not found: {raw}")
    resolved = lexical.resolve()
    if not resolved.is_relative_to(workspace):
        raise CorpusSafetyError(f"{what} escapes the workspace: {raw}")
    return resolved


def load_records(
    payload: Mapping[str, Any], workspace: str | Path
) -> list[Mapping[str, Any]]:
    """Load extraction records from the payload, inline or from a file."""

    root = Path(workspace).expanduser().resolve(strict=True)
    return _load_records(payload, root)


def _load_records(payload: Mapping[str, Any], workspace: Path) -> list[Mapping[str, Any]]:
    inline = payload.get("records")
    if isinstance(inline, Sequence) and not isinstance(inline, (str, bytes)):
        return [record for record in inline if isinstance(record, Mapping)]
    source = payload.get("records_path") or payload.get("extraction_path")
    if not source:
        raise CorpusError("corpus binding requires `records` or `records_path`")
    path = _resolve_file(workspace, source, what="records file")
    try:
        data = json.loads(_read_text(path))
    except json.JSONDecodeError as exc:
        raise CorpusError(f"records file is not valid JSON: {source}") from exc
    if isinstance(data, Mapping):
        for key in ("records", "data", "items", "results"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise CorpusError("records file must contain a JSON array of objects")
    return [record for record in data if isinstance(record, Mapping)]


def _candidate_files(pdf_root: Path) -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    for child in sorted(pdf_root.rglob("*")):
        if not child.is_file() or child.is_symlink():
            continue
        files.append((child, child.relative_to(pdf_root).as_posix()))
    return files


def _index_rows(pdf_root: Path) -> dict[str, str]:
    """Read an optional ``_index.csv`` that maps record ids to file names."""

    index = pdf_root / "_index.csv"
    if not index.is_file():
        return {}
    import csv
    import io

    rows: dict[str, str] = {}
    reader = csv.DictReader(io.StringIO(_read_text(index)))
    for row in reader:
        record_id = str(row.get("record_id") or "").strip()
        filename = str(row.get("file") or "").strip()
        if record_id and filename:
            rows[record_id] = filename
    return rows


def bind_corpus(
    workspace: str | Path,
    payload: Mapping[str, Any],
) -> CorpusBinding:
    """Bind extracted records to full texts and bibliography entries."""

    root = Path(workspace).expanduser().resolve(strict=True)
    records = _load_records(payload, root)
    if not records:
        raise CorpusError("no records to bind")

    pdf_root = _resolve_pdf_root(
        root, payload.get("fulltext_root") or payload.get("pdf_root") or "."
    )
    files = _candidate_files(pdf_root)
    index_rows = _index_rows(pdf_root)

    bib_entries: tuple[BibEntry, ...] = ()
    bib_source = payload.get("bibliography_path")
    if bib_source:
        bib_path = _resolve_file(root, bib_source, what="bibliography")
        bib_entries = parse_bib_entries(_read_text(bib_path))

    by_bib_doi: dict[str, BibEntry] = {}
    by_bib_title: dict[str, BibEntry] = {}
    for entry in bib_entries:
        doi = normalize_doi(entry.fields.get("doi"))
        if doi:
            by_bib_doi.setdefault(doi, entry)
        title_key = normalize_title(entry.fields.get("title"))
        if _title_is_reliable(title_key):
            by_bib_title.setdefault(title_key, entry)

    used_bib_keys: set[str] = set()
    bindings: list[RecordBinding] = []

    for record in records:
        record_id = str(record.get("id") or record.get("record_id") or "").strip()
        raw_title = str(record.get("title") or "").strip()
        doi = normalize_doi(record.get("doi"))
        year = str(record.get("year") or "").strip()
        problems: list[str] = []

        if not record_id:
            problems.append("record has no id")
        if not raw_title:
            problems.append("record has no title")
        if not doi:
            problems.append("record has no valid DOI")

        title_key = normalize_title(raw_title)
        title_reliable = _title_is_reliable(title_key)

        text_path: str | None = None
        text_sha: str | None = None
        strategy: str | None = None

        # Strategy 1: explicit record id in an index file or file name.
        if record_id and record_id in index_rows:
            candidate = pdf_root / index_rows[record_id]
            if candidate.is_file():
                text_path = candidate.relative_to(pdf_root).as_posix()
                strategy = STRATEGY_RECORD_ID
        if text_path is None and record_id:
            for path, relative in files:
                if record_id in path.stem:
                    text_path = relative
                    strategy = STRATEGY_RECORD_ID
                    break

        # Strategy 2: DOI appearing in the file name.
        if text_path is None and doi:
            doi_token = doi.replace("/", "").replace(".", "")
            for _path, relative in files:
                condensed = relative.lower().replace("/", "").replace(".", "")
                if doi.lower() in relative.lower() or (
                    len(doi_token) >= 8 and doi_token in condensed
                ):
                    text_path = relative
                    strategy = STRATEGY_DOI
                    break

        # Strategy 3: normalized title appearing in the file name.
        if text_path is None and title_reliable:
            for _path, relative in files:
                if title_key in normalize_title(relative):
                    text_path = relative
                    strategy = STRATEGY_TITLE
                    break

        if text_path is not None:
            absolute = pdf_root / text_path
            try:
                text_sha = hashlib.sha256(absolute.read_bytes()).hexdigest()
            except OSError:
                problems.append("bound file is unreadable")
                text_path = None
                text_sha = None

        bib_key: str | None = None
        if doi and doi in by_bib_doi:
            bib_key = by_bib_doi[doi].key
        elif title_reliable and title_key in by_bib_title:
            bib_key = by_bib_title[title_key].key
        if bib_key is not None:
            used_bib_keys.add(bib_key)

        if text_path is None and bib_key is None:
            problems.append("not bound to any full text or bibliography entry")

        bindings.append(
            RecordBinding(
                record_id=record_id,
                title=raw_title,
                doi=doi,
                year=year,
                text_path=text_path,
                text_sha256=text_sha,
                bib_key=bib_key,
                strategy=strategy,
                problems=tuple(problems),
            )
        )

    unexplained = tuple(
        sorted(entry.key for entry in bib_entries if entry.key not in used_bib_keys)
    )

    binding = CorpusBinding(
        records=tuple(bindings),
        bibliography_keys=tuple(entry.key for entry in bib_entries),
        unexplained_bib_keys=unexplained,
    )
    digest = hashlib.sha256(
        json.dumps(binding.to_dict(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return CorpusBinding(
        records=binding.records,
        bibliography_keys=binding.bibliography_keys,
        unexplained_bib_keys=binding.unexplained_bib_keys,
        digest=digest,
    )


def _bib_escape(value: str) -> str:
    # Undecodable bytes surface as U+FFFD, which aborts a LaTeX run and has no
    # BibTeX representation. Removing it leaves a title a reader can still find
    # by DOI rather than failing the whole document.
    text = str(value or "").replace("\ufffd", "").replace("\x00", "").strip()
    return text.replace("\\", "\\textbackslash").replace("&", "\\&").replace("%", "\\%")


def _make_key(record: Mapping[str, Any]) -> str:
    authors = str(record.get("authors") or record.get("first_author") or "").strip()
    surname = re.split(r"[\s,]+", authors)[0].lower() if authors else ""
    surname = _NON_ALNUM.sub("", surname) or "anon"
    year = re.sub(r"[^0-9]", "", str(record.get("year") or "")) or "nd"
    title_words = re.findall(r"[a-z0-9]+", str(record.get("title") or "").lower())
    head = "".join(title_words[:1]) or "untitled"
    base = f"{surname}{year}{head}"
    return re.sub(r"[^a-z0-9]", "", base) or "entry"


_AFFILIATION_RE = re.compile(
    r"\b(?:universit|department|dept\.|institute|institut|laborator|college|"
    r"school of|hospital|center for|centre for|inc\.|ltd|corp|company|"
    r"software development|engineer|street|road|avenue|suite|"
    r"\d{3,}\s+[A-Z])\b",
    re.IGNORECASE,
)


def _looks_like_person_name(value: str) -> bool:
    """Reject a RIS author field that carries an affiliation instead of a name.

    Some exports put a job title and a postal address in the author tag. Passing
    that through produces a BibTeX name with commas inside a single field, which
    BibTeX reports as a malformed name and can abort the bibliography.
    """

    text = value.strip()
    if not text or len(text) > 90:
        return False
    if text.count(",") >= 2:
        return False
    return not _AFFILIATION_RE.search(text)


def parse_ris(text: str) -> tuple[dict[str, Any], ...]:
    """Parse the RIS subset that carries bibliographic identity.

    Reference managers export author names, venue and year that extraction
    tables usually drop. Recovering them turns a placeholder entry into one a
    reader can actually look up. Unknown tags are ignored rather than guessed.
    """

    records: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    authors: list[str] = []

    def flush() -> None:
        nonlocal current, authors
        if not current:
            authors = []
            return
        if authors:
            current["authors"] = " and ".join(authors)
        records.append(current)
        current = {}
        authors = []

    for raw in text.splitlines():
        line = raw.rstrip("\r\n")
        if not line.strip():
            continue
        if len(line) < 6 or line[2:6] != "  - ":
            if line.startswith("ER"):
                flush()
            continue
        tag, value = line[:2], line[6:].strip()
        if tag == "TY":
            flush()
            current["type"] = value.upper()
        elif tag == "TI" or tag == "T1":
            current.setdefault("title", value)
        elif tag == "AU" or tag == "A1":
            if _looks_like_person_name(value):
                authors.append(value)
        elif tag == "JO" or tag == "T2" or tag == "JA":
            current.setdefault("journal", value)
        elif tag == "PY" or tag == "Y1":
            current.setdefault("year", value[:4])
        elif tag == "DO":
            current.setdefault("doi", value)
        elif tag == "ER":
            flush()
    flush()
    return tuple(records)


def _identity_keys(record: Mapping[str, Any]) -> tuple[str, ...]:
    keys: list[str] = []
    doi = normalize_doi(str(record.get("doi") or ""))
    if doi:
        keys.append(f"doi:{doi}")
    title = normalize_title(str(record.get("title") or ""))
    if title:
        keys.append(f"title:{title}")
    return tuple(keys)


def enrich_records_with_ris(
    records: Iterable[Mapping[str, Any]],
    ris_records: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Fill missing authors, venue and year from RIS exports.

    A record is matched by DOI first and by normalised title second, because a
    DOI is stable and a title survives small punctuation differences. Existing
    values are never overwritten: the extraction table remains authoritative
    for anything it states, and RIS only supplies what it left blank.
    """

    index: dict[str, Mapping[str, Any]] = {}
    for ris_record in ris_records:
        for key in _identity_keys(ris_record):
            index.setdefault(key, ris_record)

    enriched: list[dict[str, Any]] = []
    filled = 0
    for record in records:
        copy = dict(record)
        match = None
        for key in _identity_keys(copy):
            match = index.get(key)
            if match is not None:
                break
        if match is not None:
            changed = False
            for field in ("authors", "journal", "year"):
                if not str(copy.get(field) or "").strip() and str(match.get(field) or "").strip():
                    copy[field] = match[field]
                    changed = True
            if changed:
                filled += 1
        enriched.append(copy)
    return enriched, filled


def _unique_key(base: str, taken: set[str]) -> str:
    """Disambiguate a generated key against every key already in play.

    Extraction tables routinely omit authors, so many records collapse to the
    same ``anon<year><initial>`` stem. Emitting them unchanged would put
    duplicate keys in the bibliography and silently drop all but one entry at
    BibTeX time, which looks like missing references rather than a conflict.
    """

    if base not in taken:
        return base
    for suffix in "abcdefghijklmnopqrstuvwxyz":
        candidate = f"{base}{suffix}"
        if candidate not in taken:
            return candidate
    index = 2
    while f"{base}{index}" in taken:
        index += 1
    return f"{base}{index}"


def generate_bibtex(
    binding: CorpusBinding,
    records: Iterable[Mapping[str, Any]],
) -> tuple[str, tuple[str, ...]]:
    """Emit BibTeX for records that lack an entry, plus the keys it added.

    Entries are written as ``@misc`` with the DOI and journal retained. Author
    names are only emitted when the record carries them; otherwise the caller
    receives a warning naming the key, so an incomplete entry is never mistaken
    for a complete one. Keys are unique against the existing bibliography and
    against each other. The mapping is the authoritative citation key for every
    record.
    """

    _, text, warnings = assign_bibtex_keys(binding, records)
    return text, warnings


def assign_bibtex_keys(
    binding: CorpusBinding,
    records: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, str], str, tuple[str, ...]]:
    """Return the citation key for every bound record, plus new BibTeX entries.

    The mapping covers already-cited records as well as newly named ones, so a
    catalogue or appendix can cite the whole corpus rather than the handful of
    records that happened to appear in the prose.
    """

    by_id = {
        str(record.get("id") or record.get("record_id") or "").strip(): record
        for record in records
    }
    blocks: list[str] = []
    key_by_id: dict[str, str] = {}
    warnings: list[str] = []
    taken = set(binding.bibliography_keys)

    for record_binding in binding.records:
        if record_binding.bib_key is not None:
            key_by_id[record_binding.record_id] = record_binding.bib_key
            continue
        record = by_id.get(record_binding.record_id, {})
        key = _unique_key(_make_key(record), taken)
        taken.add(key)
        key_by_id[record_binding.record_id] = key
        fields = [("title", record_binding.title)]
        if record_binding.year:
            fields.append(("year", record_binding.year))
        journal = str(record.get("journal") or "").strip()
        if journal:
            fields.append(("journal", journal))
        authors = str(record.get("authors") or record.get("first_author") or "").strip()
        if authors:
            fields.append(("author", authors))
        else:
            warnings.append(f"{key}: no author recorded; entry is incomplete")
        if record_binding.doi:
            fields.append(("doi", record_binding.doi))
            fields.append(("url", f"https://doi.org/{record_binding.doi}"))
        body = ",\n".join(
            f"  {name} = {{{_bib_escape(value)}}}" for name, value in fields if value
        )
        blocks.append(f"@misc{{{key},\n{body}\n}}\n")

    return key_by_id, "\n".join(blocks), tuple(warnings)


def format_binding_report(binding: CorpusBinding) -> str:
    coverage = binding.coverage()
    lines = [
        "## Corpus binding report",
        "",
        f"- records: {coverage['records']}",
        f"- bound to full text: {coverage['with_full_text']} "
        f"({coverage['text_coverage']:.1%})",
        f"- bound to bibliography: {coverage['with_bibliography_entry']} "
        f"({coverage['bibliography_coverage']:.1%})",
        f"- fully bound: {coverage['fully_bound']}",
        f"- uncited records: {coverage['uncited_records']}",
        f"- bibliography keys with no record: {coverage['unmatched_bib_keys']}",
    ]
    if binding.unexplained_bib_keys:
        lines.append(
            "- unmatched keys: " + ", ".join(binding.unexplained_bib_keys)
        )
    missing_bib = [
        record.record_id
        for record in binding.records
        if record.text_path and not record.bib_key
    ]
    if missing_bib:
        preview = ", ".join(missing_bib[:20])
        suffix = f" (and {len(missing_bib) - 20} more)" if len(missing_bib) > 20 else ""
        lines.append(f"- full text present but not cited: {preview}{suffix}")
    lines.append("")
    return "\n".join(lines)


def _latex_escape(value: object) -> str:
    text = str(value or "")
    # A replacement character means the source bytes were undecodable, so what
    # is left is damage rather than text. Emitting it aborts a LaTeX run mid
    # document; dropping it leaves a title that is merely incomplete, which a
    # reader can still identify by DOI.
    if "\ufffd" in text or "\x00" in text:
        text = text.replace("\ufffd", "").replace("\x00", "").strip()
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def render_study_catalogue(
    binding: CorpusBinding,
    records: Iterable[Mapping[str, Any]],
    *,
    key_by_id: Mapping[str, str] | None = None,
    columns: Sequence[str] | None = None,
    caption: str = "Included studies",
    label: str = "tab:studies",
    max_title_chars: int = 90,
) -> tuple[str, tuple[str, ...]]:
    """Render an appendix table that cites every included study.

    A review that synthesises a hundred studies but lists a dozen references has
    not made its corpus auditable. The catalogue names each record with its
    citation key, so a reader can trace any aggregate back to the studies behind
    it. Columns are chosen from fields the records actually carry, and missing
    values are printed as an explicit placeholder rather than guessed. Returns
    the table body and a warning for every record it could not cite.
    """

    record_list = list(records)
    by_id = {
        str(record.get("id") or record.get("record_id") or "").strip(): record
        for record in record_list
    }
    keys = dict(key_by_id or {})
    warnings: list[str] = []

    # Only fields present across most records are worth a column: a field that
    # appears in two rows would print a table of placeholders.
    total = len(binding.records) or 1
    candidates = list(columns or ("year", "journal", "dataset_n"))
    chosen = [
        name for name in candidates
        if sum(1 for record in record_list if str(record.get(name) or "").strip())
        >= max(2, total * 0.25)
    ]

    header = ["Study"] + [name.replace("_", " ").title() for name in chosen]
    if any(name == "journal" for name in chosen):
        header[header.index("Journal")] = "Venue"

    lines = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\small",
        rf"\caption{{{_latex_escape(caption)}}}",
        rf"\label{{{label}}}",
        r"\begin{tabular}{@{}p{0.34\textwidth}l" + "l" * len(chosen) + r"@{}}",
        r"\toprule",
        " & ".join(header) + r" \\",
        r"\midrule",
    ]

    for record_binding in binding.records:
        key = keys.get(record_binding.record_id)
        if not key:
            warnings.append(
                f"{record_binding.record_id}: no citation key, omitted from catalogue"
            )
            continue
        record = by_id.get(record_binding.record_id, {})
        title = " ".join(str(record_binding.title or "").split())
        if len(title) > max_title_chars:
            title = title[: max_title_chars - 3].rstrip() + "..."
        cells = [rf"\citep{{{key}}} \textit{{{_latex_escape(title)}}}"]
        for name in chosen:
            value = " ".join(str(record.get(name) or "").split())
            cells.append(_latex_escape(value) if value else "NR")
        lines.append(" & ".join(cells) + r" \\")

    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table*}"])
    return "\n".join(lines) + "\n", tuple(warnings)


__all__ = [
    "BINDING_SCHEMA",
    "BibEntry",
    "CorpusBinding",
    "CorpusError",
    "CorpusSafetyError",
    "RecordBinding",
    "STRATEGY_DOI",
    "STRATEGY_RECORD_ID",
    "STRATEGY_TITLE",
    "bind_corpus",
    "format_binding_report",
    "load_records",
    "generate_bibtex",
    "assign_bibtex_keys",
    "render_study_catalogue",
    "parse_bib_entries",
    "parse_ris",
    "enrich_records_with_ris",
]
