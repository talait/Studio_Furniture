# Samakan sandaran armchair dengan sofa: miring 12°, jok 45 cm, atas sandaran 89 cm, satu bantal sandaran di tengah.
# Gabungan 03_PROYEK/doheny_sofa_feedback_back_pillows_camera.py + doheny_sofa_adjust_us_dims.py, untuk file produk.
# blender -b 02_PRODUK/DOHENY/ARMCHAIR/Doheny_Armchair.blend --python sandaran_miring_armchair.py
import bpy, bmesh, math, mathutils
D = bpy.data
root = D.objects['PRODUCT_ROOT | Doheny_Armchair']
assert not root.get('sandaran_miring'), 'sudah diterapkan'
coll = root.users_collection[0]
PITCH = math.radians(12); tp = math.tan(PITCH)
Z0 = 0.472                       # tinggi atas dudukan lama (titik tekuk)
SEAT_OLD, SEAT_NEW, ZP = 0.472, 0.45, 0.24
BACK_NEW = SEAT_NEW + 0.44       # atas sandaran 89 cm
BACK = ['DA_Back_Body', 'DA_Inner_BackPost_L', 'DA_Inner_BackPost_R', 'DA_Inner_BackRail_Middle',
        'DA_Inner_BackRail_Top', 'DA_Inner_BackSheet']


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


# 1) Sandaran miring 12° dan naik 10 cm (seperti sofa, 28 Okt)
ZT, DZ = 0.65, 0.10
def pitch(p):
    if p.z > Z0:
        if p.z >= ZT: p.z += DZ
        else: p.z = Z0 + (p.z - Z0) * (ZT - Z0 + DZ) / (ZT - Z0)
        p.y += (p.z - Z0) * tp
    return p
for n in BACK:
    o = D.objects[n]
    if n != 'DA_Back_Body':
        # rangka kotak: potong di tinggi dudukan & ZT agar ikut tertekuk seperti jok
        inv = o.matrix_world.inverted()
        bm = bmesh.new(); bm.from_mesh(o.data)
        for zc in (Z0, ZT):
            co = inv @ mathutils.Vector((0, 0, zc))
            no = (inv.to_3x3().transposed().inverted() @ mathutils.Vector((0, 0, 1))).normalized()
            bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=co, plane_no=no)
        bm.to_mesh(o.data); bm.free()
    each_point(o, pitch)

# 2) Ukuran US: jok 47,2 -> 45 cm, atas sandaran 89 cm mengikuti kemiringan (seperti sofa, 29 Okt)
k = (SEAT_NEW - ZP) / (SEAT_OLD - ZP)
def seat(p):
    if p.z > ZP: p.z = ZP + (p.z - ZP) * k
    return p
for n in ('DA_Seat_Fixed', 'DA_Seat_Fixed_PipingA', 'DA_Seat_Fixed_PipingB'):
    each_point(D.objects[n], seat)
ZT = 0.75
dz = BACK_NEW - max((D.objects['DA_Back_Body'].matrix_world @ v.co).z for v in D.objects['DA_Back_Body'].data.vertices)
def raise_back(p):
    if p.z > Z0:
        nz = p.z + dz if p.z >= ZT else Z0 + (p.z - Z0) * (ZT - Z0 + dz) / (ZT - Z0)
        p.y += (nz - p.z) * tp; p.z = nz
    return p
for n in BACK:
    each_point(D.objects[n], raise_back)

# 3) Satu bantal sandaran di tengah, selebar ruang antar lengan (sofa: 2 x 80 cm)
def xs(n):
    o = D.objects[n]; return [(o.matrix_world @ mathutils.Vector(c)).x for c in o.bound_box]
gap = min(xs('DA_ArmPanel_Inner_R')) - max(xs('DA_ArmPanel_Inner_L'))
W, H, T, P = round(gap - 0.03, 3), 0.46, 0.19, 6
bm = bmesh.new(); bmesh.ops.create_cube(bm, size=2.0)
bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=14, use_grid_fill=True)
for v in bm.verts:
    x, y, z = v.co; m = max(abs(x), abs(z)); sn = (abs(x) ** P + abs(z) ** P) ** (1 / P)
    if sn > 0: x, z = x * m / sn, z * m / sn
    v.co = (x * W / 2, y * (T / 2) * (1 - 0.62 * m ** 6), z * H / 2)
me = D.meshes.new('DA_Pillow_Back'); bm.to_mesh(me); bm.free()
for f in me.polygons: f.use_smooth = True
pillow = D.objects.new('DA_Pillow_Back', me); me.materials.append(D.materials['DS_Linen_Beige'])
coll.objects.link(pillow)
sub = pillow.modifiers.new('Subdivision', 'SUBSURF'); sub.levels = 1; sub.render_levels = 2
cz = SEAT_NEW - 0.012 + (H / 2) * math.cos(PITCH)
pillow.rotation_euler = (-PITCH, 0, 0)
pillow.location = (0, 0.269 + max(0, cz - Z0) * tp - (T / 2) * 0.80, cz)
pillow.parent = root; pillow.matrix_parent_inverse = root.matrix_world.inverted()
cu = D.objects['DA_Seat_Fixed_PipingA'].data.copy(); cu.name = 'DA_Pillow_Back_Piping'; cu.splines.clear()
sp = cu.splines.new('POLY'); N = 72; sp.points.add(N - 1)
for i in range(N):
    a = 2 * math.pi * i / N; c, sn = math.cos(a), math.sin(a)
    sp.points[i].co = (math.copysign(abs(c) ** (2 / P), c) * (W / 2 - 0.003), 0,
                       math.copysign(abs(sn) ** (2 / P), sn) * (H / 2 - 0.003), 1)
sp.use_cyclic_u = True
pc = D.objects.new('DA_Pillow_Back_Piping', cu); coll.objects.link(pc); pc.parent = pillow

root['sandaran_miring'] = True
bpy.context.view_layer.update()
top = max((D.objects['DA_Back_Body'].matrix_world @ v.co).z for v in D.objects['DA_Back_Body'].data.vertices)
print('##sandaran atas', round(top, 3), 'bantal W', W, 'ruang lengan', round(gap, 3))
bpy.ops.wm.save_mainfile()
