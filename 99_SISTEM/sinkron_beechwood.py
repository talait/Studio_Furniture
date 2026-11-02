# Sinkron grup Beechwood: pasang ulang preset latar 'beechwood_lifestyle' (latar.json) ke file proyek
# Beechwood, sehingga revisi pencahayaan, kamera, dan tekstur berlaku ke semua produk grup.
#
# Alur revisi (semua nilai bersama, tidak ada yang disetel per file):
#   1. Ubah sumbernya:
#      - tekstur kayu/handle, dinding, lantai, lampu gradasi dinding, matahari
#          -> 99_SISTEM/bangun_latar_beechwood.py
#      - exposure, lampu gradasi produk (atas/depan), lampu rongga/aksen, finish
#          -> 02_PRODUK/_LATAR/latar.json, preset 'beechwood_lifestyle'
#      - kamera & framing (fit_cameras, select_shot, resolusi kualitas)
#          -> add-on 99_SISTEM/nakas_studio_tools.py (otomatis dari ukuran produk, berlaku semua produk)
#   2. Bangun ulang library (bila builder diubah):
#        blender -b 02_PRODUK/_LATAR/Doheny_Lifestyle.blend --python 99_SISTEM/bangun_latar_beechwood.py
#   3. Sinkron file proyek:
#        blender -b 03_PROYEK/beechwood_6drawers.blend --python 99_SISTEM/sinkron_beechwood.py
#        blender -b --python 99_SISTEM/sinkron_beechwood.py -- --semua      (semua 03_PROYEK/*beechwood*.blend)
#        blender -b --python 99_SISTEM/sinkron_beechwood.py -- --file A.blend B.blend
#
# Proyek baru dari file produk (template studio + impor add-on, latar otomatis dari nama koleksi):
#   blender -b 01_STUDIO/Studio_Nakas.blend --python 99_SISTEM/sinkron_beechwood.py -- \
#       --impor "02_PRODUK/BEECHWOOD/BEECHWOOD TALLBOY.blend" --simpan 03_PROYEK/beechwood_tallboy.blend
#
# Preset memakai 'sinkron_material': true -> material kayu & handle di file selalu diganti versi library.
# Perbaikan geometri/UV khusus produk (rel 6dw, UV tallboy) tetap di skrip proyek masing-masing.
import bpy, sys, json, importlib.util
from pathlib import Path
#
# Beechwood V2 (oak natural terang + rotan, sejak 31-10-2026): preset 'beechwood_v2' (library dari
# 99_SISTEM/bangun_latar_beechwood_v2.py). Proyek baru V2:
#   blender -b 01_STUDIO/Studio_Nakas.blend --python 99_SISTEM/sinkron_beechwood.py -- \
#       --impor "02_PRODUK/BEECHWOOD/BEECHWOOD BUFFET.blend" --simpan 03_PROYEK/beechwood_v2_buffet.blend --latar beechwood_v2
# Sinkron tanpa --latar memakai preset Beechwood yang sudah terpasang di file (V1 tetap V1, V2 tetap V2).
ROOT = Path(__file__).resolve().parents[1]
LATAR_DEFAULT = 'beechwood_lifestyle'
LATAR_GRUP = ('beechwood_lifestyle', 'beechwood_v2', 'doheny_lifestyle', 'doheny_buffet')    # doheny*: buffet versi Doheny
spec = importlib.util.spec_from_file_location('nakas_studio_tools', ROOT / '99_SISTEM/nakas_studio_tools.py')
ns = importlib.util.module_from_spec(spec); sys.modules[spec.name] = ns; spec.loader.exec_module(ns); ns.register()
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def option(flag, many=False):
    if flag not in argv:
        return [] if many else None
    rest = argv[argv.index(flag) + 1:]
    values = []
    for value in rest:
        if value.startswith('--'):
            break
        values.append(value)
    return values if many else (values[0] if values else None)


def tidy_duplicates():
    """Nama '.001' dari ruang/material lama: buang versi dasar yang tak terpakai, pakai nama dasar."""
    for data in (bpy.data.materials, bpy.data.collections, bpy.data.lights):
        for item in list(data):
            base, _, num = item.name.rpartition('.')
            if num.isdigit() and base in data and data[base].users - int(getattr(data[base], 'use_fake_user', False)) == 0:
                data.remove(data[base]); item.name = base


def latar_id(scene):
    """--latar bila diberikan, selain itu preset grup Beechwood yang sudah terpasang di file."""
    if option('--latar'):
        return option('--latar')
    current = scene.get('ns_latar')
    return current if current in LATAR_GRUP else LATAR_DEFAULT


def report(scene):
    preset = ns.latar_preset(latar_id(scene))
    coll = bpy.data.collections.get(ns.LATAR_COLLECTION)
    lights = {o.name: round(o.data.energy, 1) for o in (coll.objects if coll else []) if o.type == 'LIGHT'}
    product = scene.ns_studio.product
    mats = sorted({sl.material.name for o in product.all_objects for sl in o.material_slots if sl.material}) if product else []
    wood = bpy.data.materials.get(preset['finish_kayu']['material'])
    return {'file': Path(bpy.data.filepath).name, 'latar': scene.get('ns_latar'), 'produk': product.name if product else None,
            'exposure': round(scene.view_settings.exposure, 2), 'lampu': lights,
            'penerima': {o.name: o.light_linking.receiver_collection.name for o in (coll.objects if coll else [])
                         if o.type == 'LIGHT' and o.light_linking.receiver_collection},
            'material_produk': mats,
            'node_kayu': sorted(n.name for n in wood.node_tree.nodes if n.name in ('Serat bergelombang', 'Goresan brush')) if wood else None,
            'grain': ns.root_for(scene).get('ns_grain') if ns.root_for(scene) else None,
            'duplikat': sorted(m.name for m in bpy.data.materials if m.name[-4:-3] == '.' and m.name[-3:].isdigit())}


def sync_current():
    scene = bpy.context.scene
    if not scene.get('ns_ready') or scene.ns_studio.product is None:
        raise ValueError('Bukan file proyek studio (tidak ada produk aktif): ' + bpy.data.filepath)
    shot = scene.ns_studio.shot
    ns.select_latar(scene, latar_id(scene))
    tidy_duplicates()
    ns.fit_cameras(scene)
    ns.select_shot(scene, shot)
    bpy.ops.wm.save_mainfile()
    print('##' + json.dumps(report(scene), ensure_ascii=False))


def import_product(product_path, out_path):
    scene = bpy.context.scene
    scene.ns_studio.latar_otomatis = not option('--latar')     # --latar: preset dipasang di sync_current
    result = bpy.ops.ns.import_product(filepath=str(product_path))
    if 'FINISHED' not in result:
        raise RuntimeError('Impor gagal: ' + str(product_path))
    bpy.ops.wm.save_as_mainfile(filepath=str(out_path))
    sync_current()


if option('--impor'):
    import_product((ROOT / option('--impor')).resolve(), (ROOT / option('--simpan')).resolve())
elif '--semua' in argv or option('--file', many=True):
    files = [(ROOT / f).resolve() for f in option('--file', many=True)] or \
            sorted(p for p in (ROOT / '03_PROYEK').glob('*.blend') if 'beechwood' in p.name.lower())
    for path in files:
        bpy.ops.wm.open_mainfile(filepath=str(path))
        sync_current()
else:
    sync_current()
