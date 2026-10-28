bl_info = {
    'name': 'Nakas Studio', 'author': 'Nakas Studio', 'version': (2, 4, 0),
    'blender': (4, 5, 0), 'location': 'View 3D > Sidebar > Nakas Studio',
    'description': 'Studio nakas, pergantian produk dan finish, kamera, dan batch render',
    'category': '3D View',
}

import bpy
import importlib.util
import json
import math
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from mathutils import Matrix, Vector
from bpy.props import (BoolProperty, EnumProperty, FloatProperty,
                       PointerProperty, StringProperty)
from bpy_extras.io_utils import ImportHelper

SHOTS = [
    ('HERO', '01 · Hero 3/4 kanan', 'Tampilan utama produk'),
    ('FRONT', '02 · Depan', 'Tampak depan'),
    ('LEFT', '03 · 3/4 kiri', 'Sisi kiri dan depan'),
    ('SIDE', '04 · Samping kanan', 'Profil dan kedalaman'),
    ('DETAIL', '05 · Detail', 'Detail laci dan tekstur; atur target bila perlu'),
    ('SIDE_L', '06 · Samping kiri', 'Profil kiri; produk diputar 90° agar latar tetap seamless'),
    ('BACK', '07 · Belakang 3/4', 'Sisi belakang; produk diputar 180° agar latar tetap seamless'),
    ('BASE', '08 · Detail kaki / bawah', 'Close-up sudut rendah: plinth, kaki, dan sambungan bawah'),
    ('CLOSEUP', '09 · Close-up material', 'Close-up tekstur, jahitan, dan sambungan rangka'),
]
SHOT_IDS = [item[0] for item in SHOTS]
SHOT_BUTTONS = {'HERO': 'Hero kanan', 'FRONT': 'Depan', 'LEFT': 'Hero kiri', 'SIDE': 'Samping kanan',
                'DETAIL': 'Detail produk', 'SIDE_L': 'Samping kiri', 'BACK': 'Belakang',
                'BASE': 'Detail kaki', 'CLOSEUP': 'Close-up'}
# Angle baru memakai rig lampu angle sumber (posisi kamera relatif sama).
SHOT_LIGHT_SOURCE = {'SIDE_L': 'FRONT', 'BACK': 'HERO', 'BASE': 'DETAIL', 'CLOSEUP': 'DETAIL'}

# Factory values, never captured from the user's edited lights.
# Profiles keep the original studio and the realistic studio independent.
LIGHTING_DEFAULTS = {
    'NAKAS': {
        'V1': {
            'HERO': (140, 38, 100, 45, 14), 'FRONT': (125, 48, 85, 40, 16),
            'LEFT': (135, 43, 95, 45, 14), 'SIDE': (130, 55, 110, 40, 12),
            'DETAIL': (115, 28, 120, 32, 12),
        },
        'V2': {
            'HERO': (238, 64.6, 170, 76.5, 24), 'FRONT': (212.5, 81.6, 144.5, 68, 28),
            'LEFT': (229.5, 73.1, 161.5, 76.5, 24), 'SIDE': (221, 93.5, 187, 68, 20),
            'DETAIL': (195.5, 47.6, 204, 54.4, 20),
        },
    },
}
for _profiles in LIGHTING_DEFAULTS.values():
    for _watts in _profiles.values():
        for _shot, _source in SHOT_LIGHT_SOURCE.items():
            _watts.setdefault(_shot, _watts[_source])
# Key, Fill, Rim, Top = mode awal. Tengah = softbox rendah tepat di depan produk,
# diarahkan ke rongga rak/laci agar area tengah tidak gelap (dipasang tambah_lampu_tengah.py).
LIGHT_ROLES = ('Key', 'Fill', 'Rim', 'Top', 'Tengah')

# Finish: material produk diberi peran (ns_role), bukan nama finish. Library
# 02_PRODUK/_FINISH menyediakan material FIN | ... (kayu) dan HW | ... (handle).
FINISH_LIBRARY = Path('02_PRODUK') / '_FINISH' / 'Finish_Library.blend'
FINISH_MANIFEST = Path('02_PRODUK') / '_FINISH' / 'finishes.json'
FINISH_ROLES = (('WOOD_A', 'finish_wood', 'Kayu utama'), ('HANDLE', 'finish_handle', 'Handle'))
_finish_catalog = {'mtime': None, 'items': {}}


def finish_catalog():
    """Daftar finish per peran dari finishes.json: {peran: [(id, nama, nama_material)]}."""
    root = package_root()
    path = root / FINISH_MANIFEST if root else None
    if not path or not path.is_file():
        _finish_catalog['items'] = {}
        return {}
    mtime = path.stat().st_mtime
    if _finish_catalog['mtime'] != mtime:
        data = json.loads(path.read_text(encoding='utf-8'))
        items = {}
        for item in data.get('finish', []):
            items.setdefault(item.get('peran', 'WOOD_A'), []).append((item['id'], item['nama'], 'FIN | ' + item['nama']))
        for item in data.get('hardware', []):
            items.setdefault(item.get('peran', 'HANDLE'), []).append((item['id'], item['nama'], 'HW | ' + item['nama']))
        _finish_catalog.update(mtime=mtime, items=items,
                               bases=sorted(data.get('tekstur_dasar', {})),
                               base_of={f['id']: f.get('tekstur_dasar', '?') for f in data.get('finish', [])})
    return _finish_catalog['items']


def pipeline_module(name):
    """Muat modul dari 99_SISTEM/pipeline milik paket (tanpa cache import)."""
    root = package_root()
    if not root:
        raise ValueError('Buka file dari dalam paket Studio_Furniture terlebih dahulu.')
    path = root / '99_SISTEM' / 'pipeline' / (name + '.py')
    spec = importlib.util.spec_from_file_location('ns_pipeline_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def product_finish_materials(scene, role):
    """Material finish yang tertanam di produk aktif (dibawa dari file produk), per peran."""
    root = root_for(scene)
    if root is None:
        return []
    allowed = set(str(v) for v in root.get('ns_finishes', []))
    found = []
    for mat in bpy.data.materials:
        fid = mat.get('ns_finish_id')
        if not fid or mat.library or str(fid).endswith('.lama') or mat.get('ns_role') != role:
            continue
        if role == 'WOOD_A' and allowed and str(fid) not in allowed:
            continue
        found.append((str(fid), str(mat.get('ns_finish_nama', mat.name)), mat.name))
    return found


def available_finishes(scene, role):
    """Finish yang bisa dipilih: tertanam di produk dulu, lalu library global (hardware)."""
    items = product_finish_materials(scene, role)
    seen = {fid for fid, _, _ in items}
    for fid, nama, mat in finish_catalog().get(role, []):
        if fid not in seen:
            items.append((fid, nama, mat))
    return items


def lib_finish_items(settings, context):
    scene = context.scene if context else bpy.context.scene
    items = []
    for fid, nama, mat_name in product_finish_materials(scene, 'WOOD_A'):
        mat = bpy.data.materials.get(mat_name)
        base = str(mat.get('ns_finish_dasar', '?')) if mat else '?'
        items.append((fid, f'{nama} · {base}', mat_name))
    return items or [('', '— produk belum punya finish —', '')]


def lib_tekstur_items(settings, context):
    finish_catalog()
    return [(b, b, '') for b in _finish_catalog.get('bases', [])] or [('', '— tidak ada —', '')]


def material_role(mat):
    """Peran material: prop ns_role, nama 'ROLE | X', atau tebakan dari metallic."""
    if mat is None:
        return None
    role = mat.get('ns_role')
    if role:
        return str(role)
    if mat.name.startswith('ROLE | '):
        return mat.name.split('|', 1)[1].strip().split('.')[0]
    return 'HANDLE' if mat.metallic >= 0.5 else 'WOOD_A'


def product_slots(scene):
    """{peran: [(obj, index_slot)]} untuk produk aktif."""
    slots = {}
    coll = scene.ns_studio.product
    if not coll:
        return slots
    for obj in coll.all_objects:
        if obj.type != 'MESH':
            continue
        for index, slot in enumerate(obj.material_slots):
            role = material_role(slot.material)
            if role:
                slots.setdefault(role, []).append((obj, index))
    return slots


def current_finish(scene, role):
    for obj, index in product_slots(scene).get(role, []):
        mat = obj.material_slots[index].material
        if mat and mat.get('ns_finish_id'):
            return str(mat['ns_finish_id'])
    return ''


def finish_material(finish_id, material_name, refresh=False):
    """Material finish yang sudah ada di file, atau append dari library (tanpa link).
    refresh=True memaksa append ulang (setelah library dibangun ulang); salinan lama ditandai '(lama)'."""
    for mat in bpy.data.materials:
        if mat.get('ns_finish_id') == finish_id and not mat.library:
            if not refresh:
                return mat
            mat['ns_finish_id'] = finish_id + '.lama'
            mat.name = mat.name + ' (lama)'
    root = package_root()
    path = root / FINISH_LIBRARY if root else None
    if not path or not path.is_file():
        raise ValueError('Finish_Library.blend tidak ditemukan di 02_PRODUK/_FINISH.')
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        if material_name not in src.materials:
            raise ValueError(f'Material {material_name} tidak ada di library.')
        dst.materials = [material_name]
    mat = dst.materials[0]
    mat['ns_finish_id'] = finish_id
    return mat


def apply_finish(scene, role, finish_id, refresh=False):
    """Pasang finish ke semua slot peran tersebut pada produk aktif; kembalikan jumlah slot."""
    entry = next((e for e in available_finishes(scene, role) if e[0] == finish_id), None)
    if entry is None:
        raise ValueError(f'Finish {finish_id} tidak ada di produk maupun library untuk peran {role}.')
    targets = product_slots(scene).get(role, [])
    if not targets:
        raise ValueError('Produk aktif tidak punya material dengan peran ' + role + '.')
    mat = finish_material(finish_id, entry[2], refresh)
    mat['ns_role'] = role
    for obj, index in targets:
        obj.material_slots[index].material = mat
    root = root_for(scene)
    if root is not None:
        root['ns_finish_' + role.lower()] = finish_id
    return len(targets)


def finish_items(role, prop_name):
    def items(settings, context):
        scene = context.scene if context else bpy.context.scene
        allowed = None
        root = root_for(scene) if scene and scene.get('ns_ready') else None
        if root is not None and root.get('ns_finishes'):
            allowed = set(str(v) for v in root['ns_finishes'])
        result = [(fid, nama, mat) for fid, nama, mat in available_finishes(scene, role)
                  if allowed is None or fid in allowed or role != 'WOOD_A']
        return result or [('', '— tidak ada —', 'Produk belum membawa finish')]
    return items


def finish_updated(role, prop_name):
    def update(settings, context):
        scene = context.scene
        if not scene.get('ns_ready') or settings.get('_finish_guard'):
            return
        value = getattr(settings, prop_name)
        if not value or value == current_finish(scene, role):
            return
        try:
            count = apply_finish(scene, role, value)
            settings['_finish_pesan'] = f'{count} bagian diganti ke {value}.'
        except ValueError as exc:
            settings['_finish_pesan'] = 'Gagal: ' + str(exc)
        for area in context.screen.areas if context.screen else []:
            area.tag_redraw()
    return update


def lib_tekstur_updated(settings, context):
    """Memilih tekstur dasar langsung memasang varian finish produk yang memakai tekstur itu (bila ada)."""
    scene = context.scene
    if not scene.get('ns_ready') or not settings.lib_tekstur:
        return
    for fid, nama, mat_name in product_finish_materials(scene, 'WOOD_A'):
        mat = bpy.data.materials.get(mat_name)
        if mat and str(mat.get('ns_finish_dasar', '')) == settings.lib_tekstur and fid != current_finish(scene, 'WOOD_A'):
            try:
                apply_finish(scene, 'WOOD_A', fid)
                sync_finish_props(scene)
                settings['_finish_pesan'] = f'Varian {nama} dipasang.'
            except ValueError as exc:
                settings['_finish_pesan'] = 'Gagal: ' + str(exc)
            break


def sync_finish_props(scene):
    """Samakan dropdown dengan finish yang sedang terpasang (tanpa memicu apply)."""
    settings = scene.ns_studio
    settings['_finish_guard'] = True
    try:
        for role, prop_name, _ in FINISH_ROLES:
            current = current_finish(scene, role)
            if current and current != getattr(settings, prop_name):
                try:
                    setattr(settings, prop_name, current)
                except TypeError:
                    pass
    finally:
        settings['_finish_guard'] = False


class NS_OT_ApplyFinish(bpy.types.Operator):
    bl_idname = 'ns.apply_finish'
    bl_label = 'Pasang finish'
    bl_description = 'Pasang finish dari library ke semua bagian produk dengan peran ini; file produk sumber tidak berubah'
    bl_options = {'REGISTER', 'UNDO'}
    role: StringProperty(default='WOOD_A')
    finish_id: StringProperty(default='')

    def execute(self, context):
        scene = context.scene
        prop_name = next((p for r, p, _ in FINISH_ROLES if r == self.role), None)
        finish_id = self.finish_id or (getattr(scene.ns_studio, prop_name) if prop_name else '')
        try:
            count = apply_finish(scene, self.role, finish_id)
        except ValueError as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        sync_finish_props(scene)
        self.report({'INFO'}, f'{count} bagian memakai finish {finish_id}.')
        return {'FINISHED'}


class NS_OT_AddBaseTexture(bpy.types.Operator, ImportHelper):
    bl_idname = 'ns.tambah_tekstur_dasar'
    bl_label = 'Tambah tekstur dasar'
    bl_description = 'Daftarkan unduhan Poly Haven (zip, folder hasil ekstrak, atau file di dalamnya) ke 02_PRODUK/_FINISH/tekstur_dasar; EXR diubah ke JPG'
    filter_glob: StringProperty(default='*.zip;*.blend;*.jpg;*.jpeg;*.png;*.exr', options={'HIDDEN'})
    nama: StringProperty(name='Nama set (kosong = dari nama file)', default='')

    def execute(self, context):
        try:
            td = pipeline_module('tekstur_dasar')
            ident, names = td.daftarkan(self.filepath, self.nama or None)
        except Exception as exc:
            self.report({'ERROR'}, 'Gagal mendaftarkan tekstur: ' + str(exc))
            return {'CANCELLED'}
        _finish_catalog['mtime'] = None
        try:
            context.scene.ns_studio.lib_tekstur = ident
        except TypeError:
            pass
        self.report({'INFO'}, f'Tekstur dasar "{ident}" terdaftar ({", ".join(sorted(names))}). Pilih finish, klik "Pakai untuk finish", lalu bangun ulang library.')
        return {'FINISHED'}


def product_spec_path(scene):
    root = root_for(scene)
    path = Path(str(root.get('ns_spec', ''))) if root is not None else None
    if path and path.is_file():
        return path
    raise ValueError('Produk aktif tidak punya produk.json (bukan hasil bangun_produk.py).')


class NS_OT_SetFinishTexture(bpy.types.Operator):
    bl_idname = 'ns.pakai_tekstur_finish'
    bl_label = 'Pakai tekstur ini untuk finish'
    bl_description = 'Catat di produk.json produk aktif bahwa finish terpilih memakai set tekstur dasar terpilih; berlaku setelah produk dibangun ulang'

    def execute(self, context):
        s = context.scene.ns_studio
        if not s.lib_finish or not s.lib_tekstur:
            self.report({'ERROR'}, 'Pilih finish dan tekstur dasar dulu.'); return {'CANCELLED'}
        try:
            spec = product_spec_path(context.scene)
            nama = pipeline_module('finish_kayu').pakai_tekstur_untuk_finish(spec, s.lib_finish, s.lib_tekstur)
        except Exception as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        self.report({'INFO'}, f'{nama} akan memakai {s.lib_tekstur} (dicatat di {spec.name}). Klik "Bangun ulang produk aktif".')
        return {'FINISHED'}


class NS_OT_RebuildFinishLibrary(bpy.types.Operator):
    bl_idname = 'ns.bangun_ulang_produk'
    bl_label = 'Bangun ulang produk aktif'
    bl_description = 'Jalankan Blender di latar: bangun ulang file produk dari produk.json (finish ikut dikalibrasi ulang) lalu periksa. Beberapa menit; setelah selesai impor ulang produk'
    render_qc: BoolProperty(name='Render QC (hero/front/side/ortho, lebih lama)', default=False)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        root = package_root()
        if not root:
            self.report({'ERROR'}, 'Buka file dari dalam paket Studio_Furniture dulu.'); return {'CANCELLED'}
        try:
            spec = product_spec_path(context.scene)
        except ValueError as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        pipeline = root / '99_SISTEM' / 'pipeline'
        blender = bpy.app.binary_path
        produk_dir = spec.parents[1]
        periksa = [blender, '-b', '--python', str(pipeline / 'periksa_produk.py'), '--', str(produk_dir)]
        if not self.render_qc:
            periksa.append('--tanpa-render')
        self._steps = [('Bangun produk', [blender, '-b', '--factory-startup', '--python', str(pipeline / 'bangun_produk.py'), '--', str(spec), '--finish-ulang']),
                       ('Periksa produk', periksa)]
        logdir = root / '99_SISTEM' / '_kerja'
        logdir.mkdir(exist_ok=True)
        self._logpath = logdir / 'bangun_produk.log'
        self._log = open(self._logpath, 'w', encoding='utf-8')
        self._index = -1
        self._next()
        wm = context.window_manager
        self._timer = wm.event_timer_add(1.0, window=context.window)
        wm.modal_handler_add(self)
        self.report({'INFO'}, 'Membangun ulang produk di latar belakang; log: ' + str(self._logpath))
        return {'RUNNING_MODAL'}

    def _next(self):
        self._index += 1
        if self._index >= len(self._steps):
            return False
        label, cmd = self._steps[self._index]
        self._log.write(f'\n===== {label} =====\n'); self._log.flush()
        self._proc = subprocess.Popen(cmd, stdout=self._log, stderr=subprocess.STDOUT,
                                      creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return True

    def modal(self, context, event):
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}
        code = self._proc.poll()
        if code is None:
            return {'PASS_THROUGH'}
        if code != 0:
            return self._finish(context, f'Langkah "{self._steps[self._index][0]}" gagal (kode {code}); lihat {self._logpath}.')
        if self._next():
            return {'PASS_THROUGH'}
        return self._finish(context)

    def _finish(self, context, error=None):
        context.window_manager.event_timer_remove(self._timer)
        self._log.close()
        _finish_catalog['mtime'] = None
        if error:
            self.report({'ERROR'}, error); return {'CANCELLED'}
        self.report({'INFO'}, 'File produk selesai dibangun ulang. Impor ulang lewat "Pilih file produk" untuk memakai finish barunya.')
        return {'FINISHED'}


def lighting_profile(scene):
    category = scene.get('ns_lighting_category', 'NAKAS')
    profile = scene.get('ns_lighting_profile')
    if not profile:
        version = str(scene.get('studio_version', ''))
        profile = 'V2' if version.startswith('2.') else 'V1' if version.startswith('1.') else ''
    defaults = LIGHTING_DEFAULTS.get(category, {}).get(profile)
    return category, defaults


class NS_OT_ResetLighting(bpy.types.Operator):
    bl_idname = 'ns.reset_lighting'
    bl_label = 'Reset watt lighting'
    bl_description = 'Kembalikan watt ke standar kategori; kamera, posisi lampu, warna, ukuran, dan Exposure tetap'
    bl_options = {'REGISTER', 'UNDO'}

    scope: EnumProperty(items=[('ANGLE', 'Angle aktif', ''),
                               ('CATEGORY', 'Semua angle kategori', '')], default='ANGLE')

    @classmethod
    def poll(cls, context):
        return bool(context.scene and context.scene.get('ns_ready'))

    def execute(self, context):
        scene = context.scene
        category, defaults = lighting_profile(scene)
        if defaults is None:
            self.report({'ERROR'}, 'Standar watt belum tersedia untuk kategori/versi studio ini.')
            return {'CANCELLED'}
        pending = {}
        for rig in scene.collection.children_recursive:
            shot = rig.get('ns_light_shot')
            if shot not in defaults or rig.get('ns_lighting_category', category) != category:
                continue
            if self.scope == 'ANGLE' and shot != scene.ns_studio.shot:
                continue
            rig_scale = float(scene.get('ns_rig_scale', 1.0)) ** 2
            for obj in rig.all_objects:
                role = str(obj.get('ns_role', '')).split(' ')[0]
                if obj.type == 'LIGHT' and role in LIGHT_ROLES and LIGHT_ROLES.index(role) < len(defaults[shot]):
                    pending[obj] = defaults[shot][LIGHT_ROLES.index(role)] * float(obj.get('ns_rig_gain', rig_scale))
        if not pending:
            self.report({'WARNING'}, 'Lampu preset untuk kategori ini tidak ditemukan.')
            return {'CANCELLED'}
        for obj, watts in pending.items():
            # A linked duplicate must not change another angle's light data.
            if obj.data.users > 1:
                obj.data = obj.data.copy()
            obj.data.energy = watts
        self.report({'INFO'}, f'{len(pending)} lampu {category}: watt standar dipulihkan.')
        return {'FINISHED'}


def rig_lights():
    """[(objek lampu, angle, peran)] untuk semua rig angle."""
    out = []
    for rig in bpy.data.collections:
        shot = rig.get('ns_light_shot')
        if not shot:
            continue
        for obj in rig.all_objects:
            if obj.type == 'LIGHT':
                role = str(obj.get('ns_role', '')).split(' ')[0]
                if role:
                    out.append((obj, shot, role))
    return out


_watt_cache = {}
_msgbus_owner = object()
# Properti lampu yang ikut disamakan antar angle: watt, warna, ukuran softbox, sebaran.
LIGHT_PROPS = ('energy', 'color', 'size', 'size_y', 'spread')


def light_state(data):
    state = {}
    for prop in LIGHT_PROPS:
        if hasattr(data, prop):
            value = getattr(data, prop)
            state[prop] = tuple(value) if prop == 'color' else float(value)
    return state


def snapshot_watts():
    _watt_cache.clear()
    try:
        lights = rig_lights()
    except AttributeError:
        return  # bpy.data belum boleh diakses (saat addon diaktifkan Blender); diisi lagi di load_post
    for obj, _, _ in lights:
        _watt_cache[obj.name] = light_state(obj.data)


def _differs(a, b):
    if isinstance(a, tuple):
        return any(abs(x - y) > 1e-6 for x, y in zip(a, b))
    return abs(a - b) > 1e-6


def copy_watts(source_shot, roles=None, props=None):
    """Salin properti lampu (default: semua LIGHT_PROPS) dari angle sumber ke angle lain per peran.
    Kembalikan jumlah lampu yang diubah."""
    lights = rig_lights()
    props = tuple(props) if props else LIGHT_PROPS
    source = {role: light_state(obj.data) for obj, shot, role in lights
              if shot == source_shot and (roles is None or role in roles)}
    changed = 0
    for obj, shot, role in lights:
        if shot == source_shot or role not in source:
            continue
        state = light_state(obj.data)
        todo = [p for p in props if p in source[role] and p in state and _differs(source[role][p], state[p])]
        if not todo:
            continue
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        for p in todo:
            setattr(obj.data, p, source[role][p])
        changed += 1
    snapshot_watts()
    return changed


def propagate_watts(scene):
    """Bila 'Ubah semua angle sekaligus' aktif: properti lampu yang baru berubah disalin ke peran sama di angle lain."""
    if not scene.get('ns_ready') or not hasattr(scene, 'ns_studio'):
        return 0
    if not scene.ns_studio.lighting_all_angles:
        snapshot_watts()
        return 0
    changed = []
    for obj, shot, role in rig_lights():
        before = _watt_cache.get(obj.name)
        if before is None:
            continue
        now = light_state(obj.data)
        props = [p for p in now if p in before and _differs(before[p], now[p])]
        if props:
            changed.append((shot, role, props))
    total = 0
    for shot, role, props in changed:
        total += copy_watts(shot, roles={role}, props=props)
    if not changed:
        snapshot_watts()
    return total


def _on_light_energy(*args):
    scene = getattr(bpy.context, 'scene', None)
    if scene is not None:
        try:
            propagate_watts(scene)
        except (AttributeError, ReferenceError):
            pass


def subscribe_light_energy():
    bpy.msgbus.clear_by_owner(_msgbus_owner)
    # 'energy'/'size' didefinisikan di tiap jenis lampu, 'color' di Light dasar.
    keys = [(bpy.types.Light, 'color')]
    for light_type in (bpy.types.AreaLight, bpy.types.PointLight, bpy.types.SpotLight, bpy.types.SunLight):
        keys.append((light_type, 'energy'))
    keys += [(bpy.types.AreaLight, 'size'), (bpy.types.AreaLight, 'size_y'), (bpy.types.AreaLight, 'spread')]
    for key in keys:
        bpy.msgbus.subscribe_rna(key=key, owner=_msgbus_owner, args=(), notify=_on_light_energy, options={'PERSISTENT'})
    snapshot_watts()


def _load_post(*args):
    subscribe_light_energy()


RIG_REF_SIZE = 0.55      # rig lampu dirancang untuk nakas ~55 cm
RIG_REF_CENTER = Vector((0.0, 0.0, 0.25))
RIG_LIMIT_Z, RIG_LIMIT_XY = 3.6, 4.4


def rig_scale_factor(scene):
    """Faktor pembesaran rig lampu dari ukuran produk aktif (1.0 = nakas, maks 3.0)."""
    try:
        lo, hi = product_bounds(scene)
    except ValueError:
        return 1.0
    return max(1.0, min(3.0, max(hi - lo) / RIG_REF_SIZE))


def apply_rig_scale(scene, factor):
    """Geser lampu menjauh dari pusat produk sebesar faktor dan naikkan watt kuadratnya,
    supaya pencahayaan produk besar setara dengan nakas. Posisi/watt dasar disimpan di
    lampu agar bisa dihitung ulang untuk produk berikutnya."""
    prev = float(scene.get('ns_rig_scale', 1.0))
    if abs(prev - factor) < 1e-3:
        return 0
    changed = 0
    for obj, shot, role in rig_lights():
        if 'ns_base_location' not in obj:
            obj['ns_base_location'] = [float(v) for v in ((obj.location - RIG_REF_CENTER) / prev + RIG_REF_CENTER)]
        base = Vector(obj['ns_base_location'])
        location = RIG_REF_CENTER + (base - RIG_REF_CENTER) * factor
        # Produk besar: lampu tetap di bawah plafon (4.1 m) dan di dalam dinding studio.
        clamped = Vector((max(-RIG_LIMIT_XY, min(RIG_LIMIT_XY, location.x)),
                          max(-RIG_LIMIT_XY, min(RIG_LIMIT_XY, location.y)),
                          min(RIG_LIMIT_Z, location.z)))
        obj.location = clamped
        if (clamped - location).length > 1e-4:
            aim(obj, Vector((0.0, 0.0, RIG_REF_CENTER.z * factor)))
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        # Watt mengikuti jarak nyata (hukum kuadrat terbalik): lampu yang tertahan plafon
        # lebih dekat dari rencana sehingga tidak boleh mendapat kenaikan penuh factor².
        base_distance = max((base - RIG_REF_CENTER).length, 1e-3)
        gain = ((clamped - RIG_REF_CENTER).length / base_distance) ** 2
        obj.data.energy = obj.data.energy / float(obj.get('ns_rig_gain', prev ** 2)) * gain
        obj['ns_rig_gain'] = gain
        if hasattr(obj.data, 'size'):
            obj.data.size = obj.data.size / prev * factor
        if hasattr(obj.data, 'size_y'):
            obj.data.size_y = obj.data.size_y / prev * factor
        changed += 1
    scene['ns_rig_scale'] = factor
    snapshot_watts()
    return changed


class NS_OT_SyncLighting(bpy.types.Operator):
    bl_idname = 'ns.sync_lighting'
    bl_label = 'Samakan semua angle dengan angle ini'
    bl_description = 'Salin watt, warna, ukuran, dan sebaran tiap lampu (Key, Fill, Rim, Top, Tengah) dari angle aktif ke semua angle lain'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        changed = copy_watts(context.scene.ns_studio.shot)
        self.report({'INFO'}, f'{changed} lampu di angle lain disamakan dengan angle {context.scene.ns_studio.shot}.')
        return {'FINISHED'}


# Latar (backdrop): daftar preset di 02_PRODUK/_LATAR/latar.json, bisa ditambah per koleksi produk.
# 'seamless' = cyclorama bawaan template; 'lantai_dinding' = lantai + dinding terpisah (horizon tegas)
# di koleksi LATAR | aktif, opsional dengan matahari rendah dan warna dunia sendiri.
LATAR_MANIFEST = Path('02_PRODUK') / '_LATAR' / 'latar.json'
LATAR_COLLECTION = 'LATAR | aktif'
CYC_MATERIAL = 'Studio | Warm grey seamless'
_latar_catalog = {'mtime': None, 'items': []}


def latar_catalog():
    """Daftar preset latar dari latar.json (urutan file dipertahankan)."""
    root = package_root()
    path = root / LATAR_MANIFEST if root else None
    if not path or not path.is_file():
        _latar_catalog.update(mtime=None, items=[])
        return []
    mtime = path.stat().st_mtime
    if _latar_catalog['mtime'] != mtime:
        _latar_catalog.update(mtime=mtime, items=json.loads(path.read_text(encoding='utf-8')).get('latar', []))
    return _latar_catalog['items']


def latar_preset(latar_id):
    return next((p for p in latar_catalog() if p.get('id') == latar_id), None)


def latar_items(settings, context):
    items = [(p['id'], p.get('nama', p['id']), ', '.join(p.get('koleksi', [])) or 'Semua produk')
             for p in latar_catalog()]
    return items or [('', '— latar.json tidak ada —', '')]


def cyclorama():
    return next((o for o in bpy.data.objects if o.name.startswith('Cyclorama')), None)


def _latar_material(name, spec):
    """Beton / plester: warna (node 'Warna', diubah dari panel) dengan belang halus dan bump tipis."""
    old = bpy.data.materials.get(name)
    if old:
        bpy.data.materials.remove(old)
    m = bpy.data.materials.new(name)
    color = tuple(spec.get('warna', (0.5, 0.5, 0.5)))
    var = float(spec.get('variasi', 0.15))
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    bsdf = N['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = float(spec.get('kekasaran', 0.8))
    tc = N.new('ShaderNodeTexCoord')
    rgb = N.new('ShaderNodeRGB')
    rgb.name = rgb.label = 'Warna'
    rgb.outputs[0].default_value = (*color, 1)
    mott = N.new('ShaderNodeTexNoise')
    mott.inputs['Scale'].default_value = 1.2
    mott.inputs['Detail'].default_value = 8
    mott.inputs['Roughness'].default_value = 0.65
    L.new(tc.outputs['Object'], mott.inputs['Vector'])
    span = N.new('ShaderNodeMapRange')
    span.inputs['To Min'].default_value = 1 - var
    span.inputs['To Max'].default_value = 1 + var
    L.new(mott.outputs['Fac'], span.inputs['Value'])
    mix = N.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1.0
    L.new(rgb.outputs[0], mix.inputs['A'])
    L.new(span.outputs['Result'], mix.inputs['B'])
    L.new(mix.outputs['Result'], bsdf.inputs['Base Color'])
    fine = N.new('ShaderNodeTexNoise')
    fine.inputs['Scale'].default_value = float(spec.get('bump_skala', 60))
    fine.inputs['Detail'].default_value = 6
    L.new(tc.outputs['Object'], fine.inputs['Vector'])
    bump = N.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = float(spec.get('bump_kuat', 0.1))
    L.new(fine.outputs['Fac'], bump.inputs['Height'])
    L.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    m['ns_latar'] = True
    return m


def _latar_plane(name, coll, mat, size_x, size_y):
    me = bpy.data.meshes.new(name)
    hx, hy = size_x / 2, size_y / 2
    me.from_pydata([(-hx, -hy, 0), (hx, -hy, 0), (hx, hy, 0), (-hx, hy, 0)], [], [(0, 1, 2, 3)])
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob['ns_latar'] = True
    return ob


def _clear_latar():
    coll = bpy.data.collections.get(LATAR_COLLECTION)
    if coll is None:
        return None
    for obj in list(coll.objects):
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is not None and data.users == 0:
            (bpy.data.meshes if isinstance(data, bpy.types.Mesh) else bpy.data.lights).remove(data)
    return coll


def latar_object(role):
    coll = bpy.data.collections.get(LATAR_COLLECTION)
    return next((o for o in coll.objects if o.get('ns_latar_role') == role), None) if coll else None


def place_latar(scene):
    """Dinding di belakang produk: jarak preset dari sisi terjauh produk (produk bisa diputar 90°
    untuk angle samping), dan selalu di belakang lampu rim agar lampu tidak tertutup."""
    wall = latar_object('DINDING')
    if wall is None:
        return
    try:
        lo, hi = product_bounds(scene)
        reach = max(hi.x - lo.x, hi.y - lo.y) / 2
    except ValueError:
        reach = 0.3
    behind_lights = max((o.location.y for o, _, _ in rig_lights()), default=0.0) + 0.25
    y = min(4.7, max(reach + float(wall.get('ns_jarak_m', 1.1)), behind_lights))
    wall.location = (0, y, wall.dimensions.y / 2 if wall.dimensions.y else 2.1)
    front = -4.6
    coll = bpy.data.collections.get(LATAR_COLLECTION)
    for flank in [o for o in coll.objects if o.get('ns_latar_role') == 'SAMPING'] if coll else []:
        flank.scale = (y - front, 1, 1)
        flank.location = (flank['ns_latar_x'], (y + front) / 2, 2.1)
    floor = latar_object('LANTAI')
    if floor is not None:
        # Lantai berhenti tepat di kaki dinding; sisi depan sampai batas studio.
        floor.scale = (1, (y - front) / floor.get('ns_base_depth', 1.0), 1)
        floor.location = (0, (y + front) / 2, 0)


def apply_latar(scene, latar_id):
    preset = latar_preset(latar_id)
    if preset is None:
        raise ValueError('Latar tidak ada di latar.json: ' + str(latar_id))
    world = scene.world
    bg = next((n for n in world.node_tree.nodes if n.bl_idname == 'ShaderNodeBackground'), None) if world else None
    if bg is not None and 'ns_latar_dunia_asli' not in scene:
        scene['ns_latar_dunia_asli'] = [*bg.inputs[0].default_value[:3], bg.inputs[1].default_value]
    coll = _clear_latar()
    cyc = cyclorama()
    if preset.get('tipe', 'seamless') == 'seamless':
        if coll is not None:
            bpy.data.collections.remove(coll)
        if cyc:
            cyc.hide_render = False
            cyc.hide_set(False)
        mat = bpy.data.materials.get(CYC_MATERIAL)
        if mat and preset.get('warna'):
            mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*preset['warna'], 1)
    else:
        if coll is None:
            coll = bpy.data.collections.new(LATAR_COLLECTION)
            scene.collection.children.link(coll)
        if cyc:
            cyc.hide_render = True
            cyc.hide_set(True)
        prefix = 'LATAR | ' + preset.get('nama', latar_id)
        floor = _latar_plane('Latar / lantai', coll, _latar_material(prefix + ' · lantai', preset.get('lantai', {})), 9.6, 1.0)
        floor['ns_latar_role'] = 'LANTAI'
        floor['ns_base_depth'] = 1.0
        wall_spec = preset.get('dinding', {})
        wall = _latar_plane('Latar / dinding', coll, _latar_material(prefix + ' · dinding', wall_spec), 9.6, 4.2)
        wall.rotation_euler = (math.radians(90), 0, 0)
        wall['ns_latar_role'] = 'DINDING'
        wall['ns_jarak_m'] = float(wall_spec.get('jarak_m', 1.1))
        # Dinding samping (bahan sama) menutup dinding ruang + plint yang terlihat dari angle 3/4.
        for side, x in (('kiri', -4.8), ('kanan', 4.8)):
            flank = _latar_plane('Latar / dinding ' + side, coll, wall.data.materials[0], 1.0, 4.2)
            flank.rotation_euler = (math.radians(90), 0, math.radians(90))
            flank['ns_latar_role'] = 'SAMPING'
            flank['ns_latar_x'] = x
        sun_spec = preset.get('matahari', {})
        if sun_spec.get('aktif'):
            sun = bpy.data.objects.new('Latar / matahari', bpy.data.lights.new('Latar / matahari', 'SUN'))
            sun.data.energy = float(sun_spec.get('energi', 3.0))
            sun.data.angle = math.radians(float(sun_spec.get('sudut_deg', 6)))
            sun.data.color = tuple(sun_spec.get('warna', (1, 1, 1)))
            sun.rotation_euler = Vector(sun_spec.get('arah', (0.75, 0.55, -0.55))).to_track_quat('-Z', 'Y').to_euler()
            sun['ns_latar'] = True
            sun['ns_latar_role'] = 'MATAHARI'
            coll.objects.link(sun)
        bpy.context.view_layer.update()
        place_latar(scene)
    dunia = preset.get('dunia')
    if bg is not None:
        if dunia:
            bg.inputs[0].default_value = (*dunia.get('warna', (1, 1, 1)), 1)
            bg.inputs[1].default_value = float(dunia.get('kuat', 0.15))
        elif 'ns_latar_dunia_asli' in scene:
            asli = list(scene['ns_latar_dunia_asli'])
            bg.inputs[0].default_value = (*asli[:3], 1)
            bg.inputs[1].default_value = asli[3]
    scene['ns_latar'] = latar_id


def latar_for_product(name):
    """Preset pertama yang kata 'koleksi'-nya ada di nama produk/file (tanpa beda huruf besar)."""
    low = name.lower()
    return next((p['id'] for p in latar_catalog()
                 if any(k and k.lower() in low for k in p.get('koleksi', []))), None)


def latar_updated(settings, context):
    scene = context.scene
    if not scene.get('ns_ready') or settings.get('_latar_guard') or not settings.latar:
        return
    if settings.latar == scene.get('ns_latar'):
        return
    try:
        apply_latar(scene, settings.latar)
        settings['_latar_pesan'] = ''
    except ValueError as exc:
        settings['_latar_pesan'] = 'Gagal: ' + str(exc)


def select_latar(scene, latar_id):
    """Pasang latar dan samakan dropdown tanpa memicu update dua kali."""
    apply_latar(scene, latar_id)
    settings = scene.ns_studio
    settings['_latar_guard'] = True
    try:
        settings.latar = latar_id
    except TypeError:
        pass
    finally:
        settings['_latar_guard'] = False


class NS_OT_SaveLatar(bpy.types.Operator):
    bl_idname = 'ns.simpan_latar'
    bl_label = 'Simpan latar sebagai preset'
    bl_description = 'Simpan warna lantai/dinding/backdrop, matahari, dan dunia saat ini ke 02_PRODUK/_LATAR/latar.json'
    nama: StringProperty(name='Nama latar')
    koleksi: StringProperty(name='Koleksi (pisahkan koma)', description='Kata pada nama produk yang otomatis memakai latar ini, mis. Doheny, Zuma')

    def invoke(self, context, event):
        preset = latar_preset(context.scene.get('ns_latar', '')) or {}
        self.nama = preset.get('nama', '')
        self.koleksi = ', '.join(preset.get('koleksi', []))
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        root = package_root()
        if not root or not self.nama.strip():
            self.report({'ERROR'}, 'Isi nama latar dan buka file dari dalam paket Studio_Furniture.')
            return {'CANCELLED'}
        scene = context.scene
        base = dict(latar_preset(scene.get('ns_latar', '')) or {'tipe': 'seamless'})
        base['nama'] = self.nama.strip()
        base['id'] = re.sub(r'[^a-z0-9]+', '_', base['nama'].lower()).strip('_')
        base['koleksi'] = [k.strip() for k in self.koleksi.split(',') if k.strip()]

        def color_of(obj):
            node = obj.active_material.node_tree.nodes.get('Warna') if obj and obj.active_material else None
            return [round(v, 4) for v in node.outputs[0].default_value[:3]] if node else None

        if base['tipe'] == 'seamless':
            mat = bpy.data.materials.get(CYC_MATERIAL)
            if mat:
                base['warna'] = [round(v, 4) for v in mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value[:3]]
        else:
            for role, key in (('LANTAI', 'lantai'), ('DINDING', 'dinding')):
                color = color_of(latar_object(role))
                if color:
                    base[key] = dict(base.get(key, {}), warna=color)
            wall = latar_object('DINDING')
            if wall is not None:
                base.setdefault('dinding', {})['jarak_m'] = round(float(wall.get('ns_jarak_m', 1.1)), 3)
            sun = latar_object('MATAHARI')
            spec = dict(base.get('matahari', {}), aktif=sun is not None)
            if sun is not None:
                spec.update(energi=round(sun.data.energy, 3), warna=[round(v, 4) for v in sun.data.color])
            base['matahari'] = spec
        bg = next((n for n in scene.world.node_tree.nodes if n.bl_idname == 'ShaderNodeBackground'), None) if scene.world else None
        if bg is not None and 'dunia' in base:
            base['dunia'] = {'warna': [round(v, 4) for v in bg.inputs[0].default_value[:3]], 'kuat': round(bg.inputs[1].default_value, 4)}
        path = root / LATAR_MANIFEST
        data = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'versi': 1, 'latar': []}
        presets = [p for p in data.get('latar', []) if p.get('id') != base['id']]
        index = next((i for i, p in enumerate(data.get('latar', [])) if p.get('id') == base['id']), len(presets))
        presets.insert(index, base)
        data['latar'] = presets
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
        _latar_catalog['mtime'] = None
        select_latar(scene, base['id'])
        self.report({'INFO'}, f"Latar '{base['nama']}' disimpan ke latar.json.")
        return {'FINISHED'}


def camera_for(scene, shot):
    return next((o for o in scene.objects if o.type == 'CAMERA'
                 and o.get('ns_shot') == shot), None)


def render_name(scene, shot):
    """Nama file render = nama kamera tanpa spasi/simbol, mis. CAM_03_LEFT."""
    cam = camera_for(scene, shot)
    name = re.sub(r'[^A-Za-z0-9]+', '_', cam.name if cam else shot).strip('_')
    return name or shot


GEOMETRY_TYPES = {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}
# Koleksi file sumber yang berisi studio/referensi, bukan produk (dicocokkan per kata nama koleksi).
CLUTTER_WORDS = {'studio', 'lights', 'lighting', 'camera', 'cameras', 'kamera', 'floor', 'lantai',
                 'wall', 'walls', 'dinding', 'backdrop', 'cyc', 'cyclorama', 'reference', 'referensi',
                 'dwg', 'helper', 'helpers', 'guide', 'guides', 'environment'}


def scene_clutter(obj):
    """Objek studio/referensi bawaan file produk (lantai, dinding, solid DWG, ...) -> jangan diimpor."""
    for coll in obj.users_collection:
        if CLUTTER_WORDS & set(re.split(r'[^a-z0-9]+', coll.name.lower())):
            return True
    if obj.type == 'MESH':
        thin, mid, _ = sorted(obj.dimensions)
        if thin < 0.002 and mid > 3.0:      # bidang lantai/dinding/backdrop
            return True
    return False


def product_objects(scene):
    coll = scene.ns_studio.product
    return [o for o in coll.all_objects
            if o.type in GEOMETRY_TYPES
            and not o.hide_render] if coll else []


def product_bounds(scene):
    objects = product_objects(scene)
    if not objects:
        raise ValueError('Produk aktif belum berisi geometri.')
    depsgraph = bpy.context.evaluated_depsgraph_get()
    points = []
    for obj in objects:
        evaluated = obj.evaluated_get(depsgraph)
        if obj.type == 'MESH':
            points.extend(evaluated.matrix_world @ Vector(v) for v in evaluated.bound_box)
            continue
        # bound_box curve hasil evaluasi tidak akurat (piping bisa terbaca 3.7 m); ukur dari mesh-nya.
        mesh = evaluated.to_mesh()
        points.extend(evaluated.matrix_world @ v.co for v in mesh.vertices)
        evaluated.to_mesh_clear()
    if not points:
        raise ValueError('Produk aktif belum berisi geometri.')
    lo = Vector([min(p[a] for p in points) for a in range(3)])
    hi = Vector([max(p[a] for p in points) for a in range(3)])
    return lo, hi


def root_for(scene):
    coll = scene.ns_studio.product
    if coll:
        return next((o for o in coll.all_objects if o.get('ns_product_root')), None)


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


OVERVIEW_NAMES = ('CAM_STUDIO_OVERVIEW', 'CAM | STUDIO OVERVIEW')


def overview_camera():
    return next((bpy.data.objects[n] for n in OVERVIEW_NAMES if n in bpy.data.objects), None)


# --- Angle mengikuti kamera aktif lewat driver --------------------------------------
# Putaran produk (angle samping/belakang) dan rig lampu per angle disimpan sebagai driver
# di file, membaca properti kamera aktif (scene.camera). Jadi render server / render
# per kamera di luar addon tetap mendapat produk yang diputar dan lampu angle yang benar.
CAMERA_PATH = 'camera["{}"]'


def _driver(owner, path, expression, variables, index=-1):
    fcurve = owner.driver_add(path, index) if index >= 0 else owner.driver_add(path)
    for modifier in list(fcurve.modifiers):
        fcurve.modifiers.remove(modifier)
    driver = fcurve.driver
    driver.type = 'SCRIPTED'
    for var in list(driver.variables):
        driver.variables.remove(var)
    for name, id_type, target_id, data_path in variables:
        var = driver.variables.new()
        var.name, var.type = name, 'SINGLE_PROP'
        var.targets[0].id_type = id_type
        var.targets[0].id = target_id
        var.targets[0].data_path = data_path
    driver.expression = expression
    return fcurve


def _has_driver(owner, path, index=0):
    ad = owner.animation_data
    return bool(ad and any(fc.data_path == path and fc.array_index == index for fc in ad.drivers))


def ensure_camera_props(scene):
    """Setiap kamera produk membawa nomor angle & putaran produk; overview memakai rig Hero."""
    for shot in SHOT_IDS:
        cam = camera_for(scene, shot)
        if cam:
            cam['ns_shot_index'] = SHOT_IDS.index(shot) + 1
            cam['ns_product_yaw'] = float(cam.get('ns_product_yaw', 0.0))
    overview = overview_camera()
    if overview:
        overview['ns_shot_index'] = 1
        overview['ns_product_yaw'] = 0.0


def ensure_light_drivers(scene):
    """Lampu & perlengkapan rig hanya terender bila kamera aktif milik angle rig itu."""
    for rig in bpy.data.collections:
        shot = rig.get('ns_light_shot')
        if shot not in SHOT_IDS:
            continue
        rig.hide_render = False
        index = SHOT_IDS.index(shot) + 1
        for obj in rig.all_objects:
            _driver(obj, 'hide_render', f'(cam != {index}) + 0 * frame',
                    [('cam', 'SCENE', scene, CAMERA_PATH.format('ns_shot_index'))])


def ensure_product_driver(scene):
    """Root produk: pivot di tengah tapak, rotasi Z = putaran dasar + putaran angle kamera aktif."""
    root = root_for(scene)
    if root is None:
        return
    if not _has_driver(root, 'rotation_euler', 2):
        _pivot_product(scene, root)
    _driver(root, 'rotation_euler', 'base + yaw * 0.017453292519943295 + 0 * frame',
            [('base', 'OBJECT', root, '["ns_base_yaw"]'),
             ('yaw', 'SCENE', scene, CAMERA_PATH.format('ns_product_yaw'))], index=2)
    bpy.context.view_layer.update()


def _pivot_product(scene, root):
    """Sekali per produk: putaran dasar ke ns_base_yaw, pivot root ke tengah tapak produk."""
    base = root.rotation_euler.z - float(root.get('ns_shot_yaw', 0.0))
    root.rotation_euler.z = base
    if 'ns_shot_yaw' in root:
        del root['ns_shot_yaw']
    root['ns_base_yaw'] = base
    bpy.context.view_layer.update()
    try:
        lo, hi = product_bounds(scene)
        delta = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, 0)) - Vector((*root.matrix_world.translation.xy, 0))
        children = [(child, child.matrix_world.copy()) for child in root.children]
        root.location += delta
        bpy.context.view_layer.update()
        for child, world in children:
            child.matrix_world = world
    except ValueError:
        pass


def ensure_angle_drivers(scene):
    ensure_camera_props(scene)
    ensure_light_drivers(scene)
    ensure_product_driver(scene)


def use_camera(scene, cam):
    """Jadikan kamera aktif lalu evaluasi driver (putaran produk & lampu angle)."""
    if cam is not None and scene.camera != cam:
        scene.camera = cam
    # view_layer.update() tidak menjalankan ulang driver saat kamera berganti; frame_set ya.
    scene.frame_set(scene.frame_current)


def turn_product(scene, radians):
    """Putar produk permanen (mis. tombol 90°): ubah putaran dasar, bukan rotasi yang di-driver."""
    root = root_for(scene)
    if root is None:
        return False
    if _has_driver(root, 'rotation_euler', 2):
        root['ns_base_yaw'] = float(root.get('ns_base_yaw', 0.0)) + radians
        root.update_tag()
    else:
        root.rotation_euler.z += radians
    bpy.context.view_layer.update()
    return True


def select_shot(scene, shot):
    for obj in scene.objects:
        if obj.get('ns_equipment') or obj.get('ns_guide'):
            # Perlengkapan dan panah penunjuk arah lampu tidak boleh terender
            # (produk besar membuat kamera mundur sehingga keduanya masuk frame).
            obj.visible_camera = False
            obj.visible_shadow = False
            if obj.get('ns_guide'):
                obj.visible_diffuse = False
                obj.visible_glossy = False
                obj.visible_transmission = False
    cam = camera_for(scene, shot)
    if cam is None:
        raise ValueError('Kamera preset tidak ditemukan. Buka file Nakas_Studio.blend.')
    ensure_angle_drivers(scene)
    use_camera(scene, cam)
    for coll in bpy.data.collections:
        if coll.get('ns_light_shot'):
            # Render diatur driver per lampu; viewport cukup menampilkan rig angle aktif.
            coll.hide_viewport = coll['ns_light_shot'] != shot
    if not bpy.app.background:
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    area.spaces.active.region_3d.view_perspective = 'CAMERA'
    if hasattr(scene.ns_studio, 'preview_mode'):
        apply_preview(scene)


def apply_preview(scene):
    mode = scene.ns_studio.preview_mode
    overview = scene.camera is not None and scene.camera == overview_camera()
    # Material Preview uses EEVEE, which does not use Cycles ray visibility.
    # Hide only physical equipment in the viewport; render visibility stays intact.
    for obj in scene.objects:
        if not (obj.get('ns_equipment') or obj.get('ns_guide')):
            continue
        hide = mode == 'FAST' and not overview
        if hide:
            if 'ns_preview_hidden_before' not in obj:
                obj['ns_preview_hidden_before'] = obj.hide_get()
            obj.hide_set(True)
        elif 'ns_preview_hidden_before' in obj:
            obj.hide_set(bool(obj['ns_preview_hidden_before']))
            del obj['ns_preview_hidden_before']
    scene.cycles.preview_samples = 8
    scene.cycles.use_preview_denoising = True
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != 'VIEW_3D':
                continue
            space = area.spaces.active
            space.lock_camera = False
            space.shading.type = 'SOLID' if mode == 'PAUSE' or (mode == 'FAST' and overview) else 'MATERIAL' if mode == 'FAST' else 'RENDERED'
            if space.shading.type == 'SOLID':
                # Mode Jeda tetap memperlihatkan tekstur finish (tanpa lampu), supaya ganti finish terlihat.
                space.shading.color_type = 'TEXTURE'
                space.shading.light = 'STUDIO'
            space.shading.use_scene_lights = True
            space.shading.use_scene_world = True
            space.overlay.show_overlays = False
            area.tag_redraw()


def preview_updated(settings, context):
    if context.scene.get('ns_ready'):
        apply_preview(context.scene)


class NS_OT_PreviewMode(bpy.types.Operator):
    bl_idname = 'ns.preview_mode'
    bl_label = 'Pilih pratinjau'
    mode: StringProperty(default='FAST')

    def execute(self, context):
        context.scene.ns_studio.preview_mode = self.mode
        apply_preview(context.scene)
        return {'FINISHED'}


class NS_OT_QuickAngle(bpy.types.Operator):
    bl_idname = 'ns.quick_angle'
    bl_label = 'Lihat angle produk'
    shot: StringProperty(default='HERO')

    def execute(self, context):
        context.scene.ns_studio.shot = self.shot
        select_shot(context.scene, self.shot)
        return {'FINISHED'}


class NS_OT_Navigate(bpy.types.Operator):
    bl_idname = 'ns.navigate'
    bl_label = 'Atur tampilan'
    bl_description = 'Mengubah tampilan layar; kamera render dan produk tetap'
    action: StringProperty(default='HOME')

    def execute(self, context):
        area = context.area if context.area and context.area.type == 'VIEW_3D' else next((a for a in context.screen.areas if a.type=='VIEW_3D'), None)
        if area is None:
            return {'CANCELLED'}
        space=area.spaces.active
        editing=context.scene.ns_studio.camera_edit
        # Mode edit kamera: navigasi menggerakkan kamera angle aktif (Lock Camera to View).
        space.lock_camera=editing
        view=space.region_3d
        if self.action=='HOME':
            select_shot(context.scene,context.scene.ns_studio.shot)
            view.view_camera_zoom=0
            view.view_camera_offset=(0,0)
        else:
            region=next(r for r in area.regions if r.type=='WINDOW')
            with context.temp_override(area=area,region=region):
                if self.action in {'IN','OUT'}:
                    bpy.ops.view3d.zoom(delta=1 if self.action=='IN' else -1)
                elif self.action.startswith('PAN'):
                    bpy.ops.view3d.view_pan(type=self.action)
                else:
                    if view.view_perspective=='CAMERA' and not editing:
                        if product_objects(context.scene):
                            lo,hi=product_bounds(context.scene)
                            view.view_location=(lo+hi)/2
                            view.view_distance=max(1.2,max(hi-lo)*3)
                        else:
                            view.view_location=(0,0,1)
                            view.view_distance=6
                        view.view_perspective='PERSP'
                    bpy.ops.view3d.view_orbit(type='ORBIT'+self.action,angle=math.radians(15))
        return {'FINISHED'}


def shot_updated(settings, context):
    if context.scene.get('ns_ready'):
        try:
            select_shot(context.scene, settings.shot)
        except ValueError:
            pass


def quality_updated(settings, context):
    scene = context.scene
    if settings.quality == 'PREVIEW':
        scene.render.resolution_x = scene.render.resolution_y = 800
        scene.cycles.samples = 48
        scene.cycles.adaptive_threshold = 0.08
    else:
        scene.render.resolution_x = scene.render.resolution_y = 1600
        scene.cycles.samples = 192
        scene.cycles.adaptive_threshold = 0.015
    scene.render.resolution_percentage = 100


class NS_Settings(bpy.types.PropertyGroup):
    preview_mode: EnumProperty(name='Pratinjau', default='FAST', update=preview_updated,
                              items=[('FAST','Cepat','Lighting perkiraan dengan EEVEE'),
                                     ('DETAIL','Cek detail','Cycles 8 samples; tunggu sampai stabil'),
                                     ('PAUSE','Jeda','Tampilan bentuk tanpa perhitungan lighting')])
    product: PointerProperty(type=bpy.types.Collection, name='Produk aktif')
    shot: EnumProperty(name='Kamera', items=SHOTS, update=shot_updated)
    output: StringProperty(name='Folder render', subtype='DIR_PATH', default='//renders/',
                           options={'PATH_SUPPORTS_BLEND_RELATIVE'})
    quality: EnumProperty(name='Kualitas', default='FINAL', update=quality_updated,
                         items=[('PREVIEW', 'Preview · 800 px', ''),
                                ('FINAL', 'Final · 1600 px', '')])
    frame_margin: FloatProperty(name='Ruang tepi', default=1.18, min=1.02, max=2.0)
    actual_width: FloatProperty(name='Lebar nyata (cm)', default=50.0, min=1, max=500)
    import_scale: EnumProperty(name='Faktor setelah impor', default='1', items=[
        ('1', '1 × · pertahankan ukuran', 'Importer FBX/GLTF biasanya sudah membaca unit'),
        ('0.01', '0.01 × · angka mentah cm ke m', ''),
        ('0.001', '0.001 × · angka mentah mm ke m', ''),
    ])
    include_hero: BoolProperty(name='Hero 3/4 kanan', default=True)
    include_front: BoolProperty(name='Depan', default=True)
    include_left: BoolProperty(name='3/4 kiri', default=True)
    include_side: BoolProperty(name='Samping', default=True)
    include_detail: BoolProperty(name='Detail', default=True)
    include_side_l: BoolProperty(name='Samping kiri', default=True)
    include_back: BoolProperty(name='Belakang 3/4', default=True)
    include_base: BoolProperty(name='Detail kaki / bawah', default=True)
    include_closeup: BoolProperty(name='Close-up material', default=True)
    finish_wood: EnumProperty(name='Finish kayu', items=finish_items('WOOD_A', 'finish_wood'),
                              update=finish_updated('WOOD_A', 'finish_wood'))
    finish_handle: EnumProperty(name='Finish handle', items=finish_items('HANDLE', 'finish_handle'),
                                update=finish_updated('HANDLE', 'finish_handle'))
    lib_finish: EnumProperty(name='Finish', items=lib_finish_items)
    lib_tekstur: EnumProperty(name='Tekstur dasar', items=lib_tekstur_items, update=lib_tekstur_updated)
    lighting_all_angles: BoolProperty(name='Ubah semua angle sekaligus', default=False,
                                      description='Saat watt, warna, ukuran, atau sebaran satu lampu diubah, lampu dengan peran sama di semua angle ikut berubah',
                                      update=lambda self, context: snapshot_watts())
    camera_edit: BoolProperty(name='Edit posisi kamera', default=False, update=lambda self, context: camera_edit_updated(self, context),
                              description='Orbit, geser, dan zoom di viewport menggerakkan kamera angle aktif; lalu kunci untuk produk ini')
    latar: EnumProperty(name='Latar', items=latar_items, update=latar_updated,
                        description='Backdrop studio dari 02_PRODUK/_LATAR/latar.json')
    latar_otomatis: BoolProperty(name='Latar otomatis per koleksi', default=True,
                                 description='Saat impor, pilih latar yang koleksinya cocok dengan nama produk (mis. Doheny)')
    camera_grid: EnumProperty(name='Grid komposisi', default='THIRDS', update=lambda self, context: apply_camera_guides(context.scene),
                              description='Garis bantu di tampilan kamera saat edit posisi; tidak ikut terender',
                              items=[('THIRDS', '3×3', 'Rule of thirds (sepertiga)'),
                                     ('GOLDEN', 'Golden', 'Golden ratio'),
                                     ('CENTER', 'Tengah', 'Garis tengah dan diagonal'),
                                     ('NONE', 'Off', 'Tanpa grid')])


def apply_camera_guides(scene):
    """Grid komposisi & area luar frame digelapkan hanya selama edit posisi kamera."""
    settings = scene.ns_studio
    show = settings.camera_edit
    grid = settings.camera_grid
    for shot in SHOT_IDS:
        cam = camera_for(scene, shot)
        if cam is None:
            continue
        data = cam.data
        data.show_composition_thirds = show and grid == 'THIRDS'
        data.show_composition_golden = show and grid == 'GOLDEN'
        data.show_composition_center = show and grid == 'CENTER'
        data.show_composition_center_diagonal = show and grid == 'CENTER'
        data.show_passepartout = True
        data.passepartout_alpha = 0.75 if show else 0.5


# Overlay yang dimatikan saat edit kamera: hanya grid komposisi & frame kamera yang tampil.
CLEAN_OVERLAY = ('show_floor', 'show_axis_x', 'show_axis_y', 'show_axis_z', 'show_cursor',
                 'show_object_origins', 'show_relationship_lines', 'show_outline_selected',
                 'show_text', 'show_stats', 'show_extras', 'show_bones', 'show_motion_paths')


def camera_edit_updated(settings, context):
    apply_camera_guides(context.scene)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces.active
                space.lock_camera = settings.camera_edit
                # Template mematikan overlay; grid komposisi hanya tergambar bila overlay menyala.
                overlay = space.overlay
                overlay.show_overlays = settings.camera_edit
                if settings.camera_edit:
                    for prop in CLEAN_OVERLAY:
                        if hasattr(overlay, prop):
                            setattr(overlay, prop, False)
                    overlay.show_camera_guides = True
                    overlay.show_camera_passepartout = True
                    space.region_3d.view_perspective = 'CAMERA'


# --- Kunci kamera per produk ---------------------------------------------------------
# Posisi kamera hasil edit manual disimpan di root produk, relatif terhadap pusat tapak
# dan putaran dasar produk. Atur framing / impor ulang memakai posisi itu, bukan hitungan
# otomatis; produk lain tetap memakai framing otomatis.
CAMERA_LOCK = 'ns_camera_lock'


def _product_frame(root):
    return Matrix.Translation(root.matrix_world.translation) @ Matrix.Rotation(float(root.get('ns_base_yaw', root.rotation_euler.z)), 4, 'Z')


def locked_shots(scene):
    root = root_for(scene)
    return sorted(root[CAMERA_LOCK].keys(), key=SHOT_IDS.index) if root and CAMERA_LOCK in root else []


def lock_camera(scene, shot):
    root, cam = root_for(scene), camera_for(scene, shot)
    if root is None or cam is None:
        return False
    local = _product_frame(root).inverted() @ cam.matrix_world
    locks = root.get(CAMERA_LOCK) or {}
    locks[shot] = {'matrix': [v for row in local for v in row], 'lens': cam.data.lens,
                   'focus': cam.data.dof.focus_distance, 'dof': cam.data.dof.use_dof,
                   'fstop': cam.data.dof.aperture_fstop}
    root[CAMERA_LOCK] = locks
    return True


def unlock_camera(scene, shot):
    root = root_for(scene)
    if root is None or CAMERA_LOCK not in root or shot not in root[CAMERA_LOCK]:
        return False
    del root[CAMERA_LOCK][shot]
    if not root[CAMERA_LOCK].keys():
        del root[CAMERA_LOCK]
    return True


def restore_locked_camera(scene, shot):
    root, cam = root_for(scene), camera_for(scene, shot)
    if root is None or cam is None or CAMERA_LOCK not in root or shot not in root[CAMERA_LOCK]:
        return False
    lock = root[CAMERA_LOCK][shot]
    values = list(lock['matrix'])
    cam.matrix_world = _product_frame(root) @ Matrix([values[i:i + 4] for i in range(0, 16, 4)])
    cam.data.lens = float(lock['lens'])
    cam.data.dof.focus_distance = float(lock['focus'])
    cam.data.dof.use_dof = bool(lock['dof'])
    cam.data.dof.aperture_fstop = float(lock['fstop'])
    return True


def fit_cameras(scene):
    product_bounds(scene)
    ensure_angle_drivers(scene)
    active = scene.camera
    for shot in SHOT_IDS:
        cam = camera_for(scene, shot)
        if cam is None:
            continue
        if restore_locked_camera(scene, shot):
            continue
        # Angle samping/belakang membingkai produk dalam putaran angle itu sendiri.
        use_camera(scene, cam)
        lo, hi = product_bounds(scene)
        center, size = (lo + hi) / 2, hi - lo
        corners = [Vector((x, y, z)) for x in (lo.x, hi.x)
                   for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
        fraction = Vector(cam.get('ns_target_fraction', (0, 0, 0.5)))
        target = Vector((center.x + size.x * fraction.x,
                         center.y + size.y * fraction.y,
                         lo.z + size.z * fraction.z))
        direction = Vector(cam['ns_direction']).normalized()
        cam.location = target + direction
        aim(cam, target)
        if shot == 'DETAIL' or cam.get('ns_fit') == 'detail':
            # Close-up: jarak sebanding ukuran produk, bukan membingkai seluruh produk.
            distance = max(size) * float(cam.get('ns_detail_scale', 1.45))
        else:
            # Solve the pinhole frustum for every world-space bound corner.
            # Vertical FOV follows render aspect, pixel aspect, and sensor fit.
            aspect = (scene.render.resolution_x * scene.render.pixel_aspect_x /
                      (scene.render.resolution_y * scene.render.pixel_aspect_y))
            tan_x = cam.data.sensor_width / (2 * cam.data.lens)
            tan_y = tan_x / aspect
            inverse = cam.rotation_euler.to_matrix().transposed()
            distance = 0.01
            for point in corners:
                local = inverse @ (point - target)
                distance = max(distance, local.z + abs(local.x) / tan_x * scene.ns_studio.frame_margin,
                               local.z + abs(local.y) / tan_y * scene.ns_studio.frame_margin)
        cam.location = target + direction * distance
        aim(cam, target)
        cam.data.dof.focus_distance = distance
    use_camera(scene, active)
    lo, hi = product_bounds(scene)
    return hi - lo


def center_product(scene):
    root = root_for(scene)
    if root is None:
        raise ValueError('Root produk tidak ditemukan. Gunakan Ambil Objek Terpilih.')
    lo, hi = product_bounds(scene)
    root.location += Vector((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z))
    bpy.context.view_layer.update()


def activate_product(scene, coll):
    group = bpy.data.collections.get('PRODUCTS')
    if group:
        for other in group.children:
            other.hide_render = other.hide_viewport = other != coll
    coll.hide_render = coll.hide_viewport = False
    scene.ns_studio.product = coll


def adopt_objects(scene, objects, label):
    objects = [o for o in objects if o.type not in {'CAMERA', 'LIGHT'}]
    if not any(o.type in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'} for o in objects):
        raise ValueError('Tidak ada mesh atau geometri produk yang dapat dipakai.')
    group = bpy.data.collections.get('PRODUCTS')
    if group is None:
        group = bpy.data.collections.new('PRODUCTS')
        scene.collection.children.link(group)
    coll = bpy.data.collections.new('PROD | ' + label)
    group.children.link(coll)
    coll['ns_product'] = True
    object_set = set(objects)
    root = bpy.data.objects.new('PRODUCT_ROOT | ' + label, None)
    root.empty_display_type = 'PLAIN_AXES'
    root.empty_display_size = 0.12
    root['ns_product_root'] = True
    coll.objects.link(root)
    for obj in objects:
        if obj.get('ns_product_root'):
            # Bawa metadata produk (ns_finishes, ns_exposure, ns_spec, dimensions_cm, ...) ke root baru.
            for key in obj.keys():
                if key not in {'ns_product_root', '_RNA_UI'}:
                    try:
                        root[key] = obj[key]
                    except (TypeError, ValueError):
                        pass
            obj['ns_product_root'] = False
        world = obj.matrix_world.copy()
        for previous in list(obj.users_collection):
            previous.objects.unlink(obj)
        coll.objects.link(obj)
        if obj.parent not in object_set:
            obj.parent = root
            obj.matrix_world = world
    activate_product(scene, coll)
    bpy.context.view_layer.update()
    return root


class NS_OT_Center(bpy.types.Operator):
    bl_idname = 'ns.center_product'
    bl_label = 'Letakkan di lantai & tengah'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            center_product(context.scene)
        except ValueError as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        return {'FINISHED'}


class NS_OT_Fit(bpy.types.Operator):
    bl_idname = 'ns.fit_cameras'
    bl_label = 'Atur framing semua kamera'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            fit_cameras(context.scene)
        except ValueError as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        self.report({'INFO'}, 'Framing diperbarui. Periksa dan rapikan kamera detail secara manual.')
        return {'FINISHED'}


class NS_OT_Scale(bpy.types.Operator):
    bl_idname = 'ns.scale_product'
    bl_label = 'Terapkan lebar nyata'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        try:
            # Lebar diukur pada orientasi asli, bukan saat angle samping memutar produk.
            active = scene.camera
            use_camera(scene, camera_for(scene, 'HERO'))
            lo, hi = product_bounds(scene)
            root = root_for(scene)
            if not root or hi.x - lo.x < 0.000001:
                raise ValueError('Lebar produk tidak valid.')
            root.scale *= (scene.ns_studio.actual_width / 100) / (hi.x - lo.x)
            context.view_layer.update()
            center_product(scene)
        except ValueError as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        finally:
            use_camera(scene, active)
        return {'FINISHED'}


class NS_OT_Rotate(bpy.types.Operator):
    bl_idname = 'ns.rotate_product'
    bl_label = 'Putar produk 90°'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not turn_product(context.scene, math.pi / 2):
            return {'CANCELLED'}
        center_product(context.scene)
        return {'FINISHED'}


class NS_OT_Adopt(bpy.types.Operator):
    bl_idname = 'ns.adopt_selected'
    bl_label = 'Ambil objek terpilih sebagai produk'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected = list(context.selected_objects)
        if not selected:
            self.report({'ERROR'}, 'Pilih seluruh bagian model produk terlebih dahulu.')
            return {'CANCELLED'}
        if any(o.get('ns_studio_asset') or o.get('ns_product_root') for o in selected):
            self.report({'ERROR'}, 'Pilihan berisi rig studio atau root produk. Pilih hanya model pengganti.')
            return {'CANCELLED'}
        try:
            adopt_objects(context.scene, selected, context.active_object.name if context.active_object else 'Produk baru')
            center_product(context.scene)
        except ValueError as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        self.report({'INFO'}, 'Produk aktif diganti. Periksa dimensi lalu klik Atur framing.')
        return {'FINISHED'}


class NS_OT_Import(bpy.types.Operator, ImportHelper):
    bl_idname = 'ns.import_product'
    bl_label = 'Impor produk pengganti'
    bl_options = {'REGISTER', 'UNDO'}
    filter_glob: StringProperty(default='*.blend;*.fbx;*.obj;*.glb;*.gltf', options={'HIDDEN'})

    def invoke(self, context, event):
        root = package_root()
        if root and not self.filepath:
            self.filepath = str(root / '02_PRODUK') + os.sep
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        before = set(bpy.data.objects)
        before_collections = set(bpy.data.collections)
        previous_product = context.scene.ns_studio.product
        filepath = self.filepath
        try:
            ext = Path(filepath).suffix.lower()
            if ext == '.blend':
                with bpy.data.libraries.load(filepath, link=False) as (src, dst):
                    dst.objects = list(src.objects)
                    # Koleksi ikut dimuat hanya untuk mengenali studio/referensi milik file sumber.
                    dst.collections = list(src.collections)
                    # Finish kayu yang ditanam di produk (FIN | ...) ikut dibawa walau belum dipakai objek.
                    dst.materials = [m for m in src.materials if m.startswith('FIN | ') or m.startswith('HW | ')]
                imported = [o for o in dst.objects if o is not None]
                for obj in imported:
                    # Semua objek masuk scene dulu: matrix_world baru terhitung untuk objek di scene,
                    # sebelum itu posisi objek di koleksi sumber terbaca di titik nol.
                    if obj.name not in context.scene.collection.objects:
                        context.scene.collection.objects.link(obj)
                context.view_layer.update()
                for mat in dst.materials:
                    if mat is not None and mat.get('ns_finish_id'):
                        mat.use_fake_user = True
            elif ext == '.fbx':
                bpy.ops.import_scene.fbx(filepath=filepath)
            elif ext == '.obj':
                bpy.ops.wm.obj_import(filepath=filepath)
            elif ext in {'.glb', '.gltf'}:
                bpy.ops.import_scene.gltf(filepath=filepath)
            else:
                raise ValueError('Format yang didukung: BLEND, FBX, OBJ, GLB, GLTF.')
            created = set(bpy.data.objects) - before
            product = [o for o in created if o.type not in {'CAMERA', 'LIGHT'}]
            skipped = [o for o in product if scene_clutter(o)]
            if any(o.type in GEOMETRY_TYPES for o in product if o not in skipped):
                product = [o for o in product if o not in skipped]
            else:
                skipped = []
            root = adopt_objects(context.scene, product, Path(filepath).stem)
            root.scale *= float(context.scene.ns_studio.import_scale)
            skipped_names = [o.name for o in skipped]
            for obj in created - set(product):
                bpy.data.objects.remove(obj, do_unlink=True)
            # Koleksi sumber yang kini kosong (bertingkat) dibuang sampai tidak ada sisa.
            removed = True
            while removed:
                removed = False
                for coll in set(bpy.data.collections) - before_collections:
                    if not coll.objects and not coll.children and not coll.get('ns_product'):
                        bpy.data.collections.remove(coll)
                        removed = True
            context.view_layer.update()
            center_product(context.scene)
            fit_cameras(context.scene)
            apply_rig_scale(context.scene, rig_scale_factor(context.scene))
            latar_id = latar_for_product(root.name + ' ' + filepath) if context.scene.ns_studio.latar_otomatis else None
            if latar_id and latar_id != context.scene.get('ns_latar'):
                select_latar(context.scene, latar_id)
            else:
                place_latar(context.scene)
            if root.get('ns_exposure') is not None:
                # Exposure hasil kalibrasi periksa_produk.py: terang front disamakan dengan swatch referensi.
                context.scene.view_settings.exposure = float(root['ns_exposure'])
            select_shot(context.scene, context.scene.ns_studio.shot)
            sync_finish_props(context.scene)
            note = (f' Dilewati {len(skipped)} objek studio/referensi file sumber: '
                    + ', '.join(sorted(o for o in skipped_names)[:4]) + ('…' if len(skipped) > 4 else '')) if skipped else ''
            self.report({'INFO'}, 'Produk dimuat, diposisikan, dan kamera disesuaikan. Periksa ukuran dan angle detail.' + note)
            return {'FINISHED'}
        except Exception as exc:
            for obj in set(bpy.data.objects) - before:
                bpy.data.objects.remove(obj, do_unlink=True)
            for coll in set(bpy.data.collections) - before_collections:
                bpy.data.collections.remove(coll)
            if previous_product:
                activate_product(context.scene, previous_product)
            self.report({'ERROR'}, 'Impor gagal: ' + str(exc))
            return {'CANCELLED'}


class NS_OT_Activate(bpy.types.Operator):
    bl_idname = 'ns.activate_product'
    bl_label = 'Gunakan produk'
    bl_options = {'REGISTER', 'UNDO'}
    collection_name: StringProperty()

    def execute(self, context):
        coll = bpy.data.collections.get(self.collection_name)
        if not coll or not coll.get('ns_product'):
            return {'CANCELLED'}
        activate_product(context.scene, coll)
        sync_finish_props(context.scene)
        try:
            # Kamera mengikuti produk ini: posisi terkunci miliknya, sisanya framing otomatis.
            fit_cameras(context.scene)
            place_latar(context.scene)
        except ValueError:
            pass
        return {'FINISHED'}


def render_directory(scene):
    label = bpy.path.clean_name(scene.ns_studio.product.name if scene.ns_studio.product else 'produk')
    folder = Path(bpy.path.abspath(scene.ns_studio.output)) / label / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def chosen_shots(settings):
    # File sesi lama mungkin belum punya kamera angle baru -> lewati.
    return [shot for shot in SHOT_IDS if getattr(settings, 'include_' + shot.lower())
            and camera_for(settings.id_data, shot) is not None]


class NS_OT_RenderBatch(bpy.types.Operator):
    bl_idname = 'ns.render_batch'
    bl_label = 'Render semua angle terpilih'
    bl_description = 'Simpan PNG per kamera ke folder baru; Esc untuk membatalkan'

    def execute(self, context):
        self._shots = chosen_shots(context.scene.ns_studio)
        if not self._shots:
            self.report({'ERROR'}, 'Pilih minimal satu angle.'); return {'CANCELLED'}
        try:
            product_bounds(context.scene)
            self._folder = render_directory(context.scene)
        except (ValueError, OSError) as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        self._scene = context.scene
        self._original = (self._scene.ns_studio.shot, self._scene.render.filepath)
        self._index = 0
        self._running = self._done = self._cancelled = False
        if bpy.app.background:
            try:
                for shot in self._shots:
                    self._scene.ns_studio.shot = shot
                    select_shot(self._scene, shot)
                    self._scene.render.filepath = str(self._folder / (render_name(self._scene, shot) + '.png'))
                    bpy.ops.render.render(write_still=True)
            finally:
                self._restore()
            return {'FINISHED'}
        self._complete_handler = self._on_complete
        self._cancel_handler = self._on_cancel
        bpy.app.handlers.render_complete.append(self._complete_handler)
        bpy.app.handlers.render_cancel.append(self._cancel_handler)
        self._timer = context.window_manager.event_timer_add(0.4, window=context.window)
        context.window_manager.modal_handler_add(self)
        self.report({'INFO'}, 'Batch render dimulai: ' + str(self._folder))
        return {'RUNNING_MODAL'}

    def _on_complete(self, scene, *args):
        if scene == self._scene:
            self._done = True

    def _on_cancel(self, scene, *args):
        if scene == self._scene:
            self._cancelled = True
            self._done = True

    def _restore(self):
        shot, filepath = self._original
        self._scene.ns_studio.shot = shot
        select_shot(self._scene, shot)
        self._scene.render.filepath = filepath

    def _finish(self, context, cancelled=False):
        context.window_manager.event_timer_remove(self._timer)
        for handlers, fn in ((bpy.app.handlers.render_complete, self._complete_handler),
                             (bpy.app.handlers.render_cancel, self._cancel_handler)):
            if fn in handlers:
                handlers.remove(fn)
        self._restore()
        self.report({'WARNING'} if cancelled else {'INFO'},
                    ('Batch dibatalkan. Hasil selesai tetap tersimpan: ' if cancelled else 'Render selesai: ') + str(self._folder))
        return {'CANCELLED'} if cancelled else {'FINISHED'}

    def modal(self, context, event):
        if event.type == 'ESC':
            self._cancelled = True
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}
        busy = bpy.app.is_job_running('RENDER')
        if self._cancelled and not busy:
            return self._finish(context, True)
        if self._running:
            if not self._done or busy:
                return {'PASS_THROUGH'}
            self._index += 1
            self._running = False
        if self._index >= len(self._shots):
            return self._finish(context)
        shot = self._shots[self._index]
        self._scene.ns_studio.shot = shot
        select_shot(self._scene, shot)
        self._scene.render.filepath = str(self._folder / (render_name(self._scene, shot) + '.png'))
        self._done = False
        self._running = True
        try:
            result = bpy.ops.render.render('INVOKE_DEFAULT', write_still=True)
            if result == {'CANCELLED'}:
                return self._finish(context, True)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return self._finish(context, True)
        return {'PASS_THROUGH'}


class NS_OT_SelectCamera(bpy.types.Operator):
    bl_idname = 'ns.select_camera'
    bl_label = 'Pilih kamera untuk diedit'

    def execute(self, context):
        cam = context.scene.camera
        if not cam:
            return {'CANCELLED'}
        bpy.ops.object.select_all(action='DESELECT')
        cam.select_set(True)
        context.view_layer.objects.active = cam
        return {'FINISHED'}


class NS_OT_LockCamera(bpy.types.Operator):
    bl_idname = 'ns.lock_camera'
    bl_label = 'Kunci kamera untuk produk ini'
    bl_description = 'Simpan posisi, lensa, dan fokus kamera di produk aktif; Atur framing & impor ulang memakainya'
    bl_options = {'REGISTER', 'UNDO'}
    scope: EnumProperty(items=[('ANGLE', 'Angle aktif', ''), ('ALL', 'Semua angle', '')], default='ANGLE')

    def execute(self, context):
        scene = context.scene
        shots = [scene.ns_studio.shot] if self.scope == 'ANGLE' else SHOT_IDS
        done = [shot for shot in shots if lock_camera(scene, shot)]
        if not done:
            self.report({'ERROR'}, 'Belum ada produk aktif.'); return {'CANCELLED'}
        self.report({'INFO'}, 'Kamera dikunci untuk produk ini: ' + ', '.join(done))
        return {'FINISHED'}


class NS_OT_UnlockCamera(bpy.types.Operator):
    bl_idname = 'ns.unlock_camera'
    bl_label = 'Lepas kunci kamera'
    bl_description = 'Kembali ke framing otomatis untuk produk ini'
    bl_options = {'REGISTER', 'UNDO'}
    scope: EnumProperty(items=[('ANGLE', 'Angle aktif', ''), ('ALL', 'Semua angle', '')], default='ANGLE')

    def execute(self, context):
        scene = context.scene
        shots = [scene.ns_studio.shot] if self.scope == 'ANGLE' else SHOT_IDS
        for shot in shots:
            unlock_camera(scene, shot)
        try:
            fit_cameras(scene)
        except ValueError as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        return {'FINISHED'}


class NS_OT_Overview(bpy.types.Operator):
    bl_idname = 'ns.studio_overview'
    bl_label = 'Lihat ruang studio / kembali ke produk'

    def execute(self, context):
        scene = context.scene
        overview = overview_camera()
        if overview is None:
            return {'CANCELLED'}
        if scene.camera == overview:
            select_shot(scene, scene.ns_studio.shot)
        else:
            scene.camera = overview
            for obj in scene.objects:
                if obj.get('ns_equipment'):
                    obj.visible_camera = True
                    obj.visible_shadow = True
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.region_3d.view_perspective = 'CAMERA'
        apply_preview(scene)
        return {'FINISHED'}


class NS_OT_LightingView(bpy.types.Operator):
    bl_idname = 'ns.lighting_view'
    bl_label = 'Lihat lighting · Cycles'
    bl_description = 'Gunakan Rendered View untuk melihat lampu studio dan pantulan Cycles'

    def execute(self, context):
        context.scene.ns_studio.preview_mode = 'DETAIL'
        apply_preview(context.scene)
        return {'FINISHED'}


def package_root():
    if bpy.data.filepath:
        for parent in Path(bpy.data.filepath).parents:
            if (parent/'01_STUDIO').is_dir() and (parent/'02_PRODUK').is_dir():
                return parent
    return None


class NS_OT_LoadExample(bpy.types.Operator):
    bl_idname = 'ns.load_example'
    bl_label = 'Muat contoh nakas'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        root = package_root()
        path = root/'02_PRODUK/Nakas/Nakas_Oak_2Laci.blend' if root else None
        if path is None or not path.is_file():
            self.report({'ERROR'}, 'File contoh tidak ditemukan. Gunakan Pilih file produk.')
            return {'CANCELLED'}
        context.scene.ns_studio.import_scale = '1'
        return bpy.ops.ns.import_product(filepath=str(path))


class NS_PT_Main(bpy.types.Panel):
    bl_label = 'NAKAS / STUDIO 01'
    bl_idname = 'NS_PT_main'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Nakas Studio'

    def draw(self, context):
        layout, scene = self.layout, context.scene
        if not scene.get('ns_ready'):
            layout.label(text='Buka file Nakas_Studio.blend', icon='INFO')
            return
        s = scene.ns_studio
        root = package_root()
        if root:
            box=layout.box()
            box.label(text='MULAI DARI SINI',icon='FILE_FOLDER')
            box.label(text='Produk: '+s.product.name.replace('PROD | ','') if s.product else 'Studio kosong · pilih produk')
            box.operator('ns.import_product',text='Pilih file produk',icon='IMPORT')
            if not s.product:
                box.operator('ns.load_example',icon='OUTLINER_OB_MESH')
            box.operator('wm.save_as_mainfile',text='Simpan proyek sebagai...',icon='FILE_TICK')
        if s.product:
            box = layout.box()
            box.label(text='FINISH', icon='MATERIAL')
            catalog = finish_catalog()
            slots = product_slots(scene)
            if not catalog:
                box.label(text='Library finish belum ada di 02_PRODUK/_FINISH.', icon='ERROR')
            for role, prop_name, label in FINISH_ROLES:
                if role not in catalog:
                    continue
                row = box.row(align=True)
                row.enabled = role in slots
                row.prop(s, prop_name, text=label)
                op = row.operator('ns.apply_finish', text='', icon='FILE_REFRESH')
                op.role = role; op.finish_id = ''
            missing = [role for role, _, _ in FINISH_ROLES if role in catalog and role not in slots]
            if missing:
                box.label(text='Produk ini tidak punya bagian: ' + ', '.join(missing), icon='INFO')
            pesan = s.get('_finish_pesan')
            if pesan:
                box.label(text=str(pesan), icon='ERROR' if str(pesan).startswith('Gagal') else 'CHECKMARK')
            box.label(text='Ganti tekstur kayu: dropdown "Kayu utama" di atas.', icon='INFO')
        if root:
            header, body = layout.panel('ns_finish_library', default_closed=True)
            header.label(text='Tekstur finish produk (Poly Haven)')
            if body:
                body.operator('ns.tambah_tekstur_dasar', icon='IMPORT')
                col = body.column(align=True)
                col.enabled = bool(s.product)
                col.prop(s, 'lib_finish', text='Finish')
                col.prop(s, 'lib_tekstur', text='Tekstur dasar')
                col.operator('ns.pakai_tekstur_finish', icon='CHECKMARK')
                col.operator('ns.bangun_ulang_produk', icon='FILE_REFRESH')
                body.label(text='Finish mengikuti produk.json tiap produk.', icon='INFO')
                body.label(text='Unduh zip Blend 4K Poly Haven.', icon='INFO')
        box=layout.box()
        box.label(text='TAMPILAN & NAVIGASI',icon='VIEW3D')
        row=box.row(align=True)
        row.scale_y=1.4
        for mode,label in [('FAST','Cepat'),('DETAIL','Cek detail'),('PAUSE','Jeda')]:
            row.operator('ns.preview_mode',text=label,depress=s.preview_mode==mode).mode=mode
        box.label(text='Cepat: perkiraan lighting. Detail: Cycles.' if s.preview_mode=='FAST' else 'Tunggu preview stabil.' if s.preview_mode=='DETAIL' else 'Lighting dijeda; watt tetap tersimpan.')
        grid=box.grid_flow(columns=2,row_major=True,align=True)
        for shot in SHOT_IDS:
            if camera_for(scene, shot) is None:
                continue
            label = SHOT_BUTTONS.get(shot, shot)
            grid.operator('ns.quick_angle',text=label,depress=scene.camera==camera_for(scene,shot)).shot=shot
        grid.operator('ns.studio_overview',text='Ruang studio',icon='SCENE_DATA')
        row=box.row(align=True)
        for action,label in [('IN','Perbesar +'),('OUT','Perkecil −')]:
            row.operator('ns.navigate',text=label).action=action
        box.operator('ns.navigate',text='Kembali ke kamera produk',icon='CAMERA_DATA').action='HOME'
        row=box.grid_flow(columns=2,row_major=True,align=True)
        for action,label in [('LEFT','Putar kiri'),('RIGHT','Putar kanan'),('UP','Lihat atas'),('DOWN','Lihat bawah')]:
            row.operator('ns.navigate',text=label).action=action
        box=layout.box()
        box.label(text='KAMERA ANGLE INI',icon='VIEW_CAMERA')
        box.prop(s,'camera_edit',toggle=True,icon='RESTRICT_SELECT_OFF' if s.camera_edit else 'RESTRICT_SELECT_ON')
        if s.camera_edit:
            box.label(text='Putar/Perbesar/Geser memindah kamera, bukan layar.',icon='INFO')
            box.row(align=True).prop(s,'camera_grid',expand=True)
            grid=box.grid_flow(columns=2,row_major=True,align=True)
            for action,label in [('PANLEFT','Geser kiri'),('PANRIGHT','Geser kanan'),('PANUP','Geser atas'),('PANDOWN','Geser bawah')]:
                grid.operator('ns.navigate',text=label).action=action
            if scene.camera:
                box.prop(scene.camera.data,'lens',text='Lensa mm')
        col=box.column(align=True)
        col.enabled=bool(s.product)
        col.operator('ns.lock_camera',text='Kunci angle ini untuk produk ini',icon='LOCKED').scope='ANGLE'
        col.operator('ns.lock_camera',text='Kunci semua angle',icon='LOCKED').scope='ALL'
        col.operator('ns.unlock_camera',text='Lepas kunci angle ini',icon='UNLOCKED').scope='ANGLE'
        locked=locked_shots(scene)
        box.label(text='Terkunci: '+', '.join(SHOT_BUTTONS.get(x,x) for x in locked) if locked else 'Semua angle: framing otomatis',
                  icon='LOCKED' if locked else 'CHECKMARK')
        header, body = layout.panel('ns_product_options', default_closed=True)
        header.label(text='Ganti produk & ukuran')
        if body:
            box = body
            box.label(text='01 / PRODUK · SKALA NYATA', icon='OUTLINER_OB_MESH')
            box.label(text=s.product.name.replace('PROD | ', '') if s.product else 'Belum ada produk')
            try:
                lo, hi = product_bounds(scene)
                size = (hi - lo) * 100
                box.label(text=f'L {size.x:.1f} × D {size.y:.1f} × T {size.z:.1f} cm')
            except ValueError:
                pass
            box.prop(s, 'import_scale')
            box.operator('ns.import_product', icon='IMPORT')
            box.operator('ns.adopt_selected', icon='ADD')
            box.operator('ns.center_product')
            box.operator('ns.rotate_product')
            if s.product:
                for obj in s.product.all_objects:
                    if obj.get('ns_drawer'):
                        box.prop(obj, '["Open (m)"]', text=f'Laci {obj["ns_drawer"]} · m', slider=True)
            row = box.row(align=True)
            row.prop(s, 'actual_width', text='Lebar cm')
            row.operator('ns.scale_product', text='Terapkan')
            group = bpy.data.collections.get('PRODUCTS')
            if group and len(group.children) > 1:
                box.label(text='Produk tersimpan:')
                for coll in group.children:
                    if coll != s.product:
                        op = box.operator('ns.activate_product', text=coll.name.replace('PROD | ', ''), icon='RESTRICT_RENDER_OFF')
                        op.collection_name = coll.name
        header, body = layout.panel('ns_camera_options', default_closed=True)
        header.label(text='Pengaturan kamera lanjutan')
        if body:
            box = body
            box.label(text='02 / KAMERA', icon='CAMERA_DATA')
            if overview_camera():
                box.operator('ns.studio_overview', icon='SCENE_DATA')
            box.prop(s, 'shot', text='')
            box.prop(s, 'frame_margin')
            box.operator('ns.fit_cameras', icon='FULLSCREEN_ENTER')
            box.operator('ns.select_camera')
            if scene.camera:
                box.prop(scene.camera.data, 'lens', text='Lensa mm')
                box.prop(scene.camera.data.dof, 'use_dof', text='Depth of field')
            box.label(text='Detail: rapikan target secara manual.', icon='INFO')
        box = layout.box()
        box.label(text='03 / LIGHTING · PER ANGLE', icon='LIGHT_AREA')
        category, defaults = lighting_profile(scene)
        box.label(text=f"Kategori: {category.title()} · skala rig {float(scene.get('ns_rig_scale', 1.0)):.2f}×")
        rig = next((c for c in bpy.data.collections if c.get('ns_light_shot') == s.shot), None)
        if rig:
            for obj in rig.all_objects:
                if obj.type == 'LIGHT':
                    row = box.row(align=True)
                    row.prop(obj.data, 'energy', text=obj.get('ns_role', obj.name))
                    row.prop(obj.data, 'color', text='')
        box.prop(scene.view_settings, 'exposure', text='Exposure')
        box.prop(s, 'lighting_all_angles', icon='LINKED' if s.lighting_all_angles else 'UNLINKED')
        box.operator('ns.sync_lighting', icon='DUPLICATE')
        row = box.column(align=True)
        row.enabled = defaults is not None
        row.operator('ns.reset_lighting', text='Reset watt angle', icon='LOOP_BACK').scope = 'ANGLE'
        row.operator('ns.reset_lighting', text='Reset watt kategori').scope = 'CATEGORY'
        box.label(text='Tiap angle menyimpan watt sendiri · dapat Undo', icon='INFO')
        box = layout.box()
        box.label(text='LATAR / BACKDROP', icon='WORLD')
        box.prop(s, 'latar', text='')
        box.prop(s, 'latar_otomatis')
        if latar_object('DINDING') is None:
            backdrop = bpy.data.materials.get(CYC_MATERIAL)
            if backdrop:
                node = backdrop.node_tree.nodes.get('Principled BSDF')
                box.prop(node.inputs['Base Color'], 'default_value', text='Backdrop')
        else:
            for role, label in (('LANTAI', 'Lantai'), ('DINDING', 'Dinding')):
                obj = latar_object(role)
                node = obj.active_material.node_tree.nodes.get('Warna') if obj and obj.active_material else None
                if node:
                    box.prop(node.outputs[0], 'default_value', text=label)
            sun = latar_object('MATAHARI')
            if sun:
                row = box.row(align=True)
                row.prop(sun.data, 'energy', text='Matahari')
                row.prop(sun.data, 'color', text='')
        if scene.world and scene.world.node_tree:
            bg = next((n for n in scene.world.node_tree.nodes if n.bl_idname == 'ShaderNodeBackground'), None)
            if bg:
                row = box.row(align=True)
                row.prop(bg.inputs[1], 'default_value', text='Ambient')
                row.prop(bg.inputs[0], 'default_value', text='')
        box.operator('ns.simpan_latar', icon='FILE_TICK')
        pesan = s.get('_latar_pesan')
        if pesan:
            box.label(text=str(pesan), icon='ERROR')
        box = layout.box()
        box.label(text='04 / OUTPUT', icon='OUTPUT')
        box.prop(s, 'quality', text='')
        box.prop(s, 'output', text='')
        for shot in SHOT_IDS:
            if camera_for(scene, shot) is not None:
                box.prop(s, 'include_' + shot.lower())
        box.operator('render.render', text='Render angle aktif', icon='RENDER_STILL').write_still = False
        box.operator('ns.render_batch', icon='RENDER_ANIMATION')
        box.label(text='Setiap batch memakai folder baru.')


CLASSES = (NS_Settings, NS_OT_Center, NS_OT_Fit, NS_OT_Scale, NS_OT_Rotate,
           NS_OT_Adopt, NS_OT_Import, NS_OT_Activate, NS_OT_RenderBatch,
           NS_OT_SelectCamera, NS_OT_Overview, NS_OT_ResetLighting, NS_OT_LightingView,
           NS_OT_PreviewMode, NS_OT_QuickAngle, NS_OT_Navigate, NS_OT_LoadExample,
           NS_OT_ApplyFinish, NS_OT_AddBaseTexture, NS_OT_SetFinishTexture,
           NS_OT_RebuildFinishLibrary, NS_OT_SyncLighting, NS_OT_LockCamera,
           NS_OT_UnlockCamera, NS_OT_SaveLatar, NS_PT_Main)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.ns_studio = PointerProperty(type=NS_Settings)
    subscribe_light_energy()
    if _load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post)


def unregister():
    bpy.msgbus.clear_by_owner(_msgbus_owner)
    if _load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post)
    if hasattr(bpy.types.Scene, 'ns_studio'):
        del bpy.types.Scene.ns_studio
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == '__main__':
    register()
