# Ekstrak produk Doheny Sofa / Armchair dari sesi lama (03_PROYEK/<NAMA>+studio_add_on.blend) ke file produk bersih.
# Env NAMA (default Doheny_Sofa) dan FOLDER (default SOFA): NAMA=Doheny_Armchair FOLDER=ARMCHAIR untuk armchair.
# blender -b "03_PROYEK/Doheny_Sofa+studio_add_on_SEBELUM_preset_doheny.blend" --python ekstrak_sofa.py
import bpy, os, sys
from pathlib import Path
ROOT = Path(r"C:/Users/Staff/Documents/Studio_Furniture")
sys.path.insert(0, str(ROOT / '02_PRODUK/BEECHWOOD/_skrip'))
from konstruksi_util import uv_meter
NAMA = os.environ.get('NAMA', 'Doheny_Sofa')
OUT = ROOT / '02_PRODUK/DOHENY' / os.environ.get('FOLDER', 'SOFA') / (NAMA + '.blend')
OUT.parent.mkdir(parents=True, exist_ok=True)

bpy.ops.file.make_paths_absolute()
root = bpy.data.objects['PRODUCT_ROOT | ' + NAMA]
keep = {root, *root.children_recursive}
scene = bpy.context.scene
prod = bpy.data.collections.new('PRODUK')
scene.collection.children.link(prod)
for o in keep:
    for c in list(o.users_collection):
        c.objects.unlink(o)
    prod.objects.link(o)
for c in list(bpy.data.collections):
    if c is not prod:
        bpy.data.collections.remove(c)
for o in list(bpy.data.objects):
    if o not in keep:
        bpy.data.objects.remove(o)
for w in list(bpy.data.worlds):
    w.use_fake_user = False

# Kayu ek terlihat: satu material peran WOOD_A, serat lewat 'UV meter' (seperti Bed / 6 Drawers).
wood = bpy.data.materials['DS_Oak_GrainX']
wood.name = 'ROLE | WOOD_A'
wood['ns_role'] = 'WOOD_A'
grain_of = {'DS_Oak_GrainX': 'X', 'ROLE | WOOD_A': 'X', 'DS_Oak_GrainY': 'Y', 'DS_Oak_GrainZ': 'Z'}
for o in keep:
    if o.type != 'MESH':
        continue
    for slot in o.material_slots:
        m = slot.material
        if m and m.name in grain_of:
            uv_meter(o, grain_of[m.name])
            slot.material = wood
# Kain: semua linen (dudukan, sandaran, bantal, panel lengan, piping) = peran KAIN preset.
bpy.data.materials['DS_Linen_Beige']['ns_role'] = 'KAIN'
# Rangka dalam tersembunyi: peran sendiri agar tidak ditebak WOOD_A dan tidak diganti preset.
for n in ('DS_Pine_Inner', 'DS_Plywood_Inner', 'DS_Beech_Dowel', 'DS_Webbing', 'DS_Steel_Bolt'):
    bpy.data.materials[n]['ns_role'] = 'KONSTRUKSI'

root['category'] = 'SOFA'
root['asset_id'] = NAMA.lower()
root['front'] = '-Y; ground Z=0'
root['ns_grain'] = 'V'                    # UV meter: serat sepanjang V
bpy.ops.outliner.orphans_purge(do_recursive=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT), relative_remap=True)
print('##saved', OUT, len(bpy.data.objects), [m.name for m in bpy.data.materials],
      [(i.name, i.filepath, i.packed_file is not None) for i in bpy.data.images])
