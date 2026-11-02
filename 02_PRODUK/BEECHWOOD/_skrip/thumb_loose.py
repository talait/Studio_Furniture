"""blender -b --factory-startup --python thumb_loose.py -- in.obj skala out.png [sudut]
Impor OBJ, weld, pisah loose parts, warna acak per bagian, render Workbench 512 px."""
import bmesh
import bpy
import math
import random
import sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
obj_path, scale, out_png = argv[0], float(argv[1]), argv[2]
view = argv[3] if len(argv) > 3 else "depan"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=obj_path, forward_axis="Y", up_axis="Z", global_scale=scale)
objs = [o for o in bpy.context.selected_objects if o.type == "MESH"]
bpy.ops.object.select_all(action="DESELECT")
for o in objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.join()
o = bpy.context.object
bm = bmesh.new(); bm.from_mesh(o.data)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0002)
bm.to_mesh(o.data); bm.free()
bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.separate(type="LOOSE"); bpy.ops.object.mode_set(mode="OBJECT")
parts = [p for p in bpy.context.scene.objects if p.type == "MESH"]
random.seed(3)
for i, p in enumerate(parts):
    p.color = (random.random(), random.random(), random.random(), 1)
    p.name = f"P{i:02d}"
pts = [p.matrix_world @ v.co for p in parts for v in p.data.vertices]
lo = Vector([min(q[i] for q in pts) for i in range(3)]); hi = Vector([max(q[i] for q in pts) for i in range(3)])
center = (lo + hi) / 2; radius = (hi - lo).length / 2
scene = bpy.context.scene
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); scene.collection.objects.link(cam)
cam.data.lens = 50
d = {"depan": Vector((0.6, -1.0, 0.5)), "belakang": Vector((-0.6, 1.0, 0.5)), "atas": Vector((0.01, -0.01, 1.0)), "kanan": Vector((1.0, -0.3, 0.3))}[view].normalized()
cam.location = center + d * radius * 2.6
cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
scene.camera = cam
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"; scene.display.shading.color_type = "OBJECT"
scene.display.shading.show_cavity = True
scene.render.resolution_x, scene.render.resolution_y = 512, 384
scene.render.filepath = out_png
bpy.ops.render.render(write_still=True)
print("THUMB", out_png, len(parts), "parts")
