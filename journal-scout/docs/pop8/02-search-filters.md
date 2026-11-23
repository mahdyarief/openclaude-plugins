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

**Status 2026-10-25.** Skema pencarian (`src/josc/server.py:41-62`) menerima
`query`, `count`, `author`, `venue`, `year_from`, `year_to`, `tech_only`,
`offset`, `affiliation`, `issn`, `orcid`, dan `doi` — semua field filter di
tabel atas sudah punya padanan. `search_all` (`aggregator.py:114-129`)
mengirim field hanya ke provider yang mendeklarasikannya di
`supports_filters` (`providers/base.py:24`) dan mengembalikan
`filters_applied` / `filters_ignored`.

Deklarasi per provider: `crossref.py:16`, `openalex.py:36`, `scopus.py:20`,
dan `pubmed.py:29` mencakup `affiliation`/`issn`/`orcid`/`doi` sesuai
kemampuan API masing-masing; `arxiv.py:52` dan `dblp.py:14` hanya `author`;
`semanticscholar.py:30` hanya `venue`. Form web sudah mengekspos keempat
field baru (`web/src/routes/search.tsx:55-58`, render di `:253-282`).

**Status 2026-10-25: sudah ditutup.** Translasi operator dan peringatan
operator kini ada di `src/josc/query.py`:

- `OPERATOR_SUPPORT` (`query.py:19`) memetakan tiap provider ke dukungan
  `AND`/`OR`/`NOT` sesuai matriks di tabel atas.
- `detect_operators` (`query.py:33`) menemukan token operator uppercase.
- `translate_query` (`query.py:41`) membuang operator yang tidak didukung
  (Crossref membuang `AND`, OpenAlex/Semantic Scholar membuang ketiganya,
  Scopus mengubah `NOT` menjadi `AND NOT`).
- `operator_report` (`query.py:65`) menghasilkan
  `{"requested": [...], "warnings": [{"source", "operator", "message"}]}`.
- `search_all` (`aggregator.py`) mengirim query hasil translasi per provider
  dan mengembalikan `query_warnings` + `query_translated`.
- UI menampilkan peringatan itu di `web/src/routes/search.tsx`, dan sort
  hasil (`relevance`/`citations`/`year`/`title` + asc/desc) tersedia di API
  (`api.py:242-243`) maupun tool MCP `search_all` (`server.py:267`).

~~**Field lain** (affiliation, ISSN, ORCID, DOI)~~ — **✅ selesai
2026-10-25.**

~~**`tech_only` belum punya capability flag**~~ — **✅ selesai
2026-10-24.** `supports_tech_only` (`providers/base.py:22`) membuat
Crossref, DBLP, dan PubMed dilaporkan di `filters_ignored` alih-alih
diabaikan diam-diam.

Satu hal yang tetap berbeda dari PoP8: operator **tidak** diterjemahkan ke
sintaks field-tag per API (mis. `TS=` WoS). Query hanya dibersihkan dari
operator yang tidak didukung, tanpa menambahkan tag field.
