---
title: "Bibliometric analysis is re-implemented in pure Python, not copied from GPL bibliometrix or pybibx"
author: Mahdy
date: 2026-11-24
branch: main
cost: { minutes: 20, tokens: 170699 }
id: l-8fba72be
scope: repo
status: active
src: agent
touches:
  - journal-scout/src/josc/bibliometrics.py
  - journal-scout/tests/test_bibliometrics.py
---

## Decided
- Bibliometric analysis (Bradford, Lotka, co-citation, coupling, Louvain, Callon thematic map, Kleinberg bursts, RPYS) is written from the original papers in pure Python with no new dependencies. The obvious references, bibliometrix (R), pybibx and bibliometrix-python, are GPL-3 and metaknowledge is GPL-2, while journal-scout is MIT, so their code cannot be copied in. litstudy (Apache-2.0) is the only one whose code could be borrowed, with attribution.
- Reference lists and countries come only from OpenAlex (`referenced_works`, `authorships[].countries`). Only the most-cited references (`resolve_references`, default 200) are resolved, so RPYS reports its coverage. Live run on 100 papers: about 24% of citation instances were resolved.
## Tried and ruled out
- Label propagation (already in `network.py`) for keyword clusters: dense weighted co-word graphs need modularity clustering, so a deterministic Louvain was added instead.
## Watch out
- OpenAlex OR filters take `doi:A|B`. `doi:A|doi:B` is rejected with "OR query between filters", and `get_many` swallowed that error, so multi-id batch lookups had silently returned nothing until this fix. One OR filter takes at most 100 values; chunks of 50 are used.
- In the code: `src/josc/bibliometrics.py`, `bibliometric_analysis` and `_resolve_references` in `src/josc/aggregator.py`, `get_many` and `_to_paper` in `src/josc/providers/openalex.py`.
