# 01 — Kondisi Aktual journal-scout

Ringkasan arsitektur dan permukaan API yang benar-benar ada di kode saat ini.
Semua nomor baris merujuk ke repo ini.

## Arsitektur

```
src/josc/
├── server.py       MCP server (stdio), 23 tool
├── api.py          Starlette HTTP API, 10 route
├── aggregator.py   Orkestrasi lintas provider (fan-out, merge, enrich)
├── providers/      9 provider (7 searchable, 1 enricher, 1 citation-only)
├── merge.py        Dedup + prioritas sumber
├── graph.py        Network builder + metrik + GraphML
├── exporters.py    11 formatter (bibtex … vancouver)
├── http.py         Fetcher: throttle, retry, backoff
├── cache.py        TTLCache in-memory (300 s / 1024 entri)
├── store.py        Turso/libSQL cache persisten (opsional)
├── config.py       Env var + API key
├── models.py       Dataclass Paper
├── prompts.py      3 prompt template MCP
└── utils.py        Normalisasi DOI/title, parser angka
```

## MCP server

`src/josc/server.py:17-36` mendefinisikan daftar tool:

| Kelompok | Tool |
|---|---|
| Unified (8) | `search_all`, `search_author`, `get_paper`, `get_citations`, `get_references`, `build_citation_network`, `compute_metrics`, `export_results` |
| Per-source (7) | `search_scopus`, `search_arxiv`, `search_openalex`, `search_semanticscholar`, `search_crossref`, `search_pubmed`, `search_dblp` |
| Scopus detail (3) | `get_abstract_details`, `get_author_profile`, `get_quota_status` |
| SciVal (5) | `scival_author_metrics`, `scival_institution_metrics`, `scival_author_lookup`, `scival_institution_lookup`, `scival_topic_metrics` |

Skema pencarian (`src/josc/server.py:40-57`) punya:
`query`, `count`, `author`, `venue`, `year_from`, `year_to`, `tech_only`,
`offset`.

Prompt template (`src/josc/prompts.py:62-89`): `literature_review`,
`author_overview`, `citation_trace`.

## HTTP API

Route di `src/josc/api.py:361-372`:

| Route | Handler |
|---|---|
| `GET /api/health` | `health` (`api.py:159`) |
| `GET /api/search` | `search` (`api.py:180`) |
| `GET /api/search-author` | `search_author` (`api.py:212`) |
| `GET /api/paper` | `paper` (`api.py:242`) |
| `GET /api/citations` | `citations` (`api.py:250`) |
| `GET /api/references` | `references` (`api.py:260`) |
| `GET /api/network` | `network` (`api.py:270`) |
| `GET /api/metrics` | `metrics` (`api.py:305`) |
| `GET /api/export/graphml` | `graphml_export` (`api.py:337`) |
| `POST /api/export` | `export` (`api.py:341`) |

Semua endpoint baca memakai cache lewat `_cached` (`api.py:76`). Empat di
antaranya — `search`, `search-author`, `network`, `metrics` — menerima
`?offline=true`: payload disajikan dari cache Turso dengan `stale: true`, dan
bila tidak ada entri hasilnya `503` `{"offline": true, "error": ...}`.

### Bentuk respons `/api/health`

```json
{
  "status": "ok",
  "sources": ["scopus", "arxiv", "..."],
  "cache": {
    "ttl": 300.0, "entries": 0, "max_entries": 1024,
    "hits": 0, "misses": 0, "sets": 0,
    "evictions": 0, "expired": 0, "hit_rate": 0.0
  },
  "store": {
    "backend": "turso", "ttl": 300.0,
    "entries": 0, "expired": 0,
    "hits": 0, "misses": 0, "sets": 0, "hit_rate": 0.0
  },
  "capabilities": {
    "<provider>": {
      "search": true, "citations": false,
      "references": false, "author_search": false,
      "tech_only": false
    }
  }
}
```

`cache` bernilai `null` bila caching dimatikan. Blok ini dibangun oleh
`_cache_stats()` (`api.py`) dari satu `fetcher` bersama yang dipakai
semua provider — tidak ada instance cache kedua dan tidak ada global state.
`store` bernilai `null` bila Turso tidak dikonfigurasi; dibangun oleh
`_store_stats()` (`api.py:145`) dari `TursoCache.stats()` (`store.py:170`).

## Web UI

Tiga route (`web/src/router.tsx:63-86`):

| Path | File | Isi |
|---|---|---|
| `/` | `web/src/routes/search.tsx` | form pencarian + daftar hasil |
| `/graph` | `web/src/routes/graph.tsx` | visualisasi force-directed |
| `/metrics` | `web/src/routes/metrics.tsx` | kartu metrik + tabel sitasi per tahun |

Komponen: `ForceGraph.tsx` (d3-force), `PaperCard.tsx` (kartu hasil).

## Metrik yang dihitung

`compute_metrics` (`src/josc/graph.py:204-264`) punya dua mode:

- `mode="basic"` — `papers`, `total_citations`, `h_index`, `i10_index`,
  `g_index`, `max_citations`, `mean_citations`, `citation_velocity`,
  `e_index`, plus rasio `cites_year`, `cites_paper`, `cites_author`,
  `papers_author`, `authors_paper`.
- `mode="extended"` — superset, menambah `hc_index`, `hI_index`, `hI_norm`,
  `AWCR`, `AW_index`, `AWCRpA`, `hm_index`.

`mode` diteruskan utuh ke jalur publik: `aggregator.compute_metrics(mode=...)`
(`aggregator.py:348`) → `GET /api/metrics?mode=extended` (`api.py:270`) dan
tool MCP `compute_metrics` (`server.py:184`). Nilai selain `basic`/`extended`
ditolak dengan `ValueError`.

Implementasi indeks: `h_index` (`graph.py:56`), `i10_index` (`graph.py:68`),
`g_index` (`graph.py:73`), `citation_velocity` (`graph.py:85`), `e_index`
(`graph.py:103`), `awcr` (`graph.py:119`), `aw_index` (`graph.py:131`),
`hc_index` (`graph.py:140`), `hI_index` (`graph.py:156`), `hI_norm`
(`graph.py:170`), `hm_index` (`graph.py:183`).

Tiga metrik individual-h berbeda dan tidak boleh saling dipertukarkan:
`hI_index` = `h / rata-rata penulis di h-core` (Batista), `hI_norm` =
h-index dari `citations / jumlah_penulis` per paper, `hm_index` = rank
efektif `Σ 1/a` (Schreiber).

## Citation network

`build_network` (`src/josc/graph.py:395`) menghasilkan tiga tipe edge:
`cites`, `coupled`, `cocited`. Identitas node diselesaikan lebih dulu lewat
`_canonical_ids` (`graph.py:326`) dengan union-find atas DOI, provider ID, dan
judul ternormalisasi. `to_graphml` (`graph.py:517`) mengubahnya jadi GraphML.

## Ekspor

`src/josc/exporters.py` mendaftarkan 11 format: `apa`, `bibtex`, `chicago`,
`csv`, `csv_header`, `endnote`, `harvard`, `isi`, `json`, `ris`, `vancouver`.
`format_papers` (`exporters.py:438`) dipanggil dari dua tempat:

- tool MCP `export_results` (`server.py:187-206`, dispatch di `build_json`),
- route `POST /api/export` (`api.py:279-298`).

## Persistensi

- `TTLCache` (`src/josc/cache.py:15`) — in-memory, TTL 300 s, maks 1024 entri.
- `TursoStore` (`src/josc/store.py:52`) — cache respons HTTP persisten lewat
  Turso `/v2/pipeline`. Opsional; gagal → fallback ke in-memory.

Tidak ada persistensi objek query (tidak ada tabel `searches`).

## Dedup dan prioritas sumber

`src/josc/merge.py:9-18` menetapkan urutan otoritas:
`scopus > crossref > openalex > semanticscholar > dblp > arxiv >
opencitations > unpaywall`.

`_match_keys` (`merge.py:33`) mencocokkan berurutan: DOI → `(title, year)` →
`(title, first author)`.
