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

journal-scout tidak punya konsep "search tersimpan". Setiap panggilan tool
adalah operasi stateless; tidak ada workspace, folder, atau trash. Gap-nya:

- **Persistensi query** — `TursoStore` (`src/josc/store.py`) sudah menyimpan
  cache respons HTTP, tapi bukan objek query. Menambah tabel `searches`
  (id, query, sumber, filter, timestamp, hasil) adalah langkah paling logis
  untuk mendukung "recent/saved searches".
- **Merge/split** — `merge.py` sudah punya dedup DOI-first; tinggal
  diekspos sebagai operasi pada dua himpunan hasil, bukan hanya di dalam
  satu panggilan.
- **Aksi artikel** — web UI (`web/src/components/PaperCard.tsx`) hanya
  menampilkan link DOI/URL. Unpaywall sudah ada sebagai *enricher*
  (`src/josc/providers/unpaywall.py`), tapi belum ada tombol eksplisit
  "find OA copy".

Yang **tidak** perlu ditiru: struktur folder berlapis dan trash. Untuk
sebuah MCP server, daftar search datar dengan tag lebih tepat.
