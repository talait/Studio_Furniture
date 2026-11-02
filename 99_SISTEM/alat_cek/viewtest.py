import bpy, json
from mathutils import Vector
s=bpy.context.scene; dg=bpy.context.evaluated_depsgraph_get(); out={}
for cam in [o for o in s.objects if o.type=='CAMERA' and o.get('ns_shot') in ('HERO','FRONT','LEFT','SIDE','SIDE_L','BACK')]:
    s.camera=cam; s.frame_set(s.frame_current); dg=bpy.context.evaluated_depsgraph_get()
    fr=cam.data.view_frame(scene=s); M=cam.matrix_world; o0=M.translation
    miss=0; n=0
    for i in range(25):
        for j in range(15):
            a,b=i/24,j/14
            p=fr[2].lerp(fr[1],a).lerp(fr[3].lerp(fr[0],a),b)   # kiri-bawah..kanan-atas
            d=(M@p-o0).normalized(); origin=o0.copy(); hit=False
            for _ in range(5):
                ok,loc,nor,idx,obj,mat=s.ray_cast(dg,origin+d*1e-4,d)
                if not ok: break
                if nor.dot(d)>0 and obj.original.name.startswith('Latar / dinding'): origin=loc; continue  # dinding tembus dari belakang
                hit=True; break
            n+=1; miss+= (not hit)
    out[cam['ns_shot']]=f'{miss}/{n} ray ke langit kosong'
print('##'+json.dumps(out))
