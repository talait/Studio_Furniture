# Doheny Sofa / Armchair: pindahkan sambungan jok atas/bawah ke tinggi SEAM (dari keadaan sekarang, boleh diulang).
# Default 0,269 m = tengah 88-450 mm: jok bawah dan jok atas tampak sama tinggi (+-181 mm). Tepi bulat tidak ikut meregang.
# blender -b 02_PRODUK/DOHENY/SOFA/Doheny_Sofa.blend --python sambungan_jok.py   (juga ARMCHAIR/Doheny_Armchair.blend)
import bpy, bmesh, os
D = bpy.data
root = next(o for o in D.objects if o.name.startswith('PRODUCT_ROOT'))
P = 'DS_' if 'Sofa' in root.name else 'DA_'
SEAM = float(os.environ.get('SEAM', '0.269'))   # tinggi sambungan jok (m)
R = 0.03                         # pita tepi bulat jok yang tidak ikut meregang

seat = D.objects[P + 'Seat_Fixed']; mw = seat.matrix_world; inv = mw.inverted()
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
dz = (SEAM + (d1 - t0) / 2) - d1
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
for n in (P + 'SeatDeck_PipingA', P + 'Seat_Fixed_PipingB'):
    o = D.objects[n]; m = o.matrix_world; mi = m.inverted()
    for sp in o.data.splines:
        for pt in sp.points:
            p = m @ pt.co.xyz; p.z += dz; pt.co = (*(mi @ p), pt.co.w)

root['sambungan_jok_m'] = SEAM
print('##deck', round(d0, 3), round(d1 + dz, 3), '##jok atas', round(t0 + dz, 3), round(t1, 3), 'dz', round(dz, 4))
bpy.ops.wm.save_mainfile()
