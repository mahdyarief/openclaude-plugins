# journal-scout-mcp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `journal-scout-mcp`, a single MCP server that searches and merges results from Scopus, arXiv, OpenAlex, Semantic Scholar, Crossref, DBLP, and Unpaywall through one unified `Paper` model.

**Architecture:** One MCP server with seven providers behind a shared HTTP layer. Each provider is an isolated `ProviderBase` subclass that only knows its own API and maps responses to `Paper`. An aggregator fans out searches in parallel; a merge module deduplicates by DOI then normalized title.

**Tech Stack:** Python >=3.10, `mcp>=1.0,<2`, `httpx>=0.27`, `pytest` + `pytest-asyncio` (dev), `uv` for dependency management, hatchling build backend.

## Global Constraints

- Python `requires-python = ">=3.10"`.
- Runtime dependencies exactly: `mcp>=1.0,<2` and `httpx>=0.27`. Dev extra adds `pytest>=8` and `pytest-asyncio>=0.23`.
- Package directory name: `journal_scout_mcp`. Distribution name: `journal-scout-mcp`.
- Version: `2.0.0` — keep in sync in `pyproject.toml` and `.claude-plugin/plugin.json`.
- Console script: `journal-scout-mcp = "journal_scout_mcp.server:start"`.
- All provider failures MUST surface as `ProviderError(provider, message)` and never abort a whole `search_all`.
- Elsevier 403 `ENTITLEMENTS_ERROR` and 429 `QUOTA_EXCEEDED` messages are preserved verbatim from the old `scopus-mcp` client.
- Every test uses `httpx.MockTransport`; no test touches the network.
- Run tests with: `uv run --directory . pytest -q`.
- **Working directory convention:** every relative path in this plan (`journal_scout_mcp/...`, `tests/...`, `pyproject.toml`) is relative to the plugin source root `D:/Github/agent-workspace/openclaude-plugins/scopus-mcp/`. Tasks 1-14 create the NEW package at `<root>/journal_scout_mcp/`, beside the OLD `<root>/scopus_mcp/` package. Task 15 renames the outer folder `scopus-mcp` → `journal-scout-mcp` and deletes the superseded `scopus_mcp/` folder. Do not rename the outer folder before Task 15.

## File Structure

```
journal_scout_mcp/
├── __init__.py            # empty
├── models.py              # Paper dataclass, ProviderError
├── config.py              # api_key, semantic_scholar_api_key, polite_email, cache TTLs
├── http.py                # Fetcher: get_json/get_text + retry/backoff + per-provider throttle
├── cache.py               # CacheManager (reused from scopus-mcp unchanged)
├── utils.py               # normalize_doi, normalize_title, strip_jats
├── merge.py               # dedup_key, merge_two, merge_papers
├── aggregator.py          # search_all, get_paper, get_citations
├── server.py              # 17 tools + dispatch
└── providers/
    ├── __init__.py        # build_providers, PROVIDER_NAMES
    ├── base.py            # ProviderBase ABC
    ├── scopus.py          # Scopus search/get + SciVal metrics
    ├── arxiv.py
    ├── openalex.py
    ├── semanticscholar.py
    ├── crossref.py
    ├── dblp.py
    ── unpaywall.py       # get() only (enrichment)
tests/
├── conftest.py            # fixtures
├── test_config.py
├── test_http.py
├── test_utils.py
├── test_merge.py
├── test_aggregator.py
├── fixtures/
└── test_providers/
    ├── test_crossref.py
    ├── test_dblp.py
    ├── test_unpaywall.py
    ├── test_openalex.py
    ├── test_arxiv.py
    ├── test_semanticscholar.py
    └── test_scopus.py
```

---

### Task 1: Package skeleton, config, and models

**Files:**
- Create: `journal_scout_mcp/__init__.py`
- Create: `journal_scout_mcp/models.py`
- Create: `journal_scout_mcp/config.py`
- Create: `pyproject.toml`
- Create: `tests/__init__.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `Paper` dataclass with fields (in order): `doi, title, abstract, year, authors, venue, citation_count, url, pdf_url, is_open_access, type, sources, ids`.
  - `ProviderError(Exception)` with constructor `ProviderError(provider: str, message: str)` and attributes `.provider`, `.message`.
  - `config.load_config_file() -> dict`, `config.get_api_key() -> str`, `config.get_semantic_scholar_key() -> str | None`, `config.get_polite_email() -> str`, `config.get_cache_config() -> dict`, `config.PLUGIN_DIR: Path`, `config.CONFIG_FILE: Path`.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "journal-scout-mcp"
version = "2.0.0"
description = "MCP server for multi-source journal research (Scopus, arXiv, OpenAlex, Semantic Scholar, Crossref, DBLP, Unpaywall)"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
  "mcp>=1.0,<2",
  "httpx>=0.27",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.23"]

[project.scripts]
journal-scout-mcp = "journal_scout_mcp.server:start"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["journal_scout_mcp"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Write the failing test for config precedence**

`tests/test_config.py`:

```python
import json

import journal_scout_mcp.config as config


def _write_config(tmp_path, data):
    p = tmp_path / "config.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_api_key_prefers_env(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, {"api_key": "from_file"})
    monkeypatch.setattr(config, "CONFIG_FILE", cfg)
    monkeypatch.setenv("SCOPUS_API_KEY", "from_env")
    assert config.get_api_key() == "from_env"


def test_api_key_falls_back_to_file(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, {"api_key": "from_file"})
    monkeypatch.setattr(config, "CONFIG_FILE", cfg)
    monkeypatch.delenv("SCOPUS_API_KEY", raising=False)
    assert config.get_api_key() == "from_file"


def test_api_key_missing_raises(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, {})
    monkeypatch.setattr(config, "CONFIG_FILE", cfg)
    monkeypatch.delenv("SCOPUS_API_KEY", raising=False)
    try:
        config.get_api_key()
    except ValueError as e:
        assert "api_key" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_polite_email_default(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, {})
    monkeypatch.setattr(config, "CONFIG_FILE", cfg)
    monkeypatch.delenv("JOURNAL_SCOUT_EMAIL", raising=False)
    assert config.get_polite_email() == "anonymous@example.com"


def test_semantic_scholar_key_optional(monkeypatch, tmp_path):
    cfg = _write_config(tmp_path, {})
    monkeypatch.setattr(config, "CONFIG_FILE", cfg)
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
    assert config.get_semantic_scholar_key() is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run --directory . pytest tests/test_config.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'journal_scout_mcp'`.

- [ ] **Step 4: Write `journal_scout_mcp/__init__.py` and `models.py`**

`journal_scout_mcp/__init__.py`: (empty file)

`journal_scout_mcp/models.py`:

```python
from dataclasses import dataclass, field


@dataclass
class Paper:
    doi: str | None = None
    title: str = ""
    abstract: str | None = None
    year: int | None = None
    authors: list[str] = field(default_factory=list)
    venue: str | None = None
    citation_count: int | None = None
    url: str | None = None
    pdf_url: str | None = None
    is_open_access: bool | None = None
    type: str | None = None
    sources: list[str] = field(default_factory=list)
    ids: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "doi": self.doi,
            "title": self.title,
            "abstract": self.abstract,
            "year": self.year,
            "authors": self.authors,
            "venue": self.venue,
            "citation_count": self.citation_count,
            "url": self.url,
            "pdf_url": self.pdf_url,
            "is_open_access": self.is_open_access,
            "type": self.type,
            "sources": self.sources,
            "ids": self.ids,
        }


class ProviderError(Exception):
    def __init__(self, provider: str, message: str):
        self.provider = provider
        self.message = message
        super().__init__(f"[{provider}] {message}")
```

- [ ] **Step 5: Write `journal_scout_mcp/config.py`**

```python
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

PLUGIN_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = PLUGIN_DIR / "config.json"
DEFAULT_CACHE_DIR = PLUGIN_DIR / ".cache"


def load_config_file() -> Dict[str, Any]:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def get_api_key() -> str:
    api_key = os.getenv("SCOPUS_API_KEY")
    if api_key:
        return api_key
    api_key = load_config_file().get("api_key")
    if not api_key:
        raise ValueError(
            "Elsevier API key not found. Set 'SCOPUS_API_KEY' or add "
            "'api_key' to config.json next to this plugin."
        )
    return api_key


def get_semantic_scholar_key() -> Optional[str]:
    return os.getenv("SEMANTIC_SCHOLAR_API_KEY") or load_config_file().get(
        "semantic_scholar_api_key"
    )


def get_polite_email() -> str:
    return (
        os.getenv("JOURNAL_SCOUT_EMAIL")
        or load_config_file().get("polite_email")
        or "anonymous@example.com"
    )


def get_cache_config() -> Dict[str, Any]:
    config = load_config_file()
    cache_dir = os.getenv("JOURNAL_SCOUT_CACHE_DIR") or config.get(
        "cache_dir", str(DEFAULT_CACHE_DIR)
    )
    return {"dir": cache_dir, "default": 86400}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run --directory . pytest tests/test_config.py -q`
Expected: PASS (5 passed).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml journal_scout_mcp/__init__.py journal_scout_mcp/models.py journal_scout_mcp/config.py tests/__init__.py tests/test_config.py
git commit -m "feat(journal-scout): package skeleton, Paper model, config"
```

---

### Task 2: Shared HTTP layer with retry/backoff and per-provider throttle

**Files:**
- Create: `journal_scout_mcp/http.py`
- Create: `tests/conftest.py`
- Create: `tests/test_http.py`
- Modify: `pyproject.toml` (dev extra already includes pytest-asyncio from Task 1)

**Interfaces:**
- Consumes: `models.ProviderError`.
- Produces:
  - `MAX_BACKOFF_SECONDS = 60`
  - `class Fetcher` with `__init__(self, client: Optional[httpx.AsyncClient] = None)`, `async get_json(self, url, params=None, headers=None, provider=None) -> dict`, `async get_text(self, url, params=None, headers=None, provider=None) -> str`, `async close(self)`, attribute `client`.
  - `MIN_INTERVALS: Dict[str, float]` (`arxiv: 3.0`, `semanticscholar: 1.0`; missing provider = 0.0).

- [ ] **Step 1: Write the failing test**

`tests/test_http.py`:

```python
import httpx
import pytest

from journal_scout_mcp.http import Fetcher
from journal_scout_mcp.models import ProviderError


def _fetcher(handler):
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return Fetcher(client=client)


async def test_get_json_returns_payload():
    def handler(request):
        return httpx.Response(200, json={"ok": True})

    f = _fetcher(handler)
    try:
        assert await f.get_json("https://example.test/x", provider="crossref") == {"ok": True}
    finally:
        await f.close()


async def test_retries_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500, text="boom")
        return httpx.Response(200, json={"ok": True})

    f = _fetcher(handler)
    try:
        assert await f.get_json("https://example.test/x", provider="dblp") == {"ok": True}
        assert calls["n"] == 2
    finally:
        await f.close()


async def test_permanent_500_raises_provider_error():
    def handler(request):
        return httpx.Response(500, text="boom")

    f = _fetcher(handler)
    try:
        with pytest.raises(ProviderError) as exc:
            await f.get_json("https://example.test/x", provider="dblp")
        assert exc.value.provider == "dblp"
    finally:
        await f.close()


async def test_elsevier_entitlement_error_message():
    def handler(request):
        return httpx.Response(
            403, headers={"X-ELS-Status": "ENTITLEMENTS_ERROR"}, text="forbidden"
        )

    f = _fetcher(handler)
    try:
        with pytest.raises(ProviderError) as exc:
            await f.get_json("https://api.elsevier.com/x", provider="scopus")
        assert "ENTITLEMENTS_ERROR" in str(exc.value)
    finally:
        await f.close()


async def test_elsevier_quota_error_message():
    def handler(request):
        return httpx.Response(
            429, headers={"X-ELS-Status": "QUOTA_EXCEEDED"}, text="slow down"
        )

    f = _fetcher(handler)
    try:
        with pytest.raises(ProviderError) as exc:
            await f.get_json("https://api.elsevier.com/x", provider="scopus")
        assert "quota" in str(exc.value).lower()
    finally:
        await f.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory . pytest tests/test_http.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'journal_scout_mcp.http'`.

- [ ] **Step 3: Write `journal_scout_mcp/http.py`**

```python
import asyncio
import time
from typing import Any, Dict, Optional

import httpx

from .models import ProviderError

MAX_BACKOFF_SECONDS = 60
MIN_INTERVALS: Dict[str, float] = {"arxiv": 3.0, "semanticscholar": 1.0}
MAX_RETRIES = 3


class Fetcher:
    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.client = client or httpx.AsyncClient(timeout=30.0)
        self._last_call: Dict[str, float] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def _lock(self, provider: str) -> asyncio.Lock:
        if provider not in self._locks:
            self._locks[provider] = asyncio.Lock()
        return self._locks[provider]

    async def _throttle(self, provider: Optional[str]) -> None:
        if not provider:
            return
        interval = MIN_INTERVALS.get(provider, 0.0)
        if interval <= 0:
            return
        async with self._lock(provider):
            elapsed = time.monotonic() - self._last_call.get(provider, 0.0)
            wait = interval - elapsed
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call[provider] = time.monotonic()

    async def _request(self, url, params, headers, provider):
        backoff = 1.0
        retries = MAX_RETRIES
        last_exc: Optional[Exception] = None
        last_status: Optional[int] = None
        while retries > 0:
            await self._throttle(provider)
            try:
                response = await self.client.get(url, params=params, headers=headers)
            except httpx.HTTPError as e:
                last_exc = e
                retries -= 1
                await asyncio.sleep(min(backoff, MAX_BACKOFF_SECONDS))
                backoff *= 2
                continue

            last_status = response.status_code
            if last_status == 429:
                retries -= 1
                if retries <= 0:
                    break
                els_status = response.headers.get("X-ELS-Status", "")
                if "QUOTA_EXCEEDED" in els_status:
                    raise ProviderError(
                        provider or "unknown",
                        "Elsevier weekly quota exceeded (QUOTA_EXCEEDED). "
                        "Wait for the weekly reset or raise the quota.",
                    )
                await asyncio.sleep(min(backoff, MAX_BACKOFF_SECONDS))
                backoff *= 2
                continue
            if last_status == 403:
                els_status = response.headers.get("X-ELS-Status", "") or ""
                if "ENTITLEMENTS_ERROR" in els_status:
                    raise ProviderError(
                        provider or "unknown",
                        "Elsevier returned ENTITLEMENTS_ERROR: the API key is "
                        "valid, but this institution is not entitled to the "
                        "requested resource. SciVal endpoints need a SciVal "
                        "subscription; Scopus-only tools keep working.",
                    )
                raise ProviderError(
                    provider or "unknown",
                    f"Access forbidden (403). X-ELS-Status: {els_status or 'unknown'}",
                )
            if last_status >= 500:
                retries -= 1
                if retries <= 0:
                    break
                await asyncio.sleep(min(backoff, MAX_BACKOFF_SECONDS))
                backoff *= 2
                continue
            if last_status >= 400:
                raise ProviderError(
                    provider or "unknown", f"HTTP {last_status}: {response.text[:200]}"
                )
            return response

        if last_exc:
            raise ProviderError(provider or "unknown", f"Request failed after retries ({last_exc})")
        raise ProviderError(
            provider or "unknown", f"Request failed after retries (last status={last_status})"
        )

    async def get_json(self, url, params=None, headers=None, provider=None) -> Dict[str, Any]:
        response = await self._request(url, params, headers, provider)
        return response.json()

    async def get_text(self, url, params=None, headers=None, provider=None) -> str:
        response = await self._request(url, params, headers, provider)
        return response.text

    async def close(self) -> None:
        await self.client.aclose()
```

- [ ] **Step 4: Write `tests/conftest.py`**

```python
import httpx
import pytest

from journal_scout_mcp.config import get_polite_email


@pytest.fixture
def polite_email():
    return "test@example.com"


class FakeFetcher:
    """Routes every GET to a handler that returns a canned httpx.Response."""

    def __init__(self, handler):
        self._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def _get(self, url, params=None, headers=None):
        return await self._client.get(url, params=params, headers=headers)

    async def get_json(self, url, params=None, headers=None, provider=None):
        r = await self._get(url, params, headers)
        return r.json()

    async def get_text(self, url, params=None, headers=None, provider=None):
        r = await self._get(url, params, headers)
        return r.text

    async def close(self):
        await self._client.aclose()


@pytest.fixture
def make_fetcher():
    def _make(handler):
        return FakeFetcher(handler)

    return _make
```

Note: `FakeFetcher` lets provider tests run without the throttle/backoff logic, using a handler that inspects `request.url` to return the right fixture per endpoint.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --directory . pytest tests/test_http.py -q`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git add journal_scout_mcp/http.py tests/conftest.py tests/test_http.py
git commit -m "feat(journal-scout): shared HTTP fetcher with retry and throttle"
```

---

### Task 3: Cache and normalization utilities

**Files:**
- Create: `journal_scout_mcp/cache.py`
- Create: `journal_scout_mcp/utils.py`
- Create: `tests/test_utils.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `class CacheManager` with `__init__(self, cache_dir=".cache", expiration_seconds=86400)`, `get(self, url, params=None)`, `set(self, url, data, params=None, ttl=None)`.
  - `normalize_doi(doi: Optional[str]) -> Optional[str]` — lowercase, strip `https://doi.org/`, `http://doi.org/`, `doi:` prefixes; `None` for empty.
  - `normalize_title(title: Optional[str]) -> str` — lowercase, strip non-alphanumeric except spaces, collapse whitespace.
  - `strip_jats(value: Optional[str]) -> Optional[str]` — drop `<...>` tags, unescape HTML entities, `None` passthrough.

- [ ] **Step 1: Write the failing test**

`tests/test_utils.py`:

```python
from journal_scout_mcp.utils import normalize_doi, normalize_title, strip_jats


def test_normalize_doi_strips_prefixes():
    assert normalize_doi("https://doi.org/10.1234/ABC") == "10.1234/abc"
    assert normalize_doi("doi:10.1234/ABC") == "10.1234/abc"
    assert normalize_doi("10.1234/ABC") == "10.1234/abc"


def test_normalize_doi_empty_is_none():
    assert normalize_doi("") is None
    assert normalize_doi(None) is None


def test_normalize_title_drops_punctuation():
    assert normalize_title("Attention Is All You Need!") == "attention is all you need"
    assert normalize_title("Deep   Learning: A Survey") == "deep learning a survey"


def test_strip_jats():
    assert strip_jats("<jats:p>Hello &amp; bye</jats:p>") == "Hello & bye"
    assert strip_jats(None) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory . pytest tests/test_utils.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'journal_scout_mcp.utils'`.

- [ ] **Step 3: Write `journal_scout_mcp/utils.py`**

```python
import html
import re
from typing import Optional

_DOI_PREFIXES = ("https://doi.org/", "http://doi.org/", "doi:")
_NON_ALNUM = re.compile(r"[^a-z0-9\s]")
_WHITESPACE = re.compile(r"\s+")
_TAG = re.compile(r"<[^>]+>")


def normalize_doi(doi: Optional[str]) -> Optional[str]:
    if not doi:
        return None
    value = doi.strip().lower()
    for prefix in _DOI_PREFIXES:
        if value.startswith(prefix):
            value = value[len(prefix):]
    return value or None


def normalize_title(title: Optional[str]) -> str:
    if not title:
        return ""
    value = title.strip().lower()
    value = _NON_ALNUM.sub(" ", value)
    return _WHITESPACE.sub(" ", value).strip()


def strip_jats(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = _TAG.sub(" ", value)
    return _WHITESPACE.sub(" ", html.unescape(text)).strip() or None
```

- [ ] **Step 4: Write `journal_scout_mcp/cache.py`**

Copy the existing `scopus-mcp/scopus_mcp/cache.py` verbatim:

```python
import json
import hashlib
import time
from pathlib import Path
from typing import Optional, Dict, Any, Union


class CacheManager:
    def __init__(self, cache_dir: Union[str, Path] = ".cache", expiration_seconds: int = 86400):
        self.cache_dir = Path(cache_dir).resolve()
        self.expiration_seconds = expiration_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, url: str, params: Optional[Dict[str, Any]] = None) -> str:
        key_str = url
        if params:
            key_str += json.dumps(params, sort_keys=True, default=str)
        return hashlib.sha256(key_str.encode("utf-8")).hexdigest()

    def get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        key = self._get_cache_key(url, params)
        file_path = self.cache_dir / f"{key}.json"
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                cached_entry = json.load(f)
            timestamp = cached_entry.get("timestamp", 0)
            ttl = cached_entry.get("ttl", self.expiration_seconds)
            if time.time() - timestamp > ttl:
                return None
            return cached_entry.get("data")
        except (json.JSONDecodeError, IOError):
            return None

    def set(self, url: str, data: Any, params: Optional[Dict[str, Any]] = None, ttl: Optional[int] = None) -> None:
        key = self._get_cache_key(url, params)
        file_path = self.cache_dir / f"{key}.json"
        entry = {
            "timestamp": time.time(),
            "ttl": ttl if ttl is not None else self.expiration_seconds,
            "data": data,
        }
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(entry, f)
        except IOError:
            pass
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --directory . pytest tests/test_utils.py -q`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add journal_scout_mcp/cache.py journal_scout_mcp/utils.py tests/test_utils.py
git commit -m "feat(journal-scout): cache reuse and DOI/title normalization"
```

---

### Task 4: Merge and dedup

**Files:**
- Create: `journal_scout_mcp/merge.py`
- Create: `tests/test_merge.py`

**Interfaces:**
- Consumes: `models.Paper`, `utils.normalize_doi`, `utils.normalize_title`.
- Produces:
  - `dedup_key(paper: Paper) -> str` — `"doi:<normalized>"` or `"title:<normalized>"`.
  - `merge_two(a: Paper, b: Paper) -> Paper` — combines two papers judged equal.
  - `merge_papers(papers: List[Paper]) -> List[Paper]` — dedups, then sorts by `citation_count` desc, `year` desc, `title` asc.

- [ ] **Step 1: Write the failing test**

`tests/test_merge.py`:

```python
from journal_scout_mcp.merge import dedup_key, merge_papers, merge_two
from journal_scout_mcp.models import Paper


def test_dedup_key_prefers_doi():
    p = Paper(doi="https://doi.org/10.1/AbC", title="Whatever")
    assert dedup_key(p) == "doi:10.1/abc"


def test_dedup_key_falls_back_to_title():
    p = Paper(title="Attention Is All You Need!")
    assert dedup_key(p) == "title:attention is all you need"


def test_merge_two_takes_max_citations_and_unions_sources():
    a = Paper(doi="10.1/x", title="Paper", citation_count=5, sources=["scopus"], ids={"scopus": "1"})
    b = Paper(doi="10.1/x", title="Paper", citation_count=9, abstract="abs", sources=["openalex"], ids={"openalex": "W1"})
    merged = merge_two(a, b)
    assert merged.citation_count == 9
    assert merged.abstract == "abs"
    assert set(merged.sources) == {"scopus", "openalex"}
    assert merged.ids == {"scopus": "1", "openalex": "W1"}


def test_merge_papers_dedups_and_sorts():
    papers = [
        Paper(doi="10.1/a", title="A", citation_count=1, sources=["scopus"]),
        Paper(doi="10.1/b", title="B", citation_count=10, sources=["openalex"]),
        Paper(doi="10.1/a", title="A", citation_count=4, sources=["crossref"]),
    ]
    merged = merge_papers(papers)
    assert len(merged) == 2
    assert merged[0].title == "B"
    assert merged[1].citation_count == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory . pytest tests/test_merge.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'journal_scout_mcp.merge'`.

- [ ] **Step 3: Write `journal_scout_mcp/merge.py`**

```python
from typing import List, Optional

from .models import Paper
from .utils import normalize_doi, normalize_title


def dedup_key(paper: Paper) -> str:
    doi = normalize_doi(paper.doi)
    if doi:
        return f"doi:{doi}"
    return f"title:{normalize_title(paper.title)}"


def _pick_text(*values: Optional[str]) -> Optional[str]:
    for value in values:
        if value:
            return value
    return None


def merge_two(a: Paper, b: Paper) -> Paper:
    counts = [c for c in (a.citation_count, b.citation_count) if c is not None]
    sources: List[str] = []
    for source in a.sources + b.sources:
        if source not in sources:
            sources.append(source)
    ids = dict(a.ids)
    ids.update(b.ids)
    return Paper(
        doi=_pick_text(a.doi, b.doi),
        title=_pick_text(a.title, b.title) or "",
        abstract=_pick_text(a.abstract, b.abstract),
        year=a.year or b.year,
        authors=a.authors or b.authors,
        venue=_pick_text(a.venue, b.venue),
        citation_count=max(counts) if counts else None,
        url=_pick_text(a.url, b.url),
        pdf_url=_pick_text(a.pdf_url, b.pdf_url),
        is_open_access=a.is_open_access if a.is_open_access is not None else b.is_open_access,
        type=_pick_text(a.type, b.type),
        sources=sources,
        ids=ids,
    )


def merge_papers(papers: List[Paper]) -> List[Paper]:
    merged: dict[str, Paper] = {}
    for paper in papers:
        key = dedup_key(paper)
        if key in merged:
            merged[key] = merge_two(merged[key], paper)
        else:
            merged[key] = paper
    result = list(merged.values())
    result.sort(key=lambda p: (-(p.citation_count or 0), -(p.year or 0), p.title or ""))
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory . pytest tests/test_merge.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add journal_scout_mcp/merge.py tests/test_merge.py
git commit -m "feat(journal-scout): DOI-first merge and dedup"
```

---

### Task 5: Provider base class and registry

**Files:**
- Create: `journal_scout_mcp/providers/__init__.py`
- Create: `journal_scout_mcp/providers/base.py`
- Create: `tests/test_providers/__init__.py`
- Create: `tests/test_providers/test_base.py`

**Interfaces:**
- Consumes: `models.Paper`, `models.ProviderError`.
- Produces:
  - `class ProviderBase` with class attributes `name: str = ""` and `supports_search: bool = True`, `__init__(self, fetcher, config: Optional[Dict[str, Any]] = None)`, and async stubs `search(self, query, limit, year_from=None, year_to=None, tech_only=False) -> List[Paper]`, `get(self, identifier) -> Optional[Paper]`, `citations(self, identifier, limit) -> List[Paper]`.
  - Shared fetch helpers on the base class (every provider uses these instead of defining its own): `async _fetch_json(self, url, params=None, headers=None, provider=None) -> dict` and `async _fetch_text(self, url, params=None, headers=None, provider=None) -> str`. Both accept either a shared `Fetcher` (has `get_json`/`get_text`) or a bare `httpx.AsyncClient` (has `get`); they branch on `hasattr(self.fetcher, "get_json")`. The `provider` argument defaults to `self.name` so per-provider throttling still applies.
  - `PROVIDER_NAMES: List[str]` and `build_providers(fetcher, config=None) -> List[ProviderBase]` in `providers/__init__.py`.

- [ ] **Step 1: Write the failing test**

`tests/test_providers/test_base.py`:

```python
from journal_scout_mcp.providers.base import ProviderBase


class DummyProvider(ProviderBase):
    name = "dummy"


async def test_default_methods_return_empty():
    p = DummyProvider(fetcher=None)
    assert p.supports_search is True
    assert await p.search("anything", 5) == []
    assert await p.get("anything") is None
    assert await p.citations("anything", 5) == []


def test_name_and_search_flag():
    p = DummyProvider(fetcher=None)
    assert p.name == "dummy"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory . pytest tests/test_providers/test_base.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'journal_scout_mcp.providers'`.

- [ ] **Step 3: Write `journal_scout_mcp/providers/base.py`**

```python
from typing import Any, Dict, List, Optional

from ..models import Paper


class ProviderBase:
    name: str = ""
    supports_search: bool = True

    def __init__(self, fetcher: Any, config: Optional[Dict[str, Any]] = None):
        self.fetcher = fetcher
        self.config = config or {}

    async def _fetch_json(self, url, params=None, headers=None, provider=None) -> Dict[str, Any]:
        provider = provider or self.name
        if hasattr(self.fetcher, "get_json"):
            return await self.fetcher.get_json(url, params=params, headers=headers, provider=provider)
        response = await self.fetcher.get(url, params=params, headers=headers)
        return response.json()

    async def _fetch_text(self, url, params=None, headers=None, provider=None) -> str:
        provider = provider or self.name
        if hasattr(self.fetcher, "get_text"):
            return await self.fetcher.get_text(url, params=params, headers=headers, provider=provider)
        response = await self.fetcher.get(url, params=params, headers=headers)
        return response.text

    async def search(
        self,
        query: str,
        limit: int,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        tech_only: bool = False,
    ) -> List[Paper]:
        return []

    async def get(self, identifier: str) -> Optional[Paper]:
        return None

    async def citations(self, identifier: str, limit: int) -> List[Paper]:
        return []
```

- [ ] **Step 4: Write `journal_scout_mcp/providers/__init__.py`**

```python
from typing import Any, Dict, List, Optional

from .base import ProviderBase

PROVIDER_NAMES: List[str] = [
    "scopus",
    "arxiv",
    "openalex",
    "semanticscholar",
    "crossref",
    "dblp",
    "unpaywall",
]


def build_providers(fetcher: Any, config: Optional[Dict[str, Any]] = None) -> List[ProviderBase]:
    from .scopus import ScopusProvider
    from .arxiv import ArxivProvider
    from .openalex import OpenAlexProvider
    from .semanticscholar import SemanticScholarProvider
    from .crossref import CrossrefProvider
    from .dblp import DblpProvider
    from .unpaywall import UnpaywallProvider

    classes = [
        ScopusProvider,
        ArxivProvider,
        OpenAlexProvider,
        SemanticScholarProvider,
        CrossrefProvider,
        DblpProvider,
        UnpaywallProvider,
    ]
    return [cls(fetcher, config) for cls in classes]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --directory . pytest tests/test_providers/test_base.py -q`
Expected: PASS (2 passed). `build_providers` imports provider modules lazily, so this passes before the later provider tasks exist.

- [ ] **Step 6: Commit**

```bash
git add journal_scout_mcp/providers/__init__.py journal_scout_mcp/providers/base.py tests/test_providers/__init__.py tests/test_providers/test_base.py
git commit -m "feat(journal-scout): ProviderBase ABC and registry"
```

---

### Task 6: Crossref provider

**Files:**
- Create: `journal_scout_mcp/providers/crossref.py`
- Create: `tests/fixtures/crossref_search.json`
- Create: `tests/test_providers/test_crossref.py`

**Interfaces:**
- Consumes: `ProviderBase`, `config.get_polite_email`, `utils.normalize_doi`, `utils.strip_jats`.
- Produces:
  - `class CrossrefProvider(ProviderBase)` with `name = "crossref"`, `supports_search = True`.
  - `search(self, query, limit, year_from=None, year_to=None, tech_only=False) -> List[Paper]` maps `https://api.crossref.org/works?query=<q>&rows=<limit>&mailto=<email>` (`message.items[]`).
  - `get(self, identifier) -> Optional[Paper]` maps `https://api.crossref.org/works/<doi>` (`message`).

- [ ] **Step 1: Write the fixture**

`tests/fixtures/crossref_search.json`:

```json
{
  "message": {
    "items": [
      {
        "DOI": "10.1162/neco.1997.9.8.1735",
        "title": ["Long Short-Term Memory"],
        "author": [{"given": "Sepp", "family": "Hochreiter"}, {"given": "Jürgen", "family": "Schmidhuber"}],
        "container-title": ["Neural Computation"],
        "published": {"date-parts": [[1997, 11, 15]]},
        "abstract": "<jats:p>We propose LSTM.</jats:p>",
        "is-referenced-by-count": 42000,
        "URL": "https://doi.org/10.1162/neco.1997.9.8.1735",
        "type": "journal-article"
      }
    ]
  }
}
```

- [ ] **Step 2: Write the failing test**

`tests/test_providers/test_crossref.py`:

```python
import json
from pathlib import Path

import httpx

from journal_scout_mcp.providers.crossref import CrossrefProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"


async def test_search_maps_items_to_paper(monkeypatch):
    payload = json.loads((FIXTURES / "crossref_search.json").read_text(encoding="utf-8"))

    def handler(request):
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CrossrefProvider(client)
    try:
        papers = await provider.search("long short-term memory", 5)
        assert len(papers) == 1
        p = papers[0]
        assert p.doi == "10.1162/neco.1997.9.8.1735"
        assert p.title == "Long Short-Term Memory"
        assert p.authors == ["Sepp Hochreiter", "Jürgen Schmidhuber"]
        assert p.venue == "Neural Computation"
        assert p.year == 1997
        assert p.citation_count == 42000
        assert p.abstract == "We propose LSTM."
        assert p.sources == ["crossref"]
        assert p.ids["crossref"] == "10.1162/neco.1997.9.8.1735"
    finally:
        await client.aclose()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run --directory . pytest tests/test_providers/test_crossref.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'journal_scout_mcp.providers.crossref'`.

- [ ] **Step 4: Write `journal_scout_mcp/providers/crossref.py`**

The provider accepts either a shared `Fetcher` (production, from `build_providers`) or a bare `httpx.AsyncClient` (tests). It calls the inherited `self._fetch_json(...)` from `ProviderBase`, which branches on `hasattr(self.fetcher, "get_json")`.

```python
from typing import List, Optional

from ..config import get_polite_email
from ..models import Paper
from ..utils import normalize_doi, strip_jats
from .base import ProviderBase

CROSSREF_URL = "https://api.crossref.org/works"


class CrossrefProvider(ProviderBase):
    name = "crossref"
    supports_search = True

    @staticmethod
    def _to_paper(item):
        authors = []
        for a in item.get("author", []) or []:
            name = " ".join(x for x in [a.get("given"), a.get("family")] if x)
            if name:
                authors.append(name)
        year = None
        for key in ("published", "published-print", "published-online"):
            parts = (item.get(key) or {}).get("date-parts") or []
            if parts and parts[0]:
                year = parts[0][0]
                break
        doi = normalize_doi(item.get("DOI"))
        return Paper(
            doi=doi,
            title=(item.get("title") or [""])[0],
            abstract=strip_jats(item.get("abstract")),
            year=year,
            authors=authors,
            venue=(item.get("container-title") or [None])[0],
            citation_count=item.get("is-referenced-by-count"),
            url=item.get("URL"),
            type=item.get("type"),
            sources=["crossref"],
            ids={"crossref": item.get("DOI")} if item.get("DOI") else {},
        )

    async def search(self, query: str, limit: int, year_from=None, year_to=None, tech_only=False) -> List[Paper]:
        params = {"query": query, "rows": limit, "mailto": get_polite_email()}
        data = await self._fetch_json(CROSSREF_URL, params=params)
        items = (data.get("message") or {}).get("items") or []
        return [self._to_paper(i) for i in items]

    async def get(self, identifier: str) -> Optional[Paper]:
        doi = normalize_doi(identifier)
        if not doi:
            return None
        data = await self._fetch_json(f"{CROSSREF_URL}/{doi}", params={"mailto": get_polite_email()})
        message = data.get("message")
        return self._to_paper(message) if message else None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --directory . pytest tests/test_providers/test_crossref.py -q`
Expected: PASS (1 passed).

- [ ] **Step 6: Commit**

```bash
git add journal_scout_mcp/providers/crossref.py tests/fixtures/crossref_search.json tests/test_providers/test_crossref.py
git commit -m "feat(journal-scout): Crossref provider"
```

---

### Task 7: DBLP provider

**Files:**
- Create: `journal_scout_mcp/providers/dblp.py`
- Create: `tests/fixtures/dblp_search.json`
- Create: `tests/test_providers/test_dblp.py`

**Interfaces:**
- Consumes: `ProviderBase`.
- Produces:
  - `class DblpProvider(ProviderBase)` with `name = "dblp"`, `supports_search = True`.
  - `search(self, query, limit, year_from=None, year_to=None, tech_only=False) -> List[Paper]` maps `https://dblp.org/search/publ/api?q=<q>&format=json&h=<limit>` (`result.hits.hit[].info`). DBLP has no identifier lookup, so `get()` stays the base no-op. DBLP indexes computer-science venues exclusively, so `tech_only` is an accepted no-op here — no extra filter is applied.

- [ ] **Step 1: Write the fixture**

`tests/fixtures/dblp_search.json`:

```json
{
  "result": {
    "hits": {
      "hit": [
        {
          "info": {
            "title": "Attention is All you Need.",
            "authors": {"author": [{"text": "Ashish Vaswani"}, {"text": "Noam Shazeer"}]},
            "venue": "NIPS",
            "year": "2017",
            "type": "Conference and Workshop Papers",
            "doi": "10.5555/3295222.3295349",
            "ee": "https://doi.org/10.5555/3295222.3295349"
          }
        }
      ]
    }
  }
}
```

- [ ] **Step 2: Write the failing test**

`tests/test_providers/test_dblp.py`:

```python
import json
from pathlib import Path

import httpx

from journal_scout_mcp.providers.dblp import DblpProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"


async def test_search_maps_hits_to_paper():
    payload = json.loads((FIXTURES / "dblp_search.json").read_text(encoding="utf-8"))

    def handler(request):
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = DblpProvider(client)
    try:
        papers = await provider.search("attention is all you need", 5)
        assert len(papers) == 1
        p = papers[0]
        assert p.doi == "10.5555/3295222.3295349"
        assert p.title == "Attention is All you Need"
        assert p.authors == ["Ashish Vaswani", "Noam Shazeer"]
        assert p.venue == "NIPS"
        assert p.year == 2017
        assert p.sources == ["dblp"]
        assert p.ids["dblp"] == "10.5555/3295222.3295349"
    finally:
        await client.aclose()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run --directory . pytest tests/test_providers/test_dblp.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'journal_scout_mcp.providers.dblp'`.

- [ ] **Step 4: Write `journal_scout_mcp/providers/dblp.py`**

```python
from typing import List

from ..models import Paper
from ..utils import normalize_doi
from .base import ProviderBase

DBLP_URL = "https://dblp.org/search/publ/api"


class DblpProvider(ProviderBase):
    name = "dblp"
    supports_search = True

    @staticmethod
    def _to_paper(info):
        authors_raw = (info.get("authors") or {}).get("author") or []
        if isinstance(authors_raw, dict):
            authors_raw = [authors_raw]
        authors = []
        for a in authors_raw:
            text = a.get("text") if isinstance(a, dict) else a
            if text:
                authors.append(text)
        doi = normalize_doi(info.get("doi"))
        year = info.get("year")
        return Paper(
            doi=doi,
            title=(info.get("title") or "").rstrip("."),
            year=int(year) if year else None,
            authors=authors,
            venue=info.get("venue"),
            url=info.get("ee"),
            type=info.get("type"),
            sources=["dblp"],
            ids={"dblp": info.get("doi")} if info.get("doi") else {},
        )

    async def search(self, query: str, limit: int, year_from=None, year_to=None, tech_only=False) -> List[Paper]:
        params = {"q": query, "format": "json", "h": limit}
        data = await self._fetch_json(DBLP_URL, params=params)
        hits = ((data.get("result") or {}).get("hits") or {}).get("hit") or []
        results = []
        for hit in hits:
            info = hit.get("info") or {}
            if year_from and info.get("year") and int(info["year"]) < year_from:
                continue
            if year_to and info.get("year") and int(info["year"]) > year_to:
                continue
            results.append(self._to_paper(info))
        return results
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --directory . pytest tests/test_providers/test_dblp.py -q`
Expected: PASS (1 passed).

- [ ] **Step 6: Commit**

```bash
git add journal_scout_mcp/providers/dblp.py tests/fixtures/dblp_search.json tests/test_providers/test_dblp.py
git commit -m "feat(journal-scout): DBLP provider"
```

---

### Task 8: Unpaywall provider (enrichment only)

**Files:**
- Create: `journal_scout_mcp/providers/unpaywall.py`
- Create: `tests/fixtures/unpaywall_lookup.json`
- Create: `tests/test_providers/test_unpaywall.py`

**Interfaces:**
- Consumes: `ProviderBase`, `config.get_polite_email`, `utils.normalize_doi`.
- Produces:
  - `class UnpaywallProvider(ProviderBase)` with `name = "unpaywall"`, `supports_search = False`.
  - `get(self, identifier) -> Optional[Paper]` maps `https://api.unpaywall.org/v2/<doi>?email=<email>` to a `Paper` carrying `is_open_access`, `pdf_url`, `url`, `venue`, `year`. Returns `None` when the DOI is empty.

- [ ] **Step 1: Write the fixture**

`tests/fixtures/unpaywall_lookup.json`:

```json
{
  "doi": "10.1162/neco.1997.9.8.1735",
  "is_oa": true,
  "oa_status": "green",
  "title": "Long Short-Term Memory",
  "year": 1997,
  "journal_name": "Neural Computation",
  "best_oa_location": {
    "url_for_pdf": "https://example.org/lstm.pdf",
    "url_for_landing_page": "https://example.org/lstm",
    "host_type": "repository",
    "version": "acceptedVersion"
  }
}
```

- [ ] **Step 2: Write the failing test**

`tests/test_providers/test_unpaywall.py`:

```python
import json
from pathlib import Path

import httpx

from journal_scout_mcp.providers.unpaywall import UnpaywallProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"


async def test_get_maps_open_access_location():
    payload = json.loads((FIXTURES / "unpaywall_lookup.json").read_text(encoding="utf-8"))

    def handler(request):
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = UnpaywallProvider(client)
    try:
        p = await provider.get("10.1162/neco.1997.9.8.1735")
        assert p.is_open_access is True
        assert p.pdf_url == "https://example.org/lstm.pdf"
        assert p.url == "https://example.org/lstm"
        assert p.venue == "Neural Computation"
        assert p.year == 1997
        assert p.sources == ["unpaywall"]
    finally:
        await client.aclose()


async def test_get_empty_doi_returns_none():
    provider = UnpaywallProvider(None)
    assert await provider.get("") is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run --directory . pytest tests/test_providers/test_unpaywall.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'journal_scout_mcp.providers.unpaywall'`.

- [ ] **Step 4: Write `journal_scout_mcp/providers/unpaywall.py`**

```python
from typing import Optional

from ..config import get_polite_email
from ..models import Paper
from ..utils import normalize_doi
from .base import ProviderBase

UNPAYWALL_URL = "https://api.unpaywall.org/v2"


class UnpaywallProvider(ProviderBase):
    name = "unpaywall"
    supports_search = False

    async def get(self, identifier: str) -> Optional[Paper]:
        doi = normalize_doi(identifier)
        if not doi:
            return None
        data = await self._fetch_json(f"{UNPAYWALL_URL}/{doi}", params={"email": get_polite_email()})
        best = data.get("best_oa_location") or {}
        return Paper(
            doi=doi,
            title=data.get("title") or "",
            year=data.get("year"),
            venue=data.get("journal_name"),
            pdf_url=best.get("url_for_pdf"),
            url=best.get("url_for_landing_page"),
            is_open_access=data.get("is_oa"),
            sources=["unpaywall"],
            ids={"unpaywall": doi},
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --directory . pytest tests/test_providers/test_unpaywall.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add journal_scout_mcp/providers/unpaywall.py tests/fixtures/unpaywall_lookup.json tests/test_providers/test_unpaywall.py
git commit -m "feat(journal-scout): Unpaywall OA enrichment provider"
```

---

### Task 9: OpenAlex provider

**Files:**
- Create: `journal_scout_mcp/providers/openalex.py`
- Create: `tests/fixtures/openalex_search.json`
- Create: `tests/test_providers/test_openalex.py`

**Interfaces:**
- Consumes: `ProviderBase`, `config.get_polite_email`.
- Produces:
  - `class OpenAlexProvider(ProviderBase)` with `name = "openalex"`, `supports_search = True`.
  - `search(self, query, limit, year_from=None, year_to=None, tech_only=False) -> List[Paper]` maps `https://api.openalex.org/works?search=<q>&per-page=<limit>&mailto=<email>` (`results[]`), reconstructing the abstract from `abstract_inverted_index`.
  - `get(self, identifier) -> Optional[Paper]` maps `https://api.openalex.org/works/<id>`; accepts a bare OpenAlex id (`W123`), a full URL, or a DOI.
  - `citations(self, identifier, limit) -> List[Paper]` maps `https://api.openalex.org/works?filter=cites:<id>&per-page=<limit>`.
  - Tech preset: when `tech_only=True`, adds `filter=concepts.id:C41008148`.

- [ ] **Step 1: Write the fixture**

`tests/fixtures/openalex_search.json`:

```json
{
  "results": [
    {
      "id": "https://openalex.org/W2963403868",
      "doi": "https://doi.org/10.1162/neco.1997.9.8.1735",
      "title": "Long Short-Term Memory",
      "publication_year": 1997,
      "cited_by_count": 42000,
      "type": "article",
      "authorships": [
        {"author": {"display_name": "Sepp Hochreiter"}},
        {"author": {"display_name": "Jürgen Schmidhuber"}}
      ],
      "primary_location": {
        "source": {"display_name": "Neural Computation"},
        "landing_page_url": "https://doi.org/10.1162/neco.1997.9.8.1735",
        "pdf_url": null
      },
      "open_access": {"is_oa": true, "oa_url": "https://example.org/lstm.pdf"},
      "abstract_inverted_index": {"We": [0], "propose": [1], "LSTM": [2]}
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

`tests/test_providers/test_openalex.py`:

```python
import json
from pathlib import Path

import httpx

from journal_scout_mcp.providers.openalex import OpenAlexProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"


async def test_search_reconstructs_abstract_and_maps_fields():
    payload = json.loads((FIXTURES / "openalex_search.json").read_text(encoding="utf-8"))

    def handler(request):
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAlexProvider(client)
    try:
        papers = await provider.search("long short-term memory", 5)
        assert len(papers) == 1
        p = papers[0]
        assert p.doi == "10.1162/neco.1997.9.8.1735"
        assert p.title == "Long Short-Term Memory"
        assert p.year == 1997
        assert p.citation_count == 42000
        assert p.authors == ["Sepp Hochreiter", "Jürgen Schmidhuber"]
        assert p.venue == "Neural Computation"
        assert p.abstract == "We propose LSTM"
        assert p.is_open_access is True
        assert p.pdf_url == "https://example.org/lstm.pdf"
        assert p.sources == ["openalex"]
        assert p.ids["openalex"] == "https://openalex.org/W2963403868"
    finally:
        await client.aclose()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run --directory . pytest tests/test_providers/test_openalex.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'journal_scout_mcp.providers.openalex'`.

- [ ] **Step 4: Write `journal_scout_mcp/providers/openalex.py`**

```python
from typing import List, Optional

from ..config import get_polite_email
from ..models import Paper
from ..utils import normalize_doi
from .base import ProviderBase

OPENALEX_URL = "https://api.openalex.org/works"
CS_CONCEPT_ID = "C41008148"


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


class OpenAlexProvider(ProviderBase):
    name = "openalex"
    supports_search = True

    @staticmethod
    def _to_paper(work):
        authors = []
        for a in work.get("authorships", []) or []:
            name = (a.get("author") or {}).get("display_name")
            if name:
                authors.append(name)
        primary = work.get("primary_location") or {}
        source = primary.get("source") or {}
        oa = work.get("open_access") or {}
        return Paper(
            doi=normalize_doi(work.get("doi")),
            title=work.get("title") or work.get("display_name") or "",
            abstract=reconstruct_abstract(work.get("abstract_inverted_index")),
            year=work.get("publication_year"),
            authors=authors,
            venue=source.get("display_name"),
            citation_count=work.get("cited_by_count"),
            url=primary.get("landing_page_url") or work.get("id"),
            pdf_url=primary.get("pdf_url") or oa.get("oa_url"),
            is_open_access=oa.get("is_oa"),
            type=work.get("type"),
            sources=["openalex"],
            ids={"openalex": work.get("id")} if work.get("id") else {},
        )

    def _filters(self, year_from, year_to, tech_only):
        filters = []
        if year_from:
            filters.append(f"from_publication_date:{year_from}-01-01")
        if year_to:
            filters.append(f"to_publication_date:{year_to}-12-31")
        if tech_only:
            filters.append(f"concepts.id:{CS_CONCEPT_ID}")
        return filters

    async def search(self, query: str, limit: int, year_from=None, year_to=None, tech_only=False) -> List[Paper]:
        params = {"search": query, "per-page": limit, "mailto": get_polite_email()}
        filters = self._filters(year_from, year_to, tech_only)
        if filters:
            params["filter"] = ",".join(filters)
        data = await self._fetch_json(OPENALEX_URL, params=params)
        return [self._to_paper(w) for w in data.get("results", []) or []]

    async def get(self, identifier: str) -> Optional[Paper]:
        work_id = f"doi:{identifier}" if identifier.startswith("10.") else identifier
        data = await self._fetch_json(
            f"{OPENALEX_URL}/{work_id}", params={"mailto": get_polite_email()}
        )
        return self._to_paper(data) if data else None

    async def citations(self, identifier: str, limit: int) -> List[Paper]:
        work_id = f"doi:{identifier}" if identifier.startswith("10.") else identifier
        params = {
            "filter": f"cites:{work_id}",
            "per-page": limit,
            "mailto": get_polite_email(),
        }
        data = await self._fetch_json(OPENALEX_URL, params=params)
        return [self._to_paper(w) for w in data.get("results", []) or []]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --directory . pytest tests/test_providers/test_openalex.py -q`
Expected: PASS (1 passed).

- [ ] **Step 6: Commit**

```bash
git add journal_scout_mcp/providers/openalex.py tests/fixtures/openalex_search.json tests/test_providers/test_openalex.py
git commit -m "feat(journal-scout): OpenAlex provider with abstract reconstruction"
```

---

### Task 10: arXiv provider

**Files:**
- Create: `journal_scout_mcp/providers/arxiv.py`
- Create: `tests/fixtures/arxiv_search.xml`
- Create: `tests/test_providers/test_arxiv.py`

**Interfaces:**
- Consumes: `ProviderBase`, `utils.normalize_doi`.
- Produces:
  - `class ArxivProvider(ProviderBase)` with `name = "arxiv"`, `supports_search = True`.
  - `search(self, query, limit, year_from=None, year_to=None, tech_only=False) -> List[Paper]` maps `https://export.arxiv.org/api/query?search_query=<q>&start=0&max_results=<limit>&sortBy=submittedDate&sortOrder=descending` (Atom XML) to `Paper`. Parsed with stdlib `xml.etree.ElementTree` (no extra dependency).
  - `get(self, identifier) -> Optional[Paper]` maps `https://export.arxiv.org/api/query?id_list=<id>`.
  - Tech preset: when `tech_only=True`, the search term is prefixed with `cat:cs.*` categories joined by OR.
  - arXiv IDs are stored in `ids["arxiv"]`; the PDF URL is `https://arxiv.org/pdf/<id>`.

- [ ] **Step 1: Write the fixture**

`tests/fixtures/arxiv_search.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1706.03762v5</id>
    <updated>2017-12-06T18:24:53Z</updated>
    <published>2017-06-12T17:57:34Z</published>
    <title>Attention Is All You Need</title>
    <summary>The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.</summary>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
    <link href="http://arxiv.org/abs/1706.03762v5" rel="alternate" type="text/html"/>
    <link href="http://arxiv.org/pdf/1706.03762v5" rel="related" type="application/pdf"/>
    <category term="cs.CL"/>
    <category term="cs.LG"/>
  </entry>
</feed>
```

- [ ] **Step 2: Write the failing test**

`tests/test_providers/test_arxiv.py`:

```python
from pathlib import Path

import httpx

from journal_scout_mcp.providers.arxiv import ArxivProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"
ATOM = "{http://www.w3.org/2005/Atom}"


async def test_search_parses_atom_entry():
    xml = (FIXTURES / "arxiv_search.xml").read_text(encoding="utf-8")

    def handler(request):
        return httpx.Response(200, text=xml)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ArxivProvider(client)
    try:
        papers = await provider.search("attention is all you need", 5)
        assert len(papers) == 1
        p = papers[0]
        assert p.title == "Attention Is All You Need"
        assert p.authors == ["Ashish Vaswani", "Noam Shazeer"]
        assert p.year == 2017
        assert p.abstract.startswith("The dominant sequence transduction")
        assert p.pdf_url == "http://arxiv.org/pdf/1706.03762v5"
        assert p.sources == ["arxiv"]
        assert p.ids["arxiv"] == "1706.03762v5"
    finally:
        await client.aclose()


async def test_tech_only_adds_cs_categories_to_query():
    captured = {}

    def handler(request):
        captured["query"] = request.url.params.get("search_query")
        return httpx.Response(200, text=(FIXTURES / "arxiv_search.xml").read_text(encoding="utf-8"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ArxivProvider(client)
    try:
        await provider.search("transformers", 5, tech_only=True)
        assert "cat:cs." in captured["query"]
    finally:
        await client.aclose()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run --directory . pytest tests/test_providers/test_arxiv.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'journal_scout_mcp.providers.arxiv'`.

- [ ] **Step 4: Write `journal_scout_mcp/providers/arxiv.py`**

```python
import re
import xml.etree.ElementTree as ET
from typing import List, Optional

from ..models import Paper
from ..utils import normalize_doi
from .base import ProviderBase

ARXIV_URL = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
TECH_CATEGORIES = ["cs.AI", "cs.LG", "cs.CL", "cs.CR", "cs.NI", "cs.CV", "cs.SE"]


def _arxiv_id(raw_id: str) -> str:
    if not raw_id:
        return ""
    return raw_id.rstrip("/").rsplit("/", 1)[-1]


class ArxivProvider(ProviderBase):
    name = "arxiv"
    supports_search = True

    @staticmethod
    def _to_paper(entry):
        raw_id = entry.findtext(f"{ATOM}id") or ""
        authors = [a.findtext(f"{ATOM}name") for a in entry.findall(f"{ATOM}author")]
        pdf_url = None
        for link in entry.findall(f"{ATOM}link"):
            if link.get("type") == "application/pdf":
                pdf_url = link.get("href")
        categories = [c.get("term") for c in entry.findall(f"{ATOM}category")]
        if not pdf_url:
            aid = _arxiv_id(raw_id)
            pdf_url = f"https://arxiv.org/pdf/{aid}" if aid else None
        published = entry.findtext(f"{ATOM}published") or ""
        year = int(published[:4]) if published[:4].isdigit() else None
        aid = _arxiv_id(raw_id)
        return Paper(
            title=" ".join((entry.findtext(f"{ATOM}title") or "").split()),
            abstract=" ".join((entry.findtext(f"{ATOM}summary") or "").split()),
            year=year,
            authors=[a for a in authors if a],
            venue=", ".join(c for c in categories if c) or None,
            url=raw_id or None,
            pdf_url=pdf_url,
            type="preprint",
            sources=["arxiv"],
            ids={"arxiv": aid} if aid else {},
        )

    async def search(self, query: str, limit: int, year_from=None, year_to=None, tech_only=False) -> List[Paper]:
        search_query = f"all:{query}"
        if tech_only:
            cats = " OR ".join(f"cat:{c}" for c in TECH_CATEGORIES)
            search_query = f"({search_query}) AND ({cats})"
        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": limit,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        text = await self._fetch_text(ARXIV_URL, params=params)
        feed = ET.fromstring(text)
        results = []
        for entry in feed.findall(f"{ATOM}entry"):
            paper = self._to_paper(entry)
            if year_from and paper.year and paper.year < year_from:
                continue
            if year_to and paper.year and paper.year > year_to:
                continue
            results.append(paper)
        return results

    async def get(self, identifier: str) -> Optional[Paper]:
        aid = _arxiv_id(identifier)
        if not aid:
            return None
        text = await self._fetch_text(ARXIV_URL, params={"id_list": aid})
        feed = ET.fromstring(text)
        entries = feed.findall(f"{ATOM}entry")
        return self._to_paper(entries[0]) if entries else None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --directory . pytest tests/test_providers/test_arxiv.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add journal_scout_mcp/providers/arxiv.py tests/fixtures/arxiv_search.xml tests/test_providers/test_arxiv.py
git commit -m "feat(journal-scout): arXiv provider with Atom parsing"
```

---

### Task 11: Semantic Scholar provider

**Files:**
- Create: `journal_scout_mcp/providers/semanticscholar.py`
- Create: `tests/fixtures/semanticscholar_search.json`
- Create: `tests/test_providers/test_semanticscholar.py`

**Interfaces:**
- Consumes: `ProviderBase`, `config.get_semantic_scholar_key`.
- Produces:
  - `class SemanticScholarProvider(ProviderBase)` with `name = "semanticscholar"`, `supports_search = True`.
  - `search(self, query, limit, year_from=None, year_to=None, tech_only=False) -> List[Paper]` maps `https://api.semanticscholar.org/graph/v1/paper/search?query=<q>&limit=<limit>&fields=<f>` (`data[]`).
  - `get(identifier)` maps `https://api.semanticscholar.org/graph/v1/paper/<id>?fields=<f>`; identifier is prefixed (`DOI:`, `ARXIV:`, `CorpusId:`) when needed.
  - `citations(identifier, limit)` maps `https://api.semanticscholar.org/graph/v1/paper/<id>/citations?limit=<limit>&fields=<f>` and reads `data[].citingPaper`.
  - Auth: when `get_semantic_scholar_key()` returns a value, send header `x-api-key`.
  - `FIELDS` constant: `"title,abstract,year,citationCount,authors,externalIds,openAccessPdf,venue,publicationTypes,tldr"`.

- [ ] **Step 1: Write the fixture**

`tests/fixtures/semanticscholar_search.json`:

```json
{
  "data": [
    {
      "paperId": "abc123",
      "title": "Attention Is All You Need",
      "abstract": "The dominant sequence transduction models.",
      "year": 2017,
      "citationCount": 90000,
      "venue": "NeurIPS",
      "externalIds": {"DOI": "10.5555/3295222.3295349", "ArXiv": "1706.03762"},
      "openAccessPdf": {"url": "https://example.org/attn.pdf"},
      "authors": [{"name": "Ashish Vaswani"}, {"name": "Noam Shazeer"}],
      "tldr": {"text": "A new simple network architecture, the Transformer."}
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

`tests/test_providers/test_semanticscholar.py`:

```python
import json
from pathlib import Path

import httpx

from journal_scout_mcp.providers.semanticscholar import SemanticScholarProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"


async def test_search_maps_data_to_paper():
    payload = json.loads((FIXTURES / "semanticscholar_search.json").read_text(encoding="utf-8"))

    def handler(request):
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SemanticScholarProvider(client)
    try:
        papers = await provider.search("attention", 5)
        assert len(papers) == 1
        p = papers[0]
        assert p.doi == "10.5555/3295222.3295349"
        assert p.title == "Attention Is All You Need"
        assert p.year == 2017
        assert p.citation_count == 90000
        assert p.authors == ["Ashish Vaswani", "Noam Shazeer"]
        assert p.pdf_url == "https://example.org/attn.pdf"
        assert p.sources == ["semanticscholar"]
        assert p.ids["semanticscholar"] == "abc123"
        assert p.ids["arxiv"] == "1706.03762"
    finally:
        await client.aclose()


async def test_api_key_header_sent_when_configured(monkeypatch):
    captured = {}

    def handler(request):
        captured["key"] = request.headers.get("x-api-key")
        return httpx.Response(200, json={"data": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SemanticScholarProvider(client)
    monkeypatch.setattr(
        "journal_scout_mcp.providers.semanticscholar.get_semantic_scholar_key",
        lambda: "secret-key",
    )
    try:
        await provider.search("anything", 1)
        assert captured["key"] == "secret-key"
    finally:
        await client.aclose()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run --directory . pytest tests/test_providers/test_semanticscholar.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'journal_scout_mcp.providers.semanticscholar'`.

- [ ] **Step 4: Write `journal_scout_mcp/providers/semanticscholar.py`**

```python
from typing import List, Optional

from ..config import get_semantic_scholar_key
from ..models import Paper
from ..utils import normalize_doi
from .base import ProviderBase

S2_URL = "https://api.semanticscholar.org/graph/v1"
FIELDS = "title,abstract,year,citationCount,authors,externalIds,openAccessPdf,venue,publicationTypes,tldr"


class SemanticScholarProvider(ProviderBase):
    name = "semanticscholar"
    supports_search = True

    def _headers(self):
        key = get_semantic_scholar_key()
        return {"x-api-key": key} if key else None

    @staticmethod
    def _to_paper(item):
        authors = [a.get("name") for a in item.get("authors", []) or [] if a.get("name")]
        external = item.get("externalIds") or {}
        doi = normalize_doi(external.get("DOI"))
        oa = item.get("openAccessPdf") or {}
        ids = {"semanticscholar": item.get("paperId")} if item.get("paperId") else {}
        if doi:
            ids["doi"] = doi
        if external.get("ArXiv"):
            ids["arxiv"] = external["ArXiv"]
        return Paper(
            doi=doi,
            title=item.get("title") or "",
            abstract=item.get("abstract") or (item.get("tldr") or {}).get("text"),
            year=item.get("year"),
            authors=authors,
            venue=item.get("venue") or None,
            citation_count=item.get("citationCount"),
            url=f"https://www.semanticscholar.org/paper/{item.get('paperId')}" if item.get("paperId") else None,
            pdf_url=oa.get("url"),
            is_open_access=bool(oa.get("url")),
            type=", ".join(item.get("publicationTypes") or []) or None,
            sources=["semanticscholar"],
            ids=ids,
        )

    @staticmethod
    def _ident(identifier: str) -> str:
        if identifier.startswith("10."):
            return f"DOI:{identifier}"
        return identifier

    async def search(self, query: str, limit: int, year_from=None, year_to=None, tech_only=False) -> List[Paper]:
        params = {"query": query, "limit": limit, "fields": FIELDS}
        if year_from or year_to:
            lo = year_from or ""
            hi = year_to or ""
            params["year"] = f"{lo}-{hi}"
        if tech_only:
            params["fieldsOfStudy"] = "Computer Science"
        data = await self._fetch_json(f"{S2_URL}/paper/search", params=params)
        return [self._to_paper(i) for i in data.get("data", []) or []]

    async def get(self, identifier: str) -> Optional[Paper]:
        data = await self._fetch_json(
            f"{S2_URL}/paper/{self._ident(identifier)}", params={"fields": FIELDS}
        )
        return self._to_paper(data) if data and data.get("paperId") else None

    async def citations(self, identifier: str, limit: int) -> List[Paper]:
        data = await self._fetch_json(
            f"{S2_URL}/paper/{self._ident(identifier)}/citations",
            params={"limit": limit, "fields": FIELDS},
        )
        return [self._to_paper(e.get("citingPaper") or {}) for e in data.get("data", []) or []]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --directory . pytest tests/test_providers/test_semanticscholar.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add journal_scout_mcp/providers/semanticscholar.py tests/fixtures/semanticscholar_search.json tests/test_providers/test_semanticscholar.py
git commit -m "feat(journal-scout): Semantic Scholar provider with citations"
```

---

### Task 12: Scopus provider (port from scopus-mcp)

**Files:**
- Create: `journal_scout_mcp/providers/scopus.py`
- Create: `tests/fixtures/scopus_search.json`
- Create: `tests/test_providers/test_scopus.py`

**Interfaces:**
- Consumes: `ProviderBase`, `config.get_api_key`, `utils.normalize_doi`.
- Produces:
  - `class ScopusProvider(ProviderBase)` with `name = "scopus"`, `supports_search = True`.
  - `search(query, limit, year_from=None, year_to=None, tech_only=False) -> List[Paper]` maps `https://api.elsevier.com/content/search/scopus?query=<q>&count=<limit>&httpAccept=application/json` (`search-results.entry[]`).
  - `get(identifier) -> Optional[Paper]` maps `https://api.elsevier.com/content/abstract/scopus_id/<id>`.
  - `citations(identifier, limit) -> List[Paper]` maps the same search endpoint with `REF(<id>)` as the query.
  - Auth header: `X-ELS-APIKey: <api_key>`, plus `Accept: application/json`.
  - Tech preset: `tech_only=True` appends `AND SUBJAREA(COMP)` to the query.
  - SciVal methods (`scival_author_metrics`, `scival_institution_metrics`, `scival_author_lookup`, `scival_institution_lookup`, `scival_topic_metrics`) are ported from the old `client.py` and are called directly by `server.py`, not via the `ProviderBase` interface.

- [ ] **Step 1: Write the fixture**

`tests/fixtures/scopus_search.json`:

```json
{
  "search-results": {
    "entry": [
      {
        "dc:identifier": "SCOPUS_ID:85012345678",
        "eid": "2-s2.0-85012345678",
        "dc:title": "Deep Learning for Network Intrusion Detection",
        "dc:creator": "Doe J.",
        "prism:publicationName": "IEEE Access",
        "prism:coverDate": "2023-05-01",
        "citedby-count": "42",
        "prism:doi": "10.1109/ACCESS.2023.1234567",
        "dc:description": "We survey deep learning methods for network intrusion detection.",
        "subtypeDescription": "Article"
      }
    ]
  }
}
```

- [ ] **Step 2: Write the failing test**

`tests/test_providers/test_scopus.py`:

```python
import json
from pathlib import Path

import httpx

from journal_scout_mcp.providers.scopus import ScopusProvider

FIXTURES = Path(__file__).parent.parent / "fixtures"


async def test_search_maps_entries_to_paper(monkeypatch):
    payload = json.loads((FIXTURES / "scopus_search.json").read_text(encoding="utf-8"))

    def handler(request):
        assert "X-ELS-APIKey" in request.headers
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        papers = await provider.search("intrusion detection", 5)
        assert len(papers) == 1
        p = papers[0]
        assert p.doi == "10.1109/access.2023.1234567"
        assert p.title == "Deep Learning for Network Intrusion Detection"
        assert p.year == 2023
        assert p.citation_count == 42
        assert p.venue == "IEEE Access"
        assert p.sources == ["scopus"]
        assert p.ids["scopus"] == "SCOPUS_ID:85012345678"
    finally:
        await client.aclose()


async def test_tech_only_adds_subjarea():
    captured = {}

    def handler(request):
        captured["query"] = request.url.params.get("query")
        return httpx.Response(200, json={"search-results": {"entry": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = ScopusProvider(client, {"api_key": "test-key"})
    try:
        await provider.search("networks", 5, tech_only=True)
        assert "SUBJAREA(COMP)" in captured["query"]
    finally:
        await client.aclose()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run --directory . pytest tests/test_providers/test_scopus.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'journal_scout_mcp.providers.scopus'`.

- [ ] **Step 4: Write `journal_scout_mcp/providers/scopus.py`**

```python
from typing import Any, Dict, List, Optional

from ..config import get_api_key
from ..models import Paper
from ..utils import normalize_doi
from .base import ProviderBase

SCOPUS_BASE = "https://api.elsevier.com/content/"
SCIVAL_BASE = "https://api.elsevier.com/analytics/scival/"


def _year_from_date(value: str) -> Optional[int]:
    if value and len(value) >= 4 and value[:4].isdigit():
        return int(value[:4])
    return None


class ScopusProvider(ProviderBase):
    name = "scopus"
    supports_search = True

    def __init__(self, fetcher, config=None):
        super().__init__(fetcher, config)
        self._api_key = (config or {}).get("api_key")

    def _headers(self):
        key = self._api_key or get_api_key()
        return {
            "X-ELS-APIKey": key,
            "Accept": "application/json",
        }

    @staticmethod
    def _to_paper(entry):
        scopus_id = entry.get("dc:identifier") or entry.get("eid")
        doi = normalize_doi(entry.get("prism:doi") or entry.get("doi"))
        creator = entry.get("dc:creator")
        authors = [creator] if creator else []
        year = _year_from_date(entry.get("prism:coverDate") or entry.get("prism:coverDisplayDate") or "")
        cited = entry.get("citedby-count")
        ids = {}
        if scopus_id:
            ids["scopus"] = scopus_id
        if doi:
            ids["doi"] = doi
        return Paper(
            doi=doi,
            title=entry.get("dc:title") or "",
            abstract=entry.get("dc:description"),
            year=year,
            authors=authors,
            venue=entry.get("prism:publicationName"),
            citation_count=int(cited) if cited is not None and str(cited).isdigit() else None,
            url=entry.get("prism:url") or entry.get("link"),
            type=entry.get("subtypeDescription"),
            sources=["scopus"],
            ids=ids,
        )

    async def search(self, query: str, limit: int, year_from=None, year_to=None, tech_only=False) -> List[Paper]:
        q = query
        if tech_only:
            q = f"({q}) AND SUBJAREA(COMP)"
        if year_from:
            q = f"{q} AND PUBYEAR > {year_from - 1}"
        if year_to:
            q = f"{q} AND PUBYEAR < {year_to + 1}"
        params = {"query": q, "count": limit}
        data = await self._fetch_json(f"{SCOPUS_BASE}search/scopus", params=params)
        entries = (data.get("search-results") or {}).get("entry") or []
        results = []
        for entry in entries:
            if isinstance(entry, dict) and "error" in entry:
                continue
            results.append(self._to_paper(entry))
        return results

    async def get(self, identifier: str) -> Optional[Paper]:
        sid = identifier.replace("SCOPUS_ID:", "")
        data = await self._fetch_json(f"{SCOPUS_BASE}abstract/scopus_id/{sid}")
        core = (data.get("abstracts-retrieval-response") or {}).get("coredata") or {}
        return self._to_paper(core) if core else None

    async def citations(self, identifier: str, limit: int) -> List[Paper]:
        sid = identifier.replace("SCOPUS_ID:", "")
        data = await self._fetch_json(
            f"{SCOPUS_BASE}search/scopus", params={"query": f"REF({sid})", "count": limit}
        )
        entries = (data.get("search-results") or {}).get("entry") or []
        return [self._to_paper(e) for e in entries if isinstance(e, dict) and "error" not in e]

    async def scival_author_metrics(self, author_id: str, year_from=None, year_to=None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"metricTypes": "publications,citations,hIndex"}
        if year_from:
            params["startYear"] = year_from
        if year_to:
            params["endYear"] = year_to
        return await self._fetch_json(f"{SCIVAL_BASE}author/{author_id}/metrics", params=params)

    async def scival_institution_metrics(self, institution_id: str, year_from=None, year_to=None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"metricTypes": "publications,citations,hIndex"}
        if year_from:
            params["startYear"] = year_from
        if year_to:
            params["endYear"] = year_to
        return await self._fetch_json(f"{SCIVAL_BASE}institution/{institution_id}/metrics", params=params)

    async def scival_author_lookup(self, query: str, count: int = 10) -> Dict[str, Any]:
        return await self._fetch_json(f"{SCIVAL_BASE}author", params={"query": query, "count": count})

    async def scival_institution_lookup(self, query: str, count: int = 10) -> Dict[str, Any]:
        return await self._fetch_json(f"{SCIVAL_BASE}institution", params={"query": query, "count": count})

    async def scival_topic_metrics(self, topic_id: str, year_from=None, year_to=None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"metricTypes": "publications,citations"}
        if year_from:
            params["startYear"] = year_from
        if year_to:
            params["endYear"] = year_to
        return await self._fetch_json(f"{SCIVAL_BASE}topic/{topic_id}/metrics", params=params)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --directory . pytest tests/test_providers/test_scopus.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add journal_scout_mcp/providers/scopus.py tests/fixtures/scopus_search.json tests/test_providers/test_scopus.py
git commit -m "feat(journal-scout): Scopus provider with SciVal metrics"
```

---

### Task 13: Aggregator — parallel fan-out with partial failure

**Files:**
- Create: `journal_scout_mcp/aggregator.py`
- Create: `tests/test_aggregator.py`

**Interfaces:**
- Consumes: `models.Paper`, `models.ProviderError`, `merge.merge_papers`, `providers.base.ProviderBase`.
- Produces:
  - `async search_all(providers, query, limit_per_source=5, year_from=None, year_to=None, tech_only=False, sources=None) -> dict` returning `{"results": [paper dicts], "errors": {name: message}, "counts": {name: int}}`.
  - `async get_paper(providers, identifier) -> dict` returning `{"paper": paper dict | None, "errors": {...}}`; enriches the merged paper with Unpaywall OA data when the paper has a DOI.
  - `async get_citations(providers, identifier, limit=20) -> dict` returning `{"results": [...], "errors": {...}, "counts": {...}}`.

- [ ] **Step 1: Write the failing test**

`tests/test_aggregator.py`:

```python
from journal_scout_mcp.aggregator import get_citations, get_paper, search_all
from journal_scout_mcp.models import Paper, ProviderError
from journal_scout_mcp.providers.base import ProviderBase


class GoodProvider(ProviderBase):
    name = "good"
    supports_search = True

    async def search(self, query, limit, year_from=None, year_to=None, tech_only=False):
        return [Paper(doi="10.1/x", title="Shared", citation_count=3, sources=["good"])]


class BadProvider(ProviderBase):
    name = "bad"
    supports_search = True

    async def search(self, query, limit, year_from=None, year_to=None, tech_only=False):
        raise ProviderError("bad", "boom")


class GoodCitationProvider(ProviderBase):
    name = "goodcite"
    supports_search = False

    async def citations(self, identifier, limit):
        return [Paper(doi="10.2/y", title="Citing", sources=["goodcite"])]


class GoodGetProvider(ProviderBase):
    name = "goodget"
    supports_search = False

    async def get(self, identifier):
        return Paper(doi="10.1/x", title="Shared", year=2020, sources=["goodget"])


async def test_search_all_merges_and_reports_partial_failure():
    result = await search_all([GoodProvider(None), BadProvider(None)], "q", limit_per_source=5)
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Shared"
    assert result["errors"] == {"bad": "boom"}
    assert "good" in result["counts"]


async def test_search_all_respects_sources_filter():
    result = await search_all(
        [GoodProvider(None), BadProvider(None)], "q", sources=["good"]
    )
    assert result["errors"] == {}
    assert len(result["results"]) == 1


async def test_get_paper_merges_across_providers():
    result = await get_paper([GoodGetProvider(None), GoodProvider(None)], "10.1/x")
    assert result["paper"]["doi"] == "10.1/x"
    assert set(result["paper"]["sources"]) == {"good", "goodget"}


async def test_get_citations_collects_from_providers():
    result = await get_citations([GoodCitationProvider(None)], "10.1/x", limit=10)
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Citing"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory . pytest tests/test_aggregator.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'journal_scout_mcp.aggregator'`.

- [ ] **Step 3: Write `journal_scout_mcp/aggregator.py`**

```python
import asyncio
from typing import Any, Dict, List, Optional

from .merge import merge_papers
from .models import Paper, ProviderError
from .providers.base import ProviderBase

UNPAYWALL_NAME = "unpaywall"


async def _gather(calls: Dict[str, Any]) -> tuple[List[Paper], Dict[str, str], Dict[str, int]]:
    names = list(calls.keys())
    results = await asyncio.gather(*calls.values(), return_exceptions=True)
    papers: List[Paper] = []
    errors: Dict[str, str] = {}
    counts: Dict[str, int] = {}
    for name, outcome in zip(names, results):
        if isinstance(outcome, Exception):
            message = getattr(outcome, "message", str(outcome))
            errors[name] = message
            continue
        counts[name] = len(outcome)
        papers.extend(outcome)
    return papers, errors, counts


def _select(providers: List[ProviderBase], sources: Optional[List[str]], need: str) -> List[ProviderBase]:
    selected = []
    for provider in providers:
        if sources is not None and provider.name not in sources:
            continue
        if need == "search" and not provider.supports_search:
            continue
        selected.append(provider)
    return selected


async def search_all(
    providers: List[ProviderBase],
    query: str,
    limit_per_source: int = 5,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    tech_only: bool = False,
    sources: Optional[List[str]] = None,
) -> Dict[str, Any]:
    active = _select(providers, sources, "search")
    calls = {
        p.name: p.search(query, limit_per_source, year_from, year_to, tech_only)
        for p in active
    }
    papers, errors, counts = await _gather(calls)
    merged = merge_papers(papers)
    return {
        "results": [p.to_dict() for p in merged],
        "errors": errors,
        "counts": counts,
    }


async def _enrich_with_unpaywall(providers: List[ProviderBase], paper: Paper) -> Paper:
    if not paper.doi:
        return paper
    for provider in providers:
        if provider.name != UNPAYWALL_NAME:
            continue
        try:
            oa = await provider.get(paper.doi)
        except ProviderError:
            return paper
        if oa:
            if oa.pdf_url:
                paper.pdf_url = paper.pdf_url or oa.pdf_url
            if oa.url:
                paper.url = paper.url or oa.url
            if oa.is_open_access is not None:
                paper.is_open_access = oa.is_open_access
            if provider.name not in paper.sources:
                paper.sources.append(provider.name)
        return paper
    return paper


async def get_paper(providers: List[ProviderBase], identifier: str) -> Dict[str, Any]:
    active = [p for p in providers if p.name != UNPAYWALL_NAME]
    calls = {p.name: p.get(identifier) for p in active}
    names = list(calls.keys())
    outcomes = await asyncio.gather(*calls.values(), return_exceptions=True)
    papers: List[Paper] = []
    errors: Dict[str, str] = {}
    for name, outcome in zip(names, outcomes):
        if isinstance(outcome, Exception):
            errors[name] = getattr(outcome, "message", str(outcome))
        elif outcome is not None:
            papers.append(outcome)
    merged = merge_papers(papers)
    if not merged:
        return {"paper": None, "errors": errors}
    paper = await _enrich_with_unpaywall(providers, merged[0])
    return {"paper": paper.to_dict(), "errors": errors}


async def get_citations(
    providers: List[ProviderBase],
    identifier: str,
    limit: int = 20,
) -> Dict[str, Any]:
    active = [p for p in providers if p.name in {"scopus", "openalex", "semanticscholar"}]
    calls = {p.name: p.citations(identifier, limit) for p in active}
    papers, errors, counts = await _gather(calls)
    merged = merge_papers(papers)
    return {
        "results": [p.to_dict() for p in merged],
        "errors": errors,
        "counts": counts,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory . pytest tests/test_aggregator.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add journal_scout_mcp/aggregator.py tests/test_aggregator.py
git commit -m "feat(journal-scout): parallel aggregator with partial-failure reporting"
```

---

### Task 14: MCP server with 17 tools

**Files:**
- Create: `journal_scout_mcp/server.py`
- Create: `tests/test_server.py`

**Interfaces:**
- Consumes: `config`, `http.Fetcher`, `providers.build_providers`, `providers.scopus.ScopusProvider`, `aggregator.search_all/get_paper/get_citations`, `models.ProviderError`.
- Produces:
  - `TOOL_NAMES: list[str]` — the 17 tool names in declaration order.
  - `async build_json(name: str, arguments: dict, providers, scopus_provider) -> dict` — pure dispatch used by both the MCP handler and tests.
  - `start() -> None` — builds a `Server("journal-scout-mcp")`, registers `list_tools`/`call_tool`/`list_prompts`/`get_prompt`, and runs stdio.

- [ ] **Step 1: Write the failing test**

`tests/test_server.py`:

```python
from journal_scout_mcp.server import TOOL_NAMES, build_json
from journal_scout_mcp.models import Paper
from journal_scout_mcp.providers.base import ProviderBase


class SearchProvider(ProviderBase):
    name = "openalex"
    supports_search = True

    async def search(self, query, limit, year_from=None, year_to=None, tech_only=False):
        return [Paper(doi="10.1/x", title="Hit", sources=["openalex"])]


def test_tool_names_count():
    assert len(TOOL_NAMES) == 17
    assert "search_all" in TOOL_NAMES
    assert "search_openalex" in TOOL_NAMES
    assert "scival_topic_metrics" in TOOL_NAMES
    assert "get_citing_papers" not in TOOL_NAMES


async def test_dispatch_search_all():
    result = await build_json("search_all", {"query": "q"}, [SearchProvider(None)], None)
    assert result["results"][0]["title"] == "Hit"


async def test_dispatch_per_source_search():
    result = await build_json("search_openalex", {"query": "q", "count": 3}, [SearchProvider(None)], None)
    assert result["results"][0]["title"] == "Hit"


async def test_dispatch_unknown_tool_raises():
    try:
        await build_json("nope", {}, [], None)
    except ValueError as e:
        assert "Unknown tool" in str(e)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory . pytest tests/test_server.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'journal_scout_mcp.server'`.

- [ ] **Step 3: Write `journal_scout_mcp/server.py`**

```python
import asyncio
import json
from typing import Any, Dict, List, Optional

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from . import aggregator, config
from .http import Fetcher
from .models import ProviderError
from .providers import build_providers

UNIFIED_TOOLS = ["search_all", "get_paper", "get_citations"]
PER_SOURCE_TOOLS = [
    "search_scopus",
    "search_arxiv",
    "search_openalex",
    "search_semanticscholar",
    "search_crossref",
    "search_dblp",
]
SCOPUS_DETAIL_TOOLS = ["get_abstract_details", "get_author_profile", "get_quota_status"]
SCIVAL_TOOLS = [
    "scival_author_metrics",
    "scival_institution_metrics",
    "scival_author_lookup",
    "scival_institution_lookup",
    "scival_topic_metrics",
]
TOOL_NAMES = UNIFIED_TOOLS + PER_SOURCE_TOOLS + SCOPUS_DETAIL_TOOLS + SCIVAL_TOOLS

_SEARCH_ARGUMENTS = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Search query."},
        "count": {"type": "integer", "description": "Max results.", "default": 5},
        "year_from": {"type": "integer", "description": "Earliest publication year."},
        "year_to": {"type": "integer", "description": "Latest publication year."},
        "tech_only": {"type": "boolean", "description": "Restrict to tech/computer-science.", "default": False},
    },
    "required": ["query"],
}


def _tool_list() -> List[types.Tool]:
    tools = [
        types.Tool(
            name="search_all",
            description="Search all journal sources in parallel and merge duplicate results by DOI/title.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit_per_source": {"type": "integer", "default": 5},
                    "year_from": {"type": "integer"},
                    "year_to": {"type": "integer"},
                    "tech_only": {"type": "boolean", "default": False},
                    "sources": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="get_paper",
            description="Resolve a DOI/arXiv/Scopus/OpenAlex id or title across sources, merge metadata, and attach open-access links.",
            inputSchema={
                "type": "object",
                "properties": {"identifier": {"type": "string"}},
                "required": ["identifier"],
            },
        ),
        types.Tool(
            name="get_citations",
            description="Collect the cross-source citation graph (Scopus + OpenAlex + Semantic Scholar) for one paper.",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {"type": "string"},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["identifier"],
            },
        ),
    ]
    for name in PER_SOURCE_TOOLS:
        tools.append(types.Tool(name=name, description=f"Search {name.removeprefix('search_')} only.", inputSchema=_SEARCH_ARGUMENTS))
    tools.append(types.Tool(name="get_abstract_details", description="Scopus abstract details for a Scopus id.", inputSchema={"type": "object", "properties": {"scopus_id": {"type": "string"}}, "required": ["scopus_id"]}))
    tools.append(types.Tool(name="get_author_profile", description="Scopus author profile.", inputSchema={"type": "object", "properties": {"author_id": {"type": "string"}}, "required": ["author_id"]}))
    tools.append(types.Tool(name="get_quota_status", description="Scopus API quota status.", inputSchema={"type": "object", "properties": {}}))
    tools.append(types.Tool(name="scival_author_metrics", description="SciVal author metrics.", inputSchema={"type": "object", "properties": {"author_id": {"type": "string"}, "year_from": {"type": "integer"}, "year_to": {"type": "integer"}}, "required": ["author_id"]}))
    tools.append(types.Tool(name="scival_institution_metrics", description="SciVal institution metrics.", inputSchema={"type": "object", "properties": {"institution_id": {"type": "string"}, "year_from": {"type": "integer"}, "year_to": {"type": "integer"}}, "required": ["institution_id"]}))
    tools.append(types.Tool(name="scival_author_lookup", description="SciVal author lookup by name.", inputSchema={"type": "object", "properties": {"query": {"type": "string"}, "count": {"type": "integer", "default": 10}}, "required": ["query"]}))
    tools.append(types.Tool(name="scival_institution_lookup", description="SciVal institution lookup by name.", inputSchema={"type": "object", "properties": {"query": {"type": "string"}, "count": {"type": "integer", "default": 10}}, "required": ["query"]}))
    tools.append(types.Tool(name="scival_topic_metrics", description="SciVal topic metrics.", inputSchema={"type": "object", "properties": {"topic_id": {"type": "string"}, "year_from": {"type": "integer"}, "year_to": {"type": "integer"}}, "required": ["topic_id"]}))
    return tools


async def build_json(name: str, arguments: Dict[str, Any], providers, scopus_provider) -> Dict[str, Any]:
    if name == "search_all":
        return await aggregator.search_all(
            providers,
            arguments["query"],
            limit_per_source=arguments.get("limit_per_source", 5),
            year_from=arguments.get("year_from"),
            year_to=arguments.get("year_to"),
            tech_only=arguments.get("tech_only", False),
            sources=arguments.get("sources"),
        )
    if name == "get_paper":
        return await aggregator.get_paper(providers, arguments["identifier"])
    if name == "get_citations":
        return await aggregator.get_citations(
            providers, arguments["identifier"], limit=arguments.get("limit", 20)
        )
    if name in PER_SOURCE_TOOLS:
        source = name.removeprefix("search_")
        return await aggregator.search_all(
            providers,
            arguments["query"],
            limit_per_source=arguments.get("count", 5),
            year_from=arguments.get("year_from"),
            year_to=arguments.get("year_to"),
            tech_only=arguments.get("tech_only", False),
            sources=[source],
        )
    if name == "get_abstract_details":
        return await scopus_provider.get(arguments["scopus_id"])
    if name == "get_author_profile":
        return await scopus_provider.get_author(arguments["author_id"])
    if name == "get_quota_status":
        return await scopus_provider.get_quota_status()
    if name == "scival_author_metrics":
        return await scopus_provider.scival_author_metrics(
            arguments["author_id"], arguments.get("year_from"), arguments.get("year_to")
        )
    if name == "scival_institution_metrics":
        return await scopus_provider.scival_institution_metrics(
            arguments["institution_id"], arguments.get("year_from"), arguments.get("year_to")
        )
    if name == "scival_author_lookup":
        return await scopus_provider.scival_author_lookup(
            arguments["query"], arguments.get("count", 10)
        )
    if name == "scival_institution_lookup":
        return await scopus_provider.scival_institution_lookup(
            arguments["query"], arguments.get("count", 10)
        )
    if name == "scival_topic_metrics":
        return await scopus_provider.scival_topic_metrics(
            arguments["topic_id"], arguments.get("year_from"), arguments.get("year_to")
        )
    raise ValueError(f"Unknown tool: {name}")


def start() -> None:
    async def run() -> None:
        fetcher = Fetcher()
        providers = build_providers(fetcher, {"api_key": config.get_api_key()})
        scopus_provider = next(p for p in providers if p.name == "scopus")
        server = Server("journal-scout-mcp")

        @server.list_tools()
        async def _list_tools() -> List[types.Tool]:
            return _tool_list()

        @server.call_tool()
        async def _call_tool(tool_name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
            try:
                payload = await build_json(tool_name, arguments or {}, providers, scopus_provider)
            except ProviderError as e:
                payload = {"error": e.message, "provider": e.provider}
            except Exception as e:  # noqa: BLE001 - surface a readable message to the agent
                payload = {"error": str(e)}
            return [types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]

        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
        await fetcher.close()

    asyncio.run(run())


if __name__ == "__main__":
    start()
```

Note: `get_author_profile`, `get_abstract_details`, and `get_quota_status` depend on three helper methods on `ScopusProvider` that must be ported from the old client alongside the SciVal methods. Add them to `journal_scout_mcp/providers/scopus.py` in this task:

```python
    async def get_author(self, author_id: str) -> Dict[str, Any]:
        return await self._fetch_json(f"{SCOPUS_BASE}author/author_id/{author_id}")

    async def get_quota_status(self) -> Dict[str, Any]:
        return {
            "note": "Elsevier does not expose a quota endpoint. Quota is tracked "
            "via the X-RateLimit-* and X-ELS-Status response headers on actual "
            "API calls; a 429 with QUOTA_EXCEEDED means the weekly quota is spent.",
            "seen": getattr(self, "quota_info", None),
        }
```

Then update the Task 12 provider test file with one more assertion-free smoke check that `get_author` exists:

```python
def test_scopus_provider_has_detail_helpers():
    from journal_scout_mcp.providers.scopus import ScopusProvider
    assert hasattr(ScopusProvider, "get_author")
    assert hasattr(ScopusProvider, "get_quota_status")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory . pytest tests/test_server.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add journal_scout_mcp/server.py tests/test_server.py
git commit -m "feat(journal-scout): MCP server exposing 17 tools"
```

---

### Task 15: Plugin packaging and migration from scopus-mcp

**Files:**
- Create: `.mcp.json`
- Create: `.claude-plugin/plugin.json`
- Create: `README.md`
- Create: `config.json` (gitignored), `config.json.example`
- Create: `.gitignore`
- Modify: `D:\Github\agent-workspace\openclaude-plugins\.claude-plugin\marketplace.json`
- Modify: `C:\Users\Lenovo\.openclaude\plugins\.claude-plugin\marketplace.json`
- Modify: `C:\Users\Lenovo\.openclaude\settings.json`
- Modify: `C:\Users\Lenovo\.openclaude\plugins\installed_plugins.json`

**Interfaces:**
- Consumes: nothing (packaging only).
- Produces: an installed plugin named `journal-scout-mcp@local-plugins` at version `2.0.0`, with `scopus-mcp@local-plugins` removed.

- [ ] **Step 1: Rename the source folder and delete the superseded package**

The new `journal_scout_mcp/` package already exists inside `scopus-mcp/` from Tasks 1-14. Rename the outer folder and drop the old `scopus_mcp/` package it supersedes.

```bash
cd D:/Github/agent-workspace/openclaude-plugins
mv scopus-mcp journal-scout-mcp
rm -rf journal-scout-mcp/scopus_mcp journal-scout-mcp/.venv journal-scout-mcp/.cache
ls journal-scout-mcp journal-scout-mcp/journal_scout_mcp
```

Expected: folder `journal-scout-mcp` containing the `journal_scout_mcp` package; no `scopus_mcp` folder remains.

- [ ] **Step 2: Write `.mcp.json`**

`journal-scout-mcp/.mcp.json`:

```json
{
  "journal-scout-mcp": {
    "command": "uv",
    "args": ["--directory", "${CLAUDE_PLUGIN_ROOT}", "run", "python", "-m", "journal_scout_mcp.server"]
  }
}
```

- [ ] **Step 3: Write `.claude-plugin/plugin.json`**

`journal-scout-mcp/.claude-plugin/plugin.json`:

```json
{
  "name": "journal-scout-mcp",
  "version": "2.0.0",
  "description": "Multi-source journal research MCP: Scopus, arXiv, OpenAlex, Semantic Scholar, Crossref, DBLP, Unpaywall. Unified search with DOI-first dedup, cross-source citation graph, and open-access resolution.",
  "keywords": ["mcp", "research", "scopus", "arxiv", "openalex", "semantic-scholar", "crossref", "dblp", "unpaywall"]
}
```

- [ ] **Step 4: Write `.gitignore`, `config.json.example`, and `README.md`**

`journal-scout-mcp/.gitignore`:

```
.venv/
__pycache__/
*.pyc
.cache/
config.json
```

`journal-scout-mcp/config.json.example`:

```json
{
  "api_key": "YOUR_ELSEVIER_API_KEY",
  "semantic_scholar_api_key": "",
  "polite_email": "you@example.com"
}
```

`journal-scout-mcp/config.json` (local only, not committed):

```json
{
  "api_key": "6feeacb16b5a7d6c7df6fc3707418298",
  "polite_email": "you@example.com"
}
```

`journal-scout-mcp/README.md`:

```markdown
# journal-scout-mcp

Multi-source journal research MCP server. Searches Scopus, arXiv, OpenAlex,
Semantic Scholar, Crossref, DBLP, and Unpaywall, then merges duplicate results
into one entry per paper (DOI-first dedup) and reports partial failures.

## Tools (17)

Unified: `search_all`, `get_paper`, `get_citations`.
Per-source: `search_scopus`, `search_arxiv`, `search_openalex`,
`search_semanticscholar`, `search_crossref`, `search_dblp`.
Scopus detail: `get_abstract_details`, `get_author_profile`, `get_quota_status`.
SciVal: `scival_author_metrics`, `scival_institution_metrics`,
`scival_author_lookup`, `scival_institution_lookup`, `scival_topic_metrics`.

## Config

Copy `config.json.example` to `config.json`. Only the Elsevier `api_key` is
required; the other sources work without a key. `polite_email` improves rate
limits on OpenAlex, Crossref, and Unpaywall.
```

- [ ] **Step 5: Register the plugin**

Update `D:\Github\agent-workspace\openclaude-plugins\.claude-plugin\marketplace.json` — replace the `scopus-mcp` entry (source `./scopus-mcp`) with:

```json
{
  "name": "journal-scout-mcp",
  "source": "./journal-scout-mcp",
  "description": "Multi-source journal research MCP (Scopus, arXiv, OpenAlex, Semantic Scholar, Crossref, DBLP, Unpaywall) with unified dedup.",
  "category": "development"
}
```

Apply the same replacement in `C:\Users\Lenovo\.openclaude\plugins\.claude-plugin\marketplace.json`.

In `C:\Users\Lenovo\.openclaude\settings.json`, replace `"scopus-mcp@local-plugins": true` with `"journal-scout-mcp@local-plugins": true`.

In `C:\Users\Lenovo\.openclaude\plugins\installed_plugins.json`, replace the `scopus-mcp@local-plugins` block with:

```json
    "journal-scout-mcp@local-plugins": [
      {
        "scope": "user",
        "installPath": "C:\\Users\\Lenovo\\.openclaude\\plugins\\cache\\local-plugins\\journal-scout-mcp\\2.0.0",
        "version": "2.0.0",
        "installedAt": "2026-09-19T00:00:00.000Z",
        "lastUpdated": "2026-09-19T00:00:00.000Z"
      }
    ],
```

- [ ] **Step 6: Sync to the cache directory**

```bash
cd C:/Users/Lenovo/.openclaude/plugins
mkdir -p cache/local-plugins/journal-scout-mcp/2.0.0
cp -r "D:/Github/agent-workspace/openclaude-plugins/journal-scout-mcp/." cache/local-plugins/journal-scout-mcp/2.0.0/
rm -rf cache/local-plugins/scopus-mcp
ls cache/local-plugins/journal-scout-mcp/2.0.0
```

Expected: the plugin files (including `config.json`) present in the `2.0.0` cache dir, and the old `scopus-mcp` cache dir gone.

- [ ] **Step 7: Verify the installed plugin end-to-end**

Write `C:/Users/Lenovo/AppData/Local/Temp/journal_scout_test.py`:

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

CACHE = "C:/Users/Lenovo/.openclaude/plugins/cache/local-plugins/journal-scout-mcp/2.0.0"


async def main():
    params = StdioServerParameters(
        command="uv",
        args=["--directory", CACHE, "run", "python", "-m", "journal_scout_mcp.server"],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("TOOL COUNT:", len(tools.tools))
            r = await session.call_tool(
                "search_all",
                {"query": "network intrusion detection", "limit_per_source": 2, "tech_only": True},
            )
            print("search_all isError:", r.isError)
            print("search_all text:", r.content[0].text[:600])


asyncio.run(main())
```

Run:

```bash
cd "D:/Github/agent-workspace/openclaude-plugins/journal-scout-mcp" && uv --directory "D:/Github/agent-workspace/openclaude-plugins/journal-scout-mcp" run --with "mcp<2" python "C:/Users/Lenovo/AppData/Local/Temp/journal_scout_test.py"
```

Expected: `TOOL COUNT: 17`, `search_all isError: False`, and a JSON payload whose `results` include papers with a `sources` list of two or more providers, or a populated `errors` dict if a source is down.

- [ ] **Step 8: Commit**

```bash
git add journal-scout-mcp/.mcp.json journal-scout-mcp/.claude-plugin/plugin.json journal-scout-mcp/.gitignore journal-scout-mcp/config.json.example journal-scout-mcp/README.md .claude-plugin/marketplace.json
git commit -m "feat(journal-scout): package as plugin and migrate registration from scopus-mcp"
```

---