"""blender -b --factory-startup --python analisis_credenza.py -- in.obj skala out.json
Impor OBJ, weld, pisah loose parts, cetak ukuran tiap bagian (meter)."""
import bmesh
import bpy
import json
import sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
obj_path, scale, out_json = argv[0], float(argv[1]), argv[2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=obj_path, forward_axis="Y", up_axis="Z", global_scale=scale)
objs = [o for o in bpy.context.selected_objects if o.type == "MESH"]
print("objek warna:", [(o.name, len(o.data.polygons)) for o in objs])
bpy.ops.object.select_all(action="DESELECT")
for o in objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.join()
o = bpy.context.object
bm = bmesh.new()
bm.from_mesh(o.data)
print("sebelum weld: v", len(bm.verts), "f", len(bm.faces))
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0002)  # 0.2 mm
bmesh.ops.dissolve_degenerate(bm, dist=0.00005, edges=bm.edges)
print("sesudah weld: v", len(bm.verts), "f", len(bm.faces))
bm.to_mesh(o.data)
bm.free()
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.separate(type="LOOSE")
bpy.ops.object.mode_set(mode="OBJECT")
parts = [p for p in bpy.context.scene.objects if p.type == "MESH"]
rows = []
for p in parts:
    pts = [p.matrix_world @ v.co for v in p.data.vertices]
    lo = [min(q[i] for q in pts) for i in range(3)]
    hi = [max(q[i] for q in pts) for i in range(3)]
    # warna dominan dari slot material
    cols = {}
    for poly in p.data.polygons:
        cols[poly.material_index] = cols.get(poly.material_index, 0) + 1
    mi = max(cols, key=cols.get) if cols else -1
    mname = p.data.materials[mi].name if 0 <= mi < len(p.data.materials) and p.data.materials[mi] else "?"
    rows.append({"faces": len(p.data.polygons), "verts": len(p.data.vertices),
                 "min": [round(v, 4) for v in lo], "max": [round(v, 4) for v in hi],
                 "size": [round(hi[i] - lo[i], 4) for i in range(3)], "mat": mname})
rows.sort(key=lambda r: -(r["size"][0] * r["size"][1] * r["size"][2]))
print("jumlah loose parts:", len(rows))
for r in rows[:80]:
    print(f'  f{r["faces"]:6d} v{r["verts"]:6d} min {r["min"]} size {r["size"]} {r["mat"]}')
small = [r for r in rows if max(r["size"]) < 0.01]
print("bagian < 1 cm:", len(small))
json.dump(rows, open(out_json, "w"), indent=1)
