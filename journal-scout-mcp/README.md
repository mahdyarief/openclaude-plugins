# journal-scout-mcp

Multi-source journal research MCP server. Searches Scopus, arXiv, OpenAlex,
Semantic Scholar, Crossref, DBLP, and Unpaywall, then merges duplicate results
into one entry per paper (DOI-first dedup) and reports partial failures.

## Tools (17)

| Unified | Per-source | Scopus detail |
|---|---|---|
| `search_all` | `search_scopus` | `get_abstract_details` |
| `get_paper` | `search_arxiv` | `get_author_profile` |
| `get_citations` | `search_openalex` | `get_quota_status` |
| | `search_semanticscholar` | SciVal |
| | `search_crossref` | `scival_author_metrics` |
| | `search_dblp` | `scival_institution_metrics` |
| | | `scival_author_lookup` |
| | | `scival_institution_lookup` |
| | | `scival_topic_metrics` |

## Config

Copy `config.json.example` to `config.json`. Only the Elsevier `api_key` is
required; the other sources work without a key. `polite_email` improves rate
limits on OpenAlex, Crossref, and Unpaywall.

## Objectives

- **Search** 6 scholarly databases from one MCP server.
- **Merge** duplicates by DOI-first dedup.
- **Report** partial failures (per-source) so callers never get a 500 for one
  blackholed API.
- **Degrade** gracefully where entitlements are missing (e.g. Scopus `view=FULL`).

## Development

```bash
uv venv
uv pip install -e ".[dev]"
pytest
```

## License

MIT. See `LICENSE`.
