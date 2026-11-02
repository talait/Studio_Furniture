"""blender -b <file.blend> --python verifikasi.py -- keluaran.json
Buka ulang file produk dan periksa: unit, struktur, objek, dimensi, lantai Z=0, tanpa kamera/lampu, material peran, driver laci."""
import bpy
import json
import sys
from mathutils import Vector

out_json = sys.argv[sys.argv.index("--") + 1]
scene = bpy.context.scene
res = {"file": bpy.data.filepath, "scene": scene.name, "unit": [scene.unit_settings.system, scene.unit_settings.length_unit, scene.unit_settings.scale_length],
       "objek": [], "koleksi": [], "masalah": []}


def walk(c, d=0):
    lc = None
    res["koleksi"].append({"nama": c.name, "level": d, "jumlah_objek": len(c.objects)})
    for ch in c.children:
        walk(ch, d + 1)


walk(scene.collection)
excluded = set()


def walk_lc(lc):
    if lc.exclude:
        excluded.add(lc.collection.name)
    for ch in lc.children:
        walk_lc(ch)


walk_lc(bpy.context.view_layer.layer_collection)
res["koleksi_dikecualikan"] = sorted(excluded)
roots = [o for o in bpy.data.objects if o.get("ns_product_root")]
res["root"] = [{"nama": r.name, "dimensions_cm": list(r.get("dimensions_cm", [])), "source": r.get("source", ""), "catatan": r.get("catatan", "")} for r in roots]
if len(roots) != 1:
    res["masalah"].append(f"root produk: {len(roots)} (harus 1)")
for o in bpy.data.objects:
    if o.type in ("CAMERA", "LIGHT"):
        res["masalah"].append(f"ada {o.type} di file: {o.name}")
pts = []
for o in bpy.data.objects:
    d = {"nama": o.name, "tipe": o.type, "koleksi": [c.name for c in o.users_collection], "parent": o.parent.name if o.parent else None}
    if o.type == "MESH":
        d["dimensi_mm"] = [round(v * 1000, 1) for v in o.dimensions]
        d["verts"] = len(o.data.vertices)
        d["faces"] = len(o.data.polygons)
        d["material"] = [m.name for m in o.data.materials if m]
        d["ns_role_part"] = o.get("ns_role_part")
        d["cad_handle"] = o.get("cad_handle")
        d["modifier"] = [m.type for m in o.modifiers]
        d["uv"] = [uv.name for uv in o.data.uv_layers]
        if not d["material"]:
            res["masalah"].append(f"tanpa material: {o.name}")
        if o.users_collection and o.users_collection[0].name not in excluded:
            pts += [o.matrix_world @ v.co for v in o.data.vertices]
        if o.scale != Vector((1, 1, 1)) or any(abs(r) > 1e-6 for r in o.rotation_euler):
            res["masalah"].append(f"transformasi belum diterapkan: {o.name}")
    if o.type == "EMPTY" and o.get("ns_drawer"):
        d["ns_drawer"] = o["ns_drawer"]
        d["Open (m)"] = o.get("Open (m)")
        d["driver"] = bool(o.animation_data and o.animation_data.drivers)
        d["anak"] = [c.name for c in o.children]
    res["objek"].append(d)
if pts:
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    res["bbox_aktif_mm"] = {"min": [round(v * 1000, 1) for v in lo], "max": [round(v * 1000, 1) for v in hi], "ukuran": [round(v * 1000, 1) for v in (hi - lo)]}
    if abs(lo.z) > 0.0005:
        res["masalah"].append(f"dasar tidak di Z=0: {lo.z*1000:.1f} mm")
    if abs(lo.x + hi.x) > 0.001 or abs(lo.y + hi.y) > 0.001:
        res["masalah"].append(f"tidak terpusat di XY: {[(lo.x+hi.x)*500, (lo.y+hi.y)*500]} mm")
res["jumlah_mesh"] = sum(1 for o in bpy.data.objects if o.type == "MESH")
res["material"] = [{"nama": m.name, "ns_role": m.get("ns_role")} for m in bpy.data.materials]
res["gambar_belum_pack"] = [i.name for i in bpy.data.images if i.users and not i.packed_file]
json.dump(res, open(out_json, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("VERIF", bpy.data.filepath, "mesh", res["jumlah_mesh"], "masalah", res["masalah"], "ukuran", res.get("bbox_aktif_mm", {}).get("ukuran"))
