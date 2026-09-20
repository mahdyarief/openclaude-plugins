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
