---
title: Sci-Hub bypass rejected; open-access PDFs come from CORE after Unpaywall
author: Mahdy
date: 2026-11-18
branch: main
id: l-6001ff8f
scope: repo
status: active
src: agent
touches:
  - journal-scout/.mcp.json
  - journal-scout/.mcp.json.example
  - journal-scout/README.md
  - journal-scout/config.json.example
  - journal-scout/pyproject.toml
  - journal-scout/src/josc/api/app.py
  - journal-scout/src/josc/api/state.py
  - journal-scout/src/josc/config.py
  - journal-scout/src/josc/providers/__init__.py
  - journal-scout/src/josc/providers/openalex.py
---

## Decided
- Do not add a Sci-Hub bypass resolver. The user asked for it; the answer stayed with legal open-access resolution because bypassing paywalls is not something we ship.
- Resolve extra full-text links through CORE as an enricher (`CoreProvider`), after Unpaywall, only filling a missing `pdf_url`.
## Tried and ruled out
- `scihub` (zaytoun/scihub.py, ~1.1k stars): installed in a throwaway venv and fetched two DOIs. It failed with DocumentUrlNotFound and SSL errors because its hard-coded mirror list is stale, so wrapping it would ship a dependency that returns nothing.
- CORE works only with a key in practice: the public endpoint answers HTTP 429 without one, and `https://api.core.ac.uk/v3/search/works` needs the trailing slash or returns a 301 HTML redirect.
## Watch out
- `_enrich` skips records without a DOI, so CORE never runs for DOI-less results.
- In the code: `src/josc/providers/core.py`, `_enrich` in `src/josc/aggregator.py`, `get_core_api_key` in `src/josc/config.py`.
