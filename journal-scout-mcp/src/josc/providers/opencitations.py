import re
from typing import Any, Dict, List, Optional, Tuple

from ..config import get_polite_email
from ..models import Paper, ProviderError
from ..utils import first_of, normalize_doi, parse_year
from .base import ProviderBase

INDEX_URL = "https://api.opencitations.net/index/v2"
META_URL = "https://api.opencitations.net/meta/v1/metadata"
CROSSREF_URL = "https://api.crossref.org/works"

# OpenCitations allows ~180 requests/minute per IP. Batches stay small so a
# single URL never gets close to the server's length limit.
META_BATCH = 40
CROSSREF_BATCH = 50

# Meta resolves all of these; the Index API accepts only doi: and omid:.
_RESOLUTION_SCHEMES = ("doi", "omid", "openalex", "pmid")

_AUTHOR_SUFFIX = re.compile(r"\s*\[[^\]]*\]\s*$")


class OpenCitationsProvider(ProviderBase):
    """Citation links from the OpenCitations Index, metadata from Meta.

    The Index API only answers for ``doi:`` and ``omid:`` PIDs, so any other
    identifier yields an empty list instead of an error — the same convention
    the other providers use for identifiers they cannot resolve.
    """

    name = "opencitations"
    supports_search = False
    supports_citations = True
    supports_references = True

    @staticmethod
    def _pid(identifier: str) -> Optional[str]:
        """Normalize an identifier into a PID the Index API accepts."""
        value = (identifier or "").strip()
        if not value:
            return None
        if value.lower().startswith("omid:"):
            return value
        doi = normalize_doi(value)
        return f"doi:{doi}" if doi and "/" in doi else None

    @staticmethod
    def _meta_pid(identifier: str) -> Optional[str]:
        """Normalize an identifier into a PID the Meta API accepts."""
        value = (identifier or "").strip()
        if not value:
            return None
        lowered = value.lower()
        for scheme in ("omid:", "openalex:", "pmid:"):
            if lowered.startswith(scheme):
                return f"{scheme}{value[len(scheme):]}"
        doi = normalize_doi(value)
        return f"doi:{doi}" if doi and "/" in doi else None

    @staticmethod
    def _split_pids(value: str) -> Dict[str, str]:
        """Parse a space-separated PID string into ``{scheme: value}``."""
        pids: Dict[str, str] = {}
        for token in (value or "").split():
            scheme, sep, rest = token.partition(":")
            if not sep or not rest:
                continue
            scheme = scheme.lower()
            if scheme == "doi":
                rest = normalize_doi(rest) or rest
            pids.setdefault(scheme, rest)
        return pids

    @classmethod
    def _keys(cls, pids: Dict[str, str]) -> List[str]:
        """Every identifier the resolved record can be looked up by."""
        return [
            f"{scheme}:{pids[scheme]}"
            for scheme in _RESOLUTION_SCHEMES
            if pids.get(scheme)
        ]

    @staticmethod
    def _strip_pids(value: str) -> str:
        return _AUTHOR_SUFFIX.sub("", value or "").strip()

    @classmethod
    def _meta_to_paper(cls, record: Dict[str, Any]) -> Optional[Paper]:
        pids = cls._split_pids(record.get("id", ""))
        doi = normalize_doi(pids.get("doi"))
        omid = pids.get("omid")
        title = (record.get("title") or "").strip()
        if not title and not doi and not omid:
            return None

        authors = [
            cls._strip_pids(author)
            for author in (record.get("author") or "").split("; ")
        ]
        ids: Dict[str, str] = {}
        if omid:
            ids["opencitations"] = f"omid:{omid}"
        if pids.get("openalex"):
            ids["openalex"] = pids["openalex"]

        return Paper(
            doi=doi,
            title=title,
            year=parse_year(record.get("pub_date")),
            authors=[author for author in authors if author],
            venue=cls._strip_pids(record.get("venue") or "") or None,
            type=record.get("type") or None,
            url=f"https://doi.org/{doi}" if doi else None,
            sources=["opencitations"],
            ids=ids,
        )

    async def _meta_papers(self, pids: List[str]) -> List[Tuple[Paper, List[str]]]:
        """Resolve PIDs in batches; the Meta API tolerates unknown ones."""
        resolved: List[Tuple[Paper, List[str]]] = []
        for start in range(0, len(pids), META_BATCH):
            chunk = pids[start : start + META_BATCH]
            data = await self._fetch_json(f"{META_URL}/{('__'.join(chunk))}")
            if not isinstance(data, list):
                continue
            for record in data:
                if not isinstance(record, dict):
                    continue
                paper = self._meta_to_paper(record)
                if paper is None:
                    continue
                keys = self._keys(self._split_pids(record.get("id", "")))
                resolved.append((paper, keys))
        return resolved

    @staticmethod
    def _crossref_to_paper(item: Dict[str, Any]) -> Optional[Paper]:
        doi = normalize_doi(item.get("DOI"))
        title = first_of(item.get("title")) or ""
        if not doi and not title:
            return None

        authors = []
        for author in item.get("author") or []:
            name = " ".join(
                part for part in [author.get("given"), author.get("family")] if part
            )
            if name:
                authors.append(name)

        year = None
        for key in ("published", "published-print", "published-online", "issued"):
            parts = (item.get(key) or {}).get("date-parts") or []
            if parts and parts[0]:
                year = parse_year(parts[0][0])
                break

        return Paper(
            doi=doi,
            title=title,
            year=year,
            authors=authors,
            venue=first_of(item.get("container-title")),
            citation_count=item.get("is-referenced-by-count"),
            url=item.get("URL") or (f"https://doi.org/{doi}" if doi else None),
            type=item.get("type"),
            sources=["crossref"],
            ids={"crossref": item.get("DOI")} if item.get("DOI") else {},
        )

    async def _crossref_papers(self, dois: List[str]) -> List[Paper]:
        """Batch-resolve DOIs Meta could not describe."""
        papers: List[Paper] = []
        for start in range(0, len(dois), CROSSREF_BATCH):
            chunk = dois[start : start + CROSSREF_BATCH]
            data = await self._fetch_json(
                CROSSREF_URL,
                params={
                    "filter": ",".join(f"doi:{doi}" for doi in chunk),
                    "rows": len(chunk),
                    "select": "DOI,title,author,issued,container-title,"
                    "is-referenced-by-count,type,URL",
                    "mailto": get_polite_email(),
                },
            )
            items = ((data or {}).get("message") or {}).get("items") or []
            for item in items:
                paper = self._crossref_to_paper(item)
                if paper is not None:
                    papers.append(paper)
        return papers

    async def _resolve(self, entries: List[Dict[str, str]]) -> List[Paper]:
        """Turn a list of PID maps into Papers, preserving input order."""
        if not entries:
            return []

        wanted: List[str] = []
        for pids in entries:
            for scheme in _RESOLUTION_SCHEMES:
                if pids.get(scheme):
                    wanted.append(f"{scheme}:{pids[scheme]}")

        lookup: Dict[str, Paper] = {}
        try:
            for paper, keys in await self._meta_papers(wanted):
                for key in keys:
                    lookup.setdefault(key, paper)
        except ProviderError:
            # Meta being unavailable must not lose links Crossref can resolve.
            pass

        missing = [
            pids["doi"]
            for pids in entries
            if pids.get("doi")
            and not any(key in lookup for key in self._keys(pids))
        ]
        if missing:
            for paper in await self._crossref_papers(missing):
                if paper.doi:
                    lookup.setdefault(f"doi:{paper.doi}", paper)

        papers: List[Paper] = []
        seen: set = set()
        for pids in entries:
            for key in self._keys(pids):
                paper = lookup.get(key)
                if paper is None:
                    continue
                if id(paper) not in seen:
                    seen.add(id(paper))
                    papers.append(paper)
                break
        return papers

    async def _related(self, relation: str, identifier: str, limit: int) -> List[Paper]:
        pid = self._pid(identifier)
        if not pid or limit <= 0:
            return []
        data = await self._fetch_json(f"{INDEX_URL}/{relation}/{pid}")
        if not isinstance(data, list):
            return []

        # ``references`` points from the seed to its cited works; ``citations``
        # points from citing works back to the seed.
        other = "cited" if relation == "references" else "citing"
        entries: List[Dict[str, str]] = []
        for record in data[:limit]:
            if not isinstance(record, dict):
                continue
            pids = self._split_pids(record.get(other, ""))
            if pids:
                entries.append(pids)
        return await self._resolve(entries)

    async def get(self, identifier: str) -> Optional[Paper]:
        pid = self._meta_pid(identifier)
        if not pid:
            return None
        resolved = await self._meta_papers([pid])
        return resolved[0][0] if resolved else None

    async def citations(self, identifier: str, limit: int = 20) -> List[Paper]:
        return await self._related("citations", identifier, limit)

    async def references(self, identifier: str, limit: int = 20) -> List[Paper]:
        return await self._related("references", identifier, limit)
