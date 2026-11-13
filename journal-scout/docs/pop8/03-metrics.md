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

**Status 2026-10-25: sudah ditutup.** `compute_metrics` (`graph.py:236`)
sekarang punya `mode="basic"` dan `mode="extended"`. Semua indeks di tabel
atas diimplementasikan sebagai fungsi terpisah:

| Metrik | Implementasi |
|---|---|
| `e_index` | `graph.py:103` |
| `AWCR` | `graph.py:119` (`awcr`) |
| `hc_index` | `graph.py:140` |
| `hI_index` | `graph.py:156` |
| `hI_norm` | `graph.py:170` |
| `hm_index` | `graph.py:183` |
| Tabel sitasi per tahun | `citations_by_year` (`graph.py:204`) |

Mode bisa diminta dari luar: `GET /api/metrics?mode=extended`
(`api.py:403`) dan tool MCP `compute_metrics` (`server.py:300-308`, dengan
`mode=arguments.get("mode", "basic")`). UI metrik memakai keduanya
(`web/src/routes/metrics.tsx`).

Satu metrik yang tetap **tidak** ada di PoP8: `i10_index` — itu metrik Google
Scholar, jadi journal-scout unggul di sini.
