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

**Status 2026-10-24: sudah ditutup.** `src/josc/exporters.py` mendaftarkan
11 format (`FORMATTERS`, `exporters.py:20`): `apa`, `bibtex`, `chicago`,
`csv`, `csv_header`, `endnote`, `harvard`, `isi`, `json`, `ris`, `vancouver`.
`format_papers()` (`exporters.py:438`) dipanggil dari tool MCP
`export_results` (`server.py:187-206`) dan route `POST /api/export`
(`api.py:279-298`).

Yang masih tersisa dari daftar awal:

1. ~~Wire-up `format_papers`~~ — selesai.
2. ~~Tambah format murah (`endnote`, `isi`, CSV+BOM, gaya sitasi)~~ —
   selesai.
3. **Export/import arsip** butuh model serialisasi query + hasil. Ini
   pekerjaan lebih besar dan belum dikerjakan.
