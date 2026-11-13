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
| [05-usage-guide.md](05-usage-guide.md) | Panduan pemakaian MCP tool dan web UI, sintaks query, prompt siap pakai |

## Aturan pemeliharaan

1. Setiap klaim tentang kode **wajib** menyertakan `file:line`.
2. Kalau sebuah fitur ditambahkan, perbarui `01-current-state.md` dan hapus
   barisnya dari `03-gap-analysis.md` — jangan biarkan dua dokumen
   bertentangan.
3. `04-roadmap.md` boleh berubah lebih sering; itu dokumen hidup.

## Angka kunci (terverifikasi dari kode)

| Metrik | Nilai |
|---|---|
| Provider terdaftar | 10 (`scopus, arxiv, openalex, semanticscholar, crossref, pubmed, dblp, unpaywall, opencitations, garuda`) |
| Provider bisa search | 8 (tanpa `unpaywall`, `opencitations`) |
| Tool MCP | 28 |
| Route HTTP API | 32 |
| Route web UI | 4 (`/`, `/graph`, `/metrics`, `/history`) |
| Format ekspor terdaftar | 20 (`apa, bibtex, chicago, csiro, csl-apa, csl-chicago, csl-vancouver, csv, csv_bom, csv_header, csv_plain, endnote, harvard, isi, json, mla, ris, vancouver, xls, xls_plain`) |
| Test | 540 |

Diverifikasi dengan menjalankan `TOOL_NAMES`, `provider_names()`,
`search_provider_names()`, dan `FORMATTERS` dari `src/josc`.
