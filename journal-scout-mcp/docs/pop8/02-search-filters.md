# 02 — Filter dan Operator Pencarian

Field filter yang muncul di dialog pencarian PoP8, plus batasan operator yang
PoP8 sendiri tampilkan ke pengguna (jadi ini bukan tebakan — string peringatan
itu ada di binary).

## Field filter

| Field | Keterangan |
|---|---|
| `Author` | nama penulis; dipakai juga oleh varian Author Search |
| `Affiliation` | institusi/afiliasi penulis |
| `Journal` | nama jurnal/venue |
| `ISSN` | ISSN jurnal |
| `Title words` | kata di judul |
| `KeyWords` | kata kunci |
| `YearFrom` / `YearTo` | rentang tahun terbit |
| `ORCID` | khusus OpenAlex |
| `DOI` | lookup langsung, bukan pencarian teks |

Google Scholar Profile memakai pemilih profil (`GSProfile`) alih-alih field
author bebas, karena GS mencocokkan berdasarkan `user=` di URL profil.

## Operator dan batasannya per sumber

| Sumber | AND | OR | NOT | Catatan |
|---|---|---|---|---|
| Google Scholar | ya | ya | ya | sintaks GS biasa (`-kata` untuk NOT) |
| Crossref | **tidak** | ya | ya | PoP menampilkan peringatan "Crossref does not support AND" |
| Scopus | ya | ya | ya | sintaks `AND/OR/AND NOT` Elsevier |
| OpenAlex | **tidak** | **tidak** | **tidak** | hanya satu term per field; ditandai "under development" |
| Semantic Scholar | terbatas | terbatas | terbatas | ditandai "under development" |
| PubMed | ya | ya | ya | sintaks E-utilities |
| Web of Science | ya | ya | ya | sintaks WoS |
| Microsoft Academic | ya | ya | **tidak** | sudah mati, hanya arsip |

Poin desain yang penting: PoP **tidak menormalkan** query antar sumber. Query
yang sama dikirim apa adanya ke tiap API, dan perbedaan kemampuan operator
diselesaikan dengan peringatan ke pengguna. Ini pilihan yang murah tapi
menghasilkan hasil yang tidak sebanding antar sumber.

## Implikasi untuk journal-scout

journal-scout saat ini hanya menerima `query` sebagai string bebas plus
`author`/`venue`/`year_from`/`year_to`/`tech_only`/`offset`
(`src/josc/server.py:40-57`).

**Status 2026-10-24:** `author` dan `venue` sudah diimplementasikan.
`search_all` (`aggregator.py:102-129`) hanya mengirim field yang
dideklarasikan provider di `supports_filters` (`providers/base.py:20-21`) dan
mengembalikan `filters_applied` / `filters_ignored` — jadi sinyal keterbatasan
sudah ada untuk dua field ini.

Yang masih terbuka:

1. **Field lain** (affiliation, ISSN, ORCID, DOI) belum didukung.
2. **Translasi operator per sumber** — tidak ada layer yang mengubah query
   kanonik menjadi sintaks masing-masing API.
3. **`tech_only` belum punya capability flag** — Crossref dan DBLP masih
   mengabaikannya diam-diam.
