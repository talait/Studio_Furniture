# Geometri laci Beechwood (sama dengan beechwood 6 drawers): tiap pasangan 'Front laci N' + 'Handle laci N'
# (satu parent DRAWER_N) dibangun ulang:
#   - front: panel bersih, tepi depan membulat 2.5 mm, kantong handle membulat ke dalam (bibir 2.5 mm +
#     cekungan setengah-elips sedalam 16 mm, bukaan 145 x 40 mm), UV 'UV meter' serat mendatar (V = x)
#   - handle: dibangun ulang oleh 03_PROYEK/beechwood_handle_setengah_bulat.py (batang lonjong 165 x 11 x 8 mm
#     setengah tertanam, kaki bulat mepet ujung kantong) dengan bukaan yang sama -> jalankan sesudah skrip ini:
#       blender -b <file> --python 03_PROYEK/beechwood_handle_setengah_bulat.py -- --kantong 0.0725
# Ukuran per produk: 6dw & tallboy bukaan 145 (0.0725, handle 165); bedside bukaan 125 (0.0625, handle 145).
# Material tetap slot lama (ROLE | WOOD_A / HANDLE atau finish preset); warna & tekstur dari sinkron_beechwood.py.
# Jalankan: blender -b "<file produk atau proyek>.blend" --python 99_SISTEM/beechwood_kantong_handle.py
import bpy, bmesh, math, json, sys
from mathutils import Vector

# Kantong (koordinat lokal front, muka depan di y = -tebal/2)
R, HALF = 0.0200, 0.0725            # jari-jari ujung & setengah panjang bukaan kantong (145 mm, handle 165 mm)
ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
if '--kantong' in ARGV:             # ukuran per produk, mis. bedside: -- --kantong 0.0625 (bukaan 125, handle 145)
    HALF = float(ARGV[ARGV.index('--kantong') + 1])
DEPTH, LIP = 0.016, 0.0025
EDGE = 0.0025                       # tepi depan front membulat
SEG = 24


def uv_for(co, n):
    """UV meter dengan serat mendatar: u = -z, v = x (muka depan)."""
    if abs(n.y) >= max(abs(n.x), abs(n.z)):
        return (-co.z, co.x)
    if abs(n.z) >= abs(n.x):
        return (co.y, co.x)
    return (-co.z, co.y)


def finish(bm, me):
    bm.normal_update()
    uv = bm.loops.layers.uv.new("UV meter")
    for f in bm.faces:
        for l in f.loops:
            l[uv].uv = uv_for(l.vert.co, f.normal)
    bm.to_mesh(me); bm.free()


def slab(name, c, hx, hy, hz):
    """Panel front berpusat di c: muka depan (y=c.y-hy) tepinya membulat EDGE, belakang rata."""
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    rings = []
    for i in range(7):
        a = math.pi / 2 * i / 6
        ins, y = EDGE * (1 - math.sin(a)), -hy + EDGE * (1 - math.cos(a))
        rings.append([(sx * (hx - ins), y, sz * (hz - ins)) for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    rings.append([(sx * hx, hy, sz * hz) for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    vr = [[bm.verts.new(c + Vector(p)) for p in r] for r in rings]
    bm.faces.new(vr[0]); bm.faces.new(list(reversed(vr[-1])))
    for a, b in zip(vr, vr[1:]):
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    finish(bm, me)
    return me


def inset(depth):
    if depth <= LIP:
        t = min(depth / LIP, 1.0)
        return -LIP + LIP * math.sqrt(1 - (1 - t) ** 2)
    u = (depth - LIP) / (DEPTH - LIP)
    return R * (1 - math.sqrt(max(0.0, 1 - u * u)))


def cutter(name, off, face_y):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    depths = [-0.015] + [i * LIP / 6 for i in range(7)] + \
             [LIP + (DEPTH - LIP) * math.sin(math.pi / 2 * i / 16) for i in range(1, 17)]
    cx, rings = HALF - R, []
    for dd in depths:
        r = max(R - min(inset(max(dd, 0)), R - 0.0004), 0.0004)
        ring = []
        for side in (1, -1):
            for i in range(SEG + 1):
                a = -math.pi / 2 + math.pi * i / SEG
                ring.append(bm.verts.new((off.x + side * (cx + r * math.cos(a)), face_y + dd, off.z + side * r * math.sin(a))))
        rings.append(ring)
    bm.faces.new(rings[0]); bm.faces.new(list(reversed(rings[-1])))
    n = len(rings[0])
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    finish(bm, me)
    return bpy.data.objects.new(name, me)


def replace_mesh(obj, me):
    old, mats = obj.data, list(obj.data.materials)
    for m in mats:
        me.materials.append(m)
    obj.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    me.name = me.name.split(".")[0]


rep = {}
for fr in [o for o in bpy.data.objects if o.name.startswith("Front laci") and o.parent]:
    h = next((o for o in fr.parent.children if o.name.startswith("Handle laci")), None)
    if h is None:
        continue
    # 1. Front + kantong (posisi kantong dari handle lama)
    off = fr.matrix_world.inverted() @ h.matrix_world.translation
    lo, hi = Vector(fr.bound_box[0]), Vector(fr.bound_box[6])
    c, (hx, hy, hz) = (lo + hi) / 2, (hi - lo) / 2
    replace_mesh(fr, slab(fr.data.name, c, hx, hy, hz))
    cut = cutter("TMP_kantong", off, c.y - hy)
    bpy.context.scene.collection.objects.link(cut)
    cut.matrix_world = fr.matrix_world.copy()
    m = fr.modifiers.new("tmp", 'BOOLEAN'); m.operation = 'DIFFERENCE'; m.solver = 'EXACT'; m.object = cut
    fr.modifiers.move(fr.modifiers.find("tmp"), 0)
    with bpy.context.temp_override(object=fr, active_object=fr, selected_objects=[fr]):
        bpy.ops.object.modifier_apply(modifier="tmp")
    cme = cut.data; bpy.data.objects.remove(cut); bpy.data.meshes.remove(cme)
    h['ns_kantong_half'] = HALF          # dibaca beechwood_handle_setengah_bulat.py
    bm = bmesh.new(); bm.from_mesh(fr.data)
    rep[fr.name] = {"faces": len(bm.faces), "non_manifold": sum(1 for e in bm.edges if not e.is_manifold),
                    "front": [round(v, 4) for v in fr.dimensions]}
    bm.free()
bpy.ops.wm.save_mainfile()
print("##" + json.dumps(rep, ensure_ascii=False))
