# 05 — Workflow dan Struktur UI PoP8

PoP8 adalah aplikasi desktop Windows dengan satu jendela utama berisi pohon
query di kiri dan daftar hasil di kanan. Semua operasi berputar di sekitar
"search" sebagai unit kerja.

## Struktur menu utama

Menu bar punya 96 item dalam 5 menu:

| Menu | Isi penting |
|---|---|
| `File` | New/Open/Save search, Import External Data, Export to Archive, Import from Archive, Print, Exit |
| `Edit` | Cut/Copy/Paste, Delete, Rename, Select All, Check/Uncheck, Preferences |
| `Search` | New `<source>` Search untuk tiap sumber, Retrieve Citing Works, Split Citations, Mark for Search |
| `View` | Toolbar, status bar, sort, filter, refresh, diagnostic log |
| `Help` | Help, FAQ, Book, Tutorial, Website, Survey, Donate, Check for Updates |

## Pohon query (query tree)

Node folder tetap:

```
All searches
├── Recent
├── My searches
├── Older
├── Saved searches
└── Trash
```

Operasi folder: `New Folder`, `Rename` (F2), `Cut`/`Copy`/`Paste`, `Delete`,
`Duplicate Current Search`, `Move Here`, `Copy Here`, `Merge Here`,
`Create Reference Here`, `Collect Garbage`, `Empty Trash`.

`Merge Here` menggabungkan dua search jadi satu himpunan hasil dengan dedup;
`Split Citations` memecah hasil "citing works" kembali menjadi search
terpisah per paper sumber.

## Aksi pada artikel

| Aksi | Efek |
|---|---|
| Open Article in Browser | buka landing page |
| Find Article with Unpaywall | resolve OA copy via Unpaywall |
| Open Full Text in Browser | buka PDF langsung |
| Open Citing Works in Browser | buka halaman "cited by" di sumber |
| Open Related Works in Browser | buka rekomendasi terkait |
| Open Profile in Browser | buka profil penulis |
| Retrieve Citing Works | tarik daftar pengutip ke dalam search baru |

## Seleksi hasil

`Select All`, `Check All`, `Check Selection`, `Uncheck All`,
`Uncheck Selection`, `Uncheck 0 Cites`, `Uncheck CITATION results`.
Dua yang terakhir penting: `Uncheck 0 Cites` membuang paper tanpa sitasi, dan
`Uncheck CITATION results` membuang baris hasil yang hanya berupa catatan
sitasi (bukan paper utuh) — masalah khas hasil scraping Google Scholar.

## Implikasi untuk journal-scout

**Status 2026-10-25.** Gap di bawah sudah ditutup:

- **Persistensi query — ✅ selesai.** Tabel `searches` (`store.py:138-149`)
  menyimpan `id, query, author, sources, filters, result_count, created_at,
  results`; ditulis `record_search()` (`store.py:233`) lewat `_remember()`
  (`api.py:167`, dipanggil di `api.py:267`), dibaca `list_searches()`
  (`store.py:279`) dan diekspos `GET /api/searches` (`api.py:193`). UI
  riwayat ada di `web/src/routes/history.tsx`.
- **Merge — ✅ selesai.** `POST /api/merge` (`api.py:474`) memakai dedup
  DOI-first di `merge.py`; UI memanggilnya dari `history.tsx`.
- **Split — ✅ selesai.** `TursoCache.split_search` (`store.py:493`)
  memecah satu baris `searches` menjadi beberapa baris baru berukuran
  `size`, diekspos lewat `POST /api/searches/{search_id}/split`
  (`api.py:604`) dan tombol "Split" per baris di `history.tsx`.
- **Duplicate Current Search — ✅ selesai 2026-10-25.**
  `TursoCache.duplicate_search` (`store.py:369`) meng-clone baris riwayat
  dengan id baru dan label `"<query> (copy)"`; route
  `POST /api/searches/{search_id}/duplicate` (`api.py:702`), tombol
  "Duplicate" per baris di `history.tsx:536`.
- **Arsip seluruh workspace — ✅ selesai 2026-10-25.**
  `export_workspace` (`store.py:399`) / `import_workspace` (`store.py:423`)
  diekspos lewat `GET /api/searches/export` (`api.py:661`) dan
  `POST /api/searches/import-workspace` (`api.py:681`); tombol
  "Export workspace" / "Import workspace" di `history.tsx:373` dan `:381`.
- **Aksi artikel — ✅ selesai.** `PaperCard.tsx` punya tombol
  "Find open-access copy" (`:121-129`) yang memanggil `fetchPaper`
  (`api.ts:62`), plus tombol **"Related works"** dan **"Citing works"**
  yang memanggil `GET /api/related` dan `GET /api/citations` lalu
  merender panel inline berisi maksimal 10 hasil.

**Retrieve Citing Works ke search baru — ✅ selesai.**
`GET /api/citations?save=true` (`api.py:315`) memanggil `_remember()`
dengan label `citations:<identifier>`, sehingga hasil pengutip tersimpan
sebagai baris riwayat baru.

**Import External Data — ✅ selesai.** `POST /api/import`
(`api.py:561`) mem-parsing `.ris/.bib/.enw/.csv/.txt/.ciw` lewat
`src/josc/importers.py`, dan `history.tsx` punya tombol "Import file".

Satu hal yang tetap tidak ada: `Uncheck 0 Cites` / `Uncheck CITATION
results` (filter seleksi khusus hasil scraping Google Scholar) — tidak
relevan karena journal-scout memakai API resmi.

Yang **tidak** perlu ditiru: struktur folder berlapis dan trash. Untuk
sebuah MCP server, daftar search datar dengan tag lebih tepat.
