# Bangun 02_PRODUK/_LATAR/Beechwood_Lifestyle.blend dari ruang Doheny lifestyle (lantai, dinding, plafon,
# Key Sun + Sky Fill + light linking), diwarnai ulang ke tema Beechwood (foto bed: dinding greige hangat,
# lantai batu terang hangat) + finish kayu walnut Beechwood dari proyek beechwood_6drawers.
# Jalankan: blender -b 02_PRODUK/_LATAR/Doheny_Lifestyle.blend --python 99_SISTEM/bangun_latar_beechwood.py
# (file Doheny hanya dibaca, tidak disimpan)
import bpy, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '02_PRODUK' / '_LATAR' / 'Beechwood_Lifestyle.blend'
SRC_WOOD = ROOT / '03_PROYEK' / '_BACKUP' / 'beechwood_6drawers_SEBELUM_latar_beechwood.blend'
FIN = 'FIN | Beechwood Walnut Referensi'

# Warna (linear) - dikalibrasi lewat render HERO terhadap foto bed Beechwood
DINDING = (0.78, 0.715, 0.64)            # putih hangat netral (editan foto: dinding lebih terang & dingin)
LANTAI_GELAP = (0.177, 0.163, 0.145)          # batu/microcement terang hangat (ujung gelap & terang ramp)
LANTAI_TERANG = (0.345, 0.32, 0.29)
# Serat dirapikan: pita putih lebar di pola scan hanya sedikit lebih terang (bukan belang), garis gelap
# dilunakkan, relief tipis -> permukaan rata seperti foto referensi
# Clarity serat: separuh piksel pola ada di 0.5-0.85, jadi titik palet ditaruh di persentil pola
# (p15 gelap, median, p92 terang) -> garis serat jelas di seluruh permukaan, bukan hanya garis tergelap.
KAYU = [(0.15, (92, 52, 33)), (0.68, (128, 78, 51)), (0.95, (142, 89, 60))]   # sRGB palet tekstur Doheny
# Dikalibrasi ke foto referensi kayu (smoked oak, rata-rata sRGB 116,88,64): front laci di render HERO
# disamakan rata-ratanya -> coklat lebih gelap, kurang oranye
# Feedback kedua (foto bed walnut, rail sRGB 119,70,48): terlalu gelap & kurang coklat -> lebih terang,
# hue digeser ke coklat kemerahan walnut (G/R ~0.6, bukan 0.68 kekuningan)
WARNA_HUE = 0.484   # 'Hue/Saturation/Value' Hue (0.5 = tetap)
SATURASI = 1.4   # 'Hue/Saturation/Value' Saturation
KECERAHAN = 0.56   # 'Hue/Saturation/Value' Value
RELIEF = 0.1
# Pola dipanjangkan searah serat (skala X 'Mapping.001' 0.8 -> 0.3): mata kayu/katedral di scan
# menjadi garis panjang lurus, tidak muncul sebagai lingkaran di front laci
SERAT_PANJANG = 0.9   
SERAT_PADAT = 2.0   # skala Y 'Mapping.001' (awal 1.2): garis serat lebih rapat
# Serat natural (ruang 'Mapping.001': X = searah serat, Y = melintang): garis dibelokkan pelan oleh
# noise frekuensi rendah supaya tidak lurus penggaris, plus goresan brush halus memanjang searah serat
# (relief + sedikit variasi warna) seperti veneer wire-brushed.
GELOMBANG_SKALA = (9.0, 2.0, 1.0)          # noise gelombang: ~3 belokan per meter panjang serat
GELOMBANG_AMP = 0.0   # geseran melintang (unit pola), ~beberapa lebar garis
BRUSH_SKALA = (40.0, 350.0, 1.0)           # goresan ~8 cm panjang, ~2 mm jarak
BRUSH_RELIEF, BRUSH_WARNA = 0.1, 0.05
# Pori oak (feedback: terlihat plastik): garis putus-putus gelap pendek searah serat, sedikit cekung &
# lebih kasar. Finish doff/satin: roughness naik, coat dihapus, spekular turun.
PORI_SKALA = (400.0, 1400.0, 1.0)          # pori ~5-10 mm panjang, ~1 mm lebar (terlihat di close-up)
PORI_AMBANG = (0.60, 0.70)                 # noise -> masker pori (makin tinggi makin jarang)
PORI_GELAP, PORI_RELIEF, PORI_KASAR = 0.85, 0.15, 0.05
KASAR = (0.35, 0.45)                       # satin: < 0.25 terlalu glossy, > 0.5 doff
# Finishing satin / semi-matte (~25% sheen, NC/PU satin atau hard-wax oil): kilap lebar & lembut di tepi
# membulat, lapisan tipis, pori terbuka halus (spesifikasi material referensi)
SPEKULAR, COAT = 0.45, 0.2
COAT_KASAR = 0.3
# Figur walnut lebar (referensi rail bed): coretan terang-gelap lebar & lembut memanjang searah serat,
# di atas garis serat halus
VARIASI_SKALA = (1.2, 14.0, 1.0)           # coretan panjang (~2x lebih panjang dari lebar laci), beberapa cm lebar
VARIASI_KUAT = 0.0   # faktor overlay
VARIASI_DETAIL = 1.0                       # sedikit detail: coretan halus, bukan totol-totol
VARIASI_RENTANG = (0.3, 0.7)               # noise diregang -> coretan terang/gelap jelas
# Handle kayu hitam (eboni): pola serat sama, palet gelap, sedikit lebih mengkilap
HITAM = [(0.0, (20, 16, 14)), (0.5, (30, 25, 22)), (1.0, (42, 35, 30))]
HITAM_KASAR = (0.30, 0.42)
HITAM_HSV = (0.5, 1.0, 0.76)
KAYU_K = (0.75, 1.35, 2.3)                # pengali linear hasil kalibrasi warna referensi
# Cahaya bergradasi (foto referensi studio): kolam cahaya lembut di dinding belakang, terang di
# tengah-atas lalu meredup ke tepi & bawah; matahari lebih lembut; dinding samping tanpa sinar langsung.
GRADASI_W = 300.0                          # energi area light dinding (W), hanya menerangi dinding belakang
GRADASI_UKURAN = (2.8, 1.8)                # elips (m)
GRADASI_POS, GRADASI_BIDIK = (0.45, 1.3, 2.5), (0.45, 2.046, 1.3)   # koordinat ruang file Doheny
MATAHARI_SUDUT = 20.0                      # derajat (Doheny 12): bayangan lebih lembut

wall_mat = bpy.data.materials['Lifestyle | Matte Off-White'].copy()
wall_mat.name = 'Beechwood | Dinding greige'
bsdf = next(n for n in wall_mat.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
bsdf.inputs['Base Color'].default_value = (*DINDING, 1)
wall_mat.diffuse_color = (*DINDING, 1)

floor_mat = bpy.data.materials['Lifestyle | Lantai Semen Microcement'].copy()
floor_mat.name = 'Beechwood | Lantai batu hangat'
el = floor_mat.node_tree.nodes['Color Ramp'].color_ramp.elements
el[0].color, el[-1].color = (*LANTAI_GELAP, 1), (*LANTAI_TERANG, 1)

for o in bpy.data.objects:
    for s in o.material_slots:
        if s.material and s.material.name == 'Lifestyle | Matte Off-White':
            s.material = wall_mat
        elif s.material and s.material.name == 'Lifestyle | Lantai Semen Microcement':
            s.material = floor_mat

with bpy.data.libraries.load(str(SRC_WOOD), link=False) as (src, dst):
    dst.materials = [FIN]
wood = dst.materials[0]
srgb = lambda c: (c / 255) ** 2.2
for e, (pos, c) in zip(wood.node_tree.nodes['Palet kayu'].color_ramp.elements, KAYU):
    e.position, e.color = pos, (*(srgb(v) * k for v, k in zip(c, KAYU_K)), 1)
wood.node_tree.nodes['Relief serat'].inputs['Strength'].default_value = RELIEF
wood.node_tree.nodes['Hue/Saturation/Value'].inputs['Saturation'].default_value = SATURASI
wood.node_tree.nodes['Hue/Saturation/Value'].inputs['Value'].default_value = KECERAHAN
wood.node_tree.nodes['Hue/Saturation/Value'].inputs['Hue'].default_value = WARNA_HUE
wood.node_tree.nodes['Mapping.001'].inputs['Scale'].default_value[0] = SERAT_PANJANG
wood.node_tree.nodes['Mapping.001'].inputs['Scale'].default_value[1] = SERAT_PADAT
wood['ns_finish_id'], wood['ns_role'], wood['ns_finish_nama'] = 'beechwood_walnut', 'WOOD_A', 'Beechwood Walnut'

N, L = wood.node_tree.nodes, wood.node_tree.links
def node(kind, name, **inputs):
    n = N.new(kind); n.name = n.label = name
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    return n
mp = N['Mapping.001']
wave_map = node('ShaderNodeMapping', 'Skala gelombang', Scale=GELOMBANG_SKALA)
wave = node('ShaderNodeTexNoise', 'Gelombang serat', Scale=1.0, Detail=2.0)
wave_amp = node('ShaderNodeMath', 'Gelombang amplitudo'); wave_amp.operation = 'MULTIPLY_ADD'
wave_amp.inputs[1].default_value, wave_amp.inputs[2].default_value = GELOMBANG_AMP, -GELOMBANG_AMP / 2
wave_y = node('ShaderNodeCombineXYZ', 'Gelombang melintang')
wavy = node('ShaderNodeVectorMath', 'Serat bergelombang'); wavy.operation = 'ADD'
L.new(mp.outputs['Vector'], wave_map.inputs['Vector']); L.new(wave_map.outputs['Vector'], wave.inputs['Vector'])
L.new(wave.outputs['Fac'], wave_amp.inputs[0]); L.new(wave_amp.outputs['Value'], wave_y.inputs['Y'])
L.new(mp.outputs['Vector'], wavy.inputs[0]); L.new(wave_y.outputs['Vector'], wavy.inputs[1])
for target in ('Pola serat', 'Roughness scan'):
    L.new(wavy.outputs['Vector'], N[target].inputs['Vector'])
brush_map = node('ShaderNodeMapping', 'Skala brush', Scale=BRUSH_SKALA)
brush = node('ShaderNodeTexNoise', 'Goresan brush', Scale=1.0, Detail=6.0, Roughness=0.6)
brush_bump = node('ShaderNodeBump', 'Relief brush', Strength=BRUSH_RELIEF, Distance=0.001)
L.new(wavy.outputs['Vector'], brush_map.inputs['Vector']); L.new(brush_map.outputs['Vector'], brush.inputs['Vector'])
L.new(brush.outputs['Fac'], brush_bump.inputs['Height'])
principled = next(n for n in N if n.bl_idname == 'ShaderNodeBsdfPrincipled')
L.new(N['Relief serat'].outputs['Normal'], brush_bump.inputs['Normal'])
L.new(brush_bump.outputs['Normal'], principled.inputs['Normal'])
tint = node('ShaderNodeMix', 'Warna brush'); tint.data_type, tint.blend_type = 'RGBA', 'OVERLAY'
tint.inputs['Factor'].default_value = BRUSH_WARNA
rgba = lambda socks, name: next(s for s in socks if s.name == name and s.type == 'RGBA')
L.new(N['Palet kayu'].outputs['Color'], rgba(tint.inputs, 'A')); L.new(brush.outputs['Fac'], rgba(tint.inputs, 'B'))
pore_map = node('ShaderNodeMapping', 'Skala pori', Scale=PORI_SKALA)
pore = node('ShaderNodeTexNoise', 'Pori kayu', Scale=1.0, Detail=1.0)
pore_mask = node('ShaderNodeMapRange', 'Masker pori', **{'From Min': PORI_AMBANG[0], 'From Max': PORI_AMBANG[1]})
L.new(wavy.outputs['Vector'], pore_map.inputs['Vector']); L.new(pore_map.outputs['Vector'], pore.inputs['Vector'])
L.new(pore.outputs['Fac'], pore_mask.inputs['Value'])
pore_col = node('ShaderNodeMix', 'Warna pori'); pore_col.data_type, pore_col.blend_type = 'RGBA', 'MULTIPLY'
rgba(pore_col.inputs, 'B').default_value = (PORI_GELAP,) * 3 + (1,)
L.new(pore_mask.outputs['Result'], pore_col.inputs['Factor'])
L.new(rgba(tint.outputs, 'Result'), rgba(pore_col.inputs, 'A'))
var_map = node('ShaderNodeMapping', 'Skala variasi', Scale=VARIASI_SKALA)
var = node('ShaderNodeTexNoise', 'Variasi lebar', Scale=1.0, Detail=VARIASI_DETAIL, Roughness=0.55)
L.new(wavy.outputs['Vector'], var_map.inputs['Vector']); L.new(var_map.outputs['Vector'], var.inputs['Vector'])
var_col = node('ShaderNodeMix', 'Warna variasi'); var_col.data_type, var_col.blend_type = 'RGBA', 'OVERLAY'
var_col.inputs['Factor'].default_value = VARIASI_KUAT
var_mask = node('ShaderNodeMapRange', 'Kontras variasi', **{'From Min': VARIASI_RENTANG[0], 'From Max': VARIASI_RENTANG[1]})
L.new(var.outputs['Fac'], var_mask.inputs['Value'])
L.new(rgba(pore_col.outputs, 'Result'), rgba(var_col.inputs, 'A')); L.new(var_mask.outputs['Result'], rgba(var_col.inputs, 'B'))
L.new(rgba(var_col.outputs, 'Result'), N['Hue/Saturation/Value'].inputs['Color'])
pore_bump = node('ShaderNodeBump', 'Relief pori', Strength=PORI_RELIEF, Distance=0.0005)
pore_bump.invert = True
L.new(pore_mask.outputs['Result'], pore_bump.inputs['Height'])
L.new(brush_bump.outputs['Normal'], pore_bump.inputs['Normal'])
L.new(pore_bump.outputs['Normal'], principled.inputs['Normal'])
for e, v in zip(N['Roughness serat'].color_ramp.elements, KASAR):
    e.color = (v, v, v, 1)
rough = node('ShaderNodeMath', 'Kasar pori'); rough.operation = 'MULTIPLY_ADD'; rough.inputs[1].default_value = PORI_KASAR
L.new(pore_mask.outputs['Result'], rough.inputs[0]); L.new(N['Roughness serat'].outputs['Color'], rough.inputs[2])
L.new(rough.outputs['Value'], principled.inputs['Roughness'])
principled.inputs['Specular IOR Level'].default_value, principled.inputs['Coat Weight'].default_value = SPEKULAR, COAT
principled.inputs['Coat Roughness'].default_value = COAT_KASAR
# Kilap per produk: properti objek 'ns_kurangi_kilap' (0..1; tidak ada = 0 = kilap library utuh) meredam
# Specular & Coat sebesar (1 - k). Diset di objek file produk (mis. bedside kecil), material tetap satu.
dim = node('ShaderNodeAttribute', 'Kurangi kilap'); dim.attribute_type, dim.attribute_name = 'OBJECT', 'ns_kurangi_kilap'
keep = node('ShaderNodeMath', 'Sisa kilap'); keep.operation = 'SUBTRACT'; keep.inputs[0].default_value = 1.0
L.new(dim.outputs['Fac'], keep.inputs[1])
for sock in ('Specular IOR Level', 'Coat Weight'):
    scaled = node('ShaderNodeMath', 'Kilap | ' + sock); scaled.operation = 'MULTIPLY'
    scaled.inputs[1].default_value = principled.inputs[sock].default_value
    L.new(keep.outputs['Value'], scaled.inputs[0]); L.new(scaled.outputs['Value'], principled.inputs[sock])

hitam = wood.copy(); hitam.name = 'HW | Beechwood Kayu Hitam'
HN = hitam.node_tree.nodes
for e, (pos, c) in zip(HN['Palet kayu'].color_ramp.elements, HITAM):
    e.position, e.color = pos, (*(srgb(v) for v in c), 1)
for e, v in zip(HN['Roughness serat'].color_ramp.elements, HITAM_KASAR):
    e.color = (v, v, v, 1)
HN['Arah serat'].inputs['Rotation'].default_value[2] = 1.5708     # UV handle: serat sepanjang batang (V)
for k, v in zip(('Hue', 'Saturation', 'Value'), HITAM_HSV):    # warna eboni tetap (tidak ikut koreksi walnut)
    HN['Hue/Saturation/Value'].inputs[k].default_value = v
hitam.diffuse_color = (*(srgb(v) for v in HITAM[1][1]), 1)
hitam['ns_finish_id'], hitam['ns_role'], hitam['ns_finish_nama'] = 'beechwood_kayu_hitam', 'HANDLE', 'Beechwood Kayu Hitam'
for img in bpy.data.images:
    if img.users and img.source == 'FILE' and not img.packed_file:
        img.pack()

import math
from mathutils import Vector
key, wall = bpy.data.objects['Key Sun'], bpy.data.objects['Latar / dinding']
key.data.angle = math.radians(MATAHARI_SUDUT)
excl = key.light_linking.receiver_collection
for o in bpy.data.objects:
    if o.get('ns_latar_role') == 'SAMPING' and o.name not in excl.objects:
        excl.objects.link(o)
for item in excl.collection_objects:
    item.light_linking.link_state = 'EXCLUDE'
glow = bpy.data.lights.new('Latar / gradasi dinding', 'AREA')
glow.shape, glow.size, glow.size_y = 'ELLIPSE', *GRADASI_UKURAN
glow.energy, glow.color = GRADASI_W, (1.0, 0.96, 0.91)
gl = bpy.data.objects.new('Latar / gradasi dinding', glow)
bpy.context.scene.collection.objects.link(gl)
# Anak dari dinding (ikut posisi dinding per produk). matrix_world dinding di file sumber belum
# terhitung (tidak ada di view layer), jadi pakai matrix_basis; parent inverse = identitas.
aim = (Vector(GRADASI_BIDIK) - Vector(GRADASI_POS)).to_track_quat('-Z', 'Y').to_matrix().to_4x4()
aim.translation = GRADASI_POS
gl.parent = wall
gl.matrix_parent_inverse.identity()
gl.matrix_basis = wall.matrix_basis.inverted() @ aim
gl.visible_camera = False
only_wall = bpy.data.collections.new('Gradasi | hanya dinding')
only_wall.objects.link(wall)
gl.light_linking.receiver_collection = only_wall
gl['ns_latar'], gl['ns_latar_role'] = True, 'GRADASI'

objs = {o for o in bpy.data.objects if o.get('ns_latar')}
bpy.data.libraries.write(str(OUT), objs | {wood, hitam, wall_mat, floor_mat}, fake_user=True, compress=True)
print('##LATAR', json.dumps({'objects': sorted(o.name for o in objs), 'out': str(OUT)}))
