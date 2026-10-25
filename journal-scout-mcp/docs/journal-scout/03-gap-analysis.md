# 03 — Gap Analysis terhadap PoP8

Perbandingan fitur PoP8 (lihat `../pop8/`) dengan kondisi journal-scout
(lihat `01-current-state.md`). Setiap gap dipetakan ke lokasi kode yang perlu
diubah, supaya bisa langsung dijadikan tiket kerja.

Legenda prioritas: **P0** = menghalangi kegunaan fitur yang sudah ada,
**P1** = menutup gap kompetitif penting, **P2** = nice to have.

---

## A. Ekspor — ✅ selesai 2026-10-24, diperluas 2026-10-25

| | PoP8 | journal-scout (sebelum) | journal-scout (kini) |
|---|---|---|---|
| Format | 9 data + 6 gaya sitasi + report + arsip | 4 (`bibtex, ris, csv, json`) | **17 formatter** |
| Akses | Save / Copy / Details di UI | tidak ada | tool MCP + route HTTP + 3 aksi UI |

`format_papers` (`exporters.py:438`) kini dipanggil dari tool MCP
`export_results` (`server.py:208`) dan `POST /api/export`
(`api.py:423`). Formatter baru 2026-10-24: `endnote`, `isi`, `csv_header`,
`apa`, `chicago`, `harvard`, `vancouver`. Tambahan 2026-10-25: `mla`,
`csiro`, `csv_bom`, `xls`, `csv_plain` (`exporters.py:274-278`), dan
`xls_plain` (`exporters.py:409-410`) — dua yang terakhir adalah varian
tanpa baris header, melengkapi pasangan "CSV"/"CSV with Header" dan
"Excel"/"Excel with Header" di PoP8. `_build_csv` (`exporters.py:244`)
menerima `header: bool = True`. Terverifikasi: smoke test `apa`
mengembalikan string sitasi non-kosong; `tests/test_exporters.py` lulus.

Aksi UI kini lengkap tiga: Download, Copy, dan **Details** (pratinjau) di
`ExportMenu.tsx:96-107` dengan panel `<pre>` di `:161-176`.

---

## B. Metrik — ✅ selesai 2026-10-24

| | PoP8 | journal-scout (sebelum) | journal-scout (kini) |
|---|---|---|---|
| Jumlah metrik | 18+ | 8 | **18 di `extended`** |
| Mode report | basic / extended | satu bentuk | `basic` / `extended` |

`compute_metrics` (`graph.py:236`) kini punya `mode="basic"` (default,
kompatibel) dan `mode="extended"`. Tambahan: `e_index`, `AWCR`, `AW_index`,
`AWCRpA`, `hc_index`, `hI_index`, `hI_norm`, `hm_index`, serta rasio
`cites_year`, `cites_paper`, `cites_author`, `papers_author`,
`authors_paper`.

Tiga metrik individual-h diimplementasikan terpisah sesuai definisi aslinya:
`hI_index` (Batista: `h / rata-rata penulis h-core`), `hI_norm` (h-index dari
`citations / jumlah_penulis`), `hm_index` (Schreiber: rank efektif `Σ 1/a`).

`mode` kini bisa diminta dari luar: `GET /api/metrics?mode=extended`
(`api.py:403`), tool MCP `compute_metrics` (`server.py:192`), dan toggle
Basic/Extended di `/metrics` (`web/src/routes/metrics.tsx`). Sebelumnya
`aggregator.compute_metrics` memanggil engine tanpa `mode`, sehingga jalur
publik selalu mengembalikan 14 metrik basic dan grup "Extended" di UI kosong
permanen. Diverifikasi lewat HTTP: `basic` 16 key dan `extended` 23 key
(selisih 7 metrik extended, ditambah `counts`/`errors` dari envelope API).

**Tabel sitasi per tahun — ✅ selesai 2026-10-25.** `citations_by_year()`
(`graph.py:204`) mengagregasi paper per tahun menjadi `year`, `papers`,
`citations`, dan `cumulative_citations`, lalu disisipkan sebagai `by_year`
(`graph.py:275`). UI `/metrics` menampilkan tabel "Citations per year";
`GET /api/metrics/export` (`api.py:411`) menyajikan CSV dua bagian lewat
`format_metrics_csv` (`exporters.py:482`).

Jebakan yang ditemukan saat review: formatter sempat memakai key `awcr` /
`aw_index` huruf kecil, padahal engine mengeluarkan `AWCR` / `AW_index` /
`AWCRpA`, sehingga tiga baris hilang diam-diam di laporan extended. Kini
selaras dan dikunci dua tes regresi, termasuk satu yang memanggil
`compute_metrics(mode="extended")` asli lalu memformatnya.

---

## C. Filter pencarian — ✅ selesai 2026-10-24

| | PoP8 | journal-scout (sebelum) | journal-scout (kini) |
|---|---|---|---|
| Field | Author, Affiliation, Journal, ISSN, Title, Keywords, Year, ORCID, DOI | `query` + year + tech_only + offset | + `author`, `venue`, `affiliation`, `issn`, `orcid`, `doi` |
| Operator | per-sumber, dengan peringatan | tidak ditangani | tidak ditangani (tetap gap) |
| Sinyal keterbatasan | ada | tidak ada | `filters_applied` / `filters_ignored` |

`search_all` (`aggregator.py:114`) meneruskan filter hanya ke provider yang
mendeklarasikannya di `supports_filters` (`providers/base.py:24`).
`_route_filters` (`aggregator.py:72-102`) menghasilkan laporan filter yang
diterapkan dan diabaikan, sedangkan `_filter_kwargs` (`aggregator.py:105-111`)
membangun kwargs per provider sehingga sumber tak-pendukung tidak pernah
menerima keyword yang tidak dikenalnya.

Pemetaan field ke query asli tiap API (diverifikasi terhadap dokumentasi
provider, bukan diasumsikan):

| Provider | affiliation | issn | orcid | doi |
|---|---|---|---|---|
| openalex | `raw_affiliation_strings.search:` | `primary_location.source.issn:` | `authorships.author.orcid:` | `doi:` (prefix `https://doi.org/` dibuang) |
| crossref | `query.affiliation` | `filter=issn:` | — (API tidak punya filter ORCID) | `filter=doi:` |
| scopus | `AFFIL(...)` | `ISSN(...)` | `ORCID(...)` | `DOI(...)` |
| pubmed | `"...""[AD]` | `[IS]` | `[AID]` | `[DOI]` |
| arxiv / dblp / semanticscholar | — | — | — | — |

Dua jebakan yang ditangani eksplisit: OpenAlex memecah `filter` pada koma,
jadi nilai `affiliation` diratakan dulu (`" ".join(value.replace(",", " ").split())`);
Crossref menyatukan semua batasan di satu parameter `filter`, sehingga batas
tahun dan filter field **digabung**, bukan saling menimpa (`_works`,
`crossref.py:64-78`). Pengujian ada di `tests/test_filters.py` (7 test).

Catatan: `tech_only` **kini punya capability flag** (`supports_tech_only`,
`providers/base.py:22`), jadi Crossref, DBLP, dan PubMed dilaporkan sebagai
`filters_ignored` alih-alih diabaikan diam-diam. Lihat `02-provider-matrix.md`.

---

## D. Sumber data — ✅ selesai 2026-10-24 (PubMed)

| Sumber | PoP8 | journal-scout | Biaya |
|---|---|---|---|
| Google Scholar | ya (scraping) | tidak | tinggi |
| Web of Science | ya (4 varian) | tidak | tinggi (akses) |
| PubMed | ya | **ya** | — |
| Lens.org | ya | tidak | sedang |
| arXiv | tidak | **ya** | — |
| DBLP | tidak | **ya** | — |
| OpenCitations | tidak | **ya** | — |

`PubMedProvider` (`providers/pubmed.py`) memakai E-utilities dua tahap
(`esearch` → `efetch`), `supports_search = True`,
`supports_author_search = True`. Registry kini 9 provider / 7 searchable.
`tests/test_providers/test_pubmed.py` lulus.

---

## E. Persistensi query — ✅ selesai 2026-10-24, diperluas 2026-10-25

PoP8 punya workspace: folder Recent/My/Older/Saved/Trash, duplicate, merge,
split citations. journal-scout sebelumnya sepenuhnya stateless — setiap tool
call berdiri sendiri.

**Perbaikan:** tabel `searches` di `TursoStore` (`store.py:138-149`) berisi
`id, query, author, sources, filters, result_count, created_at, results`, plus
indeks `idx_searches_created` pada `created_at DESC`. Empat method:

- `record_search()` (`store.py:233`) — `INSERT` dengan **bound parameter**;
  `sources`/`filters`/`results` diserialisasi `json.dumps`, `id` dari
  `uuid4().hex`. Kegagalan ditelan (`try/except`) karena riwayat bukan jalur
  kritis.
- `list_searches(limit=20)` (`store.py:279`) — `ORDER BY created_at DESC
  LIMIT ?`, kolom JSON didekode toleran; `[]` bila query gagal. Kini juga
  mengembalikan `size_bytes` (`LENGTH(results)`) dan `age_seconds`.
- `get_search(id)` (`store.py:308`) — satu baris lengkap termasuk `results`,
  dipakai route ekspor arsip.
- `import_search(...)` (`store.py:332`) — menyisipkan arsip sebagai baris baru
  dengan id segar.
- `duplicate_search(id)` (`store.py:369`) — clone baris dengan label
  `"<query> (copy)"`.
- `export_workspace(limit)` / `import_workspace(archive)` (`store.py:399` /
  `:423`) — arsip seluruh tabel `searches`.
- `replay_search(id)` (`store.py:443`) — payload "retry from cache" dengan
  `stale: true`, tanpa jaringan.
- `info(prefix, limit)` (`store.py:463`) — metadata per entri `query_cache`.

`GET /api/searches?limit=N` (`api.py:193`) mengembalikan
`{"searches": [...], "persistent": true}`, atau `{"searches": [],
"persistent": false}` bila Turso tidak dikonfigurasi. `search()` mencatat
setiap hasil non-offline lewat `_remember()` (`api.py:167`), yang juga
menyaring filter kosong sebelum disimpan. Pengujian ada di
`tests/test_searches.py` (11 test, termasuk verifikasi bound parameter).

**Arsip pencarian — ✅ selesai 2026-10-25.** `GET /api/searches/{id}/export`
(`api.py:496`) mengemas satu baris menjadi arsip portabel
`{format: "josc-search-archive", version: 1, ...}` dengan `results` di
dalamnya. `POST /api/searches/import` (`api.py:522`) menerima arsip yang sama
dan menyimpannya sebagai baris riwayat baru. UI `/history` menambahkan tombol
`Export` per baris, `Import archive`, dan `Merge selected` yang memanggil
`POST /api/merge` (`api.py:474`).

**Arsip seluruh workspace — ✅ selesai 2026-10-25.** `GET
/api/searches/export` (`api.py:661`) dan `POST
/api/searches/import-workspace` (`api.py:681`) memakai
`export_workspace`/`import_workspace` (`store.py:399`/`:423`). Tombol
"Export workspace" / "Import workspace" ada di `history.tsx:373`/`:381`.

**Duplicate — ✅ selesai 2026-10-25.** `POST
/api/searches/{id}/duplicate` (`api.py:702`) memakai `duplicate_search`
(`store.py:369`); tombol "Duplicate" per baris di `history.tsx:536`.

**Retry from cache — ✅ selesai 2026-10-25.** `GET
/api/searches/{id}/replay` (`api.py:716`) memakai `replay_search`
(`store.py:443`); tombol "Retry from cache" di `history.tsx:544`.

Migrasi kolom `results` memakai `ALTER TABLE searches ADD COLUMN results TEXT`
(`store.py:154`) dan menelan error duplikat, jadi deployment lama tetap aman.
Baris lama yang belum punya `results` tidak bisa di-merge — UI menolaknya
dengan pesan eksplisit alih-alih menghasilkan file kosong.

Folder berlapis dan Trash tetap tidak ditiru — daftar datar sudah menutup
kebutuhan "recent searches".

---

## F. Aksi artikel (P2) — ✅ selesai 2026-10-25

| Aksi PoP8 | Status di journal-scout |
|---|---|
| Open Article / Full Text | ada link `url`/`pdf_url` di `PaperDrawer.tsx` (footer) |
| Find Article with Unpaywall | **✅ tombol "Fetch details"** di `PaperDrawer.tsx` — satu `/api/paper` mengisi abstrak + `pdf_url` |
| Open Citing / Related Works | **✅ tombol "Related works" + "Citing works"** di `PaperDrawer.tsx`, panel inline 10 hasil |
| Retrieve Citing Works ke search baru | **✅** `GET /api/citations?save=true` (`api.py:315`) → `_remember("citations:<id>")` |

Tombol "Fetch details" muncul hanya bila paper punya identifier (`doi` atau
salah satu `ids`) dan belum punya abstrak. Satu request `/api/paper` mengisi
`resolved`, sehingga abstrak, DOI, dan `pdf_url` yang baru ditemukan langsung
tampil; footer otomatis berganti menjadi "Download PDF". Kalau sumber tidak
punya abstrak, pesannya `No abstract available from the source.`

**Related works — ✅ selesai 2026-10-24.** Flag `supports_related`
(`providers/base.py:20`, default `False`), hanya `True` di OpenAlex
(`openalex.py:35`). Method `related()` (`openalex.py:189`) menyelesaikan
paper ke work OpenAlex, membaca daftar `related_works`, lalu menghidrasinya
dengan satu request batch `filter=openalex_id:W1|W2|W3`. Aggregator
`get_related()` (`aggregator.py:244`) merutekan per flag, sama seperti
`get_citations`/`get_references`. Terekspos sebagai tool MCP
`get_related_works` (`server.py`, UNIFIED), route `GET /api/related`
(`api.py:329`), dan blok `capabilities.related` di `/api/health`
(`api.py:216`). Test: `tests/test_related.py` (6 test — routing per flag,
limit, missing/empty field).

---

## G. Infrastruktur (P2) — ✅ selesai 2026-10-25

Lihat tabel lengkap di `../pop8/06-infrastructure.md`. Tiga yang layak:

1. **Metrik cache** — **✅ selesai.** `TTLCache.stats()` (`cache.py:80-92`)
   mengembalikan `ttl, entries, max_entries, hits, misses, sets, evictions,
   expired, hit_rate`. `_cache_stats()` (`api.py:139`) membacanya dari
   satu `fetcher` bersama yang dipakai semua provider, lalu `health()`
   menyisipkannya sebagai blok `cache` (`api.py:209`). Bernilai `null` bila
   caching dimatikan.
2. **Mode offline eksplisit** — **✅ selesai.** `offline=true` di keempat
   endpoint baca (`search`, `search-author`, `network`, `metrics`) menyajikan
   payload dari cache Turso dengan `stale: true` dan tidak pernah menyentuh
   jaringan. Cache kosong atau Turso tidak dikonfigurasi → `503` dengan
   `{"offline": true, "error": ...}` (`OfflineMiss`, `api.py:40`).
3. **Diagnostik kuota seragam** — **✅ selesai 2026-10-25.**
   `quota_report` (`quota.py:62`) melaporkan sembilan sumber dengan bentuk
   respons yang sama; `GET /api/quota` (`api.py:557`) dan tool MCP
   `get_quota_status` (`server.py:346`) memakainya.
4. **Clear cache per query** — **✅ selesai 2026-10-25.**
   `TTLCache.clear(prefix)` (`cache.py:72`) + `TursoCache.clear(prefix)`
   (`store.py:218`), diekspos lewat `POST /api/cache/clear`
   (`api.py:582`).
5. **Cache info per query** — **✅ selesai 2026-10-25.**
   `TTLCache.info(prefix, limit)` (`cache.py:102`) dan
   `TursoCache.info(prefix, limit)` (`store.py:463`), diekspos lewat
   `GET /api/cache/info` (`api.py:639`).
6. **Retry operation from cache** — **✅ selesai 2026-10-25.**
   `TursoCache.replay_search(id)` (`store.py:443`), route
   `GET /api/searches/{id}/replay` (`api.py:716`), tombol "Retry from cache"
   di `history.tsx:544`.

**Split saved search** — **✅ selesai 2026-10-25.**
`TursoCache.split_search` (`store.py:493`) dan
`POST /api/searches/{id}/split` (`api.py:604`).

**Telemetri `TursoCache`** — **✅ selesai.** `stats()` (`store.py:191`)
mengembalikan `backend, ttl, entries, expired, hits, misses, sets, hit_rate`,
dengan counter hit/miss/set sepanjang umur proses dan `entries`/`expired`
dihitung dari tabel `query_cache` di database. `health()` menyisipkannya
sebagai blok `store` (`api.py:210`), `null` bila Turso tidak aktif.

---

## Yang sengaja TIDAK ditiru

| Fitur PoP8 | Alasan |
|---|---|
| CAPTCHA IE/WebView2 | journal-scout memakai API resmi, tidak scraping |
| Crash recovery | server stateless, tidak ada state lokal untuk dipulihkan |
| Trash & folder berlapis | MCP server lebih cocok daftar datar + tag |
| Microsoft Academic | sudah mati sejak 31 Des 2021 |

---

## Ringkasan prioritas

| Prioritas | Item | Dampak | Status |
|---|---|---|---|
| ~~P0~~ | Wire-up `format_papers` ke tool/route | Membuka fitur yang sudah ada tapi tidak terpakai | ✅ 2026-10-24 |
| ~~P1~~ | Metrik tambahan (e-index, AWCR, hm-index, dll.) | Paritas laporan bibliometrik | ✅ 2026-10-24 |
| ~~P1~~ | Filter terstruktur + capability flag | Hasil antar sumber jadi sebanding | ✅ 2026-10-24 |
| ~~P1~~ | Provider PubMed | Menutup gap biomedis dengan biaya rendah | ✅ 2026-10-24 |
| ~~P1~~ | Capability flag untuk `tech_only` | Crossref/DBLP mengabaikannya diam-diam | ✅ 2026-10-24 |
| ~~P2~~ | Aksi Unpaywall di UI | Akses teks penuh | ✅ 2026-10-24 |
| ~~P2~~ | Metrik cache di `/api/health` | Observability cache | ✅ 2026-10-24 |
| ~~P2~~ | Persistensi query (`searches` + `/api/searches`) | Mendukung alur kerja berulang | ✅ 2026-10-24 |
| ~~P2~~ | Mode offline (`offline=true` → `stale: true`) | Ketahanan saat provider down | ✅ 2026-10-24 |
| ~~P2~~ | Filter `affiliation`, `issn`, `orcid`, `doi` | Paritas field filter PoP8 | ✅ 2026-10-24 |
| ~~P2~~ | Telemetri `TursoCache` (server-side) | Hanya `TTLCache` in-process yang terukur | ✅ 2026-10-24 |
| ~~P1~~ | `mode=extended` belum tersambung ke jawaban publik | Grup "Extended" di UI selalu kosong | ✅ 2026-10-24 |
| ~~P2~~ | UI: filter & paginasi di form pencarian | Backend mendukung, form hanya `query`+`limit` | ✅ 2026-10-24 |
| ~~P2~~ | UI: ekspor 11 format | Hanya GraphML yang punya tombol | ✅ 2026-10-24 |
| ~~P2~~ | Related works (`supports_related` + `GET /api/related`) | Melengkapi aksi artikel PoP8 | ✅ 2026-10-24 |
| ~~P2~~ | UI: riwayat pencarian (`/history`) | Backend `/api/searches` ada, UI belum | ✅ 2026-10-24 |
| ~~P2~~ | Tabel sitasi per tahun + CSV metrik | Paritas tabel "citations per year" PoP8 | ✅ 2026-10-25 |
| ~~P2~~ | Seleksi hasil di UI + ekspor baris terpilih | Ekspor tepat sasaran, bukan semua hasil | ✅ 2026-10-25 |
| ~~P2~~ | `POST /api/merge` | Dedup lintas pencarian | ✅ 2026-10-25 |
| ~~P2~~ | Arsip pencarian ekspor/impor | Portabilitas riwayat antar mesin | ✅ 2026-10-25 |
| ~~P1~~ | Translasi operator boolean per sumber (`query.py`) | Query tidak lagi diam-diam salah tafsir | ✅ 2026-10-25 |
| ~~P1~~ | Peringatan operator ke pengguna (`query_warnings`) | Pengguna tahu operator mana yang diabaikan | ✅ 2026-10-25 |
| ~~P1~~ | Import External Data (`.ris/.bib/.enw/.csv/.txt/.ciw`) | Data luar bisa masuk tanpa re-search | ✅ 2026-10-25 |
| ~~P1~~ | Gaya sitasi MLA + CSIRO | Paritas gaya sitasi PoP8 | ✅ 2026-10-25 |
| ~~P1~~ | CSV+BOM | Excel Windows mendeteksi UTF-8 dengan benar | ✅ 2026-10-25 |
| ~~P2~~ | Search Report basic/extended | Laporan satu halaman seperti PoP8 | ✅ 2026-10-25 |
| ~~P2~~ | Diagnostik kuota seragam (`/api/quota`) | Semua sumber, bukan hanya Scopus | ✅ 2026-10-25 |
| ~~P2~~ | Split saved search | Memecah himpunan hasil jadi beberapa search | ✅ 2026-10-25 |
| ~~P2~~ | CSV/Excel tanpa header (`csv_plain`, `xls_plain`) | Paritas varian "CSV"/"Excel" di PoP8 | ✅ 2026-10-25 |
| ~~P2~~ | Aksi Details (pratinjau) di UI ekspor | Save/Copy/Details lengkap | ✅ 2026-10-25 |
| ~~P2~~ | Duplicate saved search | Clone baris riwayat dengan id baru | ✅ 2026-10-25 |
| ~~P2~~ | Arsip seluruh workspace | Portabilitas seluruh riwayat, bukan per-search | ✅ 2026-10-25 |
| ~~P2~~ | Cache info per query + retry from cache | Metadata entri dan penyajian ulang tanpa jaringan | ✅ 2026-10-25 |
| ~~P2~~ | Citing works tersimpan sebagai search baru | `save=true` di `/api/citations` | ✅ 2026-10-25 |
| ~~P2~~ | Tombol related/citing works di UI | Aksi artikel PoP8 lengkap | ✅ 2026-10-25 |
| ~~P2~~ | Sort/order hasil di API + UI | Urutkan hasil tanpa re-search | ✅ 2026-10-25 |
| ~~P2~~ | Clear cache per query | Bebaskan entri cache tertentu | ✅ 2026-10-25 |
| ~~P2~~ | Ekspor Excel `.xls` | Paritas format data PoP8 | ✅ 2026-10-25 |
