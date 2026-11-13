# 01 — Sumber Data PoP8

PoP8 tidak punya database sendiri. Setiap pencarian adalah query ke sumber
eksternal, lalu hasilnya disimpan lokal sebagai "search". Karena itu kualitas
dan batasan tiap sumber adalah batasan PoP8 itu sendiri.

## Daftar sumber

| Sumber | Varian di UI | Mekanisme |
|---|---|---|
| Google Scholar | Search, Author, Profile, Citing Works | scraping HTML GS + CAPTCHA handler |
| Google Scholar Profile | profil penulis | scrape halaman profil, daftar publikasi penulis |
| Crossref | — | REST `api.crossref.org/works`, polite `mailto` |
| Scopus | — | Elsevier API, wajib API key, ada dialog `PoPWinScopusKeyDlg` |
| Web of Science | Expanded, Starter, Lite, Automatic | tiga endpoint berbeda + auto-detect |
| PubMed | — | NCBI E-utilities (WebEnv/QueryKey, dua tahap) |
| Semantic Scholar | — | Graph API `api.semanticscholar.org/graph/v1` |
| OpenAlex | — | REST `api.openalex.org/works` |
| Lens.org | — | butuh sesi login |
| Harzing Academic Search | — | agregator khusus milik Harzing |
| Microsoft Academic | — | **dihentikan 31 Des 2021**; UI hanya untuk membuka data lama |

## Catatan per sumber

**Google Scholar.** Ini sumber utama PoP dan satu-satunya yang memberi angka
sitasi yang biasanya dipakai orang. Karena scraping, PoP harus menangani
CAPTCHA (lihat [06-infrastructure.md](06-infrastructure.md)). Varian
`Citing Works` memakai halaman "cited by" GS, bukan API.

**Web of Science.** Empat varian karena WoS punya beberapa produk dengan
endpoint dan format respons berbeda. `Automatic` mencoba mendeteksi sesi yang
tersedia; kalau sesi gagal, PoP jatuh ke `Lite`.

**Scopus.** Satu-satunya sumber yang punya jalur detail terpisah: abstract
details, author profile, dan quota status. Kuota Elsevier mingguan adalah
alasan utama PoP punya cache agresif.

**Microsoft Academic.** Sudah mati. Menu dipertahankan supaya pengguna bisa
membuka arsip hasil pencarian lama, bukan untuk query baru.

## Implikasi untuk journal-scout

**Status 2026-10-25.** journal-scout sudah mencakup Crossref, Scopus,
OpenAlex, Semantic Scholar, arXiv, DBLP, dan PubMed (`providers/pubmed.py`),
plus dua provider non-pencarian: Unpaywall sebagai enricher OA
(`providers/unpaywall.py:16`) dan OpenCitations sebagai sumber sitasi.
PubMed yang dulu dicatat sebagai "gap termurah" sudah ditutup — tool
`search_pubmed` ada di `server.py`, dan provider-nya mendeklarasikan filter
`affiliation`, `issn`, `orcid`, `doi` (`providers/pubmed.py:29`).

Yang benar-benar belum ada:

- **Google Scholar** — sumber sitasi terbesar; tidak ada API resmi, butuh
  strategi scraping atau proxy pihak ketiga. Sengaja tidak masuk roadmap.
- **Web of Science** — butuh langganan institusi, tapi satu-satunya sumber
  yang diakui untuk banyak laporan akademik.
- **Lens.org** — API tersedia dengan token gratis untuk riset; belum
  diimplementasikan.
