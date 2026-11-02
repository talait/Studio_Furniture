# Perbaikan Beechwood Dining Table Altfield: part dari DWG sudah terpisah per komponen dengan sambungan
# half-lap; di sini hanya disusun ulang per sub-rakitan, diberi catatan sambungan, dan lubang mikro top ditutup.
# Pakai: blender -b "<file>.blend" --python perbaiki_meja.py -- [--simpan] <laporan.json>
import bpy, bmesh, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import konstruksi_util as K
from konstruksi_util import note, obj_prefix, sub, pindah, periksa

root = next(o for o in bpy.data.objects if o.get("ns_product_root"))
NAMA = root.name.split(" | ", 1)[1]
prod = bpy.data.collections["PROD | " + NAMA]
grup = {
    "01 Top": [("Top meja", "disekrup ke rel atas memanjang & palang atas lewat klos/bracket")],
    "02 Rangka kaki kiri": [("Kaki kiri depan", "purus-lubang ke palang atas & bawah kiri"),
                            ("Kaki kiri belakang", "purus-lubang ke palang atas & bawah kiri"),
                            ("Palang atas kiri", "half-lap dengan rel atas memanjang"),
                            ("Palang bawah kiri", "half-lap dengan rel bawah memanjang")],
    "03 Rangka kaki kanan": [("Kaki kanan depan", "purus-lubang ke palang atas & bawah kanan"),
                             ("Kaki kanan belakang", "purus-lubang ke palang atas & bawah kanan"),
                             ("Palang atas kanan", "half-lap dengan rel atas memanjang"),
                             ("Palang bawah kanan", "half-lap dengan rel bawah memanjang")],
    "04 Rangka tengah memanjang": [("Rel atas memanjang", "half-lap dengan palang atas kiri & kanan; purus ke kaki ujung"),
                                   ("Rel bawah memanjang", "half-lap dengan palang bawah kiri & kanan; purus ke kaki ujung"),
                                   ("Kaki ujung kiri", "lubang purus untuk rel atas & bawah memanjang"),
                                   ("Kaki ujung kanan", "lubang purus untuk rel atas & bawah memanjang")],
}
for cn, items in grup.items():
    c = sub(cn, prod)
    for nm, smb in items:
        o = obj_prefix(nm + " |")
        pindah(o, c)
        o["sambungan"] = smb

# lubang mikro di top (blend sudut): tutup hanya loop tepi terbuka yang kecil
top = obj_prefix("Top meja |")
sebelum = periksa(top)["nonmanifold"]
bm = bmesh.new(); bm.from_mesh(top.data)
bnd = [e for e in bm.edges if e.is_boundary]
if bnd:
    bmesh.ops.holes_fill(bm, edges=bnd, sides=0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
bm.to_mesh(top.data); bm.free()
sesudah = periksa(top)["nonmanifold"]
note(f"Top meja: tepi non-manifold {sebelum} -> {sesudah}")

K.hapus_collection_lama(("Badan", "Kaki"), bpy.data.collections["01 Top"], prod)
K.tutup_laporan(prod, root, "disusun ulang per sub-rakitan (top, rangka kaki kiri/kanan, rangka tengah memanjang) (perbaiki_meja.py).")
if "--simpan" in sys.argv:
    bpy.ops.wm.save_mainfile(compress=True)
    note("Disimpan")
json.dump(K.laporan, open(sys.argv[-1], "w", encoding="utf-8"), indent=1, ensure_ascii=False)
