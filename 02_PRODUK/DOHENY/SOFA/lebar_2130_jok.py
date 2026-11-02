# Doheny Sofa: lebar total 1836 -> 2130 mm, dan sambungan jok atas/bawah dinaikkan ke garis referensi.
# Lebar: lengan & ujung tetap utuh, bagian tengah melebar (kebalikan doheny_make_armchair_from_sofa.py).
# Jok: jok bawah (deck) lebih tebal, jok atas lebih tipis; atas jok tetap 45 cm, tepi bulat tidak ikut meregang.
# blender -b 02_PRODUK/DOHENY/SOFA/Doheny_Sofa.blend --python lebar_2130_jok.py
import bpy, bmesh, math, sys
from pathlib import Path
from mathutils import Vector
sys.path.insert(0, str(Path(r"C:/Users/Staff/Documents/Studio_Furniture/02_PRODUK/BEECHWOOD/_skrip")))
from konstruksi_util import uv_meter
D = bpy.data
root = D.objects['PRODUCT_ROOT | Doheny_Sofa']
assert not root.get('lebar_2130'), 'sudah diterapkan'
objs = [o for o in root.children_recursive if o.type in ('MESH', 'CURVE')]
TARGET_W = 2.130
SEAM = 0.283                     # garis putus-putus referensi (tinggi sambungan jok, m)
R = 0.03                         # pita tepi bulat jok yang tidak ikut meregang


def wb(o):
    return [o.matrix_world @ Vector(c) for c in o.bound_box]


def each_point(o, fn):
    mw = o.matrix_world; inv = mw.inverted()
    if o.type == 'MESH':
        for v in o.data.vertices:
            v.co = inv @ fn(mw @ v.co)
        o.data.update()
    else:
        for sp in o.data.splines:
            for pt in sp.points:
                pt.co = (*(inv @ fn(mw @ pt.co.xyz)), pt.co.w)
            for bp in sp.bezier_points:
                for attr in ('co', 'handle_left', 'handle_right'):
                    setattr(bp, attr, inv @ fn(mw @ getattr(bp, attr)))


# 1) Lebar
old_half = max(abs(p.x) for o in objs for p in wb(o))
d = TARGET_W / 2 - old_half; T = 0.70
def fx(x):
    ax = abs(x)
    return math.copysign(ax + d, x) if ax >= T else x * (T + d) / T
def widen(p):
    p.x = fx(p.x); return p
span = [o for o in objs if (lambda xs: max(xs) - min(xs))([p.x for p in wb(o)]) > 0.5]
moves = {}
for o in objs:
    if o in span:
        continue
    xs = [p.x for p in wb(o)]; cx = (min(xs) + max(xs)) / 2
    moves[o] = fx(cx) - cx
for o in span:
    each_point(o, widen)
for o, dx in moves.items():          # geser setelah remap; anak objek span ikut world-x sendiri
    if o.parent in moves:
        continue                     # induknya sudah digeser, anak ikut
    m = o.matrix_world.copy(); m.translation.x += dx; o.matrix_world = m
bpy.context.view_layer.update()
# Serat kayu: UV meter dihitung ulang pada kayu yang meregang (rail depan, plint depan/belakang)
for o in span:
    if o.type == 'MESH' and any(s.material and s.material.get('ns_role') == 'WOOD_A' for s in o.material_slots):
        dims = o.dimensions
        uv_meter(o, 'XYZ'[max(range(3), key=lambda i: dims[i])])

# 2) Sambungan jok: dua pulau mesh DS_Seat_Fixed (jok atas & deck)
seat = D.objects['DS_Seat_Fixed']; mw = seat.matrix_world; inv = mw.inverted()
bm = bmesh.new(); bm.from_mesh(seat.data); bm.verts.ensure_lookup_table()
islands, seen = [], set()
for v in bm.verts:
    if v.index in seen:
        continue
    stack, isl = [v], []; seen.add(v.index)
    while stack:
        x = stack.pop(); isl.append(x)
        for e in x.link_edges:
            w = e.other_vert(x)
            if w.index not in seen:
                seen.add(w.index); stack.append(w)
    islands.append(isl)
assert len(islands) == 2, len(islands)
def zr(isl):
    zs = [(mw @ v.co).z for v in isl]; return min(zs), max(zs)
deck, top = sorted(islands, key=lambda i: zr(i)[0])
d0, d1 = zr(deck); t0, t1 = zr(top)
overlap = d1 - t0
dz = (SEAM + overlap / 2) - d1
def deck_z(z):
    if z >= d1 - R: return z + dz
    if z <= d0 + R: return z
    return (d0 + R) + (z - d0 - R) * (d1 - R + dz - d0 - R) / (d1 - R - d0 - R)
def top_z(z):
    if z <= t0 + R: return z + dz
    if z >= t1 - R: return z
    return (t1 - R) - (t1 - R - z) * (t1 - R - (t0 + R + dz)) / (t1 - R - (t0 + R))
for isl, fn in ((deck, deck_z), (top, top_z)):
    for v in isl:
        p = mw @ v.co; p.z = fn(p.z); v.co = inv @ p
bm.to_mesh(seat.data); bm.free(); seat.data.update()
# Piping: atas deck & bawah jok atas ikut sambungan; piping atas jok & bawah deck tetap
for n in ('DS_SeatDeck_PipingA', 'DS_Seat_Fixed_PipingB'):
    each_point(D.objects[n], lambda p: (setattr(p, 'z', p.z + dz), p)[1])

root['lebar_2130'] = True
bpy.context.view_layer.update()
allp = [p for o in objs for p in wb(o)]
print('##lebar', round(max(p.x for p in allp) - min(p.x for p in allp), 4), 'geser ujung', round(d, 4),
      '##deck', round(d0, 3), round(d1 + dz, 3), '##jok atas', round(t0 + dz, 3), round(t1, 3), 'dz', round(dz, 4))
bpy.ops.wm.save_mainfile()
