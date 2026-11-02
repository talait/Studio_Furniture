# Bangun ulang Beechwood Buffet dari mesh impor DWG (Mesh_0_* per warna ACI) menjadi part konstruksi bersih:
# carcass mitre 45° + alur panel belakang, 3 sekat, 1 ambalan per ruang pintu (2 saf), 4 pintu frame mitre + anyaman rotan + les,
# handle DWG dipertahankan, kaki sled bersilang (sambungan silang setengah). Ukuran diukur dari mesh impor, dipusatkan
# (x tengah = 0, lantai z = 0, muka pintu y = -309). Warna mengikuti foto referensi (oak natural terang + rotan natural).
# Pakai:
#   blender -b "BEECHWOOD BUFFET.blend" --python perbaiki_buffet.py -- [--simpan] <laporan.json>
import bpy, bmesh, json, math, sys, os
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import konstruksi_util as K
from konstruksi_util import MM, note, bounds, sub, pindah, uv_meter, set_origin_center

NAMA = "Beechwood Buffet"
SRC = "dibangun ulang dari impor DWG BEECHWOOD BUFFET (ukuran diukur dari Mesh_0_23), perbaiki_buffet.py 2026-10-31"
GESER = Vector((-117.5, -19.3, -1.0)) * MM        # impor lama -> koordinat baru (dipusatkan)

# ------------------------------------------------------------ ukuran (mm)
W, T = 1800.0, 28.0
X0 = W / 2
Z_BOT, Z_TOP = 191.0, 900.0                       # carcass 709 tinggi, duduk di kaki 191
Y_F, Y_B = -281.0, 309.0                          # muka depan / belakang carcass (590)
T_PINTU, CELAH = 28.0, 3.0
Y_PF = Y_F - T_PINTU                              # muka depan pintu -309
T_PB, ALUR = 7.0, 9.0                             # panel belakang 7 mm di alur 9 mm
Y_PB = Y_B - T_PB
T_SEKAT, T_AMB = 28.0, 22.0
LEBAR_PINTU = (W - 3 * CELAH) / 4                 # 447,75
FRAME, REBATE, DALAM_REB = 27.0, 6.5, 6.5         # frame tampak 27, kantong rotan 6,5 x 6,5 dari muka

# ------------------------------------------------------------ scene, collection, material
sc = bpy.context.scene
sc.name = "PRODUK | " + NAMA
prod = bpy.data.collections.get("PROD | " + NAMA) or bpy.data.collections.new("PROD | " + NAMA)
if prod.name not in sc.collection.children:
    sc.collection.children.link(prod)
root = bpy.data.objects.new("PRODUCT_ROOT | " + NAMA, None)
prod.objects.link(root)
root["ns_product_root"] = True
root["dimensions_cm"] = [W / 10, (Y_B - Y_PF) / 10, Z_TOP / 10]
root["source"] = "BEECHWOOD BUFFET.blend (impor DWG, Mesh_0_*)"
root["unit_assumption"] = "mm; mesh impor dibaca dalam meter (1 BU = 1 m)"
root["warna"] = "oak/beech natural terang + rotan natural + handle logam gelap (ikut foto referensi 31-10-2026)"
CATATAN = ("2026-10-31: Mesh impor menyatukan carcass + frame pintu 1 & 4 + kaki dalam satu objek, ada kotak duplikat di dalam sekat, "
                   "rotan tanpa tebal, dan figur manusia skala. Dibangun ulang per part; 1 ambalan/ruang = 2 saf "
                   "(dikoreksi 31-10-2026). Rail atas pintu DWG 38 mm dibuat 27 mm seperti 3 sisi lain agar mitre 45°.")

WARNA = {  # linear RGB, roughness, metallic
    "WOOD_A": ((0.66, 0.55, 0.40, 1), 0.48, 0.0),     # oak/beech natural terang (badan, pintu, kaki)
    "WOOD_B": ((0.72, 0.62, 0.48, 1), 0.60, 0.0),     # interior: sekat, ambalan, panel belakang
    "RATTAN": ((0.64, 0.48, 0.26, 1), 0.55, 0.0),     # anyaman rotan natural
    "HANDLE": ((0.30, 0.28, 0.26, 1), 0.35, 1.0),     # logam gelap seperti foto
}
for role, (col, rough, metal) in WARNA.items():
    m = bpy.data.materials.get("ROLE | " + role) or bpy.data.materials.new("ROLE | " + role)
    m.use_nodes = True
    p = next(n for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = col
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    m.diffuse_color = col

C_CAR = sub("01 Carcass", prod)
C_AMB = sub("02 Ambalan", prod)
C_PINTU = sub("03 Pintu", prod)
C_KAKI = sub("04 Kaki", prod)


# ------------------------------------------------------------ helper geometri (semua dalam mm, objek di identitas)
def bm_kotak(x0, x1, y0, y1, z0, z1):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector(((x1 - x0) * (v.co.x + 0.5) + x0, (y1 - y0) * (v.co.y + 0.5) + y0, (z1 - z0) * (v.co.z + 0.5) + z0)) * MM
    return bm


def bm_prisma(profil, sumbu, a0, a1):
    """Sama dengan K.prisma: X -> (y, z), Y -> (x, z), Z -> (x, y)."""
    def p3(u, w, a):
        return {"X": Vector((a, u, w)), "Y": Vector((u, a, w)), "Z": Vector((u, w, a))}[sumbu] * MM
    bm = bmesh.new()
    fv = [bm.verts.new(p3(u, w, a0)) for u, w in profil]
    bv = [bm.verts.new(p3(u, w, a1)) for u, w in profil]
    bm.faces.new(fv[::-1]); bm.faces.new(bv)
    for i in range(len(profil)):
        j = (i + 1) % len(profil)
        bm.faces.new((fv[i], fv[j], bv[j], bv[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def busur(cx, cy, r, a0, a1, n=12):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def stadion(c0, c1, sumbu_panjang, tengah_lain, r, n=12):
    """Profil XY 'stadion' (ujung setengah lingkaran) untuk membulatkan ujung papan kaki."""
    if sumbu_panjang == "X":
        return busur(c1 - r, tengah_lain, r, -90, 90, n) + busur(c0 + r, tengah_lain, r, 90, 270, n)
    return [(y, x) for x, y in busur(c1 - r, tengah_lain, r, -90, 90, n) + busur(c0 + r, tengah_lain, r, 90, 270, n)][::-1]


def mitre(bm, planes):
    """Buang sisi +normal tiap bidang (titik mm), tutup lubang potongan."""
    for co, no in planes:
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-7,
                               plane_co=Vector(co) * MM, plane_no=Vector(no).normalized(), clear_outer=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=2e-6)
    pl = [(Vector(co) * MM, Vector(no).normalized()) for co, no in planes]
    on = lambda v: any(abs((v.co - c).dot(n)) < 1e-5 for c, n in pl)
    bnd = [e for e in bm.edges if e.is_boundary and on(e.verts[0]) and on(e.verts[1])]
    if bnd:
        bmesh.ops.holes_fill(bm, edges=bnd, sides=0)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-7, edges=bm.edges[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def objek(name, bm, coll):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    return o


def boolean(o, cutter_bm, op):
    me = bpy.data.meshes.new("_cutter")
    cutter_bm.to_mesh(me); cutter_bm.free()
    c = bpy.data.objects.new("_cutter", me)
    sc.collection.objects.link(c)
    m = o.modifiers.new("_bool", "BOOLEAN")
    m.operation = op; m.solver = "EXACT"; m.object = c
    dg = bpy.context.evaluated_depsgraph_get()
    nm = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    nm.materials.clear()                          # boolean membawa slot kosong; material dipasang di selesai()
    o.modifiers.remove(m)
    old = o.data; o.data = nm
    bpy.data.meshes.remove(old); bpy.data.objects.remove(c); bpy.data.meshes.remove(me)
    nm.name = o.name


def selesai(o, role, grain, parent, ukuran, sambungan="", bev=True):
    set_origin_center(o)
    uv_meter(o, grain)
    if bev:
        K.bevel(o)
    o.data.materials.append(bpy.data.materials["ROLE | " + role])
    pw = o.matrix_world.copy()
    o.parent = parent
    o.matrix_parent_inverse = parent.matrix_world.inverted()
    o.matrix_world = pw
    o["ns_role_part"] = role
    o["geometry_source"] = SRC
    o["ukuran_potong_mm"] = ukuran
    if sambungan:
        o["sambungan"] = sambungan
    return o


# ------------------------------------------------------------ 0. arsipkan impor lama
lama = [o for o in bpy.data.objects if o.name.startswith("Mesh_0_")]
for o in lama:
    K.arsipkan(o, prod)
    o.name = "Lama: " + o.name
rk = bpy.data.collections.get("Rakitan_1")
if rk and not rk.objects:
    bpy.data.collections.remove(rk)
note(f"{len(lama)} mesh impor lama (termasuk figur manusia skala & garis lepas) dipindah ke _ARSIP")
for nm in ("Kamera", "Matahari", "Fill"):
    if bpy.data.objects.get(nm):
        bpy.data.objects[nm].location += GESER
note("Kamera & lampu digeser sama dengan pemusatan produk (x -117,5, y -19,3, z -1 mm)")

# ------------------------------------------------------------ 1. carcass: top, dasar, sisi kiri/kanan mitre 45° + alur belakang
XI, ZI_B, ZI_T = X0 - T, Z_BOT + T, Z_TOP - T
panel = {
    "Top": ([(-X0, Z_TOP), (X0, Z_TOP), (XI, ZI_T), (-XI, ZI_T)], (-895, 895, Y_PB, Y_B + 1, ZI_T - 12, ZI_T + ALUR), "X"),
    "Dasar": ([(-X0, Z_BOT), (-XI, ZI_B), (XI, ZI_B), (X0, Z_BOT)], (-895, 895, Y_PB, Y_B + 1, ZI_B - ALUR, ZI_B + 12), "X"),
    "Sisi kiri": ([(-X0, Z_BOT), (-X0, Z_TOP), (-XI, ZI_T), (-XI, ZI_B)], (-XI - ALUR, -XI + 12, Y_PB, Y_B + 1, Z_BOT + 4, Z_TOP - 4), "Z"),
    "Sisi kanan": ([(X0, Z_BOT), (XI, ZI_B), (XI, ZI_T), (X0, Z_TOP)], (XI - 12, XI + ALUR, Y_PB, Y_B + 1, Z_BOT + 4, Z_TOP - 4), "Z"),
}
for nm, (prof, alur, g) in panel.items():
    o = objek(f"{nm} (mitre 45°)", bm_prisma(prof, "Y", Y_F, Y_B), C_CAR)
    boolean(o, bm_kotak(*alur), "DIFFERENCE")
    pj = (W if g == "X" else Z_TOP - Z_BOT)
    selesai(o, "WOOD_A", g, root, f"{pj:.0f} x {Y_B - Y_F:.0f} x {T:.0f}", "mitre 45° + lamello/dowel; alur panel belakang 9 x 7")
note(f"Carcass {W:.0f} x {Y_B - Y_F:.0f} x {Z_TOP - Z_BOT:.0f} mm, papan {T:.0f} mm, 4 sudut mitre 45°, alur belakang {ALUR:.0f} x {T_PB:.0f}")

pb = objek("Panel belakang 7 mm", bm_kotak(-XI - ALUR + 0.5, XI + ALUR - 0.5, Y_PB, Y_B, ZI_B - ALUR + 0.5, ZI_T + ALUR - 0.5), C_CAR)
selesai(pb, "WOOD_B", "X", root, f"{2 * (XI + ALUR) - 1:.0f} x {ZI_T - ZI_B + 2 * ALUR - 1:.0f} x {T_PB:.0f}", "masuk alur keliling carcass")

# ------------------------------------------------------------ 2. sekat (di belakang tiap pertemuan pintu)
SEKAT_X = [-X0 + LEBAR_PINTU + CELAH / 2, 0.0, X0 - LEBAR_PINTU - CELAH / 2]       # -450,75 / 0 / 450,75
for i, cx in enumerate(SEKAT_X, 1):
    o = objek(f"Sekat {i}", bm_kotak(cx - T_SEKAT / 2, cx + T_SEKAT / 2, Y_F, Y_PB, ZI_B, ZI_T), C_CAR)
    selesai(o, "WOOD_B", "Z", root, f"{ZI_T - ZI_B:.0f} x {Y_PB - Y_F:.0f} x {T_SEKAT:.0f}", "dado 6 mm / dowel ke top & dasar")
tepi = [-XI] + [v for cx in SEKAT_X for v in (cx - T_SEKAT / 2, cx + T_SEKAT / 2)] + [XI]
RUANG = [(tepi[2 * k], tepi[2 * k + 1]) for k in range(4)]
note("Sekat 28 mm di x = " + ", ".join(f"{c:.2f}" for c in SEKAT_X) + "; ruang: " + ", ".join(f"{b - a:.2f}" for a, b in RUANG))

# ------------------------------------------------------------ 3. ambalan: 1 per ruang pintu -> 2 saf, jarak bersih sama
N_AMB = 1
bukaan = (ZI_T - ZI_B - N_AMB * T_AMB) / (N_AMB + 1)
for k, (a, b) in enumerate(RUANG, 1):
    c = sub(f"Ambalan ruang {k}", C_AMB)
    for j in range(N_AMB):
        z0 = ZI_B + bukaan * (j + 1) + T_AMB * j
        o = objek(f"Ambalan {k} 22 mm", bm_kotak(a + 1, b - 1, Y_F + 2, Y_PB - 2, z0, z0 + T_AMB), c)
        selesai(o, "WOOD_B", "X", root, f"{b - a - 2:.1f} x {Y_PB - Y_F - 4:.0f} x {T_AMB:.0f}", "duduk di 4 pen ambalan Ø5, bisa dipindah")
note(f"{4 * N_AMB} ambalan {T_AMB:.0f} mm ({N_AMB} per ruang), bukaan bersih {bukaan:.1f} mm x {N_AMB + 1} saf")

# ------------------------------------------------------------ 4. pintu: frame mitre 4 batang + anyaman rotan + les setengah bulat
PROF_FRAME = [(0, 0), (FRAME, 0), (FRAME, DALAM_REB), (FRAME + REBATE, DALAM_REB), (FRAME + REBATE, T_PINTU), (0, T_PINTU)]
R_LES, U_LES, D_ROTAN, T_ROTAN = 3.5, FRAME + 0.5 + 3.5, 4.0, 2.5
PROF_LES = [(U_LES + R_LES * math.cos(math.radians(a)), D_ROTAN - R_LES * math.sin(math.radians(a))) for a in range(0, 181, 15)]


def cincin(prof, x0, x1, z0, z1):
    """Profil (u, d) disapu keliling bukaan pintu -> satu cincin tertutup dengan sudut mitre (manifold)."""
    bm = bmesh.new()
    ring = []
    for u, d in prof:
        y = Y_PF + d
        ring.append([bm.verts.new(Vector((x, y, z)) * MM) for x, z in ((x0 + u, z0 + u), (x1 - u, z0 + u), (x1 - u, z1 - u), (x0 + u, z1 - u))])
    n = len(prof)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        for s in range(4):
            bm.faces.new((a[s], a[(s + 1) % 4], b[(s + 1) % 4], b[s]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def batang(prof, sisi, x0, x1, z0, z1):
    """prof (u = jarak ke dalam dari tepi luar, d = kedalaman dari muka pintu) -> potongan mitre pada sisi pintu."""
    if sisi == "kiri":
        bm = bm_prisma([(x0 + u, Y_PF + d) for u, d in prof], "Z", z0 - 1, z1 + 1)
        pl = [((x0, 0, z0), (1, 0, -1)), ((x0, 0, z1), (1, 0, 1))]
    elif sisi == "kanan":
        bm = bm_prisma([(x1 - u, Y_PF + d) for u, d in prof], "Z", z0 - 1, z1 + 1)
        pl = [((x1, 0, z0), (-1, 0, -1)), ((x1, 0, z1), (-1, 0, 1))]
    elif sisi == "bawah":
        bm = bm_prisma([(Y_PF + d, z0 + u) for u, d in prof], "X", x0 - 1, x1 + 1)
        pl = [((x0, 0, z0), (-1, 0, 1)), ((x1, 0, z0), (1, 0, 1))]
    else:
        bm = bm_prisma([(Y_PF + d, z1 - u) for u, d in prof], "X", x0 - 1, x1 + 1)
        pl = [((x0, 0, z1), (-1, 0, -1)), ((x1, 0, z1), (1, 0, -1))]
    return mitre(bm, pl)


handle_lama = bpy.data.objects["Lama: Mesh_0_18"]
for i in range(4):
    x0 = -X0 + i * (LEBAR_PINTU + CELAH); x1 = x0 + LEBAR_PINTU
    z0, z1 = Z_BOT, Z_TOP
    engsel_kiri = i in (0, 2)                     # pasangan pintu 1-2 & 3-4 bertemu di tengah, handle di pertemuan
    hx = x0 if engsel_kiri else x1
    door = bpy.data.objects.new(f"DOOR_{i + 1} | {NAMA}", None)
    c = sub(f"Pintu {i + 1}", C_PINTU)
    c.objects.link(door)
    door.location = Vector((hx, Y_F, 0)) * MM
    door.empty_display_size = 0.05
    door.parent = root
    bpy.context.view_layer.update()
    door["engsel"] = ("kiri" if engsel_kiri else "kanan") + "; sumbu di tepi belakang pintu (engsel sendok/cup 35 mm full overlay)"
    for sisi in ("kiri", "kanan", "bawah", "atas"):
        o = objek(f"Pintu {i + 1} / {'stile' if sisi in ('kiri', 'kanan') else 'rail'} {sisi}", batang(PROF_FRAME, sisi, x0, x1, z0, z1), c)
        pj = z1 - z0 if sisi in ("kiri", "kanan") else x1 - x0
        selesai(o, "WOOD_A", "Z" if sisi in ("kiri", "kanan") else "X", door,
                f"{pj:.1f} x {FRAME + REBATE:.1f} x {T_PINTU:.0f}", "mitre 45° + spline/dowel; kantong rotan 6,5 x 6,5 di muka")
    rot = objek(f"Pintu {i + 1} / anyaman rotan", bm_kotak(x0 + FRAME + 0.5, x1 - FRAME - 0.5, Y_PF + D_ROTAN, Y_PF + D_ROTAN + T_ROTAN,
                                                           z0 + FRAME + 0.5, z1 - FRAME - 0.5), c)
    selesai(rot, "RATTAN", "Z", door, f"{x1 - x0 - 2 * FRAME - 1:.1f} x {z1 - z0 - 2 * FRAME - 1:.1f} x {T_ROTAN}",
            "duduk di kantong frame, dikunci les", bev=False)
    les = objek(f"Pintu {i + 1} / les rotan", cincin(PROF_LES, x0, x1, z0, z1), c)
    selesai(les, "WOOD_A", "Z", door, f"setengah bulat R{R_LES} keliling", "dipaku tembak ke frame, menjepit tepi rotan", bev=False)
note(f"4 pintu full overlay {LEBAR_PINTU:.2f} x {Z_TOP - Z_BOT:.0f} x {T_PINTU:.0f} mm, celah {CELAH:.0f} mm; frame tampak {FRAME:.0f} mm mitre 45°")

# handle: geometri DWG dipertahankan, dipisah per pintu dan digeser ke koordinat baru
bm_all = bmesh.new(); bm_all.from_mesh(handle_lama.data); bm_all.transform(handle_lama.matrix_world)
bm_all.verts.ensure_lookup_table()
pulau, seen = [], set()
for v in bm_all.verts:
    if v.index in seen:
        continue
    st, comp = [v], []
    seen.add(v.index)
    while st:
        x = st.pop(); comp.append(x)
        for e in x.link_edges:
            y = e.other_vert(x)
            if y.index not in seen:
                seen.add(y.index); st.append(y)
    pulau.append(comp)
grup = {}
for comp in pulau:
    ys = [p.co.y for p in comp]
    if max(ys) - min(ys) < 1e-4 and len(comp) <= 14:      # bidang rotan datar -> tidak dipakai
        continue
    cx = sum(p.co.x for p in comp) / len(comp) + GESER.x
    k = min(range(4), key=lambda i: abs(cx - (-X0 + i * (LEBAR_PINTU + CELAH) + (LEBAR_PINTU if i in (0, 2) else 0)) * MM))
    grup.setdefault(k, set()).update(p.index for p in comp)
for k, idx in sorted(grup.items()):
    bm = bm_all.copy()
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in range(len(bm.verts)) if i not in idx], context="VERTS")
    bm.transform(Matrix.Translation(GESER))
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)          # las vertex kembar hasil tessellasi DWG
    bmesh.ops.dissolve_degenerate(bm, dist=1e-7, edges=bm.edges[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    o = objek(f"Handle pintu {k + 1}", bm, bpy.data.collections[f"Pintu {k + 1}"])
    selesai(o, "HANDLE", "Z", bpy.data.objects[f"DOOR_{k + 1} | {NAMA}"], "geometri DWG", "sekrup M4 tembus dari belakang stile", bev=False)
    o["geometry_source"] = "DWG (Mesh_0_18) dipertahankan, hanya digeser"
bm_all.free()
note(f"{len(grup)} handle DWG dipertahankan, dipasang di stile pertemuan pasangan pintu")

# ------------------------------------------------------------ 5. kaki sled bersilang (balok panjang + 2 kaki silang)
H_K, T_K, R_UJ = Z_BOT, 39.4, 19.7
Y_TENGAH = (Y_F + Y_B) / 2                                # 14


def papan_kaki(name, sumbu, a0, a1, kaki, fillet, tengah_lain, rel=52.0):
    """Profil samping: dua kaki di ujung + rel bawah setinggi 'rel', sudut dalam fillet; ujung dibulatkan di denah."""
    i0, i1 = a0 + kaki, a1 - kaki
    prof = [(a0, 0), (a1, 0), (a1, H_K), (i1, H_K)] + busur(i1 - fillet, rel + fillet, fillet, 0, -90) + \
           busur(i0 + fillet, rel + fillet, fillet, -90, -180) + [(i0, H_K), (a0, H_K)]
    t0, t1 = tengah_lain - T_K / 2, tengah_lain + T_K / 2
    o = objek(name, bm_prisma(prof, "Y" if sumbu == "X" else "X", t0, t1), C_KAKI)
    st = stadion(a0, a1, sumbu, tengah_lain, R_UJ)
    boolean(o, bm_prisma(st, "Z", -1, H_K + 1), "INTERSECT")
    return o


X_SILANG = 303.4
bal = papan_kaki("Kaki balok panjang", "X", -810.0, 810.0, 92.0, 50.0, Y_TENGAH)
silang = [papan_kaki(f"Kaki silang {'kiri' if s < 0 else 'kanan'}", "Y", Y_F, Y_B, 83.0, 55.0, s * X_SILANG) for s in (-1, 1)]
H_SET = 26.0
for s, o in zip((-1, 1), silang):
    boolean(bal, bm_kotak(s * X_SILANG - T_K / 2, s * X_SILANG + T_K / 2, Y_TENGAH - 30, Y_TENGAH + 30, -1, H_SET), "DIFFERENCE")
    boolean(o, bm_kotak(s * X_SILANG - 30, s * X_SILANG + 30, Y_TENGAH - T_K / 2, Y_TENGAH + T_K / 2, H_SET, 70), "DIFFERENCE")
selesai(bal, "WOOD_A", "X", root, f"1620 x {H_K:.0f} x {T_K}", "silang setengah (half-lap) dengan kaki silang; dowel + sekrup ke dasar carcass")
for o in silang:
    selesai(o, "WOOD_A", "Y", root, f"{Y_B - Y_F:.0f} x {H_K:.0f} x {T_K}", "silang setengah (half-lap) dengan balok panjang; dowel + sekrup ke dasar carcass")
note(f"Kaki: balok panjang 1620 + 2 kaki silang {Y_B - Y_F:.0f} (x = ±{X_SILANG}), tebal {T_K}, tinggi {H_K:.0f}, sambungan silang setengah {H_SET:.0f} mm")

# ------------------------------------------------------------ 6. laporan & simpan
K.tutup_laporan(prod, root, "dibangun ulang dari impor DWG: carcass mitre + alur belakang, 3 sekat, 1 ambalan per ruang (2 saf), "
                            "4 pintu frame mitre + rotan + les, handle DWG, kaki sled silang (perbaiki_buffet.py).")
root["catatan"] = CATATAN                         # tutup_laporan menempel tanggal 30-10; ganti dengan catatan sesi ini
if "--simpan" in sys.argv:
    bpy.ops.wm.save_mainfile(compress=True)
    note("Disimpan")
json.dump(K.laporan, open(sys.argv[-1], "w", encoding="utf-8"), indent=1, ensure_ascii=False)
