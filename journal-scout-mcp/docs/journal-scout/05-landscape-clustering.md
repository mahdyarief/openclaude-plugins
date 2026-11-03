# 05 — Landscape & Clustering (Keyword → Peta Korpus)

Status: **PROPOSAL (belum dikerjakan)**
Referensi pembanding: Scopus AI, OpenKnowledgeMaps (Headstart)

---

## 1. Latar belakang

Hari ini journal-scout hanya bisa membangun **ego-network** di sekitar satu
seed paper (`GET /api/network`, `build_citation_network`). Tidak ada jalur
"masukkan keyword → dapatkan peta topik" seperti Scopus AI atau
OpenKnowledgeMaps. Dua hal membuat fitur itu belum mungkin:

1. **Metadata topik nyaris kosong** di sebagian besar provider, sehingga
   clustering berbasis konten tidak punya bahan.
2. **Tidak ada pipeline clustering teks** (TF-IDF / reduksi dimensi /
   clustering) — satu-satunya clustering yang ada adalah label propagation
   murni pada edge sitasi (`_assign_communities`, `network.py:182`).

Dokumen ini memetakan gap vs dua pembanding dan mengusulkan urutan kerja
berprioritas. Implementasi dilakukan setelah proposal ini disepakati, dengan
pendekatan TDD (modul `josc/landscape.py` + `tests/test_landscape.py` dibuat
lebih dulu).

---

## 2. Pembanding

| Dimensi | Scopus AI | OpenKnowledgeMaps | journal-scout (saat ini) |
|---|---|---|---|
| Input | Natural-language query | Query / korpus | Keyword + filter terstruktur |
| Unit analisis | Topic cluster + ringkasan AI | Base map + overlay korpus | Ego-network 1 paper |
| Clustering | Topik terkurasi Scopus + AI | Sitasi + teks, label otomatis | Label propagation sitasi |
| Label cluster | Dihasilkan AI | c-TF-IDF / keyphrase | Tidak ada (nomor saja) |
| Visualisasi | Concept map + ringkasan | Peta 2D interaktif, hull, zoom | Force graph kanvas |
| Metadata topik | ASJC + authkeywords | Multi-source | Sangat lemah (lihat §3) |
| Skala | Ribuan dokumen | Ribuan dokumen | 200 node |
| Explainability | Sitasi pendukung tiap klaim | Cluster + tren + author | Stats mentah |

---

## 3. Temuan konkret (bukti kode)

1. **Topik nyaris kosong di 3 dari 5 provider.**
   - OpenAlex hanya mengambil `primary_topic.display_name`
     (`providers/openalex.py:54,79`), membuang array `topics[]`,
     `subfield`, `field`, `domain`, dan `keywords[]`.
   - Scopus **tidak mengisi `topics` sama sekali** (`providers/scopus.py:121-134`).
   - Semantic Scholar juga tidak (`providers/semanticscholar.py:49-64`).
   - Akibatnya filter topik di UI praktis hanya bekerja untuk PubMed dan
     Crossref.

2. **Tidak ada embedding / clustering teks.** Tidak ada TF-IDF, UMAP,
   HDBSCAN, atau pun `numpy`/`scikit-learn` (`pyproject.toml:7` hanya
   mcp/httpx/bs4/lxml). `_assign_communities` hanya memakai edge sitasi,
   sehingga paper tanpa relasi sitasi tidak pernah masuk cluster bermakna.

3. **Cluster tidak terlihat di UI.** `ForceGraph.tsx:29-33` mewarnai node
   berdasarkan `kind` (seed/citation/reference), bukan `community`. Nomor
   cluster hanya muncul di drawer (`graph.tsx:285`). Tidak ada label,
   ukuran cluster, atau ringkasan.

4. **Filter topik bersifat substring lokal.** `useSearchController.ts:213-235`
   menghitung `availableTopics` dari halaman hasil saat ini; tidak ada
   sinonim, hierarki, atau canonical ID. "ML" tidak cocok dengan
   "Machine Learning".

5. **Tidak ada jalur "keyword → landscape".** Graph butuh seed DOI/ID.
   Tidak ada endpoint atau tool yang menerima keyword lalu mengembalikan
   peta korpus.

---

## 4. Rencana perbaikan berprioritas

### P0 — Fondasi data topik (murah, dampak besar)

- **OpenAlex**: ambil seluruh `topics[]` + skor, plus
  `primary_topic.subfield/field/domain` dan `keywords[]`; simpan hierarki,
  bukan hanya nama.
- **Scopus**: minta `authkeywords` dan `subject-area` (ASJC) di abstract
  retrieval, petakan ke `topics`/`keywords`.
- **Semantic Scholar**: minta `fieldsOfStudy` dan `s2FieldsOfStudy`.
- Tambah field `Paper.topic_ids` / `Paper.topic_paths` agar normalisasi
  lintas provider mungkin (OpenAlex topic ID, MeSH UI, ASJC code).
- Tambah test provider yang memverifikasi bahwa `topics`/`keywords` terisi.

### P0 — Endpoint & tool landscape

Modul baru `josc/landscape.py` dengan pipeline:
`search_all` → dedup/merge → TF-IDF (judul + abstrak + keyword) →
reduksi dimensi → cluster → label c-TF-IDF → statistik.

Kontrak endpoint:

```json
POST /api/landscape
{
  "query": "...",
  "year_from": 2015,
  "sources": ["openalex", "crossref"],
  "max_papers": 500,
  "cluster_method": "agglomerative | hdbscan",
  "reduce": "svd | umap"
}
```

Respons:

```json
{
  "clusters": [
    {
      "id": 0,
      "label": "...",
      "size": 87,
      "median_year": 2021,
      "top_topics": ["..."],
      "top_authors": ["..."],
      "top_venues": ["..."]
    }
  ],
  "nodes": [
    { "id": "...", "x": 0.42, "y": -0.11, "cluster": 0, "title": "..." }
  ],
  "edges": [ ... ],
  "stats": { ... }
}
```

Tool MCP setara: `build_research_landscape`.

### P1 — Visualisasi peta

Route baru `/landscape`: scatter/force 2D, warna per cluster, convex hull,
label centroid, brush/lasso untuk filter, timeline slider, klik cluster →
daftar paper. Bisa memakai ulang kanvas `ForceGraph` atau ganti ke `d3`
penuh (sudah ada `d3-force` di `web/package.json`).

### P1 — Label & explainability

- c-TF-IDF untuk label tanpa LLM (paritas OpenKnowledgeMaps).
- Opsional penamaan via LLM bila API key tersedia (paritas Scopus AI).
- Sertakan "why": top terms, paper representatif, tren per tahun.

### P1 — Clustering hibrida

Gabungkan kemiripan teks dengan edge `coupled`/`cocited` yang sudah ada di
`network.py`. Meniru base map OpenKnowledgeMaps, lebih stabil daripada
label propagation murni.

### P2 — Analitik lanjutan

- Deteksi emerging topic (delta volume per tahun).
- Research gap (area renggang di ruang embedding).
- Ranking expert/venue per cluster.
- Ekspor PNG/SVG/JSON, cache hasil per hash query.

---

## 5. Catatan dependensi

Untuk ~500 dokumen, TF-IDF + agglomerative clustering bisa **pure-Python**
(beberapa larik + jarak cosinus). `UMAP`/`HDBSCAN` butuh `numpy` dan
`scikit-learn` — jadikan **extra opsional** `[landscape]` agar instalasi
dasar tetap ringan:

```toml
[project.optional-dependencies]
landscape = ["numpy>=1.26", "scikit-learn>=1.4"]
```

---

## 6. Urutan eksekusi yang diusulkan

1. Perluas ingest topik (P0) + test provider — prasyarat semua fitur cluster.
2. Modul `josc/landscape.py` + `tests/test_landscape.py` (TDD).
3. Expose `/api/landscape` dan tool MCP `build_research_landscape`.
4. Bangun route `/landscape` di UI.
5. Baru pertimbangkan UMAP / LLM labeling (P2).

---

## 7. Yang sengaja TIDAK ditiru (sejalan dengan 03-gap-analysis)

| Item | Alasan |
|---|---|
| Natural-language "prompt" ala Scopus AI | butuh LLM berbayar; kita pakai c-TF-IDF dulu |
| Scraping Google Scholar | tidak stabil, risiko blokir |
| Web of Science | butuh lisensi institusi |
| Label masih nomor (belum ada nama) | menunggu P1 label c-TF-IDF |
