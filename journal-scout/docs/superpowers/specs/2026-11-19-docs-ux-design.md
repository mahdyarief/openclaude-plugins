# Rancangan UX halaman Docs

## Tujuan

Membuat halaman `/docs` lebih mudah dipindai, dicari, dan digunakan untuk menyiapkan koneksi MCP, tanpa mengubah rute atau isi faktual referensi tool.

## Keputusan desain

Pertahankan halaman satu rute dengan visual produk yang sudah ada: tema gelap, dasar netral dingin, aksen sky, dan komponen shadcn yang telah digunakan aplikasi. Hindari dekorasi atau perubahan identitas visual yang tidak diperlukan.

### Pencarian tool

Tempatkan input pencarian sebelum daftar tool. Pencarian langsung tanpa debounce dan mencocokkan nama, deskripsi, serta nama grup tanpa membedakan kapitalisasi. Saat query aktif, tampilkan hanya grup yang memiliki kecocokan dan buka otomatis grup tersebut. Jika tidak ada hasil, tampilkan state kosong yang menyebut query serta aksi untuk menghapusnya. Saat query kosong, kembali ke keadaan default.

### Grup referensi

Tampilkan daftar tool per grup dalam section collapsible dengan nama grup, jumlah tool, indikator buka/tutup, dan status aksesibel `aria-expanded`. Grup Search dan Papers terbuka secara default; grup lain tertutup. Mengaktifkan tautan navigasi ke grup akan membuka grup tersebut dan menggulir ke section terkait.

### Navigasi

Pertahankan navigasi section yang sudah tersedia. Pada layar lebar, jadikan navigasi sticky dan tandai section yang sedang terlihat menggunakan IntersectionObserver. Pada layar sempit, gunakan navigasi chip horizontal yang tetap dapat dioperasikan dengan keyboard dan sentuhan.

### Koneksi MCP dan onboarding

Pertahankan endpoint, langkah koneksi, tautan status server, dan informasi autentikasi yang sudah ada. Tonjolkan snippet konfigurasi sebagai tindakan utama dalam panel koneksi, sediakan tombol copy dengan umpan balik sementara, dan jelaskan secara ringkas bahwa `JOSC_MCP_TOKEN` hanya diperlukan jika server mengaktifkan autentikasi. Langkah pemakaian tetap terpisah agar panel koneksi berfokus pada setup.

## Perilaku dan batasan

- Tidak menambah route, dependency, atau perubahan backend.
- Data dan deskripsi tool tetap berasal dari daftar yang telah ada; fitur pencarian hanya memfilter tampilan.
- Tombol copy menggunakan Clipboard API dan memberi umpan balik saat berhasil.
- Semua kontrol memiliki label yang dapat diakses, fokus keyboard yang terlihat, dan perilaku responsif.
- Tetap gunakan komponen, token warna, dan pola gaya yang sudah dipakai aplikasi.

## Verifikasi

- Uji pencarian yang cocok pada nama, deskripsi, dan grup; pastikan grup tanpa hasil tersembunyi dan state kosong dapat direset.
- Uji keadaan awal section dan bahwa pencarian membuka section yang cocok.
- Uji navigasi section membuka grup tujuan serta perilaku navigasi desktop/mobile.
- Uji tombol copy beserta umpan baliknya.
- Jalankan test web yang relevan, pemeriksaan tipe/lint yang tersedia, lalu tinjau hasil render pada ukuran desktop dan mobile.

## Di luar cakupan

Pemisahan dokumentasi menjadi beberapa route, perubahan isi faktual/API tool, dan perubahan sistem desain global.