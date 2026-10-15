# Changelog

All notable changes to this project will be documented in this file.

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
