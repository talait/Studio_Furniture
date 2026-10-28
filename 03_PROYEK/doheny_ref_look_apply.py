import bpy
s=bpy.context.scene
# ---------- Latar: dinding plester putih hangat, lantai beton abu muda
M=bpy.data.materials
wall=M['LATAR | Doheny · lantai pasir + dinding plester hangat · dinding']
floor=M['LATAR | Doheny · lantai pasir + dinding plester hangat · lantai']
wn=wall.node_tree.nodes
wn['Warna'].outputs[0].default_value=(0.92,0.90,0.87,1)
wn['Map Range'].inputs['To Min'].default_value=0.95
wn['Map Range'].inputs['To Max'].default_value=1.05
wn['Noise Texture'].inputs['Scale'].default_value=3.0
wn['Principled BSDF'].inputs['Roughness'].default_value=0.92
wn['Bump'].inputs['Strength'].default_value=0.05
fn=floor.node_tree.nodes
fn['Warna'].outputs[0].default_value=(0.21,0.205,0.2,1)
fn['Map Range'].inputs['To Min'].default_value=0.85
fn['Map Range'].inputs['To Max'].default_value=1.12
fn['Noise Texture'].inputs['Scale'].default_value=2.5
fn['Principled BSDF'].inputs['Roughness'].default_value=0.55
fn['Bump'].inputs['Strength'].default_value=0.06
# ---------- Kayu oak: lebih hangat/madu, serat lebih jelas
for name in ('DS_Oak_GrainX','DS_Oak_GrainY','DS_Oak_GrainZ'):
    nt=M[name].node_tree; n=nt.nodes
    img=n['Image Texture']; bsdf=n['Principled BSDF']
    hsv=n.get('Oak tone') or n.new('ShaderNodeHueSaturation'); hsv.name=hsv.label='Oak tone'
    hsv.location=(img.location.x+300,img.location.y+150)
    hsv.inputs['Hue'].default_value=0.515
    hsv.inputs['Saturation'].default_value=1.2
    hsv.inputs['Value'].default_value=0.62
    bc=n.get('Oak contrast') or n.new('ShaderNodeBrightContrast'); bc.name=bc.label='Oak contrast'
    bc.location=(hsv.location.x+200,hsv.location.y)
    bc.inputs['Contrast'].default_value=0.12
    for l in list(bsdf.inputs['Base Color'].links): nt.links.remove(l)
    nt.links.new(img.outputs['Color'],hsv.inputs['Color'])
    nt.links.new(hsv.outputs['Color'],bc.inputs['Color'])
    nt.links.new(bc.outputs['Color'],bsdf.inputs['Base Color'])
    n['Map Range'].inputs['To Min'].default_value=0.42
    n['Map Range'].inputs['To Max'].default_value=0.62
    n['Normal Map'].inputs['Strength'].default_value=0.45
# ---------- Lighting: matahari lembut, ambient putih
sun=bpy.data.objects['Latar / matahari']
sun.data.energy=1.6
sun.data.angle=0.35
sun.data.color=(1.0,0.96,0.91)
w=s.world.node_tree.nodes['Background']
w.inputs['Color'].default_value=(0.92,0.92,0.92,1)
w.inputs['Strength'].default_value=0.35
s.view_settings.look='AgX - Base Contrast'
s.view_settings.exposure=-0.85
# Fill rendah dikurangi agar plinth & bawah dudukan punya bayangan lembut seperti referensi
for o in s.objects:
    if o.type=='LIGHT' and o.name.endswith('/ Tengah fill') and not o.get('ref_fill_tuned'):
        if o.data.users>1: o.data=o.data.copy()
        o.data.energy*=0.55; o['ref_fill_tuned']=True
