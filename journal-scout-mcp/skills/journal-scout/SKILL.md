---
name: journal-scout
description: Use when searching academic literature across multiple sources, looking up a paper by DOI, tracing citations or references, building a citation network, computing author or topic bibliometrics, or exporting bibliographies. Covers Scopus, arXiv, OpenAlex, Semantic Scholar, Crossref, PubMed, DBLP, Garuda, Unpaywall, and OpenCitations.
---

# journal-scout

Multi-source literature research through the `journal-scout-mcp` MCP server.
Results from every source are merged into one entry per paper (DOI-first
dedup), and partial failures are reported instead of aborting the search.

## When to use

- Literature review or topic survey across several databases at once.
- Looking up a specific paper by DOI, arXiv id, Scopus id, or OpenAlex id.
- Tracing what a paper cites (`get_references`) or who cites it (`get_citations`).
- Mapping how a research area evolved (`build_citation_network`).
- Author or topic bibliometrics: h-index, i10, g-index, AWCR.
- Producing a bibliography in BibTeX, RIS, EndNote, or a citation style.

Do not use it for full-text retrieval — the server returns metadata and
open-access links, not article bodies.

## Quick reference

| Tool | Purpose |
|---|---|
| `search_all` | Parallel search across all sources, merged and deduped; `topic=` narrows locally after the merge |
| `search_author` | Papers by an author name |
| `get_paper` | One record by identifier, with open-access resolution |
| `get_references` | Papers the given paper cites |
| `get_citations` | Papers citing the given paper |
| `get_related_works` | Semantically related papers |
| `build_citation_network` | Citation graph: `cites`, `coupled`, `cocited` edges |
| `compute_metrics` | h-index, i10, g-index, AWCR, citation velocity |
| `export_results` | BibTeX, RIS, EndNote, CSV, APA/Chicago/Harvard/Vancouver |
| `search_<source>` | One provider only, e.g. `search_scopus`, `search_pubmed` |
| `search_corpus` | AND search over saved search results already in the archive; no network calls |
| `identify_paper` | Turn a local PDF into metadata plus a resolved record |
| `check_watches` | Run saved-search watches and return papers not reported before |

Scopus extras: `get_abstract_details`, `get_author_profile`,
`get_quota_status`, plus the five `scival_*` metric tools.

## Query syntax

Boolean operators must be **uppercase**: `AND`, `OR`, `NOT`. Providers that
do not support an operator receive the query without it and report it in
`query_warnings`. Do not use field tags such as `TITLE:` or `AU:` — the
translator does not handle them.

## Working with results

- Always check `errors` and `filters_ignored` in the response. A source that
  failed does not fail the whole search, but the result set is incomplete.
- `sort="relevance"` is a local score: title matches weigh 3, abstract
  matches weigh 1, and `AND`/`OR`/`NOT` earn nothing.
- `coupled` and `cocited` edges only appear when `citing_limit` is large
  enough, because they derive from the citing papers' reference lists.
- Raise `reference_limit` for longer citation chains; cost grows linearly
  with the number of extra requests.

## Full guide

For parameter tables, web UI walkthrough, ready-to-use prompts, and known
limits, read `../../docs/journal-scout/05-usage-guide.md`.
