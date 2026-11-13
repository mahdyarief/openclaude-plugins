# Not Absorbing — Explicit Scope Decisions

> **For agentic workers:** This file contains no implementation tasks. It is a decision record. Do not execute anything here.

**Goal:** Mencatat fitur Zotero 10.0.6 yang **sengaja tidak** diserap ke journal-scout-mcp, beserta alasannya, supaya keputusan ini tidak dibuka ulang tanpa bukti baru.

**Architecture:** Tidak ada perubahan kode. Setiap baris tabel adalah satu keputusan dengan bukti dari artefak Zotero dan alasan penolakan yang spesifik untuk josc.

**Tech Stack:** Tidak ada.

## Global Constraints

- Keputusan di sini bersifat default, bukan larangan mutlak. Membalik salah satunya memerlukan spec baru dan plan baru.
- Alasan penolakan harus merujuk pada perbedaan bentuk produk josc (MCP server + web explorer) versus Zotero (aplikasi desktop dengan library lokal), bukan pada "terlalu sulit".

---

## Matriks keputusan

| Fitur Zotero | Sumber bukti | Alasan tidak diserap |
|---|---|---|
| Library item + collection tree | `omni/chrome/content/zotero/xpcom/data/` | josc tidak memiliki konsep library lokal; sumber kebenarannya adalah provider daring. Menambah library berarti membangun model data baru yang bersaing dengan arsip pencarian yang sudah ada. |
| Sync server (Zotero Web API) | `omni/chrome/content/zotero/xpcom/sync.js` | Tidak ada akun, tidak ada server milik josc, dan tidak ada kebutuhan multi-device pada pemakaian MCP. |
| 748 translator situs | `omni/translators/*.js` | Setiap translator adalah scraper per situs dengan pemeliharaan berkelanjutan. josc memakai API resmi provider (Crossref, OpenAlex, Scopus, dsb.); menambah scraper akan menambah beban pemeliharaan tanpa menambah cakupan yang berarti. |
| 48 endpoint Local API | `omni/chrome/content/zotero/xpcom/server/server_localAPI.js` | Local API Zotero dirancang untuk aplikasi pihak ketiga yang membaca library lokal. josc sudah mengekspos REST-nya sendiri; meniru bentuk endpoint Zotero akan menghasilkan dua kontrak API yang harus dijaga selaras. |
| Anotasi PDF (highlight, note, tag) | `omni/chrome/content/zotero/xpcom/annotations.js` | josc tidak menyimpan PDF dan tidak punya UI pembaca. Menyimpan anotasi tanpa pembaca berarti data yang tidak bisa dipakai. |
| Item types + field schema (40 tipe) | `omni/resource/schema/global/schema.json` | josc memakai satu model `Paper` yang dipetakan dari banyak provider. Model 40 tipe Zotero (film, paten, surat, dsb.) tidak relevan untuk pencarian literatur akademik. |
| Report builder | `omni/chrome/content/zotero/xpcom/report.js` | josc sudah punya `compute_metrics` + `/api/metrics/report`. Menambah report builder kedua akan menduplikasi tanggung jawab. |
| OpenURL resolver / locate manager | `omni/chrome/content/zotero/xpcom/locateManager.js` | josc sudah mengembalikan `url`, `pdf_url`, dan `is_open_access` dari provider. Menambah resolver berarti menambah panggilan jaringan untuk data yang sebagian besar sudah ada. |
| Feed reader generik (RSS/Atom) | `omni/chrome/content/zotero/xpcom/feedReader.js` | josc hanya butuh output feed untuk watch (irisan 05), bukan pembaca feed umum. Membaca feed adalah fitur aplikasi desktop, bukan fitur server pencarian. |
| Retraction Watch paragraf penjelasan | `omni/chrome/content/zotero/xpcom/retractions.js:1048-1160` | Hanya **kunci** alasan yang diport (irisan 02). Paragraf penjelasan adalah konten pihak ketiga yang berubah mengikuti kebijakan Retraction Watch; menyalinnya ke repo akan cepat basi. |
| Word/LibreOffice integration | `core/integration/` | Di luar cakupan produk. josc menghasilkan teks sitasi; integrasi ke pengolah kata adalah tanggung jawab pengguna. |
| Fulltext FTS5 + antrean reindex | `omni/chrome/content/zotero/xpcom/fulltext.js` | josc memakai indeks in-memory yang dibangun ulang (irisan 06). FTS5 butuh database terpisah, tokenizer khusus, tabel CJK, dan antrean latar belakang; biayanya tidak sepadan untuk korpus berukuran ratusan hingga beberapa ribu record. |
| Sinkronisasi metadata ke file PDF | `omni/chrome/content/zotero/xpcom/attachments.js` | josc tidak memiliki file PDF sebagai objek yang dikelola. Irisan 04 hanya membaca PDF sebagai input, tidak menulis balik. |

---

## Aturan membalik keputusan

Sebuah baris boleh dibalik hanya bila ketiga syarat ini terpenuhi:

1. Ada kebutuhan pengguna yang konkret dan berulang yang tidak bisa dipenuhi fitur yang sudah ada.
2. Ada plan baru di direktori ini dengan task TDD lengkap, bukan tambahan pada file yang sudah ada.
3. Perubahan itu tidak menambah dependensi runtime baru tanpa alasan yang tertulis di plan tersebut.

---

## Self-review

- **Cakupan:** seluruh area besar Zotero yang tidak masuk irisan 01-06 tercatat di tabel.
- **Placeholder:** tidak ada task dan tidak ada kode; file ini memang bukan plan eksekusi.
- **Konsistensi:** setiap penolakan merujuk irisan yang sudah ada (02, 04, 05, 06) atau fitur josc yang sudah ada (`compute_metrics`, `/api/metrics/report`, `pdf_url`).
