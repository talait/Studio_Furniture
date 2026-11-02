# Perbaikan SP 05 Altfield Credenza: carcass shell terbuka (R14/SketchUp) diganti 4 panel tertutup
# bersambungan mitre 45 deg (sesuai sudut di DWG), sekat vertikal dibangun ulang jadi panel tertutup,
# collection per sub-rakitan. Pakai:
#   blender -b "<file>.blend" --python perbaiki_credenza.py -- [--simpan] <laporan.json>
import bpy, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import konstruksi_util as K
from konstruksi_util import MM, note, bounds, obj_prefix, sub, pindah, kotak, prisma

root = next(o for o in bpy.data.objects if o.get("ns_product_root"))
NAMA = root.name.split(" | ", 1)[1]
prod = bpy.data.collections["PROD | " + NAMA]
C_CAR = sub("01 Carcass", prod)
C_PINTU = sub("02 Pintu", prod)
C_KAKI = sub("03 Kaki", prod)

car = obj_prefix("Badan kabinet (carcass + top)")
role = car.get("ns_role_part", "WOOD_A")
ws = [car.matrix_world @ v.co for v in car.data.vertices]
X_OUT = max(w.x for w in ws) / MM
Z_TOP, Z_BOT = max(w.z for w in ws) / MM, min(w.z for w in ws) / MM
Y_F, Y_B = min(w.y for w in ws) / MM, max(w.y for w in ws) / MM
# tebal panel dari muka dalam (normal ±X / ±Z di dalam kotak)
X_IN = max(abs(w.x) for w in ws if abs(w.x) < X_OUT * MM - 0.005) / MM
Z_TOP_IN = max(w.z for w in ws if w.z < Z_TOP * MM - 0.005) / MM
Z_BOT_IN = min(w.z for w in ws if w.z > Z_BOT * MM + 0.005) / MM
note(f"Carcass: x ±{X_OUT:.1f} (dalam {X_IN:.1f}), z {Z_BOT:.1f}/{Z_BOT_IN:.1f} .. {Z_TOP_IN:.1f}/{Z_TOP:.1f}, y {Y_F:.1f}..{Y_B:.1f}")

panel = {
    "Top (mitre 45°)": [(-X_OUT, Z_TOP), (-X_IN, Z_TOP_IN), (X_IN, Z_TOP_IN), (X_OUT, Z_TOP)],
    "Panel dasar (mitre 45°)": [(-X_OUT, Z_BOT), (X_OUT, Z_BOT), (X_IN, Z_BOT_IN), (-X_IN, Z_BOT_IN)],
    "Sisi kanan (mitre 45°)": [(X_IN, Z_BOT_IN), (X_OUT, Z_BOT), (X_OUT, Z_TOP), (X_IN, Z_TOP_IN)],
    "Sisi kiri (mitre 45°)": [(-X_IN, Z_BOT_IN), (-X_IN, Z_TOP_IN), (-X_OUT, Z_TOP), (-X_OUT, Z_BOT)],
}
src = car.get("geometry_source", "DWG R14 pface") + "; dibangun ulang jadi panel tertutup (perbaiki_credenza.py)"
for nm, prof in panel.items():
    o = prisma(nm, prof, "Y", Y_F, Y_B, role, C_CAR, root, "X" if nm.startswith(("Top", "Panel")) else "Z", src)
    o["sambungan"] = "mitre 45° di keempat sudut kotak (sesuai DWG) + lamello/dowel"
K.arsipkan(car, prod)
car.name = "Lama: " + car.name
note("Carcass shell terbuka (23 muka) diganti 4 panel tertutup: top, panel dasar, sisi kiri, sisi kanan (mitre 45°); versi lama ke _ARSIP")

# sekat vertikal: shell dengan muka dalam -> panel tertutup dari bbox, tinggi pas di antara dasar & top
for i in (1, 2, 3):
    lama = obj_prefix(f"Sekat vertikal {i}")
    lo, hi = bounds([lama])
    t = (hi.x - lo.x) / MM
    o = kotak(f"Sekat vertikal {i} {t:.0f} mm", lo.x / MM, hi.x / MM, lo.y / MM, hi.y / MM, Z_BOT_IN, Z_TOP_IN,
              lama.get("ns_role_part", role), C_CAR, root, "Z", src)
    o["sambungan"] = "dado ke panel dasar & top; rak bay masuk alur 4 mm"
    K.arsipkan(lama, prod)
    lama.name = "Lama: " + lama.name
note("Sekat vertikal 1–3 dibangun ulang jadi panel tertutup (shell lama punya muka dalam), tinggi dipaskan antara dasar & top")

for o in [o for o in bpy.data.objects if o.name.startswith("Rak bay")]:
    pindah(o, C_CAR)
    o["sambungan"] = "masuk alur 4 mm di sekat / sisi (sesuai DWG)"
pb = obj_prefix("Panel belakang")
pindah(pb, C_CAR)
pb["sambungan"] = "masuk alur 9 mm di sisi, top & dasar (sesuai DWG)"

for i in (1, 2, 3, 4):
    c = sub(f"Pintu {i}", C_PINTU)
    pindah(obj_prefix(f"Pintu {i}"), c)
    pindah(obj_prefix(f"Handle pintu {i}"), c)
for o in (obj_prefix("Kaki kiri"), obj_prefix("Kaki kanan"), obj_prefix("Palang kaki tengah")):
    pindah(o, C_KAKI)
obj_prefix("Palang kaki tengah")["sambungan"] = "purus-lubang ke kaki kiri & kanan"

K.hapus_collection_lama(("Badan", "Pintu", "Kaki", "Hardware"), C_CAR, C_CAR)
K.tutup_laporan(prod, root, "carcass & sekat dibangun ulang jadi panel tertutup (mitre 45°), collection per sub-rakitan (perbaiki_credenza.py).")
if "--simpan" in sys.argv:
    bpy.ops.wm.save_mainfile(compress=True)
    note("Disimpan")
json.dump(K.laporan, open(sys.argv[-1], "w", encoding="utf-8"), indent=1, ensure_ascii=False)
