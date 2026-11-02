# Lengkung bingkai headboard Doheny Bed mengikuti sudut jok (bantalan kain): busur bingkai dibuat
# konsentris dengan sudut jok (radius dalam = radius jok), tebal batang tetap. Tiang memanjang ke atas
# dan rel atas memanjang ke samping untuk menyambung busur yang lebih kecil.
# Jalankan: blender -b Doheny_Bed.blend --python headboard_ikut_jok.py
import bpy, bmesh, math
R_OLD, R_NEW = 0.165, 0.10            # radius dalam busur lama / baru (= radius sudut jok, diukur ~0.10 m)
EPS = 1e-4


def find(part):
    return bpy.data.objects[next(n for n in bpy.data.objects.keys() if part in n)]


rail = find('Headboard rel atas')
rail_bm = bmesh.new(); rail_bm.from_mesh(rail.data)
Mr = rail.matrix_world; Mri = Mr.inverted()
for side, sign in (('kanan', 1), ('kiri', -1)):
    post = find('Tiang headboard ' + side)
    M, Mi = post.matrix_world, post.matrix_world.inverted()
    bm = bmesh.new(); bm.from_mesh(post.data)
    world = {v: M @ v.co for v in bm.verts}
    xs = [p.x for p in world.values()]; top = max(p.z for p in world.values())
    outer_x = max(xs) if sign > 0 else min(xs)
    inner_x = outer_x - sign * 0.035                       # sisi dalam batang
    inner_top = top - 0.035                                # sisi bawah rel atas
    old_c = (inner_x - sign * R_OLD, inner_top - R_OLD)
    new_c = (inner_x - sign * R_NEW, inner_top - R_NEW)
    moved = 0
    for v, p in world.items():
        dx, dz = sign * (p.x - old_c[0]), p.z - old_c[1]
        if dx < -EPS or dz < -EPS:
            continue                                      # bukan bagian sudut
        r, a = math.hypot(dx, dz), math.atan2(dz, dx)
        r2 = r - R_OLD + R_NEW
        p.x = new_c[0] + sign * r2 * math.cos(a)
        p.z = new_c[1] + r2 * math.sin(a)
        v.co = Mi @ p
        moved += 1
    bm.to_mesh(post.data); bm.free()
    # rel atas: ujung di sisi ini menyambung ke awal busur baru
    old_end, new_end = old_c[0], new_c[0]
    for v in rail_bm.verts:
        p = Mr @ v.co
        if abs(p.x - old_end) < 0.002:
            p.x = new_end; v.co = Mri @ p
    print(f'##{side}: {moved} titik sudut, pusat busur {old_c} -> {tuple(round(c, 3) for c in new_c)}, rel ujung {round(old_end, 3)} -> {round(new_end, 3)}')
rail_bm.to_mesh(rail.data); rail_bm.free()
bpy.ops.wm.save_mainfile()
