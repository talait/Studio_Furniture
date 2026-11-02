import bpy, json, os
from mathutils import Vector
s=bpy.context.scene
if os.environ.get('RENDERVIS'):
    # uji visibilitas render: objek hide_render / koleksi hide_render dianggap tidak ada
    pass
key=bpy.data.objects['Key Sun']
to_sun=(key.matrix_world.to_quaternion()@Vector((0,0,1))).normalized()
coll=bpy.data.collections['LATAR | aktif']
latar={o.name for o in coll.objects}
prod={o.name for c in bpy.data.collections if c.name.startswith('PROD |') for o in c.all_objects}
def render_visible(o):
    if o.hide_render: return False
    def coll_hidden(c):
        return c.hide_render
    for c in o.users_collection:
        # cari koleksi induk yang hide_render
        stack=[c]; 
        par={ch.name:p for p in bpy.data.collections for ch in p.children}
        cur=c
        while cur:
            if cur.hide_render: return False
            cur=par.get(cur.name)
        return True
    return True
dg=bpy.context.evaluated_depsgraph_get()
wall=bpy.data.objects['Latar / dinding']; wy=wall.location.y; lx=bpy.data.objects['Latar / dinding kiri'].location.x
pts=[]
for i in range(60):
    for j in range(40):
        pts.append(Vector((-4.7+9.4*i/59, -4.5+(wy+4.5-0.05)*j/39, 0.001)))            # lantai
        pts.append(Vector((-4.7+9.4*i/59, wy-0.001, 0.05+4.1*j/39)))                   # dinding belakang
        pts.append(Vector((lx+0.001, -4.5+(wy+4.5)*i/59, 0.05+4.1*j/39)))              # dinding kiri
hits={}
for p in pts:
    origin=p; 
    for _ in range(6):
        ok,loc,nor,idx,obj,mat=s.ray_cast(dg,origin+to_sun*1e-3,to_sun)
        if not ok: break
        o=obj.original
        if o.name in latar or o.name in prod: break
        if render_visible(o) and o.visible_shadow:
            hits[o.name]=hits.get(o.name,0)+1; break
        origin=loc
print('##'+json.dumps(sorted(hits.items(),key=lambda x:-x[1])[:25]))
