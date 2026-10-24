# journal-scout — Dokumentasi Internal

Dokumentasi kondisi aktual kode dan rencana pengembangan. Berbeda dari
`../pop8/` yang mendokumentasikan aplikasi lain, folder ini adalah **sumber
kebenaran tentang repo ini sendiri**.

## Daftar dokumen

| File | Isi |
|---|---|
| [01-current-state.md](01-current-state.md) | Arsitektur, modul, tool MCP, route API, route web |
| [02-provider-matrix.md](02-provider-matrix.md) | Matriks kapabilitas 9 provider |
| [03-gap-analysis.md](03-gap-analysis.md) | Gap terhadap PoP8, dipetakan ke kode |
| [04-roadmap.md](04-roadmap.md) | Urutan pengerjaan berdasarkan biaya/manfaat |

## Aturan pemeliharaan

1. Setiap klaim tentang kode **wajib** menyertakan `file:line`.
2. Kalau sebuah fitur ditambahkan, perbarui `01-current-state.md` dan hapus
   barisnya dari `03-gap-analysis.md` — jangan biarkan dua dokumen
   bertentangan.
3. `04-roadmap.md` boleh berubah lebih sering; itu dokumen hidup.

## Angka kunci (terverifikasi dari kode)

| Metrik | Nilai |
|---|---|
| Provider terdaftar | 9 (`scopus, arxiv, openalex, semanticscholar, crossref, pubmed, dblp, unpaywall, opencitations`) |
| Provider bisa search | 7 (tanpa `unpaywall`, `opencitations`) |
| Tool MCP | 23 |
| Route HTTP API | 10 |
| Route web UI | 3 (`/`, `/graph`, `/metrics`) |
| Format ekspor terdaftar | 11 (`apa, bibtex, chicago, csv, csv_header, endnote, harvard, isi, json, ris, vancouver`) |

Diverifikasi dengan menjalankan `TOOL_NAMES`, `provider_names()`,
`search_provider_names()`, dan `FORMATTERS` dari `src/josc`.
