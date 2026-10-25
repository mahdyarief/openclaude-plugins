"""Parse external bibliographic files into Paper.to_dict()-shaped dicts.

Pure and offline: no provider calls, no file I/O — the caller supplies text.
"""

from __future__ import annotations

import csv
import io
import re

from .utils import normalize_doi, parse_int, parse_year

SUPPORTED_FORMATS = ("ris", "bibtex", "enw", "csv", "txt", "ciw")

_EXTENSIONS = {
    ".ris": "ris",
    ".bib": "bibtex",
    ".bibtex": "bibtex",
    ".enw": "enw",
    ".csv": "csv",
    ".txt": "txt",
    ".ciw": "ciw",
}


def _make_record(
    title: str = "",
    authors: list[str] | None = None,
    year: object = None,
    venue: str | None = None,
    doi: str | None = None,
    abstract: str | None = None,
    url: str | None = None,
    citation_count: object = None,
) -> dict:
    record: dict = {
        "title": (title or "").strip(),
        "authors": [a.strip() for a in (authors or []) if a and a.strip()],
        "sources": ["import"],
        "ids": {},
    }
    doi = normalize_doi(doi)
    if doi:
        record["doi"] = doi
        record["ids"]["doi"] = doi
    for key, value in (("abstract", abstract), ("venue", venue), ("url", url)):
        if value and str(value).strip():
            record[key] = str(value).strip()
    parsed_year = parse_year(year)
    if parsed_year is not None:
        record["year"] = parsed_year
    citations = parse_int(citation_count)
    if citations is not None:
        record["citation_count"] = citations
    return record


def _extension_format(filename: str | None) -> str | None:
    if not filename:
        return None
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    if "." not in name:
        return None
    return _EXTENSIONS.get("." + name.rsplit(".", 1)[-1].lower())


_RIS_START = re.compile(r"^\s*TY\s*-\s*", re.M)
_BIB_START = re.compile(r"^\s*@(?:article|book|inproceedings|misc)\b", re.I | re.M)
_ENW_START = re.compile(r"^\s*%0\s+", re.M)
_TAGGED_START = re.compile(r"^\s*(?:PT|AU)\s+", re.M)
_CSV_HEADER_KEYS = {"title", "ti", "doi", "author", "authors", "year", "py"}


def detect_format(filename: str | None, content: str) -> str:
    ext = _extension_format(filename)
    if ext:
        return ext
    text = content or ""
    if _RIS_START.search(text):
        return "ris"
    if _BIB_START.search(text):
        return "bibtex"
    if _ENW_START.search(text):
        return "enw"
    first = next((line for line in text.splitlines() if line.strip()), "")
    if "," in first:
        cells = {cell.strip().lower() for cell in first.split(",")}
        if cells & _CSV_HEADER_KEYS:
            return "csv"
    if _TAGGED_START.search(text):
        return "ciw"
    return "txt"


# --- per-format parsers ------------------------------------------------------

_RIS_FIELD = re.compile(r"^([A-Z][A-Z0-9])\s*-\s?(.*)$")


def _parse_ris(content: str) -> list[dict]:
    records: list[dict] = []
    current: dict | None = None
    for raw in content.splitlines():
        match = _RIS_FIELD.match(raw.strip())
        if not match:
            continue
        tag, value = match.group(1), match.group(2).strip()
        if tag == "TY":
            current = {}
        elif tag == "ER":
            if current is not None:
                records.append(_make_record(**current))
            current = None
        elif current is not None:
            if tag in ("TI", "T1"):
                current.setdefault("title", value)
            elif tag in ("AU", "A1"):
                current.setdefault("authors", []).append(value)
            elif tag in ("PY", "Y1"):
                current.setdefault("year", value)
            elif tag in ("JO", "JF", "T2"):
                current.setdefault("venue", value)
            elif tag == "DO":
                current.setdefault("doi", value)
            elif tag == "AB":
                current.setdefault("abstract", value)
            elif tag == "UR":
                current.setdefault("url", value)
    if current is not None:
        records.append(_make_record(**current))
    return records


_BIB_ENTRY = re.compile(r"@(\w+)\s*\{", re.I)
_BIB_FIELD = re.compile(r"([A-Za-z_][\w-]*)\s*=\s*")
_BIB_SPLIT = re.compile(r"\s+and\s+", re.I)


def _bib_fields(entry: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    pos = 0
    while True:
        match = _BIB_FIELD.search(entry, pos)
        if not match:
            break
        name = match.group(1).lower()
        i = match.end()
        if i >= len(entry):
            break
        if entry[i] == "{":
            depth = 0
            j = i
            while j < len(entry):
                if entry[j] == "{":
                    depth += 1
                elif entry[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            value = entry[i + 1:j]
            pos = j + 1
        elif entry[i] == '"':
            j = entry.find('"', i + 1)
            if j == -1:
                j = len(entry)
            value = entry[i + 1:j]
            pos = j + 1
        else:
            j = i
            while j < len(entry) and entry[j] not in ",\n}":
                j += 1
            value = entry[i:j]
            pos = j + 1
        fields[name] = value.strip()
    return fields


def _parse_bibtex(content: str) -> list[dict]:
    records: list[dict] = []
    for chunk in re.split(r"(?=^\s*@\w+\s*\{)", content, flags=re.M):
        entry = chunk.strip()
        if not entry.startswith("@") or not _BIB_ENTRY.match(entry):
            continue
        fields = _bib_fields(entry)
        authors = _BIB_SPLIT.split(fields.get("author", ""))
        records.append(
            _make_record(
                title=fields.get("title", ""),
                authors=authors,
                year=fields.get("year"),
                venue=fields.get("journal") or fields.get("booktitle"),
                doi=fields.get("doi"),
                abstract=fields.get("abstract"),
                url=fields.get("url"),
                citation_count=fields.get("citation_count") or fields.get("cites"),
            )
        )
    return records


_ENW_FIELD = re.compile(r"^%(\w)\s?(.*)$")


def _parse_enw(content: str) -> list[dict]:
    records: list[dict] = []
    current: dict | None = None
    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            if current is not None:
                records.append(_make_record(**current))
                current = None
            continue
        match = _ENW_FIELD.match(line)
        if not match:
            continue
        tag, value = match.group(1).upper(), match.group(2).strip()
        if tag == "0":
            if current is not None:
                records.append(_make_record(**current))
            current = {}
            continue
        if current is None:
            current = {}
        if tag == "T":
            current.setdefault("title", value)
        elif tag == "A":
            current.setdefault("authors", []).append(value)
        elif tag == "D":
            current.setdefault("year", value)
        elif tag == "J":
            current.setdefault("venue", value)
        elif tag == "R":
            current.setdefault("doi", value)
        elif tag == "X":
            current.setdefault("abstract", value)
        elif tag == "U":
            current.setdefault("url", value)
    if current is not None:
        records.append(_make_record(**current))
    return records


_CSV_ALIASES = {
    "title": "title",
    "ti": "title",
    "doi": "doi",
    "author": "authors",
    "authors": "authors",
    "year": "year",
    "py": "year",
    "venue": "venue",
    "journal": "venue",
    "source": "venue",
    "abstract": "abstract",
    "url": "url",
    "citation_count": "citation_count",
    "citations": "citation_count",
}
_CSV_POSITIONAL = ("title", "authors", "year", "venue", "doi")


def _split_authors(value: str | None) -> list[str]:
    return [part.strip() for part in re.split(r";\s*", value or "") if part.strip()]


def _csv_record(row: dict) -> dict:
    data: dict = {}
    for raw_key, value in row.items():
        key = _CSV_ALIASES.get((raw_key or "").strip().lower())
        if key and value and str(value).strip() and key not in data:
            data[key] = str(value).strip()
    data["authors"] = _split_authors(data.get("authors"))
    return _make_record(**data)


def _parse_csv(content: str) -> list[dict]:
    text = content.lstrip("\ufeff")
    first = next((line for line in text.splitlines() if line.strip()), "")
    header = next(csv.reader([first])) if first else []
    has_header = any(cell.strip().lower() in _CSV_ALIASES for cell in header)
    if has_header:
        reader = csv.DictReader(io.StringIO(text))
    else:
        reader = csv.DictReader(io.StringIO(text), fieldnames=_CSV_POSITIONAL)
    return [
        _csv_record(row)
        for row in reader
        if any((value or "").strip() for value in row.values())
    ]


_TAGGED_FIELD = re.compile(r"^([A-Z]{2})\s+(.*)$")
_CIW_TAGS = {
    "PT", "AU", "TI", "PY", "SO", "JO", "DI", "AB", "UT", "UR", "TC", "ER",
}


def _parse_ciw(content: str) -> list[dict]:
    records: list[dict] = []
    current: dict | None = None
    for raw in content.splitlines():
        match = _TAGGED_FIELD.match(raw.strip())
        if not match:
            continue
        tag, value = match.group(1), match.group(2).strip()
        if tag == "PT":
            if current is not None:
                records.append(_make_record(**current))
            current = {}
            continue
        if tag == "ER":
            if current is not None:
                records.append(_make_record(**current))
            current = None
            continue
        if current is None:
            current = {}
        if tag == "TI":
            current.setdefault("title", value)
        elif tag == "AU":
            current.setdefault("authors", []).append(value)
        elif tag == "PY":
            current.setdefault("year", value)
        elif tag in ("SO", "JO"):
            current.setdefault("venue", value)
        elif tag == "DI":
            current.setdefault("doi", value)
        elif tag == "AB":
            current.setdefault("abstract", value)
        elif tag in ("UT", "UR"):
            current.setdefault("url", value)
        elif tag == "TC":
            current.setdefault("citation_count", value)
    if current is not None:
        records.append(_make_record(**current))
    return records


def _parse_txt(content: str) -> list[dict]:
    for line in content.splitlines():
        match = _TAGGED_FIELD.match(line.strip())
        if match and match.group(1) in _CIW_TAGS:
            return _parse_ciw(content)
    title = next((line.strip() for line in content.splitlines() if line.strip()), "")
    return [_make_record(title=title)]


_PARSERS = {
    "ris": _parse_ris,
    "bibtex": _parse_bibtex,
    "enw": _parse_enw,
    "csv": _parse_csv,
    "ciw": _parse_ciw,
    "txt": _parse_txt,
}


def parse_import(content: str, fmt: str | None = None) -> list[dict]:
    if not content or not content.strip():
        raise ValueError("Import content is empty.")
    if fmt is None:
        fmt = detect_format(None, content)
    else:
        fmt = fmt.lower()
        if fmt not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported import format: {fmt!r}")
    return _PARSERS[fmt](content)
