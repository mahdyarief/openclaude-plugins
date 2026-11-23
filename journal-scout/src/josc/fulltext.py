"""In-memory full-text search over an archived paper corpus.

This is a deliberately small replacement for an FTS5 index. It tokenizes the
searchable fields of each paper, builds an inverted index, and answers AND
queries. The index is rebuilt from the stored corpus on demand, so nothing here
needs a schema migration or a background reindex queue.
"""

import re
from typing import Any, Dict, List, Sequence

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

_SEARCHABLE_FIELDS = ("title", "abstract", "venue", "tldr")


def tokenize(text: str) -> List[str]:
    if not text:
        return []
    return [token for token in _TOKEN_PATTERN.findall(text.lower()) if len(token) > 2]


def _paper_tokens(paper: Dict[str, Any]) -> List[str]:
    tokens: List[str] = []
    for field in _SEARCHABLE_FIELDS:
        tokens.extend(tokenize(paper.get(field) or ""))
    for author in paper.get("authors") or []:
        tokens.extend(tokenize(author))
    for keyword in paper.get("keywords") or []:
        tokens.extend(tokenize(keyword))
    return tokens


def build_index(papers: Sequence[Dict[str, Any]]) -> Dict[str, List[int]]:
    index: Dict[str, List[int]] = {}
    for position, paper in enumerate(papers):
        for token in set(_paper_tokens(paper)):
            index.setdefault(token, []).append(position)
    return index


def search_index(
    index: Dict[str, List[int]],
    papers: Sequence[Dict[str, Any]],
    query: str,
) -> List[Dict[str, Any]]:
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    candidates = set(index.get(query_tokens[0], []))
    for token in query_tokens[1:]:
        candidates &= set(index.get(token, []))
    if not candidates:
        return []

    scored = []
    for position in candidates:
        tokens = _paper_tokens(papers[position])
        score = sum(tokens.count(token) for token in query_tokens)
        scored.append((score, papers[position].get("title") or "", position))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [papers[position] for _score, _title, position in scored]
