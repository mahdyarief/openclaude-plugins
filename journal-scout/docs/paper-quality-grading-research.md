# Riset & Rekomendasi: Pengelompokan dan Peringkat Kualitas Paper di Journal Scout

Tanggal: 2026-11-19
Status: **rekomendasi fitur** — belum disetujui, belum diimplementasikan.

## Tujuan

Agar hasil pencarian Journal Scout tidak hanya "banyak paper", tetapi **bermutu**:
setiap paper diberi kelas kualitas yang dapat dijelaskan sinyalnya, dan hasil bisa
dikelompokkan/disort berdasarkan kelas itu — tanpa jatuh ke kesalahan memakai
impact factor jurnal sebagai pengganti kualitas artikel (larangan eksplisit DORA).

## 1. Temuan Riset (dengan rujukan)

### 1.1 Jangan memakai metrik jurnal sebagai pengganti kualitas artikel

- **DORA / San Francisco Declaration on Research Assessment**
  (10.1242/dev.099234, Development, 2013 — teks penuh): rekomendasi 1 = *"Do not
  use journal-based metrics, such as journal impact factors, as a surrogate
  measure of the quality of individual research articles."* Rekomendasi 7 = sediakan
  **article-level metrics**. Rekomendasi 14 = pertimbangkan variasi tipe artikel
  (review vs primary) dan bidang.
- Bukti bahwa penyalahgunaan masih marak: **McKiernan et al.** ("Use of the
  Journal Impact Factor in academic review, promotion, and tenure evaluations",
  *eLife*, 2019, DOI 10.7554/elife.47338) — 63% institusi yang menyebut JIF
  mengaitkannya dengan "quality". Ini justru memperkuat alasan fitur ini:
  beri sinyal artikel-level, kurangi godaan memakai IF mentah.
- Analisis statistik: "Use of the journal impact factor for assessing individual
  articles: Statistically flawed or not?" (2021) — dalam banyak kondisi jumlah
  sitasi artikel (dinormalisasi) lebih akurat daripada IF; diskusi utamanya
  tetap sosial-teknis, bukan statistik semata.

### 1.2 Normalisasi bidang dan usia adalah cara yang paling robust

- **Leiden Manifesto** (Hicks, Wouters, Waltman, de Rijcke, Rafols, *Nature*
  520, 429–431, 2015, DOI 10.1038/520429a), Prinsip 6: *"Best practice is to
  select a suite of possible indicators... Citation rates vary by field...
  Normalized indicators are required, and the most robust normalization method is
  based on percentiles: each paper is weighted on the basis of the percentile to
  which it belongs in the citation distribution of its field (top 1%, 10% or
  20%)."* Prinsip 1: metrik kuantitatif harus **mendukung** penilaian
  kualitatif, bukan menggantikannya. Prinsip 8: hindari false precision.
- **FWCI vs RCR** (Purkayastha, Palmaro, Falk-Krzesinski, Baas, "Comparison of
  two article-level, field-independent citation metrics: Field-Weighted Citation
  Impact (FWCI) and Relative Citation Ratio (RCR)", DOI 10.1016/j.joi.2019.03.012):
  indikator artikel-level yang dinormalisasi bidang terbukti stabil lintas bidang.
- **Bornmann 2020** ("How can citation impact in bibliometrics be normalized? A
  new approach combining citing-side normalization and citation percentiles",
  *Quantitative Science Studies*, DOI 10.1162/qss_a_00089): percentile cocok
  untuk distribusi sitasi yang skewed; interpretasinya sederhana
  ("90% paper tahun & bidang ini punya sitasi di bawah paper ini").
- OpenAlex menyediakan `cited_by_percentile_year` (persentil sitasi dalam
  kohor tahun, lintas bidang) dan `citation_normalized_percentile` (persentil
  sitasi yang dinormalisasi menurut subfield, tipe publikasi, dan tahun).
  Field `cited_by_percentile_field` **tidak ada** di schema OpenAlex. Untuk
  artikel-level comparison lintas disiplin, `citation_normalized_percentile`
  lebih sesuai dengan prinsip normalisasi Leiden.

### 1.3 Kualitas artikel ≠ reputasi jurnal; rancangan studi adalah sumbangan utama

- **GRADE** (mis. "Core GRADE 4: rating certainty of evidence", *BMJ*, 2025,
  DOI 10.1136/bmj.r1468; "GRADE guidelines 21", DOI
  10.1016/j.jclinepi.2019.12.020): kepastian bukti diranking per desain studi
  (meta-analysis/RCT lebih tinggi dari observasional, dari kasus) dan
  ditingkatkan/diturunkan lewat risk of bias, imprecision, inconsistency,
  indirectness, publication bias. Artinya: di bidang klinis, **tipe desain
  studi** adalah sinyal kualitas artikel-level yang valid dan sudah tersedia
  sebagian di data kita (`study_type`, `publication_types`).
- Batasan metrik jurnal (dari panduan CiteScore/JIF/quartile, "Not all metrics
  are equal", 2021): JIF = 2-tahun, hanya WoS, distribusi sitasi skewed;
  CiteScore = 4-tahun berbasis Scopus; quartile (Q1–Q4) berbeda antara JCR dan
  Scimago/SCImago. Jangan membandingkan quartile lintas skema.

### 1.4 Integritas

Paper yang **diretract** harus dikeluarkan dari rekomendasi apa pun
(OpenAlex `is_retracted`, Crossref event-of-record sudah dipetakan di kode
sekarang). Preprint bukan hasil peer review — bukan "kualitas rendah",
melainkan "belum diverifikasi" — perlakukan sebagai flag, bukan nilai.

## 2. Apa yang Sudah Ada di Kode (gap analysis)

| Sinyal | Status di journal-scout |
|---|---|
| `citation_count`, `citations_by_year` | ✅ sudah di model & semua provider |
| `cited_by_percentile` (OpenAlex, **varian YEAR**) | ✅ sudah dipetakan |
| `citation_normalized_percentile` (OpenAlex, **subfield + tipe paper + tahun**) | ❌ belum di-fetch — gap utama; inilah field yang benar untuk pembanding bidang |
| `sjr_best_quartile` | ⚠️ hanya dari Consensus; Consensus saat ini kena kuota bulanan (HTTP 429), jadi quartile praktis tidak tersedia |
| CiteScore percentile per subject area (Scopus Serial Title API) | ❌ belum diambil; endpoint dan response perlu divalidasi dengan API key/deployment sebelum mengandalkan kuartile |
| `is_retracted` | ✅ OpenAlex + Crossref |
| `is_open_access`, `pdf_url` | ✅ (akses, bukan kualitas — jangan dipakai untuk grading) |
| `study_type`, `takeaway`, `study_count` | ⚠️ hanya Consensus |
| `publication_types` | ✅ PubMed + Crossref dll. |
| Sort agregator | `relevance`, `citations`, `year`, `title` — **tidak ada `quality`** |
| UI hasil | tabel paper — **tidak ada kelas kualitas, tidak ada grup per kelas** |

## 3. Rekomendasi Desain: "Quality Grade" Bertingkat Sinyal

Prinsip (kompatibel DORA + Leiden): **sinyal artikel-level dulu, jurnal-level
sebagai konteks, integritas sebagai flag, desain studi sebagai penguat di
bidang klinis.** Kelas selalu disajikan bersama breakdown sinyalnya — bukan
angka tunggal.

### 3.1 Sinyal per paper

1. **`cited_by_percentile_field`** (0–100, artikel-level, dinormalisasi
   bidang+usia) → sinyal utama.
2. **`journal_quartile`** (Q1–Q4) dari Scopus source (ISSN jurnal host) →
   sinyal konteks. Cache di disk (data jurnal berubah lambat).
3. **`is_retracted`** → flag integritas (mengalahkan semua grade).
4. **`is_preprint`** → flag status (belum peer-review).
5. **Desain studi** (dari `study_type`/`publication_types` bila ada) →
   penguat: meta-analysis/sistematis/RCT naik satu kelas di domain klinis.

### 3.2 Aturan kelas (deterministik, terdokumentasi)

| Kelas | Syarat |
|---|---|
| `high` | tidak retracted, dan (field pct ≥ 90), atau (desain meta-analysis/sistematis + jurnal Q1/Q2) |
| `medium` | tidak retracted, dan field pct 60–89, atau (pct belum ada + jurnal Q1/Q2) |
| `low` | tidak retracted, dan field pct < 60, atau jurnal Q4 |
| `flagged` | `is_retracted` — selalu ditampilkan terpisah dengan alasan retraction |
| `ungraded` | data tidak cukup (tidak ada pct, ISSN tidak ketemu, jurnal non-jurnal) |

Catatan jujur untuk ditampilkan di UI: paper ≤ 2 tahun tidak bisa mencapai
percentile tinggi (sitasi belum matang), jadi untuk paper baru kelasnya
didukung sinyal jurnal + desain, dan UI menandai "data sitasi masih muda".

### 3.3 Tampilan

- Hasil pencarian: **chip kelas per baris** + breakdown tooltip
  (pct bidang, quartile jurnal, retracted?, preprint?, desain).
- Kontrol **"Kelompokkan per kelas kualitas"** → grup high/medium/low/flagged.
- Sort baru `quality`: kelas descending, lalu `cited_by_percentile_field`.
- Halaman metrics: histogram distribusi kelas dari hasil aktif.

## 4. Rencana Implementasi (jika disetujui)

Urutan aman, per file:

1. `providers/openalex.py` — ambil `cited_by_percentile_field`
   (sekarang hanya `..._year` di L127).
2. `models.py` — tambah `cited_by_percentile_field`, `journal_quartile`,
   `quality_grade`; perbarui `to_dict`.
3. Modul baru `quality.py` — `grade_paper(paper) -> str` murni + aturan di §3.2
   + alasan (list string) untuk tooltip. Unit-testable.
4. `scopus_source.py` (baru) — lookup Scopus source per ISSN
   (`/sources/{issn-or-name}`, ambil `4PQ`, CiteScore), cache disk per ISSN;
   fallback tenang bila 404/kuota habis.
5. `aggregator.py` — `sort="quality"` memakai grade + pct.
6. `server.py` — expose `sort` baru; tool `group_by_quality`
   (kembali breakdown per kelas + contoh paper + alasan kelas).
7. `web/` — chip kelas, toggle grup, histogram; pakai komponen shadcn yang ada.

Di luar cakupan: appraisal metodologi mendalam per paper (itu ranah pipeline
SLR yang sudah ada: `slr_appraise`), scraping CiteScore dari web, dan
pembedaan skema quartile JCR vs Scimago (pakai satu skema: Scopus 4PQ, dan
tulis skemanya di UI).

## 5. Rujukan

- Hicks D. et al. 2015. The Leiden Manifesto for research metrics. *Nature* 520:429–431. DOI 10.1038/520429a
- San Francisco Declaration on Research Assessment (DORA), 2013. DOI 10.1242/dev.099234
- McKiernan E.C. et al. 2019. Use of the Journal Impact Factor in academic review, promotion, and tenure evaluations. *eLife* 8:e47338. DOI 10.7554/elife.47338
- Purkayastha A. et al. 2019. Comparison of two article-level, field-independent citation metrics: FWCI and RCR. DOI 10.1016/j.joi.2019.03.012
- Bornmann L. 2020. How can citation impact in bibliometrics be normalized? *Quantitative Science Studies* 1(2). DOI 10.1162/qss_a_00089
- GRADE: Core GRADE 4 (BMJ, DOI 10.1136/bmj.r1468); GRADE guidelines 21 (DOI 10.1016/j.jclinepi.2019.12.020)
- OpenAlex API docs: `cited_by_percentile_year` vs `cited_by_percentile_field`.
