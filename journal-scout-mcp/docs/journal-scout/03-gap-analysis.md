# 03 — Gap Analysis terhadap PoP8

Perbandingan fitur PoP8 (lihat `../pop8/`) dengan kondisi journal-scout
(lihat `01-current-state.md`). Setiap gap dipetakan ke lokasi kode yang perlu
diubah, supaya bisa langsung dijadikan tiket kerja.

Legenda prioritas: **P0** = menghalangi kegunaan fitur yang sudah ada,
**P1** = menutup gap kompetitif penting, **P2** = nice to have.

---

## A. Ekspor — ✅ selesai 2026-10-24

| | PoP8 | journal-scout (sebelum) | journal-scout (kini) |
|---|---|---|---|
| Format | 9 data + 6 gaya sitasi + report + arsip | 4 (`bibtex, ris, csv, json`) | **11** |
| Akses | Save / Copy / Details di UI | tidak ada | tool MCP + route HTTP |

`format_papers` (`exporters.py:438`) kini dipanggil dari tool MCP
`export_results` (`server.py:187-206`) dan `POST /api/export`
(`api.py:279-298`). Formatter baru: `endnote`, `isi`, `csv_header`, `apa`,
`chicago`, `harvard`, `vancouver`. Terverifikasi: smoke test `apa`
mengembalikan string sitasi non-kosong; `tests/test_exporters.py` lulus.

---

## B. Metrik — ✅ selesai 2026-10-24

| | PoP8 | journal-scout (sebelum) | journal-scout (kini) |
|---|---|---|---|
| Jumlah metrik | 18+ | 8 | **18 di `extended`** |
| Mode report | basic / extended | satu bentuk | `basic` / `extended` |

`compute_metrics` (`graph.py:204-264`) kini punya `mode="basic"` (default,
kompatibel) dan `mode="extended"`. Tambahan: `e_index`, `AWCR`, `AW_index`,
`AWCRpA`, `hc_index`, `hI_index`, `hI_norm`, `hm_index`, serta rasio
`cites_year`, `cites_paper`, `cites_author`, `papers_author`,
`authors_paper`.

Tiga metrik individual-h diimplementasikan terpisah sesuai definisi aslinya:
`hI_index` (Batista: `h / rata-rata penulis h-core`), `hI_norm` (h-index dari
`citations / jumlah_penulis`), `hm_index` (Schreiber: rank efektif `Σ 1/a`).

`mode` kini bisa diminta dari luar: `GET /api/metrics?mode=extended`
(`api.py:270`), tool MCP `compute_metrics` (`server.py:184`), dan toggle
Basic/Extended di `/metrics` (`web/src/routes/metrics.tsx`). Sebelumnya
`aggregator.compute_metrics` memanggil engine tanpa `mode`, sehingga jalur
publik selalu mengembalikan 14 metrik basic dan grup "Extended" di UI kosong
permanen. Diverifikasi lewat HTTP: `basic` 16 key dan `extended` 23 key
(selisih 7 metrik extended, ditambah `counts`/`errors` dari envelope API).

---

## C. Filter pencarian — ✅ selesai 2026-10-24

| | PoP8 | journal-scout (sebelum) | journal-scout (kini) |
|---|---|---|---|
| Field | Author, Affiliation, Journal, ISSN, Title, Keywords, Year, ORCID, DOI | `query` + year + tech_only + offset | + `author`, `venue`, `affiliation`, `issn`, `orcid`, `doi` |
| Operator | per-sumber, dengan peringatan | tidak ditangani | tidak ditangani (tetap gap) |
| Sinyal keterbatasan | ada | tidak ada | `filters_applied` / `filters_ignored` |

`search_all` (`aggregator.py:114-146`) meneruskan filter hanya ke provider yang
mendeklarasikannya di `supports_filters` (`providers/base.py:20-21`).
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

## E. Persistensi query — ✅ selesai 2026-10-24 (riwayat datar)

PoP8 punya workspace: folder Recent/My/Older/Saved/Trash, duplicate, merge,
split citations. journal-scout sebelumnya sepenuhnya stateless — setiap tool
call berdiri sendiri.

**Perbaikan:** tabel `searches` di `TursoStore` (`store.py:130-149`) berisi
`id, query, author, sources, filters, result_count, created_at`, plus indeks
`idx_searches_created` pada `created_at DESC`. Dua method:

- `record_search()` (`store.py:211`) — `INSERT` dengan **bound parameter**;
  `sources`/`filters` diserialisasi `json.dumps`, `id` dari `uuid4().hex`.
  Kegagalan ditelan (`try/except`) karena riwayat bukan jalur kritis.
- `list_searches(limit=20)` (`store.py:252`) — `ORDER BY created_at DESC
  LIMIT ?`, kolom JSON didekode toleran; `[]` bila query gagal.

`GET /api/searches?limit=N` (`api.py:188-198`) mengembalikan
`{"searches": [...], "persistent": true}`, atau `{"searches": [],
"persistent": false}` bila Turso tidak dikonfigurasi. `search()` mencatat
setiap hasil non-offline lewat `_remember()` (`api.py:164-185`), yang juga
menyaring filter kosong sebelum disimpan. Pengujian ada di
`tests/test_searches.py` (6 test, termasuk verifikasi bound parameter).

Folder berlapis dan Trash tetap tidak ditiru — daftar datar sudah menutup
kebutuhan "recent searches".

---

## F. Aksi artikel (P2) — sebagian selesai 2026-10-24

| Aksi PoP8 | Status di journal-scout |
|---|---|
| Open Article / Full Text | ada link `url`/`pdf_url` di `PaperCard.tsx` |
| Find Article with Unpaywall | **✅ tombol "Find open-access copy"** di `PaperCard.tsx:89-104` |
| Open Citing / Related Works | **✅ related works selesai 2026-10-24** (lihat di bawah) |
| Retrieve Citing Works ke search baru | `get_citations` mengembalikan daftar, belum tersimpan |

Tombol OA muncul hanya bila paper punya identifier (`doi` atau salah satu
`ids`) dan belum punya `pdf_url`. Tiga keadaan hasil: ditemukan (state paper
diperbarui, tombol hilang), tidak ditemukan (`No open-access copy found`), dan
gagal (`Lookup failed`). `try/finally` memastikan state loading tidak pernah
macet.

**Related works — ✅ selesai 2026-10-24.** Flag `supports_related`
(`providers/base.py:20`, default `False`), hanya `True` di OpenAlex
(`openalex.py:35`). Method `related()` (`openalex.py:189`) menyelesaikan
paper ke work OpenAlex, membaca daftar `related_works`, lalu menghidrasinya
dengan satu request batch `filter=openalex_id:W1|W2|W3`. Aggregator
`get_related()` (`aggregator.py:244`) merutekan per flag, sama seperti
`get_citations`/`get_references`. Terekspos sebagai tool MCP
`get_related_works` (`server.py`, UNIFIED), route `GET /api/related`
(`api.py:325`), dan blok `capabilities.related` di `/api/health`
(`api.py:213`). Test: `tests/test_related.py` (6 test — routing per flag,
limit, missing/empty field).

---

## G. Infrastruktur (P2) — sebagian selesai 2026-10-24

Lihat tabel lengkap di `../pop8/06-infrastructure.md`. Tiga yang layak:

1. **Metrik cache** — **✅ selesai.** `TTLCache.stats()` (`cache.py:80-92`)
   mengembalikan `ttl, entries, max_entries, hits, misses, sets, evictions,
   expired, hit_rate`. `_cache_stats()` (`api.py:110-119`) membacanya dari
   satu `fetcher` bersama yang dipakai semua provider, lalu `health()`
   menyisipkannya sebagai blok `cache` (`api.py:127`). Bernilai `null` bila
   caching dimatikan.
2. **Mode offline eksplisit** — **✅ selesai.** `offline=true` di keempat
   endpoint baca (`search`, `search-author`, `network`, `metrics`) menyajikan
   payload dari cache Turso dengan `stale: true` dan tidak pernah menyentuh
   jaringan. Cache kosong atau Turso tidak dikonfigurasi → `503` dengan
   `{"offline": true, "error": ...}` (`OfflineMiss`, `api.py:39`).
3. **Diagnostik kuota seragam** — `get_quota_status` hanya Scopus; Semantic
   Scholar dan OpenAlex juga punya limit. Belum dikerjakan.

**Telemetri `TursoCache`** — **✅ selesai.** `stats()` (`store.py:170`)
mengembalikan `backend, ttl, entries, expired, hits, misses, sets, hit_rate`,
dengan counter hit/miss/set sepanjang umur proses dan `entries`/`expired`
dihitung dari tabel `query_cache` di database. `health()` menyisipkannya
sebagai blok `store` (`api.py:165`), `null` bila Turso tidak aktif.

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
