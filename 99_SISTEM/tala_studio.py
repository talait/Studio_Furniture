# Tala catalogue studio (31-10-2026): scene "TALA | Katalog" bergaya foto katalog (front view lurus, dinding greige,
# lantai microcement terang, cahaya lembut kiri -> kanan + sapuan jendela diagonal tipis).
#
# Scene ini terpisah dari scene studio add-on (nakas_studio_tools): koleksi produk hasil impor add-on di-link ke
# sini, sehingga kamera/latar/lampu add-on tetap utuh. Semua objek studio ada di koleksi STUDIO_TALA dan diatur
# dari ukuran produk (W, D, H) yang disimpan di empty STUDIO_CTRL; ubah properti STUDIO_CTRL lalu fit_studio()
# untuk menyetel ulang (fill, wall_gap, cove_r, exposure, energi lampu, ...).
#
# Alur (sama dengan sinkron_beechwood.py: template studio + impor add-on):
#   template (sekali):  blender -b 01_STUDIO/Studio_Nakas.blend --python 99_SISTEM/tala_studio.py -- --template
#   produk (per item):  blender -b --python 99_SISTEM/tala_studio.py -- --impor "02_PRODUK/BEECHWOOD/BEECHWOOD BUFFET.blend" [B.blend ...]
#                         -> 03_PROYEK/TALA/tala_<nama>.blend   (opsi: --keluar <folder>, --preview, --tahap 2|4|7)
#   file terbuka:       blender -b <file>.blend --python 99_SISTEM/tala_studio.py -- --fit [--simpan] [--preview <png>]
# Di Blender (UI): sidebar 3D View > Tala > "Fit Studio" (modul ikut tersimpan di file sebagai teks tala_studio.py).
#
# Geometri produk tidak diubah, kecuali scale yang belum di-apply (permintaan normalisasi) dan posisi root
# (alas di Z = 0, tengah X/Y). Material produk diganti versi TALA per peran (WOOD_A/WOOD_B -> oak, RATTAN -> cane,
# HANDLE -> kuningan); material asli dicatat di objek (tala_material_asli).
import bpy, bmesh, math, os, sys, json
from mathutils import Vector, Matrix

SCENE = "TALA | Katalog"
COLL = "STUDIO_TALA"
CTRL = "STUDIO_CTRL"
TEXT = "tala_studio.py"
TEMPLATE = "01_STUDIO/tala_studio_template.blend"
TEKSTUR = "02_PRODUK/_LATAR/tekstur_tala"          # rotan_cane_warna.png / rotan_cane_tinggi.png
RES = (2000, 1200)

# Nilai bawaan STUDIO_CTRL (bisa diubah per file; fit_studio membaca dari STUDIO_CTRL)
DEFAULT = {
    "fill": 0.85,            # lebar produk / lebar frame
    "fill_tinggi": 0.80,     # batas tinggi produk / tinggi frame (produk tinggi)
    "turun": 0.04,           # produk di bawah tengah frame (x tinggi frame)
    "cam_h_faktor": 1.05,    # tinggi kamera = H x faktor
    "lensa": 85.0, "lensa_lebar": 100.0, "rasio_lebar": 2.6,   # W/H >= rasio_lebar -> lensa 100 mm
    "wall_gap": 1.2, "cove_r": 0.3,
    "key_daya": 120.0,       # W per m^2 jarak (energi = daya x jarak^2)
    "fill_rasio": 0.28, "sweep_daya": 450.0,
    "wb_k": 5600.0,          # white balance: lampu 5000-5500 K -> nuansa hangat ~5200 K, tidak oranye
    "key_az": 40.0, "key_el": 35.0, "fill_az": 40.0, "fill_el": 20.0,
    "dunia": 0.4, "exposure": -2.4,     # dinding terbaca ~#A69D93 di AgX Medium Low Contrast
    "backer": 1,             # panel gelap di belakang anyaman rotan
    # produk gantung dinding (cermin): rapat dinding, kamera lurus di tengah produk, tanpa lantai di frame
    "gantung_tinggi": 1.5,   # tinggi tengah produk dari lantai (m), seperti add-on WALL_HUNG_HEIGHT
    "gantung_fill": 0.62,    # lebar produk / lebar frame (dinding lega di sekeliling)
    "gantung_celah": 0.01,   # jarak punggung produk ke dinding (m)
    "pantulan_kuat": 7.0,    # emisi dinding pantulan di belakang kamera (hanya terlihat di cermin)
    "gantung_ev": -0.5,    # dinding rapat produk lebih dekat ke key -> exposure dikurangi agar tetap ~#A69D93
}

KATA_KAYU = ("wood", "kayu", "walnut", "oak", "teak", "jati", "veneer", "fin |")   # sama dengan add-on WOOD_WORDS
KATA_CERMIN = ("cermin", "mirror", "kaca", "glass")
CERMIN = {"perak": (0.86, 0.87, 0.87), "kaca": (0.92, 0.96, 0.94), "ior": 1.52}       # = add-on finish_cermin

WARNA = {  # sRGB hex
    "dinding": "A69D93", "lantai": "CBC8C3", "oak": "C99A68", "rotan": "D9B887",
    "backer": "3A2E25", "kuningan": "C8A04A",
}


def lin(hexs):
    c = [int(hexs[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)


def root_dir():
    for p in (globals().get("__file__"),):
        if p and os.path.isfile(p):
            return os.path.dirname(os.path.dirname(os.path.abspath(p)))
    t = bpy.data.texts.get(TEXT)
    c = bpy.data.objects.get(CTRL)
    return c.get("root_dir") if c else None


# ------------------------------------------------------------------ scene, koleksi, ctrl
def tala_scene(src=None):
    sc = bpy.data.scenes.get(SCENE) or bpy.data.scenes.new(SCENE)
    sc.unit_settings.system = "METRIC"; sc.unit_settings.scale_length = 1.0; sc.unit_settings.length_unit = "METERS"
    sc.render.engine = "CYCLES"
    if src is not None and src != sc:
        try:
            sc.cycles.device = src.cycles.device
        except Exception:
            pass
    sc.render.resolution_x, sc.render.resolution_y = RES
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.cycles.samples = 256
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    sc.cycles.sample_clamp_indirect = 10.0
    sc.render.use_compositing = False          # tanpa vignette / bloom / glare
    vs = sc.view_settings
    vs.view_transform = "AgX"
    for look in ("Medium Low Contrast", "AgX - Medium Low Contrast"):
        try:
            vs.look = look; break
        except TypeError:
            continue
    if COLL not in sc.collection.children:
        coll = bpy.data.collections.get(COLL) or bpy.data.collections.new(COLL)
        sc.collection.children.link(coll)
    return sc


def koleksi():
    return bpy.data.collections[COLL]


def ctrl_obj():
    c = bpy.data.objects.get(CTRL)
    if c is None:
        c = bpy.data.objects.new(CTRL, None)
        c.empty_display_type = "PLAIN_AXES"; c.empty_display_size = 0.3
        koleksi().objects.link(c)
    for k, v in DEFAULT.items():
        if k not in c:
            c[k] = v
    r = root_dir()
    if r:
        c["root_dir"] = r
    return c


def obj_baru(nama, data, coll=None):
    o = bpy.data.objects.get(nama)
    if o is not None:
        old = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if old is not None and getattr(old, "users", 1) == 0:
            for blocks in (bpy.data.meshes, bpy.data.lights, bpy.data.cameras):
                if old.name in blocks and blocks[old.name] == old:
                    blocks.remove(old); break
    o = bpy.data.objects.new(nama, data)
    (coll or koleksi()).objects.link(o)
    return o


# ------------------------------------------------------------------ produk
def objek_produk(target):
    if isinstance(target, bpy.types.Collection):
        return list(target.all_objects)
    return [target] + list(target.children_recursive)


def koleksi_produk(target):
    if isinstance(target, bpy.types.Collection):
        return target
    return target.users_collection[0]


def batas(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for o in objs:
        if o.type not in {"MESH", "CURVE", "SURFACE", "META", "FONT"} or o.hide_render:
            continue
        ev = o.evaluated_get(dg)
        for c in ev.bound_box:
            p = ev.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, p)); hi = Vector(map(max, hi, p))
    if lo.x > hi.x:
        raise ValueError("Produk tidak punya mesh yang dirender")
    return lo, hi


def peran_produk(objs):
    """Himpunan peran material produk (dari material asli bila produk pernah di-fit)."""
    hasil = set()
    for o in objs:
        if o.type != "MESH":
            continue
        asli = json.loads(o["tala_material_asli"]) if "tala_material_asli" in o else []
        for i, s in enumerate(o.material_slots):
            m = (bpy.data.materials.get(asli[i]) if i < len(asli) and asli[i] else None) or s.material
            p = peran(m)
            if p:
                hasil.add(p)
    return hasil


def normalisasi(target, c):
    """Apply scale (objek tanpa anak, mesh satu pengguna), alas Z = 0, tengah X/Y; simpan W, D, H di STUDIO_CTRL.
    Produk gantung (cermin tipis / root ns_gantung): cermin yang tergeletak datar diberdirikan (kaca menghadap
    kamera, -Y), punggung rapat dinding, tengah produk di gantung_tinggi."""
    objs = objek_produk(target)
    himpunan = set(objs)
    pindah = [o for o in objs if o.parent not in himpunan]
    diterapkan = []
    for o in objs:
        s = o.scale
        if o.type == "MESH" and not o.children and o.data.users == 1 and any(abs(v - 1) > 1e-6 for v in s):
            o.data.transform(Matrix.Diagonal((*s, 1.0)))
            o.scale = (1, 1, 1); diterapkan.append(o.name)
    # root add-on: kembalikan ke putaran dasar (angle samping add-on memutar root)
    for o in objs:
        if o.get("ns_product_root") and "ns_base_yaw" in o:
            o.rotation_euler.z = float(o["ns_base_yaw"])
    bpy.context.view_layer.update()
    lo, hi = batas(objs)
    ada_cermin = "CERMIN" in peran_produk(objs)
    root = next((o for o in objs if o.get("ns_product_root")), None)
    diberdirikan = False
    ukuran = hi - lo
    if ada_cermin and ukuran.z < 0.06 and min(ukuran.x, ukuran.y) > 0.2:
        # tergeletak, kaca menghadap atas: putar +90° di X -> muka atas menghadap -Y (kamera)
        pusat = (lo + hi) / 2
        M = Matrix.Translation(pusat) @ Matrix.Rotation(math.radians(90), 4, "X") @ Matrix.Translation(-pusat)
        for o in pindah:
            o.matrix_world = M @ o.matrix_world
        bpy.context.view_layer.update()
        lo, hi = batas(objs); ukuran = hi - lo
        diberdirikan = True
    gantung = (root is not None and root.get("ns_gantung") is not None) or (ada_cermin and ukuran.y < 0.08)
    c["gantung"] = int(gantung)
    z_alas = float(c["gantung_tinggi"]) - ukuran.z / 2 if gantung else 0.0
    geser = Vector((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, z_alas - lo.z))
    for o in pindah:
        o.location += geser
    bpy.context.view_layer.update()
    lo, hi = batas(objs)
    c["W"], c["D"], c["H"] = hi.x - lo.x, hi.y - lo.y, hi.z - lo.z
    c["z_alas"] = lo.z
    return {"scale_diterapkan": diterapkan, "geser_m": [round(v, 4) for v in geser],
            "WDH_m": [round(c["W"], 4), round(c["D"], 4), round(c["H"], 4)],
            "gantung": bool(gantung), "diberdirikan": diberdirikan, "z_alas": round(lo.z, 4)}


# ------------------------------------------------------------------ node helper
def nodes_baru(mat):
    mat.use_nodes = True
    nt = mat.node_tree; nt.nodes.clear()
    return nt


def sok(node, nama, tipe=None, keluar=False):
    for s in (node.outputs if keluar else node.inputs):
        if s.name == nama and (tipe is None or s.type == tipe) and s.enabled:
            return s
    raise KeyError(nama)


def mix_warna(nt, fac, a, b, loc):
    m = nt.nodes.new("ShaderNodeMix"); m.data_type = "RGBA"; m.location = loc
    m.inputs[0].default_value = fac if isinstance(fac, float) else 0.5
    if not isinstance(fac, float):
        nt.links.new(fac, m.inputs[0])
    for nama, v in (("A", a), ("B", b)):
        s = sok(m, nama, "RGBA")
        if isinstance(v, tuple):
            s.default_value = v
        else:
            nt.links.new(v, s)
    return sok(m, "Result", "RGBA", keluar=True)


def bump(nt, tinggi, kuat, jarak, loc):
    b = nt.nodes.new("ShaderNodeBump"); b.location = loc
    b.inputs["Strength"].default_value = kuat; b.inputs["Distance"].default_value = jarak
    nt.links.new(tinggi, b.inputs["Height"])
    return b.outputs["Normal"]


def material(nama):
    m = bpy.data.materials.get(nama) or bpy.data.materials.new(nama)
    m["tala"] = True
    return m


# ------------------------------------------------------------------ backdrop
def mat_backdrop(c):
    m = material("TALA | Backdrop dinding + lantai")
    nt = nodes_baru(m); L = nt.links.new
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (1200, 0)
    geo = nt.nodes.new("ShaderNodeNewGeometry"); geo.location = (-1200, 0)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); sep.location = (-1000, 300); L(geo.outputs["Position"], sep.inputs[0])
    # lantai microcement: noise skala 3 dicampur 6 % ke warna (kontras sangat rendah), bump 0.03
    nl = nt.nodes.new("ShaderNodeTexNoise"); nl.location = (-800, -200)
    nl.inputs["Scale"].default_value = 3.0; nl.inputs["Detail"].default_value = 2.0; nl.inputs["Roughness"].default_value = 0.4
    L(geo.outputs["Position"], nl.inputs["Vector"])
    fl = nt.nodes.new("ShaderNodeBsdfPrincipled"); fl.location = (300, -300)
    L(mix_warna(nt, 0.06, lin(WARNA["lantai"]), nl.outputs["Fac"], (0, -200)), fl.inputs["Base Color"])
    fl.inputs["Roughness"].default_value = 0.55
    L(bump(nt, nl.outputs["Fac"], 0.03, 0.01, (0, -450)), fl.inputs["Normal"])
    # dinding plester matte: bump noise halus 0.02
    nw = nt.nodes.new("ShaderNodeTexNoise"); nw.location = (-800, 300)
    nw.inputs["Scale"].default_value = 40.0; nw.inputs["Detail"].default_value = 6.0
    L(geo.outputs["Position"], nw.inputs["Vector"])
    wl = nt.nodes.new("ShaderNodeBsdfPrincipled"); wl.location = (300, 300)
    wl.inputs["Base Color"].default_value = lin(WARNA["dinding"]); wl.inputs["Roughness"].default_value = 0.9
    L(bump(nt, nw.outputs["Fac"], 0.02, 0.005, (0, 250)), wl.inputs["Normal"])
    # transisi lembut sepanjang cove: Z 0 -> cove_r (smoothstep)
    mr = nt.nodes.new("ShaderNodeMapRange"); mr.location = (-600, 600); mr.interpolation_type = "SMOOTHSTEP"
    mr.inputs["From Min"].default_value = 0.0; mr.inputs["From Max"].default_value = float(c["cove_r"])
    L(sep.outputs["Z"], mr.inputs["Value"])
    mx = nt.nodes.new("ShaderNodeMixShader"); mx.location = (800, 0)
    L(mr.outputs["Result"], mx.inputs[0]); L(fl.outputs["BSDF"], mx.inputs[1]); L(wl.outputs["BSDF"], mx.inputs[2])
    L(mx.outputs["Shader"], out.inputs["Surface"])
    return m


def bangun_backdrop(c, cam_y):
    """Satu mesh mulus: lantai (Z = 0) -> cove radius cove_r -> dinding di Y = D/2 + wall_gap."""
    r, yw = float(c["cove_r"]), float(c["wall_y"])
    y0 = min(-10.0, cam_y - 3.0)
    h_dinding = max(4.0, float(c["cam_h"]) + 3.0)
    prof = [(y0, 0.0)]
    for i in range(13):
        a = math.radians(-90 + 90 * i / 12)
        prof.append((yw - r + r * math.cos(a), r + r * math.sin(a)))
    prof.append((yw, h_dinding))
    me = bpy.data.meshes.new("TALA_backdrop")
    bm = bmesh.new()
    kiri = [bm.verts.new((-10.0, y, z)) for y, z in prof]
    kanan = [bm.verts.new((10.0, y, z)) for y, z in prof]
    for i in range(len(prof) - 1):
        f = bm.faces.new((kiri[i], kanan[i], kanan[i + 1], kiri[i + 1]))
        f.smooth = True
    bm.normal_update()
    for f in bm.faces:                      # normal menghadap kamera (-Y) / atas
        if f.normal.z < -1e-3 or f.normal.y > 1e-3:
            f.normal_flip()
    bm.to_mesh(me); bm.free()
    o = obj_baru("TALA_backdrop", me)
    me.materials.append(mat_backdrop(c))
    o["tala_studio"] = True
    return o


# ------------------------------------------------------------------ kamera
def bangun_kamera(c, sc):
    W, D, H = float(c["W"]), float(c["D"]), float(c["H"])
    gantung, z0 = bool(c.get("gantung", 0)), float(c.get("z_alas", 0.0))
    lensa = float(c["lensa_lebar"]) if W / max(H, 1e-3) >= float(c["rasio_lebar"]) else float(c["lensa"])
    aspek = RES[1] / RES[0]
    if gantung:
        # cermin/panel dinding: kamera lurus di tengah produk (tanpa shift), dinding lega di sekeliling,
        # lantai di luar frame (horizon tidak berlaku)
        lebar_frame = max(W / float(c["gantung_fill"]), H / (0.7 * aspek))
        cam_h = z_tengah = z0 + H / 2
    else:
        # lebar frame di bidang muka depan produk: lebar mengisi 'fill', tinggi tidak melewati 'fill_tinggi'
        lebar_frame = max(W / float(c["fill"]), H / (float(c["fill_tinggi"]) * aspek))
        cam_h = H * float(c["cam_h_faktor"])
        z_tengah = H / 2 + float(c["turun"]) * lebar_frame * aspek
    jarak = lebar_frame * lensa / 36.0
    cd = bpy.data.cameras.get("TALA_CAM") or bpy.data.cameras.new("TALA_CAM")
    cd.lens, cd.sensor_width, cd.sensor_fit = lensa, 36.0, "HORIZONTAL"
    cd.shift_x, cd.shift_y = 0.0, (z_tengah - cam_h) / lebar_frame
    cd.clip_start, cd.clip_end = 0.05, 200.0
    cd.dof.use_dof = False
    cam = bpy.data.objects.get("TALA_CAM")
    if cam is None:
        cam = bpy.data.objects.new("TALA_CAM", cd); koleksi().objects.link(cam)
    cam.data = cd
    cam.location = (0.0, -D / 2 - jarak, cam_h)
    cam.rotation_euler = (math.radians(90), 0.0, 0.0)
    cam["tala_studio"] = True
    sc.camera = cam
    c["lensa_aktif"], c["jarak_kamera"], c["cam_h"], c["shift_y"] = lensa, jarak, cam_h, cd.shift_y
    c["cam_y"] = cam.location.y
    c["wall_y"] = D / 2 + float(c["gantung_celah"] if gantung else c["wall_gap"])
    return cam


def bangun_pantulan(c):
    """Produk gantung: bidang dinding di belakang kamera, hanya terlihat di pantulan (glossy), supaya cermin
    memantulkan ruangan greige yang lembut (terang kiri -> redup kanan seperti cahaya key), bukan dunia kosong."""
    nama = "TALA_pantulan"
    o = bpy.data.objects.get(nama)
    if not c.get("gantung"):
        if o is not None:
            me = o.data; bpy.data.objects.remove(o, do_unlink=True); bpy.data.meshes.remove(me)
        return None
    me = bpy.data.meshes.new(nama)
    s, t = 8.0, 4.0
    me.from_pydata([(-s, 0, -t), (s, 0, -t), (s, 0, t), (-s, 0, t)], [], [(0, 3, 2, 1)])   # normal +Y (ke cermin)
    o = obj_baru(nama, me)
    o.location = (0.0, float(c["cam_y"]) - 0.6, float(c["cam_h"]))
    m = material("TALA | Dinding pantulan")
    nt = nodes_baru(m); L = nt.links.new
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (600, 0)
    em = nt.nodes.new("ShaderNodeEmission"); em.location = (300, 0)
    tc = nt.nodes.new("ShaderNodeTexCoord"); tc.location = (-600, 0)
    sp = nt.nodes.new("ShaderNodeSeparateXYZ"); sp.location = (-400, 0); L(tc.outputs["Object"], sp.inputs[0])
    mr = nt.nodes.new("ShaderNodeMapRange"); mr.location = (-200, 0); mr.interpolation_type = "SMOOTHSTEP"
    # pantulan tidak membalik X dunia: x < 0 = sisi kiri frame (sisi key) -> lebih terang
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = -3.0, 3.0
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 1.15, 0.75
    L(sp.outputs["X"], mr.inputs["Value"])
    kuat = nt.nodes.new("ShaderNodeMath"); kuat.operation = "MULTIPLY"; kuat.location = (50, -100)
    kuat.inputs[1].default_value = float(c["pantulan_kuat"])
    L(mr.outputs["Result"], kuat.inputs[0]); L(kuat.outputs[0], em.inputs["Strength"])
    em.inputs["Color"].default_value = lin(WARNA["dinding"])
    L(em.outputs[0], out.inputs["Surface"])
    me.materials.append(m)
    o.visible_camera = o.visible_diffuse = o.visible_shadow = o.visible_transmission = o.visible_volume_scatter = False
    o.visible_glossy = True
    o["tala_studio"] = True
    return o


# ------------------------------------------------------------------ lampu
def arah(az_deg, el_deg):
    """az > 0 = kanan kamera, < 0 = kiri; kamera melihat ke +Y (dari -Y)."""
    az, el = math.radians(az_deg), math.radians(el_deg)
    return Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))


def bidik(o, target):
    o.rotation_euler = (Vector(target) - o.location).to_track_quat("-Z", "Y").to_euler()


def lampu(nama, tipe, kelvin):
    d = bpy.data.lights.get(nama)
    if d is None or d.type != tipe:
        d = bpy.data.lights.new(nama, tipe)
    d.use_temperature = True; d.temperature = kelvin
    d.color = (1, 1, 1)
    o = bpy.data.objects.get(nama)
    if o is None:
        o = bpy.data.objects.new(nama, d); koleksi().objects.link(o)
    o.data = d
    o.visible_camera = False
    o["tala_studio"] = True
    return o


def blok_jendela(nama, lebar_celah, panjang_celah, ukuran):
    """Bidang penghalang dengan satu celah (gobo jendela) di XY lokal, celah sepanjang Y."""
    me = bpy.data.meshes.get(nama) or bpy.data.meshes.new(nama)
    bm = bmesh.new()
    s, w, l = ukuran / 2, lebar_celah / 2, panjang_celah / 2
    for x0, x1, y0, y1 in ((-s, -w, -s, s), (w, s, -s, s), (-w, w, l, s), (-w, w, -s, -l)):
        vs = [bm.verts.new((x, y, 0)) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
        bm.faces.new(vs)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.get(nama) or bpy.data.objects.new(nama, me)
    if nama not in koleksi().objects:
        koleksi().objects.link(o)
    o.data = me
    m = material("TALA | Gobo hitam")
    nt = nodes_baru(m)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); bs = nt.nodes.new("ShaderNodeBsdfDiffuse")
    bs.inputs["Color"].default_value = (0, 0, 0, 1); nt.links.new(bs.outputs[0], out.inputs[0])
    me.materials.clear(); me.materials.append(m)
    o.visible_camera = o.visible_glossy = o.visible_diffuse = o.visible_transmission = False
    o["tala_studio"] = True
    return o


def bangun_lampu(c, sc):
    W, D, H = float(c["W"]), float(c["D"]), float(c["H"])
    z0 = float(c.get("z_alas", 0.0))                 # 0 untuk produk berdiri; > 0 untuk produk gantung
    T = Vector((0, 0, z0 + H * 0.5))
    skala = max(1.0, max(W, H) / 1.8)
    jarak = max(2.5, 1.5 * max(W, H))
    key = lampu("TALA_key", "AREA", 5000)
    key.data.shape = "RECTANGLE"; key.data.size, key.data.size_y = 3.0 * skala, 2.0 * skala
    key.location = T + arah(-float(c["key_az"]), float(c["key_el"])) * jarak; bidik(key, T)
    key.data.energy = float(c["key_daya"]) * jarak ** 2
    fil = lampu("TALA_fill", "AREA", 5500)
    fil.data.shape = "SQUARE"; fil.data.size = 2.0 * skala
    fil.location = T + arah(float(c["fill_az"]), float(c["fill_el"])) * jarak; bidik(fil, T)
    fil.data.energy = key.data.energy * float(c["fill_rasio"])
    # sapuan jendela: spot kanan-atas + gobo bercelah miring -> pita cahaya diagonal di kanan produk & dinding
    tgt = Vector((0.3 * W, min(D / 2 + 0.15, float(c["wall_y"]) - 0.002), z0 + 0.5 * H))
    sw = lampu("TALA_sweep", "SPOT", 5200)
    jsw = jarak * 1.3
    sw.location = tgt + arah(55, 42) * jsw; bidik(sw, tgt)
    sw.data.spot_size, sw.data.spot_blend = math.radians(45), 1.0
    sw.data.shadow_soft_size = 0.03
    sw.data.energy = float(c["sweep_daya"]) * jsw ** 2
    gobo = blok_jendela("TALA_sweep_gobo", 0.045 * skala, 1.2, 1.6)
    maju = (tgt - sw.location).normalized()
    gobo.location = sw.location + maju * 0.6
    gobo.rotation_euler = (maju.to_track_quat("Z", "Y") @ Matrix.Rotation(math.radians(35), 4, "Z").to_quaternion()).to_euler()
    # dunia netral rendah, hanya isi
    w = bpy.data.worlds.get("TALA | Dunia") or bpy.data.worlds.new("TALA | Dunia")
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.5, 0.5, 0.5, 1); bg.inputs["Strength"].default_value = float(c["dunia"])
    sc.world = w
    c["key_jarak"] = jarak


# ------------------------------------------------------------------ material produk
def peran(mat):
    if mat is None:
        return None
    r = mat.get("ns_role") or mat.get("tala_role")
    if r:
        return str(r)
    for pre, rr in (("ROLE | ", None), ("HW | ", "HANDLE")):
        if mat.name.startswith(pre):
            return rr or mat.name[len(pre):].split(".")[0]
    nama = mat.name.lower()                            # file mentah tanpa peran: tebak dari nama material
    if any(k in nama for k in KATA_CERMIN):
        return "CERMIN"
    if any(k in nama for k in KATA_KAYU):
        return "WOOD_A"
    return None


def mat_oak(serat):
    m = material(f"TALA | Oak natural ({serat})"); m["tala_role"] = "WOOD_A"
    nt = nodes_baru(m); L = nt.links.new
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (900, 0)
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled"); bs.location = (600, 0)
    uv = nt.nodes.new("ShaderNodeUVMap"); uv.location = (-1300, 0)          # UV aktif (UV meter pada produk studio)
    mp = nt.nodes.new("ShaderNodeMapping"); mp.location = (-1100, 0)
    mp.inputs["Scale"].default_value = (1.0, 0.08, 1.0) if serat == "V" else (0.08, 1.0, 1.0)
    L(uv.outputs["UV"], mp.inputs["Vector"])
    wv = nt.nodes.new("ShaderNodeTexWave"); wv.location = (-850, 100)
    wv.wave_type = "BANDS"; wv.bands_direction = "X" if serat == "V" else "Y"
    wv.inputs["Scale"].default_value = 60.0; wv.inputs["Distortion"].default_value = 5.0
    wv.inputs["Detail"].default_value = 3.0; wv.inputs["Detail Scale"].default_value = 1.5
    L(mp.outputs["Vector"], wv.inputs["Vector"])
    no = nt.nodes.new("ShaderNodeTexNoise"); no.location = (-850, -200)
    no.inputs["Scale"].default_value = 20.0; no.inputs["Detail"].default_value = 5.0
    L(mp.outputs["Vector"], no.inputs["Vector"])
    f = nt.nodes.new("ShaderNodeMath"); f.operation = "MULTIPLY"; f.location = (-600, 0)
    L(wv.outputs["Fac"], f.inputs[0]); L(no.outputs["Fac"], f.inputs[1])
    rp = nt.nodes.new("ShaderNodeValToRGB"); rp.location = (-350, 100)
    base = lin(WARNA["oak"])
    rp.color_ramp.elements[0].position, rp.color_ramp.elements[0].color = 0.05, tuple(min(1, v * 1.06) for v in base[:3]) + (1,)
    rp.color_ramp.elements[1].position, rp.color_ramp.elements[1].color = 0.70, tuple(v * 0.58 for v in base[:3]) + (1,)
    L(f.outputs[0], rp.inputs["Fac"]); L(rp.outputs["Color"], bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = 0.45
    bs.inputs["Coat Weight"].default_value = 0.1; bs.inputs["Coat Roughness"].default_value = 0.25
    L(bump(nt, f.outputs[0], 0.12, 0.0004, (300, -300)), bs.inputs["Normal"])
    L(bs.outputs["BSDF"], out.inputs["Surface"])
    return m


def gambar(nama_file, non_color):
    path = os.path.join(ctrl_obj().get("root_dir", ""), TEKSTUR, nama_file)
    img = bpy.data.images.get(nama_file)
    if img is None:
        img = bpy.data.images.load(path)
        img.pack()
    img.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
    return img


def mat_rotan(sumbu):
    """Anyaman cane bermasker alpha; koordinat Object pada dua sumbu panel (sumbu = 'XZ', 'XY', 'YZ')."""
    m = material(f"TALA | Rotan cane ({sumbu})"); m["tala_role"] = "RATTAN"
    nt = nodes_baru(m); L = nt.links.new
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (1000, 0)
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled"); bs.location = (700, 0)
    tc = nt.nodes.new("ShaderNodeTexCoord"); tc.location = (-1300, 0)
    sp = nt.nodes.new("ShaderNodeSeparateXYZ"); sp.location = (-1100, 0)
    cb = nt.nodes.new("ShaderNodeCombineXYZ"); cb.location = (-900, 0)
    L(tc.outputs["Object"], sp.inputs[0])
    L(sp.outputs[sumbu[0]], cb.inputs["X"]); L(sp.outputs[sumbu[1]], cb.inputs["Y"])
    mp = nt.nodes.new("ShaderNodeMapping"); mp.location = (-700, 0)
    mp.inputs["Scale"].default_value = (1 / 0.026, 1 / 0.026, 1)       # ubin 2 sel x 13 mm
    L(cb.outputs[0], mp.inputs["Vector"])
    tw = nt.nodes.new("ShaderNodeTexImage"); tw.image = gambar("rotan_cane_warna.png", False); tw.location = (-400, 200)
    th = nt.nodes.new("ShaderNodeTexImage"); th.image = gambar("rotan_cane_tinggi.png", True); th.location = (-400, -250)
    for t in (tw, th):
        L(mp.outputs["Vector"], t.inputs["Vector"])
    bw = nt.nodes.new("ShaderNodeRGBToBW"); bw.location = (-100, 250); L(tw.outputs["Color"], bw.inputs[0])
    rp = nt.nodes.new("ShaderNodeValToRGB"); rp.location = (150, 250)
    c0 = lin(WARNA["rotan"])
    rp.color_ramp.elements[0].position, rp.color_ramp.elements[0].color = 0.15, tuple(v * 0.45 for v in c0[:3]) + (1,)
    rp.color_ramp.elements[1].position, rp.color_ramp.elements[1].color = 0.62, c0
    L(bw.outputs[0], rp.inputs["Fac"]); L(rp.outputs["Color"], bs.inputs["Base Color"])
    L(tw.outputs["Alpha"], bs.inputs["Alpha"])
    bs.inputs["Roughness"].default_value = 0.5
    bs.inputs["Sheen Weight"].default_value = 0.2
    L(bump(nt, th.outputs["Color"], 0.7, 0.0012, (400, -250)), bs.inputs["Normal"])
    L(bs.outputs["BSDF"], out.inputs["Surface"])
    m.surface_render_method = "DITHERED"
    return m


def mat_sederhana(nama, peran_, warna, kasar, metal=0.0):
    m = material(nama); m["tala_role"] = peran_
    nt = nodes_baru(m)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (400, 0)
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bs.inputs["Base Color"].default_value = lin(warna); bs.inputs["Roughness"].default_value = kasar
    bs.inputs["Metallic"].default_value = metal
    nt.links.new(bs.outputs["BSDF"], out.inputs["Surface"])
    return m


def mat_cermin():
    """Cermin perak di balik kaca: logam perak + coat ber-IOR kaca sedikit hijau (= add-on finish_cermin)."""
    m = material("TALA | Cermin kaca"); m["tala_role"] = "CERMIN"
    nt = nodes_baru(m)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (400, 0)
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bs.inputs["Base Color"].default_value = (*CERMIN["perak"], 1)
    bs.inputs["Metallic"].default_value = 1.0; bs.inputs["Roughness"].default_value = 0.0
    bs.inputs["Coat Weight"].default_value = 1.0; bs.inputs["Coat IOR"].default_value = CERMIN["ior"]
    bs.inputs["Coat Roughness"].default_value = 0.0; bs.inputs["Coat Tint"].default_value = (*CERMIN["kaca"], 1)
    nt.links.new(bs.outputs["BSDF"], out.inputs["Surface"])
    return m


def sumbu_panel(o):
    ext = [max(v[i] for v in o.bound_box) - min(v[i] for v in o.bound_box) for i in range(3)]
    tipis = ext.index(min(ext))
    return "".join("XYZ"[i] for i in range(3) if i != tipis), tipis, ext


def pasang_material(target, c):
    objs = [o for o in objek_produk(target) if o.type == "MESH"]
    root = next((o for o in objek_produk(target) if o.get("ns_product_root")), None)
    serat = str(root.get("ns_grain", "U")) if root else "U"
    for o in [o for o in bpy.data.objects if o.get("tala_backer")]:
        me = o.data; bpy.data.objects.remove(o, do_unlink=True); bpy.data.meshes.remove(me)
    hit, lo_hi = {}, batas(objek_produk(target))
    pusat = (lo_hi[0] + lo_hi[1]) / 2
    for o in objs:
        asli = json.loads(o["tala_material_asli"]) if "tala_material_asli" in o else \
            [s.material.name if s.material else "" for s in o.material_slots]
        o["tala_material_asli"] = json.dumps(asli, ensure_ascii=False)
        ada_rotan = False
        for i, s in enumerate(o.material_slots):
            # material asli bisa sudah terhapus (0 pengguna saat disimpan) -> material TALA di slot (tala_role)
            awal = (bpy.data.materials.get(asli[i]) if i < len(asli) and asli[i] else None) or s.material
            p = peran(awal)
            if p in ("WOOD_A", "WOOD_B"):
                s.material = mat_oak(serat)
            elif p == "RATTAN":
                s.material = mat_rotan(sumbu_panel(o)[0]); ada_rotan = True
            elif p == "HANDLE":
                s.material = mat_sederhana("TALA | Kuningan", "HANDLE", WARNA["kuningan"], 0.3, 1.0)
            elif p == "CERMIN":
                s.material = mat_cermin()
            else:
                continue
            hit[p] = hit.get(p, 0) + 1
        if ada_rotan and int(c["backer"]):
            pasang_backer(o, pusat)
    return {"slot": hit, "serat": serat}


def pasang_backer(o, pusat_produk):
    """Panel gelap tipis di sisi dalam anyaman (8 mm di belakang), ikut objek rotan; bukan bagian produk."""
    sumbu, k, ext = sumbu_panel(o)
    lo = [min(v[i] for v in o.bound_box) for i in range(3)]
    hi = [max(v[i] for v in o.bound_box) for i in range(3)]
    tengah = [(a + b) / 2 for a, b in zip(lo, hi)]
    p_lokal = o.matrix_world.inverted() @ pusat_produk
    tanda = 1 if p_lokal[k] >= tengah[k] else -1
    pos_k = (hi[k] if tanda > 0 else lo[k]) + tanda * 0.008
    a, b = [i for i in range(3) if i != k]
    me = bpy.data.meshes.new("TALA_backer")
    vs = []
    for ua, ub in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        v = [0.0, 0.0, 0.0]
        v[k] = pos_k
        v[a] = tengah[a] + ua * ext[a] * 0.49
        v[b] = tengah[b] + ub * ext[b] * 0.49
        vs.append(v)
    me.from_pydata(vs, [], [(0, 1, 2, 3)])
    me.materials.append(mat_sederhana("TALA | Backer gelap", "BACKER", WARNA["backer"], 0.8))
    b_o = bpy.data.objects.new("TALA_backer | " + o.name, me)
    koleksi().objects.link(b_o)
    b_o.parent = o; b_o.matrix_parent_inverse = Matrix.Identity(4)
    b_o["tala_backer"] = True; b_o["tala_studio"] = True


# ------------------------------------------------------------------ utama
def cari_produk():
    for s in bpy.data.scenes:
        st = getattr(s, "ns_studio", None)
        if st is not None and st.product is not None:
            return st.product, s
    c = bpy.data.objects.get(CTRL)                     # produk terakhir yang di-fit (tanpa add-on terpasang)
    if c is not None and c.get("produk"):
        t = bpy.data.collections.get(c["produk"]) or bpy.data.objects.get(c["produk"])
        if t is not None:
            return t, None
    o = bpy.context.active_object
    while o is not None and o.parent is not None:
        o = o.parent
    return o, bpy.context.scene


def fit_studio(target=None, tahap=7):
    """Atur seluruh studio TALA dari ukuran produk. tahap: 2 = normalisasi + backdrop + kamera dasar,
    4 = + lampu, 7 = + material produk & warna render."""
    sumber = None
    if target is None:
        target, sumber = cari_produk()
    if target is None:
        raise ValueError("Produk tidak ditemukan (impor produk lewat add-on dulu)")
    sc = tala_scene(sumber)
    c = ctrl_obj()
    lap = {"produk": target.name}
    # link koleksi produk ke scene TALA (lepas produk lama)
    pc = koleksi_produk(target)
    for ch in list(sc.collection.children):
        if ch.name != COLL and ch != pc:
            sc.collection.children.unlink(ch)
    if pc not in sc.collection.children_recursive:
        sc.collection.children.link(pc)
    c["produk"] = target.name
    lap.update(normalisasi(target, c))
    bangun_kamera(c, sc)
    bangun_backdrop(c, float(c["cam_y"]))
    bangun_pantulan(c)
    if tahap >= 4:
        bangun_lampu(c, sc)
    else:
        for n in ("TALA_key", "TALA_fill", "TALA_sweep", "TALA_sweep_gobo"):
            o = bpy.data.objects.get(n)
            if o:
                bpy.data.objects.remove(o, do_unlink=True)
        w = bpy.data.worlds.get("TALA | Dunia") or bpy.data.worlds.new("TALA | Dunia")
        w.use_nodes = True
        next(n for n in w.node_tree.nodes if n.type == "BACKGROUND").inputs["Strength"].default_value = 1.0
        sc.world = w
    if tahap >= 7:
        lap["material"] = pasang_material(target, c)
    sc.view_settings.exposure = float(c["exposure"]) + (float(c["gantung_ev"]) if c.get("gantung") else 0.0)
    sc.view_settings.use_white_balance = True
    sc.view_settings.white_balance_temperature = float(c["wb_k"])
    lap["kamera"] = {k: round(float(c[k]), 4) for k in ("lensa_aktif", "jarak_kamera", "cam_h", "shift_y", "wall_y")}
    lap["horizon"] = horizon(sc, c)
    return lap


def proyeksi(sc, p):
    from bpy_extras.object_utils import world_to_camera_view
    v = world_to_camera_view(sc, sc.camera, Vector(p))
    return v.x, 1 - v.y                 # x dari kiri, y dari atas (0..1)


def horizon(sc, c):
    """Posisi garis dinding-lantai di frame (fraksi dari atas) + bingkai produk."""
    for vl in sc.view_layers:
        vl.update()
    W, D, H, yw, r = (float(c[k]) for k in ("W", "D", "H", "wall_y", "cove_r"))
    z0 = float(c.get("z_alas", 0.0))
    _, y_sambung = proyeksi(sc, (0, yw, 0))
    _, y_cove = proyeksi(sc, (0, yw, r))
    pts = [proyeksi(sc, (x, y, z)) for x in (-W / 2, W / 2) for y in (-D / 2, D / 2) for z in (z0, z0 + H)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return {"sambungan_dari_atas": round(y_sambung, 3), "atas_cove_dari_atas": round(y_cove, 3),
            "produk_x": [round(min(xs), 3), round(max(xs), 3)], "produk_y_dari_atas": [round(min(ys), 3), round(max(ys), 3)],
            "fill_lebar": round(max(xs) - min(xs), 3)}


def preview(path, persen=20, sampel=24):
    sc = bpy.data.scenes[SCENE]
    r, s, d = sc.render.resolution_percentage, sc.cycles.samples, sc.cycles.use_denoising
    sc.render.resolution_percentage, sc.cycles.samples = persen, sampel
    sc.render.filepath = path
    sc.render.image_settings.file_format = "PNG"
    win = bpy.context.window
    bpy.ops.render.render(write_still=True, scene=sc.name)
    sc.render.resolution_percentage, sc.cycles.samples = r, s
    return ukur(path, sc)


def ukur(path, sc):
    """Rata-rata sRGB (0-255) di area dinding kiri-atas, dinding kanan, lantai bawah-tengah, depan produk."""
    import numpy as np
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.array(img.pixels[:]).reshape(h, w, 4)[::-1]       # baris 0 = atas
    bpy.data.images.remove(img)
    def area(x0, x1, y0, y1):
        a = px[int(y0 * h):max(int(y1 * h), int(y0 * h) + 1), int(x0 * w):max(int(x1 * w), int(x0 * w) + 1), :3]
        return [round(float(v) * 255) for v in a.reshape(-1, 3).mean(0)]
    c = bpy.data.objects[CTRL]
    hz = horizon(sc, c)
    x0, x1 = hz["produk_x"]; t0, t1 = hz["produk_y_dari_atas"]
    return {"dinding_kiri": area(0.01, 0.06, 0.05, 0.15), "dinding_kanan": area(0.94, 0.99, 0.05, 0.15),
            "lantai": area(0.4, 0.6, 0.95, 0.99), "lantai_kiri": area(0.01, 0.06, 0.93, 0.99),
            "produk_kiri": area(x0 + 0.04, x0 + 0.12, t0 + 0.25, t0 + 0.45),
            "produk_kanan": area(x1 - 0.12, x1 - 0.04, t0 + 0.25, t0 + 0.45),
            "bawah_produk": area(0.45, 0.55, t1 + 0.005, t1 + 0.02),
            "tengah_produk": area(0.45, 0.55, (t0 + t1) / 2 - 0.05, (t0 + t1) / 2 + 0.05), **hz}


# ------------------------------------------------------------------ UI (operator + panel)
class TALA_OT_fit_studio(bpy.types.Operator):
    bl_idname = "tala.fit_studio"
    bl_label = "Fit Studio"
    bl_description = "Setel ulang studio katalog Tala dari ukuran produk aktif (STUDIO_CTRL)"

    def execute(self, context):
        try:
            lap = fit_studio()
        except ValueError as e:
            self.report({"ERROR"}, str(e)); return {"CANCELLED"}
        if context.window is not None:
            context.window.scene = bpy.data.scenes[SCENE]
        self.report({"INFO"}, f"Tala studio: {lap['produk']} W/D/H {lap['WDH_m']}")
        return {"FINISHED"}


class TALA_PT_panel(bpy.types.Panel):
    bl_space_type, bl_region_type, bl_category, bl_label = "VIEW_3D", "UI", "Tala", "Tala katalog studio"

    def draw(self, context):
        col = self.layout.column()
        col.operator("tala.fit_studio", icon="CAMERA_DATA")
        c = bpy.data.objects.get(CTRL)
        if c is not None:
            for k in ("W", "D", "H", "fill", "wall_gap", "cove_r", "exposure", "key_daya", "fill_rasio", "sweep_daya"):
                if k in c:
                    col.prop(c, f'["{k}"]', text=k)


KELAS = (TALA_OT_fit_studio, TALA_PT_panel)


def register():
    for k in KELAS:
        if not hasattr(bpy.types, k.__name__):
            bpy.utils.register_class(k)


def simpan_teks():
    """Simpan modul ini di file sebagai teks (Register aktif) agar tombol Tala tersedia saat file dibuka."""
    src = globals().get("__file__")
    if not src or not os.path.isfile(src):
        return
    t = bpy.data.texts.get(TEXT) or bpy.data.texts.new(TEXT)
    t.from_string(open(src, encoding="utf-8").read())
    t.use_module = True


# ------------------------------------------------------------------ CLI
def _cli():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    def opsi(flag, banyak=False):
        if flag not in argv:
            return [] if banyak else None
        nilai = []
        for v in argv[argv.index(flag) + 1:]:
            if v.startswith("--"):
                break
            nilai.append(v)
        return nilai if banyak else (nilai[0] if nilai else True)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tahap = int(opsi("--tahap") or 7)
    def laporan(x):
        print("@@" + json.dumps(x, ensure_ascii=False, default=str))

    def ns_addon():
        import importlib.util
        if "nakas_studio_tools" in sys.modules:
            return sys.modules["nakas_studio_tools"]
        spec = importlib.util.spec_from_file_location("nakas_studio_tools", os.path.join(root, "99_SISTEM", "nakas_studio_tools.py"))
        ns = importlib.util.module_from_spec(spec); sys.modules[spec.name] = ns; spec.loader.exec_module(ns); ns.register()
        return ns

    if opsi("--template"):
        ns = ns_addon()
        addon_sc = bpy.context.scene
        sc = tala_scene(addon_sc)
        c = ctrl_obj(); c["root_dir"] = root
        c["W"], c["D"], c["H"] = 1.8, 0.6, 0.9          # ukuran contoh sampai produk diimpor
        bangun_kamera(c, sc); bangun_backdrop(c, float(c["cam_y"])); bangun_lampu(c, sc)
        sc.view_settings.exposure = float(c["exposure"])
        sc.view_settings.use_white_balance = True
        sc.view_settings.white_balance_temperature = float(c["wb_k"])
        simpan_teks()
        out = os.path.join(root, opsi("--simpan") if isinstance(opsi("--simpan"), str) else TEMPLATE)
        bpy.ops.wm.save_as_mainfile(filepath=out)
        laporan({"template": out})
        return
    if opsi("--impor"):
        keluar = os.path.join(root, opsi("--keluar") if isinstance(opsi("--keluar"), str) else "03_PROYEK/TALA")
        os.makedirs(keluar, exist_ok=True)
        for prod in opsi("--impor", True):
            bpy.ops.wm.open_mainfile(filepath=os.path.join(root, TEMPLATE))
            ns = ns_addon()
            addon_sc = bpy.context.scene                         # template disimpan dengan scene add-on aktif
            if addon_sc.name == SCENE:
                raise RuntimeError("Template harus terbuka di scene studio add-on")
            addon_sc.ns_studio.latar_otomatis = False            # scene add-on cukup latar bawaan; render dari TALA
            r = bpy.ops.ns.import_product(filepath=os.path.join(root, prod))
            if "FINISHED" not in r:
                raise RuntimeError("Impor gagal: " + prod)
            if hasattr(ns, "select_shot"):
                ns.select_shot(addon_sc, "HERO")
            lap = fit_studio(addon_sc.ns_studio.product, tahap)
            nama = os.path.splitext(os.path.basename(prod))[0].lower().replace(" ", "_")
            out = os.path.join(keluar, f"tala_{nama}.blend")
            simpan_teks()
            for wm in bpy.data.window_managers:              # file proyek terbuka di scene TALA
                for w in wm.windows:
                    w.scene = bpy.data.scenes[SCENE]
            bpy.ops.wm.save_as_mainfile(filepath=out)
            lap["file"] = out
            if opsi("--preview"):
                lap["preview"] = preview(os.path.splitext(out)[0] + "_preview.png", int(opsi("--persen") or 20), int(opsi("--sampel") or 24))
            laporan(lap)
        return
    if opsi("--fit"):
        c = ctrl_obj()
        for kv in opsi("--set", True):                  # --set exposure=-2 sweep_daya=200
            k, v = kv.split("=")
            c[k] = float(v)
        lap = fit_studio(None, tahap)
        if opsi("--simpan"):
            simpan_teks()
            bpy.ops.wm.save_mainfile()
        if isinstance(opsi("--preview"), str):
            lap["preview"] = preview(opsi("--preview"), int(opsi("--persen") or 20), int(opsi("--sampel") or 24))
        laporan(lap)


register()
# CLI hanya saat dijalankan dari file .py (--python); salinan teks di dalam .blend cukup mendaftarkan tombol UI.
if __name__ == "__main__" and "--" in sys.argv and os.path.isfile(globals().get("__file__") or ""):
    _cli()
