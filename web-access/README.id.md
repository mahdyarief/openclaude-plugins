# web-access

<img src=".claude-plugin/icon.png" alt="" width="96" align="right">

[English](README.md) · [Changelog](CHANGELOG.md) · Lisensi MIT · [![test](https://github.com/mahdyarief/web-access/actions/workflows/test.yml/badge.svg)](https://github.com/mahdyarief/web-access/actions/workflows/test.yml)

Server [MCP](https://modelcontextprotocol.io) lokal tanpa dependensi, dikemas sebagai plugin Claude Code, yang memberi agen AI akses web:

- **Pencarian web** lewat [Exa](https://exa.ai) dan [Tavily](https://tavily.com). Bisa otomatis pindah ke provider lain saat gagal, atau menggabungkan hasil keduanya dengan *rank fusion*. Mendukung filter domain, waktu, dan kategori, jawaban AI, serta snippet ringkas.
- **Rotasi API key** untuk kedua provider. Key yang kena rate limit atau kuotanya habis diistirahatkan sementara.
- **Baca web sebagai Markdown**: link, tabel, dan blok kode tetap utuh. Cari bagian yang relevan di halaman panjang dengan `find`, baca beberapa URL sekaligus, dan PDF/halaman JavaScript tetap terbaca lewat Tavily Extract atau Exa. Tavily Map/Crawl untuk membaca satu situs.
- **Aman secara default**: alamat jaringan internal/privat ditolak (termasuk trik DNS rebinding), ukuran unduhan dibatasi, tanpa telemetri.
- **GitHub**: cari repo, kode, issue, commit, dan topik, lalu baca README, file, atau isi folder sebuah repo (`github_read`).
- **Anggaran harian** opsional untuk kredit Tavily dan biaya Exa.

Langsung jalan tanpa setup apa pun, karena Exa bisa dipakai **tanpa key**. Tavily opsional, dan menambahkan pencarian berita/finansial, jawaban AI, filter waktu dan domain yang resmi, serta ekstraksi PDF.

> Dokumen ini ringkasan. Referensi lengkap semua parameter ada di [README bahasa Inggris](README.md#tools-reference).

## Kebutuhan

- **Node.js 18.17 atau lebih baru** di `PATH`. Cek dengan `node -v`. Tidak perlu `npm install`.
- **Claude Code**, atau client MCP lain yang mendukung server stdio.
- Opsional: key [Tavily](https://app.tavily.com), key [Exa](https://dashboard.exa.ai), dan [GitHub CLI](https://cli.github.com) (`gh auth login`) untuk pencarian kode GitHub.

Bisa dipakai di Windows, macOS, dan Linux.

## Instalasi

### Plugin Claude Code (disarankan)

```
/plugin marketplace add mahdyarief/web-access
/plugin install web-access@mahdyarief
```

Di Claude Code 2.1.275 ke atas, cukup satu perintah:

```
/plugin install web-access --marketplace mahdyarief/web-access
```

Saat instalasi, Claude Code menanyakan opsi berikut. **Semuanya opsional**:

| Opsi | Keterangan |
|---|---|
| **Tavily API keys** | Key `tvly-...`, pisahkan dengan koma. Key dirotasi otomatis. |
| **Exa API keys** | Pisahkan dengan koma. Kosongkan untuk memakai Exa tanpa key. |
| **Default search provider** | `auto` (default), `exa`, `tavily`, atau `both`. |

Key disimpan di penyimpanan kredensial OS, bukan di `settings.json`, dan tidak pernah lewat chat. Untuk mengubahnya, jalankan `/plugin configure web-access@mahdyarief` lalu restart Claude Code.

Lewat terminal:

```bash
claude plugin marketplace add mahdyarief/web-access
claude plugin install web-access@mahdyarief
echo '{"tavily_api_keys":"tvly-aaa,tvly-bbb"}' | claude plugin configure web-access@mahdyarief --values-stdin
```

Plugin ini berisi:
- **MCP server** `web-access` dengan semua tool di bawah
- skill **`web-research`**: panduan agar Claude memilih tool dan mode yang tepat
- skill **`/web-access:research <pertanyaan>`**: riset bertahap dengan sumber, yaitu memecah pertanyaan, mencari dengan beberapa query, membaca sumber terbaik, cek silang, lalu menjawab dengan sitasi
- skill **`/web-access:setup`**: mengatur key, mengecek status, dan mendiagnosis masalah

### Client MCP lain

```json
{
  "mcpServers": {
    "web-access": {
      "command": "node",
      "args": ["/path/lengkap/web-access/server.js"],
      "env": { "TAVILY_API_KEYS": "tvly-aaa,tvly-bbb" }
    }
  }
}
```

## Mulai cepat

Setelah terpasang, tinggal minta ke Claude:

- *"Apa yang baru di rilis Node.js terakhir?"*: `web_search` dengan `recency`
- *"Baca https://example.com/docs lalu ringkas bagian autentikasinya"*: `web_get_contents` dengan `find: "auth"`
- *"Bandingkan tiga halaman harga ini"*: `web_get_contents` dengan `urls: [...]`
- *"Halaman apa saja yang ada di docs.tavily.com soal API?"*: `web_map`
- *"Baca semua halaman API reference situs dokumentasi ini"*: `web_crawl` dengan `selectPaths`
- *"Cari repo MCP server populer yang ditulis dengan TypeScript, lalu tampilkan README yang terbaik"*: `github_search`, lalu `github_read`
- *"Riset Bun vs Deno, beri jawaban singkat dan sumbernya"*: `web_search` dengan `queries: [...]`, `provider: "both"`, dan `includeAnswer: true`
- `/web-access:research Apakah Bun sudah siap produksi di 2026?`: alur riset lengkap dengan sitasi

Untuk cek konfigurasi, jalankan `/web-access:setup` atau minta *"jalankan web_access_status"*.

## Daftar tool

| Tool | Fungsi | Butuh key? |
|---|---|---|
| `web_search` | Pencarian web: `query` atau `queries` (maks. 5, paralel lalu digabung), `numResults` (1–10), `site`, `excludeSite`, `recency`, `startDate`/`endDate`, `category`, `provider`, `includeAnswer`, `maxCharsPerResult`, `maxPerDomain`, `fresh` | Tidak |
| `web_search_exa` | Pencarian **selalu** lewat Exa: `category`, `type` (auto/lite/deep), filter yang sama | Tidak (filter resmi butuh key Exa) |
| `web_search_tavily` | Pencarian Tavily: `topic` (general/news/finance), `searchDepth`, `includeAnswer`, `numResults` (1–20) | **Tavily** |
| `web_get_contents` | Isi halaman sebagai Markdown: `url` atau `urls` (maks. 10), `find` (hanya bagian yang relevan), `format` (`markdown`/`text`), `maxChars`, `offset` | Tidak (PDF butuh key Tavily atau Exa) |
| `web_extract_tavily` | Ekstrak hingga 20 URL sekaligus | **Tavily** |
| `web_map` | Daftar URL sebuah situs (tanpa isi): `limit`, `maxDepth`, `selectPaths`, `excludePaths`, `instructions` | **Tavily** |
| `web_crawl` | Crawl situs dan ambil isi banyak halaman sekaligus: `limit` (1–50), `maxCharsPerPage` | **Tavily** |
| `github_read` | Baca README, file, atau isi folder repo GitHub: `repo` (`owner/repo` atau URL github.com), `path`, `ref`, `find` | Tidak (repo privat butuh `GITHUB_TOKEN`) |
| `web_access_status` | Status key (disamarkan), masa istirahat, **sisa kredit Tavily**, pemakaian hari ini vs anggaran, cache | Tidak |
| `github_search` | Cari repo, issue, kode, commit, topik di GitHub | Tidak (cari kode butuh `gh auth login`) |

Semua tool pencarian, ekstraksi, map, dan crawl menerima `fresh: true` untuk melewati cache.

- **`category`** (Exa): `news`, `publication` (paper/artikel), `company`, `personal site` (blog), `financial report`, `people`. Saat fallback ke Tavily, `news` dan `financial report` dipetakan ke topic `news` dan `finance`.
- **`includeAnswer`**: menambahkan jawaban AI dari Tavily dan/atau Exa `/answer` (masing-masing butuh key). Di mode `both`, kedua jawaban ditampilkan supaya bisa dicek silang.
- **`maxCharsPerResult`**: panjang snippet per hasil (default 1200, 100–10000).
- **`queries`**: beberapa query sekaligus, dijalankan paralel lalu digabung dengan rank fusion. Tiap hasil diberi label query mana saja yang menemukannya (`query 1, 3`).
- **`excludeSite`, `startDate`, `endDate`**: buang domain tertentu, dan batasi rentang tanggal (`YYYY-MM-DD`). Dikirim sebagai filter resmi ke Exa (dengan key) dan Tavily.
- **`maxPerDomain`**: maksimal hasil dari satu domain (default 3, `0` = tanpa batas, tidak berlaku kalau `site` diisi), supaya satu situs tidak memenuhi daftar.
- **`find`** di `web_get_contents`/`github_read`: hanya mengembalikan bagian yang menyebut teks itu, lengkap dengan `offset` dan judul bagiannya. Jauh lebih hemat token untuk halaman panjang.

**Exa dengan key vs tanpa key:** dengan key, request lewat REST API `api.exa.ai`, sehingga filter domain/tanggal/kategori resmi, `type`, `/answer`, dan biaya per request tersedia. Tanpa key, request lewat endpoint MCP Exa yang anonim, dan filter hanya diselipkan ke teks query.

## Mode pencarian (`web_search`)

| Mode | Perilaku | Cocok untuk |
|---|---|---|
| `auto` | Exa dulu, Tavily kalau Exa gagal. Kalau Exa **tanpa key** dan query memakai `site`/`recency`, Tavily dipakai lebih dulu karena punya filter resmi. | Sehari-hari |
| `exa` | Hanya Exa. | Hemat kredit Tavily |
| `tavily` | Tavily, Exa kalau Tavily gagal. Tanpa key Tavily, langsung pakai Exa dan diberi catatan. | Berita, kejadian terbaru |
| `both` | Exa dan Tavily jalan paralel, lalu digabung dengan **Reciprocal Rank Fusion**. URL yang sama hanya tampil sekali. Hasil yang ditemukan keduanya (`via exa + tavily`) ditaruh paling atas, sisanya diselang-seling adil berdasarkan peringkat. | Riset, cek silang |

**Ambil isi halaman:**
- **Diambil langsung dulu** (gratis, maksimal 25 MB), lalu diubah ke **Markdown** oleh parser bawaan. Yang dibuang: menu, banner cookie, iklan, tombol share, elemen tersembunyi, link edit, dan penanda sitasi. Yang dipertahankan: heading, link, tabel, list bersarang, dan blok kode beserta bahasanya.
- **Cadangan:** Tavily Extract (kalau ada key Tavily), lalu Exa contents (kalau ada key Exa). Keduanya dipakai kalau pengambilan langsung gagal, kalau URL-nya PDF, atau kalau halamannya hampir kosong (biasanya dirender JavaScript).
- **Alamat internal** ditolak, dicek di setiap redirect dan sekali lagi saat socket tersambung. URL internal tidak pernah diteruskan ke Tavily atau Exa.
- **Cache:** dokumen disimpan utuh, jadi `offset` dan `find` tidak mengunduh ulang.

**Cache:**
- Hasil yang sukses disimpan di memori selama `cacheTtlSeconds` (default 600 detik). Error tidak pernah di-cache.
- Request identik yang sedang berjalan berbarengan cukup dikirim sekali.
- Dengan `"cachePersist": true`, hasil juga disimpan ke `web-access-cache.json` di samping file config, jadi bisa dipakai lagi di sesi berikutnya.

## Konfigurasi

Key diambil dari sumber pertama yang berisi key, terpisah untuk tiap provider:

1. **Env / pengaturan plugin**: `TAVILY_API_KEYS` dan `EXA_API_KEYS` (dipisah koma).
2. **File config**: `~/.openclaude/web-access.json`. Lokasinya bisa diganti lewat `WEB_ACCESS_CONFIG`.
3. **File lama**: `~/.openclaude/exa_keys.json` dan `~/.openclaude/tavily_keys.json`.

```json
{
  "provider": "auto",
  "cacheTtlSeconds": 600,
  "exa":    { "keylessFallback": true, "timeoutMs": 45000, "keys": [] },
  "tavily": { "timeoutMs": 45000, "keys": ["tvly-..."] },
  "fetch":  { "allowPrivateNetwork": false, "maxBytes": 26214400 },
  "cachePersist": false
}
```

| Setting | Default | Arti |
|---|---|---|
| `provider` | `auto` | Mode default `web_search`. |
| `cacheTtlSeconds` | `600` | Masa simpan cache. `0` mematikan cache. |
| `exa.keylessFallback` | `true` | Kalau semua key Exa ditolak, dicoba sekali lagi tanpa key. |
| `*.timeoutMs` | `45000` | Batas waktu total satu request, untuk semua key sekaligus. |
| `fetch.allowPrivateNetwork` | `false` | Izinkan `web_get_contents` membaca localhost/jaringan privat (misalnya dokumentasi lokal). |
| `fetch.maxBytes` | `26214400` | Batas ukuran unduhan langsung (25 MB). |
| `cachePersist` | `false` | Simpan cache ke disk dan pakai lintas sesi. |
| `tavily.dailyCreditBudget` | tidak ada | Anggaran harian dalam kredit Tavily. |
| `exa.dailyBudgetUsd` | tidak ada | Anggaran harian Exa dalam dolar. |
| `tavily.keyless` | `false` | Opt-in: pakai mode Tavily tanpa key untuk search/extract. Jatah hariannya kecil per IP. Map dan crawl tetap butuh key. |

**Anggaran harian:**
- **Cara menghitung:** pemakaian diambil dari angka yang dilaporkan API (`usage.credits` dari Tavily, `costDollars` dari Exa), jadi akurat. Disimpan di file status, sehingga berlaku bersama untuk semua sesi.
- **Kalau anggaran habis:** request ke provider itu ditolak sampai pukul 00:00 UTC, dan `web_search` otomatis pindah ke provider lain.
- **Mengecek:** pemakaian hari ini terlihat di `web_access_status`.

File ini dibaca ulang otomatis setiap kali berubah, jadi tidak perlu restart. Contoh lengkapnya ada di [`web-access.example.json`](web-access.example.json).

**File status:** masa istirahat key dan pemakaian hari ini disimpan di `web-access-state.json`, **di folder yang sama dengan file config** (default `~/.openclaude/web-access-state.json`). Dengan begitu tetap berlaku setelah restart dan dipakai bersama oleh beberapa sesi. Isinya hanya sidik jari (SHA-256) key, **bukan key-nya**. File ini biasa, tidak terikat client MCP tertentu. Pindahkan dengan `WEB_ACCESS_STATE_FILE=/path/file.json`, atau `WEB_ACCESS_STATE_FILE=off` untuk menyimpan di memori saja.

## Rotasi key dan masa istirahat

Setiap request mulai dari key berikutnya (round-robin). Key yang ditolak langsung diganti, lalu diistirahatkan:

| Status | Arti | Diistirahatkan |
|---|---|---|
| 429 | Rate limit | 1 menit, atau sesuai header `Retry-After` (maks. 1 jam) |
| 402 / 432 / 433 | Kredit atau kuota habis | 24 jam |
| 401 | Key tidak valid | 6 jam |

**403 tidak membuat key diistirahatkan**, karena artinya "URL tidak didukung" atau konten dilarang, bukan masalah key.

Error jaringan dan 5xx juga membuat request mencoba key berikutnya. Error lain (misalnya 400) langsung gagal supaya key tidak terbuang. Semua percobaan berbagi satu batas waktu, jadi request tidak menggantung sampai bermenit-menit.

## Biaya kredit

- Mode `auto`/`exa`: 1 request Exa (gratis kalau tanpa key). Tavily hanya terpakai saat Exa gagal.
- Mode `both`: 1 request Exa ditambah 1 pencarian Tavily.
- `includeAnswer`: jawaban Tavily sudah termasuk dalam pencarian. Exa `/answer` menambah 1 request (kalau ada key Exa).
- `web_search_tavily`: `basic` 1 kredit, `advanced` 2 kredit.
- `web_extract_tavily`: 1 kredit per 5 URL (basic). `web_map`: 1 kredit per 10 halaman. `web_crawl`: map ditambah extract (10 halaman basic ≈ 3 kredit).
- Angka bisa berubah, cek [dokumentasi kredit Tavily](https://docs.tavily.com/documentation/api-credits). Pemakaian sebenarnya terlihat di `web_access_status`.
- Pencarian yang diulang dan sudah ada di cache tidak memakai kredit.

## Privasi dan keamanan

- Query pencarian dikirim ke Exa dan/atau Tavily. Halaman yang dibaca diambil **langsung dari komputer Anda**, atau lewat Tavily Extract kalau cadangannya dipakai.
- **Tidak ada telemetri.** Satu-satunya file yang ditulis adalah file status masa istirahat, yang berisi sidik jari, bukan key. Cache hanya di memori.
- **Proteksi SSRF:** `web_get_contents` menolak `localhost`, rentang privat dan link-local (termasuk alamat metadata cloud `169.254.169.254`), host `.local`/`.internal`, dan nama host yang resolve ke alamat tersebut. Pengecekan diulang di setiap redirect, dan sekali lagi pada IP yang benar-benar disambungkan oleh socket, sehingga trik DNS rebinding tidak bisa menyelinap.
- Key tidak pernah ditulis ke log. `web_access_status` hanya menampilkan key yang disamarkan.
- File config berupa teks biasa. Jangan pernah di-commit. Kalau key bocor (ke chat, log, atau commit), ganti (rotate) di dashboard provider.

## Troubleshooting

| Gejala | Penyebab dan solusi |
|---|---|
| `web-access` tidak muncul atau gagal di `/mcp` | Node.js belum terpasang atau versinya di bawah 18.17. Cek `node -v`, lalu restart Claude Code. |
| `No Tavily API keys configured` | Tavily opsional. Pakai `web_search` (Exa tanpa key), atau tambahkan key lewat `/plugin configure web-access@mahdyarief`. |
| Key sudah diisi tapi status masih kosong | Restart Claude Code setelah `/plugin configure`. Pastikan juga key Tavily diawali `tvly-`. |
| `All Tavily keys are cooling down` | Semua key kena limit. Cek sisa waktunya di `web_access_status`, sementara pakai `provider: "exa"`, atau tambah key. |
| `Exa error 429` tanpa key | Batas Exa untuk pemakaian tanpa key tercapai. Tambahkan key Exa atau Tavily. |
| `refusing to fetch internal address …` | Proteksi SSRF. Untuk membaca dokumentasi lokal/intranet, set `"fetch": {"allowPrivateNetwork": true}`. |
| `Tavily error 403` di map/crawl | URL itu tidak didukung Tavily. Pakai `web_get_contents` per halaman. |
| `request timed out` | Jaringan atau provider lambat. Ulangi, atau naikkan `timeoutMs`. |
| PDF tidak bisa dibaca | Tambahkan key Tavily atau Exa. |
| `Daily Tavily budget reached` / `Daily Exa budget reached` | Anggaran harian habis. Reset pukul 00:00 UTC. Naikkan anggarannya, atau biarkan `web_search` memakai provider lain. |
| Beberapa hasil dari satu situs tidak muncul | `maxPerDomain` (default 3) menyembunyikannya, dan jumlahnya disebutkan di catatan hasil. Pakai `maxPerDomain: 0` atau `site`. |
| `GitHub API requires authentication` | Pencarian kode butuh login. Jalankan `gh auth login` atau set `GITHUB_TOKEN`. |
| Hasil terasa usang | Pakai `fresh: true`, atau set `cacheTtlSeconds: 0`. |

## Update dan uninstall

```
/plugin marketplace update mahdyarief
/plugin update web-access@mahdyarief
```

Restart Claude Code setelah update. Untuk menghapus plugin:

```
/plugin uninstall web-access@mahdyarief
/plugin marketplace remove mahdyarief
```

File config, status, dan cache Anda (`~/.openclaude/web-access*.json`) tidak ikut dihapus.

## Pengembangan

```bash
npm test                    # semua respons API dipalsukan: tidak butuh internet maupun key
claude plugin validate .
```

Untuk merilis versi baru: naikkan `version` di `.claude-plugin/plugin.json` **dan** `package.json`, tambahkan catatan di `CHANGELOG.md`, jalankan tes, lalu commit dan push. Struktur file proyek dijelaskan di [README bahasa Inggris](README.md#project-structure).

## Lisensi

[MIT](LICENSE) © mahdyarief
