import bpy, sys, importlib.util, json
from pathlib import Path
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
ROOT=Path(r"C:/Users/Staff/Documents/Studio_Furniture")
spec=importlib.util.spec_from_file_location('nakas_studio_tools',ROOT/'99_SISTEM/nakas_studio_tools.py')
ns=importlib.util.module_from_spec(spec);sys.modules[spec.name]=ns;spec.loader.exec_module(ns);ns.register()
s=bpy.context.scene
import os; name=os.environ['SESI']
path=ROOT/'03_PROYEK'/(name+'.blend')
(ROOT/'04_HASIL_RENDER'/name).mkdir(parents=True,exist_ok=True)
s.ns_studio.output='//../04_HASIL_RENDER/'+name+'/'
s.render.filepath=s.ns_studio.output+'preview.png'
s.ns_studio.preview_mode='FAST'; ns.apply_preview(s)
bpy.ops.wm.save_as_mainfile(filepath=str(path))
r=bpy.ops.ns.import_product(filepath=os.environ['SRC'])
print('##import',r)
st=s.ns_studio
out={'latar':s.get('ns_latar'),'framing':st.framing,'res':[s.render.resolution_x,s.render.resolution_y],
 'view':[s.view_settings.view_transform,s.view_settings.look,round(s.view_settings.exposure,2)],
 'rig_hidden':bpy.data.collections[ns.RIG_COLLECTION].hide_render,'product':st.product.name if st.product else None}
mats={}
for o in st.product.all_objects:
    if o.type=='MESH':
        for m in o.data.materials:
            if m: mats[m.name]=mats.get(m.name,0)+1
out['mats']=mats
fm=bpy.data.materials.get('FIN | Doheny Cherry Alami')
out['grain']=[fm.get('ns_grain'),round(fm.node_tree.nodes['Arah serat'].inputs['Rotation'].default_value[2],3)] if fm else None
out['latar_objs']={o.name:[o.get('ns_latar_role'),[round(v,2) for v in o.location],o.hide_render] for o in bpy.data.collections['LATAR | aktif'].objects}
out['keysun_link']=bpy.data.objects['Key Sun'].light_linking.receiver_collection.name if bpy.data.objects['Key Sun'].light_linking.receiver_collection else None
lo,hi=ns.product_bounds(s); out['bounds']=[[round(v,3) for v in lo],[round(v,3) for v in hi]]
for shot in ns.SHOT_IDS:
    cam=ns.camera_for(s,shot)
    if cam is None: continue
    ns.use_camera(s,cam); bpy.context.view_layer.update(); lo,hi=ns.product_bounds(s)
    pts=[world_to_camera_view(s,cam,Vector((x,y,z))) for x in (lo.x,hi.x) for y in (lo.y,hi.y) for z in (lo.z,hi.z)]
    out[shot]={'x':[round(min(p.x for p in pts),3),round(max(p.x for p in pts),3)],'y':[round(min(p.y for p in pts),3),round(max(p.y for p in pts),3)],'cam':[round(v,2) for v in cam.location]}
ns.select_shot(s,'HERO')
print('##'+json.dumps(out))
bpy.ops.wm.save_mainfile()
print('##saved',path)
