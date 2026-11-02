# Studio_Furniture — catatan untuk Claude

Studio render katalog furnitur Tala Living di Blender 5.2 (`C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`).
Bahasa proyek: Indonesia (nama file, fungsi, komentar, label UI). Pertahankan itu.

## Struktur
- `01_STUDIO/` — template studio (`Studio_Nakas.blend`: kamera, rig lampu per angle, cyclorama; `tala_studio_template.blend`).
- `02_PRODUK/<Kategori|KOLEKSI>/` — file produk terpisah (Nakas, BEECHWOOD, DOHENY). `_FINISH/` library finish,
  `_LATAR/` preset latar (`latar.json`) + file ruang lifestyle (`*_Lifestyle.blend`) + tekstur latar.
- `03_PROYEK/`, `04_HASIL_RENDER/` — sesi kerja & hasil render, **tidak** masuk git.
- `05_PANDUAN/` — panduan pengguna (PENGGUNAAN_STUDIO, PIPELINE_PRODUK, STANDAR_FILE_PRODUK, PANDUAN_LAMPU).
- `99_SISTEM/` — add-on dan skrip:
  - `nakas_studio_tools.py` — add-on utama "Nakas Studio" (sidebar 3D View). Panel `NS_PT_main` (operator `ns.*`)
    dan panel "Studio katalog" `TALA_PT_main` (operator `tala.*`) dalam satu file.
  - `tala_studio.py` — skrip/teks scene "TALA | Katalog" (dijalankan `blender -b ... --python`, lihat header file).
  - `pipeline/` — DWG/STL → produk (`bangun_produk.py`, `dwg_ke_stl.py`, `finish_kayu.py`, `periksa_produk.py`).
  - `bangun_latar_*.py`, `sinkron_beechwood.py`, `tambah_angle_kamera.py`, `tambah_lampu_tengah.py`, dll. — skrip sekali jalan
    yang memodifikasi template/latar/produk. `alat_cek/` — skrip cek kecil.
  - `uji_paket.py` — pemeriksaan paket (jalankan di Blender: `blender -b --python 99_SISTEM/uji_paket.py`).
  - `pydeps/` — dependensi Python (tidak di git, lihat `pydeps/PASANG.md`).

## Aturan kerja
- **Jangan render penuh secara lokal.** Cek pakai resolusi terendah / viewport saja; pengguna merender di server
  dan memberi umpan balik — tunggu sebelum iterasi berikutnya.
- **Backup .blend** sebelum mengubah file: simpan ke `<folder>/_BACKUP/` (bukan di samping file kerja).
  `_BACKUP/`, `*_SEBELUM_*.blend`, dan `*.blend1` diabaikan git.
- Biner (`.blend`, gambar, `.stl`, `.dxf`, `.pdf`) lewat **Git LFS** (`.gitattributes`). `.blend` tidak bisa di-merge:
  bila dua cabang mengubah file yang sama, pilih satu versi lalu ulangi perubahan lewat skripnya.
- Add-on mem-pack tekstur eksternal otomatis saat menyimpan (`_autopack_save_pre`), jadi file .blend membawa teksturnya.
- Preset latar baru: tambahkan entri di `02_PRODUK/_LATAR/latar.json` (`koleksi` = kata pada nama produk yang memilihnya otomatis).

## Git
- Remote `origin` = github.com/rizky-make-it/Studio_Furniture (main), `fork` = github.com/talait/Studio_Furniture.
- Cabang fitur `fitur/<nama>`, pesan commit dalam bahasa Indonesia.
