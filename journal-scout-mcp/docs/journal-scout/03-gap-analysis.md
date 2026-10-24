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
| Field | Author, Affiliation, Journal, ISSN, Title, Keywords, Year, ORCID, DOI | `query` + year + tech_only + offset | + `author`, `venue` |
| Operator | per-sumber, dengan peringatan | tidak ditangani | tidak ditangani (tetap gap) |
| Sinyal keterbatasan | ada | tidak ada | `filters_applied` / `filters_ignored` |

`search_all` (`aggregator.py:102-129`) dan `search_author`
(`aggregator.py:132-157`) meneruskan `author`/`venue` hanya ke provider yang
mendeklarasikannya di `supports_filters` (`providers/base.py:20-21`).
`_route_filters` (`aggregator.py:72-90`) menghasilkan laporan filter yang
diterapkan dan diabaikan.

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

## E. Persistensi query (P2)

PoP8 punya workspace: folder Recent/My/Older/Saved/Trash, duplicate, merge,
split citations. journal-scout sepenuhnya stateless — setiap tool call
berdiri sendiri.

**Perbaikan:** tabel `searches` di `TursoStore` (`src/josc/store.py:52`)
berisi `id, query, sources, filters, created_at, result_json`. Cukup untuk
"recent searches" tanpa meniru folder berlapis.

---

## F. Aksi artikel (P2) — sebagian selesai 2026-10-24

| Aksi PoP8 | Status di journal-scout |
|---|---|
| Open Article / Full Text | ada link `url`/`pdf_url` di `PaperCard.tsx` |
| Find Article with Unpaywall | **✅ tombol "Find open-access copy"** di `PaperCard.tsx:89-104` |
| Open Citing / Related Works | `get_citations` ada, "related" belum |
| Retrieve Citing Works ke search baru | `get_citations` mengembalikan daftar, belum tersimpan |

Tombol OA muncul hanya bila paper punya identifier (`doi` atau salah satu
`ids`) dan belum punya `pdf_url`. Tiga keadaan hasil: ditemukan (state paper
diperbarui, tombol hilang), tidak ditemukan (`No open-access copy found`), dan
gagal (`Lookup failed`). `try/finally` memastikan state loading tidak pernah
macet.

---

## G. Infrastruktur (P2) — sebagian selesai 2026-10-24

Lihat tabel lengkap di `../pop8/06-infrastructure.md`. Tiga yang layak:

1. **Metrik cache** — **✅ selesai.** `TTLCache.stats()` (`cache.py:80-92`)
   mengembalikan `ttl, entries, max_entries, hits, misses, sets, evictions,
   expired, hit_rate`. `_cache_stats()` (`api.py:110-119`) membacanya dari
   satu `fetcher` bersama yang dipakai semua provider, lalu `health()`
   menyisipkannya sebagai blok `cache` (`api.py:127`). Bernilai `null` bila
   caching dimatikan.
2. **Mode offline eksplisit** — flag `offline=true` yang mengembalikan
   `stale: true` alih-alih `ProviderError`. Belum dikerjakan.
3. **Diagnostik kuota seragam** — `get_quota_status` hanya Scopus; Semantic
   Scholar dan OpenAlex juga punya limit. Belum dikerjakan.

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
| **P2** | Persistensi query (`searches` + `/api/searches`) | Mendukung alur kerja berulang | terbuka |
| **P2** | Mode offline (`offline=true` → `stale: true`) | Ketahanan saat provider down | terbuka |
| **P2** | Filter `affiliation`, `issn`, `orcid`, `doi` | Paritas field filter PoP8 | terbuka |
| **P2** | Telemetri `TursoCache` (server-side) | Hanya `TTLCache` in-process yang terukur | terbuka |
| ~~P1~~ | `mode=extended` belum tersambung ke jawaban publik | Grup "Extended" di UI selalu kosong | ✅ 2026-10-24 |
| ~~P2~~ | UI: filter & paginasi di form pencarian | Backend mendukung, form hanya `query`+`limit` | ✅ 2026-10-24 |
| **P2** | UI: ekspor 11 format | Hanya GraphML yang punya tombol | terbuka |
