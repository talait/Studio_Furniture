"""Tulis resep JSON untuk 6 produk BEECHWOOD."""
import json
from pathlib import Path

SP = Path(r"C:\Users\Staff\AppData\Local\Temp\claude\C--Users-Staff-Documents-Studio-Furniture\d7b4d6f4-11df-468c-93a9-78d023c4cb41\scratchpad")
OUT = Path(r"C:\Users\Staff\Documents\Studio_Furniture\02_PRODUK\BEECHWOOD")
(SP / "resep").mkdir(exist_ok=True)
(SP / "thumb").mkdir(exist_ok=True)
(SP / "laporan").mkdir(exist_ok=True)

ACIS = "DWG 2018 3DSOLID (ACIS SAB) -> tessellasi dwg2obj (LibreDWG + ezdxf)"
UNIT_MM = "angka DWG dibaca sebagai mm"


def P(nama, peran="WOOD_A", grup="Badan", **k):
    d = {"nama": nama, "peran": peran, "grup": grup}
    d.update(k)
    return d


def base(nama, dwg, kategori, obj, out_name, **k):
    r = {"nama": nama, "kategori": kategori, "dwg": dwg, "skala": 0.001, "mode": "solid",
         "sumber_obj": str(SP / "obj" / obj), "file_out": str(OUT / out_name),
         "thumb": str(SP / "thumb" / (out_name.replace(".blend", ".png"))),
         "laporan_json": str(SP / "laporan" / (out_name.replace(".blend", ".json"))),
         "geometry_source": ACIS, "unit_assumption": UNIT_MM, "weld_m": 0.00001}
    r.update(k)
    return r


resep = []

# 1. BEDSIDE -------------------------------------------------------------
resep.append(base("Beechwood Bedside", "BEECHWOOD BEDSIDE.dwg", "NAKAS", "BEECHWOOD BEDSIDE.obj", "BEECHWOOD BEDSIDE.blend",
    unit_assumption=UNIT_MM + " (INSUNITS=4 mm)",
    part={
        "2C2": P("Kaki depan kanan", grup="Kaki"), "2C5": P("Kaki belakang kanan", grup="Kaki"),
        "2C8": P("Kaki depan kiri", grup="Kaki"), "2CB": P("Kaki belakang kiri", grup="Kaki"),
        "2CE": P("Rel atas belakang"), "2D7": P("Rel atas depan"),
        "2CF": P("Badan kabinet (carcass + top)"), "2D0": P("Panel belakang"),
        "2D8": P("Rak dasar"),
        "2D6": P("Front laci 1", grup="Laci"), "2D3": P("Handle laci 1", "HANDLE", "Hardware"),
    },
    badan_handle="2CF",
    laci={"1": {"part": ["2D6", "2D3"], "travel_m": 0.3, "kotak": True}},
    fit_kolom=[{"front": ["2D6"], "z0_mm": -663.9, "z1_mm": -543.9, "celah_mm": 1.5, "ikut": {"2D6": ["2D3"]}}],
    catatan="Front laci diberi celah bayangan 1,5 mm (standar v2); handle ikut. Rak dasar (panel 18 mm, 550 x 500) di DWG digambar menerus sehingga keempat kaki menembusnya di sudut; "
            "takik boolean dicoba (EXACT dan FLOAT) tetapi hasilnya pecah karena mesh tessellasi rak, jadi rak dibiarkan sesuai DWG (tumpang tindih tersembunyi di dalam kaki, tidak terlihat).",
))

# 2. 6 DRAWERS (revisi) --------------------------------------------------
GESER_B = [-1389.0, -580.0, 0.0]
FAKTOR = 1200.0 / 1183.4
resep.append(base("Beechwood 6 Drawers", "beechwood 6dw r.dwg", "DRESSER", "beechwood 6dw r.obj", "beechwood 6dw r.blend",
    unit_assumption=UNIT_MM + " (INSUNITS=1 inci di header, tetapi ukuran hanya masuk akal sebagai mm)",
    part={
        "261": P("Badan kabinet (carcass + top)"), "257": P("Rangka belakang (kaki belakang + rel)", grup="Kaki"),
        "2E5": P("Kaki depan kiri", grup="Kaki"), "2E1": P("Kaki depan kanan", grup="Kaki"), "2E6": P("Rel atas depan"),
        "2FB": P("Front laci 1", grup="Laci"), "2F7": P("Front laci 2", grup="Laci"),
        "303": P("Front laci 3", grup="Laci"), "2FF": P("Front laci 4", grup="Laci"),
        "30C": P("Front laci 5", grup="Laci"), "308": P("Front laci 6", grup="Laci"),
        "2F8": P("Handle laci 1", "HANDLE", "Hardware"), "2E7": P("Handle laci 2", "HANDLE", "Hardware"),
        "300": P("Handle laci 3", "HANDLE", "Hardware"), "2FC": P("Handle laci 4", "HANDLE", "Hardware"),
        "309": P("Handle laci 5", "HANDLE", "Hardware"), "305": P("Handle laci 6", "HANDLE", "Hardware"),
        # sisa rakitan lama (versi sebelum revisi) -> arsip
        "25A": P("Lama: rel atas depan", arsip=True), "2CE": P("Lama: kaki depan kiri", arsip=True),
        "262": P("Lama: front laci kanan atas", arsip=True), "270": P("Lama: front laci kiri tengah", arsip=True),
        "275": P("Lama: front laci kanan tengah", arsip=True), "27A": P("Lama: front laci kiri bawah", arsip=True),
        "27F": P("Lama: front laci kanan bawah", arsip=True),
        "25D": P("Lama: handle", "HANDLE", arsip=True), "26C": P("Lama: handle", "HANDLE", arsip=True),
        "271": P("Lama: handle", "HANDLE", arsip=True), "276": P("Lama: handle", "HANDLE", arsip=True),
        "27B": P("Lama: handle", "HANDLE", arsip=True),
    },
    geser_mm={h: GESER_B for h in ["2E5", "2E1", "2E6", "2FB", "2F7", "303", "2FF", "30C", "308", "2F8", "2E7", "300", "2FC", "309", "305"]},
    skala_x={"261": {"faktor": FAKTOR, "x0_mm": 1344.3}, "257": {"faktor": FAKTOR, "x0_mm": 1344.3}},
    badan_handle="261",
    laci={str(i): {"part": [f, h], "travel_m": 0.4, "kotak": True} for i, (f, h) in enumerate(
        [("2FB", "2F8"), ("2F7", "2E7"), ("303", "300"), ("2FF", "2FC"), ("30C", "309"), ("308", "305")], start=1)},
    fit_kolom=[
        {"front": ["2FB", "303", "30C"], "z0_mm": -1879.7, "z1_mm": -1308.6, "celah_mm": 1.5, "ikut": {"2FB": ["2F8"], "303": ["300"], "30C": ["309"]}},
        {"front": ["2F7", "2FF", "308"], "z0_mm": -1879.7, "z1_mm": -1308.6, "celah_mm": 1.5, "ikut": {"2F7": ["2E7"], "2FF": ["2FC"], "308": ["305"]}},
    ],
    catatan="DWG berisi dua rakitan: A (kiri, carcass 1183 mm + 5 front lama 550 mm) dan B (kanan, rangka depan 1200 mm + 6 front 559 mm = revisi). "
            "Rakitan final = rangka depan & 6 front/handle dari B (digeser -1389,-580 mm) + carcass & rangka belakang dari A yang dilebarkan ke 1200 mm (skala X 1,014). Sisa A disimpan di collection _ARSIP.",
))

# 3. TALLBOY --------------------------------------------------------------
resep.append(base("Beechwood Tallboy", "BEECHWOOD TALLBOY.dwg", "TALLBOY", "BEECHWOOD TALLBOY.obj", "BEECHWOOD TALLBOY.blend",
    unit_assumption=UNIT_MM + " (INSUNITS=4 mm)",
    part={
        "2D1": P("Kaki depan kanan", grup="Kaki"), "2D4": P("Kaki belakang kanan", grup="Kaki"),
        "2D7": P("Kaki depan kiri", grup="Kaki"), "2DA": P("Kaki belakang kiri", grup="Kaki"),
        "2DD": P("Rel atas depan"), "2DE": P("Rel atas belakang"),
        "2DF": P("Badan kabinet (carcass + top)"), "2E0": P("Panel belakang"),
        "2F6": P("Front laci 1", grup="Laci"), "2F2": P("Front laci 2", grup="Laci"), "2EE": P("Front laci 3", grup="Laci"),
        "2EA": P("Front laci 4", grup="Laci"), "2E6": P("Front laci 5", grup="Laci"),
        "2F3": P("Handle laci 1", "HANDLE", "Hardware"), "2EF": P("Handle laci 2", "HANDLE", "Hardware"),
        "2EB": P("Handle laci 3", "HANDLE", "Hardware"), "2E7": P("Handle laci 4", "HANDLE", "Hardware"),
        "2E3": P("Handle laci 5", "HANDLE", "Hardware"),
    },
    badan_handle="2DF",
    laci={str(i): {"part": [f, h], "travel_m": 0.3, "kotak": True} for i, (f, h) in enumerate(
        [("2F6", "2F3"), ("2F2", "2EF"), ("2EE", "2EB"), ("2EA", "2E7"), ("2E6", "2E3")], start=1)},
    fit_kolom=[{"front": ["2F6", "2F2", "2EE", "2EA", "2E6"], "z0_mm": -913.9, "z1_mm": 56.1, "celah_mm": 1.5,
                "ikut": {"2F6": ["2F3"], "2F2": ["2EF"], "2EE": ["2EB"], "2EA": ["2E7"], "2E6": ["2E3"]}}],
    catatan="Di DWG 5 front (5 x 194,7 = 973,5 mm) lebih tinggi 3,5 mm dari bukaan (970 mm) sehingga front teratas menembus rel atas 2,9 mm; "
            "front disusun ulang rata dalam bukaan dengan celah 1,5 mm (tinggi tiap front 191 mm).",
))

# 4. DINING TABLE ---------------------------------------------------------
resep.append(base("Beechwood Dining Table Altfield", "BEECHWOOD DINNING TABLE  ALTFIELD.dwg", "MEJA_MAKAN",
    "BEECHWOOD DINNING TABLE  ALTFIELD.obj", "BEECHWOOD DINNING TABLE  ALTFIELD.blend",
    unit_assumption=UNIT_MM + " (INSUNITS=1 inci di header, tetapi ukuran hanya masuk akal sebagai mm)",
    part={
        "29F": P("Top meja"),
        "278": P("Kaki kiri depan", grup="Kaki"), "274": P("Kaki kiri belakang", grup="Kaki"), "27C": P("Kaki ujung kiri", grup="Kaki"),
        "291": P("Kaki kanan depan", grup="Kaki"), "28E": P("Kaki kanan belakang", grup="Kaki"), "2A7": P("Kaki ujung kanan", grup="Kaki"),
        "2B4": P("Palang bawah kiri", grup="Kaki"), "2B7": P("Palang atas kiri", grup="Kaki"),
        "2B9": P("Palang bawah kanan", grup="Kaki"), "2BB": P("Palang atas kanan", grup="Kaki"),
        "2BA": P("Rel bawah memanjang", grup="Kaki"), "2BC": P("Rel atas memanjang", grup="Kaki"),
    },
    catatan="Handle 29F (top) punya >1 blob ACIS di file (riwayat edit); versi terakhir dipakai (2100 x 800 x 30 mm). Garis 2D (LINE/LWPOLYLINE tampak gambar) diabaikan.",
))

# 5. DINING CHAIR ---------------------------------------------------------
resep.append(base("Beechwood Dining Chair", "BEECHWOOD DINNING CHAIR.dwg", "KURSI_MAKAN", "BEECHWOOD DINNING CHAIR.obj", "BEECHWOOD DINNING CHAIR.blend",
    unit_assumption=UNIT_MM + " (INSUNITS=4 mm)",
    part={
        "2BA": P("Rangka samping kiri (kaki + sandaran)", grup="Kaki"), "2C9": P("Rangka samping kanan (kaki + sandaran)", grup="Kaki"),
        "2BD": P("Palang samping kiri", grup="Kaki"), "2C0": P("Palang samping kanan", grup="Kaki"),
        "2C3": P("Palang depan", grup="Kaki"), "2C6": P("Palang belakang", grup="Kaki"),
        "2E4": P("Dudukan baji depan"), "2E7": P("Dudukan baji belakang"),
        "2E1": P("Dudukan baji kiri+kanan"),
    },
    pisah_loose=[{"handle": "2E1", "sumbu": "X", "nama": ["Dudukan baji kiri", "Dudukan baji kanan"]}],
    buang=["2CC"],
    catatan="Solid 2CC kosong (tanpa data ACIS, 69 byte) dibuang. Dudukan terdiri dari 4 baji segitiga (pola diagonal): 2E4 depan, 2E7 belakang, 2E1 = kiri+kanan dalam satu solid (dipisah jadi dua objek). "
            "Baji dudukan menempati ketinggian yang sama dengan palang samping/depan/belakang (palang berada di dalam dudukan) dan ujung palang masuk ke rangka samping (tenon) - sesuai DWG, tidak diubah.",
))

# 6. CREDENZA (R14, polyface mesh) -----------------------------------------
def box(x0, y0, z0, x1, y1, z1):
    return [[x0, y0, z0], [x1, y1, z1]]


doors_x = [(-0.001, 0.449), (0.450, 0.900), (0.900, 1.350), (1.351, 1.801)]  # pintu overlay 447,7 mm, dari pengukuran bidang muka pintu
handle_boxes = [box(0.43, -0.001, 0.75, 0.445, 0.04, 0.812), box(0.455, -0.001, 0.75, 0.47, 0.04, 0.812),
                box(1.33, -0.001, 0.75, 1.345, 0.04, 0.812), box(1.355, -0.001, 0.75, 1.37, 0.04, 0.812)]
resep.append(base("Altfield Credenza SP 05", "SP 05 ALTFIELD CREDENZA.dwg", "CREDENZA", "SP 05 ALTFIELD CREDENZA.obj", "SP 05 ALTFIELD CREDENZA.blend",
    skala=0.01, mode="loose", weld_m=0.0002, junk_m=0.0, max_hole_m=0.0,
    geometry_source="DWG R14 (AC1014) POLYLINE_PFACE mesh (43.449 polyface, blok SP_05_ALTFIELD_CREDENZA_DW) -> OBJ per warna -> weld 0,2 mm -> pisah",
    unit_assumption="angka DWG dibaca sebagai cm (180 x 65,8 x 90 -> 1,80 x 0,66 x 0,90 m); R14 tidak punya INSUNITS",
    abaikan_objek=["warna_2"],
    pisah=[{"nama": f"Pintu {i+1}", "peran": "WOOD_A", "grup": "Pintu", "objek": ["warna_1"],
            "kotak_m": box(x0, -0.001, 0.19, x1, 0.0676, 0.901),
            "tolak": {"bidang": [1, 0.0675], "normal": [0, -1, 0]}, "kecuali": handle_boxes}
           for i, (x0, x1) in enumerate(doors_x)],
    loose_part=[
        P("Badan kabinet (carcass + top)", kotak_m=box(-0.01, 0.03, 0.18, 1.81, 0.67, 0.91)),
        P("Pintu 1", grup="Pintu", kotak_m=box(doors_x[0][0], -0.001, 0.19, doors_x[0][1], 0.0676, 0.901)),
        P("Pintu 2", grup="Pintu", kotak_m=box(doors_x[1][0], -0.001, 0.19, doors_x[1][1], 0.0676, 0.901)),
        P("Pintu 3", grup="Pintu", kotak_m=box(doors_x[2][0], -0.001, 0.19, doors_x[2][1], 0.0676, 0.901)),
        P("Pintu 4", grup="Pintu", kotak_m=box(doors_x[3][0], -0.001, 0.19, doors_x[3][1], 0.0676, 0.901)),
        P("Sekat vertikal 1", kotak_m=box(0.43, 0.06, 0.21, 0.47, 0.66, 0.88)),
        P("Sekat vertikal 2", kotak_m=box(0.88, 0.06, 0.21, 0.92, 0.66, 0.88)),
        P("Sekat vertikal 3", kotak_m=box(1.33, 0.06, 0.21, 1.37, 0.66, 0.88)),
        P("Panel belakang", kotak_m=box(0.01, 0.645, 0.2, 1.79, 0.665, 0.89)),
        P("Rak bay 1", kotak_m=box(0.02, 0.06, 0.53, 0.45, 0.66, 0.56)),
        P("Rak bay 2", kotak_m=box(0.455, 0.06, 0.53, 0.895, 0.66, 0.56)),
        P("Rak bay 3", kotak_m=box(0.905, 0.06, 0.53, 1.345, 0.66, 0.56)),
        P("Rak bay 4", kotak_m=box(1.355, 0.06, 0.53, 1.78, 0.66, 0.56)),
        P("Palang kaki tengah", grup="Kaki", kotak_m=box(0.08, 0.34, -0.001, 1.72, 0.39, 0.195)),
        P("Kaki kiri", grup="Kaki", kotak_m=box(0.57, 0.06, -0.001, 0.62, 0.66, 0.195)),
        P("Kaki kanan", grup="Kaki", kotak_m=box(1.18, 0.06, -0.001, 1.23, 0.66, 0.195)),
        P("Handle pintu 1", "HANDLE", "Hardware", kotak_m=handle_boxes[0]),
        P("Handle pintu 2", "HANDLE", "Hardware", kotak_m=handle_boxes[1]),
        P("Handle pintu 3", "HANDLE", "Hardware", kotak_m=handle_boxes[2]),
        P("Handle pintu 4", "HANDLE", "Hardware", kotak_m=handle_boxes[3]),
        P("Panel dalam sekat 1 (tersembunyi)", arsip=True, catatan="panel 20 mm yang berada sepenuhnya di dalam sekat vertikal 28 mm", kotak_m=box(0.435, 0.12, 0.27, 0.465, 0.6, 0.82)),
        P("Panel dalam sekat 2 (tersembunyi)", arsip=True, catatan="panel 20 mm yang berada sepenuhnya di dalam sekat vertikal 28 mm", kotak_m=box(0.885, 0.12, 0.27, 0.915, 0.6, 0.82)),
        P("Panel dalam sekat 3 (tersembunyi)", arsip=True, catatan="panel 20 mm yang berada sepenuhnya di dalam sekat vertikal 28 mm", kotak_m=box(1.335, 0.12, 0.27, 1.365, 0.6, 0.82)),
    ],
    catatan="Model mesh SketchUp-style (bukan solid): 4 pintu overlay 447,7 x 708,8 x 28 mm, 4 handle, carcass, 3 sekat, 4 rak, panel belakang, 2 kaki bilah + palang. "
            "Pintu 1 & 4 menyatu dengan carcass setelah weld -> dipisah menurut kotak muka (warna 23); panel cekung pintu (warna 18/254) dan pelat handle digabung ke pintu/handle-nya. "
            "Tiga panel tipis yang seluruhnya berada di dalam sekat vertikal disimpan di _ARSIP (geometri tersembunyi). 160.640 LINE (148.883 panjang 0) dan serpihan warna 0 (27 pulau < 2 mm) diabaikan.",
))

for r in resep:
    p = SP / "resep" / (Path(r["file_out"]).stem + ".json")
    p.write_text(json.dumps(r, indent=1, ensure_ascii=False), encoding="utf-8")
    print("resep:", p)
