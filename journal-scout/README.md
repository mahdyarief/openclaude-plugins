# journal-scout

Multi-source journal research MCP server. Searches Scopus, arXiv, OpenAlex,
Crossref, PubMed, Consensus, and Garuda, then merges duplicate
results into one entry per paper (DOI-first dedup) and reports partial failures.
Unpaywall resolves open-access copies and OpenCitations supplies citation links.

It also builds Connected-Papers-style citation networks (direct citations,
bibliographic coupling, co-citation) and computes Publish-or-Perish style
bibliometrics, and ships a browser UI (`josc-web`).

Citation links come from OpenCitations as well: 300M+ DOI-to-DOI links, free,
no API key, no approval. It is not a searchable source — it only answers
citation and reference queries for a known DOI or OpenCitations id.

## Tools (43)

| Unified (11) | Papers & abstracts (5) | Per-source (8) |
|---|---|---|
| `search_all` | `get_paper` | `search_scopus` |
| `search_author` | `get_paper_abstract` | `search_arxiv` |
| `get_citations` | `get_abstracts` | `search_openalex` |
| `get_references` | `identify_paper` | `search_crossref` |
| `get_related_works` | `get_fulltext` | `search_pubmed` |
| `build_citation_network` | | `search_garuda` |
| `compute_metrics` | | `search_consensus` |
| `export_results` | | `search_exa` |
| `build_research_landscape` | | |
| `batch_lookup` | | |
| `topic_classify` | | |

| Scopus detail (3) | SciVal (5) | Local archive (2) |
|---|---|---|
| `get_abstract_details` | `scival_author_metrics` | `search_corpus` |
| `get_author_profile` | `scival_institution_metrics` | `check_watches` |
| `get_quota_status` | `scival_author_lookup` | |
| | `scival_institution_lookup` | |
| | `scival_topic_metrics` | |

| Keys (1) | SLR pipeline (8) |
|---|---|
| `rotate_consensus_key` | `slr_import`, `slr_screen`, `slr_full_text`, `slr_appraise`, `slr_extract`, `slr_prisma`, `slr_summary`, `slr_reset` |

`search_all` accepts a `topic` filter. It runs **after** the merge and keeps
records whose `topics` contain the text (case-insensitive substring). It is
deliberately not pushed down to providers: OpenAlex concepts, Crossref
subjects, and PubMed MeSH share no vocabulary, so a local pass costs zero
extra requests and gives one consistent semantic.

### Abstract resolution

`get_paper_abstract` resolves the abstract of one paper (by DOI, another
identifier, or title) across every lookup-capable provider. `get_abstracts`
fills missing abstracts in a list of paper dicts, such as `search_all`
results. Both keep the `not_found` status with a null abstract when no source
has one; nothing is guessed from the title, and an existing abstract is never
overwritten. Provider errors and timeouts are reported per source instead of
aborting the batch.

### Full text (open access only)

`get_fulltext` resolves one identifier through the same lookup path as
`get_paper` (including the Unpaywall enricher), downloads the best open-access
PDF, and returns its extracted text. arXiv records without a resolved PDF link
fall back to `https://arxiv.org/pdf/<id>`.

| Field | Meaning |
|---|---|
| `status` | `found`, `no_oa`, `not_found`, or `error` |
| `full_text` | Extracted text, capped by `max_chars` (default 20,000) |
| `truncated` | True when the source text was longer than `max_chars` |
| `error` | Download or extraction failure reason, for `status="error"` |

Extraction needs `pypdf`, which ships in the `pdf` extra
(`pip install "journal-scout[pdf]"`) and is installed in the Docker image. A
server without it returns `status="error"` with an install hint rather than an
empty string. This is not a paywall bypass: a paper with no OA copy reports
`no_oa`.

### Batch lookup

`batch_lookup` resolves a list of identifiers (DOI, arXiv id, OpenAlex id) in
one call. OpenAlex accepts pipe-separated OR filters (`doi:A|B`,
`openalex:W1|W2`) and arXiv accepts a native `id_list`, so those two answer a
whole batch with a single request each. Providers without a batch endpoint fall
back to one `get` per identifier, concurrently.

| Field | Meaning |
|---|---|
| `papers` | Resolved records in the same order as `identifiers`, deduplicated |
| `counts` | `requested` (unique, after dedup) and `resolved` |
| `not_found` | Identifiers no provider recognised |
| `errors` | Per-provider failure message; other providers still contribute |

Pass `sources` to restrict the lookup to specific providers. Enrichers such as
Unpaywall are skipped here — they need a DOI and add no lookup value.

### Topic classify

`topic_classify` ranks OpenAlex taxonomy entries that best match free text —
a title, abstract, or research question. Short labels match the taxonomy
search directly; longer text that the taxonomy endpoint cannot match falls
back to aggregating the assigned topics of matching works. Each candidate
carries a relevance `score`, work counts, keywords, and the full
domain → field → subfield → topic `path`.

| Field | Meaning |
|---|---|
| `text` | Required: the text to classify |
| `level` | `topic` (default), `subfield`, `field`, or `domain` |
| `limit` | Candidates to return, best first (default 5) |

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

Providers that answer citation queries: OpenAlex, Crossref
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
required; the other sources work without a key. `polite_email` improves rate
limits on OpenAlex, Crossref, and Unpaywall.

`search_exa` searches the web through Exa's public MCP endpoint
(`https://mcp.exa.ai/mcp`); it needs no API key. If `EXA_API_KEYS` (or
`EXA_API_KEY`) is set, pass a comma- or semicolon-separated list or a JSON
array to rotate across keys round-robin, and an HTTP 401/429 moves the client
to the next key. Keys are read from the environment only, so no file inside
the container is written. Exa answers with plain text rather than JSON; the
provider parses the `Title` / `URL` / `Published` / `Author` / `Highlights`
blocks and uses `Highlights` as the abstract.

Consensus keys work the same way: set `CONSENSUS_API_KEYS` to a list (or
`CONSENSUS_API_KEY` for a single key) and the provider rotates on 401/429.
The free tier has a monthly quota: once it is spent the API replies 429 with
`code: "hard_cap_reached"`, and that explanation is passed through in the
tool's `errors` instead of a bare status code.

## Rate limits

| Source | Limit |
|---|---|
| Scopus | Weekly quota, tracked via `X-RateLimit-*` / `X-ELS-Status` headers |
| OpenAlex | 100,000 requests/day (polite pool) |
| Crossref | Polite pool, no hard cap |
| PubMed | 3 requests/second without a key, 10 with |
| arXiv | 1 request per 3 seconds |
| Consensus | Per-account quota; rotate keys on 401/429 |
| OpenCitations | 180 requests/minute |
| Unpaywall | 100,000 requests/day |

## Remote MCP server

The MCP server can run as a standalone Streamable HTTP service for remote MCP
clients. One image serves both surfaces:

| Path | Purpose |
|---|---|
| `/` and all SPA routes | The `josc-web` browser UI |
| `/api/*` | REST API used by the browser UI |
| `/mcp` | Streamable HTTP MCP endpoint |
| `/healthz` | Unauthenticated container health check |

The Docker image builds the frontend in a `node:22-alpine` stage and listens on
port `8080`. Configure `JOSC_MCP_TOKEN` to enforce bearer-token authentication
on `/mcp`; the UI and `/healthz` stay public. The stdio transport remains the
default when running from source.

```bash
docker build -t journal-scout .
docker run --rm -p 8080:8080 \
  -e JOSC_MCP_TOKEN="$(openssl rand -hex 32)" \
  journal-scout
```

Configure remote MCP clients with URL `https://<your-domain>/mcp` and send
`Authorization: Bearer <token>` when authentication is enabled. The plugin's
`.mcp.json` points at the hosted server via `type: "http"`; use
`.mcp.remote.json.example` as a client config template.

Environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `JOSC_TRANSPORT` | `stdio` | Set `http` to enable Streamable HTTP |
| `JOSC_HOST` | `0.0.0.0` | HTTP bind address |
| `JOSC_PORT` | `8080` | HTTP listen port |
| `JOSC_MCP_TOKEN` | unset | Optional bearer token; set it for public deployments |

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
- **Resolve** abstracts for one paper or a whole result list from all available sources.
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
