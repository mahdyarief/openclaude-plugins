# Pengelompokan & Peringkat Kualitas Paper

## Tujuan

Setiap hasil pencarian journal-scout membawa **kelas kualitas** yang dapat dijelaskan
sinyalnya, agar pengguna menerima "paper berkualitas" — bukan sekadar banyak paper —
dapat dikelompokkan per kelas, dan disort berdasarkan kelas. Kelas selalu disajikan
beserta breakdown sinyalnya (tidak pernah angka tunggal tanpa penjelasan).

## Prinsip (sesuai DORA & Leiden Manifesto)

- **Artikel-level dulu, jurnal-level sebagai konteks.** Quartile jurnal tidak
  digunakan sebagai pengganti kualitas artikel (rekomendasi 1 DORA); ia hanya
  salah satu sinyal di antara beberapa.
- **Normalisasi bidang+usia.** Sinyal utama adalah
  `citation_normalized_percentile` OpenAlex (setara FWCI: percentile sitasi
  paper terhadap distribusi **bidang sub, tipe paper, dan tahun** penerbitan
  dalam jendela 4 tahun) — sesuai Leiden Prinsip 6 (percentile = normalisasi
  paling robust). OpenAlex tidak menyediakan field bernama
  `cited_by_percentile_field`; yang tersedia adalah `cited_by_percentile_year`
  (sudah dipetakan sekarang) dan `citation_normalized_percentile` (yang baru).
- **Integritas menang.** Paper `is_retracted` selalu kelas `flagged`, tidak masuk
  kelompok kualitas mana pun.
- **Preprint ≠ rendah**, hanya belum terverifikasi peer review: diberi flag.
- **Tipe/desain studi ditampilkan sebagai konteks, bukan bonus kelas.** GRADE
  menilai kepastian *body of evidence* (bukan memberi nilai mutu universal pada
  satu paper); RCT atau meta-analysis tidak otomatis bermutu tinggi tanpa
  appraisal risk-of-bias dan metode.
- **Data sitasi muda diberi konteks.** Paper ≤ 2 tahun dapat memiliki percentile
  yang belum stabil; UI menampilkan usia sitasi, namun grade mengikuti sinyal
  yang terukur tanpa mengganti bukti yang hilang dengan reputasi jurnal.

## Berlaku untuk semua sumber

Grading melekat di `Paper` hasil **merge** (setelah agregasi semua provider),
sehingga berlaku untuk paper dari semua sumber. Sinyal dilengkapi via
enrichment batch pasca-merge (best-effort, tanpa memblokir hasil):

| Sinyal | Sumber | Cara |
|---|---|---|
| `citation_normalized_percentile` (0–1, dinormalisasi subfield+tipe+tahun, setara FWCI) | OpenAlex | 1 request batch per chunk 100 DOI hasil merge (`filter=doi:...`) |
| `journal_quartile` (1–4), `journal_cite_score` | Scopus Serial Title API (`GET /content/serial/title/issn/{issn}`, view CITESCORE) | per ISSN, cache disk TTL 90 hari; quartile diturunkan dari band percentile CiteScore per subject area (Q1=top 25%, Q2=25–50%, Q3=50–75%, Q4=sebagian, ambil band terbaik); fallback `sjr_best_quartile` (Consensus) |
| `is_retracted` | OpenAlex + Crossref | sudah ada di merge |
| `is_preprint` | OpenAlex | sudah ada |
| desain studi | `study_type` / `publication_types` | sudah ada (Consensus/PubMed dll.) |

Paper tanpa DOI tidak ikut batch OpenAlex; paper tanpa ISSN tidak ikut lookup
Scopus — keduanya tetap di-grade dari sinyal yang ada.

## Kelas & aturan (deterministik, terdokumentasi di kode)

Sinyal per paper:
- `pct` = `citation_normalized_percentile` (0–1; nilai 0.9 = 90% paper dalam
  subfield+tipe+tahun yang sama punya sitasi lebih rendah), fallback
  `cited_by_percentile` (varian tahun, 0–100 → dibagi 100)
- `q` = `journal_quartile` (1–4, dari Scopus Serial Title API), fallback
  `sjr_best_quartile` (Consensus, skemanya berbeda — dicantumkan di tooltip)
- `design` = tipe/desain studi dari `publication_types`/`study_type`
  (hanya ditampilkan sebagai konteks di tooltip; tidak menaikkan grade)
- `young` = `year` ≥ tahun berjalan − 2 (jendela sitasi belum stabil)

Aturan (dievaluasi berurutan; yang pertama cocok menang):

1. `is_retracted` → **`flagged`**
2. tidak ada `pct` dan tidak ada `q` → **`ungraded`**
3. `pct` ≥ 0.90 → **`high`**
4. `pct` ≥ 0.75, atau `q` == 1 → **`medium`**
5. `q` == 2 → **`low`** (jurnal bereputasi, tetapi sitasi artikel belum
   mendukung kelas lebih tinggi)
6. sinyal ada tapi di bawah semua ambang di atas → **`low`**

Contoh: paper 2019 top-5% bidangnya → high. Paper 2025 dengan Q1 tetapi sitasi
belum matang → medium, ditandai "sitasi muda". Paper retracted apa pun sinyalnya
→ flagged.

Setiap paper menerima `quality_grade` + `quality_signals`
(pct, q, design, is_preprint, young, reasons: list string) untuk tooltip.

## Permukaan (surface)

- **Model**: tambah field `issn`, `citation_normalized_percentile`,
  `journal_quartile`, `journal_cite_score`, `quality_grade`, `quality_signals`
  di `Paper` + `to_dict`.
- **OpenAlex mapper**: petakan `primary_location.source.issn` → `issn` dan
  `citation_normalized_percentile` dari response work. Implementasi perlu
  verifikasi struktur objek/endpoint OpenAlex yang benar saat Task 1; jangan
  mengasumsikan ada field `cited_by_percentile_field`.
- **`quality.py`** (modul baru, fungsi murni): `grade_paper(paper) -> None`
  mengisi field grade; aturan di atas + reason string. Unit-testable tanpa
  jaringan.
- **Enrichment** di `search_all` setelah merge (flag `quality: bool = True`
  default, bisa dimatikan): batch OpenAlex per chunk ≤100 DOI via filter DOI
  (maksimum URL/query OpenAlex), lookup Scopus Serial Title API per ISSN unik
  dengan view CITESCORE (cache disk `journal-scout/.cache/scopus-serials.json`,
  TTL 90 hari). Quartile diturunkan dari CiteScore percentile band terbaik antar
  subject area. Kegagalan 401/403/429/404 tercatat sebagai warning parsial
  `errors["quality"]`, hasil tetap dikembalikan dengan sinyal yang tersedia.
- **Sort baru** `"quality"`: kelas descending (flagged paling bawah, bukan
  paling atas: flagged selalu dipisahkan), tie-break `pct` descending.
- **Tool MCP `group_by_quality`** + endpoint REST: mengembalikan hasil pencarian
  dikelompokkan per kelas: `{grade: {count, papers[], common_signals}}` —
  inilah "hasil dikelompokkan berdasarkan grade papernya".
- **Web UI** (shadcn yang ada):
  - kolom/chip kualitas di `PaperTable.tsx` (high=emerald, medium=sky,
    low=amber, flagged=rose, ungraded=slate) + tooltip breakdown sinyal;
  - toggle "Kelompokkan per kelas kualitas" di `SearchResults.tsx` yang
    merender header grup;
  - opsi sort "Kualitas"; catatan kecil bila mayoritas hasil berlabel
    "data sitasi masih muda".

## Batasan

- Tidak menambah dependency Python; tidak mengubah rute REST yang ada (hanya
  menambah parameter & tool baru).
- Quartile utama dihitung dari **CiteScore percentile per subject area** Scopus
  (best quartile pada subject-area yang sesuai; paper multidisiplin dapat punya
  beberapa bidang). Jika fallback ke `sjr_best_quartile` Consensus, tooltip
  menuliskan bahwa skemanya SJR, bukan CiteScore.
- Tanpa appraisal metodologi mendalam per paper — itu ranah pipeline SLR
  (`slr_appraise`) yang sudah ada.
- Cache disk hanya untuk lookup Scopus source (data jurnal berubah lambat);
  grade selalu dihitung dari data hasil merge terkini.

## Verifikasi

- Unit test `quality.py`: setiap aturan + contoh di atas (TDD, pytest; tidak
  ada mock jaringan — input berupa dict paper).
- Test mapper OpenAlex untuk `issn` & `citation_normalized_percentile` (fixture JSON).
- Test enrichment: batch DOI + cache Scopus (fetcher di-mock di provider, pola
  yang sudah ada).
- Test sort `"quality"` di aggregator.
- `npm run typecheck && npm run build` di `web/`; review manual chip, grup,
  dan sort di hasil pencarian.
- Uji degradasi: tanpa key Scopus → grade tetap muncul dari sinyal OpenAlex,
  `errors["quality"]` menjelaskan.

## Di luar cakupan

Scraping CiteScore dari web, pembedaan skema quartile lintas vendor,
perubahan pipeline SLR, dan penilaian risiko bias per paper.
