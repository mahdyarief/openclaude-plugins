# 02 — Matriks Kapabilitas Provider

Sumber: flag di `src/josc/providers/base.py:15-27` dan deklarasi per provider.
Angka terverifikasi dengan menjalankan `provider_names()` dan
`search_provider_names()`.

## Matriks

| Provider | search | citations | author search | references | related | peran lain |
|---|---|---|---|---|---|---|
| `scopus` | ya | ya | ya | ya | — | abstract details, author profile, quota, SciVal |
| `openalex` | ya | ya | ya | ya | **ya** | satu-satunya sumber related works |
| `semanticscholar` | ya | ya | ya | ya | — | — |
| `crossref` | ya | — | ya | ya | — | — |
| `pubmed` | ya | — | ya | — | — | E-utilities dua tahap |
| `arxiv` | ya | — | ya | — | — | — |
| `dblp` | ya | — | — | — | — | — |
| `opencitations` | **tidak** | ya | — | ya | — | citation/reference only |
| `unpaywall` | **tidak** | — | — | — | — | `enricher = True` |

## Implikasi operasional

**Hanya tiga provider yang bisa jadi sumber sitasi penuh**: Scopus, OpenAlex,
Semantic Scholar. Ini yang dipakai `get_citations`
(`src/josc/aggregator.py:206`).

**Empat provider bisa jadi sumber referensi**: Scopus, OpenAlex, Semantic
Scholar, Crossref. Dipakai `get_references` (`aggregator.py:216`) dan
`build_citation_network` (`aggregator.py:256`).

**Unpaywall bukan sumber pencarian.** `enricher = True`
(`providers/unpaywall.py:16`) membuatnya hanya dipanggil dari `_enrich`
(`aggregator.py:160`) untuk melengkapi `pdf_url` dan `is_open_access`.

**OpenCitations tidak bisa search.** `supports_search = False`
(`providers/opencitations.py:33`) — hanya bisa dijadikan sumber edge sitasi
jika ada DOI.

**Hanya OpenAlex yang punya related works.** `supports_related = True`
(`providers/openalex.py:35`), dan `related()` (`openalex.py:189`) mengambil
daftar `related_works` milik satu work lalu menghidrasinya sekaligus lewat
`GET /works?filter=openalex_id:W1|W2|W3` — satu request, bukan N. Provider
lain mewarisi default `False` (`providers/base.py:20`), jadi
`aggregator.get_related` (`aggregator.py:244`) hanya memanggil OpenAlex.
Ini disengaja: setiap sumber punya algoritma "related" yang berbeda dan
hanya OpenAlex yang mengeksposnya sebagai API publik tanpa key.

## Catatan tentang `tech_only` — ✅ selesai 2026-10-24

`tech_only` ada di skema (`server.py:41`) dan dioper ke `search_all`.
Sejak 2026-10-24 ia punya capability flag sendiri, `supports_tech_only`
(`providers/base.py:22`), sehingga pemanggil mendapat sinyal eksplisit lewat
`filters_applied` / `filters_ignored`.

| Provider | `supports_tech_only` | Bukti |
|---|---|---|
| `arxiv` | **ya** | `providers/arxiv.py:105` |
| `openalex` | **ya** | `providers/openalex.py:73` |
| `scopus` | **ya** | `providers/scopus.py:158` |
| `semanticscholar` | **ya** | `providers/semanticscholar.py:91` |
| `crossref` | tidak | hanya menerima parameter, tidak dipakai |
| `dblp` | tidak | hanya menerima parameter, tidak dipakai |
| `pubmed` | tidak | hanya menerima parameter, tidak dipakai |

Empat setter di atas adalah satu-satunya provider yang punya cabang
`tech_only` sungguhan. `_route_filters` (`aggregator.py:94-101`) melaporkan
`tech_only` hanya bila pemanggil benar-benar menyetelnya `True` — kalau tidak,
setiap respons default akan menyebutnya sebagai filter yang diabaikan.

## Filter terstruktur (`supports_filters`) — ✅ diperluas 2026-10-24

`ProviderBase.supports_filters` (`providers/base.py:20-21`) mendeklarasikan
field yang benar-benar dipakai di query provider. `aggregator._route_filters`
(`aggregator.py:72-102`) hanya mengirim field ke provider yang
mendeklarasikannya dan mengembalikan `filters_applied` / `filters_ignored` di
respons; `_filter_kwargs` (`aggregator.py:105-111`) yang membangun kwargs.

| Provider | `author` | `venue` | `affiliation` | `issn` | `orcid` | `doi` |
|---|---|---|---|---|---|---|
| `scopus` | ya | ya | ya | ya | ya | ya |
| `openalex` | ya | ya | ya | ya | ya | ya |
| `crossref` | ya | ya | ya | ya | — | ya |
| `pubmed` | — | — | ya | ya | ya | ya |
| `semanticscholar` | — | ya | — | — | — | — |
| `arxiv` | ya | — | — | — | — | — |
| `dblp` | ya | — | — | — | — | — |

Bukti per provider:

- `scopus` — `providers/scopus.py:20`; klausa `AFFIL(...)`/`ISSN(...)`/
  `ORCID(...)`/`DOI(...)` di `search()` (baris 165/167/169/171) dan
  `search_author()` (baris 183/185/187/189).
- `openalex` — `providers/openalex.py:35`; `_filters()` (baris 64-119)
  memakai `raw_affiliation_strings.search:`, `primary_location.source.issn:`,
  `authorships.author.orcid:`, dan `doi:` (prefix `https://doi.org/` dibuang).
  Nilai `affiliation` diratakan dulu karena OpenAlex memecah `filter` pada koma.
- `crossref` — `providers/crossref.py:16`; `query.affiliation` sebagai
  parameter, `issn:`/`doi:` masuk `filter` yang **digabung** dengan batas
  tahun di `_works()` (baris 64-78). Tidak ada filter ORCID di API Crossref,
  jadi kolomnya sengaja kosong.
- `pubmed` — `providers/pubmed.py:29`; `_build_term()` (baris 47-56)
  menambahkan `[AD]`, `[IS]`, `[AID]`, `[DOI]`. `author`/`venue` sengaja tidak
  dideklarasikan karena keduanya punya entry point sendiri.
- `semanticscholar`/`arxiv`/`dblp` — hanya field lama; API-nya tidak punya
  padanan untuk empat filter baru.

Pengujian: `tests/test_filters.py` (7 test) mencakup routing ke provider
pendukung, pelaporan `filters_ignored`, pembagian sebagian, dan string query
tiap provider.

## Sumber yang ada di PoP8 tapi belum ada di sini

| Sumber | Alasan belum ada | Biaya menambah |
|---|---|---|
| Google Scholar | tidak ada API resmi, butuh scraping + CAPTCHA | tinggi |
| Web of Science | butuh langganan institusi | tinggi (akses) |
| Lens.org | belum diimplementasi | sedang (token gratis) |

PubMed sudah tersedia lewat `providers/pubmed.py` (E-utilities dua tahap:
`esearch` → `efetch`).
