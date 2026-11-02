# Perbaikan Bedside & Tallboy (keluarga rangka kaki 40 mm + carcass bengkok top/sisi):
# pecah carcass (mitre 45 deg), panel/rak dasar bertakik kaki, klos rel, kotak laci lengkap,
# collection per sub-rakitan. Pakai:
#   blender -b "<file>.blend" --python perbaiki_lemari.py -- [--simpan] <laporan.json>
import bpy, json, math, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import konstruksi_util as K
from konstruksi_util import MM, note, bounds, obj_prefix, sub, pindah, kotak, prisma, potong, uv_meter

root = next(o for o in bpy.data.objects if o.get("ns_product_root"))
NAMA = root.name.split(" | ", 1)[1]
prod = bpy.data.collections["PROD | " + NAMA]
CFG = {
    "Beechwood Bedside": {"dasar_lama": "Rak dasar", "dasar_depan": "kaki", "laci_z": 12.0, "laci_h": 87.0, "laci_d": 400.0, "geser_front": 0.0},
    "Beechwood Tallboy": {"dasar_lama": None, "dasar_depan": "front", "laci_z": 21.6, "laci_h": 140.0, "laci_d": 400.0, "geser_front": None},
}[NAMA]

C_CAR = sub("01 Carcass", prod)
C_RD = sub("02 Rangka depan", prod)
C_RB = sub("03 Rangka belakang", prod)
C_LACI = sub("04 Laci", prod)

# ------------------------------------------------------------ ukuran acuan
car = obj_prefix("Badan kabinet (carcass + top)")
clo, chi = bounds([car])
kdk = obj_prefix("Kaki depan kanan"); kbk = obj_prefix("Kaki belakang kanan")
X_OUT, Z_TOP, Z_BOT = chi.x / MM, chi.z / MM, clo.z / MM
T = 20.0
X_IN, Z_TOP_IN = X_OUT - T, Z_TOP - T
Y_F, Y_B = clo.y / MM, chi.y / MM                         # muka depan / belakang carcass
X_LEG = bounds([kdk])[0].x / MM                            # muka dalam kaki (x)
Y_LEG_F0 = bounds([kdk])[0].y / MM                         # muka depan kaki depan
pb = obj_prefix("Panel belakang")
Y_PB = bounds([pb])[0].y / MM                              # muka depan panel belakang
note(f"{NAMA}: carcass x ±{X_OUT:.1f} (dalam {X_IN:.1f}), z {Z_BOT:.1f}..{Z_TOP:.1f}, y {Y_F:.1f}..{Y_B:.1f}; kaki dalam x ±{X_LEG:.1f}; panel belakang y {Y_PB:.1f}")

# ------------------------------------------------------------ 1. carcass -> top + sisi kiri + sisi kanan (mitre 45 deg)
cxr, czr = X_IN - 20.0, Z_TOP_IN - 20.0
s = 1 / math.sqrt(2)
h = car["cad_handle"]
top = potong(car, f"Top (mitre 45°) | {h}", [((cxr, 0, czr), (s, 0, -s)), ((-cxr, 0, czr), (-s, 0, -s))])
ska = potong(car, f"Sisi kanan (mitre 45°) | {h}", [((cxr, 0, czr), (-s, 0, s)), ((0, 0, 0), (-1, 0, 0))])
ski = potong(car, f"Sisi kiri (mitre 45°) | {h}", [((-cxr, 0, czr), (s, 0, s)), ((0, 0, 0), (1, 0, 0))])
for o, g in ((top, "X"), (ska, "Z"), (ski, "Z")):
    pindah(o, C_CAR)
    uv_meter(o, g)
    o["geometry_source"] = car["geometry_source"] + "; dipecah per komponen (perbaiki_lemari.py)"
    o["sambungan"] = "mitre 45° pada lengkung sudut + lamello/dowel"
top["ukuran_potong_mm"] = f"{2 * X_OUT:.0f} x {Y_B - Y_F:.0f} x {T:.0f} (tepi lengkung)"
for o in (ska, ski):
    o["ukuran_potong_mm"] = f"{Z_TOP - Z_BOT:.0f} x {Y_B - Y_F:.0f} x {T:.0f}"
bpy.data.objects.remove(car)
note(f"Carcass {h} dipecah: top + sisi kiri + sisi kanan, mitre 45° lewat pusat lengkung ({cxr:.1f}, {czr:.1f}) mm")

# ------------------------------------------------------------ 2. rangka depan / belakang
for o in (kdk, obj_prefix("Kaki depan kiri"), obj_prefix("Rel atas depan")):
    pindah(o, C_RD)
for o in (kbk, obj_prefix("Kaki belakang kiri"), obj_prefix("Rel atas belakang")):
    pindah(o, C_RB)
for o in (obj_prefix("Rel atas depan"), obj_prefix("Rel atas belakang")):
    o["sambungan"] = "purus-lubang (mortise & tenon) ke kaki"
pindah(pb, C_RB)
pb["sambungan"] = "masuk alur di kaki belakang & rel atas belakang"

# ------------------------------------------------------------ 3. panel dasar bertakik kaki (menggantikan rak dasar lama bila ada)
T_BOT = 18.0
y_depan = Y_LEG_F0 if CFG["dasar_depan"] == "kaki" else bounds([obj_prefix("Front laci 1 ")])[1].y / MM
y_bel = Y_PB
# profil XY (x, y): bagian antara sisi carcass + lidah di antara kaki depan dan kaki belakang
prof = [(-X_LEG, y_depan), (X_LEG, y_depan), (X_LEG, Y_F), (X_IN, Y_F), (X_IN, Y_B), (X_LEG, Y_B), (X_LEG, y_bel),
        (-X_LEG, y_bel), (-X_LEG, Y_B), (-X_IN, Y_B), (-X_IN, Y_F), (-X_LEG, Y_F)]
nama_dasar = "Rak dasar 18 mm" if CFG["dasar_lama"] else "Panel dasar 18 mm"
dasar = prisma(nama_dasar, prof, "Z", Z_BOT, Z_BOT + T_BOT, "WOOD_A" if CFG["dasar_lama"] else "WOOD_B", C_CAR, root, "X")
dasar["sambungan"] = "dado/dowel ke sisi, bertakik 40 x 40 di keempat kaki"
if CFG["dasar_lama"]:
    lama = obj_prefix(CFG["dasar_lama"] + " |")
    K.arsipkan(lama, prod)
    lama.name = "Lama: " + lama.name
    dasar["geometry_source"] = f"dibangun ulang dari DWG {lama['cad_handle']} (panel 18 mm), takik kaki ditambahkan"
    note(f"Rak dasar DWG (menembus 4 kaki & sisi carcass) diganti panel bertakik; versi lama ke _ARSIP")
note(f"{nama_dasar}: z {Z_BOT:.1f}..{Z_BOT + T_BOT:.1f}, y {y_depan:.1f}..{y_bel:.1f}, takik kaki 40 x 40")

# ------------------------------------------------------------ 4. laci: front rata tengah, kotak lengkap, klos rel
SLIDE = 12.7
x0, x1 = -X_LEG + SLIDE, X_LEG - SLIDE
klos = []
n = 1
while bpy.data.objects.get(f"DRAWER_{n} | {NAMA}"):
    d = bpy.data.objects[f"DRAWER_{n} | {NAMA}"]
    front = obj_prefix(f"Front laci {n} "); handle = obj_prefix(f"Handle laci {n} ")
    flo, fhi = bounds([front])
    geser = -(flo.x + fhi.x) / 2 / MM          # rata tengah di antara kaki
    if abs(geser) > 0.05:
        front.location.x += geser * MM
        note(f"Front laci {n} digeser {geser:+.1f} mm supaya celah kiri = kanan (handle sudah di tengah)")
    c = sub(f"Laci {n}", C_LACI)
    pindah(front, c); pindah(handle, c)
    z0 = flo.z / MM + CFG["laci_z"]
    K.kotak_laci(n, d, c, x0, x1, fhi.y / MM, CFG["laci_d"], z0, CFG["laci_h"])
    klos.append((z0, z0 + CFG["laci_h"]))
    n += 1
for i, (z0, z1) in enumerate(klos, 1):
    zc = (z0 + z1) / 2
    hk = min(60.0, z1 - z0)
    for sisi, (a, b) in (("kiri", (-X_IN, -X_LEG)), ("kanan", (X_LEG, X_IN))):
        o = kotak(f"Klos rel laci {sisi} {i}", a, b, Y_F, Y_B - 10, zc - hk / 2, zc + hk / 2, "WOOD_B", C_CAR, root, "Y")
        o["sambungan"] = "dilem + sekrup ke sisi; dudukan rel laci rata muka dalam kaki"
note(f"Klos rel laci {2 * len(klos)} buah ({X_IN - X_LEG:.0f} mm) agar bidang rel rata muka dalam kaki (x = ±{X_LEG:.0f})")

# ------------------------------------------------------------ 5. bersihkan collection lama, laporan
K.hapus_collection_lama(("Badan", "Kaki", "Hardware", "Laci"), C_CAR, C_LACI)
for o in bpy.data.objects:
    if o.name.startswith("DRAWER_"):
        pindah(o, C_LACI)
K.tutup_laporan(prod, root, "carcass dipecah mitre, panel/rak dasar bertakik kaki, klos rel, kotak laci lengkap, "
                            "collection per sub-rakitan (perbaiki_lemari.py).")
if "--simpan" in sys.argv:
    bpy.ops.wm.save_mainfile(compress=True)
    note("Disimpan")
json.dump(K.laporan, open(sys.argv[-1], "w", encoding="utf-8"), indent=1, ensure_ascii=False)
