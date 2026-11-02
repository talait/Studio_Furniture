# Kayu Doheny v2 (disetujui di night table / Doheny Side Table, Oct 2026): lebih terang sedikit dan lebih
# lembut seperti foto referensi 6 Drawers: serat panjang landai (pola diregang searah serat), kontras serat
# rendah tapi tetap bervariasi, relief tipis tanpa bintik, kilap satin (roughness lebih rendah).
# Nilai absolut (aman dijalankan berulang). Dipakai juga oleh 99_SISTEM/doheny_look.py.
# Jalankan ke sesi: blender -b <sesi>.blend --python 99_SISTEM/kayu_doheny_v2.py   (SAVE=1 untuk menyimpan)
import bpy, os
KAYU = {
    'kontras': 0.22, 'saturasi': 0.68, 'nilai': 0.90,
    'palet_srgb': [(0.0, (0.57, 0.385, 0.23)), (0.6, (0.67, 0.48, 0.31)), (1.0, (0.77, 0.58, 0.40))],
    'palet_rapat': 0.75,            # 1 = palet asli; <1 = garis serat lebih dekat ke warna tengah (lebih lembut)
    'skala_serat': (0.8, 1.2),      # (searah serat, melintang): <1 memanjangkan garis, >1 merapatkan
    'relief': 0.05,
    'roughness': (0.32, 0.50),
}


def srgb_to_linear(c):
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]


def pakai_kayu_v2(mat, k=KAYU):
    N = mat.node_tree.nodes
    N['Oak contrast'].inputs['Contrast'].default_value = k['kontras']
    N['Hue/Saturation/Value'].inputs['Saturation'].default_value = k['saturasi']
    N['Hue/Saturation/Value'].inputs['Value'].default_value = k['nilai']
    base = [(pos, srgb_to_linear(c)) for pos, c in k['palet_srgb']]
    mid = base[1][1]
    for el, (pos, c) in zip(N['Palet kayu'].color_ramp.elements, base):
        el.position = pos
        el.color = tuple(m + (x - m) * k['palet_rapat'] for x, m in zip(c, mid)) + (1.0,)
    N['Mapping.001'].inputs['Scale'].default_value = (*k['skala_serat'], 1.0)
    N['Relief serat'].inputs['Strength'].default_value = k['relief']
    r = N['Roughness serat'].color_ramp.elements
    r[0].color, r[1].color = (k['roughness'][0],) * 3 + (1.0,), (k['roughness'][1],) * 3 + (1.0,)
    mat['ns_kayu_versi'] = 2


if __name__ == '__main__':
    mats = [m for m in bpy.data.materials if m.get('ns_finish_id') == 'doheny_cherry_alami'
            and not m.library and m.node_tree and 'Palet kayu' in m.node_tree.nodes]
    for m in mats:
        pakai_kayu_v2(m)
    print('##kayu_v2', bpy.path.basename(bpy.data.filepath), [m.name for m in mats])
    if mats and os.environ.get('SAVE'):
        bpy.ops.wm.save_mainfile(); print('##saved')
