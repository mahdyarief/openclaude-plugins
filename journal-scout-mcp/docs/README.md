# Dokumentasi Referensi journal-scout

Basis pengetahuan untuk pengembangan jangka panjang `journal-scout-mcp`.
Dibagi dua: referensi hasil reverse engineering aplikasi **Harzing's Publish
or Perish 8** (`pop8/`) dan dokumentasi kondisi serta rencana pengembangan
journal-scout sendiri (`journal-scout/`).

## Struktur

| Folder | Isi |
|---|---|
| [`pop8/`](pop8/README.md) | Fitur PoP8 hasil ekstraksi binary — sumber referensi fitur |
| [`journal-scout/`](journal-scout/README.md) | Kondisi aktual kode, matriks provider, gap analysis, roadmap |

## Cara pakai

- Mau tahu **fitur apa yang dimiliki PoP8** → mulai dari `pop8/README.md`.
- Mau tahu **apa yang sudah dimiliki journal-scout** → `journal-scout/01-current-state.md`.
- Mau tahu **apa yang belum ada dan layak ditambahkan** → `journal-scout/03-gap-analysis.md`.
- Mau tahu **urutan pengerjaan** → `journal-scout/04-roadmap.md`.

## Prinsip dokumen

1. **Satu topik satu file.** Jangan gabungkan domain berbeda dalam satu file.
2. **Sumber kebenaran.** Klaim tentang journal-scout harus merujuk `file:line`
   di repo ini. Klaim tentang PoP8 merujuk resource/menu di `pop8win.exe`.
3. **Update di tempat.** Kalau fitur berubah, perbarui file domainnya — jangan
   menambah file baru hanya karena ada perubahan kecil.

## Metadata sumber

- Binary: `C:\Users\Lenovo\Downloads\PoP8Setup.exe`
- Versi PoP: **8.19.5300.9483**
- Metode ekstraksi: PE resource parsing (`RT_MENU`, `RT_STRING`, `RT_DIALOG`)
  dan string mining dari `pop8win.exe` (PE yang di-carve dari arsip `tzf3`).
