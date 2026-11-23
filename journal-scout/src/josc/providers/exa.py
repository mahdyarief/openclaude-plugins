from datetime import datetime
from typing import Any, List, Optional

from ..exa_client import call_exa_mcp
from ..models import Paper
from ..utils import parse_year
from .base import ProviderBase

# Exa returns results as plain text blocks separated by a horizontal rule:
#   Title: ...
#   URL: ...
#   Published: ...
#   Author: ...
#   Highlights:
#   <body>
_FIELDS = ("Title", "URL", "Published", "Author", "Highlights")


def _split_blocks(text: str) -> List[str]:
    blocks: List[str] = []
    current: List[str] = []
    for line in text.splitlines():
        if line.strip() == "---":
            if current:
                blocks.append("\n".join(current))
            current = []
            continue
        current.append(line)
    if current:
        blocks.append("\n".join(current))
    return [block.strip() for block in blocks if block.strip()]


def _parse_block(block: str) -> Optional[dict]:
    fields: dict = {}
    body: List[str] = []
    current = None
    for line in block.splitlines():
        matched = next((name for name in _FIELDS if line.startswith(f"{name}:")), None)
        if matched:
            current = matched
            fields[current] = line[len(matched) + 1 :].strip()
            continue
        if current:
            body.append(line)
        elif line.strip():
            current = "Highlights"
            fields[current] = ""
            body.append(line)
    if not fields.get("Title"):
        return None
    text = "\n".join(body).strip()
    if text:
        fields["Highlights"] = "\n".join(
            part for part in (fields.get("Highlights", ""), text) if part
        ).strip()
    return fields


def parse_text_results(text: str) -> List[dict]:
    """Convert Exa's plain-text result blocks into item dicts."""
    items: List[dict] = []
    for block in _split_blocks(text):
        parsed = _parse_block(block)
        if parsed is None:
            continue
        items.append(
            {
                "title": parsed["Title"],
                "url": parsed.get("URL"),
                "publishedDate": parsed.get("Published"),
                "author": parsed.get("Author"),
                "text": parsed.get("Highlights") or None,
            }
        )
    return items


class ExaProvider(ProviderBase):
    """Search the web for papers using Exa's MCP search tool."""

    name = "exa"
    supports_search = True

    @staticmethod
    def _results(payload: Any) -> List[dict]:
        if isinstance(payload, str):
            return parse_text_results(payload)
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("results", "papers", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def _to_paper(item: dict) -> Optional[Paper]:
        title = (item.get("title") or "").strip()
        url = item.get("url") or item.get("link")
        if not title:
            return None

        published = (
            item.get("publishedDate") or item.get("published_date") or item.get("date")
        )
        year = parse_year(published)
        if year is None and isinstance(published, str):
            try:
                year = datetime.fromisoformat(published.replace("Z", "+00:00")).year
            except ValueError:
                pass

        author = item.get("author")
        if isinstance(item.get("authors"), list):
            authors = item["authors"]
        elif isinstance(author, str):
            # Exa joins authors as "Last, First, Last, First"; split the pairs
            # instead of treating the whole line as one name.
            parts = [part.strip() for part in author.split(",") if part.strip()]
            authors = (
                [f"{parts[i]}, {parts[i + 1]}" for i in range(0, len(parts), 2)]
                if len(parts) % 2 == 0
                else [author]
            )
        else:
            authors = []
        authors = [
            name.strip() for name in authors if isinstance(name, str) and name.strip()
        ]
        abstract = item.get("text") or item.get("summary") or item.get("snippet")
        return Paper(
            title=title,
            abstract=abstract,
            year=year,
            authors=authors,
            url=url,
            pdf_url=item.get("pdf_url") or item.get("pdfUrl"),
            sources=["exa"],
            ids={"exa": str(url)} if url else {},
        )

    async def search(
        self,
        query: str,
        limit: int,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        tech_only: bool = False,
        offset: int = 0,
        **_: object,
    ) -> List[Paper]:
        del year_from, year_to, tech_only, offset
        payload = await call_exa_mcp(
            "web_search_exa",
            {
                "query": query,
                "numResults": max(1, min(100, limit)),
                "livecrawl": "fallback",
                "type": "auto",
            },
        )
        return [
            paper
            for item in self._results(payload)
            if (paper := self._to_paper(item)) is not None
        ][:limit]
