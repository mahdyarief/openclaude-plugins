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

1. ~~**Metrik baru** di `compute_metrics` (`src/josc/graph.py:236`):
   `e_index`, `AWCR`, `AW_index`, `AWCRpA`, `hc_index`, `hI_index`,
   `hI_norm`, `hm_index`.~~ ✅
2. ~~**Rasio** `cites_year`, `cites_paper`, `cites_author`, `papers_author`,
   `authors_paper`.~~ ✅
3. ~~**Mode report** `basic`/`extended` lewat parameter `mode`.~~ ✅
4. ~~**UI.** `web/src/routes/metrics.tsx` menampilkan kelompok basic/extended.~~ ✅

Kriteria selesai: **terpenuhi** — 22 test metrik lulus, termasuk pemisahan
tegas `hI_index` (Batista), `hI_norm`, dan `hm_index` (Schreiber).

**Pelengkap 2026-10-24:** `mode` kini tersambung ke jalur publik —
`aggregator.compute_metrics(mode=...)` (`aggregator.py:356`), query param
`mode` di `GET /api/metrics` (`api.py:403`), schema tool MCP
(`server.py:192`), dan toggle Basic/Extended di `/metrics` yang memanggil
`fetchMetrics({ mode })` (`api.ts:80`). Test baru:
`tests/test_metrics_mode.py` (5 test, termasuk seam HTTP via TestClient).

---

## Fase 3 — Filter terstruktur (P1) — ✅ 2026-10-24

1. ~~**Parameter baru** `author`, `venue` di `search_all`
   (`src/josc/aggregator.py:114`).~~ ✅
2. ~~**Mapping per provider**: Crossref `query.author`, OpenAlex
   `_filters(...)`, Scopus `AUTH()`, Semantic Scholar `venue`.~~ ✅
3. ~~**Capability flag** `supports_filters` di `ProviderBase`
   (`src/josc/providers/base.py:24`), dan laporkan filter yang diabaikan
   di respons.~~ ✅

Kriteria selesai: **terpenuhi** — `filters_applied` / `filters_ignored`
dikembalikan di respons. `tech_only` menyusul punya capability flag sendiri
(`supports_tech_only`) pada 2026-10-24 — lihat Fase 5.

**Pelengkap 2026-10-24 (UI):** form pencarian di `web/src/routes/search.tsx`
kini mengekspos semua filter backend — `yearFrom`, `techOnly`, pemilihan
`selectedSources` lewat `toggleSource()`, dan `offset` untuk paginasi
(`search.tsx:46-58`, submit di `:117`). Respons filter ditampilkan sebagai
banner: `filters_ignored` di `:370-373` dan `filters_applied` per provider di
`:378-381`. `searchPapers` (`api.ts:41`) mengirim `tech_only` hanya saat
aktif, sehingga provider tanpa dukungan dilaporkan `ignored` alih-alih
menerima flag yang tidak dipahami.

---

## Fase 4 — Provider PubMed (P1) — ✅ 2026-10-24

1. ~~**Provider baru** `src/josc/providers/pubmed.py`.~~ ✅
2. ~~**Dua tahap**: `esearch` untuk PMID, lalu `efetch` untuk metadata.~~ ✅
3. ~~**Daftarkan** di `_provider_classes()` (`providers/__init__.py`).~~ ✅
4. ~~**Test** dengan fixture XML E-utilities.~~ ✅ (4 test)

Kriteria selesai: **terpenuhi** — registry 9 provider / 7 searchable,
`search_provider_names()` memuat `pubmed`.

---

## Fase 5 — Persistensi dan observability (P2) — ✅ 2026-10-24

1. ~~**Tabel `searches`** di `TursoStore`.~~ ✅ — `setup()` (`store.py:130-156`)
   membuat tabel `searches` + indeks `idx_searches_created`; `record_search()`
   (`store.py:218`) menulis dengan bound parameter, `list_searches()`
   (`store.py:264`) membaca `ORDER BY created_at DESC`.
2. ~~**Endpoint** `GET /api/searches` (recent).~~ ✅ — `searches()` handler
   (`api.py:191`); pencatatan otomatis lewat `_remember()`
   (`api.py:165-188`) di akhir setiap `GET /api/search` non-offline, jadi
   `POST /api/searches` tidak diperlukan.
3. ~~**Metrik cache** di `GET /api/health` (`src/josc/api.py:204`):
   hit, miss, entri, umur.~~ ✅ — `TTLCache.stats()` (`cache.py:80-92`) dan
   blok `cache` di respons health (`api.py:209`).
4. ~~**Mode offline** `offline=true` → sajikan cache dengan `stale: true`.~~ ✅
   — `OfflineMiss` (`api.py:40`), `_flag()` (`api.py:95`), `_cached(offline=)`
   (`api.py:77`) dipakai keempat endpoint baca; miss → `503` dengan
   `{"offline": true}`.
5. ~~**Telemetri `TursoCache`** di blok `store` health.~~ ✅ — `stats()`
   (`store.py:191`) + `_store_stats()` (`api.py:151`), `null` bila Turso mati.

Kriteria selesai: **terpenuhi** — pengguna bisa mengulang pencarian lama tanpa
mengetik ulang query (`/api/searches`), dan bisa mendiagnosis cache tanpa
membuka log (`cache` + `store` di `/api/health`).

**Pelengkap 2026-10-24 (UI ekspor):** hasil pencarian kini punya
`ExportMenu` (`web/src/components/ExportMenu.tsx`) dengan pilihan 11 format,
tombol Download (Blob + object URL) dan Copy (clipboard), dirender di
`search.tsx:361`. `exportPapers()`/`EXPORT_FORMATS` di `web/src/lib/api.ts:160-174`
memanggil `POST /api/export`; format tak dikenal → 400 dengan pesan error
dari server.

---

## Fase 6 — Related works + riwayat di UI (P2) — ✅ 2026-10-24

1. ~~**`supports_related`** di `ProviderBase` (`providers/base.py:20`),
   `True` hanya di OpenAlex (`providers/openalex.py:35`).~~ ✅
2. ~~**`OpenAlexProvider.related()`** (`openalex.py:189`) — baca
   `related_works`, lalu hidrasi batch
   `GET /works?filter=openalex_id:W1|W2|W3`.~~ ✅
3. ~~**`aggregator.get_related()`** (`aggregator.py:244`) + tool MCP
   `get_related_works` + `GET /api/related` (`api.py:329`) + flag
   `capabilities.related` di `/api/health` (`api.py:216`).~~ ✅
4. ~~**`/history`** (`web/src/routes/history.tsx`) membaca `GET /api/searches`
   dan menyediakan tombol Reload yang mengirim ulang query+sources+filters
   ke route `/`.~~ ✅

Kriteria selesai: **terpenuhi** — 24 tool MCP, 12 route HTTP, 4 route web UI,
242 test hijau, `uvx ruff check .` bersih, `npm run build` hijau.
*(Angka ini snapshot saat Fase 6 ditutup. Kondisi sekarang: 16 route HTTP dan
265 test — lihat Fase 7–8 di bawah.)*

---

## Fase 7 — Seleksi hasil dan laporan (P2) — ✅ 2026-10-25

Fokus: mengubah hasil pencarian dari daftar pasif menjadi bahan kerja.

1. ~~**Seleksi hasil di `/`.** Checkbox per baris + "select all", tombol
   "Uncheck 0 Cites" (buang paper tanpa sitasi), dan ekspor hanya baris
   terpilih. `ExportMenu` (`web/src/components/ExportMenu.tsx`) menerima
   `papers` dari state seleksi, bukan dari `results` penuh.~~ ✅
   Implementasi: `selectedIds: Set<string>` di `search.tsx`, key
   `${doi ?? title}-${index}`; tombol `select all`, `select cited`
   (`citation_count > 0`), dan `clear`. `PaperCard` menampilkan checkbox hanya
   bila prop `onToggle` diberikan, jadi kartu di tempat lain tidak berubah.
2. ~~**Formatter `metrics_csv`** di `exporters.py`.~~ ✅ — `format_metrics_csv`
   (`exporters.py:482`) dengan `_METRIC_LABELS` (`exporters.py:457`) berisi 20
   baris skalar berurutan, lalu tabel per tahun. **Deviasi dari rencana:**
   tidak didaftarkan di `FORMATTERS`/`EXPORT_FORMATS` karena payload-nya bukan
   daftar paper; eksposnya lewat route terpisah `GET /api/metrics/export`
   (`api.py:411`) dan tombol "Download CSV" di `/metrics`.
3. ~~**Tabel sitasi per tahun** di `/metrics`.~~ ✅ — `citations_by_year()`
   (`graph.py:204`) mengisi `by_year` (`graph.py:275`); komponen
   `CitationsByYearTable` di `metrics.tsx` merender Year/Papers/Citations/
   Cumulative tanpa request tambahan.

Kriteria selesai: **terpenuhi** — ekspor menghormati seleksi, CSV metrik bisa
diunduh, tabel per-tahun muncul dari payload yang sama.

**Bug yang ditemukan saat review dan diperbaiki:** label CSV memakai key
`awcr`/`aw_index` huruf kecil, padahal engine mengeluarkan `AWCR`/`AW_index`/
`AWCRpA`. Tiga baris hilang diam-diam di laporan extended. Dikunci oleh
`test_metrics_csv_labels_extended_keys_with_their_real_names` dan
`test_metrics_csv_round_trips_a_real_extended_metrics_payload`.

---

## Fase 8 — Gabung dan arsip pencarian (P2) — ✅ 2026-10-25

Fokus: alur kerja berulang di atas tabel `searches` yang sudah ada.

1. ~~**`POST /api/merge`** — dedup DOI-first lewat `merge_papers`.~~ ✅ —
   `merge()` (`api.py:460`). **Deviasi dari rencana:** body memakai
   `{"papers": [...]}` (bukan `paper_lists`) dan balasannya
   `{results, input_count, merged_count}`. Kunci asing diabaikan lewat
   `_papers_from_body` (`api.py:446`) supaya UI bisa mengirim balik objek
   paper apa adanya. Tombol `Merge selected` ada di `/history`.
2. ~~**`GET /api/searches/{id}/export`** — bundel arsip query + filter +
   sumber + hasil.~~ ✅ — `search_export()` (`api.py:482`) mengembalikan
   `{format: "josc-search-archive", version: 1, ...}`; `404` bila id tidak
   ada. Kolom `results` ditambahkan lewat migrasi `ALTER TABLE`
   (`store.py:154`) dan diisi `_remember()` saat hasil masih di tangan.
3. ~~**Impor arsip** — `POST /api/searches/import`.~~ ✅ —
   `search_import()` (`api.py:508`) menyimpan arsip sebagai baris baru dengan
   id segar, balas `{id, result_count}`.

Kriteria selesai: **terpenuhi** — dua pencarian bisa digabung tanpa duplikat;
satu pencarian lama bisa diunduh sebagai arsip mandiri dan dimuat kembali di
mesin lain. Baris riwayat lama tanpa `results` ditolak UI dengan pesan
eksplisit, bukan menghasilkan file kosong.

**Verifikasi E2E 2026-10-25:** 265 test lulus, `uvx ruff check src tests`
bersih, `npm run build` sukses (164 modul), smoke HTTP nyata untuk merge,
arsip round-trip, 404, CSV basic, dan CSV extended (baris AWCR terbukti
muncul).

---

## Milestone — Absorpsi PoP8 selesai — ✅ 2026-10-25

Seluruh fitur PoP8 yang bisa dipindahkan tanpa dependensi eksternal sudah
diimplementasikan. Semua 36 item di [`03-gap-analysis.md`](03-gap-analysis.md)
tertutup (P0, P1, P2). Tidak ada fase PoP8 yang tersisa.

**Di luar PoP8 (journal-scout melampaui):**

1. ~~**Provider Garuda** — `src/josc/providers/garuda.py`.~~ ✅ 2026-10-25 —
   pencarian artikel Indonesia via scraping HTML `div.article-item`, 10 test
   dengan fixture `tests/fixtures/garuda_search.html`. PoP8 tidak punya ini.
2. **Pengaya akreditasi Sinta** — rantai `garuda id → /journal/view/{id} →
   ISSN → Sinta S1..S6`, terbukti 8/10 pada prototype
   (`.proto/check_bridge.py`). Belum diimplementasikan; PoP8 tidak punya ini.

**Angka akhir terverifikasi (2026-10-25):** 10 provider / 8 searchable,
25 tool MCP, 27 route HTTP, 17 formatter, 372 test.

**Sisa = batasan eksternal, bukan pekerjaan tertunda:**

| Gap | Sifat |
|---|---|
| Google Scholar | tidak ada API resmi, butuh CAPTCHA |
| Web of Science | butuh lisensi institusi |
| Lens.org | butuh token API (gratis, tapi harus daftar) — satu-satunya sumber PoP8 yang masih feasible |
| Field-tag query (`TS=`, `TI=`, `AU=`) | sintaksis tidak diminta; `query.py` membuang operator tak didukung |
| Cache TTL per provider | gap infrastruktur kecil |

---

## Fase 9 — Hasil tabular + drawer detail — ✅ 2026-10-25

Fokus: hasil pencarian harus bisa dibandingkan dan ditelusuri, bukan sekadar
daftar kartu yang di-scroll.

1. ~~**Tabel hasil yang bisa di-sort.**~~ ✅ — `PaperTable`
   (`web/src/components/PaperTable.tsx`) menggantikan grid kartu di `/`.
   Kolom: checkbox, Year, Title, Authors, Venue, Cited, Source. Header sticky
   dan bisa diklik (`aria-sort`), dengan urutan awal cerdas per kolom
   (teks naik, angka turun). Baris membawa `PaperRow = {paper, key}` yang
   dihitung dari urutan asli, jadi checkbox tidak desync setelah sorting.
2. ~~**Drawer detail di kanan.**~~ ✅ — `PaperDrawer`
   (`web/src/components/PaperDrawer.tsx`): panel 520px, tutup lewat tombol,
   backdrop, atau Escape. Menampilkan semua field yang ada di respons
   pencarian (authors, year, venue, type, citations, sources, OA, DOI, ids)
   plus abstrak yang diambil on-demand lewat `/api/paper`. Footer menyediakan
   Download PDF (`pdf_url`), fallback "Open source page" (`url`), Copy DOI,
   dan tautan Citation graph.

**Bug yang ditemukan saat verifikasi live dan diperbaiki:** tombol "Fetch
abstract" menampilkan abstrak paper yang salah. Akar masalahnya
`aggregator.get_paper` menanyakan identifier yang sama ke **semua** provider,
dan `SemanticScholarProvider` memetakan setiap string digit ke `CorpusId:`,
sehingga id Garuda `6420654` cocok dengan paper Semantic Scholar yang tidak
berhubungan. Perbaikan:

- `GarudaProvider.get()` (`providers/garuda.py`) — mem-parse halaman detail
  Garuda (`h3.ui.header`, `a[href*='/author/view/']`, `.abstract-article`,
  link "Download Original"), sehingga id Garuda bisa di-resolve ke abstrak
  dan PDF-nya sendiri.
- `aggregator.get_paper(..., sources=...)` — parameter opsional yang membatasi
  provider yang dihubungi.
- `GET /api/paper?source=garuda` dan parameter `sources` di tool MCP
  `get_paper` meneruskan pembatasan itu.
- `fetchPaper(identifier, source)` di `web/src/lib/api.ts`; drawer mengirim
  provider pemilik identifier (`identifierFor` mengembalikan pasangan
  identifier + sumber).

**Verifikasi:** 376 test lulus (4 test baru: `GarudaProvider.get()` mem-parse
fixture `garuda_detail.html`, scoping `get_paper`, dan wiring route
`/api/paper`). Live check pada server 8793: id Garuda `6420654` dengan
`source=garuda` mengembalikan paper Garuda yang benar (abstrak 642 karakter,
PDF `ysmk.org`, tanpa error), sedangkan tanpa `source` tetap mengembalikan
paper Semantic Scholar yang salah — membuktikan scoping bekerja.

**Tindak lanjut 2026-10-25 — panel relasi pindah ke drawer, `PaperCard` dihapus:**

`PaperCard.tsx` sudah tidak diimpor siapa pun sejak tabel menggantikan grid,
tetapi file itu masih memuat satu-satunya UI untuk Related works dan Citing
works. Sebelum menghapusnya, kemampuan itu dipindahkan ke `PaperDrawer`:

- `fetchRelations(kind, identifier, source, limit)` di `web/src/lib/api.ts`
  memanggil `/api/related` atau `/api/citations`; tipe `RelationResponse` di
  `web/src/lib/types.ts`.
- `PaperDrawer` mendapat state `openPanel`/`relationState`/`relations` plus
  guard `relationRequest` (request id) supaya respons lama tidak menimpa panel
  yang sudah diganti. Tombol "Related works" / "Citing works" dirender hanya
  bila identifier bisa di-resolve.
- **Bug yang sama ikut ditutup:** `/api/citations` dan `/api/related` dulu
  mem-fan-out identifier ke semua provider, jadi id Garuda/PubMed bisa memicu
  tebakan provider lain. `aggregator.get_citations`, `get_references`, dan
  `get_related` sekarang menerima `sources`; route meneruskan query param
  `source`, dan schema tool MCP ikut menerima `sources`.
- `web/src/components/PaperCard.tsx` dihapus (267 baris).

**Verifikasi tindak lanjut:** 380 test lulus (4 test baru: scoping
`get_citations`, scoping `get_related`, wiring route `/api/citations`, dan
wiring route `/api/related`; semuanya RED lebih dulu). `tsc --noEmit` bersih,
`npm run build` hijau (167 modul, `index-YbJzHhYI.js`), dan bundle yang
dihasilkan memuat "Related works" / "Citing works" tetapi tidak lagi memuat
"Find open-access copy" — penanda `PaperCard` benar-benar hilang.

---

## Fase 10 — Riwayat tidak redundan + load arsip — ✅ 2026-10-25

Fokus: mengulang pencarian yang sama tidak boleh menumpuk baris history, dan
hasil lama harus bisa dibuka tanpa memicu pencarian baru.

1. ~~**Upsert berbasis fingerprint.**~~ ✅ — `search_fingerprint()`
   (`src/josc/api/history.py`) menghitung SHA-256 dari query, sumber terurut,
   limit, rentang tahun, `tech_only`, offset, empat filter field, sort, dan
   order. `record_search()` (`store.py`) mencari `fingerprint` lebih dulu;
   bila ada, baris itu di-`UPDATE` (termasuk `created_at` dan `results`),
   bila tidak ada baris baru di-`INSERT`. Penulisan eksplisit (split,
   duplicate, import) tidak mengirim fingerprint sehingga tetap append.
   Migrasi menambah kolom `fingerprint TEXT` + indeks
   `idx_searches_fingerprint` lewat `ALTER TABLE` yang menelan error duplikat,
   jadi aman untuk database lama.
2. ~~**Tombol `Load cached results`.**~~ ✅ — `history.tsx` menavigasi ke
   `/?cached=<id>`; `validateSearch` route `/` (`web/src/router.tsx`)
   mendeklarasikan parameter `cached`, dan `loadCached()` di `search.tsx`
   memanggil `/api/searches/{id}/replay` lalu memetakan `ReplayResponse` ke
   `SearchResponse`. Tidak ada panggilan `/api/search`, jadi tidak ada baris
   history baru. Tombol `Retry from cache` yang lama tetap ada untuk melihat
   hasil di halaman `/history` sendiri.

**Verifikasi:** 390 test lulus (10 test baru: fingerprint stabil/order-
independent/berubah saat filter berubah, `_remember` meneruskan fingerprint,
upsert vs insert vs append, migrasi kolom, dan wiring route `/api/search`).
`tsc --noEmit` bersih, `npm run build` hijau (`index-Cu-ebtPr.js`), bundle
yang disajikan server 8793 memuat "Load cached results".

---

## Fase 11 — Hapus satu baris riwayat — ✅ 2026-10-25

Fokus: riwayat yang sudah tidak relevan harus bisa dibersihkan satu per satu,
tanpa menyentuh baris lain.

1. ~~**`TursoStore.delete_search()`.**~~ ✅ — `src/josc/store.py` melakukan
   `SELECT id FROM searches WHERE id = ?` lebih dulu; bila baris ada baru
   `DELETE FROM searches WHERE id = ?`. Mengembalikan `False` untuk id yang
   tidak dikenal sehingga route bisa membalas `404`.
2. ~~**`DELETE /api/searches/{search_id}`.**~~ ✅ — `search_delete`
   (`src/josc/api/cache_routes.py`) membalas `{"id", "deleted": true}` atau
   `{"error": "Search not found."}` dengan status `404`. Bila store tidak
   dikonfigurasi, balasannya error, bukan crash.
3. ~~**Tombol `Delete` per baris di `/history`.**~~ ✅ — `deleteRow()` meminta
   konfirmasi `window.confirm` lebih dulu, memanggil `deleteSearch()`
   (`web/src/lib/api.ts`), membuang id dari seleksi, menutup panel replay bila
   baris itu sedang ditampilkan, lalu me-refresh daftar. Varian `danger`
   ditambahkan ke `Button` (`web/src/components/ui.tsx`) supaya aksi destruktif
   terbedakan secara visual.

**Verifikasi:** 395 test lulus (5 test baru: `delete_search` menghapus baris,
`delete_search` melaporkan id asing tanpa `DELETE`, route membalas 200, route
membalas 404, dan route menolak saat store tidak ada; semuanya RED lebih
dulu). `tsc --noEmit` bersih, `npm run build` hijau
(`index-KGejPXsd.js`). Live check pada server 8793: `DELETE` untuk baris probe
mengembalikan `200 {"deleted": true}` dan jumlah baris turun 14 → 13; `DELETE`
untuk id asing mengembalikan `404 {"error": "Search not found."}`.

---

## Sisa gap setelah Fase 8

| Gap | Sifat |
|---|---|
| Terjemahan operator AND/OR/NOT per provider | keputusan produk — tiap API punya sintaksis berbeda dan sebagian tidak mendukungnya sama sekali |
| Sumber berlangganan (Web of Science, Scopus penuh) | keputusan bisnis — butuh lisensi institusi |
| Folder/trash berlapis | sengaja ditolak, lihat tabel di bawah |

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
