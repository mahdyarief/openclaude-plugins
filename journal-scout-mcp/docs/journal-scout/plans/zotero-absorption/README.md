# Zotero Absorption — Implementation Plans (Index)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Menyerap fitur Zotero 10.0.6 yang relevan ke journal-scout-mcp (`josc`) sebagai enam irisan kerja mandiri, masing-masing menghasilkan perangkat lunak teruji yang bisa dirilis sendiri.

**Architecture:** Setiap irisan adalah satu file plan yang berdiri sendiri dengan siklus TDD-nya sendiri. Urutan eksekusi ditentukan tabel di bawah; tidak ada irisan yang bergantung pada irisan lain kecuali yang dinyatakan eksplisit di blok `Interfaces: Consumes`. Semua perubahan menyentuh modul yang sudah ada di `src/josc/`; tidak ada restrukturisasi besar.

**Tech Stack:** Python ≥3.10, `mcp>=1.0,<2`, `httpx>=0.27`, `beautifulsoup4>=4.12`, `lxml>=5.0`, Starlette (extra `web`), pytest ≥8 dengan `asyncio_mode = "auto"`, ruff (`E4,E7,E9,F`).

## Global Constraints

- Python minimum `>=3.10`; jangan memakai sintaks 3.11+ seperti `Self` atau `tomllib`.
- Dependensi runtime baru hanya boleh ditambahkan bila benar-benar diperlukan, dan setiap penambahan wajib beralasan di file plan yang memintanya.
- Tidak boleh ada panggilan jaringan nyata di dalam test. Semua test memakai fake object atau `httpx.MockTransport`.
- Semua test dijalankan dari root `journal-scout-mcp`; `pythonpath = ["src"]` sudah dikonfigurasi di `pyproject.toml`.
- Gaya kode mengikuti `ruff select = ["E4","E7","E9","F"]`; tidak boleh ada nama tak terdefinisi atau import tak terpakai.
- Backward compatibility: field publik `Paper.is_retracted` tidak boleh dihapus atau diubah tipenya.
- Setiap task berakhir dengan satu commit terpisah; jangan menggabungkan dua task dalam satu commit.
- Semua teks kode, komentar, dan nama identifier ditulis dalam bahasa Inggris; hanya dokumen plan ini yang berbahasa Indonesia.

## Peta irisan

| # | File | Prioritas | Dampak | Ketergantungan |
|---|---|---|---|---|
| 1 | [01-dedup-guards.md](01-dedup-guards.md) | A | Tinggi — menghilangkan penggabungan duplikat palsu | — |
| 2 | [02-retraction-enrichment.md](02-retraction-enrichment.md) | A | Tinggi — peringatan sitasi pada karya yang ditarik | — |
| 3 | [03-csl-citations.md](03-csl-citations.md) | A | Sedang — gaya sitasi baru tanpa menulis formatter | 02 (opsional) |
| 4 | [04-pdf-recognition.md](04-pdf-recognition.md) | B | Sedang — input paper dari PDF lokal | — |
| 5 | [05-saved-search-alerts.md](05-saved-search-alerts.md) | B | Sedang — pemantauan literatur berkelanjutan | — |
| 6 | [06-fulltext-search.md](06-fulltext-search.md) | B | Rendah–Sedang — pencarian teks pada korpus tersimpan | 04 (opsional) |
| 7 | [07-not-absorbing.md](07-not-absorbing.md) | C | — | keputusan eksplisit |

## Bukti dari Zotero 10.0.6

Artefak yang diperiksa berada di `D:\Github\agent-workspace\_zotero_extract\` (hasil ekstraksi `7zS.sfx.exe` → `core\app\omni.ja`). Setiap klaim di plan merujuk salah satu dari ini:

| Sumber Zotero | Yang diambil |
|---|---|
| `omni/chrome/content/zotero/xpcom/duplicates.js:332-382` | Guard duplikasi: DOI mismatch, ISBN mismatch, selisih tahun > 1, aturan kreator |
| `omni/chrome/content/zotero/xpcom/retractions.js:1048-1160` | 111 kategori alasan Retraction Watch + `getReasonDescription()` |
| `omni/chrome/content/zotero/xpcom/retractions.js:31-33` | Flag `FLAG_NORMAL`, `FLAG_HIDDEN`, `FLAG_NO_CITATION_WARNING` |
| `omni/chrome/content/zotero/xpcom/recognizeDocument.js` | Pengenalan metadata dari dokumen PDF |
| `omni/chrome/content/zotero/xpcom/fulltext.js` | Indeks teks penuh dan pencarian |
| `omni/chrome/content/zotero/xpcom/feedReader.js` | Model feed untuk pemantauan berkala |

## Protokol eksekusi

1. Pilih satu file plan. Jangan mengerjakan dua file sekaligus.
2. Kerjakan task secara berurutan di dalam file itu; setiap task harus hijau sebelum lanjut.
3. Jalankan seluruh suite sebelum menutup file plan: `pytest -q`.
4. Setelah semua task di satu file selesai, perbarui `docs/journal-scout/01-current-state.md` sesuai aturan pemeliharaan di `docs/journal-scout/README.md`.
5. Lanjut ke file berikutnya sesuai urutan tabel.
