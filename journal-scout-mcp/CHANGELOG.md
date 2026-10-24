# Changelog

All notable changes to this project will be documented in this file.

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
- Offline mode: `?offline=true` serves cached payloads with `stale: true`
  and answers 503 when the key is missing
- Browser UI (`josc-web`): search form with the filter fields, citation
  graph viewer, metrics view, and an 11-format export menu
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
- 236 tests passing

## [2.1.0] - 2026-10-15

### Added
- `cache.py` — TTL LRU cache (300s default, pluggable backend)
- `exporters.py` — `format_papers()` supporting BibTeX (with umlaut escape),
  RIS (Crossref type → RIS type mapping), CSV
- `prompts.py` — 5 prompt templates, wired through MCP `list_prompts`/
  `get_prompt`
- `search_author` on arXiv (au:"...") + `supports_author_search` flag
- `search_author` on Semantic Scholar (2-step: /author/search →
  /author/{id}/papers)
- Crossref year filtering via `filter=from-pub-date,until-pub-date`
- `get_abstract_details` now returns `paper.to_dict()` (JSON-safe)
- RIS type defaults to `JOUR` when paper has no/invalid type

### Fixed
- `get_abstract_details` no longer raises on `json.dumps` (Paper object
  returned instead of dict)
- BibTeX umlauts escaped (`Jürgen` → `J{\"u}rgen`)
- Scopus `_authors()` handles dict-shaped `dc:creator`
- Scopus `_fetch_abstract` degrades gracefully when `view=FULL` returns 401

### Changed
- 139 tests passing (up from 129)

## [2.0.0] - 2026-09-21

### Added
- PR slop detection plugin
- Productivity hooks removal
- Docs and slide/typing skills

## [1.0.0] - 2026-09-21

### Added
- Initial release: Scopus, arXiv, OpenAlex, Semantic Scholar, Crossref,
  DBLP, Unpaywall search with DOI-first dedup
