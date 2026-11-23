"""Map a paper dict to a CSL-JSON item.

This is not a full CSL implementation. It supports the elements needed to
render a journal-article reference list: author, issued, title,
container-title, DOI, volume, issue, page and URL. Styles that rely on
conditional ``cs:choose`` trees or nested ``cs:names`` substitution are out of
scope and will render incorrectly.
"""

from typing import Any, Dict, List, Sequence

from .utils import normalize_doi, normalize_title, parse_year


class CSLStyleError(ValueError):
    """Raised when a citation style specification is invalid."""


def _split_name(name: str) -> Dict[str, str]:
    parts = (name or "").strip().split()
    if not parts:
        return {"family": "", "given": ""}
    if len(parts) == 1:
        return {"family": parts[0], "given": ""}
    return {"family": parts[-1], "given": " ".join(parts[:-1])}


def paper_to_csl(paper: Dict[str, Any]) -> Dict[str, Any]:
    doi = normalize_doi(paper.get("doi"))
    title = paper.get("title") or ""
    item: Dict[str, Any] = {
        "type": "article-journal",
        "id": doi or normalize_title(title),
        "title": title,
    }
    if doi:
        item["DOI"] = doi
    if paper.get("venue"):
        item["container-title"] = paper["venue"]
    if paper.get("url"):
        item["URL"] = paper["url"]
    year = parse_year(paper.get("year"))
    if year is not None:
        item["issued"] = {"date-parts": [[year]]}
    authors: Sequence[str] = paper.get("authors") or []
    if authors:
        item["author"] = [_split_name(name) for name in authors]
    return item


_REQUIRED_STYLE_KEYS = frozenset(
    {
        "author_format",
        "author_join",
        "author_limit",
        "title_quotes",
        "title_suffix",
        "venue_wrap",
        "year_wrap",
        "include_doi",
    }
)

CSL_STYLES: Dict[str, Dict[str, Any]] = {
    "apa": {
        "author_format": "family-initials",
        "author_join": "comma",
        "author_limit": 0,
        "title_quotes": False,
        "title_suffix": ".",
        "venue_wrap": "{v}.",
        "year_wrap": "({v}).",
        "include_doi": True,
    },
    "vancouver": {
        "author_format": "family-initials-plain",
        "author_join": "comma",
        "author_limit": 0,
        "author_suffix": ".",
        "title_quotes": False,
        "title_suffix": ".",
        "venue_wrap": "{v}.",
        "year_wrap": "({v}).",
        "include_doi": False,
    },
    "chicago": {
        "author_format": "family-initials",
        "author_join": "and",
        "author_limit": 0,
        "title_quotes": True,
        "title_suffix": ".",
        "venue_wrap": "",
        "year_wrap": "({v}).",
        "include_doi": False,
        "part_order": ["authors", "title", "venue", "year", "doi"],
    },
}


_RENDERED_PARTS = frozenset({"authors", "year", "title", "venue", "doi"})


def _resolve_style(style: Any) -> Dict[str, Any]:
    if isinstance(style, str):
        if style not in CSL_STYLES:
            raise CSLStyleError(f"unknown style {style!r}")
        return CSL_STYLES[style]
    if not isinstance(style, dict):
        raise CSLStyleError("style must be a name or a dict")
    missing = _REQUIRED_STYLE_KEYS - set(style)
    if missing:
        raise CSLStyleError(f"style missing keys: {sorted(missing)}")
    order = style.get("part_order")
    if order is not None:
        unknown = [part for part in order if part not in _RENDERED_PARTS]
        if unknown:
            raise CSLStyleError(f"part_order has unknown entries: {unknown}")
    return style


def _format_author(author: Dict[str, str], style: Dict[str, Any]) -> str:
    family = author.get("family", "")
    given = author.get("given", "")
    mode = style["author_format"]
    if mode == "family":
        return family
    if mode == "family-given":
        return f"{family}, {given}".strip(", ")
    if mode == "family-initials-plain":
        plain = "".join(part[0].upper() for part in given.split() if part)
        return f"{family} {plain}".strip()
    initials = "".join(part[0].upper() + "." for part in given.split() if part)
    if initials:
        return f"{family}, {initials}"
    return family


def _format_authors(item: Dict[str, Any], style: Dict[str, Any]) -> str:
    authors = item.get("author") or []
    if not authors:
        return ""
    limit = int(style["author_limit"] or 0)
    selected = authors[:limit] if limit else authors
    formatted = [_format_author(author, style) for author in selected]
    if style["author_join"] == "and":
        if len(formatted) == 1:
            joined = formatted[0]
        else:
            joined = ", ".join(formatted[:-1]) + " and " + formatted[-1]
    else:
        joined = ", ".join(formatted)
    return joined + style.get("author_suffix", "")


def _wrap(value: str, template: str, default: str) -> str:
    if not value:
        return ""
    if not template:
        return default.format(v=value)
    return template.format(v=value)


def render_csl(papers: Sequence[Dict[str, Any]], style: Any) -> str:
    """Render paper dicts into a reference list using a style specification."""
    spec = _resolve_style(style)
    if not papers:
        return ""
    lines: List[str] = []
    for paper in papers:
        item = paper_to_csl(paper)
        rendered: Dict[str, str] = {"authors": "", "year": "", "title": "", "venue": "", "doi": ""}
        rendered["authors"] = _format_authors(item, spec)
        issued = item.get("issued") or {}
        date_parts = issued.get("date-parts") or []
        if date_parts and date_parts[0]:
            rendered["year"] = _wrap(str(date_parts[0][0]), spec["year_wrap"], "({v})")
        title = item.get("title") or ""
        if title:
            if spec["title_quotes"]:
                rendered["title"] = f'"{title}{spec["title_suffix"]}"'
            else:
                rendered["title"] = title + spec["title_suffix"]
        venue = item.get("container-title") or ""
        if venue:
            rendered["venue"] = _wrap(venue, spec["venue_wrap"], "{v}")
        if spec["include_doi"] and item.get("DOI"):
            rendered["doi"] = f"https://doi.org/{item['DOI']}"
        order = spec.get("part_order") or ["authors", "year", "title", "venue", "doi"]
        parts = [rendered[key] for key in order if rendered.get(key)]
        lines.append(" ".join(parts))
    return "\n".join(lines) + "\n"
