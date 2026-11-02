# Fungsi bersama untuk perbaikan konstruksi BEECHWOOD (pecah part, panel tambahan, kotak laci, uji tembus).
# Diturunkan dari perbaiki_6dwr.py; dipakai oleh perbaiki_lemari.py, perbaiki_credenza.py, perbaiki_meja.py.
import bpy, bmesh, math
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

MM = 0.001
SRC_TAMBAH = "tambahan konstruksi (perbaikan 30-10-2026), bukan dari DWG"
laporan = {"log": [], "part": [], "masalah": [], "tembus": []}


def note(msg):
    print("[konstruksi]", msg)
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
    delta_l = mw.inverted() @ ((lo + hi) / 2)
    for v in o.data.vertices:
        v.co -= delta_l
    o.matrix_world = mw @ Matrix.Translation(delta_l)


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


def potong(src, name, planes, hapus_sebidang=()):
    """Salin src lalu buang geometri di sisi +normal tiap bidang; lubang potongan ditutup.
    planes: [(titik_mm, normal)]."""
    o = src.copy(); o.data = src.data.copy(); o.name = name
    for c in src.users_collection:
        c.objects.link(o)
    inv = o.matrix_world.inverted()
    bm = bmesh.new(); bm.from_mesh(o.data)
    for co, no in planes:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-7, plane_co=inv @ (Vector(co) * MM), plane_no=Vector(no), clear_outer=True)
    for co, no in hapus_sebidang:
        co_l = inv @ (Vector(co) * MM); n = Vector(no)
        dead = [f for f in bm.faces if all(abs((v.co - co_l).dot(n)) < 1e-5 for v in f.verts)]
        bmesh.ops.delete(bm, geom=dead, context="FACES_ONLY")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=2e-6)
    pl = [(inv @ (Vector(co) * MM), Vector(no)) for co, no in planes]
    on = lambda v: any(abs((v.co - c).dot(n)) < 1e-5 for c, n in pl)
    bnd = [e for e in bm.edges if e.is_boundary and on(e.verts[0]) and on(e.verts[1])]
    if bnd:
        bmesh.ops.holes_fill(bm, edges=bnd, sides=0)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-7, edges=bm.edges[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(o.data); bm.free()
    o.data.update()
    set_origin_center(o)
    return o


def _objek_baru(name, bm, role, coll, parent, src, grain, ukuran):
    me = bpy.data.meshes.new(name)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    o.parent = parent
    o.matrix_parent_inverse = parent.matrix_world.inverted()
    o.matrix_world = Matrix.Identity(4)
    set_origin_center(o)
    uv_meter(o, grain)
    bevel(o)
    o.data.materials.append(role_material(role))
    o["ns_role_part"] = role
    o["geometry_source"] = src
    o["ukuran_potong_mm"] = " x ".join(f"{d:.1f}".rstrip("0").rstrip(".") for d in sorted(ukuran, reverse=True))
    return o


def kotak(name, x0, x1, y0, y1, z0, z1, role, coll, parent, grain, src=SRC_TAMBAH):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector(((x1 - x0) * (v.co.x + 0.5) + x0, (y1 - y0) * (v.co.y + 0.5) + y0, (z1 - z0) * (v.co.z + 0.5) + z0)) * MM
    return _objek_baru(name, bm, role, coll, parent, src, grain, [x1 - x0, y1 - y0, z1 - z0])


def prisma(name, profil, sumbu, a0, a1, role, coll, parent, grain, src=SRC_TAMBAH):
    """Profil 2D (mm) diekstrusi sepanjang sumbu 'X', 'Y' atau 'Z' dari a0 ke a1.
    Profil memakai dua sumbu sisanya berurutan: X -> (y, z), Y -> (x, z), Z -> (x, y)."""
    def p3(u, w, a):
        return {"X": Vector((a, u, w)), "Y": Vector((u, a, w)), "Z": Vector((u, w, a))}[sumbu] * MM
    bm = bmesh.new()
    fv = [bm.verts.new(p3(u, w, a0)) for u, w in profil]
    bv = [bm.verts.new(p3(u, w, a1)) for u, w in profil]
    bm.faces.new(fv[::-1]); bm.faces.new(bv)
    for i in range(len(profil)):
        j = (i + 1) % len(profil)
        bm.faces.new((fv[i], fv[j], bv[j], bv[i]))
    us = [p[0] for p in profil]; ws = [p[1] for p in profil]
    return _objek_baru(name, bm, role, coll, parent, src, grain, [max(us) - min(us), max(ws) - min(ws), abs(a1 - a0)])


def sub(name, parent_coll):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in parent_coll.children:
        parent_coll.children.link(c)
    return c


def pindah(o, c):
    for old in list(o.users_collection):
        old.objects.unlink(o)
    c.objects.link(o)


def hapus_collection_lama(nama_list, tujuan_mesh, tujuan_empty):
    for nm in nama_list:
        c = bpy.data.collections.get(nm)
        if c:
            for o in list(c.objects):
                pindah(o, tujuan_empty if o.type == "EMPTY" else tujuan_mesh)
            bpy.data.collections.remove(c)


def arsipkan(o, prod):
    c = bpy.data.collections.get("_ARSIP sisa DWG (tidak dipakai)")
    if c is None:
        c = bpy.data.collections.new("_ARSIP sisa DWG (tidak dipakai)")
        prod.children.link(c)
        c.hide_render = True
        lc = next((l for l in bpy.context.view_layer.layer_collection.children[prod.name].children if l.collection == c), None)
        if lc:
            lc.exclude = True
    pindah(o, c)
    o.hide_render = True
    return c


def kotak_laci(n, drawer, coll, x0, x1, y0, depth, z0, h, t=12.0, t_dasar=7.0):
    """Kotak laci lengkap: sisi kiri/kanan, depan dalam, belakang, dasar (tidak saling tembus)."""
    for o in [o for o in bpy.data.objects if o.name.startswith(f"Laci {n} / ")]:
        bpy.data.objects.remove(o)
    y1, z1 = y0 + depth, z0 + h
    parts = [
        (f"Laci {n} / sisi kiri {t:.0f} mm", x0, x0 + t, y0, y1, z0, z1, "Y", "dovetail/dowel ke depan dalam & belakang"),
        (f"Laci {n} / sisi kanan {t:.0f} mm", x1 - t, x1, y0, y1, z0, z1, "Y", "dovetail/dowel ke depan dalam & belakang"),
        (f"Laci {n} / depan dalam {t:.0f} mm", x0 + t, x1 - t, y0, y0 + t, z0, z1, "X", "front laci disekrup dari dalam"),
        (f"Laci {n} / belakang {t:.0f} mm", x0 + t, x1 - t, y1 - t, y1, z0 + 10 + t_dasar, z1, "X", "duduk di atas dasar laci"),
        (f"Laci {n} / dasar {t_dasar:.0f} mm", x0 + t, x1 - t, y0 + t, y1 - t, z0 + 10, z0 + 10 + t_dasar, "X", "masuk alur di sisi & depan dalam"),
    ]
    for nm, a, b, c0, c1, e0, e1, g, smb in parts:
        o = kotak(nm, a, b, c0, c1, e0, e1, "WOOD_B", coll, drawer, g)
        o["sambungan"] = smb
    note(f"Laci {n}: kotak {x1-x0:.1f} x {depth:.0f} x {h:.0f} mm (x {x0:.1f}..{x1:.1f}, z {z0:.1f}..{z1:.1f})")


def uji_tembus(objs, margin=0.0005):
    W = {o.name: [o.matrix_world @ v.co for v in o.data.vertices] for o in objs}
    BB = {n: (Vector([min(p[i] for p in v) for i in range(3)]), Vector([max(p[i] for p in v) for i in range(3)])) for n, v in W.items()}
    T = {}

    def inside(a, b):
        if b.name not in T:
            T[b.name] = BVHTree.FromPolygons(W[b.name], [p.vertices[:] for p in b.data.polygons])
        lo, hi = BB[b.name]; n = 0
        for p in W[a.name]:
            if not all(lo[i] - margin <= p[i] <= hi[i] + margin for i in range(3)):
                continue
            loc, nor, idx, d = T[b.name].find_nearest(p)
            if loc is not None and d > margin and (p - loc).dot(nor) < 0:
                n += 1
        return n
    res = []
    names = sorted(BB)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            (al, ah), (bl, bh) = BB[a], BB[b]
            if all(min(ah[k], bh[k]) - max(al[k], bl[k]) > 0.0003 for k in range(3)):
                na, nb = inside(bpy.data.objects[a], bpy.data.objects[b]), inside(bpy.data.objects[b], bpy.data.objects[a])
                if na or nb:
                    res.append([a, b, na, nb])
    return res


def tutup_laporan(prod, root, catatan):
    arsip = bpy.data.collections.get("_ARSIP sisa DWG (tidak dipakai)")
    if arsip and arsip.name in prod.children:
        prod.children.unlink(arsip); prod.children.link(arsip)
    aktif = [o for o in bpy.data.objects if o.type == "MESH" and not (arsip and arsip in o.users_collection)]
    bpy.context.view_layer.update()
    for o in aktif:
        lo_, hi_ = bounds([o])
        laporan["part"].append({"nama": o.name, "collection": o.users_collection[0].name, "peran": o.get("ns_role_part", ""),
                                "ukuran_mm": [round(v / MM, 1) for v in (hi_ - lo_)], "min_mm": [round(v / MM, 1) for v in lo_],
                                "potong": o.get("ukuran_potong_mm", ""), "sambungan": o.get("sambungan", ""), **periksa(o)})
    lo, hi = bounds(aktif)
    laporan["bbox_mm"] = [[round(v / MM, 1) for v in lo], [round(v / MM, 1) for v in hi]]
    laporan["tembus"] = uji_tembus(aktif)
    laporan["unparented"] = [o.name for o in bpy.data.objects if o.parent is None and not o.name.startswith("PRODUCT_ROOT")]

    def tree(c, d=0):
        s = ["  " * d + f"{c.name} ({len(c.objects)})"]
        for ch in c.children:
            s += tree(ch, d + 1)
        return s
    laporan["collection"] = tree(prod)
    root["catatan"] = root.get("catatan", "") + " | 2026-10-30: " + catatan
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
