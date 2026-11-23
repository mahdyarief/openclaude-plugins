# 06 — Infrastruktur PoP8

Bagian yang tidak terlihat di menu utama tapi menentukan apakah aplikasi bisa
dipakai sehari-hari: penanganan CAPTCHA, cache, mode offline, dan pemulihan.

## Cache HTTP

PoP8 menyimpan respons HTTP per URL. Yang tersedia di UI:

- **Clear cache** untuk satu query (bukan hanya seluruh cache).
- **Cache info** — ukuran, tanggal, dan umur entri.
- **Retry operation from cache** — ulangi operasi memakai entri cache.

Cache ini bukan optimasi kosmetik: kuota Elsevier (Scopus) bersifat mingguan,
dan Google Scholar akan memblokir kalau dihitung terlalu sering.

## Mode offline

Kalau jaringan mati, PoP8 tetap membuka search yang sudah ada dan menyajikan
hasil dari cache. Tidak ada antrean request yang dijalankan belakangan —
operasi yang butuh jaringan akan gagal dengan pesan, bukan menggantung.

## Penanganan CAPTCHA Google Scholar

Dua backend jendela CAPTCHA:

| Backend | Catatan |
|---|---|
| IE CAPTCHA window | jalur lama, memakai kontrol Internet Explorer |
| WebView2 CAPTCHA window | jalur baru, butuh WebView2 Runtime |

Deteksi dilakukan dengan mencari penanda `gs_captcha_ccl` dan
`gsc_captcha_ccl` di respons. Setelah pengguna menyelesaikan CAPTCHA, request
diulang otomatis. Kalau sesi tetap gagal, PoP8 memberi opsi fallback.

## Rate limit dan fallback

- Peringatan saat mendekati ambang request per jam (ambang 1 jam).
- **WoS Lite fallback** — kalau sesi Web of Science gagal sign-in, query
  diarahkan ke endpoint Lite yang tidak butuh sesi penuh.
- **Scopus API key dialog** (`PoPWinScopusKeyDlg`) — kunci disimpan dan
  dipakai ulang; tanpa kunci, sumber Scopus tidak aktif.

## Pemulihan dan diagnostik

- **Crash recovery** — pesan "did not exit normally… restore last available
  search data" dan pemulihan search terakhir.
- **Diagnostic log** — bisa dibuka dari menu View/Help.
- **Check for Updates** — memeriksa versi baru dari server Harzing.
- **Internet Options** — jalan pintas ke pengaturan proxy Windows.

## Implikasi untuk journal-scout

journal-scout punya fondasi yang lebih rapi, tapi lebih sedikit fitur
operasional:

| Kapabilitas | PoP8 | journal-scout |
|---|---|---|
| Cache respons | per URL, bisa dibersihkan per query | `TTLCache` 300 s / 1024 entri (`src/josc/cache.py:11-12`), `clear(prefix)` (`cache.py:72`) |
| Cache persisten | ya (file lokal) | Turso/libSQL opsional (`src/josc/store.py`), `TursoCache.clear(prefix)` (`store.py:218`) |
| Throttle per sumber | implisit lewat cache + peringatan | `MIN_INTERVALS` eksplisit (`src/josc/http.py:12-17`) |
| Retry/backoff | ya | `MAX_RETRIES=3`, `MAX_BACKOFF_SECONDS=60` (`src/josc/http.py:11,18`) |
| Mode offline | ya | ✅ `offline=true` + `stale: true` (`api.py:77-95`, `OfflineMiss` `api.py:40`) |
| CAPTCHA | ya (IE + WebView2) | tidak relevan (tidak ada scraping) |
| Crash recovery | ya | tidak relevan (server stateless) |
| Diagnostik kuota | peringatan ambang | ✅ `quota_report` semua provider (`quota.py:62`), `GET /api/quota` (`api.py:557`) |

Status gap, urut prioritas:

1. ~~**Cache hit/miss yang bisa diinspeksi**~~ — **✅ selesai.**
   `TTLCache.stats()` (`cache.py:80`) mengembalikan `ttl, entries,
   max_entries, hits, misses, sets, evictions, expired, hit_rate`;
   `_cache_stats()` (`api.py:139`) menyisipkannya ke `GET /api/health`
   (`api.py:204`) sebagai blok `cache`. `TursoCache.stats()` (`store.py:191`)
   menambahkan blok `store` lewat `_store_stats()` (`api.py:151`).
2. ~~**Mode offline eksplisit**~~ — **✅ selesai.** `offline=true` di endpoint
   baca menyajikan payload cache Turso dengan `stale: true`; cache kosong
   menghasilkan `503` lewat `OfflineMiss` (`api.py:40`).
3. ~~**Diagnostik kuota yang seragam**~~ — **✅ selesai.**
   `quota_report` (`quota.py:62`) mengembalikan limit terdokumentasi untuk
   sembilan sumber dengan bentuk respons yang sama; `GET /api/quota`
   (`api.py:557`) mengeksposnya, dan tool MCP `get_quota_status`
   (`server.py:346`) menyisipkan detail live Scopus sebagai
   `scopus_detail`.

4. ~~**Clear cache per query**~~ — **✅ selesai.** `TTLCache.clear(prefix)`
   (`cache.py:72`) dan `TursoCache.clear(prefix)` (`store.py:218`),
   diekspos lewat `POST /api/cache/clear` (`api.py:582`).

5. ~~**Cache info per query**~~ — **✅ selesai 2026-10-25.**
   `TTLCache.info(prefix, limit)` (`cache.py:102`) mengembalikan
   `key, size_bytes, age_seconds, ttl_remaining, expired` per entri;
   `TursoCache.info(prefix, limit)` (`store.py:463`) melakukan hal yang sama
   untuk tabel `query_cache` dengan `expires_in_seconds`. Keduanya diekspos
   lewat `GET /api/cache/info` (`api.py:639`) sebagai
   `{"memory": [...], "store": [...]}`.

6. ~~**Retry operation from cache**~~ — **✅ selesai 2026-10-25.**
   `TursoCache.replay_search(id)` (`store.py:443`) menyajikan ulang
   `results` tersimpan dengan `stale: true` tanpa menyentuh jaringan;
   route `GET /api/searches/{id}/replay` (`api.py:716`), tombol
   "Retry from cache" per baris riwayat di `history.tsx:544`.

**Sisa yang masih terbuka:** ukuran/umur baris riwayat kini ikut dikirim
(`size_bytes`, `age_seconds` di `list_searches`, `store.py:279`) dan
ditampilkan di UI (`history.tsx:563`), tetapi belum ada endpoint untuk
mengubah TTL atau memeriksa cache per provider secara terpisah.

Yang **tidak** perlu ditiru: CAPTCHA dan crash recovery. Keduanya ada karena
PoP8 adalah aplikasi desktop yang melakukan scraping; journal-scout memakai
API resmi dan berjalan sebagai server.
