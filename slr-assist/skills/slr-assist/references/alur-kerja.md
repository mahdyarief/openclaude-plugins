# Alur kerja per tahap

Nomor tahap sama dengan keluaran `slr.py status`.

## 1. Perencanaan (Kitchenham fase 1, PRISMA-P)

Isi `protokol.md` berurutan. Satu bagian per giliran; jangan isi semuanya sekaligus
tanpa masukan peneliti.

1. **Kebutuhan SLR.** Cari dulu tinjauan sejenis (mis. `search_scopus` dengan
   `"systematic review" OR "scoping review"` + topik). Catat di tabel §1. Bila
   sudah ada tinjauan yang sangat mirip dan baru, sampaikan ke peneliti sebelum lanjut.
2. **PICOC.** Comparison boleh "–". Context sebaiknya spesifik (negara, sektor).
3. **RQ.** 2–5 RQ. Setiap RQ harus bisa dijawab dari kolom ekstraksi.
4. **Search string.**
   - Kata kunci per unsur PICOC: sinonim, singkatan, ejaan UK/US, istilah lokal.
   - OR di dalam unsur, AND antar-unsur. Biasanya P AND I (AND C konteks);
     Outcome sering mempersempit berlebihan, jadi uji dengan dan tanpa O.
   - **Uji studi acuan:** 3–5 paper kunci harus tertangkap. Bila tidak, perbaiki.
   - Terjemahkan per basis data (Scopus `TITLE-ABS-KEY`, WoS `TS=`, PubMed `[tiab]`/MeSH,
     IEEE `"All Metadata"`). Garuda dan Google Scholar tidak mendukung boolean penuh;
     catat keterbatasan itu.
5. **Kriteria.** Eksklusi diberi kode berurutan; kode pertama yang cocok dipakai.
   Pisahkan kriteria yang bisa dinilai dari judul/abstrak dan yang butuh full-text.
6. **Uji kualitas.** Checklist C1–C7 bawaan cocok untuk studi SI/SE. Untuk studi
   kesehatan empiris sarankan alat baku (CASP, JBI, MMAT) dan sebut di protokol.
   Kuartil jurnal dicatat terpisah.
7. **Ekstraksi.** Turunkan kolom dari RQ. Tambah kolom di `ekstraksi.csv` bila perlu.
8. **Sintesis.** Naratif/tematik untuk studi heterogen; meta-analisis hanya bila
   ukuran efek sebanding. Sebut cara menilai kepastian bukti atau alasan tidak.
9. **Reviewer.** Catat apakah ada reviewer kedua dan peran AI (PRISMA butir 8–9).
10. **Kunci.** Ubah baris status menjadi `Status: dikunci YYYY-MM-DD`. Sarankan
    registrasi OSF (gratis) bila akan dipublikasikan.

## 2a. Identifikasi

- Peneliti menjalankan string di setiap basis data (atau lewat journal-scout bila
  aksesnya ada), lalu mengekspor **semua** hasil (RIS/BibTeX/CSV, dengan abstrak).
- Untuk setiap basis data: `log-cari` dulu, baru `impor --sumber <nama sama>`.
- `jenis lain` untuk penelusuran sitasi (*backward/forward snowballing*) dan situs
  web; muncul di kolom kanan diagram PRISMA.
- Bila jumlah di log beda dengan jumlah terimpor (ekspor dibatasi 2.000, dsb.),
  `rekap` memberi peringatan. Catat alasannya di kolom `catatan` log.
- Periksa contoh duplikat hasil `dedup` (`antrian` tidak menampilkannya; buka
  `rekaman.csv` kolom `duplikat_dari`). Kesalahan dedup diperbaiki dengan mengosongkan
  `pra_saring`/`duplikat_dari` lalu `dedup` lagi.

## 2b. Saring judul dan abstrak

- `antrian --tahap ta --batas 20`. Baca judul **dan** abstrak.
- Ragu → `unclear` (ikut ke full-text). Lebih baik inklusif di tahap ini.
- Sajikan tabel usulan → peneliti setuju/ubah → `putus --batch` → `sahkan`.
- Bila ada reviewer kedua: ambil sampel (mis. 20%), minta mereka menyaring tanpa
  melihat keputusan pertama, hitung kesepakatan (Cohen's kappa), catat di laporan.

## 2c. Full-text

- `antrian --tahap ambil`: cari PDF lewat jalur legal (OA, Unpaywall/CORE,
  perpustakaan kampus, minta ke penulis). Gagal setelah usaha wajar →
  `putus --tahap ambil --keputusan tidak_didapat`.
- `antrian --tahap ft`: baca metode dan hasil. Exclude dengan kode full-text
  (mis. E4) dan alasan spesifik. Daftar ini menjadi lampiran PRISMA butir 16b.

## 2d. Uji kualitas

- Satu studi per giliran. Untuk setiap butir C, sebut bukti (bagian/halaman) di
  `--catatan` bila skornya Sebagian atau Tidak.
- Terapkan ambang sesuai protokol. Bila protokol bilang "dikeluarkan", lakukan
  dengan `putus --tahap ft --keputusan exclude --kode <kode kualitas>` setelah peneliti setuju,
  supaya tercatat di diagram.

## 2e. Ekstraksi

- Pilot 2–3 studi dulu, lalu tanya apakah kolom perlu diubah.
- Setiap isian RQ: ringkasan + halaman, mis. `"F1 0,81 pada MIMIC-III (hlm. 7)"`.
- Data tidak dilaporkan → tulis `tidak dilaporkan`, jangan dikosongkan atau ditebak.

## 2f. Sintesis

- Buat `sintesis.md` dengan satu bagian per RQ.
- Tematik: kode awal per studi → kelompokkan jadi tema → tabel tema × studi.
- Setiap klaim sintesis menyebut id/sitasi studi pendukung.
- Bagian "Celah penelitian" dan "Keterbatasan bukti".

## 3. Pelaporan

1. `rekap --simpan` → `prisma.md` (diagram + tabel). Selesaikan semua peringatan
   atau jelaskan di laporan.
2. Salin `references/prisma-2020-checklist.md` ke folder proyek sebagai
   `checklist-prisma.md` dan isi kolom lokasi.
3. Struktur laporan/bab: Pendahuluan (butir 3–4) → Metode (5–15, kutip protokol)
   → Hasil (16–22: diagram, tabel karakteristik studi, tabel kualitas, sintesis per RQ)
   → Diskusi (23) → Lain-lain (24–27).
4. `ekspor --format bib` untuk daftar pustaka studi final; cek dulu duplikat dengan
   pustaka yang sudah ada.
5. Kalimat metode baku ada di `references/kitchenham-dan-prisma.md`.
