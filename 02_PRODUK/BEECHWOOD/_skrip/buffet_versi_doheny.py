# Versi Doheny untuk sesi studio Beechwood Buffet (31-10-2026): kayu interior (WOOD_B) ikut finish kayu Doheny
# (WOOD_A sudah diganti preset latar 'doheny_lifestyle'), dan rotan pintu diganti salah satu anyaman:
#   rapat -> anyaman polos over/under rapat, helai 8 mm (seperti foto buffet awal)
#   cane  -> anyaman cane terbuka 6 arah (sepasang vertikal + sepasang horizontal + 2 diagonal, lubang oktagon),
#            sel 13 mm, warna rotan natural terang (referensi foto lembaran cane)
# Tekstur dibuat dengan numpy (ubin 2 x 2 sel, mulus berulang), disimpan ke ../_tekstur dan di-pack ke file.
# Rotan memakai koordinat Object (x, z) sehingga lubang muka depan & belakang panel selalu segaris.
# Pakai (pada file sesi hasil sinkron_beechwood.py --latar doheny_lifestyle):
#   blender -b 03_PROYEK/<sesi>.blend --python buffet_versi_doheny.py -- --anyaman rapat|cane [--simpan]
import bpy, sys, os
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ANYAMAN = argv[argv.index("--anyaman") + 1]
DIR_TEKSTUR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_tekstur")
FIN_DOHENY = "FIN | Doheny Cherry Alami"

# warna rotan natural (sRGB 0-1) dari foto referensi lembaran cane
C_TERANG = np.array([238, 216, 172]) / 255
C_TENGAH = np.array([216, 180, 124]) / 255
C_GELAP = np.array([148, 106, 58]) / 255

SPEK = {  # sel (m), resolusi ubin, keluarga helai
    "rapat": {"sel": 0.008, "N": 512, "nama": "RTN | Rotan Anyaman Rapat", "lubang": False},
    "cane": {"sel": 0.013, "N": 1024, "nama": "RTN | Rotan Cane Terbuka", "lubang": True},
}


def dekat(x):
    """Jarak bertanda ke bilangan bulat terdekat."""
    return x - np.round(x)


def keluarga(u, v, jenis):
    """Daftar helai: (jarak ke sumbu helai, setengah lebar, koordinat melintang, bias tinggi over/under, id helai)."""
    if jenis == "rapat":
        du, dv = dekat(u - 0.5), dekat(v - 0.5)
        cu, cv = np.cos(np.pi * np.floor(u)), np.cos(np.pi * np.floor(v))
        return [(np.abs(du), 0.44, u, 0.2 * np.cos(np.pi * (v - 0.5)) * cu, np.floor(u) % 2),
                (np.abs(dv), 0.44, v, -0.2 * np.cos(np.pi * (u - 0.5)) * cv, 2 + np.floor(v) % 2)]
    a, wp, wd = 0.11, 0.07, 0.075                  # pasangan helai +-a dari garis sel; diagonal lewat titik tengah tepi sel
    du, dv = dekat(u), dekat(v)
    s1, s2 = u + v, u - v
    return [(np.abs(np.abs(du) - a), wp, u, 0.18 * np.cos(np.pi * v) * np.cos(np.pi * np.round(u)), (np.round(u) * 2 + (du > 0)) % 4),
            (np.abs(np.abs(dv) - a), wp, v, -0.18 * np.cos(np.pi * u) * np.cos(np.pi * np.round(v)), 4 + (np.round(v) * 2 + (dv > 0)) % 4),
            (np.abs(dekat(s1 - 0.5)) / np.sqrt(2), wd, s1, 0.22 + 0.08 * np.sin(np.pi * s2), 8 + np.round(s1 - 0.5) % 4),
            (np.abs(dekat(s2 - 0.5)) / np.sqrt(2), wd, s2, 0.22 - 0.08 * np.sin(np.pi * s1), 12 + np.round(s2 - 0.5) % 4)]


def buat_tekstur(jenis, N, ss=2):
    rng = np.random.default_rng(7)
    M = N * ss
    g = (np.arange(M) + 0.5) / M * 2.0             # ubin = 2 sel (fase over/under berulang tiap 2 sel)
    u, v = np.meshgrid(g, g)
    serat_acak = rng.random(1200)
    tint_acak = 0.9 + 0.16 * rng.random(16)
    h_top = np.full(u.shape, -9.0); p_top = np.zeros(u.shape); f_top = np.ones(u.shape); t_top = np.ones(u.shape)
    for d, w, lintang, bias, sid in keluarga(u, v, jenis):
        p = np.sqrt(np.clip(1 - (d / w) ** 2, 0, 1))
        h = np.where(p > 0, 0.5 * p + bias, -9.0)
        ganti = h > h_top
        # serat memanjang: noise 1D melintang helai (periodik 2 sel)
        idx = (lintang * 300.0) % 600.0
        serat = 1 + 0.16 * (np.interp(idx, np.arange(600), serat_acak[:600]) - 0.5)
        h_top = np.where(ganti, h, h_top); p_top = np.where(ganti, p, p_top)
        f_top = np.where(ganti, serat, f_top); t_top = np.where(ganti, tint_acak[sid.astype(int) % 16], t_top)
    ada = (p_top > 0).astype(float)
    nilai = np.clip((0.3 + 0.7 * p_top ** 0.6) * f_top * t_top, 0, 1.05)
    k1 = np.clip(nilai * 2, 0, 1)[..., None]; k2 = np.clip(nilai * 2 - 1, 0, 1)[..., None]
    warna = C_GELAP + (C_TENGAH - C_GELAP) * k1 + (C_TERANG - C_TENGAH) * k2
    tinggi = np.where(ada > 0, np.clip((h_top + 0.5) / 1.3, 0, 1), 0.0)
    if not SPEK[jenis]["lubang"]:                  # celah anyaman rapat: gelap, tidak tembus
        warna = np.where(ada[..., None] > 0, warna, C_GELAP * 0.35); ada = np.ones_like(ada)
    # supersample -> rata-rata ss x ss (anti-alias)
    turun = lambda x: x.reshape(N, ss, N, ss, *x.shape[2:]).mean(axis=(1, 3))
    a = turun(ada)
    w = turun(warna * ada[..., None]) / np.maximum(a[..., None], 1e-6)
    return np.dstack([w, a]), turun(tinggi)


def simpan_gambar(nama, rgba, non_color=False):
    N = rgba.shape[0]
    img = bpy.data.images.get(nama) or bpy.data.images.new(nama, N, N, alpha=True)
    if img.size[0] != N:
        img.scale(N, N)
    img.pixels.foreach_set(rgba.astype(np.float32).ravel())
    os.makedirs(DIR_TEKSTUR, exist_ok=True)
    img.filepath_raw = os.path.join(DIR_TEKSTUR, nama + ".png"); img.file_format = "PNG"
    img.save()
    img.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
    img.pack()
    return img


def material_rotan(jenis):
    sp = SPEK[jenis]
    rgba, tinggi = buat_tekstur(jenis, sp["N"])
    img = simpan_gambar(f"rotan_{jenis}_warna", rgba)
    hgt = simpan_gambar(f"rotan_{jenis}_tinggi", np.dstack([tinggi, tinggi, tinggi, np.ones_like(tinggi)]), True)
    m = bpy.data.materials.get(sp["nama"]) or bpy.data.materials.new(sp["nama"])
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    L = nt.links.new
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (900, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (600, 0)
    tc = nt.nodes.new("ShaderNodeTexCoord"); tc.location = (-1200, 0)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); sep.location = (-1000, 0)
    gab = nt.nodes.new("ShaderNodeCombineXYZ"); gab.location = (-800, 0)
    mp = nt.nodes.new("ShaderNodeMapping"); mp.location = (-600, 0)
    mp.inputs["Scale"].default_value = (1 / (2 * sp["sel"]), 1 / (2 * sp["sel"]), 1)
    L(tc.outputs["Object"], sep.inputs[0]); L(sep.outputs["X"], gab.inputs["X"]); L(sep.outputs["Z"], gab.inputs["Y"])
    L(gab.outputs[0], mp.inputs["Vector"])
    ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = img; ti.location = (-300, 150)
    th = nt.nodes.new("ShaderNodeTexImage"); th.image = hgt; th.location = (-300, -250)
    for t in (ti, th):
        t.extension = "REPEAT"; L(mp.outputs["Vector"], t.inputs["Vector"])
    L(ti.outputs["Color"], bsdf.inputs["Base Color"])
    if sp["lubang"]:
        L(ti.outputs["Alpha"], bsdf.inputs["Alpha"])
    bsdf.inputs["Roughness"].default_value = 0.5
    b = nt.nodes.new("ShaderNodeBump"); b.location = (300, -250)
    b.inputs["Strength"].default_value = 0.7; b.inputs["Distance"].default_value = 0.0012
    L(th.outputs["Color"], b.inputs["Height"]); L(b.outputs["Normal"], bsdf.inputs["Normal"])
    L(bsdf.outputs["BSDF"], out.inputs["Surface"])
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = "DITHERED"
    m["ns_role"] = "RATTAN"
    m["catatan"] = f"anyaman {jenis}, sel {sp['sel'] * 1000:.0f} mm, buffet_versi_doheny.py 2026-10-31"
    return m


fin = bpy.data.materials[FIN_DOHENY]
rotan = material_rotan(ANYAMAN)
ganti = {"ROLE | WOOD_B": fin, "ROLE | RATTAN": rotan}
hit = {k: 0 for k in ganti}
miring = []
for o in bpy.data.objects:
    for sl in getattr(o, "material_slots", []):
        if sl.material and sl.material.name in ganti:
            hit[sl.material.name] += 1
            if sl.material.name == "ROLE | RATTAN" and any(abs(r) > 1e-4 for r in o.matrix_world.to_euler()):
                miring.append(o.name)
            sl.material = ganti[sl.material.name]
root = next((o for o in bpy.data.objects if o.get("ns_product_root")), None)
# UV buffet (konstruksi_util.uv_meter) membawa serat di V; preset Doheny tidak menetapkan 'serat' -> add-on membaca root
fin["ns_grain"] = "V"
arah = fin.node_tree.nodes.get("Arah serat")
if arah is not None:
    arah.inputs["Rotation"].default_value[2] = np.radians(90)
if root is not None:
    root["ns_grain"] = "V"
    root["warna"] = f"finish & latar Doheny (cherry alami, handle kuningan) + rotan {ANYAMAN}"
print("@@", {"slot_diganti": hit, "rotan_miring": miring, "grain_root": root.get("ns_grain") if root else None,
             "grain_fin": fin.get("ns_grain")})
if "--simpan" in argv:
    bpy.ops.wm.save_mainfile(compress=True)
    print("@@ disimpan", bpy.data.filepath)
