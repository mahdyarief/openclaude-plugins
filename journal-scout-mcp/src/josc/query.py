"""Boolean-operator translation across providers.

Providers differ in which uppercase tokens (``AND``/``OR``/``NOT``) their
search syntax accepts. ``translate_query`` rewrites a user query per provider:

* a supported operator is kept exactly as written;
* an unsupported operator is dropped (replaced by one space, whitespace
  collapsed), so ``"a AND b"`` becomes ``"a b"`` for Crossref;
* Scopus spells negation ``AND NOT``, so ``"a NOT b"`` becomes ``"a AND NOT b"``;
* a provider absent from ``OPERATOR_SUPPORT`` is not searchable here and gets
  the query unchanged.

Translation never adds quotes, parentheses or field tags, and never edits the
search terms themselves.
"""

import re

OPERATOR_SUPPORT: dict[str, dict[str, bool]] = {
    "crossref": {"AND": False, "OR": True, "NOT": True},
    "openalex": {"AND": False, "OR": False, "NOT": False},
    "semanticscholar": {"AND": False, "OR": False, "NOT": False},
    "scopus": {"AND": True, "OR": True, "NOT": True},
    "pubmed": {"AND": True, "OR": True, "NOT": True},
    "arxiv": {"AND": True, "OR": True, "NOT": True},
    "dblp": {"AND": True, "OR": True, "NOT": True},
}

_OPERATOR_ORDER = ("AND", "OR", "NOT")
_OPERATOR_RE = re.compile(r"\b(?:AND|OR|NOT)\b")


def detect_operators(query: str) -> list[str]:
    """Return the uppercase boolean tokens present, in canonical order."""
    if not query:
        return []
    found = set(_OPERATOR_RE.findall(query))
    return [operator for operator in _OPERATOR_ORDER if operator in found]


def translate_query(query: str, provider: str) -> str:
    support = OPERATOR_SUPPORT.get(provider)
    if support is None:
        return query

    if provider == "scopus":
        if "NOT" not in detect_operators(query):
            return query
        translated = re.sub(r"\bNOT\b", "AND NOT", query)
        translated = re.sub(r"\bAND\s+AND\s+NOT\b", "AND NOT", translated)
        return " ".join(translated.split())

    translated = query
    removed = False
    for operator in detect_operators(query):
        if support.get(operator):
            continue
        translated = re.sub(rf"\b{operator}\b", " ", translated)
        removed = True
    if removed:
        return " ".join(translated.split())
    return query


def operator_report(providers: list[str], query: str) -> dict:
    requested = detect_operators(query)
    if not requested:
        return {"requested": [], "warnings": []}

    warnings = []
    for provider in providers:
        support = OPERATOR_SUPPORT.get(provider)
        if support is None:
            continue
        for operator in requested:
            if support.get(operator):
                continue
            warnings.append(
                {
                    "source": provider,
                    "operator": operator,
                    "message": (
                        f"{provider} does not support {operator}; "
                        "the operator will be ignored for this source."
                    ),
                }
            )
    return {"requested": requested, "warnings": warnings}
