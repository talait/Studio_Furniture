# Doheny Bed (referensi render ke-2): jok headboard diberi peran BOUCLE (tekstur boucle dari preset,
# terpisah dari KAIN yang juga dipakai sofa), bantal dibuat lebih tebal/empuk dengan menskalakan
# ketebalannya (sumbu Y lokal). Displace sepanjang normal merusak mesh bantal (tepi tipis jadi sobek).
# Penebalan ditambahkan ke depan saja: sisi belakang bantal tetap di posisi asli (tidak tembus headboard).
# Jalankan: blender -b Doheny_Bed.blend --python bantal_boucle_bed.py
import bpy
from mathutils import Vector
TEBAL = 1.35                       # faktor ketebalan bantal terhadap ukuran asli
hb = bpy.data.materials['Kain Linen Headboard']; hb['ns_role'] = 'BOUCLE'


def back_y(obj):
    bpy.context.view_layer.update()
    return max((obj.matrix_world @ Vector(c)).y for c in obj.bound_box)


for obj in [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('Bantal')]:
    old = obj.modifiers.get('Gembung')
    if old is not None:
        obj.modifiers.remove(old)
    base = float(obj.get('ns_skala_y_asli', obj.scale.y))
    obj['ns_skala_y_asli'] = base
    if 'ns_belakang_y_asli' not in obj:            # ukur sisi belakang pada skala asli
        obj.scale.y = base
        obj['ns_belakang_y_asli'] = back_y(obj)
    obj.scale.y = base * TEBAL
    obj.matrix_world.translation.y += obj['ns_belakang_y_asli'] - back_y(obj)
    print('##', obj.name, round(obj.scale.y, 3), 'belakang', round(back_y(obj), 3), 'asli', round(obj['ns_belakang_y_asli'], 3))
bpy.ops.wm.save_mainfile()
