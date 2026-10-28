import bpy
img=bpy.data.images.load(r"C:/Users/Staff/Downloads/DOHENY/textures/oak_plank_bersih.png", check_existing=True)
img.filepath=bpy.path.relpath(img.filepath)
img.colorspace_settings.name='sRGB'
for name in ('DS_Oak_GrainX','DS_Oak_GrainY','DS_Oak_GrainZ'):
    nt=bpy.data.materials[name].node_tree; n=nt.nodes
    tex=n['Image Texture']; tex.image=img
    # Kompensasi AgX + lampu studio terang agar warna render = warna tekstur
    hsv=n.get('Oak tone') or n.new('ShaderNodeHueSaturation'); hsv.name=hsv.label='Oak tone'
    hsv.location=(tex.location.x+300,tex.location.y+150)
    hsv.inputs['Hue'].default_value=0.5
    hsv.inputs['Saturation'].default_value=1.2
    hsv.inputs['Value'].default_value=0.58
    bc=n.get('Oak contrast') or n.new('ShaderNodeBrightContrast'); bc.name=bc.label='Oak contrast'
    bc.location=(hsv.location.x+200,hsv.location.y)
    bc.inputs['Contrast'].default_value=0.08
    nt.links.new(tex.outputs['Color'],hsv.inputs['Color'])
    nt.links.new(hsv.outputs['Color'],bc.inputs['Color'])
    nt.links.new(bc.outputs['Color'],n['Principled BSDF'].inputs['Base Color'])
