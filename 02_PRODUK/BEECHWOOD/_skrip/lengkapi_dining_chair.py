# Lengkapi Beechwood Dining Chair sesuai foto referensi (31-10-2026): rangka DWG tidak diubah, hanya ditambah/diisi.
#   - Sandaran solid: papan lebar melengkung (cekung ke arah duduk) di antara dua tiang belakang, mengikuti
#     kemiringan tiang (garis tengah tiang diukur dari irisan mesh), tepi atas ~2 mm di bawah puncak tiang.
#   - Dudukan tali anyaman (paper/danish cord): 4 baji segitiga DWG (pola amplop) dipakai sebagai badan anyaman,
#     material baru ROLE | TALI (ns_role 'TALI'): helai Ø5 mm melilit palang, tegak lurus palang di tiap segitiga
#     (depan/belakang: helai sepanjang Y, kiri/kanan: sepanjang X), puntiran tali, warna natural terang.
# Pakai:
#   blender -b "BEECHWOOD DINNING CHAIR.blend" --python lengkapi_dining_chair.py -- [--simpan]
import bpy, bmesh, math, sys, os
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import konstruksi_util as K

ROOT = bpy.data.objects["PRODUCT_ROOT | Beechwood Dining Chair"]
C_BADAN = bpy.data.collections["Badan"]

# ------------------------------------------------------------ ukuran sandaran (m), dari irisan rangka samping
X_DALAM = 0.2085                 # muka dalam tiang belakang (irisan: x = ±0.2079..0.2096)
Z_BAWAH, Z_ATAS = 0.736, 0.856   # tinggi papan 120 mm; puncak tiang 0.858
TEBAL = 0.022
LENGKUNG = 0.012                 # tengah papan mundur 12 mm (cekung ke arah duduk)
YC0, KEMIRINGAN = 0.2077, 0.188  # garis tengah tiang: y = YC0 + KEMIRINGAN x (z - 0.76)  (~10.6° ke belakang)
N_X = 32


def sandaran():
    lama = bpy.data.objects.get("Sandaran solid")
    if lama is not None:
        me = lama.data; bpy.data.objects.remove(lama); bpy.data.meshes.remove(me)
    a = math.atan(KEMIRINGAN)
    naik = Vector((0, math.sin(a), math.cos(a)))          # arah tinggi papan (ikut kemiringan tiang)
    nrm = Vector((0, math.cos(a), -math.sin(a)))          # normal papan ke belakang
    s_max = (Z_ATAS - Z_BAWAH) / math.cos(a)
    y_bawah = YC0 + KEMIRINGAN * (Z_BAWAH - 0.76)
    bm = bmesh.new()
    grid = {}
    for i in range(N_X + 1):
        x = -X_DALAM + 2 * X_DALAM * i / N_X
        sag = LENGKUNG * (1 - (x / X_DALAM) ** 2)
        for j, s in enumerate((0.0, s_max)):
            c = Vector((x, y_bawah + sag, Z_BAWAH)) + naik * s
            grid[i, j, 0] = bm.verts.new(c - nrm * TEBAL / 2)     # muka depan (sisi duduk)
            grid[i, j, 1] = bm.verts.new(c + nrm * TEBAL / 2)     # muka belakang
    for i in range(N_X):
        bm.faces.new((grid[i, 0, 0], grid[i + 1, 0, 0], grid[i + 1, 1, 0], grid[i, 1, 0]))   # depan
        bm.faces.new((grid[i, 0, 1], grid[i, 1, 1], grid[i + 1, 1, 1], grid[i + 1, 0, 1]))   # belakang
        bm.faces.new((grid[i, 1, 0], grid[i + 1, 1, 0], grid[i + 1, 1, 1], grid[i, 1, 1]))   # atas
        bm.faces.new((grid[i, 0, 0], grid[i, 0, 1], grid[i + 1, 0, 1], grid[i + 1, 0, 0]))   # bawah
    for i in (0, N_X):
        bm.faces.new((grid[i, 0, 0], grid[i, 1, 0], grid[i, 1, 1], grid[i, 0, 1]))           # ujung (ke tiang)
    o = K._objek_baru("Sandaran solid", bm, "WOOD_A", C_BADAN, ROOT, K.SRC_TAMBAH + "; sesuai foto referensi kursi",
                      "X", (2 * X_DALAM * 1000, (Z_ATAS - Z_BAWAH) * 1000, TEBAL * 1000))
    o.modifiers["Bevel tepi"].width = 0.002
    o["sambungan"] = "pen 10 mm ke tiang belakang kiri/kanan (tidak dimodelkan); papan lengkung laminasi/solid dibentuk"
    for p in o.data.polygons:                         # muka lengkung halus, sudut tetap tajam lewat bevel
        p.use_smooth = True
    return o


def mat_tali():
    m = bpy.data.materials.get("ROLE | TALI") or bpy.data.materials.new("ROLE | TALI")
    m["ns_role"] = "TALI"
    m["catatan"] = "tali anyaman (paper/danish cord) Ø5 mm, natural terang; lengkapi_dining_chair.py 2026-10-31"
    m.diffuse_color = (0.66, 0.53, 0.35, 1)
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear(); L = nt.links.new
    def n(tipe, loc, **kw):
        x = nt.nodes.new(tipe); x.location = loc
        for k, v in kw.items():
            setattr(x, k, v)
        return x
    def mat(op, a, b, loc):
        x = n("ShaderNodeMath", loc, operation=op)
        for i, v in enumerate((a, b)):
            if isinstance(v, (int, float)):
                x.inputs[i].default_value = v
            elif v is not None:
                L(v, x.inputs[i])
        return x.outputs[0]
    out = n("ShaderNodeOutputMaterial", (1400, 0))
    bs = n("ShaderNodeBsdfPrincipled", (1100, 0))
    tc = n("ShaderNodeTexCoord", (-1400, 0))
    sp = n("ShaderNodeSeparateXYZ", (-1200, 0)); L(tc.outputs["Object"], sp.inputs[0])
    # arah helai per objek: tali_arah 0 -> helai sepanjang Y (jarak antar helai di X), 1 -> sepanjang X
    at = n("ShaderNodeAttribute", (-1200, -300), attribute_type="OBJECT", attribute_name="tali_arah")
    mx = n("ShaderNodeMix", (-1000, 100), data_type="FLOAT")
    L(at.outputs["Fac"], mx.inputs[0]); L(sp.outputs["X"], mx.inputs[2]); L(sp.outputs["Y"], mx.inputs[3])
    melintang = mx.outputs[0]
    my = n("ShaderNodeMix", (-1000, -100), data_type="FLOAT")
    L(at.outputs["Fac"], my.inputs[0]); L(sp.outputs["Y"], my.inputs[2]); L(sp.outputs["X"], my.inputs[3])
    sepanjang = mat("ADD", my.outputs[0], sp.outputs["Z"], (-800, -100))     # ikut lilitan di muka samping palang
    PITCH, PUNTIR = 0.005, 0.006
    s = mat("MULTIPLY", melintang, 1 / PITCH, (-800, 150))
    profil = mat("ABSOLUTE", mat("SINE", mat("MULTIPLY", s, math.pi, (-600, 150)), None, (-450, 150)), None, (-300, 150))
    profil = mat("POWER", profil, 0.45, (-150, 150))                           # helai bulat, alur sempit gelap
    # puntiran: alur miring halus di sepanjang helai (helai tetap terbaca sebagai garis menerus)
    t = mat("ADD", mat("MULTIPLY", sepanjang, 1 / PUNTIR, (-600, -150)), mat("MULTIPLY", s, 0.5, (-600, -300)), (-450, -200))
    puntir = mat("MULTIPLY", mat("ADD", mat("SINE", mat("MULTIPLY", t, 2 * math.pi, (-300, -200)), None, (-150, -200)), 1.0, (0, -200)), 0.5, (150, -200))
    tinggi = mat("MULTIPLY", profil, mat("ADD", mat("MULTIPLY", puntir, 0.2, (300, -200)), 0.8, (450, -200)), (600, 0))
    no = n("ShaderNodeTexNoise", (300, 300)); no.inputs["Scale"].default_value = 60.0; no.inputs["Detail"].default_value = 3.0
    L(tc.outputs["Object"], no.inputs["Vector"])
    rp = n("ShaderNodeValToRGB", (750, 150)); L(tinggi, rp.inputs["Fac"])
    e = rp.color_ramp.elements
    e[0].position, e[0].color = 0.08, (0.24, 0.15, 0.07, 1)         # alur antar helai
    e[1].position, e[1].color = 0.95, (0.72, 0.53, 0.31, 1)         # punggung helai (natural tan ~ sRGB 220/192/151)
    vr = n("ShaderNodeMix", (950, 150), data_type="RGBA", blend_type="MULTIPLY")
    vr.inputs[0].default_value = 0.12
    L(rp.outputs["Color"], vr.inputs[6]); L(no.outputs["Color"], vr.inputs[7])
    L(vr.outputs[2], bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = 0.75
    bs.inputs["Sheen Weight"].default_value = 0.3
    bp = n("ShaderNodeBump", (950, -200)); bp.inputs["Strength"].default_value = 0.8; bp.inputs["Distance"].default_value = 0.0015
    L(tinggi, bp.inputs["Height"]); L(bp.outputs["Normal"], bs.inputs["Normal"])
    L(bs.outputs["BSDF"], out.inputs["Surface"])
    return m


def dudukan_tali(m):
    hasil = []
    for o in bpy.data.objects:
        if not o.name.startswith("Dudukan baji"):
            continue
        o.data.materials.clear(); o.data.materials.append(m)
        o["tali_arah"] = 1.0 if ("kiri" in o.name or "kanan" in o.name) else 0.0
        o["ns_role_part"] = "TALI"
        o["sambungan"] = "anyaman tali melilit palang depan/belakang/samping, pola amplop 4 segitiga"
        hasil.append(o.name)
    return hasil


o = sandaran()
tali = dudukan_tali(mat_tali())
K.note(f"Sandaran solid {2 * X_DALAM * 1000:.0f} x {(Z_ATAS - Z_BAWAH) * 1000:.0f} x {TEBAL * 1000:.0f} mm, lengkung {LENGKUNG * 1000:.0f} mm, "
       f"miring {math.degrees(math.atan(KEMIRINGAN)):.1f}°; dudukan tali: {', '.join(tali)}")
if "lengkapi_dining_chair" not in str(ROOT.get("catatan", "")):
    ROOT["catatan"] = str(ROOT.get("catatan", "")) + (" | 31-10-2026 lengkapi_dining_chair.py: sandaran solid ditambah, "
                                                   "dudukan = tali anyaman (ROLE | TALI) pada 4 baji DWG; rangka tidak diubah.")
if "--simpan" in sys.argv:
    bpy.ops.wm.save_mainfile(compress=True)
    print("[lengkapi] disimpan", bpy.data.filepath)
