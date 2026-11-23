# 04 — Format Ekspor PoP8

PoP8 memisahkan ekspor menjadi empat keluarga: data bibliografis, sitasi
terformat, report, dan arsip. Setiap format data/sitasi tersedia dalam tiga
varian aksi: **Save** (ke file), **Copy** (ke clipboard), dan **Details**
(pratinjau).

## Data bibliografis

| Format | Ekstensi | Catatan |
|---|---|---|
| CSV | `.csv` | tanpa baris header |
| CSV with Header | `.csv` | baris pertama berisi nama kolom |
| Excel | `.xls` | tanpa baris header |
| Excel with Header | `.xls` | dengan header |
| BibTeX | `.bib` | escape LaTeX untuk karakter non-ASCII |
| EndNote | `.enw` | format EndNote |
| ISI / WoS Export | `.txt` | format tagged WoS |
| JSON | `.json` | dump terstruktur |
| RIS / RefManager | `.ris` | format RIS standar |

## Sitasi terformat

| Gaya | Contoh pemakaian |
|---|---|
| APA | psikologi, ilmu sosial |
| Chicago | humaniora, sejarah |
| CSIRO | standar Australia |
| Harvard | umum di Inggris/Australia |
| MLA | sastra, bahasa |
| Vancouver | kedokteran, biomedis |

## Report

- **Search Report (basic)** — satu halaman ringkasan.
- **Search Report (extended)** — ringkasan + tabel sitasi per tahun.
- **Metrics as CSV** — metrik saja, tanpa daftar karya.

## Arsip

| Aksi | Shortcut | Isi |
|---|---|---|
| Export to Archive | `Ctrl+Shift+S` | seluruh workspace/query tree ke satu file arsip |
| Import from Archive | `Ctrl+Shift+O` | memuat kembali arsip |
| Import External Data | `Ctrl+O` | `.ciw, .csv, .enw, .ris, .txt` |

## Implikasi untuk journal-scout

**Status 2026-10-25: seluruh daftar sudah ditutup.** `src/josc/exporters.py`
sekarang mendaftarkan 17 formatter (`FORMATTERS`): `apa`, `bibtex`, `chicago`,
`csiro`, `csv`, `csv_bom`, `csv_header`, `csv_plain`, `endnote`, `harvard`,
`isi`, `json`, `mla`, `ris`, `vancouver`, `xls`, `xls_plain`.
`format_papers()` dipanggil dari tool MCP `export_results` dan route
`POST /api/export` (`api.py:423`).

Pemetaan ke tabel PoP8 di atas:

| PoP8 | Formatter journal-scout |
|---|---|
| CSV (tanpa header) | `csv_plain` (`exporters.py:274-278`) |
| CSV with Header | `csv` (`exporters.py:268-271`) — header selalu ditulis |
| Excel (tanpa header) | `xls_plain` (`exporters.py:409-410`) |
| Excel with Header | `xls` (`exporters.py:380`) — header selalu ditulis |

`_build_csv` (`exporters.py:244`) menerima `header: bool = True`; hanya
`csv_plain` yang memanggilnya dengan `header=False`. `csv_header` adalah
formatter lama dengan **susunan kolom berbeda**, bukan varian header dari
`csv` — jangan tertukar.

Aksi UI: `ExportMenu.tsx` menyediakan **Download** (`handleDownload`
`:64-79`), **Copy** (`handleCopy` `:80-95`), dan **Details** (`handleDetails`
`:96-107`, panel pratinjau `:161-180`). Details memanggil `exportPapers` yang
sama lalu menampilkan teksnya di `<pre>` tanpa mengunduh file.

1. ~~Wire-up `format_papers`~~ — selesai.
2. ~~Tambah format murah (`endnote`, `isi`, gaya sitasi)~~ — selesai.
3. ~~**Export/import arsip**~~ — **selesai 2026-10-25.** `GET
   /api/searches/{id}/export` (`api.py:496`) mengemas query + filter + sumber
   + hasil menjadi arsip JSON `{format: "josc-search-archive", version: 1}`,
   dan `POST /api/searches/import` (`api.py:521`) memuatnya kembali sebagai
   baris riwayat baru.
   **Arsip seluruh workspace** juga sudah ada: `GET /api/searches/export`
   (`api.py:661`) mengemas semua baris lewat `export_workspace`
   (`store.py:399`), dan `POST /api/searches/import-workspace`
   (`api.py:681`) memuatnya lewat `import_workspace` (`store.py:423`). UI
   `/history` punya tombol "Export workspace" / "Import workspace"
   (`history.tsx:373` dan `:394`).
4. ~~**MLA**~~ — **selesai.** `@_register("mla")` di `exporters.py:514`,
   implementasi `_to_mla` (`exporters.py:515`).
5. ~~**CSIRO**~~ — **selesai.** `@_register("csiro")` di `exporters.py:552`,
   implementasi `_to_csiro` (`exporters.py:553`).
6. ~~**Excel `.xls`**~~ — **selesai.** `@_register("xls")` di
   `exporters.py:371`, implementasi `_to_xls` (`exporters.py:372`) memakai
   SpreadsheetML 2003 XML yang bisa dibuka Excel.
7. ~~**CSV+BOM**~~ — **selesai.** `@_register("csv_bom")`
   (`exporters.py:273`) memakai `_build_csv` bersama (`exporters.py:244`)
   lalu menambahkan `\ufeff`.
8. ~~**Search Report (basic/extended)**~~ — **selesai.**
   `format_search_report(payload, mode)` (`exporters.py:671`) dirender lewat
   `GET /api/metrics/report?mode=basic|extended` (`api.py:628`).

**Import External Data** (`.ciw/.csv/.enw/.ris/.txt`) juga sudah ditutup:
`src/josc/importers.py` menyediakan `detect_format` (`:75`) dan
`parse_import` (`:361`), diekspos lewat `POST /api/import`
(`api.py:561`).
