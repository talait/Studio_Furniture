# Bangun 02_PRODUK/_LATAR/Beechwood_V2_Lifestyle.blend: template Beechwood V2 (warna baru 31-10-2026, ikut foto
# referensi buffet: oak/beech natural terang + rotan natural + handle logam gelap).
# Ruang, dinding, lantai, lampu sama persis dengan Beechwood_Lifestyle.blend; hanya finish kayu yang diganti:
# pola scan serat/pori/brush walnut dipakai ulang, palet diganti oak natural terang, koreksi hue walnut dinetralkan.
# Handle V2 (logam gelap) didefinisikan di latar.json (preset 'beechwood_v2'), tidak perlu material library.
# Peran WOOD_B (interior) & RATTAN (anyaman) tetap material produk (add-on hanya mengganti WOOD_A & HANDLE).
# Jalankan: blender -b 02_PRODUK/_LATAR/Beechwood_Lifestyle.blend --python 99_SISTEM/bangun_latar_beechwood_v2.py
# (file Beechwood_Lifestyle hanya dibaca, tidak disimpan)
import bpy, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '02_PRODUK' / '_LATAR' / 'Beechwood_V2_Lifestyle.blend'
FIN_V1 = 'FIN | Beechwood Walnut Referensi'
FIN_V2 = 'FIN | Beechwood V2 Oak Natural'

# Palet linear (posisi pola sama dengan V1: p15 gelap, median, p92 terang). Target tampilan front di render
# lifestyle (exposure -3, Khronos PBR Neutral) ~ sRGB 205/189/163 seperti frame buffet di foto referensi.
PALET = [(0.15, (0.42, 0.33, 0.22)), (0.68, (0.58, 0.48, 0.35)), (0.95, (0.66, 0.56, 0.42))]
HSV = (0.5, 1.0, 1.0)                   # netral: tidak ada geseran hue/saturasi walnut

wood = bpy.data.materials[FIN_V1].copy()
wood.name = FIN_V2
N = wood.node_tree.nodes
for e, (pos, c) in zip(N['Palet kayu'].color_ramp.elements, PALET):
    e.position, e.color = pos, (*c, 1)
for k, v in zip(('Hue', 'Saturation', 'Value'), HSV):
    N['Hue/Saturation/Value'].inputs[k].default_value = v
wood.diffuse_color = (*PALET[1][1], 1)
wood['ns_finish_id'], wood['ns_role'], wood['ns_finish_nama'] = 'beechwood_v2_oak_natural', 'WOOD_A', 'Beechwood V2 Oak Natural'
wood['ns_grain'], wood['ns_kayu_versi'] = 'V', 'v2-1'

objs = {o for o in bpy.data.objects if o.get('ns_latar')}
bpy.data.libraries.write(str(OUT), objs | {wood}, fake_user=True, compress=True)
print('##LATAR', json.dumps({'objects': sorted(o.name for o in objs), 'finish': FIN_V2, 'out': str(OUT)}))
