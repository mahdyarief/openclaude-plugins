# Arsitektur Zotero Translator — Referensi untuk journal-scout-mcp

Sumber: Zotero 10.0.6, folder `D:/Github/agent-workspace/_rea_work/zotero/extracted/core/app-omni-extracted/translators/` (752 file `.js`).
Target penerapan: `D:/Github/agent-workspace/openclaude-plugins/journal-scout-mcp/src/josc/`.
Tanggal analisis: 2026-10-24.

## 1. Spesifikasi resmi (AGENTS.md / CLAUDE.md)

`AGENTS.md` dan `CLAUDE.md` di folder translators **identik** (verifikasi `diff` kosong). Poin relevan:

| Bukti (file:line) | Isi |
|---|---|
| AGENTS.md:5-10 | Ada 4 tipe translator: **Web** (scrape situs), **Import** (parse format file → item), **Export** (item → format file), **Search** (lookup via identifier DOI/ISBN/PMID/arXiv ke API eksternal — "identifier-resolution services like Crossref, OpenAlex, or Library of Congress") |
| AGENTS.md:12 | Satu file boleh gabung multi-tipe; semua fungsi tiap tipe ditulis dalam satu file |
| AGENTS.md:39-41 | `XHR`/`fetch()` tidak tersedia; HTTP lewat global `request()`, `requestText()`, `requestJSON()`, `requestDocument()`; `ZU.doGet/doPost/processDocuments` **deprecated** |
| AGENTS.md:44-45 | Hindari selector yang mudah berubah; translator web umumnya 50–100 baris (sering hanya memanggil EM), >1000 baris = salah desain |
| AGENTS.md:18-26 | Translator yang dihapus wajib dicatat di `deleted.txt` + naikkan penanda versi baris pertama |

Distribusi `translatorType` (bitmask, hasil grep seluruh 752 file): `4` (web) = 691, `1` (import) = 16, `2` (export) = 12, `8` (search) = 11, `3` (import+export) = 9, `12` (web+export) = 8, `6` (import+export+web) = 1. Tercatat 699 file memiliki `detectWeb`.

## 2. Anatomi satu file translator

Setiap file = **JSON header** + **kode JS**. Contoh nyata `Library of Congress ISBN.js:1-12`:

```json
{
	"translatorID": "c070e5a2-4bfd-44bb-9b3c-4be20c50d0d9",
	"label": "Library of Congress ISBN",
	"creator": "Sebastian Karcher",
	"target": "",
	"minVersion": "3.0.9",
	"maxVersion": "",
	"priority": 97,
	"inRepository": true,
	"translatorType": 8,
	"lastUpdated": "2023-08-25 05:06:07"
}
```

| Field | Arti | Catatan dari contoh |
|---|---|---|
| `translatorID` | UUID tetap, dirujuk translator lain | `DOI Content Negotiation.js:90` memanggil Crossref REST by ID `0a61e167-...` |
| `label` | Nama tampil | — |
| `target` | Pola URL (web) / ekstensi file (import/export) | Kosong/null untuk search |
| `priority` | Angka kecil = dicoba lebih dulu | Lihat tabel §3 |
| `translatorType` | Bitmask: 1=import, 2=export, 4=web, 8=search | Semua file di §3 bernilai 8 |
| `minVersion`/`lastUpdated` | Kompatibilitas & versioning | |

Fungsi yang harus ada **tergantung tipe**: web → `detectWeb(doc,url)` + `doWeb(doc,url)`; search → `detectSearch(item)` + `doSearch(item)`; import → `detectImport()`/`doImport()`; export → `doExport()`. Semua translator mengakhiri item dengan `item.complete()` dan diakhiri blok `var testCases = [...]` sebagai unit test bawaan (mis. `Library of Congress ISBN.js:46-70`).
