# 02 — Matriks Kapabilitas Provider

Sumber: flag di `src/josc/providers/base.py:16-22` dan deklarasi per provider.
Angka terverifikasi dengan menjalankan `provider_names()` dan
`search_provider_names()`.

## Matriks

| Provider | search | citations | author search | references | peran lain |
|---|---|---|---|---|---|
| `scopus` | ya | ya | ya | ya | abstract details, author profile, quota, SciVal |
| `openalex` | ya | ya | ya | ya | — |
| `semanticscholar` | ya | ya | ya | ya | — |
| `crossref` | ya | — | ya | ya | — |
| `pubmed` | ya | — | ya | — | E-utilities dua tahap |
| `arxiv` | ya | — | ya | — | — |
| `dblp` | ya | — | — | — | — |
| `opencitations` | **tidak** | ya | — | ya | citation/reference only |
| `unpaywall` | **tidak** | — | — | — | `enricher = True` |

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

## Catatan tentang `tech_only`

`tech_only` ada di skema (`server.py:41`) dan dioper ke `search_all`. Yang
benar-benar memakainya:

| Provider | Memakai `tech_only`? | Bukti |
|---|---|---|
| `arxiv` | ya | `providers/arxiv.py:105` |
| `openalex` | ya | `providers/openalex.py:73` |
| `scopus` | ya | `providers/scopus.py:158` |
| `semanticscholar` | ya | `providers/semanticscholar.py:91` |
| `crossref` | **tidak** | hanya menerima parameter, tidak dipakai |
| `dblp` | **tidak** | hanya menerima parameter, tidak dipakai |

Jadi `tech_only` bukan fitur mati, tapi juga tidak seragam. `supports_filters`
hanya mendeklarasikan `author`/`venue`, bukan `tech_only`, sehingga pemanggil
belum mendapat sinyal bahwa Crossref dan DBLP mengabaikan `tech_only`.

## Filter terstruktur (`supports_filters`)

`ProviderBase.supports_filters` (`providers/base.py:20-21`) mendeklarasikan
field yang benar-benar dipakai di query provider. `aggregator._route_filters`
(`aggregator.py:72-90`) hanya mengirim field ke provider yang mendeklarasikannya
dan mengembalikan `filters_applied` / `filters_ignored` di respons.

| Provider | `author` | `venue` | Bukti |
|---|---|---|---|
| `scopus` | ya | ya | `AUTH(...)`, `SRCTITLE(...)` |
| `openalex` | ya | ya | `_filters(...)` |
| `crossref` | ya | ya | `query.author`, `query.container-title` |
| `semanticscholar` | — | ya | `params["venue"]` |
| `arxiv` | ya | — | `au:"..."` |
| `dblp` | ya | — | parameter `author` |
| `pubmed` | — | — | belum mendeklarasikan filter |

## Sumber yang ada di PoP8 tapi belum ada di sini

| Sumber | Alasan belum ada | Biaya menambah |
|---|---|---|
| Google Scholar | tidak ada API resmi, butuh scraping + CAPTCHA | tinggi |
| Web of Science | butuh langganan institusi | tinggi (akses) |
| Lens.org | belum diimplementasi | sedang (token gratis) |

PubMed sudah tersedia lewat `providers/pubmed.py` (E-utilities dua tahap:
`esearch` → `efetch`).
