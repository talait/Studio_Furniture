# Sesi buffet versi Doheny (31-10-2026): kunci kamera hasil setelan manual, perbaiki fokus close-up, dan pasang
# preset latar 'doheny_buffet' (Doheny lifestyle + lampu gradasi produk, tanpa lampu rongga yang menyorot kaki).
#   - Fokus CLOSEUP/BASE: jarak ke permukaan produk di tengah frame (ray cast), f/8 agar rotan & frame tajam.
#   - Kamera dikunci (root['ns_camera_lock']) -> sinkron/atur framing tidak menimpa setelan manual.
#   - --kamera-dari <sesi.blend>: salin kunci kamera dari sesi lain (produk sama), mis. versi cane -> rapat.
# Pakai:
#   blender -b 03_PROYEK/<sesi>.blend --python buffet_doheny_kamera_lampu.py -- [--kamera-dari <sesi.blend>] [--simpan]
import bpy, sys, json, importlib.util
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("nakas_studio_tools", ROOT / "99_SISTEM/nakas_studio_tools.py")
ns = importlib.util.module_from_spec(spec); sys.modules[spec.name] = ns; spec.loader.exec_module(ns); ns.register()
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FSTOP_DETAIL = 8.0
LATAR = "doheny_buffet"

sc = bpy.context.scene
root = ns.root_for(sc)
hasil = {}

if "--kamera-dari" in argv:
    sumber = argv[argv.index("--kamera-dari") + 1]
    with bpy.data.libraries.load(sumber) as (src, dst):
        dst.objects = [n for n in src.objects if n == root.name]
    lain = dst.objects[0]
    root[ns.CAMERA_LOCK] = lain[ns.CAMERA_LOCK].to_dict()
    bpy.data.objects.remove(lain)
    for shot in ns.locked_shots(sc):
        ns.restore_locked_camera(sc, shot)
    hasil["kamera_dari"] = sumber
else:
    deps = bpy.context.evaluated_depsgraph_get()
    for shot in ("CLOSEUP", "BASE"):
        cam = ns.camera_for(sc, shot)
        if cam is None:
            continue
        pos = cam.matrix_world.translation
        maju = cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))
        ok, loc, *_ = sc.ray_cast(deps, pos, maju)
        if ok:
            cam.data.dof.focus_distance = (loc - pos).dot(maju)
        cam.data.dof.use_dof = True
        cam.data.dof.aperture_fstop = FSTOP_DETAIL
        hasil[shot] = {"fokus_m": round(cam.data.dof.focus_distance, 3), "f": FSTOP_DETAIL}
    for shot in ns.SHOT_IDS:
        ns.lock_camera(sc, shot)
    hasil["dikunci"] = ns.locked_shots(sc)

root["ns_rongga"] = False
shot = sc.ns_studio.shot
ns.select_latar(sc, LATAR)
ns.fit_cameras(sc)                     # kamera terkunci -> posisi manual dipulihkan
ns.select_shot(sc, shot)
coll = bpy.data.collections.get(ns.LATAR_COLLECTION)
hasil["latar"] = sc.get("ns_latar")
hasil["lampu"] = {o.name: round(o.data.energy, 1) for o in coll.objects if o.type == "LIGHT"} if coll else None
print("@@" + json.dumps(hasil, ensure_ascii=False))
if "--simpan" in argv:
    bpy.ops.wm.save_mainfile()
