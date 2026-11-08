# Theme Previews

Every theme rendered from the same [`sample.md`](sample.md). Click a thumbnail for the full PDF.

## Plugin themes

| | | |
|---|---|---|
| [![academic](academic.png)](academic.pdf)<br>**academic** — thesis / report | [![jurnal](jurnal.png)](jurnal.pdf)<br>**jurnal** — two-column paper | [![tugas-kuliah](tugas-kuliah.png)](tugas-kuliah.pdf)<br>**tugas-kuliah** — laporan kampus |
| [![artikel](artikel.png)](artikel.pdf)<br>**artikel** — magazine long-form | [![catatan-buku](catatan-buku.png)](catatan-buku.pdf)<br>**catatan-buku** — notes | [![default](default.png)](default.pdf)<br>**default** |
| [![tufte](tufte.png)](tufte.pdf)<br>**tufte** — lecture notes, sidenotes | [![proposal](proposal.png)](proposal.pdf)<br>**proposal** — research / grant | [![naskah](naskah.png)](naskah.pdf)<br>**naskah** — submission manuscript |
| [![surat-dinas](surat-dinas.png)](surat-dinas.pdf)<br>**surat-dinas** — official letter | [![memo](memo.png)](memo.pdf)<br>**memo** — executive briefing | [![teknis](teknis.png)](teknis.pdf)<br>**teknis** — technical docs / SOP |
| [![notulen](notulen.png)](notulen.pdf)<br>**notulen** — meeting minutes | [![zine](zine.png)](zine.pdf)<br>**zine** — brutalist essay | |

## md2pdf built-in themes

| | | |
|---|---|---|
| [![github](github.png)](github.pdf)<br>**github** | [![obsidian-light](obsidian-light.png)](obsidian-light.pdf)<br>**obsidian-light** | [![obsidian-dark](obsidian-dark.png)](obsidian-dark.pdf)<br>**obsidian-dark** |
| [![dracula](dracula.png)](dracula.pdf)<br>**dracula** | [![nord](nord.png)](nord.pdf)<br>**nord** | |

The built-in "dark" themes use a white page in print by design; only accents change.

## Regenerate

```bash
node previews/build.cjs
```

Thumbnails need poppler's `pdftoppm` on `PATH`; without it only PDFs are rebuilt.
