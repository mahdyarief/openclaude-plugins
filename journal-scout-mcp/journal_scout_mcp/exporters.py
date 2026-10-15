"""Convert Paper / dict-of-paper batches to common bibliography formats.

Each public function accepts a normalized list of paper dicts (the shape
``Paper.to_dict()`` produces) and returns a string in the requested format.
The dispatch entry point is :func:`format_papers` which selects the formatter
by name and is the only symbol the rest of the package needs to know.
"""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any, Dict, Iterable, List, Tuple

# Single source of truth for the formats the server advertises. Adding a new
# format = adding an entry here + a formatter function. No switch statement to
# update in two places, no hand-rolled if/elif chain.
FORMATTERS: Dict[str, Any] = {}


def _register(name: str):
    def deco(fn):
        FORMATTERS[name] = fn
        return fn
    return deco


# --- helpers -----------------------------------------------------------------

_NON_ALNUM = re.compile(r"[^A-Za-z0-9]+")


def _citation_key(paper: Dict[str, Any]) -> str:
    """Build a BibTeX/RIS-friendly citation key from a paper record.

    Prefers the DOI when present, otherwise lowercases the first author and
    appends the year (or ``nd``). Strips diacritics only at the ASCII level —
    good enough for citation keys, which must be portable.
    """
    doi = paper.get("doi")
    if doi:
        return doi.replace("/", "_").replace(".", "_").lower()
    authors = paper.get("authors") or []
    first = authors[0] if authors else "anon"
    last = first.split()[-1] if first.split() else "anon"
    year = paper.get("year") or "nd"
    return f"{_NON_ALNUM.sub('', last).lower()}{year}"


def _first_author_last_name(paper: Dict[str, Any]) -> str:
    authors = paper.get("authors") or []
    if not authors:
        return "Anonymous"
    first = authors[0].strip()
    parts = first.split()
    return parts[-1] if len(parts) > 1 else first


def _escape_braces(text: str) -> str:
    """Escape the LaTeX-significant subset of characters for BibTeX values.

    Non-ASCII letters are converted to their LaTeX accent form (``ü`` becomes
    ``{\\\"u}``) so the entry renders correctly with a vanilla BibTeX
    backend that does not understand ``\\"u`` in UTF-8.
    """
    text = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    out: List[str] = []
    for ch in text:
        cp = ord(ch)
        # Common Latin-1 accented letters → LaTeX accent escapes.
        if cp == 0xFC:    # ü
            out.append('{\\"u}')
        elif cp == 0xE4:  # ä
            out.append('{\\"a}')
        elif cp == 0xF6:  # ö
            out.append('{\\"o}')
        elif cp == 0xDF:  # ß
            out.append('{"s}')
        elif cp == 0xE9:  # é
            out.append("\\'e")
        elif cp == 0xE8:  # è
            out.append("\\`e")
        elif cp == 0xE0:  # à
            out.append("\\`a")
        elif cp == 0xF1:  # ñ
            out.append('{\\~n}')
        elif cp == 0xE7:  # ç
            out.append('{\\c{c}}')
        elif ch in "{}":
            pass  # already escaped above
        else:
            out.append(ch)
    return "".join(out)


def _csv_field(text: Any) -> str:
    """Normalize a Paper field for CSV output (None -> empty, list -> '; ')."""
    if text is None:
        return ""
    if isinstance(text, list):
        return "; ".join(str(x) for x in text)
    return str(text)


# Crossref/Scopus use lowercase work-type codes; RIS expects uppercase single-
# or two-letter ones. Keep the mapping local so a new paper type only needs
# touching this dict.
_RIS_TYPE: Dict[str, str] = {
    "article": "JOUR",
    "journal-article": "JOUR",
    "inproceedings": "CONF",
    "conference-paper": "CONF",
    "proceedings-article": "CONF",
    "book": "BOOK",
    "book-chapter": "CHAP",
    "thesis": "THES",
    "report": "RPRT",
    "misc": "GEN",
}


def _ris_type(paper: Dict[str, Any]) -> str:
    """Map a ``Paper.type`` value to the corresponding RIS reference type."""
    raw = (paper.get("type") or "").lower()
    return _RIS_TYPE.get(raw, "GEN")


# --- formatters --------------------------------------------------------------


@_register("bibtex")
def _to_bibtex(papers: List[Dict[str, Any]]) -> str:
    if not papers:
        return ""
    chunks: List[str] = []
    for paper in papers:
        key = _citation_key(paper)
        # Most entries are article-like; journal/conference distinction is
        # preserved by reading ``type`` (Crossref-style) when present.
        entry_type = paper.get("type") or "article"
        if entry_type not in {"article", "inproceedings", "book", "misc"}:
            entry_type = "article"
        lines: List[str] = [f"@{entry_type}{{{key},"]
        if paper.get("title"):
            lines.append(f"  title  = {{{_escape_braces(paper['title']).rstrip('.')}}},")
        authors = paper.get("authors") or []
        if authors:
            joined = " and ".join(_escape_braces(a) for a in authors)
            lines.append(f"  author = {{{joined}}},")
        if paper.get("year"):
            lines.append(f"  year   = {{{paper['year']}}},")
        if paper.get("venue"):
            field = "journal" if entry_type == "article" else "booktitle"
            lines.append(f"  {field:8s} = {{{_escape_braces(paper['venue'])}}},")
        if paper.get("doi"):
            lines.append(f"  doi    = {{{paper['doi']}}},")
        if paper.get("url"):
            lines.append(f"  url    = {{{paper['url']}}},")
        # The trailing comma after the last field is legal BibTeX and lets
        # users append fields without restructuring the entry.
        chunks.append("\n".join(lines) + "\n}\n")
    return "\n".join(chunks)


@_register("ris")
def _to_ris(papers: List[Dict[str, Any]]) -> str:
    if not papers:
        return ""
    chunks: List[str] = []
    for paper in papers:
        lines: List[str] = [f"TY  - {_ris_type(paper)}"]
        for author in paper.get("authors") or []:
            lines.append(f"AU  - {author}")
        if paper.get("title"):
            lines.append(f"TI  - {paper['title']}")
        if paper.get("venue"):
            # JO = journal, T2 = secondary title (book chapter proceedings).
            lines.append(f"JO  - {paper['venue']}")
        if paper.get("year"):
            lines.append(f"PY  - {paper['year']}")
        if paper.get("doi"):
            lines.append(f"DO  - {paper['doi']}")
        if paper.get("url"):
            lines.append(f"UR  - {paper['url']}")
        if paper.get("abstract"):
            lines.append(f"AB  - {paper['abstract']}")
        lines.append("ER  -")
        chunks.append("\n".join(lines))
    return "\n\n".join(chunks) + "\n"


@_register("csv")
def _to_csv(papers: List[Dict[str, Any]]) -> str:
    if not papers:
        return ""
    fieldnames = [
        "title",
        "authors",
        "year",
        "venue",
        "doi",
        "url",
        "pdf_url",
        "citation_count",
        "is_open_access",
        "sources",
        "ids",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    for paper in papers:
        writer.writerow({k: _csv_field(paper.get(k)) for k in fieldnames})
    return buf.getvalue()


@_register("json")
def _to_json(papers: List[Dict[str, Any]]) -> str:
    return json.dumps(papers, ensure_ascii=False, indent=2) if papers else ""


# --- public entry point -----------------------------------------------------


def format_papers(papers: Iterable[Dict[str, Any]], fmt: str) -> str:
    """Format a list of paper dicts in the named bibliography format.

    Unknown formats raise ``ValueError`` so the server can surface a clean
    4xx-style error instead of silently returning something the caller can't
    parse. Use ``FORMATTERS`` to enumerate the supported names.
    """
    key = fmt.lower()
    if key not in FORMATTERS:
        raise ValueError(
            f"Unknown export format: {fmt!r}. Supported: {sorted(FORMATTERS)}"
        )
    return FORMATTERS[key](list(papers))
