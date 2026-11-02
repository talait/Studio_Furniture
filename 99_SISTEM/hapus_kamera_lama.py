# Hapus angle kamera yang tidak dipakai lagi (31 Okt 2026): CAM_04_SIDE (samping kanan), CAM_07_BACK (belakang 3/4),
# dan CAM_STUDIO_OVERVIEW, beserta rig lampunya (LIGHTS 04 | SIDE, LIGHTS 07 | BACK). Add-on sudah tidak membuat /
# menampilkan angle ini (nakas_studio_tools.REMOVED_SHOTS); skrip ini membersihkan file yang sudah ada.
# Objek rig yang juga dipakai rig angle lain tidak dihapus. Kunci kamera & override per produk untuk angle ini dibuang.
# Tiap file dicadangkan ke _BACKUP/<nama>_SEBELUM_hapus_kamera.blend di foldernya sebelum disimpan.
#   blender -b --python 99_SISTEM/hapus_kamera_lama.py -- --semua          (template studio + semua 03_PROYEK/*.blend)
#   blender -b --python 99_SISTEM/hapus_kamera_lama.py -- --file A.blend B.blend
import bpy, sys, json, shutil, importlib.util
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('nakas_studio_tools', ROOT / '99_SISTEM/nakas_studio_tools.py')
ns = importlib.util.module_from_spec(spec); sys.modules[spec.name] = ns; spec.loader.exec_module(ns); ns.register()
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def clean_current():
    removed = []
    cams = [o for o in bpy.data.objects if o.type == 'CAMERA'
            and (o.get('ns_shot') in ns.REMOVED_SHOTS or o.name in ns.OVERVIEW_NAMES)]
    rigs = [c for c in bpy.data.collections if c.get('ns_light_shot') in ns.REMOVED_SHOTS]
    keep = {o for c in bpy.data.collections if c.get('ns_light_shot') and c not in rigs for o in c.all_objects}
    for scene in bpy.data.scenes:
        if scene.camera in cams:
            scene.camera = ns.camera_for(scene, 'HERO')
        if hasattr(scene, 'ns_studio') and scene.ns_studio.shot in ns.REMOVED_SHOTS:
            scene.ns_studio.shot = 'HERO'
    for rig in rigs:
        for obj in [o for o in rig.all_objects if o not in keep]:
            removed.append(obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)
        for child in list(rig.children_recursive):
            if not child.all_objects:
                bpy.data.collections.remove(child)
        removed.append(rig.name)
        bpy.data.collections.remove(rig)
    for cam in cams:
        removed.append(cam.name)
        bpy.data.objects.remove(cam, do_unlink=True)
    for root in [o for o in bpy.data.objects if o.get('ns_product_root')]:
        locks = root.get(ns.CAMERA_LOCK)
        for shot in ns.REMOVED_SHOTS:
            if locks is not None and shot in locks:
                del locks[shot]
            if 'ns_kamera_' + shot in root:
                del root['ns_kamera_' + shot]
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    return removed


def process(path):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    removed = clean_current()
    if not removed:
        print('##' + json.dumps({'file': path.name, 'dihapus': 0}))
        return
    backup = path.parent / '_BACKUP' / f'{path.stem}_SEBELUM_hapus_kamera.blend'
    backup.parent.mkdir(exist_ok=True)
    if not backup.exists():
        shutil.copy2(path, backup)
    bpy.ops.wm.save_mainfile()
    cams = sum(1 for n in removed if n.startswith('CAM'))
    print('##' + json.dumps({'file': path.name, 'kamera': cams, 'objek_rig': len(removed) - cams}, ensure_ascii=False))


if '--semua' in argv:
    files = [ROOT / '01_STUDIO' / 'Studio_Nakas.blend'] + sorted((ROOT / '03_PROYEK').glob('*.blend'))
else:
    files = [(ROOT / f).resolve() for f in argv[argv.index('--file') + 1:]] if '--file' in argv else []
for path in files:
    process(path)
