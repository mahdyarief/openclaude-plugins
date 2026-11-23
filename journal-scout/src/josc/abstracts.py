import asyncio
from typing import Any, Dict, List, Optional

from .models import Paper
from .providers.base import ProviderBase
from .utils import normalize_doi

DEFAULT_TIMEOUT = 10.0


def _clean(value: Any) -> Optional[str]:
    text = " ".join(str(value).split()) if value else ""
    return text or None


def _identifiers(record: Dict[str, Any]) -> List[str]:
    values = [record.get("doi"), record.get("url"), record.get("identifier")]
    ids = record.get("ids") or {}
    if isinstance(ids, dict):
        values.extend(ids.values())
    return list(dict.fromkeys(v for v in values if isinstance(v, str) and v))


def _candidate_identifiers(record: Dict[str, Any]) -> List[str]:
    values = _identifiers(record)
    doi = normalize_doi(record.get("doi") or "") or None
    if doi:
        values.append(f"https://doi.org/{doi}")
    return list(dict.fromkeys(values))


def _has_lookup(provider: ProviderBase) -> bool:
    if not isinstance(provider, ProviderBase):
        return callable(getattr(provider, "get", None))
    # ``ProviderBase.get`` always exists and returns None, so a subclass that
    # never overrode it cannot resolve an identifier and must be skipped.
    return type(provider).get is not ProviderBase.get


async def _try_provider(provider: ProviderBase, record: Dict[str, Any]) -> Optional[Paper]:
    last_exc: Optional[Exception] = None
    for identifier in _candidate_identifiers(record):
        try:
            paper = await provider.get(identifier)
        except Exception as exc:
            last_exc = exc
            continue
        if paper is not None:
            return paper
    if last_exc is not None:
        raise last_exc
    return None


def _matches_record(candidate: Paper, record: Dict[str, Any], by_title: bool) -> bool:
    wanted = normalize_doi(record.get("doi") or "")
    got = normalize_doi(candidate.doi or "")
    if wanted and got:
        return wanted == got
    if not by_title:
        # The provider was asked for one specific identifier, so a result with
        # no DOI of its own is still that record. A *search* result, though,
        # must prove it is the right paper before its abstract is borrowed.
        return True
    wanted_title = _clean(record.get("title"))
    got_title = _clean(candidate.title)
    return bool(wanted_title and got_title and wanted_title.casefold() == got_title.casefold())


async def _try_search(provider: ProviderBase, title: str) -> Optional[Paper]:
    search = getattr(provider, "search", None)
    if not callable(search):
        return None
    try:
        papers = await search(title, 3)
    except Exception:
        return None
    return papers[0] if papers else None


async def resolve_abstract(
    providers: List[ProviderBase],
    paper: Optional[Dict[str, Any]] = None,
    doi: Optional[str] = None,
    title: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    record = dict(paper or {})
    if doi:
        record["doi"] = doi
    if title:
        record["title"] = title

    identifiers = [p.name for p in providers if _has_lookup(p)]
    errors: Dict[str, str] = {}
    found: Optional[Paper] = None
    source: Optional[str] = None

    for provider in providers:
        if not _has_lookup(provider):
            continue
        try:
            candidate = await asyncio.wait_for(
                _try_provider(provider, record), timeout=timeout
            )
        except (asyncio.TimeoutError, Exception) as exc:
            errors[provider.name] = str(exc) or exc.__class__.__name__
            continue
        if candidate is not None and _clean(candidate.abstract) and _matches_record(candidate, record, False):
            found, source = candidate, provider.name
            break

    if found is None:
        title_text = _clean(record.get("title"))
        if title_text:
            for provider in providers:
                if not callable(getattr(provider, "search", None)):
                    continue
                try:
                    candidate = await asyncio.wait_for(
                        _try_search(provider, title_text), timeout=timeout
                    )
                except (asyncio.TimeoutError, Exception) as exc:
                    errors[provider.name] = str(exc) or exc.__class__.__name__
                    continue
                if candidate is not None and _clean(candidate.abstract) and _matches_record(candidate, record, True):
                    found, source = candidate, provider.name
                    break

    abstract = _clean(found.abstract) if found is not None else None
    return {
        "abstract": abstract,
        "source": source,
        "status": "found" if abstract else "not_found",
        "errors": errors,
        "attempted": identifiers,
    }


async def enrich_abstracts(
    providers: List[ProviderBase],
    papers: List[Dict[str, Any]],
    timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    enriched: List[Dict[str, Any]] = []
    summary = {"found": 0, "not_found": 0, "existing": 0}

    for paper in papers:
        record = dict(paper or {})
        existing = _clean(record.get("abstract"))
        if existing:
            record["abstract"] = existing
            record["status"] = "existing"
            summary["existing"] += 1
            enriched.append(record)
            continue
        result = await resolve_abstract(providers, record, timeout=timeout)
        record["abstract"] = result["abstract"]
        record["abstract_source"] = result["source"]
        record["status"] = result["status"]
        summary[result["status"]] += 1
        enriched.append(record)

    return {"papers": enriched, "summary": summary}
