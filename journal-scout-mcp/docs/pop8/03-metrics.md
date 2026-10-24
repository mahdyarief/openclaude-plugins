# 03 — Metrik Bibliometrik PoP8

Nama field diambil dari header CSV report dan label dialog report di
`pop8win.exe`. Nama internal memakai underscore (`h_index`), label UI memakai
spasi (`h-index`).

## Metrik inti

| Field | Arti | Rumus |
|---|---|---|
| `Papers` | jumlah karya | `len(papers)` |
| `Citations` | total sitasi | `sum(citation_count)` |
| `Years` | rentang tahun | `max(year) - min(year) + 1` |
| `Cites_Year` | sitasi per tahun | `Citations / Years` |
| `Cites_Paper` | rata-rata sitasi per karya | `Citations / Papers` |
| `Cites_Author` | rata-rata sitasi per penulis | `Citations / total_authors` |
| `Papers_Author` | produktivitas | `Papers / jumlah_penulis_unik` |
| `Authors_Paper` | kolaborasi | `total_authors / Papers` |

## Indeks

| Field | Nama | Definisi |
|---|---|---|
| `h_index` | Hirsch h-index | h karya teratas masing-masing punya ≥ h sitasi |
| `g_index` | Egghe g-index | g karya teratas totalnya ≥ g² |
| `hc_index` | h-index kontemporer | h-index dihitung hanya dari karya ≤ N tahun terakhir |
| `hI_index` | h-index individual | versi h-index yang memperhitungkan penulis |
| `hI_norm` | hI ternormalisasi | hI dibagi jumlah penulis rata-rata |
| `AWCR` | Age-Weighted Citation Rate | sitasi dibobot umur karya |
| `AW_index` | AW-index | `sqrt(AWCR)` |
| `AWCRpA` | AWCR per Author | `AWCR / jumlah_penulis` |
| `e_index` | e-index | `sqrt(total_sitasi_ekor - h²)`; mengukur ekor di atas h |
| `hm_index` | hm-index | h-index dengan pembobotan porsi penulis |

## Metrik tambahan di report

`Citation years` (daftar tahun sitasi), `Annual citations`, `Age-weighted
citation rate`, `Total citations`, `Hirsch h-index`, `Egghe g-index`.

## Dua mode report

- **Search Report (basic)** — ringkasan satu halaman: Papers, Citations,
  Years, Cites/Year, Cites/Paper, Cites/Author, h-index, g-index.
- **Search Report (extended)** — menambah hc/hI/hI_norm/AWCR/AW-index/
  AWCRpA/e-index/hm-index dan tabel sitasi per tahun.

## Implikasi untuk journal-scout

`src/josc/graph.py:102-117` baru menghitung 8 angka: `papers`,
`total_citations`, `h_index`, `i10_index`, `g_index`, `max_citations`,
`mean_citations`, `citation_velocity`. Yang belum ada:

- `hc_index`, `hI_index`, `hI_norm`, `AWCR`, `AW_index`, `AWCRpA`,
  `e_index`, `hm_index` — semuanya deterministik dari daftar
  `(citation_count, year, authors)`, tidak butuh data tambahan.
- `i10_index` justru **tidak** ada di PoP8 (itu metrik Google Scholar), jadi
  journal-scout sudah unggul di sini.
- Report dua mode (basic/extended) belum ada; `compute_metrics` selalu
  mengembalikan satu bentuk.

Prioritas: `e_index` dan `AWCR` paling murah karena hanya butuh
`citation_count` dan `year` yang sudah ada di `Paper`. `hm_index` butuh
jumlah penulis dan urutan penulis, yang juga sudah tersimpan di
`Paper.authors`.
