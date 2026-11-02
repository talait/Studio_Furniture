# Laporan Konversi DWG → Blender — koleksi BEECHWOOD

Tanggal: 2026-10-29 · Dibuat otomatis oleh tugas terjadwal `beechwood-dwg-to-blend` (Claude Code) · Blender 5.2.2 LTS, headless.

Folder: `02_PRODUK/BEECHWOOD/` — 6 file `.blend` (satu per DWG), `_source_dwg/` (DWG asli), `_preview/` (thumbnail Workbench 512 px depan & belakang), `_skrip/` (skrip, resep, laporan JSON, hasil verifikasi JSON).

## Ringkasan

| # | Sumber (Drive) | Hasil .blend | Rute | L × D × T (mm) | Objek mesh | Status |
|---|---|---|---|---|---|---|
| 1 | `BEECHWOOD BEDSIDE.dwg` (86,452 B, AC1032 (AutoCAD 2018)) | `BEECHWOOD BEDSIDE.blend` | 3DSOLID ACIS → tessellasi | 550 × 505.2 × 500 | 20 aktif + 1 arsip | OK (diperbaiki 30-10, lihat 1a) |
| 2 | `beechwood 6dw r.dwg` (405,850 B, AC1032 (AutoCAD 2018)) | `beechwood 6dw r.blend` | 3DSOLID ACIS → tessellasi | 1200 × 605.3 × 700 | 60 aktif + 12 arsip | OK (diperbaiki 30-10, lihat 2a) |
| 3 | `BEECHWOOD TALLBOY.dwg` (174,093 B, AC1032 (AutoCAD 2018)) | `BEECHWOOD TALLBOY.blend` | 3DSOLID ACIS → tessellasi | 600 × 505.2 × 1100 | 56 aktif + 0 arsip | OK (diperbaiki 30-10, lihat 3a) |
| 4 | `BEECHWOOD DINNING TABLE  ALTFIELD.dwg` (114,988 B, AC1032 (AutoCAD 2018)) | `BEECHWOOD DINNING TABLE  ALTFIELD.blend` | 3DSOLID ACIS → tessellasi | 2100 × 800 × 750 | 13 aktif + 0 arsip | OK (disusun ulang 30-10, lihat 4a) |
| 5 | `SP 05 ALTFIELD CREDENZA.dwg` (38,665,124 B, AC1014 (AutoCAD R14)) | `SP 05 ALTFIELD CREDENZA.blend` | mesh PFACE (R14) | 1800 × 658.1 × 900 | 23 aktif + 7 arsip | OK (diperbaiki 30-10, lihat 5a) |
| 6 | `BEECHWOOD DINNING CHAIR.dwg` (409,854 B, AC1032 (AutoCAD 2018)) | `BEECHWOOD DINNING CHAIR.blend` | 3DSOLID ACIS → tessellasi | 550.9 × 620.2 × 858.1 | 10 aktif + 0 arsip | OK |

Semua enam file berhasil dikonversi; tidak ada yang dilewati. Verifikasi buka-ulang headless: unit metrik (scale_length 1, tampilan cm), dasar tepat di Z = 0, terpusat di XY, tanpa kamera/lampu, semua mesh bermaterial peran, transformasi sudah diterapkan.

## Lingkungan dan metode umum

**Pengambilan file.** Tautan share Drive mengarah ke halaman login Google (bukan publik), jadi `curl` dan browser bawaan gagal. Dua file (Bedside, 6dw r) sudah ada di `C:\Users\Staff\Downloads` dengan ukuran byte persis sama dengan metadata Drive; empat sisanya diunduh lewat Chrome milik pengguna (sudah login) dari `drive.usercontent.google.com/download?id=…`. Ukuran semua file dicocokkan dengan metadata Drive. File DWG tersimpan di `_source_dwg/` dan diperlakukan sebagai data tidak tepercaya (dibaca oleh Python `-I`, skrip di luar folder itu).

**Alat.** LibreDWG 0.13.3 (Docker, `dwgread -O JSON`, dump section AcDs), `C:\Users\Staff\tools\libredwg\dwg2obj.py` (ezdxf SAB parser + tessellasi B-rep: bidang, silinder/kerucut, torus, bola; kurva garis & elips; spline didekati garis), Blender 5.2.2 headless. AutoCAD Core Console (`99_SISTEM/pipeline/dwg_ke_stl.py`) dan ODA File Converter tidak terpasang di mesin ini; `dwg2dxf` tidak membawa geometri ACIS, jadi rute DXF tidak dipakai untuk solid. Catatan: skrip `dwg2obj.py` hanya dipanggil, tidak diubah.

**Pembersihan mesh (per objek, `_skrip/bersih.py`).** Merge by distance 0,01 mm → hapus tepi/muka degenerate dan vertex/tepi lepas → **perbaikan sambungan-T** (vertex lain yang terletak di atas tepi terbuka → tepi dipotong di titik itu, toleransi 0,3 mm; 0,1 mm untuk handle) → hapus muka duplikat → tutup lubang kecil (loop batas keliling < 25 cm) → recalculate normals outside → dissolve muka sebidang (0,06°). Hasil tiap objek dicek: tepi non-manifold, tepi terbuka, muka luas nol, jumlah pulau. Sisa yang tidak bisa diperbaiki otomatis dicatat per produk; semuanya berada di blend sudut (fillet < 1 mm) atau di alur handle (tepi spline), tidak terlihat pada render.

**Struktur file (mengikuti `05_PANDUAN/STANDAR_FILE_PRODUK.md` v2).** Scene `PRODUK | <nama>`, satu collection `PROD | <nama>` dengan child collection `Badan`, `Kaki`, `Laci`, `Pintu`, `Hardware` (dan `_ARSIP sisa DWG (tidak dipakai)` yang dikecualikan dari view layer bila ada); empty `PRODUCT_ROOT | <nama>` (`ns_product_root`, `dimensions_cm`, `source`, `unit_assumption`, `catatan`); setiap part = satu objek mesh bernama `<Nama bagian> | <handle DWG>` dengan properti `cad_handle`, `ns_role_part`, `geometry_source`; origin tiap part di pusat bbox-nya, root di (0,0,0); depan −Y, lebar X, tinggi Z, dasar di Z = 0. Laci: empty `DRAWER_n` (`ns_drawer`, properti `Open (m)`, driver `location.y = -Open`) yang menjadi induk front, handle dan kotak laci sederhana (dasar 7 mm, sisi & belakang 12 mm — **tambahan standar v2, bukan dari DWG**, properti `geometry_source` menandainya). Material per peran: `ROLE | WOOD_A`, `ROLE | WOOD_B` (kotak laci), `ROLE | HANDLE` (metalik) dengan properti `ns_role`; finish kayu `FIN | …` belum ditanam (butuh `produk.json` + swatch klien lewat `pipeline/bangun_produk.py`). UV `UV meter` tri-planar (1 UV = 1 m), modifier Bevel 0,6 mm (handle 0,35 mm) + Weighted Normal, smooth by angle 30°. File disimpan terkompresi.

**Pemeriksaan tabrakan.** Untuk setiap pasangan part aktif yang bbox-nya tumpang tindih > 0,3 mm di tiga sumbu, dihitung vertex part A yang berada di dalam mesh part B (BVH, margin 0,3 mm) dan sebaliknya. Hasil per produk di bawah; pasangan handle–front (handle terbenam di alur front, sesuai DWG) tidak diulang di tiap bagian.

**Thumbnail.** Hanya render Workbench 512 × 384 (depan 3/4 dan belakang) untuk cek visual, di `_preview/`; tidak ada render Eevee/Cycles. Kamera tidak disimpan di file.

## 1. `BEECHWOOD BEDSIDE.dwg` → `BEECHWOOD BEDSIDE.blend`

- **Sumber:** Drive id `1Ijo4x03Cl7MFIEvzzJdLocuxv08BpLhw`, 86,452 byte, format AC1032 (AutoCAD 2018), satuan: INSUNITS=4 (mm).
- **Isi DWG:** 11 3DSOLID di model space (layer 0), tanpa garis/teks/dimensi.
- **Rute konversi:** DWG → `dwgread -O JSON` + dump AcDs (LibreDWG, Docker) → blob SAB per solid → tessellasi B-rep (`dwg2obj.py`) → OBJ (mm) → Blender (skala 0,001).
- **Dimensi hasil (L × D × T):** 550 × 505.2 × 500 mm; `dimensions_cm` di root = [55.0, 50.52, 50.0].
- **Nama produk di file:** `Beechwood Bedside` (kategori `NAKAS`).

**Komponen** (objek mesh; ukuran bbox mm; handle = handle entitas DWG, `pface` = mesh R14, `-` = tambahan):

| Collection | Objek | Peran | Ukuran (mm) | Muka | Sisa tepi terbuka | Catatan |
|---|---|---|---|---|---|---|
| Badan | `Badan kabinet (carcass + top) | 2CF` | WOOD_A | 550 × 420 × 410 | 3,985 | 0 |  |
| Badan | `Panel belakang | 2D0` | WOOD_A | 470 × 9 × 370 | 6 | 0 |  |
| Badan | `Rak dasar | 2D8` | WOOD_A | 550 × 500 × 18 | 4,166 | 0 |  |
| Badan | `Rel atas belakang | 2CE` | WOOD_A | 470 × 40 × 40 | 1,121 | 0 |  |
| Badan | `Rel atas depan | 2D7` | WOOD_A | 470 × 40 × 40 | 1,119 | 0 |  |
| Kaki | `Kaki belakang kanan | 2C5` | WOOD_A | 40 × 40 × 500 | 4,307 | 11 |  |
| Kaki | `Kaki belakang kiri | 2CB` | WOOD_A | 40 × 40 × 500 | 4,324 | 8 |  |
| Kaki | `Kaki depan kanan | 2C2` | WOOD_A | 40 × 40 × 500 | 4,345 | 12 |  |
| Kaki | `Kaki depan kiri | 2C8` | WOOD_A | 40 × 40 × 500 | 4,308 | 30 |  |
| Laci | `Front laci 1 | 2D6` | WOOD_A | 470 × 30 × 117 | 6,718 | 649 | 5 pulau (pecahan di alur/blend) |
| Laci | `Laci 1 / belakang 12 mm` | WOOD_B | 446 × 12 × 87 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 1 / dasar 7 mm` | WOOD_B | 446 × 398.2 × 7 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 1 / sisi kanan 12 mm` | WOOD_B | 12 × 398.2 × 87 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 1 / sisi kiri 12 mm` | WOOD_B | 12 × 398.2 × 87 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Hardware | `Handle laci 1 | 2D3` | HANDLE | 163.6 × 21 × 8 | 10,696 | 12 |  |

**Kualitas mesh:** 9 dari 15 objek aktif manifold tertutup sepenuhnya; sisanya punya tepi terbuka seperti di kolom tabel (lihat *Masalah*).

**Masalah yang ditemukan dan perbaikan:**

- Mesh hasil tessellasi punya sambungan-T (patch lengkung dibagi 8×, bidang datar tetangganya tidak) dan lubang mikro di blend sudut → diperbaiki di Blender (lihat *Pembersihan mesh*). Sisa: kaki 8–30 tepi terbuka (lubang < 1 mm di blend sudut), front laci 649 tepi terbuka di zona alur handle (kurva spline `intcurve` didekati garis lurus oleh tessellator), handle 12 tepi terbuka.
- Front laci di DWG menyentuh rel atas tanpa celah → diberi celah bayangan 1,5 mm atas-bawah (standar v2, tinggi 120 → 117 mm), handle ikut bergeser.
- Rak dasar (panel 18 mm, 550 × 500) digambar menerus sehingga keempat kaki menembusnya di sudut (tersembunyi di dalam kaki). Takik boolean dicoba (EXACT dan FLOAT) tetapi mesh tessellasi rak pecah → rak dibiarkan sesuai DWG. Tidak terlihat dari luar.
- Handle (pelat 164 × 21 × 8 mm) terbenam 16 mm ke dalam front: sesuai DWG (alur handle di front), dibiarkan.

**Keputusan / judgement call:**

- Carcass + top adalah satu solid di DWG (550 × 420 × 410) → satu objek `Badan kabinet (carcass + top)`; tidak dipecah karena tidak ada batas part di data.
- Kotak laci sederhana (dasar 7 mm, sisi/belakang 12 mm) ditambahkan mengikuti STANDAR_FILE_PRODUK v2; ditandai `geometry_source = tambahan`, bukan dari DWG. Mudah dihapus bila tidak diinginkan.
- Depan = −Y (sisi handle), tidak perlu rotasi.

**Keraguan yang tersisa:**

- Tidak ada keraguan dimensi; semua bagian cocok dengan nakas 550 × 505 × 500 mm.

**Uji tembus antar part** (vertex A di dalam B / B di dalam A):

- 1 pasangan handle ↔ front laci: handle terbenam 16 mm di alur front (sesuai DWG).
- `Kaki depan kanan | 2C2` ↔ `Rak dasar | 2D8`: bbox tumpang tindih 40 × 40 × 18 mm, 235 / 24 vertex.
- `Kaki belakang kanan | 2C5` ↔ `Rak dasar | 2D8`: bbox tumpang tindih 40 × 40 × 18 mm, 290 / 24 vertex.
- `Kaki depan kiri | 2C8` ↔ `Rak dasar | 2D8`: bbox tumpang tindih 40 × 40 × 18 mm, 108 / 24 vertex.
- `Kaki belakang kiri | 2CB` ↔ `Rak dasar | 2D8`: bbox tumpang tindih 40 × 40 × 18 mm, 218 / 24 vertex.
- 2 pasangan lain hanya bersentuhan (bbox tumpang tindih, 0 vertex di dalam).

**Log build (otomatis):**

- Front laci 1 | 2D6: tinggi 120.0 -> 117.0 mm, pusat geser +0.0 mm (fit kolom -663.9..-543.9 mm, celah 1.5 mm)
- Laci 1: kotak laci sederhana ditambahkan (lebar 446, dalam 398, tinggi 87 mm)

**Verifikasi buka-ulang:** unit ['METRIC', 'CENTIMETERS', 1.0], 15 mesh, bbox aktif min [-275.0, -252.6, 0.0] max [275.0, 252.6, 500.0] mm, collection dikecualikan: -, masalah: tidak ada. Thumbnail: `_preview/BEECHWOOD BEDSIDE.png` dan `_preview/BEECHWOOD BEDSIDE_belakang.png`.

### 1a. Perbaikan 30-10-2026: per komponen konstruksi

Skrip: `_skrip/perbaiki_lemari.py` (+ `_skrip/konstruksi_util.py`). Cadangan: `_versi_lama/BEECHWOOD BEDSIDE_SEBELUM_struktur_20261030.blend`. Laporan mesin: `_skrip/laporan_json/BEECHWOOD BEDSIDE_perbaikan.json`. Preview Workbench resolusi rendah: `_preview/BEECHWOOD BEDSIDE.png`, `_belakang`, `_dalam`, `_bawah`. **Struktur collection dan daftar komponen di atas sudah digantikan oleh bagian ini.**

**Struktur:** `01 Carcass` (Top, Sisi kiri, Sisi kanan, Rak dasar 18 mm, 2 klos rel) · `02 Rangka depan` (2 kaki depan, rel atas depan) · `03 Rangka belakang` (2 kaki belakang, rel atas belakang, panel belakang) · `04 Laci / Laci 1` (front, handle, sisi kiri/kanan, depan dalam, belakang, dasar). Total 20 mesh aktif + 1 arsip.

- **Carcass 2CF** (top + 2 sisi bengkok) dipecah mitre 45° lewat pusat lengkung (±235; 460) → top 550 × 420 × 20, sisi 410 × 420 × 20; semua manifold tertutup.
- **Rak dasar DWG** (550 × 500, menembus keempat kaki dan sisi carcass) diganti **Rak dasar 18 mm bertakik kaki 40 × 40**: lebar 510 di antara sisi, lidah 470 di antara kaki depan (rata muka kaki) dan sampai panel belakang. Rak lama ke `_ARSIP`.
- **Klos rel 20 mm** (2) di sisi dalam agar bidang rel rata muka dalam kaki (x ±235).
- **Kotak laci dibangun ulang**: 444,6 × 400 × 87 mm, ruang rel 12,7 mm, + depan dalam 12 mm; kotak lama (sisi & dasar saling tembus) dihapus.
- Uji tembus: 0, kecuali handle di alur front (sesuai DWG) dan 1 vertex di garis mitre top/sisi (bersinggungan).

## 2. `beechwood 6dw r.dwg` → `beechwood 6dw r.blend`

- **Sumber:** Drive id `1KoZ9m7RVX2hVKBNeql8-yYu-3MDAvNcd`, 405,850 byte, format AC1032 (AutoCAD 2018), satuan: INSUNITS=1 (inci) di header, angka jelas mm.
- **Isi DWG:** 29 3DSOLID + 5 LWPOLYLINE + 4 VIEWPORT (layout). DWG berisi **dua rakitan berdampingan**: A (kiri, x 1344–2528): carcass 1183 mm, rangka belakang, 1 kaki depan kiri, rel atas depan, 5 front 550 mm + 5 handle (front kiri-atas tidak ada); B (kanan, x 2733–3933): rangka depan 1200 mm (2 kaki + rel) dan 6 front 559 mm + 6 handle, **tanpa carcass**. Nama file "6dw r" = revisi.
- **Rute konversi:** Sama dengan Bedside (ACIS SAB → tessellasi → OBJ → Blender).
- **Dimensi hasil (L × D × T):** 1200 × 605.3 × 700 mm; `dimensions_cm` di root = [120.0, 60.53, 70.0].
- **Nama produk di file:** `Beechwood 6 Drawers` (kategori `DRESSER`).

**Komponen** (objek mesh; ukuran bbox mm; handle = handle entitas DWG, `pface` = mesh R14, `-` = tambahan):

| Collection | Objek | Peran | Ukuran (mm) | Muka | Sisa tepi terbuka | Catatan |
|---|---|---|---|---|---|---|
| Badan | `Badan kabinet (carcass + top) | 261` | WOOD_A | 1200 × 520 × 611.1 | 4,113 | 0 |  |
| Badan | `Rel atas depan | 2E6` | WOOD_A | 1120 × 40 × 40 | 934 | 0 |  |
| Kaki | `Kaki depan kanan | 2E1` | WOOD_A | 40 × 40 × 700 | 4,277 | 26 |  |
| Kaki | `Kaki depan kiri | 2E5` | WOOD_A | 40 × 40 × 700 | 3,585 | 10 |  |
| Kaki | `Rangka belakang (kaki belakang + rel) | 257` | WOOD_A | 1200 × 40 × 700 | 15,060 | 22 |  |
| Laci | `Front laci 1 | 2FB` | WOOD_A | 559.4 × 30 × 187.4 | 6,894 | 686 | 7 pulau (pecahan di alur/blend) |
| Laci | `Front laci 2 | 2F7` | WOOD_A | 559.4 × 30 × 187.4 | 6,948 | 692 | 5 pulau (pecahan di alur/blend) |
| Laci | `Front laci 3 | 303` | WOOD_A | 559.4 × 30 × 187.4 | 7,028 | 691 | 6 pulau (pecahan di alur/blend) |
| Laci | `Front laci 4 | 2FF` | WOOD_A | 559.4 × 30 × 187.4 | 7,088 | 531 | 6 pulau (pecahan di alur/blend) |
| Laci | `Front laci 5 | 30C` | WOOD_A | 559.4 × 30 × 187.4 | 6,910 | 685 | 7 pulau (pecahan di alur/blend) |
| Laci | `Front laci 6 | 308` | WOOD_A | 559.4 × 30 × 187.4 | 6,979 | 709 | 6 pulau (pecahan di alur/blend) |
| Laci | `Laci 1 / belakang 12 mm` | WOOD_B | 535.4 × 12 × 157.4 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 1 / dasar 7 mm` | WOOD_B | 535.4 × 498.3 × 7 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 1 / sisi kanan 12 mm` | WOOD_B | 12 × 498.3 × 157.4 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 1 / sisi kiri 12 mm` | WOOD_B | 12 × 498.3 × 157.4 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 2 / belakang 12 mm` | WOOD_B | 535.4 × 12 × 157.4 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 2 / dasar 7 mm` | WOOD_B | 535.4 × 498.3 × 7 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 2 / sisi kanan 12 mm` | WOOD_B | 12 × 498.3 × 157.4 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 2 / sisi kiri 12 mm` | WOOD_B | 12 × 498.3 × 157.4 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 3 / belakang 12 mm` | WOOD_B | 535.4 × 12 × 157.4 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 3 / dasar 7 mm` | WOOD_B | 535.4 × 498.3 × 7 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 3 / sisi kanan 12 mm` | WOOD_B | 12 × 498.3 × 157.4 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 3 / sisi kiri 12 mm` | WOOD_B | 12 × 498.3 × 157.4 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 4 / belakang 12 mm` | WOOD_B | 535.4 × 12 × 157.4 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 4 / dasar 7 mm` | WOOD_B | 535.4 × 498.3 × 7 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 4 / sisi kanan 12 mm` | WOOD_B | 12 × 498.3 × 157.4 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 4 / sisi kiri 12 mm` | WOOD_B | 12 × 498.3 × 157.4 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 5 / belakang 12 mm` | WOOD_B | 535.4 × 12 × 157.4 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 5 / dasar 7 mm` | WOOD_B | 535.4 × 498.3 × 7 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 5 / sisi kanan 12 mm` | WOOD_B | 12 × 498.3 × 157.4 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 5 / sisi kiri 12 mm` | WOOD_B | 12 × 498.3 × 157.4 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 6 / belakang 12 mm` | WOOD_B | 535.4 × 12 × 157.4 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 6 / dasar 7 mm` | WOOD_B | 535.4 × 498.3 × 7 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 6 / sisi kanan 12 mm` | WOOD_B | 12 × 498.3 × 157.4 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 6 / sisi kiri 12 mm` | WOOD_B | 12 × 498.3 × 157.4 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Hardware | `Handle laci 1 | 2F8` | HANDLE | 163.6 × 21 × 8 | 10,682 | 18 |  |
| Hardware | `Handle laci 2 | 2E7` | HANDLE | 163.6 × 21 × 8 | 12,362 | 23 |  |
| Hardware | `Handle laci 3 | 300` | HANDLE | 163.6 × 21 × 8 | 10,830 | 24 |  |
| Hardware | `Handle laci 4 | 2FC` | HANDLE | 163.6 × 21 × 8 | 12,342 | 28 |  |
| Hardware | `Handle laci 5 | 309` | HANDLE | 163.6 × 21 × 8 | 10,675 | 18 |  |
| Hardware | `Handle laci 6 | 305` | HANDLE | 163.6 × 21 × 8 | 12,363 | 35 |  |
| _ARSIP sisa DWG (tidak dipakai) | `Lama: front laci kanan atas | 262` | WOOD_A | 550 × 30 × 190 | 8,631 | 733 | arsip, dikecualikan dari view layer & render |
| _ARSIP sisa DWG (tidak dipakai) | `Lama: front laci kanan bawah | 27F` | WOOD_A | 550 × 30 × 190 | 2,359 | 35 | arsip, dikecualikan dari view layer & render |
| _ARSIP sisa DWG (tidak dipakai) | `Lama: front laci kanan tengah | 275` | WOOD_A | 550 × 30 × 190 | 7,029 | 697 | arsip, dikecualikan dari view layer & render |
| _ARSIP sisa DWG (tidak dipakai) | `Lama: front laci kiri bawah | 27A` | WOOD_A | 550 × 30 × 190 | 2,340 | 50 | arsip, dikecualikan dari view layer & render |
| _ARSIP sisa DWG (tidak dipakai) | `Lama: front laci kiri tengah | 270` | WOOD_A | 550 × 30 × 190 | 2,325 | 27 | arsip, dikecualikan dari view layer & render |
| _ARSIP sisa DWG (tidak dipakai) | `Lama: handle | 25D` | HANDLE | 163.6 × 21 × 8 | 12,346 | 41 | arsip, dikecualikan dari view layer & render |
| _ARSIP sisa DWG (tidak dipakai) | `Lama: handle | 26C` | HANDLE | 163.6 × 21 × 8 | 10,930 | 15 | arsip, dikecualikan dari view layer & render |
| _ARSIP sisa DWG (tidak dipakai) | `Lama: handle | 271` | HANDLE | 163.6 × 21 × 8 | 12,312 | 36 | arsip, dikecualikan dari view layer & render |
| _ARSIP sisa DWG (tidak dipakai) | `Lama: handle | 276` | HANDLE | 163.6 × 21 × 8 | 10,898 | 24 | arsip, dikecualikan dari view layer & render |
| _ARSIP sisa DWG (tidak dipakai) | `Lama: handle | 27B` | HANDLE | 163.6 × 21 × 8 | 12,338 | 36 | arsip, dikecualikan dari view layer & render |
| _ARSIP sisa DWG (tidak dipakai) | `Lama: kaki depan kiri | 2CE` | WOOD_A | 40 × 40 × 700 | 3,930 | 18 | arsip, dikecualikan dari view layer & render |
| _ARSIP sisa DWG (tidak dipakai) | `Lama: rel atas depan | 25A` | WOOD_A | 1143.6 × 40 × 40 | 3,205 | 37 | arsip, dikecualikan dari view layer & render |

**Kualitas mesh:** 26 dari 41 objek aktif manifold tertutup sepenuhnya; sisanya punya tepi terbuka seperti di kolom tabel (lihat *Masalah*).

**Masalah yang ditemukan dan perbaikan:**

- Dua rakitan tidak lengkap masing-masing → dirakit jadi satu dresser lengkap (lihat *Keputusan*).
- Front B digambar rapat satu sama lain (celah 0–0,3 mm) → disusun ulang rata dalam bukaan carcass (−1879,7 … −1308,6 mm) dengan celah 1,5 mm; tinggi front 190 → 187,4 mm; handle ikut.
- Carcass B tidak ada; carcass A (1183,4 mm) lebih sempit 16,6 mm dari rangka depan B (1200 mm) → carcass A dan rangka belakang A dilebarkan dengan skala X 1,0140 (tebal panel berubah 1,4 %, tidak terlihat).
- Carcass tidak punya panel belakang di DWG (rangka belakang = bingkai 40 mm, bagian tengah terbuka). Kotak laci tambahan terlihat dari belakang. Tidak ditambah panel karena tidak ada di DWG.
- Rel atas rangka belakang dan tepi atas carcass yang sama-sama membulat bertemu pada bidang yang sama → ada garis sambungan tipis bergerigi di tampak belakang (dua permukaan berimpit, bukan tembus; uji tembus 0 vertex). Sesuai DWG.
- Sisa mesh: front 531–712 tepi terbuka di alur handle, handle 18–35, kaki 10–26, rangka belakang 22 (semua di blend/alur, tidak terlihat).

**Keputusan / judgement call:**

- Rakitan final = rangka depan (2 kaki + rel) + 6 front + 6 handle dari B (digeser −1389, −580, 0 mm) + carcass & rangka belakang dari A (dilebarkan ke 1200 mm). Ukuran akhir 1200 × 605 × 700 mm.
- Semua sisa A (rel atas depan lama, kaki depan kiri lama, 5 front lama, 5 handle lama) disimpan di collection `_ARSIP sisa DWG (tidak dipakai)` (dikecualikan dari view layer & render), bukan dihapus, agar bisa dibandingkan.
- Penomoran laci: 1–2 baris atas (kiri, kanan), 3–4 tengah, 5–6 bawah.

**Keraguan yang tersisa:**

- Apakah desainer memang bermaksud melebarkan carcass ke 1200 mm (mengikuti rangka depan B) atau menyempitkan front B ke 1183 mm — saya pilih 1200 karena rangka depan B lengkap dan konsisten (2 × 40 + 2 × 559,4 + celah 1,1 = 1200). Kalau yang benar 1183, cukup skala X carcass & rangka belakang dikembalikan dan front B diskalakan 0,986.
- Satuan: header menyatakan inci, tetapi tinggi 700 / lebar 1183 hanya masuk akal sebagai mm.

**Uji tembus antar part** (vertex A di dalam B / B di dalam A):

- 6 pasangan handle ↔ front laci: handle terbenam 16 mm di alur front (sesuai DWG).

**Log build (otomatis):**

- Rangka belakang (kaki belakang + rel) (257) diskalakan X x1.0140 dari x0=1344.3 mm
- Badan kabinet (carcass + top) (261) diskalakan X x1.0140 dari x0=1344.3 mm
- Front laci 5 | 30C: tinggi 190.0 -> 187.4 mm, pusat geser -0.6 mm (fit kolom -1879.7..-1308.6 mm, celah 1.5 mm)
- Front laci 3 | 303: tinggi 190.0 -> 187.4 mm, pusat geser -0.5 mm (fit kolom -1879.7..-1308.6 mm, celah 1.5 mm)
- Front laci 1 | 2FB: tinggi 190.0 -> 187.4 mm, pusat geser -0.2 mm (fit kolom -1879.7..-1308.6 mm, celah 1.5 mm)
- Front laci 6 | 308: tinggi 190.0 -> 187.4 mm, pusat geser -0.6 mm (fit kolom -1879.7..-1308.6 mm, celah 1.5 mm)
- Front laci 4 | 2FF: tinggi 190.0 -> 187.4 mm, pusat geser -0.5 mm (fit kolom -1879.7..-1308.6 mm, celah 1.5 mm)
- Front laci 2 | 2F7: tinggi 190.0 -> 187.4 mm, pusat geser -0.2 mm (fit kolom -1879.7..-1308.6 mm, celah 1.5 mm)
- Laci 1: kotak laci sederhana ditambahkan (lebar 535, dalam 498, tinggi 157 mm)
- Laci 2: kotak laci sederhana ditambahkan (lebar 535, dalam 498, tinggi 157 mm)
- Laci 3: kotak laci sederhana ditambahkan (lebar 535, dalam 498, tinggi 157 mm)
- Laci 4: kotak laci sederhana ditambahkan (lebar 535, dalam 498, tinggi 157 mm)
- Laci 5: kotak laci sederhana ditambahkan (lebar 535, dalam 498, tinggi 157 mm)
- Laci 6: kotak laci sederhana ditambahkan (lebar 535, dalam 498, tinggi 157 mm)

**Verifikasi buka-ulang:** unit ['METRIC', 'CENTIMETERS', 1.0], 53 mesh, bbox aktif min [-600.0, -302.7, 0.0] max [600.0, 302.7, 700.0] mm, collection dikecualikan: ['_ARSIP sisa DWG (tidak dipakai)'], masalah: tidak ada. Thumbnail: `_preview/beechwood 6dw r.png` dan `_preview/beechwood 6dw r_belakang.png`.

### 2a. Perbaikan 30-10-2026: model dilengkapi dan disusun ulang per komponen konstruksi

Permintaan: base dan back panel tidak ada; struktur ulang per komponen seperti konstruksi furnitur. Skrip: `_skrip/perbaiki_6dwr.py` (dijalankan pada file hasil konversi 29-10). Cadangan file lama: `_versi_lama/beechwood 6dw r_SEBELUM_struktur_20261030.blend`. **Tabel komponen di atas sudah digantikan oleh daftar ini.**

**Struktur collection baru** (di bawah `PROD | Beechwood 6 Drawers`, root `PRODUCT_ROOT` tetap):

| Collection | Komponen | Ukuran potong (mm) | Material | Sumber | Sambungan (catatan) |
|---|---|---|---|---|---|
| 01 Carcass | Top (mitre 45°) | 1200 × 520 × 20, tepi lengkung R40 | WOOD_A | DWG 261, dipecah | mitre 45° di lengkung sudut + lamello/dowel |
| 01 Carcass | Sisi kiri / Sisi kanan (mitre 45°) | 611 × 520 × 20,3 | WOOD_A | DWG 261, dipecah | mitre 45° ke top |
| 01 Carcass | **Panel dasar 18 mm** | 1159,3 × 511 × 18 | WOOD_B | tambahan | dado/dowel ke sisi, rata bawah sisi (z 88,9) |
| 01 Carcass | **Panel belakang 9 mm** | 1159,3 × 591,1 × 9, sudut atas R20 | WOOD_A | tambahan | rebate di sisi, top & dasar; rata belakang carcass |
| 01 Carcass | **Partisi tengah 18 mm** | 573,1 × 511 × 18 | WOOD_B | tambahan | dado ke panel dasar dan bawah top |
| 01 Carcass | **Klos rel laci kiri/kanan baris 1–3** (6) | 501 × 60 × 19,7 | WOOD_B | tambahan | dudukan rel, rata muka dalam kaki depan |
| 02 Rangka depan | Kaki depan kiri / kanan | 40 × 40 × 700 | WOOD_A | DWG 2E5 / 2E1 | — |
| 02 Rangka depan | Rel atas depan | 1120 × 40 × 40 | WOOD_A | DWG 2E6 | purus-lubang ke kaki depan |
| 03 Rangka belakang | Kaki belakang kiri / kanan | 40,6 × 40 × 700 | WOOD_A | DWG 257, dipecah | lubang purus untuk rel |
| 03 Rangka belakang | Rel atas belakang | 1118,8 × 40 × 60 (termasuk lengkung sudut) | WOOD_A | DWG 257, dipecah | purus-lubang ke kaki belakang |
| 04 Laci / Laci 1–6 | Front laci n + Handle laci n | 559,4 × 187,4 × 30 / 163,6 × 21 × 8 | WOOD_A / HANDLE | DWG | front disekrup ke depan dalam |
| 04 Laci / Laci 1–6 | Sisi kiri, sisi kanan 12 mm | 500 × 140 × 12 | WOOD_B | tambahan | dovetail/dowel |
| 04 Laci / Laci 1–6 | **Depan dalam 12 mm** (baru) | 501,6 × 140 × 12 | WOOD_B | tambahan | front laci disekrup dari dalam |
| 04 Laci / Laci 1–6 | Belakang 12 mm | 501,6 × 123 × 12 | WOOD_B | tambahan | duduk di atas dasar laci |
| 04 Laci / Laci 1–6 | Dasar 7 mm | 501,6 × 476 × 7 | WOOD_B | tambahan | di antara sisi (alur) |

Total 60 objek mesh aktif (12 carcass, 3 rangka depan, 3 rangka belakang, 6 × 7 laci) + 12 arsip. Collection lama `Badan`, `Kaki`, `Hardware`, `Laci` dihapus; handle kini berada di collection lacinya masing-masing (tetap anak `DRAWER_n`, driver `Open (m)` tetap jalan). Setiap komponen punya properti `ukuran_potong_mm` dan `sambungan`.

**Perubahan dan keputusan:**

- **Carcass 261** (satu lembar bengkok top + 2 sisi, R dalam 20 / luar 40) dipecah dengan bidang mitre 45° lewat pusat lengkung (±559,7; 660) mm → top, sisi kiri, sisi kanan; potongan ditutup, ketiganya manifold tertutup (0 tepi terbuka).
- **Rangka belakang 257** (U terbalik) dipecah di muka dalam kaki (x −559,44 / +559,40) → 2 kaki + rel. Lengkung sudut dalam ikut rel. Mesh asli kaki kanan punya ±350 tepi non-manifold (muka bertumpuk dari tessellasi di telapak & sudut) → **kaki belakang kanan = cermin kaki belakang kiri** (37 tepi sisa, di zona sambungan rel).
- **Panel dasar & panel belakang** ditambahkan (tidak ada di DWG). Sudut atas panel belakang dibuat R20 mengikuti lengkung dalam carcass agar tidak menembus.
- **Partisi tengah** ditambahkan di belakang celah antar front (x −9…9) sebagai dudukan rel laci kolom dalam.
- **Kotak laci dibangun ulang**: lebar 525,6 (ruang rel 12,7 mm tiap sisi, rel tidak dimodelkan sesuai standar v2), dalam 500, tinggi 140, dasar laci terbawah 112 mm (di atas panel dasar 106,9). Kotak lama (lebar 535, menabrak area partisi, sisi & dasar saling tembus) dihapus.
- **Klos rel** 19,7 mm di sisi dalam carcass agar bidang rel rata dengan muka dalam kaki depan (x ±560), sehingga kotak laci tidak menabrak kaki depan.
- UV `UV meter` diperbarui per komponen: top & rel serat X, sisi & kaki serat Z.

**Verifikasi buka-ulang:** bbox 1200 × 605,4 × 700 mm (tidak berubah), semua objek punya parent & material, uji tembus BVH antar semua pasangan: **0 tembus** kecuali handle di alur front (sesuai DWG). Preview Workbench: `_preview/beechwood 6dw r.png`, `_belakang.png`, `_dalam.png` (top disembunyikan, laci 1 & 4 dibuka), `_bawah.png`.

**Keraguan yang tersisa:** tebal panel dasar 18 / belakang 9 / partisi 18 dan ukuran kotak laci adalah standar konstruksi, bukan dari DWG; sesuaikan jika ada gambar kerja. Apakah panel belakang mau WOOD_A (veneer, tampak dari belakang, pilihan saat ini) atau WOOD_B (plywood)?

## 3. `BEECHWOOD TALLBOY.dwg` → `BEECHWOOD TALLBOY.blend`

- **Sumber:** Drive id `1XY9qIZu8KNMEbDpDdYZNlyIjNBRS09qa`, 174,093 byte, format AC1032 (AutoCAD 2018), satuan: INSUNITS=4 (mm).
- **Isi DWG:** 18 3DSOLID + 1 LWPOLYLINE, layer 0.
- **Rute konversi:** Sama dengan Bedside.
- **Dimensi hasil (L × D × T):** 600 × 505.2 × 1100 mm; `dimensions_cm` di root = [60.0, 50.52, 110.0].
- **Nama produk di file:** `Beechwood Tallboy` (kategori `TALLBOY`).

**Komponen** (objek mesh; ukuran bbox mm; handle = handle entitas DWG, `pface` = mesh R14, `-` = tambahan):

| Collection | Objek | Peran | Ukuran (mm) | Muka | Sisa tepi terbuka | Catatan |
|---|---|---|---|---|---|---|
| Badan | `Badan kabinet (carcass + top) | 2DF` | WOOD_A | 600 × 420 × 1010 | 3,990 | 0 |  |
| Badan | `Panel belakang | 2E0` | WOOD_A | 520 × 9 × 970 | 6 | 0 |  |
| Badan | `Rel atas belakang | 2DE` | WOOD_A | 520 × 40 × 40 | 1,121 | 0 |  |
| Badan | `Rel atas depan | 2DD` | WOOD_A | 520 × 40 × 40 | 1,122 | 0 |  |
| Kaki | `Kaki belakang kanan | 2D4` | WOOD_A | 40 × 40 × 1100 | 4,261 | 14 |  |
| Kaki | `Kaki belakang kiri | 2DA` | WOOD_A | 40 × 40 × 1100 | 4,276 | 10 |  |
| Kaki | `Kaki depan kanan | 2D1` | WOOD_A | 40 × 40 × 1100 | 4,288 | 13 |  |
| Kaki | `Kaki depan kiri | 2D7` | WOOD_A | 40 × 40 × 1100 | 4,260 | 7 |  |
| Laci | `Front laci 1 | 2F6` | WOOD_A | 515.2 × 30 × 191 | 6,778 | 732 | 5 pulau (pecahan di alur/blend) |
| Laci | `Front laci 2 | 2F2` | WOOD_A | 515.2 × 30 × 191 | 6,776 | 725 | 5 pulau (pecahan di alur/blend) |
| Laci | `Front laci 3 | 2EE` | WOOD_A | 515.2 × 30 × 191 | 6,779 | 728 | 5 pulau (pecahan di alur/blend) |
| Laci | `Front laci 4 | 2EA` | WOOD_A | 515.2 × 30 × 191 | 6,791 | 731 | 5 pulau (pecahan di alur/blend) |
| Laci | `Front laci 5 | 2E6` | WOOD_A | 515.2 × 30 × 191 | 6,769 | 724 | 5 pulau (pecahan di alur/blend) |
| Laci | `Laci 1 / belakang 12 mm` | WOOD_B | 491.2 × 12 × 161 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 1 / dasar 7 mm` | WOOD_B | 491.2 × 398.2 × 7 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 1 / sisi kanan 12 mm` | WOOD_B | 12 × 398.2 × 161 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 1 / sisi kiri 12 mm` | WOOD_B | 12 × 398.2 × 161 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 2 / belakang 12 mm` | WOOD_B | 491.2 × 12 × 161 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 2 / dasar 7 mm` | WOOD_B | 491.2 × 398.2 × 7 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 2 / sisi kanan 12 mm` | WOOD_B | 12 × 398.2 × 161 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 2 / sisi kiri 12 mm` | WOOD_B | 12 × 398.2 × 161 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 3 / belakang 12 mm` | WOOD_B | 491.2 × 12 × 161 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 3 / dasar 7 mm` | WOOD_B | 491.2 × 398.2 × 7 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 3 / sisi kanan 12 mm` | WOOD_B | 12 × 398.2 × 161 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 3 / sisi kiri 12 mm` | WOOD_B | 12 × 398.2 × 161 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 4 / belakang 12 mm` | WOOD_B | 491.2 × 12 × 161 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 4 / dasar 7 mm` | WOOD_B | 491.2 × 398.2 × 7 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 4 / sisi kanan 12 mm` | WOOD_B | 12 × 398.2 × 161 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 4 / sisi kiri 12 mm` | WOOD_B | 12 × 398.2 × 161 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 5 / belakang 12 mm` | WOOD_B | 491.2 × 12 × 161 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 5 / dasar 7 mm` | WOOD_B | 491.2 × 398.2 × 7 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 5 / sisi kanan 12 mm` | WOOD_B | 12 × 398.2 × 161 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Laci | `Laci 5 / sisi kiri 12 mm` | WOOD_B | 12 × 398.2 × 161 | 6 | 0 | tambahan standar v2 (kotak laci), bukan dari DWG |
| Hardware | `Handle laci 1 | 2F3` | HANDLE | 163.6 × 21 × 8 | 10,679 | 18 |  |
| Hardware | `Handle laci 2 | 2EF` | HANDLE | 163.6 × 21 × 8 | 10,687 | 21 |  |
| Hardware | `Handle laci 3 | 2EB` | HANDLE | 163.6 × 21 × 8 | 10,692 | 22 |  |
| Hardware | `Handle laci 4 | 2E7` | HANDLE | 163.6 × 21 × 8 | 10,699 | 23 |  |
| Hardware | `Handle laci 5 | 2E3` | HANDLE | 163.6 × 21 × 8 | 10,714 | 17 |  |

**Kualitas mesh:** 24 dari 38 objek aktif manifold tertutup sepenuhnya; sisanya punya tepi terbuka seperti di kolom tabel (lihat *Masalah*).

**Masalah yang ditemukan dan perbaikan:**

- Lima front (5 × 194,7 = 973,5 mm) lebih tinggi 3,5 mm dari bukaan carcass (970 mm) sehingga front teratas menembus rel atas 2,9 mm → front disusun ulang rata dalam bukaan dengan celah 1,5 mm (tinggi tiap front 191 mm, pergeseran pusat ≤ 2,6 mm), handle ikut.
- Handle terbenam 16 mm ke dalam front (alur handle, sesuai DWG).
- Sisa mesh: front 724–732 tepi terbuka di alur handle, handle 17–23, kaki 7–14; carcass, rel, panel belakang bersih (manifold).

**Keputusan / judgement call:**

- Carcass + top satu solid di DWG → satu objek. Kotak laci sederhana ditambahkan (standar v2). Laci dinomori dari atas (1) ke bawah (5).

**Keraguan yang tersisa:**

- Tidak ada; tallboy 600 × 505 × 1100 mm.

**Uji tembus antar part** (vertex A di dalam B / B di dalam A):

- 5 pasangan handle ↔ front laci: handle terbenam 16 mm di alur front (sesuai DWG).

**Log build (otomatis):**

- Front laci 5 | 2E6: tinggi 194.7 -> 191.0 mm, pusat geser +0.1 mm (fit kolom -913.9..56.1 mm, celah 1.5 mm)
- Front laci 4 | 2EA: tinggi 194.7 -> 191.0 mm, pusat geser -0.6 mm (fit kolom -913.9..56.1 mm, celah 1.5 mm)
- Front laci 3 | 2EE: tinggi 194.7 -> 191.0 mm, pusat geser -1.3 mm (fit kolom -913.9..56.1 mm, celah 1.5 mm)
- Front laci 2 | 2F2: tinggi 194.7 -> 191.0 mm, pusat geser -1.9 mm (fit kolom -913.9..56.1 mm, celah 1.5 mm)
- Front laci 1 | 2F6: tinggi 194.7 -> 191.0 mm, pusat geser -2.6 mm (fit kolom -913.9..56.1 mm, celah 1.5 mm)
- Laci 1: kotak laci sederhana ditambahkan (lebar 491, dalam 398, tinggi 161 mm)
- Laci 2: kotak laci sederhana ditambahkan (lebar 491, dalam 398, tinggi 161 mm)
- Laci 3: kotak laci sederhana ditambahkan (lebar 491, dalam 398, tinggi 161 mm)
- Laci 4: kotak laci sederhana ditambahkan (lebar 491, dalam 398, tinggi 161 mm)
- Laci 5: kotak laci sederhana ditambahkan (lebar 491, dalam 398, tinggi 161 mm)

**Verifikasi buka-ulang:** unit ['METRIC', 'CENTIMETERS', 1.0], 38 mesh, bbox aktif min [-300.0, -252.6, 0.0] max [300.0, 252.6, 1100.0] mm, collection dikecualikan: -, masalah: tidak ada. Thumbnail: `_preview/BEECHWOOD TALLBOY.png` dan `_preview/BEECHWOOD TALLBOY_belakang.png`.

### 3a. Perbaikan 30-10-2026: base dilengkapi, per komponen konstruksi

Skrip: `_skrip/perbaiki_lemari.py` (+ `_skrip/konstruksi_util.py`). Cadangan: `_versi_lama/BEECHWOOD TALLBOY_SEBELUM_struktur_20261030.blend`. Laporan mesin: `_skrip/laporan_json/BEECHWOOD TALLBOY_perbaikan.json`. Preview Workbench resolusi rendah: `_preview/BEECHWOOD TALLBOY.png`, `_belakang`, `_dalam`, `_bawah`. **Struktur collection dan daftar komponen di atas sudah digantikan oleh bagian ini.**

**Struktur:** `01 Carcass` (Top, Sisi kiri, Sisi kanan, Panel dasar 18 mm, 10 klos rel) · `02 Rangka depan` (2 kaki depan, rel atas depan) · `03 Rangka belakang` (2 kaki belakang, rel atas belakang, panel belakang) · `04 Laci / Laci 1–5` (masing-masing 7 part). Total 56 mesh aktif.

- **Panel dasar tidak ada di DWG** (bawah carcass terbuka) → ditambah **Panel dasar 18 mm** (z 90–108) bertakik kaki 40 × 40: lebar 560 di antara sisi, lidah 520 di antara kaki dari belakang front (y −217,6) sampai panel belakang.
- **Carcass 2DF** dipecah mitre 45° lewat pusat lengkung (±260; 1060) → top 600 × 420 × 20, sisi 1010 × 420 × 20 (bidang potong sisi dibatasi x = 0 karena lemari tinggi).
- **Front laci** di DWG tidak di tengah (celah kiri 0, kanan 4,8 mm; handle sudah di tengah) → 5 front digeser +2,4 mm, celah 2,4 mm kiri = kanan.
- **Klos rel 20 mm** (10) dan **kotak laci dibangun ulang** 494,6 × 400 × 140 mm (+ depan dalam), laci terbawah mulai z 113,1 di atas panel dasar.
- Uji tembus: 0, kecuali handle di alur front dan 1 vertex di garis mitre top/sisi.

## 4. `BEECHWOOD DINNING TABLE  ALTFIELD.dwg` → `BEECHWOOD DINNING TABLE  ALTFIELD.blend`

- **Sumber:** Drive id `1sYXFlK5Ubo3ABQcYOyXO0Q4KSV_LbIp_`, 114,988 byte, format AC1032 (AutoCAD 2018), satuan: INSUNITS=1 (inci) di header, angka jelas mm.
- **Isi DWG:** 13 3DSOLID + 55 LINE + 10 LWPOLYLINE (tampak 2D) + 2 VIEWPORT; layer 0 dan Defpoints; blok `_ArchTick`.
- **Rute konversi:** Sama dengan Bedside. Peringatan dwg2obj: tabel `datidx` tak terbaca dan handle 29F (top) punya lebih dari satu blob ACIS (riwayat edit) → versi terakhir dipakai (2100 × 800 × 30 mm, cocok dengan posisi kaki).
- **Dimensi hasil (L × D × T):** 2100 × 800 × 750 mm; `dimensions_cm` di root = [210.0, 80.0, 75.0].
- **Nama produk di file:** `Beechwood Dining Table Altfield` (kategori `MEJA_MAKAN`).

**Komponen** (objek mesh; ukuran bbox mm; handle = handle entitas DWG, `pface` = mesh R14, `-` = tambahan):

| Collection | Objek | Peran | Ukuran (mm) | Muka | Sisa tepi terbuka | Catatan |
|---|---|---|---|---|---|---|
| Badan | `Top meja | 29F` | WOOD_A | 2100 × 800 × 30 | 665 | 16 |  |
| Kaki | `Kaki kanan belakang | 28E` | WOOD_A | 50 × 100 × 720 | 2,098 | 0 |  |
| Kaki | `Kaki kanan depan | 291` | WOOD_A | 50 × 100 × 720 | 2,213 | 0 |  |
| Kaki | `Kaki kiri belakang | 274` | WOOD_A | 50 × 100 × 720 | 2,096 | 0 |  |
| Kaki | `Kaki kiri depan | 278` | WOOD_A | 50 × 100 × 720 | 2,213 | 0 |  |
| Kaki | `Kaki ujung kanan | 2A7` | WOOD_A | 100 × 50 × 720 | 2,096 | 0 |  |
| Kaki | `Kaki ujung kiri | 27C` | WOOD_A | 100 × 50 × 720 | 2,098 | 0 |  |
| Kaki | `Palang atas kanan | 2BB` | WOOD_A | 50 × 400 × 50 | 10 | 0 |  |
| Kaki | `Palang atas kiri | 2B7` | WOOD_A | 50 × 400 × 50 | 10 | 0 |  |
| Kaki | `Palang bawah kanan | 2B9` | WOOD_A | 50 × 400 × 50 | 10 | 0 |  |
| Kaki | `Palang bawah kiri | 2B4` | WOOD_A | 50 × 400 × 50 | 10 | 0 |  |
| Kaki | `Rel atas memanjang | 2BC` | WOOD_A | 1700 × 50 × 50 | 14 | 0 |  |
| Kaki | `Rel bawah memanjang | 2BA` | WOOD_A | 1700 × 50 × 50 | 14 | 0 |  |

**Kualitas mesh:** 12 dari 13 objek aktif manifold tertutup sepenuhnya; sisanya punya tepi terbuka seperti di kolom tabel (lihat *Masalah*).

**Masalah yang ditemukan dan perbaikan:**

- Garis 2D (LINE/LWPOLYLINE, tampak gambar) diabaikan — tidak diimpor.
- Top meja 16 tepi terbuka (lubang mikro di blend sudut); 12 bagian lain manifold bersih.
- Empat pasang palang/rel hanya bersentuhan (bbox tumpang tindih 50 × 50 × 50 di sambungan, uji tembus 0 vertex) — sambungan rangka normal.

**Keputusan / judgement call:**

- Kaki dinamai menurut posisi dilihat dari depan (−Y): kiri/kanan depan/belakang + dua kaki ujung di tengah lebar; palang H kiri/kanan atas/bawah; dua rel memanjang.

**Keraguan yang tersisa:**

- Satuan header inci, tetapi 2100 × 800 × 750 hanya masuk akal sebagai mm.

**Uji tembus antar part** (vertex A di dalam B / B di dalam A):

- Tidak ada part yang saling menembus.
- 4 pasangan lain hanya bersentuhan (bbox tumpang tindih, 0 vertex di dalam).

**Log build (otomatis):**


**Verifikasi buka-ulang:** unit ['METRIC', 'CENTIMETERS', 1.0], 13 mesh, bbox aktif min [-1050.0, -400.0, 0.0] max [1050.0, 400.0, 750.0] mm, collection dikecualikan: -, masalah: tidak ada. Thumbnail: `_preview/BEECHWOOD DINNING TABLE  ALTFIELD.png` dan `_preview/BEECHWOOD DINNING TABLE  ALTFIELD_belakang.png`.

### 4a. Perbaikan 30-10-2026: susun ulang per sub-rakitan

Skrip: `_skrip/perbaiki_meja.py` (+ `_skrip/konstruksi_util.py`). Cadangan: `_versi_lama/BEECHWOOD DINNING TABLE  ALTFIELD_SEBELUM_struktur_20261030.blend`. Laporan mesin: `_skrip/laporan_json/BEECHWOOD DINNING TABLE  ALTFIELD_perbaikan.json`. Preview Workbench resolusi rendah: `_preview/BEECHWOOD DINNING TABLE  ALTFIELD.png`, `_belakang`, `_dalam`, `_bawah`. **Struktur collection dan daftar komponen di atas sudah digantikan oleh bagian ini.**

Meja ini sudah terpisah per komponen di DWG, lengkap dengan takik half-lap di persilangan palang dan rel memanjang, jadi tidak ada part yang ditambah.

**Struktur:** `01 Top` (Top meja) · `02 Rangka kaki kiri` (kaki kiri depan/belakang, palang atas/bawah kiri) · `03 Rangka kaki kanan` (idem kanan) · `04 Rangka tengah memanjang` (rel atas/bawah memanjang, kaki ujung kiri/kanan). Tiap part diberi properti `sambungan` (purus-lubang / half-lap).

- Lubang mikro top meja ditutup: tepi non-manifold 23 → 19 (sisa di blend sudut, tidak terlihat).
- Uji tembus: 0.

## 5. `SP 05 ALTFIELD CREDENZA.dwg` → `SP 05 ALTFIELD CREDENZA.blend`

- **Sumber:** Drive id `1OYkTYSe136mHDLnzNEkYhK4K8ptBf8Gf`, 38,665,124 byte, format AC1014 (AutoCAD R14), satuan: tanpa INSUNITS; angka = cm.
- **Isi DWG:** DWG R14 (38,7 MB): **bukan solid**, melainkan 43.449 POLYLINE_PFACE (172.543 vertex, 86.709 muka) + 160.640 LINE (148.883 di antaranya panjang 0) + 1 LWPOLYLINE, dalam blok `SP_05_ALTFIELD_CREDENZA_DW` (1 INSERT, rotasi 180°) dan blok `SUMELE` (628 pface, tidak di-insert → tidak tampak, diabaikan). Model ala SketchUp; warna ACI 18 = handle & panel cekung pintu, 23 = badan/pintu/kaki, 254 = panel cekung pintu, 0 = serpihan.
- **Rute konversi:** DWG → `dwgread -O JSON` (LibreDWG) → ekstrak POLYLINE_PFACE (`credenza_extract.py`: indeks vertind > 32767 = indeks negatif/tepi tak terlihat; vertex korup bernilai 1e+96…1e+214 dibuang beserta mukanya) → OBJ per warna (cm) → Blender (skala 0,01) → weld 0,2 mm → pisah pulau lepas → pintu 1 & 4 yang menyatu dengan carcass dipisah menurut kotak muka → pulau yang memetakan ke part yang sama digabung.
- **Dimensi hasil (L × D × T):** 1800 × 658.1 × 900 mm; `dimensions_cm` di root = [180.0, 65.81, 90.0].
- **Nama produk di file:** `Altfield Credenza SP 05` (kategori `CREDENZA`).

**Komponen** (objek mesh; ukuran bbox mm; handle = handle entitas DWG, `pface` = mesh R14, `-` = tambahan):

| Collection | Objek | Peran | Ukuran (mm) | Muka | Sisa tepi terbuka | Catatan |
|---|---|---|---|---|---|---|
| Badan | `Badan kabinet (carcass + top)` | WOOD_A | 1800 × 590.6 × 708.8 | 23 | 9 |  |
| Badan | `Panel belakang` | WOOD_A | 1761.7 × 6.8 × 670.5 | 6 | 0 |  |
| Badan | `Rak bay 1` | WOOD_A | 411.7 × 583.9 × 22.5 | 10 | 0 |  |
| Badan | `Rak bay 2` | WOOD_A | 429.7 × 583.9 × 22.5 | 14 | 0 |  |
| Badan | `Rak bay 3` | WOOD_A | 429.7 × 583.9 × 22.5 | 14 | 0 |  |
| Badan | `Rak bay 4` | WOOD_A | 411.7 × 583.9 × 22.5 | 10 | 0 |  |
| Badan | `Sekat vertikal 1` | WOOD_A | 28.1 × 583.9 × 652.6 | 24 | 0 |  |
| Badan | `Sekat vertikal 2` | WOOD_A | 28.1 × 583.9 × 652.6 | 24 | 0 |  |
| Badan | `Sekat vertikal 3` | WOOD_A | 28.1 × 583.9 × 652.6 | 25 | 6 |  |
| Kaki | `Kaki kanan` | WOOD_A | 39.4 × 590.6 × 191.2 | 1,333 | 16 |  |
| Kaki | `Kaki kiri` | WOOD_A | 39.4 × 590.6 × 191.2 | 1,348 | 42 |  |
| Kaki | `Palang kaki tengah` | WOOD_A | 1620 × 39.4 × 191.2 | 1,068 | 53 |  |
| Pintu | `Pintu 1` | WOOD_A | 447.8 × 28.1 × 708.8 | 1,420 | 42 |  |
| Pintu | `Pintu 2` | WOOD_A | 447.7 × 28.1 × 708.8 | 1,422 | 26 |  |
| Pintu | `Pintu 3` | WOOD_A | 447.7 × 28.1 × 708.8 | 1,405 | 33 |  |
| Pintu | `Pintu 4` | WOOD_A | 447.7 × 28.1 × 708.8 | 1,404 | 26 |  |
| Hardware | `Handle pintu 1` | HANDLE | 5.6 × 39.4 × 56.3 | 7,800 | 60 |  |
| Hardware | `Handle pintu 2` | HANDLE | 5.6 × 39.4 × 56.3 | 7,768 | 80 |  |
| Hardware | `Handle pintu 3` | HANDLE | 5.6 × 39.4 × 56.3 | 7,692 | 55 |  |
| Hardware | `Handle pintu 4` | HANDLE | 5.6 × 39.4 × 56.3 | 7,780 | 85 |  |
| _ARSIP sisa DWG (tidak dipakai) | `Panel dalam sekat 1 (tersembunyi)` | WOOD_A | 20.3 × 471.4 × 540.1 | 6 | 0 | arsip, dikecualikan dari view layer & render |
| _ARSIP sisa DWG (tidak dipakai) | `Panel dalam sekat 2 (tersembunyi)` | WOOD_A | 20.2 × 471.4 × 540.1 | 6 | 0 | arsip, dikecualikan dari view layer & render |
| _ARSIP sisa DWG (tidak dipakai) | `Panel dalam sekat 3 (tersembunyi)` | WOOD_A | 20.2 × 471.4 × 540.1 | 6 | 0 | arsip, dikecualikan dari view layer & render |

**Kualitas mesh:** 5 dari 20 objek aktif manifold tertutup sepenuhnya; sisanya punya tepi terbuka seperti di kolom tabel (lihat *Masalah*).

**Masalah yang ditemukan dan perbaikan:**

- Pintu 1 dan 4 menyatu dengan carcass setelah weld (berbagi vertex) → dipisah dengan kotak x pintu (dari pengukuran bidang muka pintu: pintu overlay 447,7 mm, mulai x = 0 / 450 / 900 / 1351), dengan pengecualian muka carcass yang menghadap −Y pada bidang belakang pintu dan zona handle.
- Panel cekung pintu (warna 18/254, muka datar di y 42,8 & 46,1 cm) dan pelat belakang handle (warna 23) terpisah di DWG → digabung ke objek pintu/handle-nya.
- Tiga panel tipis 20 × 471 × 540 mm berada **seluruhnya di dalam** sekat vertikal 28 mm (geometri tersembunyi) → disimpan di `_ARSIP`, bukan dihapus.
- 27 serpihan warna 0 (< 2 mm, di kaki) dan semua LINE diabaikan.
- Mesh SketchUp tidak tertutup (shell terbuka, muka dalam) → jumlah tepi non-manifold bukan indikator kerusakan di sini; uji tembus antar part juga tidak andal untuk shell terbuka (angka kecil 1–11 vertex adalah muka yang berimpit pada sambungan rak/sekat ke carcass).

**Keputusan / judgement call:**

- Satuan cm (180 × 65,8 × 90 → 1,80 × 0,66 × 0,90 m, credenza 4 pintu).
- Blok `SUMELE` tidak di-insert di model space → tidak diekstrak.
- Tidak ada laci; pintu tidak diberi engsel/driver (di luar standar v2 yang hanya mendefinisikan laci).

**Keraguan yang tersisa:**

- Nama file bukan 'BEECHWOOD' (SP 05 Altfield) — diproses apa adanya sebagai koleksi yang sama sesuai permintaan.

**Uji tembus antar part** (vertex A di dalam B / B di dalam A):

- `Badan kabinet (carcass + top)` ↔ `Panel belakang`: bbox tumpang tindih 1761.7 × 6.8 × 670.5 mm, 0 / 1 vertex.
- `Badan kabinet (carcass + top)` ↔ `Sekat vertikal 3`: bbox tumpang tindih 28.1 × 583.9 × 652.6 mm, 0 / 9 vertex.
- `Badan kabinet (carcass + top)` ↔ `Sekat vertikal 2`: bbox tumpang tindih 28.1 × 583.9 × 652.6 mm, 0 / 4 vertex.
- `Badan kabinet (carcass + top)` ↔ `Sekat vertikal 1`: bbox tumpang tindih 28.1 × 583.9 × 652.6 mm, 1 / 4 vertex.
- `Badan kabinet (carcass + top)` ↔ `Rak bay 1`: bbox tumpang tindih 411.7 × 583.9 × 22.5 mm, 0 / 5 vertex.
- `Badan kabinet (carcass + top)` ↔ `Rak bay 2`: bbox tumpang tindih 429.7 × 583.9 × 22.5 mm, 0 / 11 vertex.
- `Badan kabinet (carcass + top)` ↔ `Rak bay 3`: bbox tumpang tindih 429.7 × 583.9 × 22.5 mm, 0 / 11 vertex.
- `Badan kabinet (carcass + top)` ↔ `Rak bay 4`: bbox tumpang tindih 411.7 × 583.9 × 22.5 mm, 0 / 5 vertex.
- `Palang kaki tengah` ↔ `Kaki kiri`: bbox tumpang tindih 39.4 × 39.4 × 191.2 mm, 0 / 6 vertex.
- `Palang kaki tengah` ↔ `Kaki kanan`: bbox tumpang tindih 39.4 × 39.4 × 191.2 mm, 9 / 7 vertex.
- 6 pasangan lain hanya bersentuhan (bbox tumpang tindih, 0 vertex di dalam).

**Log build (otomatis):**

- pisah 'Pintu 1' dari warna_1: 1418 muka
- pisah 'Pintu 2' dari warna_1: 1419 muka
- pisah 'Pintu 3' dari warna_1: 1401 muka
- pisah 'Pintu 4' dari warna_1: 1402 muka
- objek impor 'warna_2' diabaikan (52 muka, serpihan)
- 'Handle pintu 3': 2 pulau digabung jadi satu objek (7807 muka)
- 'Pintu 4': 3 pulau digabung jadi satu objek (1404 muka)
- 'Handle pintu 2': 2 pulau digabung jadi satu objek (7896 muka)
- 'Handle pintu 1': 2 pulau digabung jadi satu objek (7906 muka)
- 'Handle pintu 4': 2 pulau digabung jadi satu objek (7906 muka)
- 'Pintu 3': 4 pulau digabung jadi satu objek (1405 muka)
- 'Pintu 2': 4 pulau digabung jadi satu objek (1423 muka)
- 'Pintu 1': 3 pulau digabung jadi satu objek (1420 muka)

**Verifikasi buka-ulang:** unit ['METRIC', 'CENTIMETERS', 1.0], 23 mesh, bbox aktif min [-900.0, -329.1, 0.0] max [900.0, 329.1, 900.0] mm, collection dikecualikan: ['_ARSIP sisa DWG (tidak dipakai)'], masalah: tidak ada. Thumbnail: `_preview/SP 05 ALTFIELD CREDENZA.png` dan `_preview/SP 05 ALTFIELD CREDENZA_belakang.png`.

### 5a. Perbaikan 30-10-2026: carcass jadi panel tertutup, per komponen konstruksi

Skrip: `_skrip/perbaiki_credenza.py` (+ `_skrip/konstruksi_util.py`). Cadangan: `_versi_lama/SP 05 ALTFIELD CREDENZA_SEBELUM_struktur_20261030.blend`. Laporan mesin: `_skrip/laporan_json/SP 05 ALTFIELD CREDENZA_perbaikan.json`. Preview Workbench resolusi rendah: `_preview/SP 05 ALTFIELD CREDENZA.png`, `_belakang`, `_dalam`, `_bawah`. **Struktur collection dan daftar komponen di atas sudah digantikan oleh bagian ini.**

**Struktur:** `01 Carcass` (Top, Panel dasar, Sisi kiri, Sisi kanan, Panel belakang, Sekat vertikal 1–3, Rak bay 1–4) · `02 Pintu / Pintu 1–4` (pintu + handle) · `03 Kaki` (kaki kiri, kaki kanan, palang kaki tengah). Total 23 mesh aktif + 7 arsip.

- **Carcass** di DWG hanya shell terbuka 23 muka (top, dasar, sisi jadi satu objek) → diganti **4 panel tertutup 28,1 mm bersambungan mitre 45°**, persis di sudut DWG: Top & Panel dasar 1800 × 590,6, Sisi 708,7 × 590,6. Shell lama ke `_ARSIP`.
- **Sekat vertikal 1–3** (shell dengan muka dalam) dibangun ulang jadi panel tertutup 652,5 × 583,9 × 28,1 mm, pas di antara dasar dan top; versi lama ke `_ARSIP`.
- Rak bay masuk alur 4 mm di sekat (terdeteksi sebagai tembus 4 vertex; **sesuai DWG**, dado). Panel belakang 6,8 mm masuk alur 9 mm di sisi/top/dasar (sesuai DWG).
- Pintu, handle, dan kaki tidak diubah (shell SketchUp; non-manifold bukan indikator kerusakan). Pintu belum diberi engsel/driver (standar v2 hanya mendefinisikan laci).

## 6. `BEECHWOOD DINNING CHAIR.dwg` → `BEECHWOOD DINNING CHAIR.blend`

- **Sumber:** Drive id `1wAbsTwZHmLsiTkghvLHFwpGjnZagtYVJ`, 409,854 byte, format AC1032 (AutoCAD 2018), satuan: INSUNITS=4 (mm).
- **Isi DWG:** 10 3DSOLID, layer 0, warna merah (ACI 1). Solid 2CC kosong (69 byte, tanpa data ACIS).
- **Rute konversi:** Sama dengan Bedside. 9 solid punya blob SAB; 2CC dibuang.
- **Dimensi hasil (L × D × T):** 550.9 × 620.2 × 858.1 mm; `dimensions_cm` di root = [55.09, 62.02, 85.81].
- **Nama produk di file:** `Beechwood Dining Chair` (kategori `KURSI_MAKAN`).

**Komponen** (objek mesh; ukuran bbox mm; handle = handle entitas DWG, `pface` = mesh R14, `-` = tambahan):

| Collection | Objek | Peran | Ukuran (mm) | Muka | Sisa tepi terbuka | Catatan |
|---|---|---|---|---|---|---|
| Badan | `Dudukan baji belakang | 2E7` | WOOD_A | 480.6 × 253 × 61 | 6,296 | 102 |  |
| Badan | `Dudukan baji depan | 2E4` | WOOD_A | 530.6 × 253 × 61 | 5,303 | 120 |  |
| Badan | `Dudukan baji kanan | 2E1` | WOOD_A | 250.5 × 490.9 × 61 | 5,655 | 113 |  |
| Badan | `Dudukan baji kiri | 2E1` | WOOD_A | 250.5 × 490.9 × 61 | 5,470 | 101 |  |
| Kaki | `Palang belakang | 2C6` | WOOD_A | 477.6 × 30 × 45 | 1,529 | 0 |  |
| Kaki | `Palang depan | 2C3` | WOOD_A | 477.6 × 30 × 45 | 1,542 | 0 |  |
| Kaki | `Palang samping kanan | 2C0` | WOOD_A | 50.3 × 402.1 × 50.7 | 1,071 | 78 |  |
| Kaki | `Palang samping kiri | 2BD` | WOOD_A | 50.3 × 402.1 × 50.7 | 1,058 | 62 |  |
| Kaki | `Rangka samping kanan (kaki + sandaran) | 2C9` | WOOD_A | 67.6 × 620.2 × 858.1 | 6,782 | 415 |  |
| Kaki | `Rangka samping kiri (kaki + sandaran) | 2BA` | WOOD_A | 67.6 × 620.2 × 858.1 | 6,056 | 423 |  |

**Kualitas mesh:** 2 dari 10 objek aktif manifold tertutup sepenuhnya; sisanya punya tepi terbuka seperti di kolom tabel (lihat *Masalah*).

**Masalah yang ditemukan dan perbaikan:**

- Dudukan terdiri dari **empat baji segitiga** (pola diagonal): solid 2E4 = baji depan, 2E7 = baji belakang, 2E1 = baji kiri + kanan dalam satu solid → 2E1 dipisah menjadi dua objek (`Dudukan baji kiri` / `kanan`). Awalnya saya kira 2E1 dan 2E4+2E7 adalah dua versi dudukan yang tumpang tindih; pemeriksaan bidang datar solid (muka segitiga) dan render menunjukkan keempatnya saling melengkapi.
- Baji dudukan menempati ketinggian yang sama dengan palang samping/depan/belakang (z 400–461 vs 405–460): palang berada di dalam volume dudukan. Ujung palang masuk ke rangka samping (tenon). Keduanya sesuai DWG (rangka tersembunyi di dalam dudukan) → tidak diubah; tercatat di daftar tembus.
- Rangka samping (kaki + sandaran, bentuk lengkung dengan permukaan spline) menyisakan 415–423 tepi terbuka; baji dudukan 101–120; palang samping 62–78; palang depan/belakang bersih.

**Keputusan / judgement call:**

- Depan = −Y (sandaran di +Y), tidak perlu rotasi. Semua kayu (WOOD_A); tidak ada petunjuk material kain di DWG.

**Keraguan yang tersisa:**

- Jika dudukan sebenarnya berlapis kain, ganti peran material empat baji dudukan ke KAIN.

**Uji tembus antar part** (vertex A di dalam B / B di dalam A):

- `Rangka samping kiri (kaki + sandaran) | 2BA` ↔ `Palang samping kiri | 2BD`: bbox tumpang tindih 50.3 × 402.1 × 50.7 mm, 113 / 0 vertex.
- `Rangka samping kiri (kaki + sandaran) | 2BA` ↔ `Palang depan | 2C3`: bbox tumpang tindih 29.9 × 30 × 45 mm, 1 / 134 vertex.
- `Rangka samping kiri (kaki + sandaran) | 2BA` ↔ `Palang belakang | 2C6`: bbox tumpang tindih 29.9 × 30 × 45 mm, 1 / 133 vertex.
- `Rangka samping kiri (kaki + sandaran) | 2BA` ↔ `Dudukan baji depan | 2E4`: bbox tumpang tindih 56.4 × 253 × 61 mm, 2 / 1056 vertex.
- `Rangka samping kiri (kaki + sandaran) | 2BA` ↔ `Dudukan baji belakang | 2E7`: bbox tumpang tindih 31.4 × 253 × 61 mm, 128 / 919 vertex.
- `Rangka samping kiri (kaki + sandaran) | 2BA` ↔ `Dudukan baji kiri | 2E1`: bbox tumpang tindih 62.8 × 490.9 × 61 mm, 6 / 2183 vertex.
- `Palang samping kiri | 2BD` ↔ `Dudukan baji depan | 2E4`: bbox tumpang tindih 47.7 × 204.9 × 50.7 mm, 0 / 15 vertex.
- `Palang samping kiri | 2BD` ↔ `Dudukan baji belakang | 2E7`: bbox tumpang tindih 22.7 × 197.2 × 50.7 mm, 43 / 146 vertex.
- `Palang samping kiri | 2BD` ↔ `Dudukan baji kiri | 2E1`: bbox tumpang tindih 50.3 × 402.1 × 50.7 mm, 815 / 107 vertex.
- `Palang samping kanan | 2C0` ↔ `Rangka samping kanan (kaki + sandaran) | 2C9`: bbox tumpang tindih 50.3 × 402.1 × 50.7 mm, 49 / 532 vertex.
- `Palang samping kanan | 2C0` ↔ `Dudukan baji depan | 2E4`: bbox tumpang tindih 49.7 × 204.9 × 50.7 mm, 82 / 29 vertex.
- `Palang samping kanan | 2C0` ↔ `Dudukan baji belakang | 2E7`: bbox tumpang tindih 24.8 × 197.2 × 50.7 mm, 0 / 872 vertex.
- `Palang samping kanan | 2C0` ↔ `Dudukan baji kanan | 2E1`: bbox tumpang tindih 50.3 × 402.1 × 50.7 mm, 827 / 475 vertex.
- `Palang depan | 2C3` ↔ `Rangka samping kanan (kaki + sandaran) | 2C9`: bbox tumpang tindih 31.9 × 30 × 45 mm, 126 / 0 vertex.
- `Palang depan | 2C3` ↔ `Dudukan baji depan | 2E4`: bbox tumpang tindih 477.6 × 30 × 45 mm, 1026 / 0 vertex.
- `Palang depan | 2C3` ↔ `Dudukan baji kiri | 2E1`: bbox tumpang tindih 217.6 × 27.3 × 45 mm, 24 / 15 vertex.
- `Palang depan | 2C3` ↔ `Dudukan baji kanan | 2E1`: bbox tumpang tindih 217.5 × 27.3 × 45 mm, 25 / 5 vertex.
- `Palang belakang | 2C6` ↔ `Rangka samping kanan (kaki + sandaran) | 2C9`: bbox tumpang tindih 31.9 × 30 × 45 mm, 127 / 2 vertex.
- `Palang belakang | 2C6` ↔ `Dudukan baji belakang | 2E7`: bbox tumpang tindih 477.6 × 30 × 45 mm, 935 / 6 vertex.
- `Palang belakang | 2C6` ↔ `Dudukan baji kiri | 2E1`: bbox tumpang tindih 217.6 × 23.6 × 45 mm, 67 / 4 vertex.
- `Palang belakang | 2C6` ↔ `Dudukan baji kanan | 2E1`: bbox tumpang tindih 217.5 × 23.6 × 45 mm, 65 / 12 vertex.
- `Rangka samping kanan (kaki + sandaran) | 2C9` ↔ `Dudukan baji depan | 2E4`: bbox tumpang tindih 58.4 × 253 × 61 mm, 170 / 1045 vertex.
- `Rangka samping kanan (kaki + sandaran) | 2C9` ↔ `Dudukan baji belakang | 2E7`: bbox tumpang tindih 33.4 × 253 × 61 mm, 51 / 904 vertex.
- `Rangka samping kanan (kaki + sandaran) | 2C9` ↔ `Dudukan baji kanan | 2E1`: bbox tumpang tindih 64.8 × 490.9 × 61 mm, 55 / 2136 vertex.
- `Dudukan baji depan | 2E4` ↔ `Dudukan baji kiri | 2E1`: bbox tumpang tindih 244 × 245.3 × 61 mm, 0 / 37 vertex.
- `Dudukan baji depan | 2E4` ↔ `Dudukan baji kanan | 2E1`: bbox tumpang tindih 244 × 245.3 × 61 mm, 19 / 46 vertex.
- `Dudukan baji belakang | 2E7` ↔ `Dudukan baji kiri | 2E1`: bbox tumpang tindih 219.1 × 245.6 × 61 mm, 1 / 119 vertex.
- `Dudukan baji belakang | 2E7` ↔ `Dudukan baji kanan | 2E1`: bbox tumpang tindih 219.1 × 245.6 × 61 mm, 1 / 28 vertex.

**Log build (otomatis):**

- 2E1 dipisah menjadi 'Dudukan baji kiri' (5470 muka)
- 2E1 dipisah menjadi 'Dudukan baji kanan' (5655 muka)

**Verifikasi buka-ulang:** unit ['METRIC', 'CENTIMETERS', 1.0], 10 mesh, bbox aktif min [-275.5, -310.1, 0.0] max [275.5, 310.1, 858.1] mm, collection dikecualikan: -, masalah: tidak ada. Thumbnail: `_preview/BEECHWOOD DINNING CHAIR.png` dan `_preview/BEECHWOOD DINNING CHAIR_belakang.png`.

## Batasan umum dan saran lanjutan

- **Tessellasi ACIS lokal** (`dwg2obj.py`) adalah satu-satunya rute untuk solid DWG 2018 di mesin ini. Kelemahannya: tepi spline (`intcurve`) jadi garis lurus (alur handle di front laci), patch torus/kerucut kecil bisa menghasilkan muka saling tumpang tindih di blend sudut, dan boolean (EXACT/FLOAT) pada mesh ini pecah. Kalau butuh mesh benar-benar manifold, ekspor STL per solid dari AutoCAD (`pipeline/dwg_ke_stl.py`, FACETRES 10) lalu jalankan ulang `_skrip/bangun_beechwood.py` dengan resep yang sama — nama part, grup, laci dan perbaikan posisi sudah tercatat di `_skrip/resep/*.json`.
- **Finish kayu / handle** belum ditanam (file memakai material peran polos). Untuk mengikuti pipeline studio sepenuhnya, buat `sumber/produk.json` per produk (finish_kayu + swatch) dan jalankan `pipeline/bangun_produk.py`, atau pilih finish lewat panel studio (material `ROLE | …` dikenali sebagai WOOD_A/HANDLE).
- **Kotak laci** adalah tambahan konvensi v2 (tidak ada di DWG); hapus objek `Laci n / …` jika tidak diinginkan. Dresser 6 laci tidak punya panel belakang di DWG, jadi kotak laci terlihat dari belakang.
- **Thumbnail** hanya Workbench 512 px; belum ada render studio (sesuai aturan: render penuh dilakukan di server pengguna).
- Tidak ada yang di-commit ke git; semua hasil berada di folder `02_PRODUK/BEECHWOOD/` (untracked).
