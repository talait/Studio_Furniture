"""Bangun file produk .blend dari OBJ hasil dwg2obj / credenza_extract, mengikuti STANDAR_FILE_PRODUK v2.

blender -b --factory-startup --python bangun_beechwood.py -- resep.json
Keluaran: file .blend (compressed), thumbnail Workbench 512 px, laporan JSON (<blend>.laporan.json di scratchpad).
"""
import bmesh
import bpy
import json
import math
import sys
from pathlib import Path
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
R = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
SCALE = float(R["skala"])
laporan = {"nama": R["nama"], "catatan": [], "part": [], "masalah": []}


def note(msg):
    print("  -", msg)
    laporan["catatan"].append(msg)


def bounds(objs):
    pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return lo, hi


def handle_of(o):
    return o.name.split("Solid_")[-1] if o.name.startswith("Solid_") else o.name


# ------------------------------------------------------------------ impor
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 1.0
scene.unit_settings.length_unit = "CENTIMETERS"
bpy.ops.wm.obj_import(filepath=R["sumber_obj"], forward_axis="Y", up_axis="Z", global_scale=SCALE)
imported = [o for o in bpy.context.selected_objects if o.type == "MESH"]
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)  # skala impor -> koordinat mesh (meter)
for o in imported:
    o.data.materials.clear()
print("impor:", len(imported), "objek")


sys.path.insert(0, str(Path(__file__).resolve().parent))
from bersih import clean, periksa, vertices_inside

# ------------------------------------------------------------------ mode loose (credenza)
if R.get("mode") == "loose":
    for o in list(imported):
        if o.name in R.get("abaikan_objek", []):
            note(f"objek impor '{o.name}' diabaikan ({len(o.data.polygons)} muka, serpihan)")
            bpy.data.objects.remove(o)
            continue
        clean(o, R.get("weld_m", 0.0002), R.get("tjunc_m", 0.0003), max_hole=0.0, junk_m=0.0)
        for rule in R.get("pisah", []):
            if rule.get("objek") and o.name not in rule["objek"]:
                continue
            lo, hi = Vector(rule["kotak_m"][0]), Vector(rule["kotak_m"][1])
            size = hi - lo
            tolak = rule.get("tolak")
            kecuali = [(Vector(k[0]), Vector(k[1])) for k in rule.get("kecuali", [])]
            bm = bmesh.new()
            bm.from_mesh(o.data)

            def in_box(f):
                c = f.calc_center_median()
                if not all(lo[i] <= c[i] <= hi[i] for i in range(3)):
                    return False
                fl = [min(v.co[i] for v in f.verts) for i in range(3)]
                fh = [max(v.co[i] for v in f.verts) for i in range(3)]
                if not all(fh[i] - fl[i] <= size[i] + 0.002 for i in range(3)):
                    return False
                if tolak and abs(c[tolak["bidang"][0]] - tolak["bidang"][1]) < 0.0005 and f.normal.dot(Vector(tolak["normal"])) > 0.5:
                    return False
                for klo, khi in kecuali:
                    if all(klo[i] <= c[i] <= khi[i] for i in range(3)):
                        return False
                return True

            sel = [f for f in bm.faces if in_box(f)]
            if not sel:
                bm.free()
                continue
            new_bm = bmesh.new()
            vmap = {}
            for f in sel:
                vs = []
                for v in f.verts:
                    if v not in vmap:
                        vmap[v] = new_bm.verts.new(v.co)
                    vs.append(vmap[v])
                try:
                    new_bm.faces.new(vs)
                except ValueError:
                    pass
            bmesh.ops.delete(bm, geom=sel, context="FACES")
            bm.to_mesh(o.data)
            bm.free()
            me = bpy.data.meshes.new(rule["nama"])
            new_bm.to_mesh(me)
            new_bm.free()
            no = bpy.data.objects.new(rule["nama"], me)
            scene.collection.objects.link(no)
            no["_resep"] = json.dumps({k: v for k, v in rule.items() if k in ("nama", "peran", "grup", "catatan", "arsip")})
            note(f"pisah '{rule['nama']}' dari {o.name}: {len(sel)} muka")
        o.data.update()
        if len(o.data.polygons) == 0:
            bpy.data.objects.remove(o)
            continue
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.separate(type="LOOSE")
        bpy.ops.object.mode_set(mode="OBJECT")
    parts = [o for o in scene.objects if o.type == "MESH"]
    # cocokkan loose part ke daftar resep lewat pusat bbox
    cfgs = {}
    part_objs = []
    unmatched = 0
    for o in parts:
        if o.get("_resep"):
            cfg = json.loads(o["_resep"])
            del o["_resep"]
        else:
            lo, hi = bounds([o])
            c = (lo + hi) / 2
            cfg = None
            best_vol = None
            for cand in R.get("loose_part", []):
                klo, khi = Vector(cand["kotak_m"][0]), Vector(cand["kotak_m"][1])
                if all(klo[i] <= c[i] <= khi[i] for i in range(3)) and all(klo[i] - 0.002 <= lo[i] and hi[i] <= khi[i] + 0.002 for i in range(3)):
                    vol = (khi - klo).x * (khi - klo).y * (khi - klo).z
                    if best_vol is None or vol < best_vol:
                        cfg, best_vol = cand, vol
            if cfg is None:
                unmatched += 1
                cfg = {"nama": f"Bagian tak dikenal {unmatched:02d}", "peran": "WOOD_A", "grup": "Badan"}
                sz = hi - lo
                note(f"loose part tak cocok resep: ukuran mm {[round(v*1000,1) for v in sz]} min {[round(v*1000,1) for v in lo]} muka {len(o.data.polygons)}")
        if len(o.data.polygons) == 0:
            bpy.data.objects.remove(o)
            continue
        c = dict(cfg)
        c["handle"] = cfg.get("handle", "pface")
        o.name = cfg["nama"]
        part_objs.append((o, c))
    # gabungkan pulau-pulau yang memetakan ke part resep yang sama (satu komponen fisik = satu objek)
    by_name = {}
    for o, c in part_objs:
        by_name.setdefault(c["nama"], []).append((o, c))
    part_objs = []
    for nama, grp in by_name.items():
        if len(grp) > 1:
            grp.sort(key=lambda oc: -len(oc[0].data.polygons))
            bpy.ops.object.select_all(action="DESELECT")
            for o, c in grp:
                o.select_set(True)
            bpy.context.view_layer.objects.active = grp[0][0]
            bpy.ops.object.join()
            note(f"'{nama}': {len(grp)} pulau digabung jadi satu objek ({len(grp[0][0].data.polygons)} muka)")
            grp[0][0].name = nama
        part_objs.append(grp[0])
else:
    # ------------------------------------------------------------------ mode solid (satu objek per 3DSOLID)
    part_cfg = R.get("part", {})
    part_objs = []
    for o in imported:
        h = handle_of(o)
        cfg = dict(part_cfg.get(h, {}))
        if h in R.get("buang", []):
            note(f"solid {h} dibuang (sesuai resep)")
            bpy.data.objects.remove(o)
            continue
        if not cfg:
            lo, hi = bounds([o])
            sz = (hi - lo) * 1000
            note(f"solid {h} tidak ada di resep, ukuran mm {[round(v,1) for v in sz]}")
            cfg = {"nama": f"Part {h}", "peran": "WOOD_A", "grup": "Badan"}
        cfg["handle"] = h
        # geser / skala dalam koordinat CAD (mm)
        g = R.get("geser_mm", {}).get(h)
        if g:
            for v in o.data.vertices:
                v.co += Vector(g) * SCALE
        sk = R.get("skala_x", {}).get(h)
        if sk:
            x0 = sk["x0_mm"] * SCALE
            for v in o.data.vertices:
                v.co.x = x0 + (v.co.x - x0) * sk["faktor"]
            note(f"{cfg['nama']} ({h}) diskalakan X x{sk['faktor']:.4f} dari x0={sk['x0_mm']} mm")
        o.name = f"{cfg['nama']} | {h}"
        part_objs.append((o, cfg))

# ------------------------------------------------------------------ bersihkan mesh
for o, cfg in part_objs:
    tj = R.get("tjunc_m", 0.0003) if cfg.get("peran") != "HANDLE" else min(R.get("tjunc_m", 0.0003), 0.0001)
    v0, f0, nsplit = clean(o, R.get("weld_m", 0.00001), tj, max_hole=R.get("max_hole_m", 0.25), junk_m=R.get("junk_m", 0.003))
    cfg["_before"] = (v0, f0)
    cfg["_tjunc"] = nsplit

# ------------------------------------------------------------------ penyesuaian front laci (celah bayangan / fit kolom)
objs_by_handle = {cfg["handle"]: o for o, cfg in part_objs}
objs_by_name = {o.name.split(" | ")[0]: o for o, cfg in part_objs}


def obj_for(key):
    return objs_by_handle.get(key) or objs_by_name.get(key)


for fit in R.get("fit_kolom", []):
    fronts = [obj_for(h) for h in fit["front"]]
    z0, z1 = fit["z0_mm"] * SCALE, fit["z1_mm"] * SCALE
    reveal = fit.get("celah_mm", 1.5) * SCALE
    n = len(fronts)
    pitch = (z1 - z0) / n
    fronts = sorted(fronts, key=lambda o: bounds([o])[0].z)
    for i, fr in enumerate(fronts):
        lo, hi = bounds([fr])
        old_c, old_h = (lo.z + hi.z) / 2, hi.z - lo.z
        new_c, new_h = z0 + (i + 0.5) * pitch, pitch - 2 * reveal
        k = new_h / old_h
        for v in fr.data.vertices:
            v.co.z = new_c + (v.co.z - old_c) * k
        for hh in fit.get("ikut", {}).get(fr.name.split(" | ")[-1], []):
            ho = obj_for(hh)
            for v in ho.data.vertices:
                v.co.z += new_c - old_c
        if abs(k - 1) > 0.002 or abs(new_c - old_c) > 0.0005:
            note(f"{fr.name}: tinggi {old_h*1000:.1f} -> {new_h*1000:.1f} mm, pusat geser {(new_c-old_c)*1000:+.1f} mm (fit kolom {fit['z0_mm']}..{fit['z1_mm']} mm, celah {fit.get('celah_mm',1.5)} mm)")

# ------------------------------------------------------------------ potong (boolean difference) mis. takik rak untuk kaki
def prism_cutter(src, z0, z1):
    """Pemotong bersih: convex hull penampang XY `src` (vertex dalam rentang z0..z1) ditarik sepanjang z0-1mm..z1+1mm."""
    pts2 = [(v.co.x, v.co.y) for v in src.data.vertices if z0 - 0.001 <= v.co.z <= z1 + 0.001]
    if len(pts2) < 3:
        pts2 = [(v.co.x, v.co.y) for v in src.data.vertices]
    bm = bmesh.new()
    for x, y in pts2:
        bm.verts.new((x, y, z0 - 0.001))
        bm.verts.new((x, y, z1 + 0.001))
    bmesh.ops.convex_hull(bm, input=bm.verts)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.00001)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("pemotong")
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new("pemotong", me)
    scene.collection.objects.link(o)
    return o


for cut in R.get("potong", []):
    target = obj_for(cut["target"])
    tlo, thi = bounds([target])
    for h in cut["pemotong"]:
        c = obj_for(h)
        cutter = prism_cutter(c, tlo.z, thi.z) if cut.get("mode", "prisma") == "prisma" else c
        mod = target.modifiers.new("Potong", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = cut.get("solver", "EXACT")
        if mod.solver == "EXACT":
            mod.use_self = bool(cut.get("use_self", True))
            mod.use_hole_tolerant = bool(cut.get("hole_tolerant", True))
        mod.object = cutter
        bpy.context.view_layer.objects.active = target
        f_before = len(target.data.polygons)
        bpy.ops.object.modifier_apply(modifier=mod.name)
        note(f"{target.name} ditakik (boolean difference, prisma penampang {c.name}): muka {f_before} -> {len(target.data.polygons)}")
        if cutter is not c:
            bpy.data.objects.remove(cutter)
    clean(target, R.get("weld_m", 0.00001), R.get("tjunc_m", 0.0003), max_hole=0.0)

# ------------------------------------------------------------------ pisah satu solid menjadi beberapa objek (pulau lepas), urut sumbu
from bersih import vertex_islands
for sp in R.get("pisah_loose", []):
    src = obj_for(sp["handle"])
    cfg_src = next(c for o, c in part_objs if o is src)
    bm = bmesh.new()
    bm.from_mesh(src.data)
    islands = vertex_islands(bm)
    axis = "XYZ".index(sp.get("sumbu", "X"))
    islands.sort(key=lambda isl: sum(v.co[axis] for v in isl) / len(isl))
    if len(islands) != len(sp["nama"]):
        note(f"pisah_loose {sp['handle']}: {len(islands)} pulau, resep punya {len(sp['nama'])} nama -> dilewati")
        bm.free()
        continue
    part_objs = [(o, c) for o, c in part_objs if o is not src]
    for isl, nama in zip(islands, sp["nama"]):
        nb = bmesh.new()
        vmap = {}
        faces = {f for v in isl for f in v.link_faces}
        for f in faces:
            vs = []
            for v in f.verts:
                if v not in vmap:
                    vmap[v] = nb.verts.new(v.co)
                vs.append(vmap[v])
            nb.faces.new(vs)
        me = bpy.data.meshes.new(nama)
        nb.to_mesh(me)
        nb.free()
        o = bpy.data.objects.new(f"{nama} | {sp['handle']}", me)
        scene.collection.objects.link(o)
        c = dict(cfg_src)
        c["nama"] = nama
        part_objs.append((o, c))
        note(f"{sp['handle']} dipisah menjadi '{nama}' ({len(faces)} muka)")
    bm.free()
    bpy.data.objects.remove(src)
    objs_by_handle = {cfg["handle"]: o for o, cfg in part_objs}
    objs_by_name = {o.name.split(" | ")[0]: o for o, cfg in part_objs}

# ------------------------------------------------------------------ pusatkan: tengah XY, lantai Z=0 (hanya part yang dipakai)
aktif = [o for o, cfg in part_objs if not cfg.get("arsip")]
lo, hi = bounds(aktif)
offset = Vector((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z))
for o, cfg in part_objs:
    for v in o.data.vertices:
        v.co += offset
lo, hi = bounds(aktif)
size = hi - lo
dims_cm = [round(float(v) * 100, 2) for v in size]
print("UKURAN L x D x T mm:", [round(v * 1000, 1) for v in size])

# ------------------------------------------------------------------ struktur: collection, root, grup
nama = R["nama"]
coll = bpy.data.collections.new("PROD | " + nama)
scene.collection.children.link(coll)
coll["ns_product"] = True
coll["category"] = R.get("kategori", "")
groups = {}
for g in ("Badan", "Laci", "Pintu", "Hardware"):
    pass


def group_coll(name):
    if name not in groups:
        c = bpy.data.collections.new(name)
        coll.children.link(c)
        groups[name] = c
    return groups[name]


root = bpy.data.objects.new("PRODUCT_ROOT | " + nama, None)
root.empty_display_type = "PLAIN_AXES"
root.empty_display_size = 0.12
coll.objects.link(root)
root["ns_product_root"] = True

arsip_coll = None


def link_only(o, c):
    for old in list(o.users_collection):
        old.objects.unlink(o)
    c.objects.link(o)


def set_origin_center(o):
    lo, hi = bounds([o])
    c = (lo + hi) / 2
    delta = c - o.location  # objek tanpa rotasi/skala
    for v in o.data.vertices:
        v.co -= delta
    o.location = c


# materials per peran
ROLE_COLORS = {"WOOD_A": (0.60, 0.42, 0.25, 1), "WOOD_B": (0.74, 0.62, 0.47, 1), "HANDLE": (0.55, 0.45, 0.30, 1), "METAL": (0.42, 0.44, 0.46, 1)}


def role_material(role):
    name = "ROLE | " + role
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = ROLE_COLORS.get(role, (0.6, 0.6, 0.6, 1))
    b.inputs["Roughness"].default_value = {"HANDLE": 0.3, "METAL": 0.35, "WOOD_B": 0.62}.get(role, 0.5)
    b.inputs["Metallic"].default_value = 1.0 if role in ("HANDLE", "METAL") else 0.0
    m.diffuse_color = ROLE_COLORS.get(role, (0.6, 0.6, 0.6, 1))
    m["ns_role"] = role
    return m


def uv_meter(obj, grain):
    for old in list(obj.data.uv_layers):
        obj.data.uv_layers.remove(old)
    uv = obj.data.uv_layers.new(name="UV meter")
    uv.active = uv.active_render = True
    g = "XYZ".index(grain)
    for p in obj.data.polygons:
        n = max(range(3), key=lambda a: abs(p.normal[a]))
        gg = g if g != n else (2 if n != 2 else 0)
        u_axis = next(a for a in (0, 1, 2) if a not in (n, gg))
        for ix in p.loop_indices:
            v = obj.data.vertices[obj.data.loops[ix].vertex_index].co
            uv.data[ix].uv = (v[u_axis], v[gg])


def grain_axis(obj, cfg):
    if cfg.get("serat") in ("X", "Y", "Z"):
        return cfg["serat"]
    lo, hi = bounds([obj])
    sz = hi - lo
    thinnest = min(range(3), key=lambda a: sz[a])
    return "X" if thinnest == 2 else "Z"


def bevel(obj, width):
    mod = obj.modifiers.new("Bevel tepi", "BEVEL")
    mod.width = width
    mod.segments = 3
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(42)
    mod.harden_normals = True
    wn = obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    wn.keep_sharp = True
    wn.weight = 40
    for p in obj.data.polygons:
        p.use_smooth = True


# laci: empties
drawers = {}
for key, lc in R.get("laci", {}).items():
    n = int(key)
    travel = float(lc.get("travel_m", 0.25))
    d = bpy.data.objects.new(f"DRAWER_{n} | {nama}", None)
    d.empty_display_type = "ARROWS"
    d.empty_display_size = 0.08
    group_coll("Laci").objects.link(d)
    d.parent = root
    d["ns_drawer"] = n
    d["Open (m)"] = 0.0
    d.id_properties_ui("Open (m)").update(min=0, max=travel, soft_min=0, soft_max=travel)
    drv = d.driver_add("location", 1).driver
    drv.type = "SCRIPTED"
    var = drv.variables.new()
    var.name = "opening"
    var.type = "SINGLE_PROP"
    var.targets[0].id = d
    var.targets[0].data_path = '["Open (m)"]'
    drv.expression = "-opening"
    drawers[n] = (d, lc, [])

all_meshes = []
for o, cfg in part_objs:
    o.parent = root
    if cfg.get("arsip"):
        if arsip_coll is None:
            arsip_coll = bpy.data.collections.new("_ARSIP sisa DWG (tidak dipakai)")
            coll.children.link(arsip_coll)
            arsip_coll.hide_render = True
        link_only(o, arsip_coll)
        o["catatan"] = cfg.get("catatan", "sisa DWG, tidak dipakai di rakitan")
        o.hide_render = True
        o.hide_set(True) if False else None
    else:
        gname = cfg.get("grup", "Badan")
        link_only(o, group_coll(gname))
    # laci
    for n, (d, lc, members) in drawers.items():
        if cfg["handle"] in lc.get("part", []) or o.name.split(" | ")[0] in lc.get("part", []):
            o.parent = d
            members.append((o, cfg))
    o["cad_handle"] = cfg["handle"]
    o["ns_role_part"] = cfg.get("peran", "WOOD_A")
    o["geometry_source"] = R.get("geometry_source", "DWG")
    if cfg.get("catatan"):
        o["catatan"] = cfg["catatan"]
    all_meshes.append((o, cfg))

# kotak laci sederhana (standar v2): dasar 7 mm, sisi 12 mm, belakang 12 mm
carcass = obj_for(R.get("badan_handle", "")) if R.get("badan_handle") else None
for n, (d, lc, members) in drawers.items():
    fronts = [o for o, cfg in members if cfg.get("peran", "WOOD_A").startswith("WOOD")]
    if not lc.get("kotak", True) or not fronts or carcass is None:
        continue
    front = max(fronts, key=lambda o: bounds([o])[1].x - bounds([o])[0].x)
    flo, fhi = bounds([front])
    clo, chi = bounds([carcass])
    clear = float(lc.get("celah_m", 0.012))
    depth = max(0.1, (chi.y - 0.012) - fhi.y - 0.02)
    w = (fhi.x - flo.x) - 2 * clear
    h = max(0.04, (fhi.z - flo.z) - 0.03)
    zb = flo.z + 0.012
    y0 = fhi.y
    cx = (flo.x + fhi.x) / 2
    box = [
        (f"Laci {n} / dasar 7 mm", (w, depth, 0.007), (cx, y0 + depth / 2, zb + 0.0035)),
        (f"Laci {n} / sisi kiri 12 mm", (0.012, depth, h), (cx - w / 2 + 0.006, y0 + depth / 2, zb + h / 2)),
        (f"Laci {n} / sisi kanan 12 mm", (0.012, depth, h), (cx + w / 2 - 0.006, y0 + depth / 2, zb + h / 2)),
        (f"Laci {n} / belakang 12 mm", (w, 0.012, h), (cx, y0 + depth - 0.006, zb + h / 2)),
    ]
    for bname, sz, loc in box:
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        o = bpy.context.object
        o.name = bname
        o.dimensions = sz
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        link_only(o, group_coll("Laci"))
        o.parent = d
        o["ns_role_part"] = "WOOD_B"
        o["geometry_source"] = "tambahan standar v2 (kotak laci sederhana, bukan dari DWG)"
        all_meshes.append((o, {"peran": "WOOD_B", "handle": "-", "nama": bname, "tambahan": True}))
    note(f"Laci {n}: kotak laci sederhana ditambahkan (lebar {w*1000:.0f}, dalam {depth*1000:.0f}, tinggi {h*1000:.0f} mm)")

# ------------------------------------------------------------------ pemeriksaan tabrakan bbox antar part aktif
aktif_objs = [o for o, cfg in all_meshes if not cfg.get("arsip") and not cfg.get("tambahan")]
bb = {o.name: bounds([o]) for o in aktif_objs}
names = list(bb)
tol = 0.0003
for i, a in enumerate(names):
    for b in names[i + 1:]:
        (alo, ahi), (blo, bhi) = bb[a], bb[b]
        pen = [min(ahi[k], bhi[k]) - max(alo[k], blo[k]) for k in range(3)]
        if all(p > tol for p in pen):
            oa, ob = bpy.data.objects[a], bpy.data.objects[b]
            margin = 0.0003
            na, nb = vertices_inside(oa, ob, margin), vertices_inside(ob, oa, margin)
            if na or nb:
                laporan["masalah"].append({"jenis": "tembus", "a": a, "b": b, "bbox_mm": [round(p * 1000, 1) for p in pen],
                                           "vertex_a_di_dalam_b": na, "vertex_b_di_dalam_a": nb})
            else:
                laporan.setdefault("bbox_sentuh", []).append({"a": a, "b": b, "mm": [round(p * 1000, 1) for p in pen]})

# ------------------------------------------------------------------ UV, bevel, material, origin, properti
for i, (o, cfg) in enumerate(all_meshes):
    role = cfg.get("peran", "WOOD_A")
    set_origin_center(o)
    uv_meter(o, grain_axis(o, cfg))
    bevel(o, 0.00035 if role == "HANDLE" else float(R.get("bevel_m", 0.0006)))
    o.data.materials.clear()
    o.data.materials.append(role_material(role))
    o.data.set_sharp_from_angle(angle=math.radians(30))
    chk = periksa(o)
    lo_, hi_ = bounds([o])
    laporan["part"].append({"nama": o.name, "handle": cfg.get("handle", "-"), "peran": role,
                            "grup": o.users_collection[0].name if o.users_collection else "",
                            "ukuran_mm": [round(v * 1000, 1) for v in (hi_ - lo_)],
                            "min_mm": [round(v * 1000, 1) for v in lo_],
                            "sebelum_vf": cfg.get("_before"), "tjunc_split": cfg.get("_tjunc"), "sesudah": chk, "arsip": bool(cfg.get("arsip")),
                            "tambahan": bool(cfg.get("tambahan"))})
    if chk["nonmanifold"] or chk["zero_area"]:
        laporan["masalah"].append({"jenis": "mesh", "nama": o.name, **chk})
bpy.context.view_layer.update()

root["dimensions_cm"] = dims_cm
root["source"] = R.get("dwg", "")
root["unit_assumption"] = R.get("unit_assumption", "")
root["catatan"] = R.get("catatan", "")
scene["asset_id"] = R.get("id", nama.lower().replace(" ", "_"))
scene["category"] = R.get("kategori", "")
scene.name = "PRODUK | " + nama
for area in bpy.context.screen.areas if bpy.context.screen else []:
    if area.type == "VIEW_3D":
        area.spaces.active.shading.type = "MATERIAL"
if arsip_coll is not None:
    # kecualikan dari view layer supaya tidak tampil / render
    def find_lc(lc, c):
        if lc.collection == c:
            return lc
        for ch in lc.children:
            r = find_lc(ch, c)
            if r:
                return r
    lc = find_lc(bpy.context.view_layer.layer_collection, arsip_coll)
    if lc:
        lc.exclude = True
bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
out = Path(R["file_out"])
out.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
laporan["ukuran_cm"] = dims_cm
laporan["jumlah_objek_mesh"] = len(all_meshes)
laporan["file"] = str(out)
Path(R["laporan_json"]).write_text(json.dumps(laporan, indent=1, ensure_ascii=False), encoding="utf-8")
print("SAVED", out, "part", len(all_meshes), "ukuran cm", dims_cm)

# ------------------------------------------------------------------ thumbnail Workbench (setelah simpan; kamera tidak ikut disimpan)
if R.get("thumb"):
    for o, cfg in all_meshes:
        role = cfg.get("peran", "WOOD_A")
        o.color = {"WOOD_A": (0.75, 0.55, 0.35, 1), "WOOD_B": (0.85, 0.75, 0.6, 1), "HANDLE": (0.3, 0.3, 0.32, 1)}.get(role, (0.6, 0.6, 0.6, 1))
    center = (lo + hi) / 2
    radius = (hi - lo).length / 2
    for i, view in enumerate([Vector((0.6, -1.0, 0.45)), Vector((-0.5, 1.0, 0.45))]):
        cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
        scene.collection.objects.link(cam)
        cam.data.lens = 50
        d = view.normalized()
        cam.location = center + d * radius * 2.7
        cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
        scene.camera = cam
        scene.render.engine = "BLENDER_WORKBENCH"
        scene.display.shading.light = "STUDIO"
        scene.display.shading.color_type = "OBJECT"
        scene.display.shading.show_cavity = True
        scene.render.resolution_x, scene.render.resolution_y = 512, 384
        scene.render.filepath = R["thumb"].replace(".png", "" if i == 0 else "_belakang") + ("" if i == 0 else ".png")
        if i == 0:
            scene.render.filepath = R["thumb"]
        bpy.ops.render.render(write_still=True)
        print("THUMB", scene.render.filepath)
