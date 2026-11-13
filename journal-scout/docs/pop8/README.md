# Harzing's Publish or Perish 8 — Referensi Fitur

Hasil reverse engineering `PoP8Setup.exe` (versi **8.19.5300.9483**).
Semua klaim di folder ini berasal dari resource UI asli `pop8win.exe`
(`RT_MENU`, `RT_STRING`, `RT_DIALOG`) dan string yang di-mine dari binary,
bukan dari dokumentasi resmi.

## Daftar dokumen

| File | Isi |
|---|---|
| [01-data-sources.md](01-data-sources.md) | 11 sumber data, varian, dan batasannya |
| [02-search-filters.md](02-search-filters.md) | Field filter, operator, dan batasan per sumber |
| [03-metrics.md](03-metrics.md) | 18 metrik bibliometrik dan definisinya |
| [04-export-formats.md](04-export-formats.md) | Format data, sitasi, report, dan arsip |
| [05-workflow-ui.md](05-workflow-ui.md) | Struktur menu, query tree, aksi artikel |
| [06-infrastructure.md](06-infrastructure.md) | Cache, offline mode, CAPTCHA, update |
| [07-query-engine-re.md](07-query-engine-re.md) | CLI `pop8query.exe`: 15 switch sumber, field query, format output, pesan error |

## Rantai unpack (untuk reproduksi)

```
PoP8Setup.exe (PE32 x86, 3.1 MB, SHA-256 0747a558…)
 ├─ .rsrc RT_TYPE_15 "rlzm" @ 398960, len 69777
 │    LZMA1 raw (lc=3 lp=0 pb=2, dict 512 KiB, tanpa end-marker)
 │    → resz container (393,293 B) → TinDel.exe (uninstall cleaner)
 └─ overlay @ 0x77400
      → tiz3 payload (2,632,920 B)
           LZMA1 raw dari offset 0x4D, dict 16 MiB
           → tzf3 archive (11,436,099 B)
                → 7 PE termasuk pop8win.exe (x86 + x64),
                  pop8query.exe, twux.exe, WebView2Loader.dll
```

Catatan: `lzma.decompress()` menolak stream ini karena tidak ada end-marker.
Pakai `lzma.LZMADecompressor(format=FORMAT_RAW, ...)`.

## Gap yang masih tersisa di journal-scout

Diperbarui 2026-10-25. Semua yang bisa ditutup tanpa dependensi eksternal sudah
dikerjakan; sisa di bawah ini adalah batasan nyata, bukan pekerjaan tertunda.

| Gap | Status | Alasan |
|---|---|---|
| Google Scholar | tidak diimplementasikan | tidak ada API resmi; butuh scraping/proxy, di luar roadmap |
| Web of Science | tidak diimplementasikan | butuh langganan institusi |
| Lens.org | tidak diimplementasikan | API butuh token; kandidat berikutnya jika dibutuhkan |
| Field-tag query (`TS=`, `TI=`, `AU=`) | tidak diimplementasikan | `query.py` hanya membuang operator tak didukung, tidak menambah sintaks field |
| `Uncheck 0 Cites` / `Uncheck CITATION results` | tidak diimplementasikan | spesifik hasil scraping Google Scholar |
| Trash & folder berlapis | sengaja tidak ditiru | MCP server memakai daftar datar |
| CAPTCHA, crash recovery | sengaja tidak ditiru | journal-scout memakai API resmi dan stateless |
| Cache TTL per provider | belum ada | `GET /api/cache/info` hanya membaca, belum mengubah TTL |

## Verdict signature

Signer **Tarma Software Research Ltd**, Sectigo EV, valid 2024-01-11 s/d
2027-01-10, timestamp DigiCert. Digest Authenticode cocok dengan blob
certificate di akhir file → binary utuh. Salinan `WIN_CERTIFICATE` di awal
overlay punya digest berbeda dan merupakan sisa proses signing lama, bukan
indikasi tampering.
