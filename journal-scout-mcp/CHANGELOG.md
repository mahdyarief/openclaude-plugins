# Changelog

All notable changes to this project will be documented in this file.

Historical entries are reconstructed from the upstream commit history
(`3ae2bcc` → `92ae1b7`), not from the development branch.

## [2.3.0] - 2026-10-24

Supersedes upstream v2.2.0 (2026-10-14), whose changes — prompt templates,
year filters, arXiv/Semantic Scholar author search, and the
`get_abstract_details` serialization fix — are all contained in this tree.

### Added
- Publish-or-Perish style bibliometrics: `compute_metrics` with `basic`
  (14 fields) and `extended` (21 fields) modes, including `hI`, `hI_norm`,
  and `hm` alongside `h`, `g`, `hc`, `e`, `ARC`, and `AWCR`
- Connected-Papers style citation networks: co-citation, bibliographic
  coupling, and max-node pruning (`build_citation_network`)
- OpenCitations provider for DOI-to-DOI citation and reference links
- Structured field filters — `author`, `venue`, `affiliation`, `issn`,
  `orcid`, `doi` — routed per provider through `supports_filters`, with
  `filters_applied` / `filters_ignored` reported in every search response
- Search history: `searches` table in Turso, `GET /api/searches`, and
  automatic recording of every live search
- Related works: `supports_related` on the provider base class, OpenAlex
  `related()` hydrating `related_works` in one batched request,
  `aggregator.get_related()`, the `get_related_works` MCP tool, and
  `GET /api/related`
- Offline mode: `?offline=true` serves cached payloads with `stale: true`
  and answers 503 when the key is missing
- Browser UI (`josc-web`): search form with the filter fields, citation
  graph viewer, metrics view, a search-history page, and an 11-format
  export menu
- Export formats: BibTeX, RIS, CSV, CSV with header, JSON, GraphML, and
  four plain-text variants via `format_papers()`
- Cache telemetry in `GET /api/health` — in-memory `cache` block and
  persistent `store` block

### Changed
- Package restructured from `journal_scout_mcp/` to `src/josc/`; entry
  points are now `josc.server:start` and `josc.api:start`
- Ruff configuration added (`E4`, `E7`, `E9`, `F`) so CI linting passes on
  the existing codebase without a mass rewrite
- CI installs both `dev` and `web` extras, since two tests exercise the
  Starlette surface

### Fixed
- Co-citation is computed from complete reference lists before node
  materialisation, so `weight >= 2` is reachable within the node budget
- Crossref field filters are merged with the year bounds instead of
  replacing them
- OpenAlex affiliation values are comma-flattened, since OpenAlex splits
  its `filter` parameter on commas
- Scopus `_authors()` handles dict-shaped `dc:creator`; `_fetch_abstract()`
  degrades gracefully when `view=FULL` returns 401

### Tests
- 242 tests passing

## [2.2.0] - 2026-10-14

Upstream commit `0ddd5c9`, 14 files changed.

### Added
- `prompts.py` — 3 prompt templates (`literature_review`,
  `author_overview`, `citation_trace`), wired through MCP `list_prompts` /
  `get_prompt`
- `search_author` on arXiv (`au:"..."`) and Semantic Scholar
  (2-step: `/author/search` → `/author/{id}/papers`)
- `supports_author_search` flag on the provider base class
- Crossref year filtering via `filter=from-pub-date,until-pub-date`

### Fixed
- `get_abstract_details` returns `paper.to_dict()` instead of a bare Paper
  object, so `json.dumps` no longer raises
- Scopus `_fetch_abstract` degrades gracefully when `view=FULL` returns 401

## [2.1.0] - 2026-10-14

Upstream commit `45e6b69`, 32 files changed, 1133 insertions.

### Added
- `cache.py` — TTL cache, 300 s default
- `search_author` on Crossref, OpenAlex and Scopus
- `offset` on the search entry points for pagination
- Throttle, retry and exponential backoff in `http.py`

### Changed
- `merge.py` — smarter deduplication and source priority
- Provider registry rebuilt around capability flags
- 18 test modules (up from 17)

## [2.0.0] - 2026-09-26

Upstream commit `3ae2bcc`, 49 files, initial public release (MIT).

### Added
- Scopus, arXiv, OpenAlex, Semantic Scholar, Crossref, DBLP and Unpaywall
  providers with DOI-first deduplication
- MCP server exposing the unified, per-source, Scopus detail and SciVal
  tool groups
- Test suite, `config.json.example` and `uv.lock`
