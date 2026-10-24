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
| Cache respons | per URL, bisa dibersihkan per query | `TTLCache` 300 s / 1024 entri (`src/josc/cache.py:11-12`) |
| Cache persisten | ya (file lokal) | Turso/libSQL opsional (`src/josc/store.py`) |
| Throttle per sumber | implisit lewat cache + peringatan | `MIN_INTERVALS` eksplisit (`src/josc/http.py:12-17`) |
| Retry/backoff | ya | `MAX_RETRIES=3`, `MAX_BACKOFF_SECONDS=60` (`src/josc/http.py:11,18`) |
| Mode offline | ya | tidak ada — kegagalan langsung jadi `ProviderError` |
| CAPTCHA | ya (IE + WebView2) | tidak relevan (tidak ada scraping) |
| Crash recovery | ya | tidak relevan (server stateless) |
| Diagnostik kuota | peringatan ambang | tool `get_quota_status` (Scopus saja) |

Gap yang layak ditutup, urut prioritas:

1. **Cache hit/miss yang bisa diinspeksi** — tambah metrik di `Fetcher`
   (jumlah hit, miss, entri, umur) dan ekspos lewat `GET /api/health` yang
   sudah ada (`src/josc/api.py:279`).
2. **Mode offline eksplisit** — flag yang membuat pencarian hanya membaca
   cache dan mengembalikan penanda `stale: true`, alih-alih error.
3. **Diagnostik kuota yang seragam** — `get_quota_status` saat ini hanya
   Scopus; Semantic Scholar dan OpenAlex juga punya limit yang perlu
   dilaporkan dengan bentuk respons yang sama.

Yang **tidak** perlu ditiru: CAPTCHA dan crash recovery. Keduanya ada karena
PoP8 adalah aplikasi desktop yang melakukan scraping; journal-scout memakai
API resmi dan berjalan sebagai server.
