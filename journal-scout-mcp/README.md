# journal-scout-mcp

Multi-source journal research MCP server. Searches Scopus, arXiv, OpenAlex,
Semantic Scholar, Crossref, PubMed, DBLP, and Garuda, then merges duplicate
results into one entry per paper (DOI-first dedup) and reports partial failures.
Unpaywall resolves open-access copies and OpenCitations supplies citation links.

It also builds Connected-Papers-style citation networks (direct citations,
bibliographic coupling, co-citation) and computes Publish-or-Perish style
bibliometrics, and ships a browser UI (`josc-web`).

Citation links come from OpenCitations as well: 300M+ DOI-to-DOI links, free,
no API key, no approval. It is not a searchable source — it only answers
citation and reference queries for a known DOI or OpenCitations id.

## Tools (25)

| Unified | Per-source | Scopus detail |
|---|---|---|
| `search_all` | `search_scopus` | `get_abstract_details` |
| `search_author` | `search_arxiv` | `get_author_profile` |
| `get_paper` | `search_openalex` | `get_quota_status` |
| `get_citations` | `search_semanticscholar` | SciVal |
| `get_references` | `search_crossref` | `scival_author_metrics` |
| `get_related_works` | `search_pubmed` | `scival_institution_metrics` |
| `build_citation_network` | `search_dblp` | `scival_author_lookup` |
| `compute_metrics` | `search_garuda` | `scival_institution_lookup` |
| `export_results` | | `scival_topic_metrics` |

`search_all` accepts a `topic` filter. It runs **after** the merge and keeps
records whose `topics` contain the text (case-insensitive substring). It is
deliberately not pushed down to providers: OpenAlex concepts, Crossref
subjects, and PubMed MeSH share no vocabulary, so a local pass costs zero
extra requests and gives one consistent semantic.

### Export

`export_results` renders any list of paper dicts in one of 17 formats:
`apa`, `bibtex`, `chicago`, `csiro`, `csv`, `csv_bom`, `csv_header`,
`csv_plain`, `endnote`, `harvard`, `isi`, `json`, `mla`, `ris`, `vancouver`,
`xls`, `xls_plain`. The same engine is exposed over HTTP as `POST /api/export`.

### Citation networks

`build_citation_network` resolves the seed paper, fetches its references and
citing papers from every capable source, then fetches the reference lists of
the top citing papers to derive three edge types:

| Edge | Meaning |
|---|---|
| `cites` | Direct citation (seed → reference, citing paper → seed) |
| `coupled` | Bibliographic coupling: references shared with the seed |
| `cocited` | Co-citation: reference pairs appearing together in citing papers |

Pass `graph_format="graphml"` to get a Gephi/VOSviewer file instead of JSON.

`get_references` exposes just the merged reference list of one paper.

Providers that answer citation queries: OpenAlex, Semantic Scholar, Crossref
and OpenCitations. OpenCitations adds links the others miss (and vice versa),
and its metadata is resolved through the OpenCitations Meta API with a
Crossref batch fallback, so a paper is returned even when one of the two
cannot describe it.

### Metrics

`compute_metrics` accepts either `author` or `query` and returns papers, total
citations, h-index, i10-index, g-index, max/mean citations, and citation
velocity over the merged multi-source result set. `mode="extended"` adds the
Publish-or-Perish indices: `hc_index`, `hI_index` (Batista), `hI_norm`,
`hm_index` (Schreiber), `AWCR`, `AW_index`, `AWCRpA`, plus citation ratios.

## Config

Copy `config.json.example` to `config.json`. Only the Elsevier `api_key` is
required; the other sources work without a key. `semantic_scholar_api_key`
raises the Semantic Scholar rate limit, and `polite_email` improves rate limits
on OpenAlex, Crossref, and Unpaywall.

## josc-web

`web/` is a Vite + React 19 + TanStack Router + Tailwind 4 app that talks to a
thin Starlette API (`src/josc/api/`) over the same aggregator the MCP server
uses.

```bash
pip install -e ".[web]"

cd web && npm install && npm run build && cd ..

josc-web        # serves the API and the built UI on :8793
```

For UI development, run `npm run dev` inside `web/` (Vite proxies `/api` to
`127.0.0.1:8793`).

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Provider list and capability flags |
| `GET /api/quota` | Scopus quota state |
| `GET /api/search?query=&topic=` | Fan-out search, optional post-merge topic filter |
| `GET /api/search-author?author=` | Author search |
| `GET /api/paper?identifier=` | Resolve one paper |
| `GET /api/citations?identifier=` | Citing papers |
| `GET /api/references?identifier=` | Reference list |
| `GET /api/related?identifier=` | Related works (OpenAlex) |
| `GET /api/network?identifier=&format=json\|graphml` | Citation network |
| `GET /api/metrics?author=\|query=&mode=basic\|extended` | Bibliometric summary |
| `GET /api/metrics/export`, `GET /api/metrics/report` | Metrics as CSV / report |
| `GET /api/searches?limit=` | Recorded search history |
| `POST /api/searches/import`, `GET /api/searches/export` | Import / export history archives |
| `POST /api/searches/{id}/replay\|split\|duplicate` | Re-run, split, or copy a saved search |
| `DELETE /api/searches/{id}` | Delete a saved search |
| `POST /api/import` | Import BibTeX / RIS / CSV records |
| `POST /api/cache/clear`, `GET /api/cache/info` | Cache control and telemetry |
| `POST /api/merge` | Merge an external record list |
| `GET /api/export/graphml?identifier=` | GraphML download |
| `POST /api/export` | Bibliography export (JSON body: `papers`, `format`) |

The UI has four routes: `/` (search), `/graph`, `/metrics`, and `/history`
(the recorded search list, with replay, split, duplicate, export, and import).

## Objectives

- **Search** 8 scholarly databases from one MCP server, plus OpenCitations for
  citation links on any DOI.
- **Merge** duplicates by DOI-first dedup.
- **Report** partial failures (per-source) so callers never get a 500 for one
  blackholed API.
- **Degrade** gracefully where entitlements are missing (e.g. Scopus `view=FULL`).
- **Map** citation structure with coupling/co-citation and export it to GraphML.

## Development

```bash
uv venv
uv pip install -e ".[dev]"
pytest
```

## License

MIT. See `LICENSE`.
