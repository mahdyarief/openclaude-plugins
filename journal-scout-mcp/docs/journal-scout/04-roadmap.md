# 04 — Roadmap Pengembangan

Dokumen hidup. Urutan di bawah disusun berdasarkan rasio dampak/biaya, bukan
berdasarkan kebaruan. Setiap fase harus bisa dikerjakan dan dirilis sendiri.

Referensi: gap lengkap di [`03-gap-analysis.md`](03-gap-analysis.md).

---

## Fase 1 — Buka fitur yang sudah ada (P0) — ✅ 2026-10-24

Tidak ada fitur baru yang perlu dirancang. Semua mesinnya sudah ada.

1. ~~**Wire-up ekspor.** Tool MCP `export_results` + `POST /api/export`
   memanggil `format_papers` (`src/josc/exporters.py:438`).~~ ✅
2. ~~**Tambah format murah.** `endnote`, `isi`, dan CSV+header/Excel (BOM).~~ ✅
3. ~~**Tambah gaya sitasi.** `apa`, `chicago`, `harvard`, `vancouver`.~~ ✅
4. ~~**Test.** Perluas `tests/test_exporters.py`.~~ ✅ (18 test)

Kriteria selesai: **terpenuhi** — 11 format, bisa diakses lewat tool MCP dan
route HTTP.

---

## Fase 2 — Paritas metrik (P1) — ✅ 2026-10-24

1. ~~**Metrik baru** di `compute_metrics` (`src/josc/graph.py:204`):
   `e_index`, `AWCR`, `AW_index`, `AWCRpA`, `hc_index`, `hI_index`,
   `hI_norm`, `hm_index`.~~ ✅
2. ~~**Rasio** `cites_year`, `cites_paper`, `cites_author`, `papers_author`,
   `authors_paper`.~~ ✅
3. ~~**Mode report** `basic`/`extended` lewat parameter `mode`.~~ ✅
4. ~~**UI.** `web/src/routes/metrics.tsx` menampilkan kelompok basic/extended.~~ ✅

Kriteria selesai: **terpenuhi** — 22 test metrik lulus, termasuk pemisahan
tegas `hI_index` (Batista), `hI_norm`, dan `hm_index` (Schreiber).

---

## Fase 3 — Filter terstruktur (P1) — ✅ 2026-10-24

1. ~~**Parameter baru** `author`, `venue` di `search_all`
   (`src/josc/aggregator.py:102`).~~ ✅
2. ~~**Mapping per provider**: Crossref `query.author`, OpenAlex
   `_filters(...)`, Scopus `AUTH()`, Semantic Scholar `venue`.~~ ✅
3. ~~**Capability flag** `supports_filters` di `ProviderBase`
   (`src/josc/providers/base.py:20-21`), dan laporkan filter yang diabaikan
   di respons.~~ ✅

Kriteria selesai: **terpenuhi** — `filters_applied` / `filters_ignored`
dikembalikan di respons. Catatan: `tech_only` belum punya capability flag.

---

## Fase 4 — Provider PubMed (P1) — ✅ 2026-10-24

1. ~~**Provider baru** `src/josc/providers/pubmed.py`.~~ ✅
2. ~~**Dua tahap**: `esearch` untuk PMID, lalu `efetch` untuk metadata.~~ ✅
3. ~~**Daftarkan** di `_provider_classes()` (`providers/__init__.py`).~~ ✅
4. ~~**Test** dengan fixture XML E-utilities.~~ ✅ (4 test)

Kriteria selesai: **terpenuhi** — registry 9 provider / 7 searchable,
`search_provider_names()` memuat `pubmed`.

---

## Fase 5 — Persistensi dan observability (P2)

1. **Tabel `searches`** di `TursoStore` (`src/josc/store.py:52`).
2. **Endpoint** `GET /api/searches` (recent) dan `POST /api/searches`.
3. **Metrik cache** di `GET /api/health` (`src/josc/api.py:109`):
   hit, miss, entri, umur.
4. **Mode offline** `offline=true` → sajikan cache dengan `stale: true`.

Kriteria selesai: pengguna bisa mengulang pencarian lama tanpa mengetik ulang
query, dan bisa mendiagnosis cache tanpa membuka log.

---

## Yang tidak masuk roadmap

| Item | Alasan |
|---|---|
| Google Scholar scraping | tidak stabil, butuh CAPTCHA, risiko blokir |
| Web of Science | butuh lisensi institusi |
| Folder/trash berlapis | tidak cocok untuk MCP server |
| CAPTCHA handler | tidak relevan tanpa scraping |
| Microsoft Academic | sudah dihentikan |

---

## Aturan update dokumen ini

- Centang item yang selesai dengan tanggal, jangan hapus barisnya.
- Kalau sebuah item dibatalkan, pindahkan ke tabel "tidak masuk roadmap"
  beserta alasannya.
- Setelah fase selesai, perbarui `01-current-state.md` dan
  `03-gap-analysis.md` agar tidak ada klaim usang.

---

## Pola kerja paralel (multi-agent)

Fase 1–4 dirancang agar bisa dikerjakan bersamaan oleh beberapa agent.
Kuncinya **pembagian file yang tidak tumpang tindih**, bukan pembagian fase.

| Agent | Fase | File yang boleh disentuh |
|---|---|---|
| A | 1 — ekspor | `exporters.py`, `server.py`, `api.py`, `tests/test_exporters.py` |
| B | 2 — metrik | `graph.py`, `tests/test_graph.py`, `web/src/routes/metrics.tsx` |
| C | 4 — PubMed | `providers/pubmed.py` (baru), `providers/__init__.py`, `tests/test_providers/test_pubmed.py` |
| D | 3 — filter | `providers/base.py`, `aggregator.py`, `server.py`, 6 provider searchable, `tests/test_aggregator.py` |

Dua pasangan file memang dipakai bersama dan perlu penanganan khusus:

- **`server.py`** dipakai agent A (tool `export_results`) dan D (field
  `author`/`venue`). Keduanya menambah, tidak menghapus — aman selama
  masing-masing hanya menyisipkan baris.
- **`providers/__init__.py`** hanya agent C yang boleh menyentuh.

### Catatan penting soal worktree

`git worktree` **tidak dipakai** di repo ini karena restrukturisasi
`journal_scout_mcp/` → `src/josc/` masih belum di-commit. Worktree akan
meng-checkout versi lama dan agent akan bekerja di kode yang salah. Setelah
restrukturisasi di-commit, worktree baru aman dipakai.

### Verifikasi setelah agent selesai

1. `git diff --stat` — pastikan tidak ada file di luar daftar di atas.
2. `./.venv/Scripts/python.exe -m pytest -q` — seluruh suite harus lulus.
3. Smoke test: `export_results` mengembalikan string non-kosong;
   `compute_metrics(mode="extended")` mengembalikan superset dari `basic`;
   `search_provider_names()` memuat `pubmed`.
4. Perbarui `01-current-state.md` (jumlah tool, provider, metrik) dan
   `03-gap-analysis.md` (hapus item yang sudah selesai).
