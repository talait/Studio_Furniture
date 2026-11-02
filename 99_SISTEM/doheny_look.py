# Tampilan Doheny disamakan dengan foto referensi 6 Drawers (Oct 2026), dikalibrasi dengan render kecil:
#  - Key Sun dari samping-depan (az 65) dan rendah (el 28) -> bayangan lantai panjang; sudut 12 deg -> tepi
#    bayangan blur lembut; Sky Fill 5 agar bayangan tetap terbaca; depan laci sedikit teduh,
#    top & sisi kanan terang, bayangan lantai jelas memanjang ke kiri
#  - dinding greige lebih terang, lantai beton terang + bintik agregat, kayu v2: madu terang, serat lembut + satin (kayu_doheny_v2.py)
# Dipakai 99_SISTEM/bangun_latar_doheny.py (library preset) dan bisa dijalankan ke sesi Doheny yang ada.
# Nilai bisa ditimpa lewat env (mis. SUN_AZ=60); HW=r,g,b mengganti warna handle 'HW | Olive matte (cat)'.
import bpy, os, math, json
from mathutils import Vector
E=lambda k,d: float(os.environ.get(k,d))
D=bpy.data
def sun(name, energy, angle, az, el):
    o=D.objects[name]; o.data.energy=energy; o.data.angle=math.radians(angle)
    a,e=math.radians(az),math.radians(el)
    to=Vector((math.sin(a)*math.cos(e),-math.cos(a)*math.cos(e),math.sin(e)))
    o.rotation_euler=(-to).to_track_quat('-Z','Y').to_euler()
sun('Key Sun',E('SUN_E',27),E('SUN_ANG',12),E('SUN_AZ',65),E('SUN_EL',28))
D.objects['Sky Fill'].data.energy=E('SKY_E',5)
# dinding
w=D.materials['Lifestyle | Matte Off-White'].node_tree.nodes['Principled BSDF']
wc=[float(x) for x in os.environ.get('WALL','0.88,0.83,0.78').split(',')]
w.inputs['Base Color'].default_value=(*wc,1)
# lantai
fm=D.materials['Lifestyle | Lantai Semen Microcement']; N=fm.node_tree.nodes; L=fm.node_tree.links
ramp=next(n for n in N if n.bl_idname=='ShaderNodeValToRGB')
k=E('FLOOR_K',1.7); sat=E('FLOOR_SAT',0.55)
con=E('FLOOR_CON',0.9); mean=[(a+b)/2 for a,b in zip((0.20,0.185,0.165),(0.46,0.43,0.395))]
for el,base in zip(ramp.color_ramp.elements,((0.20,0.185,0.165),(0.46,0.43,0.395))):
    base=[m+(b-m)*con for m,b in zip(mean,base)]
    g=sum(base)/3; c=[ (g+(b-g)*sat)*k for b in base]; el.color=(*c,1)
def ci(node,name):  # soket warna (RGBA) pada ShaderNodeMix
    return next(x for x in node.inputs if x.name==name and x.type=='RGBA')
def co(node):
    return next(x for x in node.outputs if x.type=='RGBA')
if E('SPECKLE',1)>0 and 'Bintik' not in N:
    bsdf=N['Principled BSDF'] if 'Principled BSDF' in N else next(n for n in N if n.bl_idname=='ShaderNodeBsdfPrincipled')
    geo=next(n for n in N if n.bl_idname=='ShaderNodeNewGeometry')
    vor=N.new('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value=E('SPECK_SCALE',60); vor.feature='F1'
    L.new(geo.outputs['Position'],vor.inputs['Vector'])
    dots=N.new('ShaderNodeMapRange'); dots.inputs['From Min'].default_value=0.0; dots.inputs['From Max'].default_value=E('SPECK_SIZE',0.2)
    dots.inputs['To Min'].default_value=1.0; dots.inputs['To Max'].default_value=0.0; dots.clamp=True
    L.new(vor.outputs['Distance'],dots.inputs['Value'])
    tone=N.new('ShaderNodeMath'); tone.operation='GREATER_THAN'; tone.inputs[1].default_value=E('SPECK_LIGHT',0.85)
    L.new(vor.outputs['Color'],tone.inputs[0])            # sebagian bintik gelap, sebagian terang
    mix=N.new('ShaderNodeMix'); mix.data_type='RGBA'; mix.name='Bintik'
    src=bsdf.inputs['Base Color'].links[0].from_socket
    dark=N.new('ShaderNodeMix'); dark.data_type='RGBA'; dark.blend_type='MULTIPLY'; dark.inputs['Factor'].default_value=1
    L.new(src,ci(dark,'A')); ci(dark,'B').default_value=(*[E('SPECK_DARK',0.32)]*3,1)
    light=N.new('ShaderNodeMix'); light.data_type='RGBA'; light.blend_type='SCREEN'; light.inputs['Factor'].default_value=0.6
    L.new(src,ci(light,'A')); ci(light,'B').default_value=(1,1,1,1)
    pick=N.new('ShaderNodeMix'); pick.data_type='RGBA'
    L.new(tone.outputs[0],pick.inputs['Factor']); L.new(co(dark),ci(pick,'A')); L.new(co(light),ci(pick,'B'))
    L.new(dots.outputs['Result'],mix.inputs['Factor']); L.new(src,ci(mix,'A')); L.new(co(pick),ci(mix,'B'))
    L.new(co(mix),bsdf.inputs['Base Color'])
hw=os.environ.get('HW')
if hw:
    h=D.materials.get('HW | Olive matte (cat)')
    if h: h.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(*[float(x) for x in hw.split(',')],1)
# kayu
# kayu v2 (serat lembut + satin) dari kayu_doheny_v2.py; WOOD_V/S/C tetap bisa menimpa
# (__file__ = skrip ini, atau bangun_latar_doheny.py yang meng-exec-nya; keduanya di 99_SISTEM)
_kv2={}
_p=os.path.join(os.path.dirname(os.path.abspath(__file__)),'kayu_doheny_v2.py')
exec(compile(open(_p,encoding='utf-8').read().split("if __name__ == '__main__':")[0],_p,'exec'),_kv2)
_k=dict(_kv2['KAYU'],nilai=E('WOOD_V',_kv2['KAYU']['nilai']),saturasi=E('WOOD_S',_kv2['KAYU']['saturasi']),kontras=E('WOOD_C',_kv2['KAYU']['kontras']))
_kv2['pakai_kayu_v2'](D.materials['FIN | Doheny Cherry Alami'],_k)
if os.environ.get('SAVE'): bpy.ops.wm.save_mainfile(); print('##saved')
