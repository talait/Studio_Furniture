"""Tulis LAPORAN_KONVERSI.md dari laporan build (JSON), verifikasi (JSON) dan resep."""
import json
from pathlib import Path

SP = Path(r"C:\Users\Staff\AppData\Local\Temp\claude\C--Users-Staff-Documents-Studio-Furniture\d7b4d6f4-11df-468c-93a9-78d023c4cb41\scratchpad")
OUT = Path(r"C:\Users\Staff\Documents\Studio_Furniture\02_PRODUK\BEECHWOOD")

FILES = [
    ("BEECHWOOD BEDSIDE", "1Ijo4x03Cl7MFIEvzzJdLocuxv08BpLhw", 86452, "AC1032 (AutoCAD 2018)", "INSUNITS=4 (mm)"),
    ("beechwood 6dw r", "1KoZ9m7RVX2hVKBNeql8-yYu-3MDAvNcd", 405850, "AC1032 (AutoCAD 2018)", "INSUNITS=1 (inci) di header, angka jelas mm"),
    ("BEECHWOOD TALLBOY", "1XY9qIZu8KNMEbDpDdYZNlyIjNBRS09qa", 174093, "AC1032 (AutoCAD 2018)", "INSUNITS=4 (mm)"),
    ("BEECHWOOD DINNING TABLE  ALTFIELD", "1sYXFlK5Ubo3ABQcYOyXO0Q4KSV_LbIp_", 114988, "AC1032 (AutoCAD 2018)", "INSUNITS=1 (inci) di header, angka jelas mm"),
    ("SP 05 ALTFIELD CREDENZA", "1OYkTYSe136mHDLnzNEkYhK4K8ptBf8Gf", 38665124, "AC1014 (AutoCAD R14)", "tanpa INSUNITS; angka = cm"),
    ("BEECHWOOD DINNING CHAIR", "1wAbsTwZHmLsiTkghvLHFwpGjnZagtYVJ", 409854, "AC1032 (AutoCAD 2018)", "INSUNITS=4 (mm)"),
]

NARASI = {
    "BEECHWOOD BEDSIDE": {
        "isi_dwg": "11 3DSOLID di model space (layer 0), tanpa garis/teks/dimensi.",
        "rute": "DWG → `dwgread -O JSON` + dump AcDs (LibreDWG, Docker) → blob SAB per solid → tessellasi B-rep (`dwg2obj.py`) → OBJ (mm) → Blender (skala 0,001).",
        "masalah": [
            "Mesh hasil tessellasi punya sambungan-T (patch lengkung dibagi 8×, bidang datar tetangganya tidak) dan lubang mikro di blend sudut → diperbaiki di Blender (lihat *Pembersihan mesh*). Sisa: kaki 8–30 tepi terbuka (lubang < 1 mm di blend sudut), front laci 649 tepi terbuka di zona alur handle (kurva spline `intcurve` didekati garis lurus oleh tessellator), handle 12 tepi terbuka.",
            "Front laci di DWG menyentuh rel atas tanpa celah → diberi celah bayangan 1,5 mm atas-bawah (standar v2, tinggi 120 → 117 mm), handle ikut bergeser.",
            "Rak dasar (panel 18 mm, 550 × 500) digambar menerus sehingga keempat kaki menembusnya di sudut (tersembunyi di dalam kaki). Takik boolean dicoba (EXACT dan FLOAT) tetapi mesh tessellasi rak pecah → rak dibiarkan sesuai DWG. Tidak terlihat dari luar.",
            "Handle (pelat 164 × 21 × 8 mm) terbenam 16 mm ke dalam front: sesuai DWG (alur handle di front), dibiarkan.",
        ],
        "keputusan": [
            "Carcass + top adalah satu solid di DWG (550 × 420 × 410) → satu objek `Badan kabinet (carcass + top)`; tidak dipecah karena tidak ada batas part di data.",
            "Kotak laci sederhana (dasar 7 mm, sisi/belakang 12 mm) ditambahkan mengikuti STANDAR_FILE_PRODUK v2; ditandai `geometry_source = tambahan`, bukan dari DWG. Mudah dihapus bila tidak diinginkan.",
            "Depan = −Y (sisi handle), tidak perlu rotasi.",
        ],
        "keraguan": ["Tidak ada keraguan dimensi; semua bagian cocok dengan nakas 550 × 505 × 500 mm."],
    },
    "beechwood 6dw r": {
        "isi_dwg": "29 3DSOLID + 5 LWPOLYLINE + 4 VIEWPORT (layout). DWG berisi **dua rakitan berdampingan**: A (kiri, x 1344–2528): carcass 1183 mm, rangka belakang, 1 kaki depan kiri, rel atas depan, 5 front 550 mm + 5 handle (front kiri-atas tidak ada); B (kanan, x 2733–3933): rangka depan 1200 mm (2 kaki + rel) dan 6 front 559 mm + 6 handle, **tanpa carcass**. Nama file \"6dw r\" = revisi.",
        "rute": "Sama dengan Bedside (ACIS SAB → tessellasi → OBJ → Blender).",
        "masalah": [
            "Dua rakitan tidak lengkap masing-masing → dirakit jadi satu dresser lengkap (lihat *Keputusan*).",
            "Front B digambar rapat satu sama lain (celah 0–0,3 mm) → disusun ulang rata dalam bukaan carcass (−1879,7 … −1308,6 mm) dengan celah 1,5 mm; tinggi front 190 → 187,4 mm; handle ikut.",
            "Carcass B tidak ada; carcass A (1183,4 mm) lebih sempit 16,6 mm dari rangka depan B (1200 mm) → carcass A dan rangka belakang A dilebarkan dengan skala X 1,0140 (tebal panel berubah 1,4 %, tidak terlihat).",
            "Carcass tidak punya panel belakang di DWG (rangka belakang = bingkai 40 mm, bagian tengah terbuka). Kotak laci tambahan terlihat dari belakang. Tidak ditambah panel karena tidak ada di DWG.",
            "Rel atas rangka belakang dan tepi atas carcass yang sama-sama membulat bertemu pada bidang yang sama → ada garis sambungan tipis bergerigi di tampak belakang (dua permukaan berimpit, bukan tembus; uji tembus 0 vertex). Sesuai DWG.",
            "Sisa mesh: front 531–712 tepi terbuka di alur handle, handle 18–35, kaki 10–26, rangka belakang 22 (semua di blend/alur, tidak terlihat).",
        ],
        "keputusan": [
            "Rakitan final = rangka depan (2 kaki + rel) + 6 front + 6 handle dari B (digeser −1389, −580, 0 mm) + carcass & rangka belakang dari A (dilebarkan ke 1200 mm). Ukuran akhir 1200 × 605 × 700 mm.",
            "Semua sisa A (rel atas depan lama, kaki depan kiri lama, 5 front lama, 5 handle lama) disimpan di collection `_ARSIP sisa DWG (tidak dipakai)` (dikecualikan dari view layer & render), bukan dihapus, agar bisa dibandingkan.",
            "Penomoran laci: 1–2 baris atas (kiri, kanan), 3–4 tengah, 5–6 bawah.",
        ],
        "keraguan": [
            "Apakah desainer memang bermaksud melebarkan carcass ke 1200 mm (mengikuti rangka depan B) atau menyempitkan front B ke 1183 mm — saya pilih 1200 karena rangka depan B lengkap dan konsisten (2 × 40 + 2 × 559,4 + celah 1,1 = 1200). Kalau yang benar 1183, cukup skala X carcass & rangka belakang dikembalikan dan front B diskalakan 0,986.",
            "Satuan: header menyatakan inci, tetapi tinggi 700 / lebar 1183 hanya masuk akal sebagai mm.",
        ],
    },
    "BEECHWOOD TALLBOY": {
        "isi_dwg": "18 3DSOLID + 1 LWPOLYLINE, layer 0.",
        "rute": "Sama dengan Bedside.",
        "masalah": [
            "Lima front (5 × 194,7 = 973,5 mm) lebih tinggi 3,5 mm dari bukaan carcass (970 mm) sehingga front teratas menembus rel atas 2,9 mm → front disusun ulang rata dalam bukaan dengan celah 1,5 mm (tinggi tiap front 191 mm, pergeseran pusat ≤ 2,6 mm), handle ikut.",
            "Handle terbenam 16 mm ke dalam front (alur handle, sesuai DWG).",
            "Sisa mesh: front 724–732 tepi terbuka di alur handle, handle 17–23, kaki 7–14; carcass, rel, panel belakang bersih (manifold).",
        ],
        "keputusan": ["Carcass + top satu solid di DWG → satu objek. Kotak laci sederhana ditambahkan (standar v2). Laci dinomori dari atas (1) ke bawah (5)."],
        "keraguan": ["Tidak ada; tallboy 600 × 505 × 1100 mm."],
    },
    "BEECHWOOD DINNING TABLE  ALTFIELD": {
        "isi_dwg": "13 3DSOLID + 55 LINE + 10 LWPOLYLINE (tampak 2D) + 2 VIEWPORT; layer 0 dan Defpoints; blok `_ArchTick`.",
        "rute": "Sama dengan Bedside. Peringatan dwg2obj: tabel `datidx` tak terbaca dan handle 29F (top) punya lebih dari satu blob ACIS (riwayat edit) → versi terakhir dipakai (2100 × 800 × 30 mm, cocok dengan posisi kaki).",
        "masalah": [
            "Garis 2D (LINE/LWPOLYLINE, tampak gambar) diabaikan — tidak diimpor.",
            "Top meja 16 tepi terbuka (lubang mikro di blend sudut); 12 bagian lain manifold bersih.",
            "Empat pasang palang/rel hanya bersentuhan (bbox tumpang tindih 50 × 50 × 50 di sambungan, uji tembus 0 vertex) — sambungan rangka normal.",
        ],
        "keputusan": ["Kaki dinamai menurut posisi dilihat dari depan (−Y): kiri/kanan depan/belakang + dua kaki ujung di tengah lebar; palang H kiri/kanan atas/bawah; dua rel memanjang."],
        "keraguan": ["Satuan header inci, tetapi 2100 × 800 × 750 hanya masuk akal sebagai mm."],
    },
    "SP 05 ALTFIELD CREDENZA": {
        "isi_dwg": "DWG R14 (38,7 MB): **bukan solid**, melainkan 43.449 POLYLINE_PFACE (172.543 vertex, 86.709 muka) + 160.640 LINE (148.883 di antaranya panjang 0) + 1 LWPOLYLINE, dalam blok `SP_05_ALTFIELD_CREDENZA_DW` (1 INSERT, rotasi 180°) dan blok `SUMELE` (628 pface, tidak di-insert → tidak tampak, diabaikan). Model ala SketchUp; warna ACI 18 = handle & panel cekung pintu, 23 = badan/pintu/kaki, 254 = panel cekung pintu, 0 = serpihan.",
        "rute": "DWG → `dwgread -O JSON` (LibreDWG) → ekstrak POLYLINE_PFACE (`credenza_extract.py`: indeks vertind > 32767 = indeks negatif/tepi tak terlihat; vertex korup bernilai 1e+96…1e+214 dibuang beserta mukanya) → OBJ per warna (cm) → Blender (skala 0,01) → weld 0,2 mm → pisah pulau lepas → pintu 1 & 4 yang menyatu dengan carcass dipisah menurut kotak muka → pulau yang memetakan ke part yang sama digabung.",
        "masalah": [
            "Pintu 1 dan 4 menyatu dengan carcass setelah weld (berbagi vertex) → dipisah dengan kotak x pintu (dari pengukuran bidang muka pintu: pintu overlay 447,7 mm, mulai x = 0 / 450 / 900 / 1351), dengan pengecualian muka carcass yang menghadap −Y pada bidang belakang pintu dan zona handle.",
            "Panel cekung pintu (warna 18/254, muka datar di y 42,8 & 46,1 cm) dan pelat belakang handle (warna 23) terpisah di DWG → digabung ke objek pintu/handle-nya.",
            "Tiga panel tipis 20 × 471 × 540 mm berada **seluruhnya di dalam** sekat vertikal 28 mm (geometri tersembunyi) → disimpan di `_ARSIP`, bukan dihapus.",
            "27 serpihan warna 0 (< 2 mm, di kaki) dan semua LINE diabaikan.",
            "Mesh SketchUp tidak tertutup (shell terbuka, muka dalam) → jumlah tepi non-manifold bukan indikator kerusakan di sini; uji tembus antar part juga tidak andal untuk shell terbuka (angka kecil 1–11 vertex adalah muka yang berimpit pada sambungan rak/sekat ke carcass).",
        ],
        "keputusan": [
            "Satuan cm (180 × 65,8 × 90 → 1,80 × 0,66 × 0,90 m, credenza 4 pintu).",
            "Blok `SUMELE` tidak di-insert di model space → tidak diekstrak.",
            "Tidak ada laci; pintu tidak diberi engsel/driver (di luar standar v2 yang hanya mendefinisikan laci).",
        ],
        "keraguan": ["Nama file bukan 'BEECHWOOD' (SP 05 Altfield) — diproses apa adanya sebagai koleksi yang sama sesuai permintaan."],
    },
    "BEECHWOOD DINNING CHAIR": {
        "isi_dwg": "10 3DSOLID, layer 0, warna merah (ACI 1). Solid 2CC kosong (69 byte, tanpa data ACIS).",
        "rute": "Sama dengan Bedside. 9 solid punya blob SAB; 2CC dibuang.",
        "masalah": [
            "Dudukan terdiri dari **empat baji segitiga** (pola diagonal): solid 2E4 = baji depan, 2E7 = baji belakang, 2E1 = baji kiri + kanan dalam satu solid → 2E1 dipisah menjadi dua objek (`Dudukan baji kiri` / `kanan`). Awalnya saya kira 2E1 dan 2E4+2E7 adalah dua versi dudukan yang tumpang tindih; pemeriksaan bidang datar solid (muka segitiga) dan render menunjukkan keempatnya saling melengkapi.",
            "Baji dudukan menempati ketinggian yang sama dengan palang samping/depan/belakang (z 400–461 vs 405–460): palang berada di dalam volume dudukan. Ujung palang masuk ke rangka samping (tenon). Keduanya sesuai DWG (rangka tersembunyi di dalam dudukan) → tidak diubah; tercatat di daftar tembus.",
            "Rangka samping (kaki + sandaran, bentuk lengkung dengan permukaan spline) menyisakan 415–423 tepi terbuka; baji dudukan 101–120; palang samping 62–78; palang depan/belakang bersih.",
        ],
        "keputusan": ["Depan = −Y (sandaran di +Y), tidak perlu rotasi. Semua kayu (WOOD_A); tidak ada petunjuk material kain di DWG."],
        "keraguan": ["Jika dudukan sebenarnya berlapis kain, ganti peran material empat baji dudukan ke KAIN."],
    },
}

GRUP_URUT = ["Badan", "Kaki", "Laci", "Pintu", "Hardware", "_ARSIP sisa DWG (tidak dipakai)"]


def fmt_mm(v):
    return " × ".join(f"{x:g}" for x in v)


md = []
md.append("# Laporan Konversi DWG → Blender — koleksi BEECHWOOD\n")
md.append("Tanggal: 2026-10-29 · Dibuat otomatis oleh tugas terjadwal `beechwood-dwg-to-blend` (Claude Code) · Blender 5.2.2 LTS, headless.\n")
md.append("Folder: `02_PRODUK/BEECHWOOD/` — 6 file `.blend` (satu per DWG), `_source_dwg/` (DWG asli), `_preview/` (thumbnail Workbench 512 px depan & belakang), `_skrip/` (skrip, resep, laporan JSON, hasil verifikasi JSON).\n")

# ---- ringkasan tabel
md.append("## Ringkasan\n")
md.append("| # | Sumber (Drive) | Hasil .blend | Rute | L × D × T (mm) | Objek mesh | Status |")
md.append("|---|---|---|---|---|---|---|")
rows = []
for i, (name, fid, size, ver, unit) in enumerate(FILES, 1):
    L = json.loads((SP / "laporan" / f"{name}.json").read_text(encoding="utf-8"))
    V = json.loads((SP / "verif" / f"{name}.json").read_text(encoding="utf-8"))
    aktif = [p for p in L["part"] if not p["arsip"]]
    rute = "mesh PFACE (R14)" if "CREDENZA" in name else "3DSOLID ACIS → tessellasi"
    uk = fmt_mm(V["bbox_aktif_mm"]["ukuran"])
    status = "OK" if not V["masalah"] else "; ".join(V["masalah"])
    md.append(f"| {i} | `{name}.dwg` ({size:,} B, {ver}) | `{name}.blend` | {rute} | {uk} | {len(aktif)} aktif + {len(L['part']) - len(aktif)} arsip | {status} |")
md.append("")
md.append("Semua enam file berhasil dikonversi; tidak ada yang dilewati. Verifikasi buka-ulang headless: unit metrik (scale_length 1, tampilan cm), dasar tepat di Z = 0, terpusat di XY, tanpa kamera/lampu, semua mesh bermaterial peran, transformasi sudah diterapkan.\n")

# ---- metode umum
md.append("## Lingkungan dan metode umum\n")
md.append("""**Pengambilan file.** Tautan share Drive mengarah ke halaman login Google (bukan publik), jadi `curl` dan browser bawaan gagal. Dua file (Bedside, 6dw r) sudah ada di `C:\\Users\\Staff\\Downloads` dengan ukuran byte persis sama dengan metadata Drive; empat sisanya diunduh lewat Chrome milik pengguna (sudah login) dari `drive.usercontent.google.com/download?id=…`. Ukuran semua file dicocokkan dengan metadata Drive. File DWG tersimpan di `_source_dwg/` dan diperlakukan sebagai data tidak tepercaya (dibaca oleh Python `-I`, skrip di luar folder itu).

**Alat.** LibreDWG 0.13.3 (Docker, `dwgread -O JSON`, dump section AcDs), `C:\\Users\\Staff\\tools\\libredwg\\dwg2obj.py` (ezdxf SAB parser + tessellasi B-rep: bidang, silinder/kerucut, torus, bola; kurva garis & elips; spline didekati garis), Blender 5.2.2 headless. AutoCAD Core Console (`99_SISTEM/pipeline/dwg_ke_stl.py`) dan ODA File Converter tidak terpasang di mesin ini; `dwg2dxf` tidak membawa geometri ACIS, jadi rute DXF tidak dipakai untuk solid. Catatan: skrip `dwg2obj.py` hanya dipanggil, tidak diubah.

**Pembersihan mesh (per objek, `_skrip/bersih.py`).** Merge by distance 0,01 mm → hapus tepi/muka degenerate dan vertex/tepi lepas → **perbaikan sambungan-T** (vertex lain yang terletak di atas tepi terbuka → tepi dipotong di titik itu, toleransi 0,3 mm; 0,1 mm untuk handle) → hapus muka duplikat → tutup lubang kecil (loop batas keliling < 25 cm) → recalculate normals outside → dissolve muka sebidang (0,06°). Hasil tiap objek dicek: tepi non-manifold, tepi terbuka, muka luas nol, jumlah pulau. Sisa yang tidak bisa diperbaiki otomatis dicatat per produk; semuanya berada di blend sudut (fillet < 1 mm) atau di alur handle (tepi spline), tidak terlihat pada render.

**Struktur file (mengikuti `05_PANDUAN/STANDAR_FILE_PRODUK.md` v2).** Scene `PRODUK | <nama>`, satu collection `PROD | <nama>` dengan child collection `Badan`, `Kaki`, `Laci`, `Pintu`, `Hardware` (dan `_ARSIP sisa DWG (tidak dipakai)` yang dikecualikan dari view layer bila ada); empty `PRODUCT_ROOT | <nama>` (`ns_product_root`, `dimensions_cm`, `source`, `unit_assumption`, `catatan`); setiap part = satu objek mesh bernama `<Nama bagian> | <handle DWG>` dengan properti `cad_handle`, `ns_role_part`, `geometry_source`; origin tiap part di pusat bbox-nya, root di (0,0,0); depan −Y, lebar X, tinggi Z, dasar di Z = 0. Laci: empty `DRAWER_n` (`ns_drawer`, properti `Open (m)`, driver `location.y = -Open`) yang menjadi induk front, handle dan kotak laci sederhana (dasar 7 mm, sisi & belakang 12 mm — **tambahan standar v2, bukan dari DWG**, properti `geometry_source` menandainya). Material per peran: `ROLE | WOOD_A`, `ROLE | WOOD_B` (kotak laci), `ROLE | HANDLE` (metalik) dengan properti `ns_role`; finish kayu `FIN | …` belum ditanam (butuh `produk.json` + swatch klien lewat `pipeline/bangun_produk.py`). UV `UV meter` tri-planar (1 UV = 1 m), modifier Bevel 0,6 mm (handle 0,35 mm) + Weighted Normal, smooth by angle 30°. File disimpan terkompresi.

**Pemeriksaan tabrakan.** Untuk setiap pasangan part aktif yang bbox-nya tumpang tindih > 0,3 mm di tiga sumbu, dihitung vertex part A yang berada di dalam mesh part B (BVH, margin 0,3 mm) dan sebaliknya. Hasil per produk di bawah; pasangan handle–front (handle terbenam di alur front, sesuai DWG) tidak diulang di tiap bagian.

**Thumbnail.** Hanya render Workbench 512 × 384 (depan 3/4 dan belakang) untuk cek visual, di `_preview/`; tidak ada render Eevee/Cycles. Kamera tidak disimpan di file.
""")

# ---- per file
for i, (name, fid, size, ver, unit) in enumerate(FILES, 1):
    L = json.loads((SP / "laporan" / f"{name}.json").read_text(encoding="utf-8"))
    V = json.loads((SP / "verif" / f"{name}.json").read_text(encoding="utf-8"))
    R = json.loads((SP / "resep" / f"{name}.json").read_text(encoding="utf-8"))
    N = NARASI[name]
    md.append(f"## {i}. `{name}.dwg` → `{name}.blend`\n")
    md.append(f"- **Sumber:** Drive id `{fid}`, {size:,} byte, format {ver}, satuan: {unit}.")
    md.append(f"- **Isi DWG:** {N['isi_dwg']}")
    md.append(f"- **Rute konversi:** {N['rute']}")
    uk = V["bbox_aktif_mm"]["ukuran"]
    md.append(f"- **Dimensi hasil (L × D × T):** {fmt_mm(uk)} mm; `dimensions_cm` di root = {L['ukuran_cm']}.")
    md.append(f"- **Nama produk di file:** `{R['nama']}` (kategori `{R['kategori']}`).")
    md.append("")
    md.append("**Komponen** (objek mesh; ukuran bbox mm; handle = handle entitas DWG, `pface` = mesh R14, `-` = tambahan):\n")
    md.append("| Collection | Objek | Peran | Ukuran (mm) | Muka | Sisa tepi terbuka | Catatan |")
    md.append("|---|---|---|---|---|---|---|")
    parts = sorted(L["part"], key=lambda p: (GRUP_URUT.index(p["grup"]) if p["grup"] in GRUP_URUT else 99, p["nama"]))
    for p in parts:
        s = p["sesudah"]
        cat = ""
        if p["tambahan"]:
            cat = "tambahan standar v2 (kotak laci), bukan dari DWG"
        elif p["arsip"]:
            cat = "arsip, dikecualikan dari view layer & render"
        elif s["islands"] > 1:
            cat = f"{s['islands']} pulau (pecahan di alur/blend)"
        md.append(f"| {p['grup']} | `{p['nama']}` | {p['peran']} | {fmt_mm(p['ukuran_mm'])} | {s['faces']:,} | {s['boundary']} | {cat} |")
    md.append("")
    aktif = [p for p in L["part"] if not p["arsip"]]
    bersih = [p for p in aktif if p["sesudah"]["nonmanifold"] == 0 and p["sesudah"]["islands"] == 1]
    md.append(f"**Kualitas mesh:** {len(bersih)} dari {len(aktif)} objek aktif manifold tertutup sepenuhnya; sisanya punya tepi terbuka seperti di kolom tabel (lihat *Masalah*).\n")
    md.append("**Masalah yang ditemukan dan perbaikan:**\n")
    for m in N["masalah"]:
        md.append(f"- {m}")
    md.append("")
    md.append("**Keputusan / judgement call:**\n")
    for m in N["keputusan"]:
        md.append(f"- {m}")
    md.append("")
    md.append("**Keraguan yang tersisa:**\n")
    for m in N["keraguan"]:
        md.append(f"- {m}")
    md.append("")
    tembus = [m for m in L["masalah"] if m["jenis"] == "tembus" and not ("Handle" in m["a"] and "Front" in m["b"])]
    hf = [m for m in L["masalah"] if m["jenis"] == "tembus" and ("Handle" in m["a"] and "Front" in m["b"])]
    md.append("**Uji tembus antar part** (vertex A di dalam B / B di dalam A):\n")
    if hf:
        md.append(f"- {len(hf)} pasangan handle ↔ front laci: handle terbenam 16 mm di alur front (sesuai DWG).")
    for m in tembus:
        md.append(f"- `{m['a']}` ↔ `{m['b']}`: bbox tumpang tindih {fmt_mm(m['bbox_mm'])} mm, {m['vertex_a_di_dalam_b']} / {m['vertex_b_di_dalam_a']} vertex.")
    if not tembus and not hf:
        md.append("- Tidak ada part yang saling menembus.")
    sentuh = L.get("bbox_sentuh", [])
    if sentuh:
        md.append(f"- {len(sentuh)} pasangan lain hanya bersentuhan (bbox tumpang tindih, 0 vertex di dalam).")
    md.append("")
    md.append("**Log build (otomatis):**\n")
    for c in L["catatan"]:
        md.append(f"- {c}")
    md.append("")
    md.append(f"**Verifikasi buka-ulang:** unit {V['unit']}, {V['jumlah_mesh']} mesh, bbox aktif min {V['bbox_aktif_mm']['min']} max {V['bbox_aktif_mm']['max']} mm, collection dikecualikan: {V['koleksi_dikecualikan'] or '-'}, masalah: {V['masalah'] or 'tidak ada'}. Thumbnail: `_preview/{name}.png` dan `_preview/{name}_belakang.png`.\n")

# ---- batasan umum
md.append("## Batasan umum dan saran lanjutan\n")
md.append("""- **Tessellasi ACIS lokal** (`dwg2obj.py`) adalah satu-satunya rute untuk solid DWG 2018 di mesin ini. Kelemahannya: tepi spline (`intcurve`) jadi garis lurus (alur handle di front laci), patch torus/kerucut kecil bisa menghasilkan muka saling tumpang tindih di blend sudut, dan boolean (EXACT/FLOAT) pada mesh ini pecah. Kalau butuh mesh benar-benar manifold, ekspor STL per solid dari AutoCAD (`pipeline/dwg_ke_stl.py`, FACETRES 10) lalu jalankan ulang `_skrip/bangun_beechwood.py` dengan resep yang sama — nama part, grup, laci dan perbaikan posisi sudah tercatat di `_skrip/resep/*.json`.
- **Finish kayu / handle** belum ditanam (file memakai material peran polos). Untuk mengikuti pipeline studio sepenuhnya, buat `sumber/produk.json` per produk (finish_kayu + swatch) dan jalankan `pipeline/bangun_produk.py`, atau pilih finish lewat panel studio (material `ROLE | …` dikenali sebagai WOOD_A/HANDLE).
- **Kotak laci** adalah tambahan konvensi v2 (tidak ada di DWG); hapus objek `Laci n / …` jika tidak diinginkan. Dresser 6 laci tidak punya panel belakang di DWG, jadi kotak laci terlihat dari belakang.
- **Thumbnail** hanya Workbench 512 px; belum ada render studio (sesuai aturan: render penuh dilakukan di server pengguna).
- Tidak ada yang di-commit ke git; semua hasil berada di folder `02_PRODUK/BEECHWOOD/` (untracked).
""")

out = OUT / "LAPORAN_KONVERSI.md"
out.write_text("\n".join(md), encoding="utf-8")
print("LAPORAN", out, len("\n".join(md)), "karakter")
