# Protokol SLR: <judul singkat>

> Disusun mengikuti tahap perencanaan Kitchenham & Charters (2007) dan butir
> PRISMA-P 2015. Kunci (bekukan) protokol sebelum pencarian dimulai. Perubahan
> sesudahnya dicatat di bagian **Riwayat perubahan** (PRISMA 2020 butir 24c).

- Peneliti: <nama>
- Pembimbing / reviewer kedua: <nama atau "tidak ada">
- Registrasi: <PROSPERO / OSF / tidak diregistrasi>
- Status: draf | dikunci <YYYY-MM-DD>

## 1. Kebutuhan SLR

Mengapa SLR diperlukan? Sebutkan tinjauan sejenis yang sudah ada (cari dulu),
dan apa celah yang belum dijawab tinjauan itu.

| Tinjauan yang sudah ada | Tahun | Cakupan | Celah |
|---|---|---|---|
| | | | |

## 2. Struktur pertanyaan (PICOC)

| Unsur | Isi |
|---|---|
| Populasi (Population) | |
| Intervensi (Intervention) | |
| Perbandingan (Comparison) | |
| Hasil (Outcome) | |
| Konteks (Context) | |

## 3. Research question

| Kode | Pertanyaan | Alasan / data yang dicari |
|---|---|---|
| RQ1 | | |
| RQ2 | | |

## 4. Strategi pencarian

### 4.1 Kata kunci per unsur PICOC

| Unsur | Kata kunci dan sinonim |
|---|---|
| P | |
| I | |
| O | |
| C (konteks) | |

### 4.2 Search string utama (format Scopus)

```
TITLE-ABS-KEY ( ( ... ) AND ( ... ) AND ( ... ) )
AND PUBYEAR > 2020 AND PUBYEAR < 2027
AND ( LIMIT-TO ( DOCTYPE , "ar" ) OR LIMIT-TO ( DOCTYPE , "cp" ) )
AND ( LIMIT-TO ( LANGUAGE , "English" ) )
```

Terjemahan ke basis data lain ditulis lengkap di `log-pencarian.csv`
(PRISMA-S: satu baris per basis data, dengan tanggal dan filter).

### 4.3 Uji string (studi acuan)

Sebutkan 3–5 paper yang *harus* tertangkap. Jika string tidak menangkapnya,
perbaiki string sebelum protokol dikunci.

| Studi acuan | DOI | Tertangkap? |
|---|---|---|
| | | |

### 4.4 Sumber

| Basis data / sumber lain | Dipakai | Alasan |
|---|---|---|
| Scopus | | |
| ScienceDirect | | |
| IEEE Xplore | | |
| ACM Digital Library | | |
| PubMed | | |
| SpringerLink | | |
| Garuda / SINTA (literatur Indonesia) | | |
| Penelusuran sitasi (*snowballing*) | | |
| Google Scholar (hanya pelengkap) | | |

- Rentang tahun: <dari> – <sampai>
- Bahasa: <...>
- Jenis literatur: jurnal / prosiding / buku / bab buku / *grey literature*

## 5. Kriteria inklusi dan eksklusi

Kode eksklusi dipakai berurutan: keputusan memakai kode pertama yang cocok.

| Kode | Kriteria eksklusi | Tahap yang memakai |
|---|---|---|
| E1 | Di luar rentang tahun / bahasa / jenis literatur | inisiasi |
| E2 | Topik tidak relevan dengan PICOC | judul/abstrak |
| E3 | | judul/abstrak |
| E4 | Bukan studi primer / tidak ada hasil empiris | full-text |
| E5 | Full-text tidak tersedia setelah usaha wajar | full-text |

| Kode | Kriteria inklusi |
|---|---|
| I1 | |
| I2 | |

Aturan *unclear*: rekaman yang ragu di tahap judul/abstrak diteruskan ke full-text.

## 6. Uji kualitas (Kitchenham) / risiko bias (PRISMA butir 11)

Skor: Ya = 1, Sebagian = 0,5, Tidak = 0.

| Kode | Pertanyaan |
|---|---|
| C1 | Apakah tujuan penelitian dijelaskan dengan jelas? |
| C2 | Apakah latar belakang dan konteks penelitian dijelaskan? |
| C3 | Apakah penelitian terkait dibahas untuk menunjukkan kontribusinya? |
| C4 | Apakah metode atau arsitektur usulan dijelaskan? |
| C5 | Apakah ada hasil penelitian? |
| C6 | Apakah kesimpulan relevan dengan tujuan penelitian? |
| C7 | Apakah ada saran penelitian lanjutan? |

- Ambang: <misal total ≥ 4 dari 7> → di bawah ambang: <dikeluarkan / tetap masuk dengan catatan>
- Kuartil Scopus/SJR dicatat **terpisah** di kolom `kuartil`, tidak dijumlahkan ke
  total. Peringkat jurnal bukan ukuran kualitas sebuah studi.
- Bila studinya empiris di bidang kesehatan, pertimbangkan alat baku
  (mis. CASP, JBI, MMAT) dan sebut alat itu di sini.

## 7. Ekstraksi data

Kolom ekstraksi = kolom `ekstraksi.csv`. Setiap kolom RQ diisi kutipan atau
ringkasan **disertai halaman** (`halaman_bukti`).

| Kolom | Untuk RQ | Definisi |
|---|---|---|
| | | |

Ekstraksi diuji dulu pada 2–3 studi (*pilot*), lalu kolom diperbaiki bila perlu.

## 8. Sintesis

- Metode: <naratif / tematik / *vote counting* / meta-analisis>
- Alasannya: <...>
- Cara menilai kepastian bukti (PRISMA butir 15): <GRADE / tidak dilakukan + alasan>

## 9. Penyaringan oleh lebih dari satu orang

- Reviewer: <peneliti saja / peneliti + pembimbing / dua reviewer independen>
- Bila ada dua reviewer: persentase sampel yang dinilai ganda, cara menyelesaikan
  beda pendapat, dan ukuran kesepakatan (Cohen's kappa).
- Peran AI: Claude mengusulkan keputusan; keputusan akhir disahkan peneliti
  (kolom `disahkan`). Tulis ini di bagian metode (PRISMA butir 8 dan 9).

## 10. Jadwal

| Tahap | Rencana | Selesai |
|---|---|---|
| Perencanaan: kebutuhan + protokol | | |
| Pencarian | | |
| Penyaringan judul/abstrak | | |
| Penyaringan full-text | | |
| Uji kualitas | | |
| Ekstraksi | | |
| Sintesis | | |
| Penulisan laporan | | |

## Riwayat perubahan

| Tanggal | Perubahan | Alasan | Dampak pada hasil |
|---|---|---|---|
| | | | |
