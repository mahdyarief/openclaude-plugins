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

Catatan: `tech_only` belum punya capability flag, jadi Crossref dan DBLP
masih diam-diam mengabaikannya. Lihat `02-provider-matrix.md`.

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

## F. Aksi artikel (P2)

| Aksi PoP8 | Status di journal-scout |
|---|---|
| Open Article / Full Text | ada link `url`/`pdf_url` di `PaperCard.tsx` |
| Find Article with Unpaywall | enricher sudah ada (`providers/unpaywall.py`), belum ada aksi eksplisit |
| Open Citing / Related Works | `get_citations` ada, "related" belum |
| Retrieve Citing Works ke search baru | `get_citations` mengembalikan daftar, belum tersimpan |

**Perbaikan:** tombol "Find OA copy" di `PaperCard.tsx` yang memanggil
`get_paper` dengan enrich Unpaywall. Murah karena endpoint-nya sudah ada.

---

## G. Infrastruktur (P2)

Lihat tabel lengkap di `../pop8/06-infrastructure.md`. Tiga yang layak:

1. **Metrik cache** (hit/miss/umur) diekspos di `GET /api/health`
   (`src/josc/api.py:109`). Saat ini cache tidak bisa diinspeksi.
2. **Mode offline eksplisit** — flag `offline=true` yang mengembalikan
   `stale: true` alih-alih `ProviderError`.
3. **Diagnostik kuota seragam** — `get_quota_status` hanya Scopus; Semantic
   Scholar dan OpenAlex juga punya limit.

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
| **P1** | Capability flag untuk `tech_only` | Crossref/DBLP masih mengabaikannya diam-diam | terbuka |
| **P2** | Persistensi query | Mendukung alur kerja berulang | terbuka |
| **P2** | Aksi Unpaywall di UI | Akses teks penuh | terbuka |
| **P2** | Metrik cache + mode offline | Observability dan ketahanan | terbuka |
| **P2** | Filter `affiliation`, `issn`, `orcid`, `doi` | Paritas field filter PoP8 | terbuka |
