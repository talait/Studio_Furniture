# Tambah plint (kaki) melengkung yang menjorok ke dalam di bawah rangka Doheny Bed, seperti foto referensi:
# rangka seolah melayang di atas alas setinggi HEIGHT, mundur INSET dari sisi luar rangka, sudut membulat.
# Rangka (seluruh produk kecuali plint) diturunkan/dinaikkan agar duduk tepat di atas plint.
# UV dalam meter, serat sepanjang keliling (V, sama seperti rangka).
# Jalankan pada file tanpa plint: blender -b Doheny_Bed.blend --python tambah_plint_bed.py
import bpy, bmesh, math
from mathutils import Vector
INSET, HEIGHT, RADIUS, SEG = 0.05, 0.05, 0.04, 10
INSET_BELAKANG = 0.0               # sisi headboard: plint rata dengan belakang rangka (tidak mengambang)
NAME = 'Kayu | Plint bawah melengkung'
old = bpy.data.objects.get(NAME)
if old is not None:
    bpy.data.objects.remove(old, do_unlink=True)
root = next(o for o in bpy.data.objects if o.name.startswith('PRODUCT_ROOT'))
frame = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('Kayu')]
pts = [o.matrix_world @ Vector(c) for o in frame for c in o.bound_box]
# turunkan produk agar sisi bawah rangka tepat di HEIGHT (anak langsung root saja, cucu ikut induknya)
shift = HEIGHT - min(p.z for p in pts)
for obj in [o for o in bpy.data.collections['PRODUK'].objects if o.parent == root]:
    obj.matrix_world.translation.z += shift
bpy.context.view_layer.update()
pts = [o.matrix_world @ Vector(c) for o in frame for c in o.bound_box]
x0, x1 = min(p.x for p in pts) + INSET, max(p.x for p in pts) - INSET
y0, y1 = min(p.y for p in pts) + INSET, max(p.y for p in pts) - INSET_BELAKANG
z0, z1 = 0.0, min(p.z for p in pts)                      # celah di bawah rangka
# keliling persegi panjang membulat (berlawanan jarum jam)
outline = []
for cx, cy, a0 in ((x1 - RADIUS, y0 + RADIUS, -90), (x1 - RADIUS, y1 - RADIUS, 0),
                   (x0 + RADIUS, y1 - RADIUS, 90), (x0 + RADIUS, y0 + RADIUS, 180)):
    for i in range(SEG + 1):
        a = math.radians(a0 + 90 * i / SEG)
        outline.append((cx + RADIUS * math.cos(a), cy + RADIUS * math.sin(a)))
bm = bmesh.new()
bot = [bm.verts.new((x, y, z0)) for x, y in outline]
top = [bm.verts.new((x, y, z1)) for x, y in outline]
n = len(outline)
uv = bm.loops.layers.uv.new('UV meter')
dist = [0.0]
for i in range(1, n + 1):
    a, b = outline[i - 1], outline[i % n]
    dist.append(dist[-1] + math.dist(a, b))
for i in range(n):
    j = (i + 1) % n
    f = bm.faces.new((bot[i], bot[j], top[j], top[i]))
    # serat 'V' (sepanjang V seperti rangka produk ini): V = jarak keliling, U = tinggi
    for loop, (u, v) in zip(f.loops, ((z0, dist[i]), (z0, dist[i + 1]), (z1, dist[i + 1]), (z1, dist[i]))):
        loop[uv].uv = (u, v)
ftop = bm.faces.new(top); fbot = bm.faces.new(list(reversed(bot)))
for f in (ftop, fbot):
    for loop in f.loops:
        loop[uv].uv = (loop.vert.co.y, loop.vert.co.x)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
me = bpy.data.meshes.new(NAME)
bm.to_mesh(me); bm.free()
for p in me.polygons:
    p.use_smooth = True
obj = bpy.data.objects.new(NAME, me)
bpy.data.collections['PRODUK'].objects.link(obj)
obj.data.materials.append(bpy.data.materials['FIN | Oak Natural (foto referensi)'])
bev = obj.modifiers.new('Bevel', 'BEVEL'); bev.width = 0.004; bev.segments = 3; bev.limit_method = 'ANGLE'
obj.modifiers.new('WeightedNormal', 'WEIGHTED_NORMAL')
root = next(o for o in bpy.data.objects if o.name.startswith('PRODUCT_ROOT'))
obj.parent = root; obj.matrix_parent_inverse = root.matrix_world.inverted()
print('##plint', [round(v, 3) for v in (x0, x1, y0, y1, z0, z1)], 'keliling', round(dist[-1], 2), 'm')
bpy.ops.wm.save_mainfile()
