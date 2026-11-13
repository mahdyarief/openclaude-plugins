# Data Model Zotero & Fitur di Atasnya — Referensi untuk journal-scout-mcp

**Provenance:** Zotero 10.0.6, `omni.ja` Gecko diekstrak ke
`_rea_work/zotero/extracted/core/app-omni-extracted/`. Analisis: 2026-10-24.
Path relatif terhadap root ekstraksi. Skema item/field otoritatif **bukan** di
`xpcom/schema.js`, melainkan `resource/schema/global/schema.json`, dimuat
`schema.js:395` (`Zotero.File.getResourceAsync('resource://zotero/schema/global/schema.json')`)
lalu disimpan ke `Zotero.Schema.globalSchemaMeta` di `schema.js:656-662`.

## Ringkasan

journal-scout-mcp memakai satu model datar (`Paper`, `src/josc/models.py:5`)
dengan 13 field. Zotero memisahkan **tipe item** (40), **field** (121 nama
unik), dan **creator type** (37) — pemisahan inilah yang membuat metadata
akademik bisa divalidasi, digabung, dan diformat tanpa kehilangan semantik.
Tiga fitur paling layak diabsorb: (a) parser identifier bebas-teks, (b)
hierarki sinyal deduplikasi, (c) flag retraksi per-item. Koreksi brief:
`fieldFormats` Zotero **tidak** kaya (`issn`/`isbn`/`rating` tidak ada).

## 1. Item types

Total **40 tipe item** (`schema.json`, array `itemTypes`); nomor baris
diverifikasi langsung dari deklarasi `"itemType": "..."`.

| Tipe | Baris | Relevansi | Field kunci (selain base) |
|---|---|---|---|
| `journalArticle` | `schema.json:1583` | artikel jurnal | `publicationTitle`, `volume`, `issue`, `pages`, `ISSN`, `PMID`, `PMCID`, `journalAbbreviation` |
| `conferencePaper` | `schema.json:714` | prosiding | `proceedingsTitle`<`publicationTitle`, `conferenceName`, `eventPlace`, `ISBN` |
| `book` | `schema.json:333` | monograf | `edition`, `series`, `numPages`, `ISBN`, `publisher`, `place` |
| `bookSection` | `schema.json:444` | bab buku | `bookTitle`<`publicationTitle`, `pages`, `ISBN` |
| `thesis` | `schema.json:2840` | disertasi/tesis | `thesisType`<`type`, `university`<`publisher`, `numPages` |
| `report` | `schema.json:2569` | laporan teknis | `reportNumber`<`number`, `reportType`<`type`, `institution`<`publisher` |
| `preprint` | `schema.json:2299` | arXiv/bioRxiv | `genre`<`type`, `repository`<`publisher`, `archiveID`<`number` |
| `dataset` | `schema.json:822` | data riset | `identifier`<`number`, `versionNumber`, `repository`<`publisher` |
| `patent` | `schema.json:2117` | paten | `patentNumber`<`number`, `assignee`, `issuingAuthority`, `filingDate`, `issueDate` |
| `standard` | `schema.json:2667` | standar teknis | `organization`, `committee`, `number`, `versionNumber`, `status` |
| `manuscript` | `schema.json:1857` | manuskrip | `manuscriptType`<`type`, `institution`, `numPages` |
| `webpage` | `schema.json:3145` | halaman web | `websiteTitle`, `websiteType`, `date`, `url`, `accessDate` |
| `magazineArticle` | `schema.json:1771` | majalah | `publicationTitle`, `volume`, `issue`, `pages`, `ISSN` |
| `newspaperArticle` | `schema.json:2020` | koran | `publicationTitle`, `place`, `section`, `pages`, `ISSN` |
| `encyclopediaArticle` | `schema.json:1133` | ensiklopedia | `encyclopediaTitle`, `pages`, `ISBN` |
| `dictionaryEntry` | `schema.json:903` | kamus | `dictionaryTitle`, `pages` |

Sisa 24 tipe non-skolastik/media: `annotation`, `artwork`, `attachment`,
`audioRecording`, `bill`, `blogPost`, `case`, `computerProgram`, `document`,
`email`, `film`, `forumPost`, `hearing`, `instantMessage`, `interview`, `letter`,
`map`, `note`, `podcast`, `presentation`, `radioBroadcast`, `statute`,
`tvBroadcast`, `videoRecording`. **Tidak ada field khusus arXiv** (inferensi
dari daftar field `preprint`, `schema.json:2299`); ID arXiv disimpan lewat
`archiveID` (base `number`), `repository` (base `publisher`), atau `extra`.

## 2. Field schema

**Base field** (cakupan dari 40 tipe): `url` 38, `accessDate` 38,
`abstractNote` 37, `DOI` 37, `citationKey` 37, `shortTitle` 37, `rights` 37,
`extra` 37, `language` 36, `title` 35, `date` 34, `place` 27. Jadi `title`,
`date`, `DOI`, `url`, `abstractNote`, `language`, `rights`, `extra` memang
base universal.

**`baseField` alias:** `proceedingsTitle<publicationTitle` (`schema.json:714`),
`bookTitle<publicationTitle` (`444`), `thesisType<type` + `university<publisher`
(`2840`), `reportNumber<number` (`2569`), `genre<type` + `archiveID<number` +
`repository<publisher` (`2299`), `identifier<number` (`822`). Query generik
memakai nama base; label tetap spesifik tipe.

**Format & validasi — koreksi brief.** Tabel `fieldFormats` minimal:

| Bukti | Isi |
|---|---|
| `resource/schema/system.sql:31` | `CREATE TABLE fieldFormats (fieldFormatID INTEGER PRIMARY KEY, regex TEXT, isInteger INT)` |
| `system.sql:67-70` | komentar `-- unused`, lalu hanya 3 baris: `(1,'.*',0)`, `(2,'[0-9]*',1)`, `(3,'[0-9]{4}',1)` |
| `data/itemFields.js:59-69` | `init()` memuat `SELECT * FROM fieldFormats`, simpan `{regex, isInteger}` per `fieldFormatID` |
| `data/itemFields.js:93` | tiap field simpan `formatID: field.fieldFormatID` |
| `schema.json` `meta.fields` | hanya `{"date":{"type":"date"},"filingDate":{"type":"date"}}` |

Validasi field Zotero **berbasis regex generik** (integer vs non-integer),
bukan validator semantik per format. `cleanDOI`/`cleanISBN` (§4) adalah
normalisasi terpisah. Klaim `issn`/`isbn`/`rating` sebagai format terdaftar:
**tidak ada**.

## 3. Creator types

**37 creator type** unik:
`artist, attorneyAgent, author, bookAuthor, cartographer, castMember, chair,
commenter, composer, contributor, cosponsor, counsel, creator, director, editor,
executiveProducer, guest, host, interviewee, interviewer, inventor, narrator,
organizer, originalCreator, performer, podcaster, presenter, producer,
programmer, recipient, reviewedAuthor, scriptwriter, seriesCreator,
seriesEditor, sponsor, translator, wordsBy`.

| Tipe item | Primary (`*`) | Creator diizinkan |
|---|---|---|
| `journalArticle` (`schema.json:1583`) | `author*` | author, contributor, editor, translator, reviewedAuthor |
| `book` (`333`) | `author*` | author, contributor, editor, translator, seriesEditor |
| `bookSection` (`444`) | `author*` | author, contributor, editor, **bookAuthor**, translator, seriesEditor |
| `conferencePaper` (`714`) | `author*` | author, contributor, editor, translator, seriesEditor |
| `thesis` (`2840`) | `author*` | author, contributor |
| `report` (`2569`) | `author*` | author, editor, contributor, translator, seriesEditor |
| `preprint` (`2299`) | `author*` | author, contributor, editor, translator, reviewedAuthor |
| `dataset` (`822`) | `author*` | author, contributor |
| `patent` (`2117`) | `inventor*` | inventor, attorneyAgent, contributor |

`director`/`performer`/`castMember` tidak dipakai tipe skolastik — itu untuk
`film`, `tvBroadcast`, `radioBroadcast`, `podcast`.

## 4. Parsing identifier

`xpcom/id.js` **bukan** parser identifier — isinya `Zotero.ID_Tracker`
(`id.js:26`), tracker ID tabel internal. Parser sebenarnya di
`xpcom/utilities/utilities.js`:

| Bukti | Isi |
|---|---|
| `utilities.js:383` | `extractIdentifiers: function (text)` — pintu masuk |
| `utilities.js:431-445` | regex arXiv; versi dibuang (`0706.0044v1` → `0706.0044`); pola `[\-A-Za-z\.]+/\d{7}` atau `\d{4}\.\d{4,5}` |
| `utilities.js:447-458` | ADS Bibcode: `\b(\d{4}\D\S{13}[A-Z.:])\b` |
| `utilities.js:460-472` | PMID: `(^\|\s\|,\|:)(\d{1,9})(?=\s\|,\|$)` |
| `utilities.js:481` | `cleanDOI(x)` — normalisasi DOI, throw bila bukan string |
| `utilities.js:532` | `cleanISBN(isbnStr, dontValidate)` — normalisasi + validasi ISBN |

Urutan (inferensi dari komentar `431` "Next try arXiv" dan `460` "Finally, try
PMID"): DOI/ISBN → arXiv → ADS Bibcode → PMID. Deteksi berhenti
(`if (!identifiers.length)`) begitu satu jenis ditemukan, jadi string campuran
tidak menghasilkan identifier ganda.

## 5. Deduplikasi (`xpcom/duplicates.js`)

Normalisasi judul (`duplicates.js:111-125`): `removeDiacritics` → tanda baca
ASCII jadi spasi → `trim` → `toLowerCase`.

| Langkah | Bukti | Aturan |
|---|---|---|
| 1. Judul (blocking key) | `duplicates.js:277-284` | kandidat via `getTypeFieldsFromBase('title')` + `getID('title')`; attachment & note dikecualikan |
| 2. Judul harus sama | `duplicates.js:332-343` | setelah normalisasi, `aTitle !== bTitle` → bukan dupe |
| 3. DOI | `duplicates.js:345-350` | keduanya punya DOI dan berbeda → bukan dupe |
| 4. ISBN | `duplicates.js:352-357` | keduanya punya ISBN dan berbeda → bukan dupe |
| 5. Tahun | `duplicates.js:359-364` | keduanya punya tahun, selisih > 1 → bukan dupe |
| 6. Penulis | `duplicates.js:366-395` | minimal satu `lastName` + inisial `firstName` cocok; keduanya tanpa creator → match (`375-378`) |

Judul ternormalisasi adalah *blocking key*; DOI/ISBN/tahun/penulis adalah
*veto/konfirmasi*, bukan skor fuzzy.

## 6. Deteksi retraksi (`xpcom/retractions.js`)

Konstanta (`retractions.js:27-33`): `TYPE_DOI:'d'`, `TYPE_PMID:'p'`,
`FLAG_NORMAL:0`, `FLAG_HIDDEN:1`, `FLAG_NO_CITATION_WARNING:2`; `_version:1`
(`retractions.js:37`).

1. **Init** — `retractions.js:39` daftarkan observer pref `retractions.enabled`.
2. **Prefiks** — DOI/PMID di-hash jadi prefiks via `_valueToKey`
   (`retractions.js:757`) dan `_getPrefixString` (`766-786`).
3. **Fetch** — `_downloadPossibleMatches` (`607-622`): `POST
   this._getURLPrefix() + 'search'`, body JSON array prefiks,
   `responseType:'json'`, lalu `results.push(...this._fixedResults)` (`620`);
   `_fixedResults` (`1163`) adalah fallback hardcoded yang selalu ikut.
4. **Cache** — `_saveCacheFile(list, etag, doiPrefixLength, pmidPrefixLength)`
   (`retractions.js:585-600`).
5. **Per-item** — tabel `retractedItems` (`userdata.sql:440`):
   `(itemID INTEGER PRIMARY KEY, data TEXT, flag INT DEFAULT 0)`.
6. **Alasan** — taksonomi `_reasonDescriptions` (`retractions.js:1048`), mis.
   "Author Unresponsive", "Cites Retracted Work".
7. **Surfacing** — `flag` (0/1/2) menyembunyikan item atau mematikan
   peringatan sitasi.

Untuk journal-scout cukup peta `DOI/PMID → status retraksi` + flag boolean,
tanpa cache ETag/prefiks Zotero.

## 7. Sitasi (`xpcom/cite.js`, high level)

- `cite.js:661` — `Zotero.Utilities.Item.itemToCSLJSON(zoteroItem)` → objek CSL JSON.
- `cite.js:663-664` — `cslItem.id` wajib ID database (batasan citeproc-js).
- `cite.js:666-676` — untuk `journalArticle`/`newspaperArticle`/`magazineArticle`
  ber-`pages`, `URL` + `accessed` dihapus (kecuali pref `export.citePaperJournalArticleURL`).
- `cite.js:687` — `retrieveLocale(lang)` untuk locale CSL.
- Engine citeproc-js dibundel di `xpcom/citeproc.js` (`CSL.Engine.*` di
  `citeproc.js:3794-3799`). Skema CSL mendeklarasikan **32 tipe** (`csl.types`).

Field yang dipetakan `itemToCSLJSON`: `title`, creator, `date`,
`publicationTitle`, `volume`, `issue`, `pages`, `DOI`, `url`, `abstractNote`,
`language` (inferensi; pemetaan detail tidak ditelusuri).

## 8. Yang bisa diabsorb journal-scout

1. **Parser identifier bebas-teks** → `src/josc/utils.py`. Port
   `extractIdentifiers` (`utilities.js:383-475`) + `cleanDOI` (`481`) +
   `cleanISBN` (`532`). Effort: **kecil** (~80-120 baris + tes).
2. **Hierarki dedup** → `src/josc/merge.py`. `dedup_key`/`_match_keys`
   (`merge.py:21,33`) kini berbasis DOI/judul; tambahkan veto ala
   `duplicates.js:345-364` (DOI/ISBN beda → tolak, tahun > 1 → tolak, lalu
   cocokkan penulis). Effort: **sedang** (~60 baris + perluas `Paper`).
3. **Flag retraksi** → `src/josc/models.py` + `src/josc/providers/`. Tambah
   `retracted: bool | None` + `retraction_reason: str | None` ke `Paper`
   (`models.py:5-18`), cek DOI/PMID ke sumber retraksi di provider. Effort:
   **sedang** (butuh sumber data + cache sederhana).
4. **Tipe item + field kanonik** → `src/josc/models.py`. Ganti `type: str`
   bebas dengan enum 16 tipe skolastik (§1); tambah `volume`, `issue`, `pages`,
   `issn`, `isbn`, `publisher`, `venue_type`. Effort: **kecil-sedang**
   (update semua provider).
5. **Creator role** → `src/josc/models.py` + `providers/`. Pisahkan minimal
   `authors` + `editors`; 37 creator type penuh berlebihan. Effort: **kecil**.
6. **CSL JSON output** → modul baru `src/josc/csl.py`. Ekspor `Paper` → CSL
   JSON untuk `citeproc-py`. Effort: **sedang** (pemetaan tipe + tanggal).
7. **Validasi integer/tahun** — sudah setara `parse_int`/`parse_year`
   (`utils.py:48,64`); **tidak perlu** diabsorb.

## 9. Yang belum terungkap

- **`itemToCSLJSON`** — pemetaan field→CSL tidak ditelusuri; hanya titik
  panggil (`cite.js:661`).
- **`_getURLPrefix()`** — badan fungsi tidak ditemukan via grep di `xpcom/`;
  URL dasar layanan retraksi belum dipastikan. Semua rujukan hanya pemakaian
  (`retractions.js:610`).
- **Format field semantik** — tidak ada bukti `issn`/`isbn`/`doi`/`rating`
  sebagai `fieldFormats`; mungkin ditangani di UI di luar `xpcom/`, belum diperiksa.
- **Translator → item type** — 748 file di `translators/` belum dipetakan.
- **`schema.js` vs `schema.json`** — `schema.js` (4058 baris) sebagian besar
  logika migrasi/loader; definisi tipe/field/creator ada di `schema.json`.
  Pembagian tanggung jawab persisnya belum dipetakan penuh.
- **Versi skema** — `schema.json` memakai `version: 44` (inferensi dari field
  `version`), mekanisme migrasi antar-versi tidak dianalisis.
