"""Fetch the open-access full text of a resolved paper.

Resolution reuses the provider lookup the aggregator already performs, then
downloads the best open-access PDF and extracts its text. Nothing here papers
over a missing entitlement: a paywalled record reports ``no_oa`` instead of an
empty string, and a failed download or a missing ``pypdf`` reports ``error``.
"""

import asyncio
from typing import Any, Dict, List, Optional

from .models import Paper, ProviderError
from .pdf_text import extract_pdf_text_from_bytes
from .providers.base import ProviderBase

DEFAULT_MAX_CHARS = 20_000
ARXIV_PDF_URL = "https://arxiv.org/pdf/{id}"


async def _resolve(providers: List[ProviderBase], identifier: str) -> Optional[Paper]:
    """Ask every lookup-capable provider for the identifier, first hit wins."""
    candidates = [
        provider
        for provider in providers
        if not provider.enricher and getattr(provider, "get", None) is not None
    ]
    if not candidates:
        return None
    outcomes = await asyncio.gather(
        *(provider.get(identifier) for provider in candidates),
        return_exceptions=True,
    )
    for outcome in outcomes:
        if isinstance(outcome, Paper):
            return outcome
    return None


async def _attach_oa_links(providers: List[ProviderBase], paper: Paper) -> Paper:
    """Ask the enrichers for a better open-access PDF link.

    Mirrors the aggregator's enrichment pass, but stops at the first link so
    a paywalled record is not silently re-checked against every enricher.
    Errors are swallowed: enrichment is best-effort, a failure there must not
    block a PDF the primary source already resolved.
    """
    if paper.pdf_url or not paper.doi:
        return paper
    for provider in providers:
        if not provider.enricher:
            continue
        try:
            extra = await provider.get(paper.doi)
        except ProviderError:
            continue
        if extra and extra.pdf_url:
            paper.pdf_url = extra.pdf_url
            if extra.is_open_access is not None:
                paper.is_open_access = extra.is_open_access
            break
    return paper


def _pdf_url(paper: Paper) -> Optional[str]:
    if paper.pdf_url:
        return paper.pdf_url
    arxiv_id = (paper.ids or {}).get("arxiv")
    if arxiv_id:
        return ARXIV_PDF_URL.format(id=arxiv_id)
    return None


def _fetcher(providers: List[ProviderBase], paper: Paper) -> Any:
    for provider in providers:
        if getattr(provider, "fetcher", None) is not None:
            return provider.fetcher
    return None


async def fetch_fulltext(
    providers: List[ProviderBase],
    identifier: str,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> Dict[str, Any]:
    """Resolve ``identifier`` to an OA PDF and return its extracted text."""
    paper = await _resolve(providers, identifier)
    if paper is None:
        return {
            "identifier": identifier,
            "status": "not_found",
            "full_text": None,
            "pdf_url": None,
            "truncated": False,
        }

    await _attach_oa_links(providers, paper)

    pdf_url = _pdf_url(paper)
    if not pdf_url:
        return {
            "identifier": identifier,
            "status": "no_oa",
            "full_text": None,
            "pdf_url": None,
            "truncated": False,
            "paper": paper.to_dict(),
        }

    fetcher = _fetcher(providers, paper)
    if fetcher is None or not hasattr(fetcher, "get_bytes"):
        return {
            "identifier": identifier,
            "status": "error",
            "full_text": None,
            "pdf_url": pdf_url,
            "truncated": False,
            "error": "No fetcher available to download the PDF.",
            "paper": paper.to_dict(),
        }

    try:
        data = await fetcher.get_bytes(pdf_url, provider="fulltext")
        text = extract_pdf_text_from_bytes(data)
    except ProviderError as exc:
        return {
            "identifier": identifier,
            "status": "error",
            "full_text": None,
            "pdf_url": pdf_url,
            "truncated": False,
            "error": exc.message,
            "paper": paper.to_dict(),
        }
    except Exception as exc:  # pypdf missing, malformed PDF, ...
        return {
            "identifier": identifier,
            "status": "error",
            "full_text": None,
            "pdf_url": pdf_url,
            "truncated": False,
            "error": str(exc),
            "paper": paper.to_dict(),
        }

    truncated = len(text) > max_chars
    return {
        "identifier": identifier,
        "status": "found",
        "full_text": text[:max_chars],
        "pdf_url": pdf_url,
        "truncated": truncated,
        "chars": min(len(text), max_chars),
        "paper": paper.to_dict(),
    }
