# 05 — Panduan Pemakaian journal-scout

Panduan praktis untuk memakai journal-scout lewat dua permukaan: **MCP tool**
(dipanggil dari sesi Claude) dan **web UI** di `http://127.0.0.1:8793`.
Semua contoh di bawah sudah disesuaikan dengan skema yang benar-benar ada di
`src/josc/server.py` dan route di `src/josc/api/app.py`.

## 1. Pilih permukaan

| Kebutuhan | Pakai |
|---|---|
| Riset cepat di dalam sesi Claude, hasil langsung dipakai untuk menulis | MCP tool `search_all` |
| Menelusuri banyak hasil, sortir, filter, ekspor, buka abstrak | Web UI `/` |
| Melihat keterkaitan sitasi antar paper | Web UI `/graph` |
| Menghitung h-index / i10 / g-index / AWCR | Web UI `/metrics` atau MCP `compute_metrics` |
| Membuka kembali pencarian lama | Web UI `/history` |

## 2. Sintaks query

Query diteruskan ke provider masing-masing setelah diterjemahkan oleh
`query.translate_query` (`src/josc/query.py`). Aturannya:

- Operator boolean **harus HURUF BESAR**: `AND`, `OR`, `NOT`.
- Provider yang tidak mendukung sebuah operator akan menerima query tanpa
  operator itu, dan respons memuat `query_warnings` supaya Anda tahu.
- Scopus menulis negasi sebagai `AND NOT`; konversi dilakukan otomatis.
- Jangan pakai tanda kutip atau tag field (`TITLE:`, `AU:`); translator tidak
  menambahkan dan tidak mengubahnya.

Dukungan operator per provider (`OPERATOR_SUPPORT`):

| Provider | AND | OR | NOT |
|---|---|---|---|
| scopus | ya | ya | ya |
| pubmed | ya | ya | ya |
| arxiv | ya | ya | ya |
| dblp | ya | ya | ya |
| crossref | tidak | ya | ya |
| openalex | tidak | tidak | tidak |
| semanticscholar | tidak | tidak | tidak |

Contoh query yang aman untuk semua provider: `data quality AND governance`.
Contoh yang hanya optimal di Scopus/PubMed: `(machine learning OR deep learning) NOT survey`.

## 3. MCP tool: alur yang disarankan

### 3.1 Pencarian awal

```
search_all
  query="data quality AND governance"
  limit_per_source=10
  year_from=2018
  sort="relevance"
  order="desc"
```

Parameter yang tersedia pada `search_all`:

| Parameter | Arti |
|---|---|
| `query` | Kata kunci (wajib) |
| `limit_per_source` | Hasil per sumber sebelum dedup, default 5 |
| `sources` | Batasi sumber, mis. `["scopus","openalex"]` |
| `year_from` / `year_to` | Rentang tahun |
| `tech_only` | Hanya bidang teknologi/ilmu komputer |
| `offset` | Paginasi |
| `author`, `venue`, `affiliation`, `issn`, `orcid`, `doi` | Filter; hanya diteruskan ke provider yang mendeklarasikannya |
| `topic` | Filter lokal pasca-merge: pertahankan hasil yang `topics`-nya mengandung teks ini (substring, case-insensitive) |
| `sort` | `relevance`, `citations`, `year`, `title` |
| `order` | `asc` atau `desc` |

Filter `topic` sengaja dijalankan **setelah** merge dan tidak dikirim ke
provider: kosakata topik tiap sumber berbeda (OpenAlex concept, Crossref
subject, PubMed MeSH), jadi tidak ada parameter query yang seragam. Biayanya
nol request tambahan. Contoh: `search_all query="data quality" topic="machine learning"`.

Skor `relevance` memberi bobot 3 untuk kecocokan di judul dan 1 untuk
kecocokan di abstrak, dan mengabaikan token `AND`/`OR`/`NOT`
(`aggregator._relevance_score`).

Respons selalu memuat `results`, `errors`, `counts`, `filters_applied`,
`filters_ignored`, `query_warnings`, dan `query_translated`. Periksa
`errors` dan `filters_ignored` — sumber yang gagal tidak menggagalkan
keseluruhan pencarian, tetapi hasilnya tidak lengkap.

### 3.2 Memperdalam satu paper

```
get_paper identifier="10.1145/3292500.3330701"
get_references identifier="10.1145/3292500.3330701" limit=30
get_citations identifier="10.1145/3292500.3330701" limit=30
get_related_works identifier="10.1145/3292500.3330701" limit=20
```

Gunakan `sources` bila identifier hanya dikenali satu provider, misalnya
`identifier="S2:..."` dengan `sources=["semanticscholar"]`.

### 3.3 Peta sitasi

```
build_citation_network
  identifier="10.1145/1515693.1516680"
  limit=20
  citing_limit=10
  reference_limit=10
  max_nodes=200
  graph_format="json"
```

| Parameter | Arti |
|---|---|
| `limit` | Jumlah referensi dan sitasi yang diambil untuk seed |
| `citing_limit` | Berapa paper pengutip yang daftar referensinya ikut diambil (untuk `coupled`/`cocited`) |
| `reference_limit` | Berapa referensi seed yang referensinya ikut diambil (hop kedua) |
| `max_nodes` | Batas jumlah node |
| `graph_format` | `json` atau `graphml` untuk Gephi/VOSviewer |

Jenis edge: `cites` (sitasi langsung), `coupled` (bibliographic coupling),
`cocited` (co-citation). Setiap node membawa `abstract`, `pdf_url`,
`is_open_access`, `in_degree`, `out_degree`, `degree`, dan `community`.
`stats.communities` menunjukkan jumlah klaster hasil label propagation.

### 3.4 Metrik

```
compute_metrics author="Nama Penulis" limit_per_source=50 mode="extended"
compute_metrics query="topik riset" year_from=2015 mode="basic"
```

`basic` mengembalikan jumlah paper, total sitasi, h-index, i10-index,
g-index, max/mean sitasi, dan citation velocity. `extended` menambah
`hc_index`, `hI_index`, `hI_norm`, `hm_index`, `AWCR`, `AW_index`, `AWCRpA`.

### 3.5 Ekspor

```
export_results papers=[...] format="bibtex"
```

Format yang tersedia: `apa`, `bibtex`, `chicago`, `csiro`, `csv`, `csv_bom`,
`csv_header`, `csv_plain`, `endnote`, `harvard`, `isi`, `json`, `mla`, `ris`,
`vancouver`, `xls`, `xls_plain`.

### 3.6 Tool per sumber

`search_scopus`, `search_arxiv`, `search_openalex`, `search_semanticscholar`,
`search_crossref`, `search_pubmed`, `search_dblp`, `search_garuda` memakai
skema filter yang sama; bedanya hanya `count` sebagai pengganti
`limit_per_source`.

## 4. Web UI

Jalankan server (dari root repo):

```bash
.venv/Scripts/python.exe .venv/Scripts/josc-web.exe
```

Lalu buka `http://127.0.0.1:8793`.

### 4.1 `/` — Literature search

1. Isi query, atur **per source**, klik **Search**.
2. **Sort** pilihan `Relevance` / `Citations` / `Year` / `Title`, tombol
   `Ascending`/`Descending` untuk membalik urutan.
3. **Filters** membuka `Year from`, `Year to`, `tech_only`, `offset`,
   `affiliation`, `issn`, `orcid`, `doi`, dan pilihan sumber.
4. Baris **Topic** di bawah chip hasil memfilter secara lokal: ketik teks atau
   klik salah satu chip topik teratas. Filter ini instan dan tidak memicu
   request baru; tombol **Clear** mengembalikan seluruh hasil.
5. Klik satu baris untuk membuka **PaperDrawer** (abstrak, DOI, PDF).
6. Centang baris (atau **Select all** / **Select cited**) lalu pakai
   **Export** untuk mengunduh format pilihan.
7. Pencarian otomatis tersimpan dan bisa dibuka lagi di `/history`.

### 4.2 `/graph` — Citation graph

1. Isi **Seed identifier** (DOI, Scopus id, atau OpenAlex id).
2. Atur **refs / cites** dan **citing refs**, klik **Build graph**.
3. Pada kanvas:
   - scroll untuk zoom, drag latar untuk pan, drag node untuk memindahkan;
   - hover node untuk menyorot tetangganya;
   - checkbox `cites` / `coupled` / `cocited` menyembunyikan jenis edge;
   - dua slider tahun memfilter rentang publikasi;
   - `+`, `−`, `Reset` untuk kontrol viewport.
4. Klik node untuk membuka panel kanan: klaster, status open access, judul,
   penulis, tahun, venue, `cites out` / `cited by`, tipe, abstrak, DOI, dan
   tautan Source record / PDF / doi.org.
5. **Expand references** / **Expand citations** menambahkan node dan edge
   baru langsung ke graf tanpa membangun ulang.
6. **Timeline** mengubah tata letak: sumbu horizontal menjadi tahun
   publikasi, sehingga arah perkembangan riset terbaca.
7. **Export GraphML** mengunduh graf untuk Gephi/VOSviewer.

### 4.3 `/metrics` — Metrik

Masukkan `author` atau `query`, atur `limit_per_source`, rentang tahun, dan
`mode` (`basic`/`extended`). Tersedia ekspor CSV dan laporan.

### 4.4 `/history` — Riwayat

Daftar pencarian tersimpan (dengan jumlah hasil dan umur). Aksi yang tersedia:
replay, duplikat, split, ekspor satu pencarian, impor arsip, dan hapus.
Impor file eksternal (BibTeX/RIS/CSV) juga lewat halaman ini.

## 5. Prompt siap pakai

Salin ke sesi Claude:

- **Survei literatur**
  > Gunakan `search_all` dengan query "data quality AND governance",
  > `limit_per_source=15`, `year_from=2015`, `sort="relevance"`. Kelompokkan
  > hasil per tema, sebutkan sumber yang gagal dari `errors`, lalu sarankan
  > 5 paper paling relevan beserta alasannya.

- **Lacak perkembangan satu paper**
  > Ambil `build_citation_network` untuk DOI 10.1145/1515693.1516680 dengan
  > `limit=20`, `citing_limit=10`, `reference_limit=10`. Jelaskan klaster yang
  > terbentuk dan paper mana yang menjadi penghubung antar klaster.

- **Profil penulis**
  > Jalankan `compute_metrics` dengan `author="Nama"`,
  > `limit_per_source=50`, `mode="extended"`. Ringkas h-index, i10, AWCR, dan
  > tren sitasi per tahun; sebutkan sumber data yang error.

- **Ekspor pustaka**
  > Ambil 30 hasil teratas untuk query "explainable AI" memakai `search_all`,
  > lalu format dengan `export_results` ke `bibtex`. Tampilkan juga daftar
  > DOI yang tidak punya metadata lengkap.

## 6. Field enrichment yang tersedia

Setiap hasil pencarian membawa metadata tambahan yang di-parse dari payload
provider — tidak ada request ekstra, jadi tidak menambah waktu tunggu:

| Field | Muncul dari | Dipakai untuk |
|---|---|---|
| `is_retracted` | OpenAlex, Crossref | Badge `retracted` di tabel + banner di drawer |
| `cited_by_percentile` | OpenAlex | Label `top X%` di kolom Cited |
| `citations_by_year` | OpenAlex | Grafik tren sitasi di drawer |
| `topics` | OpenAlex, Crossref, PubMed | Badge topik + daftar Topics |
| `keywords` | PubMed | Daftar Keywords |
| `publication_types` | PubMed | Daftar Pub types |
| `institutions` | OpenAlex | Daftar Institutions |
| `funders` | Crossref | Daftar Funders |
| `license` | Crossref | Tautan lisensi |
| `language` | OpenAlex | Field Language |
| `tldr` | Semantic Scholar | Kotak TL;DR di drawer |
| `is_open_access` | Scopus, OpenAlex | Badge `open access` |

Field yang kosong dari satu provider diisi oleh provider lain saat hasil
digabung (`merge_two`): topik/kata kunci di-union, flag retraksi menang bila
salah satu sumber menyatakan `true`, dan tren sitasi mengambil nilai maksimum
per tahun.

## 7. Batasan yang perlu diketahui

- `sort="relevance"` adalah skor lokal sederhana (judul/abstrak), bukan
  peringkat dari provider.
- `coupled` dan `cocited` hanya muncul bila `citing_limit` cukup besar,
  karena keduanya diturunkan dari daftar referensi paper pengutip.
- Hop kedua hanya mengambil `reference_limit` referensi pertama; naikkan
  bila butuh rantai sitasi lebih panjang, tetapi biayanya bertambah linear
  terhadap jumlah request.
- Provider tanpa API key tetap berjalan, tetapi kena rate limit lebih cepat;
  isi `polite_email` dan `semantic_scholar_api_key` di `config.json` bila
  tersedia.
