# Material kaca "hammered" (palu) prosedural: lekuk kubah membulat dari Voronoi F1 halus dalam koordinat
# objek (meter), sedikit dibengkokkan noise agar tidak teratur; relief lewat Bump pada BSDF transmisi.
# Opsi: ukuran lekuk, kedalaman, warna kaca, buram (satin). Dipakai untuk pratinjau opsi & penerapan.
import bpy

OPSI = {
    'A': {'nama': 'Hammered halus (low-iron bening)', 'sel_mm': 6, 'kuat': 0.35, 'distorsi': 0.25,
          'warna': (0.97, 0.985, 0.98), 'buram': 0.0},
    'B': {'nama': 'Hammered klasik (seperti referensi)', 'sel_mm': 11, 'kuat': 0.5, 'distorsi': 0.35,
          'warna': (0.93, 0.965, 0.95), 'buram': 0.0},
    'C': {'nama': 'Hammered besar lembut (Flemish)', 'sel_mm': 22, 'kuat': 0.45, 'distorsi': 0.6,
          'warna': (0.93, 0.965, 0.95), 'buram': 0.0},
    'D': {'nama': 'Hammered klasik satin (lebih privat)', 'sel_mm': 11, 'kuat': 0.5, 'distorsi': 0.35,
          'warna': (0.95, 0.965, 0.96), 'buram': 0.18},
}


def kaca_hammered(kunci, nama=None):
    o = OPSI[kunci]
    mat = bpy.data.materials.new(nama or f'KACA | {o["nama"]}')
    mat.use_nodes = True
    N, L = mat.node_tree.nodes, mat.node_tree.links
    bsdf = N['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*o['warna'], 1)
    bsdf.inputs['Transmission Weight'].default_value = 1.0
    bsdf.inputs['IOR'].default_value = 1.52
    bsdf.inputs['Roughness'].default_value = o['buram']
    tc = N.new('ShaderNodeTexCoord')
    warp = N.new('ShaderNodeTexNoise'); warp.inputs['Scale'].default_value = 1000 / o['sel_mm'] / 3
    warp.inputs['Detail'].default_value = 2.0
    L.new(tc.outputs['Object'], warp.inputs['Vector'])
    mix = N.new('ShaderNodeMix'); mix.data_type = 'VECTOR'; mix.inputs['Factor'].default_value = o['distorsi'] * o['sel_mm'] / 1000
    L.new(tc.outputs['Object'], [s for s in mix.inputs if s.name == 'A' and s.type == 'VECTOR'][0])
    L.new(warp.outputs['Color'], [s for s in mix.inputs if s.name == 'B' and s.type == 'VECTOR'][0])
    add = N.new('ShaderNodeVectorMath'); add.operation = 'ADD'
    L.new(tc.outputs['Object'], add.inputs[0]); L.new(warp.outputs['Color'], add.inputs[1])
    scale = N.new('ShaderNodeVectorMath'); scale.operation = 'SCALE'
    scale.inputs['Scale'].default_value = o['distorsi'] * o['sel_mm'] / 1000      # geser maks ~ sebagian sel
    L.new(warp.outputs['Color'], scale.inputs[0])
    add2 = N.new('ShaderNodeVectorMath'); add2.operation = 'ADD'
    L.new(tc.outputs['Object'], add2.inputs[0]); L.new(scale.outputs['Vector'], add2.inputs[1])
    vor = N.new('ShaderNodeTexVoronoi'); vor.feature = 'SMOOTH_F1'
    vor.inputs['Scale'].default_value = 1000 / o['sel_mm']
    vor.inputs['Smoothness'].default_value = 0.6
    vor.inputs['Randomness'].default_value = 0.9
    L.new(add2.outputs['Vector'], vor.inputs['Vector'])
    dome = N.new('ShaderNodeMath'); dome.operation = 'POWER'; dome.inputs[1].default_value = 2.0   # lekuk membulat
    L.new(vor.outputs['Distance'], dome.inputs[0])
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = o['kuat']
    bump.inputs['Distance'].default_value = o['sel_mm'] / 1000 * 0.25
    L.new(dome.outputs['Value'], bump.inputs['Height']); L.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    for n in (mix, add):            # sisa percobaan, tidak dipakai
        N.remove(n)
    mat['ns_role'] = 'KACA'
    mat['ns_catatan'] = f'Kaca hammered opsi {kunci}: {o["nama"]}, sel ~{o["sel_mm"]} mm, IOR 1.52'
    return mat
