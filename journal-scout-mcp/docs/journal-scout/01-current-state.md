# 01 — Kondisi Aktual journal-scout

Ringkasan arsitektur dan permukaan API yang benar-benar ada di kode saat ini.
Semua nomor baris merujuk ke repo ini.

## Arsitektur

```
src/josc/
├── server.py       MCP server (stdio), 24 tool
├── api.py          Starlette HTTP API, 16 route
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

`src/josc/server.py:17-37` mendefinisikan daftar tool:

| Kelompok | Tool |
|---|---|
| Unified (9) | `search_all`, `search_author`, `get_paper`, `get_citations`, `get_references`, `get_related_works`, `build_citation_network`, `compute_metrics`, `export_results` |
| Per-source (8) | `search_scopus`, `search_arxiv`, `search_openalex`, `search_semanticscholar`, `search_crossref`, `search_pubmed`, `search_dblp`, `search_garuda` |
| Scopus detail (3) | `get_abstract_details`, `get_author_profile`, `get_quota_status` |
| SciVal (5) | `scival_author_metrics`, `scival_institution_metrics`, `scival_author_lookup`, `scival_institution_lookup`, `scival_topic_metrics` |
| Local archive (3) | `search_corpus`, `identify_paper`, `check_watches` |

Skema pencarian (`src/josc/server.py:41-62`) punya:
`query`, `count`, `author`, `venue`, `year_from`, `year_to`, `tech_only`,
`offset`, `affiliation`, `issn`, `orcid`, `doi`. Empat field terakhir
diteruskan ke provider yang mendeklarasikannya di `supports_filters`; lihat
`02-provider-matrix.md`.

`search_all` juga menerima `topic` — filter lokal pasca-merge yang menjaga
hasil yang `topics`-nya mengandung teks tersebut (substring, case-insensitive).
Filter ini tidak diteruskan ke provider karena kosakata topik tiap provider
berbeda (OpenAlex concept, Crossref subject, PubMed MeSH); lihat
`aggregator._filter_by_topic` (`src/josc/aggregator.py`).

Tool `get_paper` menerima `identifier` dan `sources` (array opsional).
`sources` membatasi provider yang dihubungi: identifier numerik telanjang
ambigu karena Semantic Scholar membaca digit apa pun sebagai `CorpusId`,
PubMed sebagai PMID, dan Scopus sebagai Scopus id. Pemanggil yang memegang id
Garuda harus menyebutkan `sources: ["garuda"]`, kalau tidak provider lain ikut
menebak dan bisa mengembalikan paper yang sama sekali berbeda
(`aggregator.get_paper`, `src/josc/aggregator.py`).

Parameter `sources` yang sama juga ada di `get_citations`, `get_references`,
dan `get_related_works` (`aggregator.py`), dan diteruskan lewat query param
`source` di `GET /api/citations`, `GET /api/references`, `GET /api/related`.

`search_corpus` menjawab pencarian teks penuh tanpa jaringan. `load_corpus()`
(`src/josc/corpus.py`) membaca `list_searches()` lalu `get_search()` dari
`SearchArchive`, menggabungkan `results`, dan membuang duplikat memakai
DOI atau judul ternormalisasi. `build_index()`/`search_index()`
(`src/josc/fulltext.py`) membangun inverted index di memori per request dan
mewajibkan **semua** token kueri cocok. Tidak ada FTS5, tabel baru, atau
reindex queue — konsekuensinya korpus dibangun ulang setiap panggilan, yang
masih murah untuk hitungan ratusan sampai beberapa ribu record.

Prompt template (`src/josc/prompts.py:62-91`): `literature_review`,
`author_overview`, `citation_trace`.

## Metadata enrichment (Tier 0 — tanpa request tambahan)

`Paper` (`src/josc/models.py`) membawa field kualitas yang di-parse dari payload
yang sudah dikirim provider, jadi tidak ada panggilan jaringan ekstra:

| Field | Sumber | Arti |
|---|---|---|
| `is_retracted` | OpenAlex `is_retracted`, Crossref `update-to[type=retraction]` | Penanda retraksi |
| `cited_by_percentile` | OpenAlex `cited_by_percentile_year.min` | Persentil sitasi dalam bidang+tahun |
| `citations_by_year` | OpenAlex `counts_by_year` | Tren sitasi per tahun |
| `topics` | OpenAlex `primary_topic`, Crossref `subject`, PubMed `MeshHeadingList` | Klasifikasi bidang |
| `keywords` | PubMed `KeywordList` | Kata kunci penulis |
| `publication_types` | PubMed `PublicationTypeList` | Tipe publikasi |
| `institutions` | OpenAlex `authorships[].institutions` | Afiliasi penulis |
| `funders` | Crossref `funder` | Pendanaan |
| `license` | Crossref `license[].URL` | Lisensi |
| `language` | OpenAlex `language` | Bahasa |
| `tldr` | Semantic Scholar `tldr.text` | Ringkasan satu kalimat (terpisah dari abstrak) |
| `is_open_access` | Scopus `openaccess` / `openaccessFlag`, OpenAlex `open_access.is_oa` | Status OA |

`merge_two` (`src/josc/merge.py`) menggabungkan field ini: flag retraksi
menang jika salah satu sumber menyatakan `True`, topik/kata kunci/funder
di-union, dan `citations_by_year` mengambil nilai maksimum per tahun.

UI menampilkannya di `PaperTable` (badge `retracted`/`open access`/topik, serta
`top X%` di kolom sitasi) dan `PaperDrawer` (banner retraksi, TL;DR, topics,
keywords, institutions, funders, license, language, dan grafik tren sitasi).

## Degradasi Scopus `view=REF`

Scopus `references()` memakai `abstract?view=REF`, yang hanya tersedia untuk key
dengan entitlement subscriber. `citations()` tidak terpengaruh karena memakai
endpoint *search* (`REF(sid)`). Bila key menjawab 401 `AUTHORIZATION_ERROR`,
`references()` (`src/josc/providers/scopus.py`) mengubahnya menjadi pesan
actionable dan menyetel `_ref_entitlement_denied`, sehingga panggilan
berikutnya gagal lokal tanpa membakar kuota. Graf tetap terbangun; hanya edge
referensi Scopus yang dilewati dan alasannya tercatat di `errors.scopus`.

## HTTP API

Route di `src/josc/api.py:544-559`:

| Route | Handler |
|---|---|
| `GET /api/health` | `health` (`api.py:204`) |
| `GET /api/search` | `search` (`api.py:226`) |
| `GET /api/search-author` | `search_author` (`api.py:271`) |
| `GET /api/paper` | `paper` (`api.py:301`) |
| `GET /api/citations` | `citations` (`api.py:309`) |
| `GET /api/references` | `references` (`api.py:319`) |
| `GET /api/related` | `related` (`api.py:329`) |
| `GET /api/network` | `network` (`api.py:339`) |
| `GET /api/metrics` | `metrics` (`api.py:403`) |
| `GET /api/metrics/export` | `metrics_export` (`api.py:411`) |
| `GET /api/searches` | `searches` (`api.py:191`) |
| `POST /api/searches/import` | `search_import` (`api.py:508`) |
| `GET /api/searches/{search_id}/export` | `search_export` (`api.py:482`) |
| `DELETE /api/searches/{search_id}` | `search_delete` (`api/cache_routes.py`) — hapus satu baris riwayat; `404` bila id tidak ada |
| `POST /api/merge` | `merge` (`api.py:460`) |
| `GET /api/export/graphml` | `graphml_export` (`api.py:419`) |
| `POST /api/export` | `export` (`api.py:423`) |

Semua endpoint baca memakai cache lewat `_cached` (`api.py:77`). Empat di
antaranya — `search`, `search-author`, `network`, `metrics` — menerima
`?offline=true`: payload disajikan dari cache Turso dengan `stale: true`, dan
bila tidak ada entri hasilnya `503` `{"offline": true, "error": ...}`.

`GET /api/search` juga menerima empat filter field — `affiliation`, `issn`,
`orcid`, `doi` — dan setiap hasil non-offline dicatat ke tabel `searches`
lewat `_remember()` (`api/history.py`). Riwayat ini **upsert berbasis
fingerprint**: `search_fingerprint()` (`api/history.py`) menghitung SHA-256
atas seluruh parameter yang mempengaruhi hasil (query, sumber terurut, limit,
rentang tahun, `tech_only`, offset, keempat filter field, sort, order), lalu
`record_search()` (`store.py`) memperbarui baris lama bila fingerprint itu
sudah ada dan hanya `INSERT` bila belum. Konsekuensinya, mengulang pencarian
yang identik memperbarui `created_at` + `results` alih-alih menambah baris
duplikat. Penulisan eksplisit (split, duplicate, import) tidak mengirim
fingerprint sehingga tetap append. `GET /api/searches?limit=N` membaca
kembali riwayat itu; responsnya `{"searches": [...], "persistent": true}`,
atau `{"searches": [], "persistent": false}` bila Turso tidak aktif.

Tiga route menambahkan kemampuan ala PoP8 (Fase 7–8, 2026-10-25):

| Route | Perilaku |
|---|---|
| `GET /api/metrics/export` | CSV dua bagian: `Metric,Value` lalu tabel `Year,Papers,Citations,Cumulative citations`. Formatter `format_metrics_csv` (`exporters.py:482`). |
| `POST /api/merge` | Body `{"papers": [...]}`; dedup lewat `merge_papers` (`merge.py`), balas `{results, input_count, merged_count}`. Kunci asing diabaikan (`_papers_from_body`, `api.py:446`). |
| `GET /api/searches/{id}/export` | Arsip JSON `{format:"josc-search-archive", version:1, query, author, sources, filters, created_at, results}`; `404` bila id tidak ada. |
| `POST /api/searches/import` | Menerima arsip yang sama, menyimpannya sebagai baris riwayat baru, balas `{id, result_count}`. |

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
      "references": false, "related": false,
      "author_search": false, "tech_only": false
    }
  }
}
```

`cache` bernilai `null` bila caching dimatikan. Blok ini dibangun oleh
`_cache_stats()` (`api.py:139`) dari satu `fetcher` bersama yang dipakai
semua provider — tidak ada instance cache kedua dan tidak ada global state.
`store` bernilai `null` bila Turso tidak dikonfigurasi; dibangun oleh
`_store_stats()` (`api.py:151`) dari `TursoCache.stats()` (`store.py:191`).

## Web UI

Empat route (`web/src/router.tsx:65-115`):

| Path | File | Isi |
|---|---|---|
| `/` | `web/src/routes/search.tsx` | form pencarian + daftar hasil + seleksi baris |
| `/graph` | `web/src/routes/graph.tsx` | visualisasi force-directed |
| `/metrics` | `web/src/routes/metrics.tsx` | kartu metrik + tabel sitasi per tahun + unduh CSV |
| `/history` | `web/src/routes/history.tsx` | riwayat pencarian + Reload / Export / Import / Merge / Delete |

`/` dan `/history` memakai `validateSearch`, jadi state form pencarian hidup di
URL dan bisa dibagikan sebagai tautan. Route `/history` membedakan tiga
keadaan kosong: `persistent: false` (Turso tidak aktif), riwayat kosong, dan
gagal memuat.

Seleksi hasil (`search.tsx`): `selectedIds` menyimpan key `${doi ?? title}-${index}`.
Kontrol `select all`, `select cited` (hanya `citation_count > 0`), dan `clear`
ada di baris chip hasil. `ExportMenu` menerima `selectedCount`/`totalCount`,
jadi ekspor memakai baris terpilih bila ada, atau seluruh hasil bila tidak ada
yang dipilih. Checkbox hidup di kolom pertama `PaperTable` dan memanggil
`onToggle(key)` tanpa membuka drawer (baris memakai `stopPropagation`).

Fase 8 di `/history`: setiap baris punya checkbox dan tombol `Export` (unduh
arsip JSON). Toolbar punya `Import archive` (input file tersembunyi) dan
`Merge selected`, yang mengambil arsip tiap baris, menggabungkan `results`,
memanggil `POST /api/merge`, lalu mengunduh `merged-search.json`. Bila arsip
lama tidak menyimpan `results`, UI menolak merge dengan pesan yang jelas.

Dua tombol riwayat punya semantik berbeda dan penting untuk tidak tertukar:

| Tombol | Perilaku |
|---|---|
| `Reload` | Menavigasi ke `/` dengan `q`/`sources`/filter, lalu halaman `/` memanggil `/api/search`. Hasilnya dicatat lagi ke history, tetapi upsert fingerprint membuat baris lama yang diperbarui, bukan duplikat baru. |
| `Load cached results` | Menavigasi ke `/?cached=<search_id>`; halaman `/` memanggil `/api/searches/{id}/replay` dan mengisi tabel langsung. Tidak menyentuh `/api/search` dan tidak menulis history sama sekali. |
| `Retry from cache` | Memuat arsip ke panel hasil di halaman `/history` sendiri, tanpa pindah halaman. |
| `Delete` | Meminta konfirmasi, lalu `DELETE /api/searches/{id}`. Baris hilang dari daftar dan dari seleksi; panel replay ikut ditutup bila sedang menampilkan baris itu. Tidak bisa dibatalkan. |

Parameter `cached` dideklarasikan di `validateSearch` route `/`
(`web/src/router.tsx`). `loadCached()` di `search.tsx` memetakan payload
`ReplayResponse` (`query`, `sources`, `results`) ke bentuk `SearchResponse`,
sehingga tabel, drawer, dan ekspor bekerja sama seperti hasil pencarian biasa.

Komponen: `ForceGraph.tsx` (d3-force), `PaperTable.tsx` (tabel hasil yang bisa
di-sort), `PaperDrawer.tsx` (drawer detail + panel Related/Citing works),
`ExportMenu.tsx` (unduh/salin dalam 11 format), `AppShell.tsx` (sidebar).

## Metrik yang dihitung

`compute_metrics` (`src/josc/graph.py:236`) punya dua mode:

- `mode="basic"` — `papers`, `total_citations`, `h_index`, `i10_index`,
  `g_index`, `max_citations`, `mean_citations`, `citation_velocity`,
  `e_index`, plus rasio `cites_year`, `cites_paper`, `cites_author`,
  `papers_author`, `authors_paper`.
- `mode="extended"` — superset, menambah `hc_index`, `hI_index`, `hI_norm`,
  `AWCR`, `AW_index`, `AWCRpA`, `hm_index`.

`mode` diteruskan utuh ke jalur publik: `aggregator.compute_metrics(mode=...)`
(`aggregator.py:356`) → `GET /api/metrics?mode=extended` (`api.py:403`) dan
tool MCP `compute_metrics` (`server.py:192`). Nilai selain `basic`/`extended`
ditolak dengan `ValueError`.

Implementasi indeks: `h_index` (`graph.py:56`), `i10_index` (`graph.py:68`),
`g_index` (`graph.py:73`), `citation_velocity` (`graph.py:85`), `e_index`
(`graph.py:103`), `awcr` (`graph.py:119`), `aw_index` (`graph.py:131`),
`hc_index` (`graph.py:140`), `hI_index` (`graph.py:156`), `hI_norm`
(`graph.py:170`), `hm_index` (`graph.py:183`).

Tabel sitasi per tahun ditambahkan sebagai `citations_by_year()`
(`graph.py:204`) dan disisipkan ke payload sebagai `by_year`
(`graph.py:275`). Setiap baris berisi `year`, `papers`, `citations`, dan
`cumulative_citations`; paper tanpa `year` dilewati. Ini meniru tabel
"citations per year" PoP8 dan dipakai baik oleh UI `/metrics` maupun CSV.

Catatan penting untuk konsumen CSV: `compute_metrics` mengeluarkan key
`AWCR`, `AW_index`, dan `AWCRpA` **dengan huruf besar**. Formatter
`format_metrics_csv` harus memakai ejaan yang sama; sebelumnya formatter
memakai `awcr`/`aw_index` sehingga baris itu hilang diam-diam. Regresi ini
dikunci oleh `tests/test_exporters.py::test_metrics_csv_round_trips_a_real_extended_metrics_payload`.

Tiga metrik individual-h berbeda dan tidak boleh saling dipertukarkan:
`hI_index` = `h / rata-rata penulis di h-core` (Batista), `hI_norm` =
h-index dari `citations / jumlah_penulis` per paper, `hm_index` = rank
efektif `Σ 1/a` (Schreiber).

## Citation network

`build_network` (`src/josc/graph.py:428`) menghasilkan tiga tipe edge:
`cites`, `coupled`, `cocited`. Identitas node diselesaikan lebih dulu lewat
`_canonical_ids` (`graph.py:359`) dengan union-find atas DOI, provider ID, dan
judul ternormalisasi. `to_graphml` (`graph.py:550`) mengubahnya jadi GraphML.

## Ekspor

`src/josc/exporters.py` mendaftarkan 11 format: `apa`, `bibtex`, `chicago`,
`csv`, `csv_header`, `endnote`, `harvard`, `isi`, `json`, `ris`, `vancouver`.
`format_papers` (`exporters.py:438`) dipanggil dari dua tempat:

- tool MCP `export_results` (`server.py:208`, dispatch di `build_json`
  (`server.py:247`)),
- route `POST /api/export` (`api.py:423`).

Formatter kedua, `format_metrics_csv` (`exporters.py:482`), mengubah payload
metrik menjadi CSV dua bagian: daftar skalar berurutan sesuai `_METRIC_LABELS`
(`exporters.py:457`), lalu tabel per tahun bila `by_year` ada. Daftar label
memakai urutan tetap (papers, total_citations, h_index, …, authors_paper)
supaya kolom CSV stabil antar rilis.

## Persistensi

- `TTLCache` (`src/josc/cache.py:15`) — in-memory, TTL 300 s, maks 1024 entri.
- `TursoStore` (`src/josc/store.py:53`) — cache respons HTTP persisten lewat
  Turso `/v2/pipeline`. Opsional; gagal → fallback ke in-memory.
- Tabel `searches` (`store.py:138-149`) — riwayat pencarian datar:
  `id, query, author, sources, filters, result_count, created_at, results` +
  indeks `idx_searches_created` pada `created_at DESC`. Kolom `results`
  menyimpan payload hasil pencarian sebagai JSON, ditambahkan lewat
  `ALTER TABLE ... ADD COLUMN results TEXT` (`store.py:154`) yang aman untuk
  deployment lama karena error duplikat ditelan.
  Ditulis `record_search()` (`store.py:218`, bound parameter) dan dibaca
  `list_searches()` (`store.py:264`), diekspos sebagai `GET /api/searches`
  (`api.py:191`). `get_search()` (`store.py:287`) mengembalikan satu baris
  lengkap dengan `results` untuk arsip; `import_search()` (`store.py:311`)
  menyisipkan arsip sebagai baris baru dengan id segar.
  `id` dari `uuid4().hex`; `sources`/`filters`/`results` disimpan sebagai JSON.
  Kegagalan tulis ditelan — riwayat bukan jalur kritis.

## Dedup dan prioritas sumber

`src/josc/merge.py:9-18` menetapkan urutan otoritas:
`scopus > crossref > openalex > semanticscholar > dblp > arxiv >
opencitations > unpaywall`.

`_match_keys` (`merge.py:33`) mencocokkan berurutan: DOI → `(title, year)` →
`(title, first author)`.
