# journal-scout-mcp

Multi-source journal research **MCP server** for Anthropic Claude. Searches
Scopus, arXiv, OpenAlex, Semantic Scholar, Crossref, DBLP, and Unpaywall,
then merges duplicate results into one entry per paper (DOI-first dedup)
and reports partial failures.

This is a **Claude skill** for using the `journal-scout-mcp` MCP server.
Configure the MCP server in your Claude Code/plugin setup, then invoke any
of the available tools.

## Setup

1. **Install the MCP server** in your Claude config (`~/.claude.json` or
   equivalent). The server runs from the `journal-scout-mcp` repo as an
   MCP plugin:

   ```json
   {
     "journal-scout-mcp": {
       "command": "uv",
       "args": ["--directory", "${CLAUDE_PLUGIN_ROOT}", "run", "python", "-m", "journal_scout_mcp.server"]
     }
   }
   ```

2. **Configure credentials** — copy `config.json.example` to `config.json`.
   Only the Elsevier `api_key` (Scopus) is required; all other sources work
   without a key. `polite_email` improves rate limits on OpenAlex, Crossref,
   and Unpaywall.

3. **Enable** the plugin in your Claude session. The tool list includes:

   - **Unified:** `search_all`, `get_paper`, `get_citations`
   - **Per-source:** `search_scopus`, `search_arxiv`, `search_openalex`,
     `search_semanticscholar`, `search_crossref`, `search_dblp`
   - **Scopus detail:** `get_abstract_details`, `get_author_profile`,
     `get_quota_status`
   - **SciVal:** `scival_author_metrics`,
     `scival_institution_metrics`, `scival_author_lookup`,
     `scival_institution_lookup`, `scival_topic_metrics`

4. **Restart** Claude / plugin if the tool list does not reload.

## When to use

- **Literature review** — `search_all` or per-source searches to gather
  papers on a topic.
- **Author / affiliation research** — `search_author`,
  `get_author_profile`, SciVal metrics.
- **Paper lookup** — `get_paper` by DOI/arXiv ID.
- **Citation network** — `get_citations` for a paper.
- **Open-access check** — Unpaywall via `get_paper` / `get_citations`.

## Usage examples

- Find papers by an author: `search_author(name="Zaizhang Wu")`
- Search papers by keyword: `search_all(query="deep learning")`
- Get abstract details for a Scopus ID: `get_abstract_details(scopus_id="27624627907")`

## Notes

- Scopus `view=FULL` is degraded gracefully (falls back to abstract snippet)
  when entitlement is missing.
- DBLP may be blocked by a bot challenge from some IPs — treat results as
  partial.
- All network errors are reported as partial failures in `search_all` results.
