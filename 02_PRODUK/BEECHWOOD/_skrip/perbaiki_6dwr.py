# Perbaikan "beechwood 6dw r.blend": lengkapi panel dasar, panel belakang, partisi tengah, klos rel,
# kotak laci lengkap; pecah carcass (top + 2 sisi, sambungan mitre 45 deg) dan rangka belakang
# (2 kaki + rel); susun ulang collection per sub-rakitan konstruksi.
# Pakai: blender -b "<file>.blend" --python perbaiki_6dwr.py -- <laporan.json>
import bpy, bmesh, json, math, sys
from mathutils import Vector

MM = 0.001
NAMA = "Beechwood 6 Drawers"
laporan = {"log": [], "part": [], "masalah": []}


def note(msg):
    print("[6dwr]", msg)
    laporan["log"].append(msg)


def bounds(objs):
    ws = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    lo = Vector([min(w[i] for w in ws) for i in range(3)])
    hi = Vector([max(w[i] for w in ws) for i in range(3)])
    return lo, hi


def obj_prefix(p):
    return next(o for o in bpy.data.objects if o.name.startswith(p))


def periksa(o):
    bm = bmesh.new(); bm.from_mesh(o.data)
    nm = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    za = sum(1 for f in bm.faces if f.calc_area() < 1e-12)
    bm.free()
    return {"nonmanifold": nm, "zero_area": za, "faces": len(o.data.polygons)}


def set_origin_center(o):
    mw = o.matrix_world.copy()
    lo, hi = bounds([o])
    c = (lo + hi) / 2
    delta_l = mw.inverted() @ c
    for v in o.data.vertices:
        v.co -= delta_l
    o.matrix_world = mw @ __import__("mathutils").Matrix.Translation(delta_l)


# ---- material, UV, bevel: sama dengan bangun_beechwood.py
def role_material(role):
    return bpy.data.materials["ROLE | " + role]


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


def bevel(obj, width=0.0006):
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


# ---- pembelahan mesh dengan bidang (bisect + tutup lubang potong)
def potong(src, name, planes, hapus_sebidang=()):
    """planes: [(co_mm, normal)] ; geometri di sisi +normal dibuang."""
    o = src.copy(); o.data = src.data.copy(); o.name = name
    for c in src.users_collection:
        c.objects.link(o)
    inv = o.matrix_world.inverted()
    bm = bmesh.new(); bm.from_mesh(o.data)
    for co, no in planes:
        co_l = inv @ (Vector(co) * MM)
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-7, plane_co=co_l, plane_no=Vector(no), clear_outer=True)
    for co, no in hapus_sebidang:
        # buang muka yang seluruhnya terletak pada bidang potong (mis. muka dalam kaki pada potongan rel)
        co_l = inv @ (Vector(co) * MM); n = Vector(no)
        dead = [f for f in bm.faces if all(abs((v.co - co_l).dot(n)) < 1e-5 for v in f.verts)]
        bmesh.ops.delete(bm, geom=dead, context="FACES_ONLY")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=2e-6)
    # tutup hanya lubang potongan (tepi terbuka yang terletak pada bidang potong); lubang lama dari tessellasi dibiarkan
    pl = [(inv @ (Vector(co) * MM), Vector(no)) for co, no in planes]
    on = lambda v: any(abs((v.co - c).dot(n)) < 1e-5 for c, n in pl)
    bnd = [e for e in bm.edges if e.is_boundary and on(e.verts[0]) and on(e.verts[1])]
    if bnd:
        bmesh.ops.holes_fill(bm, edges=bnd, sides=0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(o.data); bm.free()
    o.data.update()
    set_origin_center(o)
    return o


def kotak(name, x0, x1, y0, y1, z0, z1, role, coll, parent, src, grain=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector(((x1 - x0) * (v.co.x + 0.5) + x0, (y1 - y0) * (v.co.y + 0.5) + y0, (z1 - z0) * (v.co.z + 0.5) + z0)) * MM
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    o.parent = parent
    o.matrix_parent_inverse = parent.matrix_world.inverted()
    o.matrix_world = __import__("mathutils").Matrix.Identity(4)
    set_origin_center(o)
    sz = sorted([(x1 - x0, "X"), (y1 - y0, "Y"), (z1 - z0, "Z")])
    if grain is None:
        grain = "X" if sz[0][1] == "Z" else ("X" if sz[0][1] == "Y" and (x1 - x0) > (z1 - z0) else "Z")
        if sz[0][1] == "X":
            grain = "Y" if (y1 - y0) > (z1 - z0) else "Z"
    uv_meter(o, grain)
    bevel(o)
    o.data.materials.append(role_material(role))
    o["ns_role_part"] = role
    o["geometry_source"] = src
    o["ukuran_potong_mm"] = " x ".join(f"{d:.1f}".rstrip("0").rstrip(".") for d in sorted([x1 - x0, y1 - y0, z1 - z0], reverse=True))
    return o


root = bpy.data.objects["PRODUCT_ROOT | " + NAMA]
prod = bpy.data.collections["PROD | " + NAMA]


def sub(name, parent_coll=None):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    pc = parent_coll or prod
    if c.name not in pc.children:
        pc.children.link(c)
    return c


def pindah(o, c):
    for old in list(o.users_collection):
        old.objects.unlink(o)
    c.objects.link(o)


C_CAR = sub("01 Carcass")
C_RD = sub("02 Rangka depan")
C_RB = sub("03 Rangka belakang")
C_LACI = sub("04 Laci")

SRC_DWG = "DWG 2018 3DSOLID (ACIS SAB) -> tessellasi dwg2obj (LibreDWG + ezdxf)"
SRC_POT = SRC_DWG + "; dipecah per komponen (perbaiki_6dwr.py)"
SRC_TAMBAH = "tambahan konstruksi (perbaiki_6dwr.py), bukan dari DWG"

# ------------------------------------------------------------ 1. carcass: top + sisi kiri + sisi kanan (mitre 45 deg)
car = obj_prefix("Badan kabinet (carcass + top)")
clo, chi = bounds([car])
X_OUT = chi.x / MM                      # 600
T_SIDE = 20.3                            # tebal sisi setelah skala X 1,014 (inner face 579.7)
X_IN = X_OUT - T_SIDE
Z_TOP = chi.z / MM                      # 700
Z_TOP_IN = 680.0
Z_BOT = clo.z / MM                      # 88.9
Y_F, Y_B = clo.y / MM, chi.y / MM       # -257.3, 262.7
# bidang mitre lewat titik pusat lengkung (X_IN-20, Z_TOP_IN-20) = (559.7, 660) pada 45 deg
cxr, czr = X_IN - 20.0, Z_TOP_IN - 20.0
s = 1 / math.sqrt(2)
top = potong(car, "Top (mitre 45°) | 261", [((cxr, 0, czr), (s, 0, -s)), ((-cxr, 0, czr), (-s, 0, -s))])
sisi_ka = potong(car, "Sisi kanan (mitre 45°) | 261", [((cxr, 0, czr), (-s, 0, s))])
sisi_ki = potong(car, "Sisi kiri (mitre 45°) | 261", [((-cxr, 0, czr), (s, 0, s))])
for o in (top, sisi_ka, sisi_ki):
    pindah(o, C_CAR)
    o["geometry_source"] = SRC_POT
    o["sambungan"] = "mitre 45° pada lengkung sudut (R dalam 20 / luar 40 mm) + lamello/dowel"
top["ukuran_potong_mm"] = f"{2 * X_OUT:.0f} x {Y_B - Y_F:.0f} x 20 (tepi lengkung R40)"
for o in (sisi_ka, sisi_ki):
    o["ukuran_potong_mm"] = f"{czr - Z_BOT + 40:.0f} x {Y_B - Y_F:.0f} x {T_SIDE}"
bpy.data.objects.remove(car)
note(f"Carcass 261 dipecah: top + sisi kiri + sisi kanan, mitre 45° lewat pusat lengkung ({cxr:.1f}, {czr:.1f}) mm")

# ------------------------------------------------------------ 2. rangka belakang: kaki kiri, kaki kanan, rel atas
fr = obj_prefix("Rangka belakang (kaki belakang + rel)")
flo, fhi = bounds([fr])
# muka dalam kaki belakang, diukur per sisi (skala X 1,014 dari x0 membuat kiri/kanan tidak persis simetris)
ws = [fr.matrix_world @ v.co for v in fr.data.vertices]
XKI = max(w.x for w in ws if w.x < 0 and w.z < 0.6) / MM
XKA = min(w.x for w in ws if w.x > 0 and w.z < 0.6) / MM
note(f"Rangka belakang: muka dalam kaki di x = {XKI:.2f} / {XKA:.2f} mm")
kb_ki = potong(fr, "Kaki belakang kiri | 257", [((XKI, 0, 0), (1, 0, 0))])
# mesh asli kaki kanan punya muka bertumpuk dari tessellasi (± 350 tepi non-manifold di telapak & sudut) ->
# kaki kanan = cermin kaki kiri, outer face di x = +600
kb_ka = kb_ki.copy(); kb_ka.data = kb_ki.data.copy(); kb_ka.name = "Kaki belakang kanan | 257"
for c in kb_ki.users_collection:
    c.objects.link(kb_ka)
bm = bmesh.new(); bm.from_mesh(kb_ka.data)
for v in bm.verts:
    v.co.x = -v.co.x
bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
bm.to_mesh(kb_ka.data); bm.free()
kb_ka.location.x = -kb_ki.location.x
bpy.context.view_layer.update()
kb_ka.location.x += fhi.x - bounds([kb_ka])[1].x
kb_ka["catatan"] = "dicerminkan dari kaki belakang kiri: mesh asli kanan cacat tessellasi (muka bertumpuk)"
note("Kaki belakang kanan dibuat dari cermin kaki belakang kiri (mesh asli kanan punya muka bertumpuk)")
rel_b = potong(fr, "Rel atas belakang | 257", [((XKI, 0, 0), (-1, 0, 0)), ((XKA, 0, 0), (1, 0, 0))],
               hapus_sebidang=[((XKI, 0, 0), (1, 0, 0)), ((XKA, 0, 0), (1, 0, 0))])
for o in (kb_ki, kb_ka, rel_b):
    pindah(o, C_RB)
    o["geometry_source"] = SRC_POT
kb_ki["sambungan"] = kb_ka["sambungan"] = "lubang purus untuk rel atas belakang"
rel_b["sambungan"] = "purus-lubang (mortise & tenon) ke kaki belakang"
bpy.data.objects.remove(fr)
# arah serat per komponen: top & rel mendatar (X), sisi & kaki tegak (Z)
for o, g in ((top, "X"), (sisi_ki, "Z"), (sisi_ka, "Z"), (rel_b, "X"), (kb_ki, "Z"), (kb_ka, "Z")):
    uv_meter(o, g)

# ------------------------------------------------------------ 3. rangka depan
kd_ki, kd_ka, rel_d = obj_prefix("Kaki depan kiri"), obj_prefix("Kaki depan kanan"), obj_prefix("Rel atas depan")
for o in (kd_ki, kd_ka, rel_d):
    pindah(o, C_RD)
rel_d["sambungan"] = "purus-lubang (mortise & tenon) ke kaki depan"

# ------------------------------------------------------------ 4. panel tambahan carcass
T_BOT, T_BACK, T_DIV = 18.0, 9.0, 18.0
Y_BACK_IN = Y_B - T_BACK
Z_BOT_TOP = Z_BOT + T_BOT
baru = []
baru.append(kotak("Panel dasar 18 mm", -X_IN, X_IN, Y_F, Y_BACK_IN, Z_BOT, Z_BOT_TOP, "WOOD_B", C_CAR, root, SRC_TAMBAH, "X"))
baru[-1]["sambungan"] = "dado/dowel ke sisi kiri & kanan, rata bawah sisi"
pb = kotak("Panel belakang 9 mm", -X_IN, X_IN, Y_BACK_IN, Y_B, Z_BOT, Z_TOP_IN, "WOOD_A", C_CAR, root, SRC_TAMBAH, "X")
# sudut atas mengikuti lengkung dalam carcass (R = X_IN - cxr, pusat (±cxr, czr)), supaya tidak menembus sudut bengkok
R_IN = X_IN - cxr
prof = [(-X_IN, Z_BOT), (X_IN, Z_BOT)]
prof += [(cxr + R_IN * math.cos(math.radians(a)), czr + R_IN * math.sin(math.radians(a))) for a in range(0, 91, 10)]
prof += [(-cxr + R_IN * math.cos(math.radians(a)), czr + R_IN * math.sin(math.radians(a))) for a in range(90, 181, 10)]
bm = bmesh.new()
fv = [bm.verts.new(Vector((x, Y_BACK_IN, z)) * MM) for x, z in prof]
bv = [bm.verts.new(Vector((x, Y_B, z)) * MM) for x, z in prof]
bm.faces.new(fv[::-1]); bm.faces.new(bv)
for i in range(len(prof)):
    j = (i + 1) % len(prof)
    bm.faces.new((fv[i], fv[j], bv[j], bv[i]))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
mw = pb.matrix_world.copy()
for v in bm.verts:
    v.co = mw.inverted() @ v.co
bm.to_mesh(pb.data); bm.free()
uv_meter(pb, "X")
for p in pb.data.polygons:
    p.use_smooth = True
pb["sambungan"] = "masuk alur (rebate) sisi, top & dasar; rata belakang carcass; sudut atas R20 mengikuti lengkung carcass"
baru.append(pb)
baru.append(kotak("Partisi tengah 18 mm", -T_DIV / 2, T_DIV / 2, Y_F, Y_BACK_IN, Z_BOT_TOP, Z_TOP_IN, "WOOD_B", C_CAR, root, SRC_TAMBAH, "Z"))
baru[-1]["sambungan"] = "dado ke panel dasar dan bawah top"
note(f"Ditambah: panel dasar {2*X_IN:.1f} x {Y_BACK_IN-Y_F:.1f} x {T_BOT}, panel belakang {2*X_IN:.1f} x {Z_TOP_IN-Z_BOT:.1f} x {T_BACK}, "
     f"partisi tengah {Y_BACK_IN-Y_F:.1f} x {Z_TOP_IN-Z_BOT_TOP:.1f} x {T_DIV} mm")

# ------------------------------------------------------------ 5. laci: kotak lengkap + klos rel
X_LEG_IN = 560.0          # muka dalam kaki depan; klos membuat bidang rel rata dengan kaki
SLIDE = 12.7              # ruang rel laci (rel tidak dimodelkan, standar v2)
BOX_H, BOX_D, T_BOX, T_DASAR = 140.0, 500.0, 12.0, 7.0
for o in [o for o in bpy.data.objects if o.name.startswith("Laci ") and " / " in o.name]:
    bpy.data.objects.remove(o)
klos_baris = {}
for n in range(1, 7):
    d = bpy.data.objects[f"DRAWER_{n} | {NAMA}"]
    front = obj_prefix(f"Front laci {n} ")
    handle = obj_prefix(f"Handle laci {n} ")
    flo_, fhi_ = bounds([front])
    kiri = (flo_.x + fhi_.x) < 0
    xa, xb = (-X_LEG_IN, -T_DIV / 2) if kiri else (T_DIV / 2, X_LEG_IN)
    x0, x1 = xa + SLIDE, xb - SLIDE
    y0 = fhi_.y / MM          # muka belakang front
    y1 = y0 + BOX_D
    z0 = flo_.z / MM + 21.6
    z1 = z0 + BOX_H
    c = sub(f"Laci {n}", C_LACI)
    for o in (front, handle):
        pindah(o, c)
    src = SRC_TAMBAH
    parts = [
        (f"Laci {n} / sisi kiri 12 mm", x0, x0 + T_BOX, y0, y1, z0, z1, "Y"),
        (f"Laci {n} / sisi kanan 12 mm", x1 - T_BOX, x1, y0, y1, z0, z1, "Y"),
        (f"Laci {n} / depan dalam 12 mm", x0 + T_BOX, x1 - T_BOX, y0, y0 + T_BOX, z0, z1, "X"),
        (f"Laci {n} / belakang 12 mm", x0 + T_BOX, x1 - T_BOX, y1 - T_BOX, y1, z0 + 17.0, z1, "X"),
        (f"Laci {n} / dasar 7 mm", x0 + T_BOX, x1 - T_BOX, y0 + T_BOX, y1 - T_BOX, z0 + 10.0, z0 + 10.0 + T_DASAR, "X"),
    ]
    for nm, a, b, c0, c1, e0, e1, g in parts:
        o = kotak(nm, a, b, c0, c1, e0, e1, "WOOD_B", c, d, src, g)
        o["sambungan"] = {"sisi": "dovetail/dowel ke depan dalam & belakang", "depan": "front laci disekrup dari dalam",
                          "belakang": "duduk di atas panel dasar laci", "dasar": "masuk alur di sisi & depan dalam"}[nm.split("/ ")[1].split()[0]]
    baris = (n + 1) // 2
    klos_baris[baris] = (z0, z1)
    note(f"Laci {n}: kotak {x1-x0:.1f} x {BOX_D:.0f} x {BOX_H:.0f} mm (x {x0:.1f}..{x1:.1f}, z {z0:.1f}..{z1:.1f}), ruang rel {SLIDE} mm")
for baris, (z0, z1) in sorted(klos_baris.items()):
    zc = (z0 + z1) / 2
    for sisi, (a, b) in (("kiri", (-X_IN, -X_LEG_IN)), ("kanan", (X_LEG_IN, X_IN))):
        o = kotak(f"Klos rel laci {sisi} baris {baris}", a, b, Y_F, Y_BACK_IN - 10, zc - 30, zc + 30, "WOOD_B", C_CAR, root, SRC_TAMBAH, "Y")
        o["sambungan"] = "dilem + sekrup ke sisi; dudukan rel laci rata muka dalam kaki depan"
note("Klos rel laci 6 buah (2 per baris) agar bidang rel rata dengan muka dalam kaki depan (x = ±560 mm)")

# ------------------------------------------------------------ 6. bersihkan collection lama
for nm in ("Badan", "Kaki", "Hardware", "Laci"):
    c = bpy.data.collections.get(nm)
    if c:
        for o in list(c.objects):
            pindah(o, C_LACI if o.type == "EMPTY" else C_CAR)
        bpy.data.collections.remove(c)
for o in bpy.data.objects:
    if o.name.startswith("DRAWER_"):
        pindah(o, C_LACI)
arsip = bpy.data.collections.get("_ARSIP sisa DWG (tidak dipakai)")
if arsip and arsip.name in prod.children:
    prod.children.unlink(arsip); prod.children.link(arsip)   # urutan: arsip paling bawah

# ------------------------------------------------------------ 7. pemeriksaan
aktif = [o for o in bpy.data.objects if o.type == "MESH" and arsip not in o.users_collection]
bpy.context.view_layer.update()
bb = {o.name: bounds([o]) for o in aktif}
names = sorted(bb)
for i, a in enumerate(names):
    for b in names[i + 1:]:
        (alo, ahi), (blo, bhi) = bb[a], bb[b]
        pen = [min(ahi[k], bhi[k]) - max(alo[k], blo[k]) for k in range(3)]
        if all(p > 0.0003 for p in pen):
            laporan["masalah"].append({"jenis": "bbox_tumpang", "a": a, "b": b, "mm": [round(p / MM, 1) for p in pen]})
for o in aktif:
    lo_, hi_ = bounds([o])
    laporan["part"].append({"nama": o.name, "collection": o.users_collection[0].name, "peran": o.get("ns_role_part", ""),
                            "ukuran_mm": [round(v / MM, 1) for v in (hi_ - lo_)], "min_mm": [round(v / MM, 1) for v in lo_],
                            "potong": o.get("ukuran_potong_mm", ""), "sambungan": o.get("sambungan", ""), **periksa(o)})
lo, hi = bounds(aktif)
laporan["bbox_mm"] = [[round(v / MM, 1) for v in lo], [round(v / MM, 1) for v in hi]]
root["catatan"] = root.get("catatan", "") + (" | 2026-10-30: dilengkapi panel dasar, panel belakang, partisi tengah, klos rel, "
                                             "kotak laci lengkap; carcass & rangka belakang dipecah per komponen (perbaiki_6dwr.py).")
bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
if "--simpan" in sys.argv:
    bpy.ops.wm.save_mainfile(compress=True)
    note("Disimpan")
json.dump(laporan, open(sys.argv[-1], "w", encoding="utf-8"), indent=1, ensure_ascii=False)
