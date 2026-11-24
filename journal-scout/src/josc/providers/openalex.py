import asyncio
import re
from typing import Any, Dict, List, Optional

from ..config import get_openalex_api_key, get_polite_email
from ..models import Paper, ProviderError
from ..utils import normalize_doi, parse_year
from .base import ProviderBase

OPENALEX_URL = "https://api.openalex.org/works"
OPENALEX_TAXONOMY_URL = "https://api.openalex.org"
_TAXONOMY_LEVELS = ("domain", "field", "subfield", "topic")
_OPENALEX_PAUSE_HINT = (
    "OpenAlex paused unauthenticated search. Set OPENALEX_API_KEY or add "
    "'openalex_api_key' to config.json next to this plugin, then retry."
)
CS_CONCEPT_ID = "C41008148"
_DOI_URL_PREFIXES = ("https://doi.org/", "http://doi.org/")
_OPENALEX_ID = re.compile(r"W\d+")
_OPENALEX_URL_PREFIXES = ("https://openalex.org/", "http://openalex.org/")


def reconstruct_abstract(inverted_index):
    if not inverted_index:
        return None
    positions = []
    for word, idxs in inverted_index.items():
        for i in idxs:
            positions.append((i, word))
    if not positions:
        return None
    positions.sort()
    return " ".join(word for _, word in positions)


def _topic_path(topic: dict) -> List[str]:
    """Collapse domain → field → subfield → topic into an ordered breadcrumb."""
    path: List[str] = []
    for level in ("domain", "field", "subfield"):
        name = (topic.get(level) or {}).get("display_name")
        if name and name not in path:
            path.append(name)
    name = topic.get("display_name")
    if name and name not in path:
        path.append(name)
    return path


_OR_FILTER_CHUNK = 50


class OpenAlexProvider(ProviderBase):
    name = "openalex"
    supports_search = True
    supports_citations = True
    supports_author_search = True
    supports_references = True
    supports_related = True
    supports_filters = frozenset({"author", "venue", "affiliation", "issn", "orcid", "doi"})
    supports_tech_only = True

    async def _fetch_json(self, url, params=None, headers=None, provider=None):
        """Attach the OpenAlex API key to every request.

        OpenAlex pauses anonymous search when load is high (HTTP 503 with a
        "Search is temporarily paused" body); authenticated keys keep working.
        """
        params = dict(params or {})
        api_key = get_openalex_api_key()
        if api_key:
            params["api_key"] = api_key
        target = provider or self.name
        if hasattr(self.fetcher, "get_json"):
            try:
                return await self.fetcher.get_json(
                    url, params=params, headers=headers, provider=target
                )
            except ProviderError as exc:
                if api_key is None and "paused" in str(exc).lower():
                    raise ProviderError(
                        target, f"{exc} {_OPENALEX_PAUSE_HINT}"
                    ) from exc
                raise
        response = await self.fetcher.get(url, params=params, headers=headers)
        if response.status_code >= 400:
            body = response.text[:200]
            hint = f" {_OPENALEX_PAUSE_HINT}" if response.status_code >= 500 else ""
            raise ProviderError(target, f"HTTP {response.status_code}: {body}{hint}")
        return response.json()

    @staticmethod
    def _to_paper(work):
        authors = []
        institutions = []
        countries: List[str] = []
        for a in work.get("authorships", []) or []:
            name = (a.get("author") or {}).get("display_name")
            if name:
                authors.append(name)
            codes = list(a.get("countries") or [])
            for institution in a.get("institutions") or []:
                label = institution.get("display_name")
                if label and label not in institutions:
                    institutions.append(label)
                codes.append(institution.get("country_code"))
            for code in codes:
                if code and code.upper() not in countries:
                    countries.append(code.upper())
        primary = work.get("primary_location") or {}
        source = primary.get("source") or {}
        oa = work.get("open_access") or {}
        topics: List[str] = []
        topic_ids: List[str] = []
        topic_paths: List[List[str]] = []
        primary_topic = work.get("primary_topic") or {}
        if primary_topic.get("display_name"):
            primary_path = _topic_path(primary_topic)
            topic_paths.append(primary_path)
            if primary_topic.get("id"):
                topic_ids.append(primary_topic["id"])
            for name in primary_path:
                if name not in topics:
                    topics.append(name)
        for topic_entry in work.get("topics") or []:
            name = topic_entry.get("display_name")
            if name:
                if name not in topics:
                    topics.append(name)
                topic_ids.append(topic_entry.get("id") or name)
                topic_paths.append(_topic_path(topic_entry))
        keywords: List[str] = []
        for keyword in work.get("keywords") or []:
            value = keyword.get("display_name")
            if value:
                keywords.append(value)
        percentile = (work.get("cited_by_percentile_year") or {}).get("min")
        citations_by_year = {}
        for entry in work.get("counts_by_year") or []:
            year = parse_year(entry.get("year"))
            count = entry.get("cited_by_count")
            if year is not None and count is not None:
                citations_by_year[year] = count
        return Paper(
            doi=normalize_doi(work.get("doi")),
            title=work.get("title") or work.get("display_name") or "",
            abstract=reconstruct_abstract(work.get("abstract_inverted_index")),
            year=parse_year(work.get("publication_year")),
            authors=authors,
            venue=source.get("display_name"),
            citation_count=work.get("cited_by_count"),
            url=primary.get("landing_page_url") or work.get("id"),
            pdf_url=primary.get("pdf_url") or oa.get("oa_url"),
            is_open_access=oa.get("is_oa"),
            type=work.get("type"),
            sources=["openalex"],
            ids={"openalex": work.get("id")} if work.get("id") else {},
            is_retracted=work.get("is_retracted"),
            cited_by_percentile=percentile,
            citations_by_year=citations_by_year,
            topics=topics,
            topic_ids=topic_ids,
            topic_paths=topic_paths,
            keywords=keywords,
            institutions=institutions,
            countries=countries,
            references=[ref for ref in work.get("referenced_works") or [] if ref],
            language=work.get("language"),
        )

    def _filters(self, year_from, year_to, tech_only, author=None, venue=None,
                 affiliation=None, issn=None, orcid=None, doi=None):
        filters = []
        if author:
            # A comma separates filters in OpenAlex, so a name like
            # "Harzing, Anne-Wil" must be flattened to spaces first.
            name = " ".join(author.replace(",", " ").split())
            filters.append(f"raw_author_name.search:{name}")
        if venue:
            # Same comma constraint as author: a comma would split filters.
            name = " ".join(venue.replace(",", " ").split())
            filters.append(f"primary_location.source.display_name.search:{name}")
        if affiliation:
            # Comma constraint applies here too: flatten the string first.
            value = " ".join(affiliation.replace(",", " ").split())
            filters.append(f"raw_affiliation_strings.search:{value}")
        if issn:
            filters.append(f"primary_location.source.issn:{issn.strip()}")
        if orcid:
            filters.append(f"authorships.author.orcid:{orcid.strip()}")
        if doi:
            value = doi.strip()
            if value.startswith("https://doi.org/"):
                value = value[len("https://doi.org/"):]
            filters.append(f"doi:{value}")
        if year_from:
            filters.append(f"from_publication_date:{year_from}-01-01")
        if year_to:
            filters.append(f"to_publication_date:{year_to}-12-31")
        if tech_only:
            filters.append(f"concepts.id:{CS_CONCEPT_ID}")
        return filters

    @staticmethod
    def _page_for(offset: int, limit: int) -> int:
        # OpenAlex paginates by page number alongside per-page, so derive the
        # page that skips ``offset`` records.
        return offset // max(limit, 1) + 1

    async def _search_filtered(self, filters, limit, offset) -> List[Paper]:
        params = {"per-page": limit, "mailto": get_polite_email()}
        if filters:
            params["filter"] = ",".join(filters)
        if offset:
            params["page"] = self._page_for(offset, limit)
        data = await self._fetch_json(OPENALEX_URL, params=params)
        return [self._to_paper(w) for w in data.get("results", []) or []]

    async def search(self, query: str, limit: int, year_from=None, year_to=None, tech_only=False, author=None, venue=None, offset: int = 0, affiliation=None, issn=None, orcid=None, doi=None) -> List[Paper]:
        params = {"search": query, "per-page": limit, "mailto": get_polite_email()}
        filters = self._filters(
            year_from, year_to, tech_only, author=author, venue=venue,
            affiliation=affiliation, issn=issn, orcid=orcid, doi=doi,
        )
        if filters:
            params["filter"] = ",".join(filters)
        if offset:
            params["page"] = self._page_for(offset, limit)
        data = await self._fetch_json(OPENALEX_URL, params=params)
        return [self._to_paper(w) for w in data.get("results", []) or []]

    async def search_author(self, author: str, limit: int, year_from=None, year_to=None, venue=None, offset: int = 0, affiliation=None, issn=None, orcid=None, doi=None) -> List[Paper]:
        filters = self._filters(
            year_from, year_to, False, author=author, venue=venue,
            affiliation=affiliation, issn=issn, orcid=orcid, doi=doi,
        )
        return await self._search_filtered(filters, limit, offset)

    @staticmethod
    def _work_id(identifier: str) -> Optional[str]:
        if not identifier:
            return None
        value = identifier.strip()
        if value.lower().startswith("openalex:"):
            value = value[len("openalex:"):].strip()
        if value.lower().startswith(_DOI_URL_PREFIXES):
            value = normalize_doi(value) or value
        if value.startswith("10."):
            return f"doi:{value}"
        lowered = value.rstrip("/").lower()
        for prefix in _OPENALEX_URL_PREFIXES:
            if lowered.startswith(prefix):
                value = value[len(prefix):]
                break
        if _OPENALEX_ID.fullmatch(value):
            return value
        return None

    async def get(self, identifier: str) -> Optional[Paper]:
        work_id = self._work_id(identifier)
        if not work_id:
            return None
        data = await self._fetch_json(
            f"{OPENALEX_URL}/{work_id}", params={"mailto": get_polite_email()}
        )
        return self._to_paper(data) if data else None

    async def get_many(self, identifiers: List[str]) -> List[Paper]:
        """Resolve several identifiers with one request per id type.

        OpenAlex accepts ``filter=doi:A|B`` (a single request) and
        ``filter=openalex:W1|W2``, but the two fields cannot be combined in one
        filter, so DOIs and W-ids are fetched concurrently and merged back into
        the caller's order.
        """
        wanted: List[str] = []
        dois: List[str] = []
        work_ids: List[str] = []
        for identifier in identifiers:
            work_id = self._work_id(identifier)
            if not work_id:
                continue
            wanted.append(identifier)
            if work_id.startswith("doi:"):
                dois.append(work_id[len("doi:") :])
            else:
                work_ids.append(work_id)
        requests = []
        if dois:
            requests.append(("doi", dois))
        if work_ids:
            requests.append(("openalex", work_ids))

        async def _fetch(field: str, values: List[str]) -> List[Paper]:
            # OpenAlex ORs values inside one filter (``doi:A|B``); repeating the
            # field name (``doi:A|doi:B``) is rejected as an OR across filters.
            # One OR filter takes at most 100 values, so chunk below that.
            papers: List[Paper] = []
            for start in range(0, len(values), _OR_FILTER_CHUNK):
                chunk = values[start : start + _OR_FILTER_CHUNK]
                params = {
                    "filter": f"{field}:" + "|".join(chunk),
                    "per-page": len(chunk),
                    "mailto": get_polite_email(),
                }
                data = await self._fetch_json(OPENALEX_URL, params=params)
                papers.extend(self._to_paper(work) for work in data.get("results", []) or [])
            return papers

        outcomes = await asyncio.gather(
            *(_fetch(field, values) for field, values in requests),
            return_exceptions=True,
        )
        papers: List[Paper] = []
        for outcome in outcomes:
            if isinstance(outcome, list):
                papers.extend(outcome)
        order = {identifier.lower(): index for index, identifier in enumerate(wanted)}

        def _position(paper: Paper) -> int:
            candidates = [normalize_doi(paper.doi) or ""]
            openalex_id = (paper.ids or {}).get("openalex", "")
            if openalex_id:
                candidates.append(openalex_id.rsplit("/", 1)[-1])
            for candidate in candidates:
                if candidate.lower() in order:
                    return order[candidate.lower()]
            return len(order)

        return sorted(papers, key=_position)

    @staticmethod
    def _taxonomy_entry(raw: Dict[str, Any], level: str) -> Dict[str, Any]:
        """Normalise one taxonomy record into a flat candidate.

        ``path`` always reads from the broadest level down to ``level``, so a
        topic candidate carries the full domain → field → subfield → topic
        breadcrumb while a coarser request stops at its own level.
        """
        path: List[str] = []
        for parent in ("domain", "field", "subfield"):
            if _TAXONOMY_LEVELS.index(parent) <= _TAXONOMY_LEVELS.index(level):
                name = (raw.get(parent) or {}).get("display_name")
                if name and name not in path:
                    path.append(name)
        name = raw.get("display_name")
        if name and name not in path:
            path.append(name)
        keywords: List[str] = []
        for keyword in raw.get("keywords") or []:
            value = keyword.get("display_name")
            if value:
                keywords.append(value)
        return {
            "id": raw.get("id"),
            "name": name,
            "level": level,
            "score": raw.get("relevance_score"),
            "works_count": raw.get("works_count"),
            "cited_by_count": raw.get("cited_by_count"),
            "description": raw.get("description"),
            "path": path,
            "keywords": keywords,
        }

    async def _classify_from_works(
        self, text: str, limit: int, level: str
    ) -> List[Dict[str, Any]]:
        """Derive taxonomy candidates from works matching free-form ``text``.

        The taxonomy endpoint's ``search`` matches only short labels; a title,
        abstract, or research question returns zero hits. Searching works and
        aggregating their assigned concepts handles that common case.
        """
        params = {
            "search": text,
            "per-page": max(limit * 5, 25),
            "mailto": get_polite_email(),
        }
        data = await self._fetch_json(OPENALEX_URL, params=params)
        grouped: Dict[str, Dict[str, Any]] = {}
        for work in data.get("results", []) or []:
            primary = work.get("primary_topic") or {}
            raw = primary.copy()
            if level != "topic":
                raw = (primary.get(level) or {}).copy()
                if level in ("subfield", "field"):
                    raw["domain"] = primary.get("domain") or {}
                if level == "subfield":
                    raw["field"] = primary.get("field") or {}
            key = raw.get("id") or raw.get("display_name")
            if not key:
                continue
            # ``primary_topic.score`` is the work's match strength for that
            # topic; the coarser levels carry no score of their own.
            score = (
                primary.get("score")
                or work.get("score")
                or raw.get("score")
                or raw.get("relevance_score")
            )
            entry = grouped.setdefault(
                key, {"raw": raw, "scores": [], "works": 0}
            )
            if isinstance(score, (int, float)):
                entry["scores"].append(score)
            entry["works"] += 1
        candidates = []
        for entry in grouped.values():
            candidate = self._taxonomy_entry(entry["raw"], level)
            candidate["score"] = (
                sum(entry["scores"]) / len(entry["scores"])
                if entry["scores"]
                else None
            )
            candidate["works_count"] = entry["works"]
            candidates.append(candidate)
        candidates.sort(key=lambda c: c["score"] or 0, reverse=True)
        return candidates[:limit]

    async def classify_topics(
        self, text: str, limit: int = 5, level: str = "topic"
    ) -> List[Dict[str, Any]]:
        """Rank OpenAlex taxonomy entries that best match ``text``.

        The taxonomy endpoint answers short labels directly. Free-form text
        that it cannot match falls back to aggregating the topics of works
        that do match, so titles and abstracts still classify sensibly.
        """
        if level not in _TAXONOMY_LEVELS:
            raise ValueError(
                f"Unknown taxonomy level {level!r}; expected one of {_TAXONOMY_LEVELS}."
            )
        collection = "topics" if level == "topic" else f"{level}s"
        params = {
            "search": text,
            "per-page": max(int(limit), 1),
            "mailto": get_polite_email(),
        }
        data = await self._fetch_json(
            f"{OPENALEX_TAXONOMY_URL}/{collection}", params=params
        )
        candidates = [
            self._taxonomy_entry(raw, level) for raw in data.get("results", []) or []
        ]
        if not candidates:
            candidates = await self._classify_from_works(text, int(limit), level)
        return candidates

    async def _resolve_work(self, identifier: str) -> Optional[dict]:
        """Fetch the raw work record, resolving DOIs/URLs to an OpenAlex id."""
        work_id = self._work_id(identifier)
        if not work_id:
            return None
        data = await self._fetch_json(
            f"{OPENALEX_URL}/{work_id}", params={"mailto": get_polite_email()}
        )
        return data or None

    @staticmethod
    def _short_id(work_url: str) -> str:
        return (work_url or "").rsplit("/", 1)[-1]

    async def citations(self, identifier: str, limit: int) -> List[Paper]:
        work = await self._resolve_work(identifier)
        if not work or not work.get("id"):
            return []
        # ``cites:`` expects an OpenAlex Work id (W...), never a doi: prefix.
        params = {
            "filter": f"cites:{self._short_id(work['id'])}",
            "per-page": limit,
            "mailto": get_polite_email(),
        }
        data = await self._fetch_json(OPENALEX_URL, params=params)
        return [self._to_paper(w) for w in data.get("results", []) or []]

    async def related(self, identifier: str, limit: int) -> List[Paper]:
        work = await self._resolve_work(identifier)
        if not work:
            return []
        related_ids = [self._short_id(u) for u in work.get("related_works") or []]
        related_ids = [rid for rid in related_ids if rid][: max(limit, 0)]
        if not related_ids:
            return []
        # ``openalex_id:`` takes a pipe-separated OR of Work ids and returns
        # full work objects, so one request hydrates the whole list.
        params = {
            "filter": f"openalex_id:{'|'.join(related_ids)}",
            "per-page": min(len(related_ids), 50),
            "mailto": get_polite_email(),
        }
        data = await self._fetch_json(OPENALEX_URL, params=params)
        return [self._to_paper(w) for w in data.get("results", []) or []]

    async def references(self, identifier: str, limit: int) -> List[Paper]:
        work = await self._resolve_work(identifier)
        if not work:
            return []
        ref_ids = [self._short_id(u) for u in work.get("referenced_works") or []]
        ref_ids = [rid for rid in ref_ids if rid][:limit]
        if not ref_ids:
            return []
        params = {
            "filter": f"openalex:{'|'.join(ref_ids)}",
            "per-page": min(limit, 50),
            "mailto": get_polite_email(),
        }
        data = await self._fetch_json(OPENALEX_URL, params=params)
        return [self._to_paper(w) for w in data.get("results", []) or []]
