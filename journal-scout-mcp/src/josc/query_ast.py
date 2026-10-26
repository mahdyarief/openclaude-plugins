"""Structured field-scoped query compilation.

A :class:`Condition` is one ``field``/``value`` pair plus the boolean operator
that joins it to the previous condition. :func:`compile_conditions` renders the
list into one provider-specific query string and reports which fields the
provider honored natively and which it had to degrade to free text.

Providers disagree about field syntax — Scopus wraps terms in ``TITLE()``,
arXiv prefixes ``ti:``, DBLP uses ``venue:``, and Semantic Scholar has no field
scoping at all — so the AST is compiled per provider rather than translated
from a single shared string.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

VALID_FIELDS = ("title", "abstract", "author", "venue", "all")
VALID_OPERATORS = ("AND", "OR", "NOT")


@dataclass(frozen=True)
class Condition:
    """One field-scoped search clause."""

    field: str
    value: str
    operator: str = "AND"


@dataclass
class CompiledQuery:
    """A provider-specific query string plus what it could not honor."""

    query: str
    honored: List[str]
    degraded: List[str]


def _clean(value: str) -> str:
    """Collapse whitespace and drop double quotes that would break syntax."""
    return " ".join(str(value).replace('"', " ").split())


def _scoper_scopus(field: str):
    return {
        "title": lambda v: f'TITLE("{v}")',
        "abstract": lambda v: f'ABS("{v}")',
        "author": lambda v: f'AUTH("{v}")',
        "venue": lambda v: f'SRCTITLE("{v}")',
        "all": lambda v: v,
    }.get(field)


def _scoper_pubmed(field: str):
    return {
        "title": lambda v: f'"{v}"[Title]',
        "abstract": lambda v: f'"{v}"[Abstract]',
        "author": lambda v: f'"{v}"[Author]',
        "venue": lambda v: f'"{v}"[Journal]',
        "all": lambda v: v,
    }.get(field)


def _scoper_arxiv(field: str):
    return {
        "title": lambda v: f'ti:"{v}"',
        "abstract": lambda v: f'abs:"{v}"',
        "author": lambda v: f'au:"{v}"',
        "all": lambda v: v,
    }.get(field)


def _scoper_dblp(field: str):
    # DBLP has no title: prefix; a bare term is already a title/venue match.
    return {
        "author": lambda v: f"author:{v}",
        "venue": lambda v: f"venue:{v}",
        "all": lambda v: v,
    }.get(field)


def _scoper_free_text(field: str):
    return {"all": lambda v: v}.get(field)


_SCOPERS = {
    "scopus": _scoper_scopus,
    "pubmed": _scoper_pubmed,
    "arxiv": _scoper_arxiv,
    "dblp": _scoper_dblp,
    "crossref": _scoper_free_text,
    "openalex": _scoper_free_text,
    "semanticscholar": _scoper_free_text,
    "garuda": _scoper_free_text,
}

# Derived from the compiler so the matrix can never claim scoping that the
# compiler cannot actually emit.
FIELD_CAPABILITIES = {
    provider: frozenset(
        field for field in VALID_FIELDS if scoper(field) is not None
    )
    for provider, scoper in _SCOPERS.items()
}


def parse_conditions(raw: Optional[Iterable]) -> List[Condition]:
    """Normalize user-supplied clauses, dropping blanks and rejecting typos."""
    conditions: List[Condition] = []
    for item in raw or []:
        if isinstance(item, Condition):
            cond = item
        elif isinstance(item, dict):
            cond = Condition(
                field=str(item.get("field") or "").strip().lower(),
                value=str(item.get("value") or "").strip(),
                operator=str(item.get("operator") or "AND").strip().upper(),
            )
        else:
            raise ValueError(f"Unsupported condition: {item!r}")

        if not cond.value:
            continue
        if cond.field not in VALID_FIELDS:
            raise ValueError(f"Unknown search field: {cond.field!r}")
        if cond.operator not in VALID_OPERATORS:
            raise ValueError(f"Unknown operator: {cond.operator!r}")
        conditions.append(cond)
    return conditions


def _join_operator(provider: str, operator: str) -> str:
    # Scopus spells negation as a two-token phrase.
    if provider == "scopus" and operator == "NOT":
        return "AND NOT"
    return operator


def compile_conditions(
    conditions: Sequence[Condition], provider: str
) -> CompiledQuery:
    """Render clauses into one query string for ``provider``."""
    scoper = _SCOPERS.get(provider, _scoper_free_text)
    honored: List[str] = []
    degraded: List[str] = []
    fragments: List[str] = []

    for cond in conditions:
        value = _clean(cond.value)
        if not value:
            continue
        render = scoper(cond.field)
        if render is None:
            fragments.append(value)
            degraded.append(cond.field)
            continue
        rendered = render(value)
        if fragments:
            fragments.append(f"{_join_operator(provider, cond.operator)} {rendered}")
        else:
            fragments.append(rendered)
        honored.append(cond.field)

    return CompiledQuery(
        query=" ".join(fragments),
        honored=honored,
        degraded=degraded,
    )
