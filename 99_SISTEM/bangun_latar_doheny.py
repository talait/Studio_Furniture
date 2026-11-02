# Bangun 02_PRODUK/_LATAR/Doheny_Lifestyle.blend dari file Lamp Table yang sudah disetujui:
# ruang lifestyle (lantai, dinding, plafon), Key Sun + Sky Fill (+ light linking), dan finish kayu.
# Jalankan: blender -b 02_PRODUK/_LATAR/Doheny_Lifestyle_SUMBER.blend --python 99_SISTEM/bangun_latar_doheny.py
# (SUMBER = salinan file Lamp Table sebelum diganti ke preset; jangan dibuka/disimpan sebagai sesi kerja)
import bpy, json, math
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '02_PRODUK' / '_LATAR' / 'Doheny_Lifestyle.blend'
FIN = 'FIN | Doheny Cherry Alami'

src = bpy.data.materials['LT_Oak_Natural']
mat = src.copy(); mat.name = FIN
N, L = mat.node_tree.nodes, mat.node_tree.links
uv = next(n for n in N if n.bl_idname == 'ShaderNodeUVMap'); uv.uv_map = ''     # UV aktif produk mana pun
rot = N.new('ShaderNodeMapping'); rot.name = rot.label = 'Arah serat'
rot.location = (uv.location.x + 180, uv.location.y - 250)
for link in [l for l in L if l.from_node == uv]:
    to = link.to_socket; L.remove(link); L.new(rot.outputs['Vector'], to)
L.new(uv.outputs['UV'], rot.inputs['Vector'])
# Tiap bagian (laci, panel) mengambil potongan serat berbeda: geser UV acak per objek.
# Tekstur tile menyambung di kedua arah, jadi geseran berapa pun tidak memunculkan garis.
info = N.new('ShaderNodeObjectInfo'); info.location = (rot.location.x, rot.location.y - 380)
jitter = N.new('ShaderNodeCombineXYZ'); jitter.name = jitter.label = 'Geser serat acak'
jitter.location = (rot.location.x + 180, rot.location.y - 380)
for axis, factor in (('X', 13.7), ('Y', 5.3)):
    m = N.new('ShaderNodeMath'); m.operation = 'MULTIPLY'; m.inputs[1].default_value = factor
    m.location = (rot.location.x + 30, rot.location.y - (300 if axis == 'X' else 460))
    L.new(info.outputs['Random'], m.inputs[0]); L.new(m.outputs[0], jitter.inputs[axis])
add = N.new('ShaderNodeVectorMath'); add.operation = 'ADD'; add.location = (rot.location.x + 360, rot.location.y - 250)
for link in [l for l in L if l.from_node == rot]:
    to = link.to_socket; L.remove(link); L.new(add.outputs['Vector'], to)
L.new(rot.outputs['Vector'], add.inputs[0]); L.new(jitter.outputs['Vector'], add.inputs[1])
# "Kayu universal": satu peta pola abu-abu (terang = kayu terang, gelap = garis serat; dibuat dengan
# 03_PROYEK/doheny_kayu_oak_texture.py) menggerakkan warna, roughness, dan bump sekaligus, sehingga
# kilap & relief mengikuti garis yang sama dengan warna. Gaya warna lain cukup mengganti 'Palet kayu'.
def srgb_to_linear(c):
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)


def ramp(name, stops, loc):
    node = N.new('ShaderNodeValToRGB'); node.name = node.label = name; node.location = loc
    elems = node.color_ramp.elements
    while len(elems) < len(stops):
        elems.new(0.5)
    for el, (pos, col) in zip(elems, stops):
        el.position, el.color = pos, col
    return node


hsv = N['Hue/Saturation/Value']
bsdf = N['Principled BSDF']
color = hsv.inputs['Color'].links[0].from_node                   # gambar warna lama (Image Texture.002)
vec = color.inputs['Vector'].links[0].from_socket                 # Mapping.001: UV meter + arah serat + geser acak
# Pola dari scan kayu asli (03_PROYEK/doheny_pola_dari_scan.py): 1 tile = 1 m x 1 m, serat sepanjang U.
SCAN = 'silver_oak_veneer_01'
SCAN_DIR = ROOT / '02_PRODUK' / '_FINISH' / 'tekstur_dasar' / SCAN
vec.node.inputs['Scale'].default_value = (1.0, 1.0, 1.0)
vec.node.inputs['Location'].default_value = (0.0, 0.0, 0.0)


def scan_image(path, name):
    img = bpy.data.images.load(str(path)); img.colorspace_settings.name = 'Non-Color'; img.pack()
    node = N.new('ShaderNodeTexImage'); node.name = node.label = name
    node.image, node.interpolation = img, 'Cubic'
    L.new(vec, node.inputs['Vector'])
    return node


pola = scan_image(ROOT / '02_PRODUK' / '_LATAR' / 'tekstur_Doheny' / f'doheny_pola_{SCAN}_4k.png', 'Pola serat')
pola.location = color.location
x, y = pola.location
# Warna: palet Doheny yang disetujui (sRGB terang / tengah / garis), HSV & kontras tetap sama.
palet = ramp('Palet kayu', [(0.0, srgb_to_linear((0.57, 0.385, 0.23))), (0.6, srgb_to_linear((0.67, 0.48, 0.31))),
                            (1.0, srgb_to_linear((0.77, 0.58, 0.40)))], (x + 300, y + 200))
L.new(pola.outputs['Color'], palet.inputs['Fac']); L.new(palet.outputs['Color'], hsv.inputs['Color'])
hsv.inputs['Hue'].default_value, hsv.inputs['Saturation'].default_value, hsv.inputs['Value'].default_value = 0.508, 0.8, 1.15
N['Oak contrast'].inputs['Contrast'].default_value = 0.12
# Roughness & relief dari peta scan yang sama -> kilap dan lekuk tepat mengikuti garis serat asli.
rough_img = scan_image(SCAN_DIR / f'{SCAN}_rough_4k.jpg', 'Roughness scan'); rough_img.location = (x, y - 300)
kasar = ramp('Roughness serat', [(0.0, (0.42, 0.42, 0.42, 1)), (1.0, (0.62, 0.62, 0.62, 1))], (x + 300, y - 300))
L.new(rough_img.outputs['Color'], kasar.inputs['Fac']); L.new(kasar.outputs['Color'], bsdf.inputs['Roughness'])
# Relief: bump dari pola scan (bukan normal map tangent: UV diputar 'Arah serat' untuk produk serat V,
# normal map tangent akan salah arah, bump tidak). Garis serat sedikit masuk; jarak dalam meter.
bump = N.new('ShaderNodeBump'); bump.name = bump.label = 'Relief serat'; bump.location = (x + 300, y - 600)
bump.inputs['Strength'].default_value = 0.12; bump.inputs['Distance'].default_value = 0.0006
L.new(pola.outputs['Color'], bump.inputs['Height']); L.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
# Peta ash lama (roughness & normal dari kayu lain, seratnya tidak cocok) dan gambar warna lama dibuang.
keep = {'Pola serat', 'Roughness scan'}
for node in [n for n in N if n.bl_idname in {'ShaderNodeTexImage', 'ShaderNodeNormalMap', 'ShaderNodeMapRange'}
             and n.name not in keep]:
    N.remove(node)
for node in [n for n in N if n.bl_idname == 'ShaderNodeMapping' and n.name not in ('Arah serat',)
             and not any(l.to_node.bl_idname == 'ShaderNodeTexImage' for out in n.outputs for l in out.links)]:
    N.remove(node)
mat['ns_finish_id'] = 'doheny_cherry_alami'; mat['ns_role'] = 'WOOD_A'; mat['ns_finish_nama'] = 'Doheny Cherry Alami'
for img in bpy.data.images:
    if img.users and img.source == 'FILE' and not img.packed_file:
        img.pack()

# Kalibrasi tampilan terhadap foto referensi (matahari, dinding, lantai, warna kayu).
exec(compile((ROOT / '99_SISTEM' / 'doheny_look.py').read_text(encoding='utf-8'), 'doheny_look.py', 'exec'))

coll = bpy.data.collections['LATAR | aktif']
objs = set(coll.objects)
for o in objs:
    o['ns_latar'] = True
bpy.data.objects['Sky Fill']['ns_latar_role'] = 'LANGIT'
bpy.data.libraries.write(str(OUT), objs | {mat}, fake_user=True, compress=True)

s = bpy.context.scene
bg = next(n for n in s.world.node_tree.nodes if n.bl_idname == 'ShaderNodeBackground')
print('##LATAR', json.dumps({'objects': sorted(o.name for o in objs), 'dunia': [round(v, 4) for v in bg.inputs[0].default_value[:3]],
      'kuat': round(bg.inputs[1].default_value, 4), 'view': [s.view_settings.view_transform, s.view_settings.look, s.view_settings.exposure],
      'linked': bpy.data.objects['Key Sun'].light_linking.receiver_collection.name}))
