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

## Install: three ways to run it

| Mode | Runs where | Needs | Config |
|---|---|---|---|
| **A. Claude plugin → hosted server** (default) | Someone else's server | Nothing local | Server operator's keys |
| **B. Claude plugin → local stdio** | Your machine, launched by Claude | Python 3.10+, [`uv`](https://docs.astral.sh/uv/), `curl` | `config.json` or env vars |
| **C. Self-hosted HTTP** (Docker) | Your server | Docker | Env vars only |

### A. Claude plugin, hosted server

The shipped `.mcp.json` points the plugin at a hosted Streamable HTTP endpoint:

```json
{ "journal-scout": { "type": "http", "url": "https://journal.nimb.us.ci/mcp" } }
```

Install the plugin and the tools appear; nothing runs locally. You depend on
that server being up and on its operator's API keys and settings (for example
whether the Sci-Net fallback is on). To point at your own deployment instead,
copy `.mcp.remote.json.example` and change the URL; add
`"headers": {"Authorization": "Bearer <token>"}` when the server sets
`JOSC_MCP_TOKEN`.

### B. Claude plugin, local stdio (no server)

Run the MCP server as a child process of Claude, with your own keys:

```bash
cp .mcp.json.example .mcp.json        # stdio launcher, shown below
cp config.json.example config.json    # then fill in your keys
uv sync --extra pdf                   # optional: pre-build the venv
```

```json
{
  "journal-scout": {
    "type": "stdio",
    "command": "uv",
    "args": ["run", "--directory", "${CLAUDE_PLUGIN_ROOT}", "--extra", "pdf", "journal-scout"]
  }
}
```

`${CLAUDE_PLUGIN_ROOT}` expands to the installed plugin directory; outside a
plugin, replace it with the absolute path of this repo. `config.json` is read
from the repo root (it is git-ignored), and env vars override it. Restart
Claude after changing `.mcp.json`.

### C. Self-hosted HTTP server

See [Remote MCP server](#remote-mcp-server) below: one Docker image serves
`/mcp`, the `josc-web` UI, and the REST API.

## Tools (44)

| Unified (12) | Papers & abstracts (6) | Per-source (8) |
|---|---|---|
| `search_all` | `get_paper` | `search_scopus` |
| `search_author` | `get_paper_abstract` | `search_arxiv` |
| `get_citations` | `get_abstracts` | `search_openalex` |
| `get_references` | `identify_paper` | `search_crossref` |
| `get_related_works` | `get_fulltext` | `search_pubmed` |
| `build_citation_network` | | `search_garuda` |
| `compute_metrics` | `get_pdf` | `search_consensus` |
| `export_results` | | `search_exa` |
| `build_research_landscape` | | |
| `batch_lookup` | | |
| `topic_classify` | | |
| `bibliometric_analysis` | | |

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

### Full text

`get_fulltext` resolves one identifier through the same lookup path as
`get_paper` (including the Unpaywall enricher), then tries PDF routes in order,
moving on only when a route fails (HTTP error, or a reply that is not a PDF,
such as a landing page or bot challenge):

| # | `pdf_source` | Where the PDF link comes from |
|---|---|---|
| 1 | `open_access`, `arxiv` | The record's own OA link, then `https://arxiv.org/pdf/<id>` |
| 2 | `crossref` | `application/pdf` links the publisher deposited at Crossref |
| 3 | `landing` | `<meta name="citation_pdf_url">` on the page `doi.org/<doi>` redirects to |
| 4 | `acm`, `nejm_ai`, `peerj` | Built-in URL patterns for `10.1145/`, `10.1056/AI…`, `10.7717/peerj…` |
| 5 | `scinet` | `sci-net.xyz/<doi>`, **only when enabled** (see below) |

Steps 2 and 3 work for any publisher, so new publishers rarely need a pattern.
A DOI that no metadata source knows can still be fetched by these DOI-only
routes.

Each URL is downloaded with **system `curl` first**, and retried with the Python
HTTP client (httpx) if curl fails; some publisher front ends (e.g. Springer's
"Client Challenge") refuse httpx but serve curl. Without `curl` on `PATH`, only
httpx is used.

| Field | Meaning |
|---|---|
| `status` | `found`, `no_oa`, `not_found`, or `error` |
| `full_text` | Extracted text, capped by `max_chars` (default 20,000) |
| `truncated` | True when the source text was longer than `max_chars` |
| `pdf_url` | The PDF that produced the text (or the last one tried, on error) |
| `pdf_source` | The route above that succeeded |
| `via` | `curl` or `httpx`: the client that downloaded it |
| `attempts` | Every failed `{source, pdf_url, via, error}` before the result |
| `error` | Last failure reason, for `status="error"` |

| Setting | Env var | `config.json` | Tool argument | Default |
|---|---|---|---|---|
| Sci-Net fallback | `JOURNAL_SCOUT_SCINET=1` | `"scinet_fallback": true` | `scinet` | **off** |
| curl first | `JOURNAL_SCOUT_CURL=0` | `"curl_fallback": false` | `curl` | on |

Steps 1–4 only fetch copies the publisher or a repository serves openly; a
paper with no such copy reports `no_oa`. Sci-Net is different: it hosts papers
outside their publishers' licences, so it is opt-in, always labelled
`pdf_source="scinet"`, and whether to enable it is the operator's call.

Extraction needs `pypdf`, which ships in the `pdf` extra
(`pip install "journal-scout[pdf]"`) and is installed in the Docker image. A
server without it returns `status="error"` with an install hint rather than an
empty string.

### PDF file download

`get_pdf` returns the PDF **file**, not its text. It walks the same routes as
`get_fulltext` and checks the bytes are a PDF (no `pypdf` needed). Where the
file lands depends on how the client reaches the server:

| Server mode | `delivery` | What happens |
|---|---|---|
| Local stdio (install mode B) | `saved` | Written to `<folder>/source/pdf/<doi>.pdf`; `path` is returned |
| Remote HTTP (modes A and C) | `download` | The server cannot write to your disk. It keeps the PDF for 15 minutes and returns `download_url`, `save_path` and a ready `command` (`mkdir -p ... && curl -fsSL -o ...`) that the client runs in its working folder |

`<folder>` is `save_dir` when given (relative paths resolve against the working
folder), else the client's first MCP root, i.e. the folder Claude is working
in, else `JOSC_PDF_DIR` (used as is), else the server's working directory.
`filename` overrides the default name (`10.1016/j.x.1` becomes
`10.1016_j.x.1.pdf`); directory parts in it are dropped.

The download link is `GET /api/pdf?identifier=<doi>&filename=<name>`. Called
without a prior `get_pdf`, it resolves the PDF on demand, and `scinet` and
`curl` query flags override the server settings. A paper with no PDF answers
JSON with status 404 (`not_found`, `no_oa`) or 502 (`error`).

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

### Bibliometric analysis

`bibliometric_analysis` runs bibliometrix/VOSviewer-style science mapping over
a corpus: pass `query` to search (same filters as `search_all`) or `papers` to
analyse records you already have. Every analysis is pure Python with no new
dependencies; pick a subset with `analyses`.

| Analysis | What it returns |
|---|---|
| `summary` | Main information: timespan, annual growth rate, average citations, collaboration index, co-authors per document, international co-authorship %, field coverage |
| `annual_production` | Papers and citations per year |
| `sources` / `authors` / `institutions` / `keywords` | Top-N with documents, citations, h-index (authors also fractionalised) |
| `countries` | SCP/MCP production per country and country collaboration pairs |
| `bradford` | Bradford zones, core sources, Bradford multiplier |
| `lotka` | Author productivity, fitted beta, K-S test against classic Lotka |
| `networks` | Co-authorship, keyword co-occurrence, country and institution collaboration, co-citation, bibliographic coupling; Louvain communities, association strength |
| `thematic_map` | Callon centrality/density quadrants (motor, niche, basic, emerging/declining) |
| `trend_topics` | Q1/median/Q3 year per term |
| `bursts` | Kleinberg keyword bursts with start, end and strength |
| `rpys` | Reference Publication Year Spectroscopy with peak years |
| `three_field` | Sankey links authors → keywords → countries (or sources) |

References and countries come from OpenAlex, so include `openalex` in
`sources` for `co_citation`, `bibliographic_coupling` and `rpys`. The
`resolve_references` most-cited references (default 200) are looked up on
OpenAlex for co-citation labels and RPYS years; the result reports coverage.
Export one network with `graph_network` and `graph_format="graphml"` (Gephi)
or `"pajek"` (VOSviewer, Pajek). Authors are matched by normalised name.

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
TOKEN="$(openssl rand -hex 32)"; echo "MCP token: $TOKEN"
docker run -d --name journal-scout -p 8080:8080 \
  -e JOSC_MCP_TOKEN="$TOKEN" \
  -e SCOPUS_API_KEY=... \
  -e JOURNAL_SCOUT_EMAIL=you@example.com \
  journal-scout
curl http://localhost:8080/healthz
```

Inside the image, pass every key and setting as an **environment variable**
(or `--env-file .env`): the package is installed into site-packages, so the
repo-root `config.json` that a source checkout reads is not used. The image
includes `curl` for the curl-first PDF downloads.

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
| `JOSC_WEB_DIST` | `/app/web/dist` in Docker | Built UI directory served at `/` |
| `JOSC_PUBLIC_URL` | from request headers | Public base URL for `get_pdf` download links, e.g. `https://journal.example` |
| `JOSC_PDF_DIR` | unset | stdio only: folder `get_pdf` saves to when the client exposes no MCP root |

API keys and behaviour (each also has a `config.json` key for source checkouts):

| Variable | `config.json` key | Purpose |
|---|---|---|
| `SCOPUS_API_KEY` | `api_key` | Elsevier key; required for Scopus / SciVal tools |
| `OPENALEX_API_KEY` | `openalex_api_key` | OpenAlex premium key |
| `CONSENSUS_API_KEYS` / `CONSENSUS_API_KEY` | `consensus_api_key` | Consensus key list (rotated) or single key |
| `EXA_API_KEYS` / `EXA_API_KEY` | — | Optional Exa keys (rotated); env only |
| `JOURNAL_SCOUT_EMAIL` | `polite_email` | Contact email for OpenAlex / Crossref / Unpaywall polite pools |
| `JOURNAL_SCOUT_CACHE_TTL` | `cache_ttl` | Seconds to cache identical upstream queries (`0` disables) |
| `JOURNAL_SCOUT_SCINET` | `scinet_fallback` | Enable the Sci-Net full-text fallback (default off) |
| `JOURNAL_SCOUT_CURL` | `curl_fallback` | Download PDFs with curl first (default on) |
| `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN` | `turso_url`, `turso_token` | Optional libSQL/Turso persistence for history and watches |

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
| `GET /api/pdf?identifier=&filename=` | Paper PDF as a file download (see [PDF file download](#pdf-file-download)) |

The UI routes are `/` (search), `/landscape`, `/graph`, `/metrics`, `/pdf`,
`/history` (the recorded search list, with replay, split, duplicate, export,
and import), and `/docs`. `/pdf` takes one or more DOIs or arXiv ids, one per
line, and downloads each PDF through `/api/pdf`, with a Sci-Net override and
optional auto-save; `/pdf?doi=<doi>` prefills the form.

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
uv sync --extra dev --extra pdf --extra server
uv run pytest
uv run ruff check src tests
```

Run the tests through `uv run`: the lockfile pins `mcp` 1.x, and a global
Python with `mcp` 2.x fails the schema tests (`Tool.inputSchema` was renamed).
Tests never call real `curl`; `tests/conftest.py` disables it.

## License

MIT. See `LICENSE`.
