# Kitchenham dan PRISMA: dipakai bersama, bukan dipilih salah satu

## Inti

| | Kitchenham & Charters (2007) | PRISMA 2020 (Page et al., 2021) |
|---|---|---|
| Jenis | Pedoman **cara melakukan** SLR | Pedoman **cara melaporkan** SLR |
| Isi | 3 fase: perencanaan, pelaksanaan, pelaporan; protokol, uji kualitas, ekstraksi, sintesis | Checklist 27 butir + diagram alur (*flow diagram*) |
| Asal bidang | Rekayasa perangkat lunak | Kesehatan, kini dipakai lintas bidang |
| Menjawab | "Langkah apa yang harus saya kerjakan?" | "Apa yang harus tertulis di naskah agar pembaca bisa menilai dan mengulang?" |

Keduanya tidak bersaing. Kalimat baku di bagian metode:

> Tinjauan pustaka sistematis ini dilakukan mengikuti pedoman Kitchenham dan
> Charters (2007) dan dilaporkan sesuai PRISMA 2020 (Page et al., 2021).

Pelengkap PRISMA yang relevan:

- **PRISMA-P 2015**: isi protokol (dipakai saat menyusun `protokol.md`).
- **PRISMA-S**: pelaporan pencarian (16 butir, dipakai untuk `log-pencarian.csv`).
- **SEGRESS** (Kitchenham, Madeyski & Budgen, 2023): PRISMA 2020 yang
  disesuaikan untuk rekayasa perangkat lunak. Pakai ini bila target publikasi di
  venue SE (IEEE TSE, IST, JSS, EMSE).

## Kapan menekankan yang mana

- **Topik kesehatan / informatika kesehatan** (mis. klaim, koding ICD, BPJS):
  reviewer jurnal kesehatan mengharapkan PRISMA 2020. Diagram alur dan checklist
  wajib dilampirkan. Kitchenham tetap boleh disebut sebagai pedoman proses.
- **Topik SI/SE murni**: Kitchenham sudah lazim; tambahkan PRISMA 2020 atau
  SEGRESS untuk pelaporan. Tanpa diagram alur, reviewer sering meminta revisi.
- **Tesis**: sebut keduanya. Lampirkan checklist PRISMA terisi.

## Apa yang PRISMA tambahkan pada lembar kerja Kitchenham

Celah lembar kerja Kitchenham yang biasa (termasuk *Kertas Kerja SLR* v1.0) bila
dilaporkan dengan PRISMA 2020:

| Celah di lembar kerja | Tuntutan PRISMA 2020 | Ditangani plugin di |
|---|---|---|
| Tidak ada langkah hapus duplikat | Flow: *records removed before screening* (duplikat, alat otomatis, lain) | `rekaman.csv` kolom `pra_saring`, `duplikat_dari` |
| Jumlah per basis data di setiap tahap | Flow memakai jumlah gabungan setelah dedup; per basis data hanya di tahap identifikasi | `slr_rekap.py` membuat keduanya |
| Tidak ada "laporan tidak didapat" | *Reports sought* vs *reports not retrieved* | kolom `ft_status` |
| Alasan eksklusi full-text tidak dihitung | Alasan eksklusi full-text beserta jumlahnya wajib di flow | kolom `ft_kode` |
| Search string satu baris | String lengkap per basis data + tanggal + filter (butir 7, PRISMA-S) | `log-pencarian.csv` |
| Siapa yang menyaring tidak dicatat | Jumlah reviewer, independen atau tidak, alat otomatis yang dipakai (butir 8–9) | protokol §9, kolom `disahkan` |
| Checklist kualitas C8 = kuartil Scopus | Butir 11 meminta penilaian risiko bias **studi**, bukan peringkat jurnal | kuartil dipisah dari total |
| Tidak ada kepastian bukti | Butir 15 dan 22 (mis. GRADE), atau alasan tidak dilakukan | protokol §8 |
| Perubahan protokol tidak dicatat | Butir 24c: amandemen protokol | protokol "Riwayat perubahan" |
| Tidak ada registrasi | Butir 24a–b | protokol, kepala dokumen |

## Pemetaan fase

| Fase Kitchenham | Langkah | Butir PRISMA 2020 yang dihasilkan |
|---|---|---|
| Perencanaan | Kebutuhan SLR | 3 (rasional) |
| | PICOC + RQ | 4 (tujuan) |
| | Protokol | 5–15, 24 |
| Pelaksanaan | Identifikasi penelitian | 6, 7, 16a (flow: identifikasi) |
| | Seleksi studi | 8, 16a–b (flow: penyaringan) |
| | Uji kualitas | 11, 18 |
| | Ekstraksi | 9, 10, 17, 19 |
| | Sintesis | 12–15, 20–22 |
| Pelaporan | Penulisan | 1–2, 23, 25–27 + checklist terisi |
