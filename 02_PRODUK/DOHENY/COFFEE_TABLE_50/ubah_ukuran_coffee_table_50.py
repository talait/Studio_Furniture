# Doheny Coffee Table (140 x 60 x 40 cm) -> versi side table 50 x 50 x 50 cm, desain sama:
# empat sudut lengkung, rel atas/bawah, kaca hammered di atas. Pembagi tengah (tiang tengah + sambungan
# lengkung + rel silang) dihapus -> satu bukaan, satu kaca.
# Tiap sumbu: verteks di dalam "zona" diregang/dirapatkan linear, di luar zona hanya bergeser, sehingga
# potongan sudut, radius lengkung, tebal rel dan kaca tetap; modifier Bevel tidak diubah. UV 'UV meter'
# dihitung ulang per face supaya tetap dalam meter.
# Jalankan: blender -b Doheny_Coffee_Table_50.blend --python ubah_ukuran_coffee_table_50.py
import bpy, numpy as np
from mathutils import Vector

TARGET = (0.50, 0.50, 0.50)
# zona: X & Y di antara potongan sudut (|x|<0.55, |y|<0.15); Z di bagian lurus kaki (0.1051-0.295)
ZONES = {0: (-0.55, 0.55), 1: (-0.15, 0.15), 2: (0.11, 0.29)}
ANCHOR = {0: 0.5, 1: 0.5, 2: 0.0}      # X & Y simetris dari tengah; Z dari lantai
NAME = 'Doheny Coffee Table 50'
HAPUS = ('Rel silang tengah', 'Sambungan tiang tengah', 'Tiang tengah')

for o in [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith(HAPUS)]:
    bpy.data.objects.remove(o, do_unlink=True)
meshes = [o for o in bpy.data.objects if o.type == 'MESH']


def bounds(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    return Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)])


lo0, hi0 = bounds(meshes)
scale = {ax: 1 + (TARGET[ax] - (hi0[ax] - lo0[ax])) / (zhi - zlo) for ax, (zlo, zhi) in ZONES.items()}


def remap(c, ax):
    zlo, zhi = ZONES[ax]; s = scale[ax]
    extra = (zhi - zlo) * (s - 1)
    shift_lo = -extra * ANCHOR[ax]
    if c <= zlo:
        return c + shift_lo
    if c >= zhi:
        return c + shift_lo + extra
    return zlo + shift_lo + (c - zlo) * s


def remap_vec(p):
    return Vector((remap(p.x, 0), remap(p.y, 1), remap(p.z, 2)))


for o in meshes:
    me = o.data
    M, Mi = o.matrix_world.copy(), o.matrix_world.inverted()
    old_w = [M @ v.co for v in me.vertices]
    new_w = [remap_vec(p) for p in old_w]
    # UV meter: uv_baru = uv_lama + J * (posisi_baru - posisi_lama), J dari face lama (kuadrat terkecil)
    uv = me.uv_layers.get('UV meter')
    if uv is not None:
        for poly in me.polygons:
            idx = [me.loops[li].vertex_index for li in poly.loop_indices]
            P = np.array([old_w[i] for i in idx]); U = np.array([uv.data[li].uv[:] for li in poly.loop_indices])
            Pc, Uc = P - P.mean(0), U - U.mean(0)
            if np.abs(Pc).max() < 1e-9:
                continue
            J, *_ = np.linalg.lstsq(Pc, Uc, rcond=None)
            for k, (li, i) in enumerate(zip(poly.loop_indices, idx)):
                uv.data[li].uv = (U[k] + np.array(new_w[i] - old_w[i]) @ J).tolist()
    for v, p in zip(me.vertices, new_w):
        v.co = Mi @ p
    me.update()
bpy.context.view_layer.update()

root = next(o for o in bpy.data.objects if o.name.startswith('PRODUCT_ROOT'))
root.name = 'PRODUCT_ROOT | ' + NAME
lo2, hi2 = bounds(meshes)
root['dimensions_cm'] = [round((hi2[i] - lo2[i]) * 100, 3) for i in range(3)]
root['ns_nama_produk'] = NAME
root['ns_ukuran_nominal_cm'] = [50, 50, 50]
print('##skala', {k: round(v, 4) for k, v in scale.items()}, 'ukuran cm', list(root['dimensions_cm']))
bpy.ops.wm.save_mainfile()
