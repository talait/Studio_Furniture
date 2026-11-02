# USANG (31 Okt 2026): angle samping kanan, belakang, dan kamera overview sudah dihapus (hapus_kamera_lama.py).
# Jangan dijalankan lagi: skrip ini membuat ulang kamera overview dan memakai kamera SIDE.
"""Tambah angle kamera 06-09 (samping kiri, belakang 3/4, detail kaki, close-up), jadikan
angle Samping kanan profil seamless, beri nama kamera tanpa spasi (CAM_01_HERO ...,
CAM_STUDIO_OVERVIEW), dan pasang driver agar putaran produk & lampu angle mengikuti
kamera aktif (benar juga untuk render per kamera di luar addon / render server).

Jalankan dari folder utama:
  blender -b --python 99_SISTEM/tambah_angle_kamera.py -- [file.blend]

Tanpa argumen: template 01_STUDIO/Studio_Nakas.blend (dibackup sekali sebelum disimpan).
Dengan file sesi (03_PROYEK/...): file itu diperbarui di tempat; Blender menyimpan .blend1.

- Samping kanan/kiri dan belakang: kamera tetap di depan backdrop; addon memutar produk
  (ns_product_yaw di kamera) saat angle dipilih, jadi latar selalu seamless.
- Detail kaki & close-up: framing sebanding ukuran produk (ns_fit 'detail', ns_detail_scale).
- Rig lampu angle baru = salinan lampu angle sumber (SHOT_LIGHT_SOURCE addon).
Idempoten: aman dijalankan berulang.
"""
import bpy, sys, shutil, math, importlib.util
from pathlib import Path
from datetime import datetime
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / '01_STUDIO' / 'Studio_Nakas.blend'

_old = sys.modules.get('nakas_studio_tools')
if _old and hasattr(bpy.types.Scene, 'ns_studio'):
    _old.unregister()
_spec = importlib.util.spec_from_file_location('nakas_studio_tools', ROOT / '99_SISTEM' / 'nakas_studio_tools.py')
ns = importlib.util.module_from_spec(_spec)
sys.modules['nakas_studio_tools'] = ns
_spec.loader.exec_module(ns)
ns.register()

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
TARGET = Path(ARGS[0]) if ARGS else TEMPLATE

# Kamera baru: (kamera sumber, arah kamera, titik bidik sebagai fraksi ukuran produk,
# putaran produk °, pengaturan close-up)
NEW_CAMERAS = {
    'SIDE_L': ('FRONT', (0.0, -2.0, 0.30), (0, 0, 0.5), 90.0, None),
    'BACK': ('HERO', None, None, 180.0, None),
    'BASE': ('DETAIL', (1.0, -1.6, 0.25), (0.30, -0.45, 0.10), 0.0, {'scale': 0.8, 'lens': 70.0}),
    # bidik sudut depan-atas kanan (pertemuan rangka & material), bukan udara di atas dudukan
    'CLOSEUP': ('DETAIL', (1.0, -1.4, 0.80), (0.47, -0.46, 0.78), 0.0, {'scale': 0.6, 'lens': 85.0}),
}
REF_LO, REF_HI = Vector((-0.25, -0.20, 0.0)), Vector((0.25, 0.20, 0.55))   # nakas acuan template


def rig_for(shot):
    return next((c for c in bpy.data.collections if c.get('ns_light_shot') == shot), None)


def cam_name(shot):
    return f'CAM_{ns.SHOT_IDS.index(shot) + 1:02d}_{shot}'


def rotate_about_z(objects, degrees):
    rot = Matrix.Rotation(math.radians(degrees), 4, 'Z')
    for obj in objects:
        # matrix_basis, bukan matrix_world: objek di rig tersembunyi tidak dievaluasi
        # sehingga matrix_world-nya identitas (objek-objek ini tanpa parent).
        obj.matrix_basis = rot @ obj.matrix_basis
        if 'ns_base_location' in obj:
            obj['ns_base_location'] = list(rot.to_3x3() @ Vector(obj['ns_base_location']))


def side_to_profile(scene):
    """Samping kanan: kamera + rig diputar -90° ke depan backdrop, produk diputar -90°."""
    cam = ns.camera_for(scene, 'SIDE')
    if cam is None or 'ns_product_yaw' in cam:
        return False
    rig = rig_for('SIDE')
    # Hanya lampu yang ikut diputar; softbox/stand fisik tetap di tempat agar tidak
    # menghalangi kamera dan cahaya di posisi baru.
    rotate_about_z([cam] + ([o for o in rig.all_objects if o.type == 'LIGHT'] if rig else []), -90.0)
    cam['ns_direction'] = list(Matrix.Rotation(math.radians(-90), 3, 'Z') @ Vector(cam['ns_direction']))
    cam['ns_product_yaw'] = -90.0
    return True


def add_camera(scene, shot):
    source_shot, direction, fraction, yaw, closeup = NEW_CAMERAS[shot]
    if ns.camera_for(scene, shot):
        return False
    src = ns.camera_for(scene, source_shot)
    cam = src.copy()
    cam.data = src.data.copy()
    for coll in src.users_collection:
        coll.objects.link(cam)
    cam['ns_shot'] = shot
    if direction:
        cam['ns_direction'] = direction
    if fraction:
        cam['ns_target_fraction'] = fraction
    cam['ns_product_yaw'] = yaw
    if closeup:
        cam['ns_fit'] = 'detail'
        cam['ns_detail_scale'] = closeup['scale']
        cam.data.lens = closeup['lens']
        cam.data.dof.use_dof = True
        cam.data.dof.aperture_fstop = 4.0
        size = REF_HI - REF_LO
        f = Vector(cam['ns_target_fraction'])
        target = Vector(((REF_LO.x + REF_HI.x) / 2 + size.x * f.x, (REF_LO.y + REF_HI.y) / 2 + size.y * f.y, REF_LO.z + size.z * f.z))
        distance = max(size) * closeup['scale']
        cam.location = target + Vector(cam['ns_direction']).normalized() * distance
        ns.aim(cam, target)
        cam.data.dof.focus_distance = distance
    return True


def add_rig(shot):
    if rig_for(shot):
        return 0
    source = rig_for(ns.SHOT_LIGHT_SOURCE[shot])
    parent = next((c for c in bpy.data.collections if source.name in c.children), None)
    rig = bpy.data.collections.new(f'LIGHTS {ns.SHOT_IDS.index(shot) + 1:02d} | {shot}')
    (parent.children if parent else bpy.context.scene.collection.children).link(rig)
    for key in source.keys():
        rig[key] = source[key]
    rig['ns_light_shot'] = shot
    copied = 0
    for obj in source.all_objects:
        if obj.type != 'LIGHT':
            continue
        new = obj.copy()
        new.data = obj.data.copy()
        new.name = new.data.name = obj.name.replace(ns.SHOT_LIGHT_SOURCE[shot] + ' /', shot + ' /', 1)
        if 'ns_light_shot' in new:
            new['ns_light_shot'] = shot
        rig.objects.link(new)
        copied += 1
    rig.hide_render = rig.hide_viewport = True
    return copied


scene = bpy.context.scene
if Path(bpy.data.filepath).resolve() != TARGET.resolve():
    bpy.ops.wm.open_mainfile(filepath=str(TARGET))
    scene = bpy.context.scene

report = {'profile_side': side_to_profile(scene), 'cameras': [], 'lights': {}}
for shot in NEW_CAMERAS:
    if add_camera(scene, shot):
        report['cameras'].append(shot)
    report['lights'][shot] = add_rig(shot)
for shot in ns.SHOT_IDS:
    cam = ns.camera_for(scene, shot)
    if cam:
        cam.name = cam_name(shot)
overview = ns.overview_camera()
if overview:
    overview.name = ns.OVERVIEW_NAMES[0]
# Driver: putaran produk & rig lampu mengikuti kamera aktif, juga untuk render di luar addon.
ns.ensure_angle_drivers(scene)

if scene.ns_studio.product and ns.product_objects(scene):
    ns.fit_cameras(scene)
ns.select_shot(scene, scene.ns_studio.shot)
ns.snapshot_watts()

if TARGET.resolve() == TEMPLATE.resolve():
    backup = TEMPLATE.with_name('Studio_Nakas_sebelum_angle_' + datetime.now().strftime('%Y%m%d_%H%M') + '.blend')
    if not any(TEMPLATE.parent.glob('Studio_Nakas_sebelum_angle_*.blend')):
        shutil.copy2(TEMPLATE, backup)
bpy.ops.wm.save_mainfile()
print('ANGLE_OK', TARGET.name, report)
