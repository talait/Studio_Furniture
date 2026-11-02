import bpy, sys, os
s=bpy.context.scene
tag=os.environ.get('TAG','cur')
s.render.resolution_x,s.render.resolution_y,s.render.resolution_percentage=int(os.environ.get('RX','960')),int(os.environ.get('RY','540')),100
s.cycles.samples=int(os.environ.get('SPP','40')); s.cycles.use_denoising=True
for cam in os.environ.get('CAMS','CAM_01_HERO').split(','):
    s.camera=bpy.data.objects[cam]
    # rig per angle: hanya LIGHTS untuk angle ini
    key=cam.split('_',2)[2] if cam.count('_')>=2 else ''
    for c in bpy.data.collections:
        if c.name.startswith('LIGHTS '):
            c.hide_render = not c.name.endswith('| '+key)
    s.render.filepath=os.path.join(os.environ['OUT'],f'{tag}_{cam}.png')
    bpy.ops.render.render(write_still=True)
