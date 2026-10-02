# journal-scout-mcp — Design Spec

**Date:** 2026-09-19
**Status:** Approved (design), pending implementation plan
**Supersedes:** `scopus-mcp` (v1.0.0)

## 1. Purpose

`journal-scout-mcp` adalah MCP server untuk riset jurnal yang menggabungkan
beberapa sumber menjadi satu antarmuka terpadu. Fokus pengguna: mahasiswa
Telkom University di bidang teknologi, yang butuh mencari paper lintas sumber
(Scopus, arXiv, OpenAlex, Semantic Scholar, Crossref, DBLP) lalu menggabungkan
hasil duplikat menjadi satu entri, plus resolusi open-access dan citation graph
lintas-source.

Masalah yang diselesaikan: satu paper biasanya terindeks di banyak sumber
(DOI yang sama muncul di Scopus, OpenAlex, Crossref, S2 sekaligus). Tool
multi-source tanpa dedup akan membanjiri hasil dengan duplikat. Karena itu
merge berbasis DOI/judul adalah inti dari "sinergi" yang diminta.

## 2. Scope

**In scope:**
- Satu MCP server `journal-scout-mcp` dengan 7 provider.
- Unified tool (search_all, get_paper, get_citations) + per-source search tools.
- Tech-sector presets (`tech_only`) per source.
- Migrasi replace-total dari `scopus-mcp` (nama folder, package, registrasi, cache).

**Out of scope:**
- Institution scouting khusus Telkom University (tidak dipilih; tetap generik).
- Full-text download / PDF parsing.
- UI apa pun — ini MCP server headless.

## 3. Architecture

Satu MCP server, tujuh provider, satu lapisan HTTP bersama.

```
agent  ->  server.py (17 tools)
              | dispatch
         aggregator.py -- fan-out paralel (asyncio.gather) --
              |                                              |
         merge.py (dedup DOI-first + judul fuzzy)             |
              |                                              |
         models.py (Paper terpadu)                            |
                                                              v
                     providers/{scopus,arxiv,openalex,semanticscholar,crossref,dblp,unpaywall}.py
                                                              v
                                            http.py (retry/backoff + quota headers)
                                                              v
                                            cache.py (CacheManager per-provider TTL)
```

### 3.1 File layout

```
journal_scout_mcp/
├── __init__.py
├── server.py            # deklarasi tool + dispatch call_tool/list_tools
├── aggregator.py        # fan-out paralel + tangkap partial failure
├── merge.py             # dedup DOI-first + judul fuzzy, strategi penggabungan field
├── models.py            # @dataclass Paper (schema terpadu), ProviderError
├── http.py              # fetch JSON/XML + retry/backoff + per-source throttle
├── config.py            # api_key, semantic_scholar_api_key, polite_email, TTL
├── cache.py             # CacheManager (reuse dari scopus-mcp tanpa perubahan)
├── utils.py             # normalisasi DOI/judul, pembersih respons per-source
└── providers/
    ├── __init__.py      # registry: daftar instance provider aktif
    ├── base.py          # ProviderBase ABC (name, supports_search, search/get/citations)
    ├── scopus.py        # Scopus + SciVal (port dari client.py lama)
    ├── arxiv.py         # Atom XML, parse dengan xml.etree (stdlib)
    ├── openalex.py      # JSON, reconstruct abstract_inverted_index
    ├── semanticscholar.py
    ├── crossref.py
    ├── dblp.py
    └── unpaywall.py     # enrichment only (get), tidak punya search
```

Setiap provider adalah unit terisolasi: hanya tahu API-nya sendiri dan cara
memetakan respons ke `Paper`. Provider tidak tahu provider lain dan tidak tahu
tentang merge. `aggregator.py` mengatur fan-out; `merge.py` menggabungkan.
Konsekuensinya: tiap provider bisa dites sendiri dengan fixture respons, dan
menambah source baru = menambah satu file.

### 3.2 Unified Paper model (`models.py`)

```python
@dataclass
class Paper:
    doi: str | None
    title: str
    abstract: str | None
    year: int | None
    authors: list[str]
    venue: str | None
    citation_count: int | None
    url: str | None
    pdf_url: str | None
    is_open_access: bool | None
    type: str | None
    sources: list[str]        # provider yang mengembalikan paper ini
    ids: dict[str, str]       # {"doi", "scopus", "arxiv", "s2", "openalex", "dblp"}
```

`ids` menyimpan identifier source-spesifik supaya identifier dari satu sumber
bisa dipakai untuk query sumber lain (mis. DOI dari Crossref dipakai Unpaywall),
inilah yang membuat kombinasi lintas-source mungkin.

`ProviderBase` (`providers/base.py`):

```python
class ProviderBase:
    name: str
    supports_search: bool = True

    async def search(self, query, limit, year_from=None, year_to=None,
                     tech_only=False) -> list[Paper]: ...
    async def get(self, identifier) -> Paper | None: ...
    async def citations(self, identifier, limit) -> list[Paper]: ...
```

`ProviderError(provider, message)` didefinisikan di `models.py`; provider yang
gagal melempar ini.

## 4. Tool surface (17 tools)

### Unified (3)
- `search_all(query, limit_per_source=5, year_from=None, year_to=None,
  tech_only=False, sources=None)` — fan-out paralel ke semua provider search,
  merge + dedup. `sources` adalah daftar nama provider opsional (mis.
  `["arxiv", "openalex"]`) untuk membatasi fan-out; default `null` = semua
  provider yang `supports_search=True`.
- `get_paper(identifier)` — resolve DOI / arXiv ID / S2 ID / Scopus ID /
  OpenAlex ID / judul; merge metadata; enrich link OA via Unpaywall. Urutan
  resolve: kalau identifier berbentuk DOI, query Crossref+OpenAlex+S2 dulu
  (paling cepat & akurat) lalu Scopus; kalau arXiv ID, mulai dari arXiv;
  kalau judul bebas, cari via `search_all` terbatas lalu ambil hit teratas.
- `get_citations(identifier, limit=20)` — citation graph gabungan: Scopus
  `citing` + OpenAlex `cited_by` + Semantic Scholar `citations`, di-merge.

### Per-source search (6)
`search_scopus`, `search_arxiv`, `search_openalex`, `search_semanticscholar`,
`search_crossref`, `search_dblp`. Unpaywall tidak punya search.

### Scopus detail (3)
`get_abstract_details`, `get_author_profile`, `get_quota_status`.

### SciVal (5)
`scival_author_metrics`, `scival_institution_metrics`, `scival_author_lookup`,
`scival_institution_lookup`, `scival_topic_metrics`.

`get_citing_papers` lama dibuang (superseded oleh `get_citations`). Prompt
lama diperbarui: `research-summary`, `author-analysis`, `scival-author-impact`.

## 5. Merge & dedup (`merge.py`)

Kunci dedup berprioritas:
1. **DOI** dinormalisasi (lowercase, buang `https://doi.org/`, `doi:`) — kunci
   terkuat.
2. **Judul ternormalisasi** (lowercase, buang tanda baca, buang spasi berlebih,
   buang stopword umum) — dipakai hanya saat salah satu pihak tidak punya DOI.

Strategi penggabungan field saat dua `Paper` dinilai sama:
- `abstract`: dari provider mana pun yang punya nilai (streaming: Crossref/
  OpenAlex/S2 umumnya lebih lengkap daripada DBLP).
- `citation_count`: **maksimum** lintas-source (tiap sumber menghitung beda).
- `pdf_url`: Unpaywall bila ada (OA legal), fallback arXiv.
- `sources`: gabungan nama provider (di-union, urutan stabil).
- `ids`: digabung, konflik diselesaikan dengan prioritas source.

Sort akhir: `citation_count` desc, lalu `year` desc, lalu `title` asc
(determinisme agar hasil stabil antar-run).

## 6. Data flow `search_all`

1. Bangun query per-source. `tech_only=true` menerapkan preset:
   - arXiv: kategori `cs.*` (cs.AI, cs.LG, cs.CR, cs.NI, ...)
   - DBLP: filter venue CS teratas
   - OpenAlex: filter concept Computer Science
   - Scopus: tambah `SUBJAREA(COMP)`
2. `asyncio.gather(*[p.search(...) for p in providers], return_exceptions=True)`.
3. Exception per-provider ditangkap; satu source gagal tidak menggagalkan seluruh
   pencarian.
4. Respons mentah dipetakan ke `Paper`, digabung lewat `merge.py`.
5. Kembalikan `{"results": [...], "errors": {"arxiv": "..."}, "counts": {"scopus": 5, ...}}`.

## 7. Error handling

- Provider melempar `ProviderError(provider, message)`; agregator menangkapnya
  dan memasukkannya ke dict `errors`. Agent selalu tahu source mana yang gagal
  dan kenapa, sementara source lain tetap memberi hasil.
- Elsevier (dipertahankan dari scopus-mcp):
  - `429` + `X-ELS-Status: QUOTA_EXCEEDED` -> pesan kuota mingguan yang jelas.
  - `403` + `X-ELS-Status: ENTITLEMENTS_ERROR` -> pesan langganan SciVal.
  - Retry/backoff eksponensial dibatasi `MAX_BACKOFF_SECONDS = 60`; counter
    `retries` diturunkan tiap percobaan (memperbaiki infinite-loop 429 upstream).
- Rate limit per-source dijaga jeda minimum di `http.py`:
  - arXiv ~3 dtk, Semantic Scholar ~1 dtk, lainnya longgar.
  - Implementasi: `asyncio.Semaphore` + timestamp last-call per provider.

## 8. Configuration

`config.json` (gitignored) diperluas:
- `api_key` — Elsevier (sudah ada).
- `semantic_scholar_api_key` — opsional, menaikkan limit.
- `polite_email` — dipakai OpenAlex/Crossref/Unpaywall polite pool; limit jauh
  lebih baik.
- `tech_presets` — opsional override preset.

Tidak ada key wajib selain Elsevier. arXiv, DBLP, Crossref, Unpaywall, OpenAlex
jalan tanpa key.

## 9. Provider API details (ringkas)

| Provider | Base URL | Format | Auth | Catatan |
|---|---|---|---|---|
| Scopus | `api.elsevier.com/content/` | JSON | `X-ELS-APIKey` | quota mingguan |
| SciVal | `api.elsevier.com/analytics/scival/` | JSON | `X-ELS-APIKey` | butuh langganan; 403 jika tidak |
| arXiv | `export.arxiv.org/api/query` | Atom XML | none | ~3 dtk/req; parse stdlib |
| OpenAlex | `api.openalex.org/works` | JSON | `mailto` polite | 250M+ works; abstract_inverted_index perlu rekonstruksi |
| Semantic Scholar | `api.semanticscholar.org/graph/v1` | JSON | `x-api-key` opsional | citation graph + TLDR |
| Crossref | `api.crossref.org/works` | JSON | `mailto` polite | backbone DOI |
| DBLP | `dblp.org/search/publ/api` | JSON | none | venue CS paling bersih |
| Unpaywall | `api.unpaywall.org/v2/{doi}` | JSON | `email` wajib | OA resolver |

## 10. Testing

- Unit test per provider dengan `httpx.MockTransport` + fixture JSON tersimpan
  (satu file per provider). Tidak menyentuh jaringan.
- `merge.py`: kasus DOI-match, title-match, konflik `citation_count`, tanpa-DOI.
- `aggregator`: kasus _partial failure_ (satu provider melempar -> hasil tetap
  keluar + masuk `errors`).
- `config.py`: precedence env var vs config.json.
- Smoke test opsional yang benar-benar memanggil jaringan; di-skip secara default.

## 11. Migration & registration

1. Rename folder `scopus-mcp` -> `journal-scout-mcp`; package `scopus_mcp` ->
   `journal_scout_mcp`.
2. `pyproject.toml`: name `journal-scout-mcp`, version `2.0.0`, console script.
3. `.mcp.json`: key -> `journal-scout-mcp`.
4. `.claude-plugin/plugin.json`: name + version 2.0.0, deskripsi 17 tool.
5. Update kedua `marketplace.json` (source D: + installed), `settings.json`
   `enabledPlugins`, `installed_plugins.json`.
6. Buat cache dir BARU `cache/local-plugins/journal-scout-mcp/2.0.0/` (jangan
   timpa dir versi lama — loader + manifest melacak nama dir versi).
7. Hapus registrasi `scopus-mcp` (marketplace, enabledPlugins, installed_plugins,
   cache) SETELAH verifikasi journal-scout-mcp lolos.
8. `/reload-plugins`, verifikasi via MCP client SDK (tool count + satu search live).

## 12. Success criteria

- `/reload-plugins` memuat `journal-scout-mcp` tanpa error; 17 tool terdaftar.
- `search_all` mengembalikan hasil dari >=3 provider dengan duplikat DOI
  tergabung menjadi satu entri.
- Satu provider gagal (mis. SciVal 403) tidak menggagalkan `search_all`;
  kegagalan muncul di `errors`.
- `get_paper(doi)` mengembalikan satu entri merged + link OA jika tersedia.
- Registrasi `scopus-mcp` lama bersih setelah migrasi.
