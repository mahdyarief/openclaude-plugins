# 07 — Query Engine CLI (`pop8query.exe`)

Dokumen ini membedah **mesin query command-line** PoP8 — binary `pop8query.exe` yang ikut ter-carve dari arsip installer **8.19.5300.9483**. Berbeda dengan `pop8win.exe` (GUI), binary ini tidak punya dialog: ia menerjemahkan field query terstruktur menjadi sintaks native tiap sumber data, menjalankan query, lalu menulis hasil ke `outfile`. Semua klaim berasal dari **string mining** `_rea_work/pop8/strings/query_x64.ascii.txt` (plus `query_x86.ascii.txt` untuk paritas), bukan decompiler. Versi: `query_x64.ascii.txt:000dd248` → `8.19.5300.9483 (2025.12.17.1527)`; copyright `000dd1f8`; platform `000dd228` → `Windows 64-bit (AMD/Intel x64)`. Binary x86 memuat versi dan switch sama (`query_x86.ascii.txt:000bf560`, `000bfa15`).

## Ringkasan

`pop8query.exe` adalah front-end CLI tipis di atas lapisan query PoP8. Alurnya (inferensi dari nama kelas + pesan): parse opsi → bangun *query tree* (`Cannot initialize query tree: %s`, `000de678`) → objek `PoPQuery`/`PoPExecutableQuery` (`00109d08`, `0010a930`) memilih implementasi per sumber (`PoPCrossrefQuery` `0010ac10`, `PoPGScholarQuery` `0010bf08`, `PoPGSCitingQuery` `0010c490`, `PoPGSAuthorQuery` `0010c7b8`, `PoPHadbQuery` `0010cf68`, `PoPLensQuery` `0010d2e0`, `PoPMas2Query` `0010d690`) → sintaks native dibentuk → query dikirim atau hanya dicetak (`--syntax`) → hasil disortir dan diformat. Cache memakai `lastQueryTime`/`QueryTime` (`00109c50`, `00109c60`) dan `lastResultTime`/`CacheTime` (`00109c70`, `00109c80`). Teks bantuan verbatim ada di `000dd0a0`–`000de530`; daftar kata opsi mentah di `000dd060`–`000dd1ec`.

## Antarmuka CLI

### Pemilihan sumber data (15 switch)

| Switch | Keterangan (verbatim) | Offset |
|---|---|---|
| `--gscholar` | Google Scholar search (default) | `000dd533` |
| `--gsauthor` | Google Scholar Profile author search | `000dd4ff` |
| `--gsprofile` | Google Scholar Profile retrieval | `000dd599` |
| `--gsciting` | Google Scholar citing references search | `000dd562` |
| `--crossref` | Crossref search | `000dd4e0` |
| `--scopus` | Scopus search | `000dd689` |
| `--pubmed` | PubMed search | `000dd66c` |
| `--semscholar` | Semantic Scholar search | `000dd6a6` |
| `--openalex` | OpenAlex search | `000dd64d` |
| `--lens` | Lens.org search | `000dd5f7` |
| `--hadb` | Harzing Academic Search search | `000dd5c9` |
| `--wos` | Web of Science (original Thomson-Reuters) | `000dd6cd` |
| `--wosexpanded` | Web of Science (Clarivate Expanded) | `000dd70d` |
| `--wosstarter` | Web of Science (Clarivate Starter) | `000dd747` |
| `--masv2` | Microsoft Academic v2 (obsolete) | `000dd616` |

### Field query (10 switch)

| Switch | Keterangan (verbatim) | Offset |
|---|---|---|
| `--author authorspec` | spesifikasi penulis | `000dd80f` |
| `--affiliation affiliation` | afiliasi/institusi | `000dd823` |
| `--citedid id` | ID penulis yang disitasi | `000dd83d` |
| `--field fieldofstudy` | bidang studi | `000dd84a` |
| `--issn issn` | ISSN jurnal | `000dd85f` |
| `--journal journalname` | nama jurnal | `000dd86b` |
| `--title title` | judul | `000dd881` |
| `--keywords words` | kata kunci | `000dd88f` |
| `--years from-to` | rentang tahun; juga `year`, `from-`, `-to` | `000dd8a0` |
| `--raw syntax` | pakai sintaks native apa adanya | `000dd8d6` |

Header bantuan: *"the following query fields are available (note that not all data sources support all query fields)"* (`000dd790`, `000dd7d9`). Untuk `--raw`: *"uses 'syntax' verbatim ... ignores other query fields. The syntax must fit the data source in question"* (`000dd910`, `000dd953`).

### Executive / utilitas (15 switch)

| Switch | Keterangan (verbatim) | Offset |
|---|---|---|
| `-f argfile` | ambil opsi tambahan dari `argfile` (satu per baris, boleh komentar) | `000dd9a4`, `000ddc10` |
| `--direct` / `--noerrlog` / `--offline` | bypass cache / tanpa error log / hanya cache (tanpa kontak server) | `000dd9db`, `000dda4b`, `000dda8a` |
| `--dryrun` | lakukan semua kecuali mengirim query | `000dda12`, `000ddd20` |
| `--syntax` | cetak sintaks native tanpa mengirim query | `000ddada`, `000dddb0` |
| `--datadir path` | root direktori data PoP | `000ddb18` |
| `--max number` | maksimum hasil | `000ddb56` |
| `--maxage hours` | pakai cache bila umurnya ≤ `hours` | `000ddb8b` |
| `--wait secs` | jeda antar request | `000ddbca` |
| `--info` + `--all` / `--datasource` | cetak info konfigurasi; perluas ke semua sumber | `000dd280`, `000dd2f0`, `000dd382` |
| `--help` / `--version` | teks bantuan / versi program (token parser) | `000dd104`, `000dd1b8` |

### Output (4 switch)

| Switch | Keterangan (verbatim) | Offset |
|---|---|---|
| `--append` | append ke `outfile`, bukan menimpa | `000dde61` |
| `--regress` | output cocok untuk regression testing | `000dde9a` |
| `--format fmt` | format data keluaran | `000dded5` |
| `--sort [-]field` | urut naik; awalan `-` = turun | `000ddf31` |

## Field query dan pemetaannya

Pemetaan diambil dari string ringkasan per sumber (bukan tabel eksplisit); kolom dukungan adalah **inferensi** kecuali ditandai lain. Binary hanya menyatakan *"not all data sources support all query fields"* (`000dd7d9`).

| Field | Arti | Bukti dukungan per sumber |
|---|---|---|
| `--author` | penulis | Scopus `AUTH` (`001110c8`), Crossref `query.author` (`00114078`), PubMed `[Author]` (`001106b8`), Lens `author.display_name:` (`001163f0`), GS `author:` (`001145e8`) |
| `--affiliation` | afiliasi | Crossref `query.affiliation` (`00114088`), PubMed `[Affiliation]` (`001106c8`), Scopus `AFFIL` (`001110d0`), Lens `author.affiliation.name:` (`00116408`) |
| `--citedid` | ID penulis | Scopus `AU-ID(` (`001110c0`) / `ORCID(` (`001110b8`), OpenAlex `author.id:` (`00110010`) / `author.orcid:` (`00110030`) |
| `--field` | bidang studi | **tidak ditemukan** tag eksplisit — inferensi: hanya sebagian sumber |
| `--issn` | ISSN | Crossref `issn:` (`001140cc`), OpenAlex `primary_location.source.issn` (`0010fe78`), Lens `source.issn:` (`00116438`), GS ringkasan ISSN (`00114690`) |
| `--journal` | nama jurnal | Crossref `query.container-title` (`001140a0`), PubMed `[Journal]` (`001106d8`), Scopus `SRCTITLE` (`001110d8`), Lens `source.title:` (`00116428`), GS `source:` (`001145f0`) |
| `--title` | judul | Scopus `TITLE` (`001110e4`) / `TITLE-ABS-KEY` (`001110f0`), Crossref `query.bibliographic` (`001140b8`), PubMed `[Title]` (`001106e8`), OpenAlex `title.search` (`0010fed8`), Lens `title:` (`00116448`), GS `intitle:` (`001145f8`) |
| `--keywords` | kata kunci | PubMed `[Text Word]` (`001106f0`), Semantic Scholar `Keywords=%ts` (`001116d8`), OpenAlex `search` (`00110128`); GS tanpa tag khusus (inferensi) |
| `--years` | rentang tahun | Scopus `PUBYEAR = > <` (`00111100`–`00111120`), Crossref `from-pub-date`/`until-pub-date` (`001140d8`, `001140f0`), OpenAlex `publication_year:` (`00110130`), PubMed `[Publication Date]` (`00110708`), Lens `year_published:` (`00116470`), GS `as_ylo`/`as_yhi` (`00114760`, `00114768`), WoS `begin`/`end` (`001120a0`) |
| `--raw` | sintaks native verbatim | semua sumber, dengan syarat sintaks cocok (`000dd953`) |

## Sintaks native per sumber

Literal dari string binary, kecuali ditandai inferensi.

| Sumber | Tag / template | Offset |
|---|---|---|
| Scopus | `ORCID(`, `AU-ID(`, `AUTH`, `AFFIL`, `SRCTITLE`, `TITLE`, `TITLE-ABS-KEY` | `001110b8`–`001110f0` |
| Scopus | `PUBYEAR = `, `PUBYEAR > `, `PUBYEAR < ` | `00111100`, `00111110`, `00111120` |
| Scopus | endpoint `api.elsevier.com/content/search/scopus`, `X-ELS-APIKey`, param `query`, sort `-relevancy`/`-citedby-count` | `00111130`, `001111c0`, `001111d0`, `001111d8` |
| Crossref | `query.author`, `query.affiliation`, `query.container-title`, `query.bibliographic` | `00114078`–`001140b8` |
| Crossref | `issn:`, `from-pub-date:%u-01-01`, `until-pub-date:%u-12-31`, endpoint `api.crossref.org` + `/works`, sort `is-referenced-by-count`/`desc` | `001140cc`–`00114158` |
| OpenAlex | `authorships.author.orcid`, `authorships.institutions.id`, `display_name.search`, `title.search`, `primary_location.source.issn` | `0010fe08`–`0010fed8` |
| OpenAlex | `publication_year:%u-%u`, `publication_year:>%u`, `publication_year:<%u`, `filter`; endpoint `api.openalex.org/works`, sort `relevance_score:desc`/`cited_by_count:desc` | `00110130`–`00110284` |
| PubMed | `[Author]`, `[Affiliation]`, `[Journal]`, `[Title]`, `[Text Word]`, `[Publication Date]`, `NOT `/` OR `, rentang `%u:%u` | `001106a8`–`00110708` |
| PubMed | endpoint `esearch.fcgi`, `efetch.fcgi` | `00110740`, `00110780` |
| Semantic Scholar | endpoint `/graph/v1/paper/search/bulk`, `RawSyntax=%ts`, `Keywords=%ts`, filter `[filter: year=%u-%u]`, sort `paperId:asc`/`citationCount:desc` | `00111688`–`00111780` |
| Lens | `author.orcid:`, `author.display_name:`, `author.affiliation.name:`, `source.title:`, `source.issn:`, `title:`, `abstract:`, `year_published:`, rentang `[%u TO %u]` | `001163e0`–`00116470` |
| Lens | endpoint `api.lens.org/scholarly/search`, body `"from":%u`, `"size":%u`, sort `referenced_by_count` | `00116480`, `00116510`, `00116520`, `001165c8` |
| Google Scholar | `author:`, `source:`, `intitle:`, filter `as_ylo=`/`as_yhi=`, param `as_sdt`/`as_vis`/`as_rr`, endpoint `scholar.google.com/scholar` | `001145e8`–`00114790`, `00114658` |
| Google Scholar | batas panjang istilah `Combined search terms length...` | `00114610` |
| WoS | SOAP `WokSearch`/`WokSearchLite`, `queryParameters`, `databaseId`, `userQuery`, `timeSpan`, `begin`, filter `begin=/end=` | `00111f98`, `00111fd8`, `00112188`–`001121c4`, `001120a0` |

Catatan: tidak ada tag gaya WoS (`TS=`, `TI=`, `AU=`, `PY=`) di `query_x64.ascii.txt` maupun `win_x64.ascii.txt` — WoS dikirim sebagai `userQuery` SOAP (inferensi: sintaks dibentuk di luar region yang ter-mine). Harzing (`HADb`) dan Microsoft Academic (`MASv2`) hanya punya kelas query (`0010cf68`, `0010d690`) tanpa template sintaks terlihat. **dblp dan arXiv tidak ada sama sekali** di kedua binary (grep negatif) — berbeda dari `journal-scout-mcp` yang mendukung keduanya.

## Query tree / operator boolean

| Bukti | Offset |
|---|---|
| `Cannot initialize query tree: %s` (CLI) | `query_x64.ascii.txt:000de678` |
| `Fatal error: the query tree cannot be created.` (GUI) | `win_x64.ascii.txt:00119f10` |
| `Fatal error: the query tree cannot be configured.` (GUI) | `win_x64.ascii.txt:00119f40` |
| `%s: cannot save export query tree` (GUI) | `win_x64.ascii.txt:00153900` |
| `%ls: Cannot export the queries: %s` / `... import ...` (GUI) | `win_x64.ascii.txt:00119fd0`, `00119ff8` |
| literal `" AND "` (perangkai teks) | `query_x64.ascii.txt:000de4a4` |

Peringatan operator per sumber (literal): Crossref `does not support AND operator` (`00114050`), OpenAlex `does not support the NOT operator` (`00110050`), `does not support the OR operator` (`00110080`), `only supports a single term in search field %s` (`001100f0`), Microsoft Academic `does not support NOT operator` (`0010f3d0`). Token `NOT`/` OR ` juga muncul di region PubMed (`001106a8`, `001106b0`).

**Belum terbukti:** struktur node pohon (field/operator/children), presedensi, dan cara CLI menyerialkan pohon. Tidak ada tabel token `AND`/`OR`/`NOT` berdiri sendiri di binary CLI; literal `" AND "` tunggal hanya menunjukkan perangkai teks. Pohon kemungkinan dibangun di GUI (`pop8win.exe`) dan CLI hanya mengonsumsi hasilnya — **inferensi**, belum diverifikasi.

## Format output dan sorting

Format dikenali dari ekstensi `outfile` atau nama `fmt` (`000de1cd`), default CSV (`000de44a`). Daftar bantuan (`000de1f5`–`000de41e`):

| Ekstensi | Format | Offset |
|---|---|---|
| `.csv` | CSV (comma-separated values) | `000de1f5` |
| `.enw` / `.ris` | EndNote export / Reference Manager export | `000de21d`, `000de349` |
| `.html` / `.md` / `.rtf` / `.txt` | full search report (HTML / Markdown / RichText / plain text) | `000de23c`, `000de2eb`, `000de372`, `000de3eb` |
| `.isi` | ISI export data | `000de269` |
| `.json` / `.jsonl` | JSON / JSON Lines (1 record per baris) | `000de284`, `000de2b1` |
| `.qml` | QML (Quechua markup language) | `000de320` |
| `.tdf` | TDF (Tarma data format) | `000de3a2` |
| `.tsv` | TSV (tab-separated values) | `000de3c5` |
| `.xml` | XML | `000de41e` |
| `.bibtex` | BibTeX (registry, tidak di daftar bantuan) | `0010b1c0` |

Registry format: `BibTeX`/`.bibtex` (`0010b1b4`, `0010b1c0`), `EndNote Export`/`.enw` (`0010b5c0`, `0010b5d0`), `ISI/WoS Export`/`.isi` (`0010b710`, `0010b720`), `Reference Manager`/`.ris` (`0010b8e0`, `0010b8f4`).

Sort field (`--sort`, `000ddf31`):

| Field | Urutan | Offset |
|---|---|---|
| `author`, `source`, `title` | alfabetis (nama penulis / nama jurnal / judul) | `000ddf87`, `000de073`, `000de0a9` |
| `cites`, `cites_annual`, `cites_norm` | numerik (total / per tahun / ternormalisasi) | `000ddfb3`, `000ddfe0`, `000de00e` |
| `rank` | numerik peringkat pencarian (**default**) | `000de040` |
| `year` | numerik tahun terbit | `000de0cf` |

Kontrak kolom CSV hasil di header literal `0010b430`: `Cites,Authors,Title,Year,Source,Publisher,ArticleURL,CitesURL,GSRank,QueryDate,Type,DOI,ISSN,CitationURL,Volume,Issue,StartPage,EndPage,ECC,CitesPerYear,CitesPerAuthor,AuthorCount,Age,Abstract,FullTextURL,RelatedURL`. Format angka: `,%d,` (`0010b50c`), `,%u.%02u` (`0010b518`).

## Pesan error sebagai spesifikasi perilaku

| Pesan (verbatim) | Aturan validasi yang tersirat | Offset |
|---|---|---|
| `%s: cannot read option file: %s` | `-f argfile` harus bisa dibaca; gagal → fatal | `000de480` |
| `Invalid years specification '%s'; ...` | `--years` hanya menerima `from-to`, `year`, `from-`, `-to` | `000de4b0` |
| `Unknown output format '%s'; ...` | `--format` harus salah satu nama/ekstensi di tabel | `000de4f0` |
| `Unknown sort order '%s'; ...` | `--sort` harus salah satu dari 8 field | `000de568` |
| `No query parameters specified; ...` | minimal satu field query wajib ada | `000de6f0` |
| `Cannot initialize query tree: %s` | pohon query harus terbentuk sebelum eksekusi | `000de678` |
| `Cannot initialize query: %s` | objek query per sumber harus terinisialisasi | `000de730` |
| `%s: cannot format query parameters: %s - %s` | formatter parameter bisa gagal (mis. field tak didukung) | `000de778` |
| `%s: query parameters: %s` | jalur debug `--dryrun`/`--syntax` mencetak parameter | `000de7a8` |
| `%s: cannot format query syntax: %s - %s` | konversi ke sintaks native bisa gagal | `000de7c8` |
| `%s: query syntax: %s` | keluaran `--syntax` | `000de7f8` |
| `%s: query failed: %s - %s` | kegagalan jaringan/API dilaporkan sebagai error query | `000de838` |
| `%s: query results saved as %s` | sukses menulis `outfile` | `000de888` |
| `Data was truncated` | hasil melebihi `--max` → ditandai terpotong | `000df528` |
| `Max results: %u per query` | info batas hasil per query | `001094b8` |
| `Query fields: %s` | info field aktif (keluaran `--info`) | `00109518` |
| `-----START OF QUERY [%ts]-----` / `-----END OF QUERY [%ts]-----` | penanda blok log query | `001095d8`, `001097f8` |
| `%s: cancelling the query` | query bisa dibatalkan (mis. SIGINT) | `00109638` |
| `%s: 0 results after query` | hasil kosong dilaporkan eksplisit | `00109740` |

Keluaran `--info` lain: `Data source: [%d] %s` (`00109468`), `Settings key: %s` (`00109480`), `Max cache age: %d seconds` (`00109498`), `Max results: %u per request` (`001094d8`), `Retrieval order: [%d] %s` (`001094f8`), `Searching %ts` (`001095c8`).

## Implikasi untuk journal-scout-mcp

- **Mode `--syntax` / dry-run.** Cetak sintaks native per provider tanpa mengirim request (`000ddada`, `000de7f8`). Implementasi murah: `render_query(provider, params) -> str` dipakai bersama jalur eksekusi.
- **Preview parameter terstruktur.** `--dryrun` mencetak `query parameters: %s` (`000de7a8`) sebelum format native — berguna untuk debugging pemetaan field.
- **`--maxage` untuk kesegaran cache** (`000ddb8b`): simpan timestamp hasil (pola `CacheTime`/`lastResultTime`, `00109c70`, `00109c80`) dan pakai ulang bila umur ≤ ambang.
- **Set sort field yang konsisten** (`000ddf31`): `author`, `cites`, `cites_annual`, `cites_norm`, `rank`, `source`, `title`, `year` — bisa dipetakan ke pengurutan lokal setelah agregasi lintas provider.
- **Argfile** (`000dd9a4`, `000ddc10`): dukung file opsi satu-per-baris dengan komentar, memudahkan reproduksi query panjang.
- **Peringatan operator per provider** (`00114050`, `00110050`, `00110080`): permukaan yang sama bisa dipakai untuk menolak/menurunkan query yang tidak didukung provider.

## Yang belum terungkap

- Tidak ada decompiler/disassembler — semua dari string. Alur kontrol, struktur data pohon, dan presedensi operator **tidak terverifikasi**.
- Struktur *query tree* (node, anak, operator) tidak terbaca; hanya pesan error dan satu literal `" AND "` (`000de4a4`).
- Template sintaks untuk `--field` (bidang studi), Harzing (`HADb`), dan Microsoft Academic (`MASv2`) tidak ditemukan sebagai string.
- Apakah WoS membentuk tag (`TS=`, dll.) di runtime tidak terlihat; yang ada hanya jalur SOAP `userQuery`.
- Perilaku dinamis (`--maxage` benar-benar memakai cache? `--wait` menunda?) belum diuji — hanya tersirat dari teks bantuan.
- Tabel kata opsi `000dd060`–`000dd1ec` tidak memuat `max`, `raw`, `wos`, `all`, `datasource`, `outfile`; kemungkinan itu tabel prefiks/abreviasi, bukan registry switch lengkap (inferensi).
