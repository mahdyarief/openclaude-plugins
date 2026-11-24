---
name: slr-assist
description: "Systematic literature review end to end: Kitchenham & Charters (2007) for conducting, PRISMA 2020 for reporting (PRISMA-P protocol, PRISMA-S search log, flow diagram, 27-item checklist). Ships file-based tools (slr.py, no server): init project, log searches, import RIS/BibTeX/CSV/JSON exports, DOI/title dedup, staged screening with protocol exclusion codes, researcher sign-off, quality appraisal, data extraction, PRISMA counts + Mermaid flow, BibTeX/RIS export. Use for: SLR, systematic review, tinjauan pustaka sistematis, kajian pustaka sistematik, protokol SLR, PICOC, research question, search string, inclusion/exclusion criteria, screening judul abstrak, full-text, uji kualitas, ekstraksi data, sintesis, diagram PRISMA, Kitchenham vs PRISMA."
---

# slr-assist

Asisten SLR berbasis file. Prosesnya mengikuti **Kitchenham & Charters (2007)**
(perencanaan → pelaksanaan → pelaporan) dan pelaporannya mengikuti **PRISMA 2020**.
Keduanya dipakai bersama, tidak perlu memilih salah satu; lihat
`references/kitchenham-dan-prisma.md`.

## Prinsip

1. **File adalah sumber kebenaran.** Semua keputusan ditulis ke CSV di folder
   proyek lewat tool `slr.py`, bukan disimpan di ingatan percakapan. Angka PRISMA
   selalu dari `slr.py rekap`, tidak pernah dihitung atau diketik sendiri.
2. **Claude mengusulkan, peneliti memutuskan.** Keputusan saring, skor kualitas,
   dan isi ekstraksi adalah usulan. Jalankan `sahkan` **hanya** setelah peneliti
   menyatakan setuju di percakapan. Jangan pernah mengesahkan atas inisiatif sendiri.
3. **Protokol dikunci sebelum mencari.** Perubahan sesudahnya dicatat di bagian
   "Riwayat perubahan" protokol (PRISMA 24c), bukan ditimpa diam-diam.
4. **Setiap exclude memakai kode dari protokol** (E1, E2, ...) dan alasan singkat.
   Tool menolak kode yang tidak ada di tabel eksklusi `protokol.md`.
5. **Sitasi diverifikasi.** Metadata studi diambil dari ekspor basis data atau
   Crossref/OpenAlex, tidak ditebak. Isi ekstraksi disertai halaman.
6. Pakai bahasa yang dipakai peneliti; istilah baku (include/exclude, full-text)
   boleh tetap dalam bahasa Inggris.

## Tools

Jalankan dengan Bash. `SLR` = `python <folder skill ini>/scripts/slr.py`
(di Linux/macOS mungkin `python3`). Semua tool mencetak JSON; kode keluar 1 berarti
galat dan **tidak ada yang ditulis**. `SLR tools` mencetak skema lengkap.

| Tool | Fungsi | Contoh |
|---|---|---|
| `init` | Buat proyek dari templat (tidak menimpa) | `SLR init slr/klaim --judul "AI klaim BPJS"` |
| `status` | Tahap sekarang, antrian, angka, peringatan, langkah berikut | `SLR status slr/klaim` |
| `log-cari` | Catat satu pencarian (PRISMA-S) | `SLR log-cari slr/klaim --sumber Scopus --string "..." --hasil 412 --filter "2021-2026; ar,cp; English"` |
| `impor` | Impor `.ris/.nbib/.bib/.csv/.json` + dedup | `SLR impor slr/klaim scopus.ris --sumber Scopus` |
| `dedup` | Tandai ulang duplikat (DOI, lalu judul+tahun) | `SLR dedup slr/klaim` |
| `antrian` | Rekaman yang menunggu di satu tahap | `SLR antrian slr/klaim --tahap ta --batas 20` |
| `putus` | Catat keputusan (satu atau `--batch`) | `SLR putus slr/klaim --id R0012 --tahap ta --keputusan exclude --kode E2 --alasan "bukan klaim asuransi"` |
| `sahkan` | Tandai sudah diperiksa peneliti | `SLR sahkan slr/klaim --oleh MA --id R0012` |
| `nilai` | Uji kualitas C1–C7 (+ kuartil terpisah) | `SLR nilai slr/klaim --id R0012 --skor "C1=ya,C2=sebagian,..." --kuartil Q2` |
| `ekstrak` | Isi kolom ekstraksi (JSON) | `SLR ekstrak slr/klaim --id R0012 --data-file r0012.json` |
| `rekap` | Diagram PRISMA (Mermaid), tabel per sumber/tahun, peringatan | `SLR rekap slr/klaim --simpan` |
| `ekspor` | Studi final ke BibTeX (tanpa `url`) atau RIS | `SLR ekspor slr/klaim --format bib --keluar final.bib` |

Tahap `putus`: `ta` (judul/abstrak: include, exclude, unclear) → `ambil`
(didapat, tidak_didapat) → `ft` (include, exclude). `unclear` ikut ke full-text.
Mengubah keputusan mengosongkan `disahkan`, jadi perlu disahkan ulang.

Batch keputusan: tulis file JSON di folder sementara, lalu `putus --tahap ta --batch f.json`:
`[{"id":"R0001","keputusan":"include","alasan":"..."}, {"id":"R0002","keputusan":"exclude","kode":"E2","alasan":"..."}]`

## Alur

Mulai setiap sesi dengan `SLR status <folder>` dan ikuti `lanjut`. Detail tiap
tahap ada di `references/alur-kerja.md`; baca bagian tahap yang sedang dikerjakan.

| Tahap (status) | Yang dikerjakan | Rujukan |
|---|---|---|
| `1-perencanaan` | Kebutuhan SLR → PICOC → RQ → string + uji studi acuan → kriteria → checklist kualitas → ekstraksi → sintesis → jadwal → kunci | `templates/protokol.md` |
| `2a-identifikasi` | Jalankan string tiap basis data, `log-cari`, ekspor, `impor` | PRISMA-S |
| `2b-saring-judul-abstrak` | `antrian --tahap ta` per 20, usulkan keputusan, tampilkan tabel ke peneliti, `putus --batch`, lalu `sahkan` setelah disetujui | |
| `2c-*` | Cari full-text (legal: OA/Unpaywall/perpustakaan), `putus --tahap ambil`, lalu `ft` | |
| `2d-uji-kualitas` | `nilai` per studi, bukti per butir | protokol §6 |
| `2e-ekstraksi` | `ekstrak` per studi, setiap klaim + halaman | protokol §7 |
| `2f-sintesis` | Tulis `sintesis.md` per RQ dari `ekstraksi.csv` | |
| `3-pelaporan` | `rekap --simpan`, isi `references/prisma-2020-checklist.md`, tulis laporan | |

## Cara menyajikan usulan ke peneliti

Saat penyaringan, tampilkan per batch tabel ringkas lalu tunggu jawaban:

| id | Judul (singkat) | Usulan | Kode | Alasan |
|---|---|---|---|---|

Tanyakan satu hal: "Setuju semua, atau ada id yang mau diubah?" Tulis dulu
keputusan yang disetujui dengan `putus`, lalu `sahkan --id ...` untuk id itu saja.

## Integrasi opsional

- **journal-scout** (MCP, bila terpasang): `search_scopus`, `search_openalex`,
  `search_garuda`, `search_crossref` untuk mencari. Simpan hasilnya ke `.json` lalu
  `impor`. State `slr_*` milik journal-scout hanya hidup selama sesi MCP, jadi
  jangan dijadikan catatan utama; catatan utama tetap file `slr-assist`.
  `batch_lookup` dipakai untuk memverifikasi DOI.
- **academic-research-skills / sr-screener**: untuk penyaringan dua reviewer AI
  buta + adjudikasi + kappa pada set besar. Impor keputusannya kembali dengan
  `putus --batch`.

## Jangan

- Mengarang jumlah hasil pencarian, DOI, atau isi paper.
- Menyaring dari judul saja bila abstrak tersedia.
- Menjumlahkan kuartil jurnal ke skor kualitas.
- Memakai jalur ilegal (mis. Sci-Hub) untuk full-text.
- Menyebut SLR "pertama" tanpa bukti dari pencarian tinjauan sejenis di protokol §1.
