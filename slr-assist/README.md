# slr-assist

Asisten *systematic literature review* (SLR): proses mengikuti **Kitchenham &
Charters (2007)**, pelaporan mengikuti **PRISMA 2020**. Berisi tools tanpa server
(satu CLI Python, stdlib saja) + satu skill + satu slash command.

Diadaptasi dari *Kertas Kerja SLR v1.0* (lembar kerja individu berbasis Kitchenham),
lalu dilengkapi tuntutan PRISMA 2020: hapus duplikat, laporan tidak didapat, alasan
eksklusi full-text, log pencarian PRISMA-S, catatan siapa yang menyaring, dan
diagram alur.

## Kenapa "tools tanpa server"

Setiap subperintah `slr.py` berperilaku seperti tool MCP: argumen masuk, JSON
keluar, kode keluar 1 dan tidak menulis apa pun bila input salah. `slr.py tools`
mencetak daftar tool beserta skema argumennya (mirip `tools/list`). Bedanya, tidak ada
proses latar, dan state tersimpan di file proyek (CSV/Markdown), jadi bisa di-commit
ke git dan tidak hilang saat sesi berakhir.

## Isi

```
slr-assist/
├─ .claude-plugin/plugin.json
├─ commands/slr.md                    /slr [status|mulai|prisma|<tahap>] <folder>
├─ skills/slr-assist/
│  ├─ SKILL.md                        prinsip, tabel tools, alur
│  ├─ scripts/slr.py                  12 tools
│  ├─ templates/                      protokol.md + 4 CSV
│  └─ references/
│     ├─ kitchenham-dan-prisma.md     dipakai bersama; pemetaan fase ↔ butir PRISMA
│     ├─ alur-kerja.md                panduan per tahap
│     ├─ prisma-2020-checklist.md     27 butir (ringkasan kerja)
│     └─ rujukan.md                   rujukan terverifikasi + BibTeX
└─ tests/                             uji alur penuh + data contoh
```

## Tools

| Tool | Fungsi |
|---|---|
| `init` | Buat folder proyek dari templat |
| `status` | Tahap sekarang, antrian, angka PRISMA, peringatan, langkah berikut |
| `log-cari` | Catat pencarian per basis data (PRISMA-S) |
| `impor` | Impor `.ris/.nbib/.bib/.csv/.json` (termasuk keluaran journal-scout) + dedup |
| `dedup` | Tandai duplikat: DOI, lalu judul + tahun |
| `antrian` | Rekaman yang menunggu di tahap `ta`, `ambil`, `ft`, `kualitas`, `ekstraksi`, `sahkan` |
| `putus` | Keputusan saring; exclude wajib kode dari tabel eksklusi protokol |
| `sahkan` | Tanda keputusan sudah diperiksa peneliti |
| `nilai` | Uji kualitas C1–C7; kuartil jurnal dicatat terpisah dari total |
| `ekstrak` | Kolom ekstraksi per studi (JSON) |
| `rekap` | Diagram alur PRISMA 2020 (Mermaid, id/en), tabel per sumber/tahun, alasan eksklusi |
| `ekspor` | Studi ke BibTeX (tanpa `url`) atau RIS |

## Folder proyek

```
<proyek>/
├─ protokol.md          perencanaan (Kitchenham + PRISMA-P), dikunci sebelum mencari
├─ log-pencarian.csv    satu baris per pencarian
├─ rekaman.csv          satu baris per rekaman, semua keputusan saring
├─ kualitas.csv         skor C1–C7 per studi final
├─ ekstraksi.csv        data per studi final, dengan halaman bukti
├─ sintesis.md          ditulis per RQ
└─ prisma.md            hasil `rekap --simpan`
```

## Pemakaian

```bash
openclaude plugin install slr-assist@mahdyarief
```

Lalu di sesi: `/slr mulai slr/topik-saya`, dan seterusnya `/slr status slr/topik-saya`.

Langsung lewat CLI:

```bash
python skills/slr-assist/scripts/slr.py tools
python skills/slr-assist/scripts/slr.py status slr/topik-saya
```

Uji: `python -m unittest discover slr-assist/tests`

## Integrasi

- **journal-scout**: untuk mencari dan memverifikasi DOI. Hasil pencarian disimpan
  ke `.json` lalu di-`impor`. State `slr_*` journal-scout hanya hidup selama sesi,
  jadi catatan utama tetap file slr-assist.
- **academic-research-skills / sr-screener**: penyaringan dua reviewer AI +
  adjudikasi + kappa untuk set besar; keputusannya bisa dimasukkan dengan `putus --batch`.

## Prasyarat

Python 3.8+. Tidak ada dependensi lain.
