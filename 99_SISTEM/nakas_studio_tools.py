bl_info = {
    'name': 'Nakas Studio', 'author': 'Nakas Studio', 'version': (2, 5, 0),
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
    ('DETAIL', '05 · Detail', 'Detail laci dan tekstur; atur target bila perlu'),
    ('SIDE_L', '06 · Samping kiri', 'Profil kiri; produk diputar 90° agar latar tetap seamless'),
    ('BASE', '08 · Detail kaki / bawah', 'Close-up sudut rendah: plinth, kaki, dan sambungan bawah'),
    ('CLOSEUP', '09 · Close-up material', 'Close-up tekstur, jahitan, dan sambungan rangka'),
]
SHOT_IDS = [item[0] for item in SHOTS]
# Nomor angle tetap seperti nama kamera (CAM_05_DETAIL dst.). Angle 04 Samping kanan, 07 Belakang, dan kamera
# overview studio dihapus dari default (31 Okt 2026, 99_SISTEM/hapus_kamera_lama.py); nomornya tidak dipakai ulang
# agar driver lampu di file lama tetap menunjuk angle yang benar.
SHOT_NUMBER = {'HERO': 1, 'FRONT': 2, 'LEFT': 3, 'DETAIL': 5, 'SIDE_L': 6, 'BASE': 8, 'CLOSEUP': 9}
REMOVED_SHOTS = ('SIDE', 'BACK')
SHOT_BUTTONS = {'HERO': 'Hero kanan', 'FRONT': 'Depan', 'LEFT': 'Hero kiri',
                'DETAIL': 'Detail produk', 'SIDE_L': 'Samping kiri',
                'BASE': 'Detail kaki', 'CLOSEUP': 'Close-up'}
# Angle baru memakai rig lampu angle sumber (posisi kamera relatif sama).
SHOT_LIGHT_SOURCE = {'SIDE_L': 'FRONT', 'BASE': 'DETAIL', 'CLOSEUP': 'DETAIL'}

# Factory values, never captured from the user's edited lights.
# Profiles keep the original studio and the realistic studio independent.
LIGHTING_DEFAULTS = {
    'NAKAS': {
        'V1': {
            'HERO': (140, 38, 100, 45, 14), 'FRONT': (125, 48, 85, 40, 16),
            'LEFT': (135, 43, 95, 45, 14),
            'DETAIL': (115, 28, 120, 32, 12),
        },
        'V2': {
            'HERO': (238, 64.6, 170, 76.5, 24), 'FRONT': (212.5, 81.6, 144.5, 68, 28),
            'LEFT': (229.5, 73.1, 161.5, 76.5, 24),
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


# --- Pack otomatis ----------------------------------------------------------------------
# Tekstur eksternal (mis. di Downloads) ikut tersimpan di .blend agar file bisa dirender
# di server render tanpa folder tekstur.
def enable_autopack():
    bpy.data.use_autopack = True


def pack_external_images():
    """Pack gambar eksternal yang filenya ada; kembalikan jumlah yang hilang (tidak di-pack)."""
    missing = 0
    for img in bpy.data.images:
        if img.packed_file or img.source not in {'FILE', 'TILED'} or not img.filepath:
            continue
        if not os.path.exists(bpy.path.abspath(img.filepath)):
            print(f'Nakas Studio: tekstur hilang, tidak di-pack: {img.filepath}')
            missing += 1
            continue
        try:
            img.pack()
        except RuntimeError as exc:
            print(f'Nakas Studio: gagal pack {img.name}: {exc}')
            missing += 1
    return missing


@bpy.app.handlers.persistent
def _autopack_load_post(*args):
    enable_autopack()


@bpy.app.handlers.persistent
def _autopack_save_pre(*args):
    # Autopack bawaan Blender memberi error saat ada tekstur hilang, dan script yang menyimpan
    # ikut berhenti. Bila ada yang hilang, autopack bawaan dilewati untuk simpan ini saja
    # (yang ada sudah di-pack di sini); aktif lagi saat file dibuka.
    bpy.data.use_autopack = pack_external_images() == 0


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


# --- Latar 'blend': ruang lifestyle + matahari + finish kayu dari file library ----------
# Dipakai koleksi Doheny: tampilan Lamp Table (dinding belakang + kiri + plafon off-white,
# lantai microcement, Key Sun yang tidak menyinari dinding belakang, Sky Fill, Khronos PBR
# Neutral) disimpan di 02_PRODUK/_LATAR/<file>; latar.json menyebut file dan pengaturannya.
LIFESTYLE_FRONT = -4.6          # tepi depan lantai & dinding samping (minimal)
LIFESTYLE_EXTENT = 4.2          # tepi depan/samping ruang = 4.2x ukuran terbesar produk bila lebih jauh
LIFESTYLE_WIDTH = 9.6           # lebar mesh lantai & dinding belakang bawaan
LIFESTYLE_CEILING = (-1.0, 2.0, 2.8)   # plafon: tepi depan, tepi kanan, tinggi (sisi kanan terbuka untuk matahari)
RIG_COLLECTION = 'LIGHTING | Nakas · per angle'
STUDIO_PREFIX = 'STUDIO |'


def _latar_blend_path(preset):
    root = package_root()
    path = root / LATAR_MANIFEST.parent / preset['file'] if root else None
    if not path or not path.is_file():
        raise ValueError('File latar tidak ditemukan: ' + str(preset.get('file')))
    return path


def _append_latar_blend(preset, coll):
    with bpy.data.libraries.load(str(_latar_blend_path(preset)), link=False) as (src, dst):
        dst.objects = [n for n in src.objects]
    for obj in dst.objects:
        if obj is not None:
            coll.objects.link(obj)
            obj['ns_latar'] = True


def place_lifestyle(scene):
    """Dinding belakang & kiri pada jarak preset dari setengah lebar produk; kanan terbuka."""
    preset = latar_preset(scene.get('ns_latar', '')) or {}
    dist = float(preset.get('jarak_dinding_m', 1.5))
    try:
        lo, hi = product_bounds(scene)
        reach, size = max(abs(lo.x), abs(hi.x)), max(hi - lo)
    except ValueError:
        reach, size, hi = 0.3, 0.6, None
    # Produk besar (ranjang) membuat kamera mundur jauh: lantai & dinding ikut melebar/memanjang
    # (~4.2x ukuran terbesar produk) agar tepi ruang tidak masuk frame atau pantulan.
    extent = max(-LIFESTYLE_FRONT, LIFESTYLE_EXTENT * size)
    wall_y, left_x, front = reach + dist, -(reach + dist), -extent
    if hi is not None and wall_flush(scene) and wall_mount_height(scene) is None:
        wall_y = hi.y + FLUSH_GAP                 # ranjang: headboard rapat ke dinding belakang
        # Kamera ranjang jauh & tinggi: dinding kiri di tepi lantai agar kamera kiri tetap di dalam ruang
        # (kalau tidak, lantai di balik dinding kiri yang terbayang gelap ikut masuk frame).
        left_x = -extent
    elif hi is not None:
        left_x = wall_corner_x(scene, preset, left_x, wall_y, extent)
    wide = max(1.0, 2 * extent / LIFESTYLE_WIDTH)
    wall, floor, ceil = latar_object('DINDING'), latar_object('LANTAI'), latar_object('PLAFON')
    if wall is not None:
        wall['ns_jarak_m'] = dist
        wall['ns_depan_y'] = front
        wall.location = (0, wall_y, 2.1)
        wall.scale = (wide, 1, 1)
    if floor is not None:
        floor.scale = (wide, (wall_y - front) / floor.get('ns_base_depth', 1.0), 1)
        floor.location = (0, (wall_y + front) / 2, 0)
    coll = bpy.data.collections.get(LATAR_COLLECTION)
    for flank in [o for o in coll.objects if o.get('ns_latar_role') == 'SAMPING'] if coll else []:
        flank.scale = (wall_y - front, 1, 1)
        left = flank['ns_latar_x'] < 0
        flank['ns_latar_x'] = left_x if left else -left_x
        flank.location = (flank['ns_latar_x'], (wall_y + front) / 2, 2.1)
        flank.hide_render = not left
    if ceil is not None:
        ceil_front, ceil_right, ceil_z = LIFESTYLE_CEILING
        ceil.scale = (ceil_right - left_x, wall_y - ceil_front, 1)
        ceil.location = ((ceil_right + left_x) / 2, (wall_y + ceil_front) / 2, ceil_z)
    mount_on_wall(scene)
    _key_sun_links(scene)
    place_accent_lights(scene, preset)
    place_gradient_lights(scene, preset)
    place_cavity_light(scene, preset)


# --- Sudut dinding di frame HERO (preset latar 'sudut_dinding') ----------------------------
# Sudut dinding belakang-kiri yang jatuh tepat di tepi siluet produk pada kamera HERO terlihat
# "gantung". Bila titik sudut (di lantai) ada di zona itu, dinding kiri digeser: mode 'tutup' =
# sudut masuk ke belakang produk (posisi x lebar siluet dari tepi kiri), kecuali dinding jadi lebih
# dekat dari jarak_min_m ke produk -> 'jauh' = sudut menjauh jarak_frame (lebar frame) dari siluet.
SUDUT_ZONA = 0.08              # lebar frame: sudut di luar siluet tapi sedekat ini = gantung
SUDUT_MASUK_MIN = 0.2          # lebar siluet: sudut di dalam siluet tapi sedangkal ini = gantung


def wall_corner_x(scene, preset, left_x, wall_y, extent):
    """Posisi x dinding kiri agar sudut dinding tidak menempel di tepi produk pada frame HERO."""
    from bpy_extras.object_utils import world_to_camera_view
    spec = preset.get('sudut_dinding') or {}
    hero, active = camera_for(scene, 'HERO'), scene.camera
    if not spec.get('aktif') or hero is None:
        return left_x
    use_camera(scene, hero)                        # siluet pada putaran dasar produk
    try:
        lo, hi = product_bounds(scene)
        view = [world_to_camera_view(scene, hero, Vector((x, y, z)))
                for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    finally:
        use_camera(scene, active)
    sil_l, sil_r = min(p.x for p in view), max(p.x for p in view)
    sil_b, sil_t = min(p.y for p in view), max(p.y for p in view)

    def corner(x):
        return world_to_camera_view(scene, hero, Vector((x, wall_y, 0.0)))

    c = corner(left_x)
    gap = c.x - sil_l
    if not sil_b < c.y < sil_t or gap <= -SUDUT_ZONA or gap >= SUDUT_MASUK_MIN * (sil_r - sil_l):
        return left_x

    def solve(target):                             # x sudut di frame naik bila dinding digeser ke kanan
        a, b = -extent, lo.x - 0.05
        for _ in range(50):
            m = (a + b) / 2
            a, b = (m, b) if corner(m).x < target else (a, m)
        return (a + b) / 2

    if spec.get('mode', 'tutup') == 'tutup':
        x = solve(sil_l + float(spec.get('posisi', 0.33)) * (sil_r - sil_l))
        if x <= lo.x - float(spec.get('jarak_min_m', 0.5)):
            return x
    return solve(sil_l - float(spec.get('jarak_frame', 0.10)))


# --- Lampu rongga (preset latar 'lampu_rongga') --------------------------------------------
# Produk dengan rongga terbuka di depan (nakas: laci di atas, rak terbuka di bawah) membuat panel
# belakang rongga hampir hitam. Rongga dideteksi dengan ray cast dari depan produk: sel grid yang
# sinarnya masuk lebih dari RONGGA_DALAM x kedalaman produk sebelum mengenai produk = rongga.
# Lampu area dipasang di mulut rongga tepat di bawah tepi atasnya (di bawah laci), menghadap panel
# belakang dan sedikit menunduk; light linking hanya ke produk, tak terlihat kamera/pantulan, dan
# ikut root produk sehingga ikut berputar pada angle samping/belakang. root['ns_rongga'] = False
# mematikan untuk produk tertentu.
CAVITY_LIGHT = 'Latar / lampu rongga'
RONGGA_DALAM = 0.5
RONGGA_GRID = 24
RONGGA_TINGGI_MIN = 0.08       # m


def find_cavity(scene):
    """(x0, x1, z0, z1, y_depan, y_belakang) rongga terbuka terbesar di depan produk, atau None."""
    objs = set(product_objects(scene))
    if not objs:
        return None
    lo, hi = product_bounds(scene)
    depth = hi.y - lo.y
    deps = bpy.context.evaluated_depsgraph_get()
    cells = []
    for i in range(RONGGA_GRID):
        for j in range(RONGGA_GRID):
            x = lo.x + (hi.x - lo.x) * (i + 0.5) / RONGGA_GRID
            z = lo.z + (hi.z - lo.z) * (j + 0.5) / RONGGA_GRID
            origin, hit_y = Vector((x, lo.y - 0.05, z)), None
            for _ in range(6):                                   # lewati objek bukan produk
                ok, loc, _n, _i, obj, _m = scene.ray_cast(deps, origin, Vector((0, 1, 0)), distance=depth + 0.1)
                if not ok:
                    break
                if obj.original in objs:
                    hit_y = loc.y
                    break
                origin = loc + Vector((0, 1e-3, 0))
            if hit_y is not None and hit_y - lo.y > RONGGA_DALAM * depth:
                cells.append((x, z, hit_y))
    if len(cells) < 4:
        return None
    # ambil pita z terpanjang yang kontigu (rongga utama), lalu batas x di pita itu
    zs = sorted({round(c[1], 5) for c in cells})
    step = (hi.z - lo.z) / RONGGA_GRID
    runs, run = [], [zs[0]]
    for z in zs[1:]:
        if z - run[-1] <= step * 1.5:
            run.append(z)
        else:
            runs.append(run); run = [z]
    runs.append(run)
    band = max(runs, key=len)
    inside = [c for c in cells if band[0] - 1e-6 <= round(c[1], 5) <= band[-1] + 1e-6]
    xs = [c[0] for c in inside]
    x0, x1, z0, z1 = min(xs) - step / 2, max(xs) + step / 2, band[0] - step / 2, band[-1] + step / 2
    # Rongga sungguhan: cukup tinggi & lebar (bukan celah antar laci/cermin tipis) dan beratap produk
    # (laci/top di atasnya; ranjang terbuka ke atas sehingga tidak dihitung).
    if z1 - z0 < max(RONGGA_TINGGI_MIN, 0.15 * (hi.z - lo.z)) or x1 - x0 < 0.5 * (hi.x - lo.x):
        return None
    probe = Vector(((x0 + x1) / 2, (lo.y + min(c[2] for c in inside)) / 2, (z0 + z1) / 2))
    ok, _l, _n, _i, obj, _m = scene.ray_cast(deps, probe, Vector((0, 0, 1)), distance=hi.z - probe.z + 0.01)
    if not ok or obj.original not in objs:
        return None
    return (x0, x1, z0, z1, lo.y, min(c[2] for c in inside))


def place_cavity_light(scene, preset):
    old = bpy.data.objects.get(CAVITY_LIGHT)
    if old is not None:
        data = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if data is not None and data.users == 0:
            bpy.data.lights.remove(data)
    spec = preset.get('lampu_rongga') or {}
    coll, root, product = bpy.data.collections.get(LATAR_COLLECTION), root_for(scene), scene.ns_studio.product
    if not spec.get('aktif') or coll is None or root is None or product is None or root.get('ns_rongga') is False:
        return None
    hero, active = camera_for(scene, 'HERO'), scene.camera
    if hero is not None:
        use_camera(scene, hero)                    # ukur pada putaran dasar produk
    try:
        cavity = find_cavity(scene)
        root_base = root.matrix_world.copy()
    finally:
        use_camera(scene, active)
    root['ns_rongga'] = cavity is not None
    if cavity is None:
        return None
    x0, x1, z0, z1, front, back = cavity
    data = bpy.data.lights.new(CAVITY_LIGHT, 'AREA')
    data.shape = 'RECTANGLE'
    data.size = (x1 - x0) * float(spec.get('lebar_faktor', 0.8))
    data.size_y = min(0.04, (z1 - z0) * 0.2)
    data.energy = float(spec.get('energi', 4.0)) * (x1 - x0) / 0.4      # sebanding lebar rongga
    data.energy *= float(root.get('ns_lampu_rongga', 1.0))              # pengali per produk (lihat lampu gradasi)
    data.color = tuple(spec.get('warna', (1.0, 0.95, 0.88)))
    data.spread = math.radians(float(spec.get('sebaran_deg', 120)))
    obj = bpy.data.objects.new(CAVITY_LIGHT, data)
    coll.objects.link(obj)
    obj['ns_latar'] = True
    obj['ns_latar_role'] = 'RONGGA'
    obj.location = ((x0 + x1) / 2, front + float(spec.get('masuk_m', 0.02)), z1 - data.size_y)
    aim(obj, Vector(((x0 + x1) / 2, back, z0 + (z1 - z0) * float(spec.get('bidik_tinggi', 0.35)))))
    obj.visible_camera = obj.visible_glossy = obj.visible_transmission = False
    obj.light_linking.receiver_collection = product
    # Ikut root produk (putaran angle); lokasi/rotasi di atas tetap posisi dunia pada putaran dasar.
    obj.parent = root
    obj.matrix_parent_inverse = root_base.inverted()
    return obj


# --- Produk rapat dinding (ranjang) & cahaya matahari -------------------------------------
# root['ns_rapat_dinding'] = True: dinding belakang ditaruh tepat di belakang produk (headboard).
# Dengan matahari rendah, plafon menutupi area dekat dinding sehingga produk rapat dinding (cermin,
# ranjang) dan dindingnya gelap: untuk produk rapat dinding plafon tidak ikut render.
FLUSH_GAP = 0.02
SUN_RECEIVER = 'ns_receiver_coll'
SUN_BLOCKER = 'Key Sun | plafon tanpa bayangan'


def wall_flush(scene):
    root = root_for(scene)
    return root is not None and (bool(root.get('ns_rapat_dinding')) or root.get('ns_gantung') is not None)


def detect_wall_flush(scene):
    """Ranjang (punya peran KASUR) otomatis rapat dinding bila belum ditentukan."""
    root = root_for(scene)
    if root is None or 'ns_rapat_dinding' in root or not product_slots(scene).get('KASUR'):
        return False
    root['ns_rapat_dinding'] = True
    # Angle yang memutar produk (belakang, samping kiri) akan menabrak dinding.
    for prop in ('include_side_l',):
        setattr(scene.ns_studio, prop, False)
    return True


def _excluding(name, obj):
    """Koleksi light-linking berisi satu objek berstatus EXCLUDE (dibuat ulang bila hilang)."""
    coll = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if obj.name not in coll.objects:
        coll.objects.link(obj)
    for item in coll.collection_objects:
        item.light_linking.link_state = 'EXCLUDE'
    return coll


def _key_sun_links(scene):
    """Key Sun: dinding belakang tetap dikecualikan (sinar langsung membuat dinding hampir putih).
    Produk rapat dinding: plafon disembunyikan dari render, karena tepat di atas produk ia menutupi
    matahari & Sky Fill sehingga produk dan dinding gelap. Produk biasa: plafon tetap seperti dikalibrasi."""
    key, sky, wall, ceil = (latar_object(r) for r in ('MATAHARI', 'LANGIT', 'DINDING', 'PLAFON'))
    if sky is not None:
        sky.light_linking.blocker_collection = None
    if key is not None and wall is not None:
        key.light_linking.receiver_collection = _excluding(str(key.get(SUN_RECEIVER, 'Key Sun | tanpa dinding')), wall)
        key[SUN_RECEIVER] = key.light_linking.receiver_collection.name
        # Preset 'matahari_tanpa_samping': dinding samping juga tanpa sinar langsung (gradasi lembut,
        # tidak putih menyala), mis. Beechwood lifestyle.
        if (latar_preset(scene.get('ns_latar', '')) or {}).get('matahari_tanpa_samping'):
            coll = bpy.data.collections.get(LATAR_COLLECTION)
            for flank in [o for o in coll.objects if o.get('ns_latar_role') == 'SAMPING'] if coll else []:
                _excluding(key.light_linking.receiver_collection.name, flank)
    if key is not None:
        key.light_linking.blocker_collection = None      # plafon tetap membayangi (look terkalibrasi)
    if ceil is not None:
        ceil.hide_render = wall_flush(scene)


# --- Lampu aksen (preset latar 'lampu_aksen') ----------------------------------------------
# Dua softbox strip tegak di depan-kiri & depan-kanan produk, diarahkan ke sisi depan produk
# (bingkai/tiang samping) supaya tepi membulat dapat kilau & dimensi. Light linking: hanya
# menerangi produk, jadi lantai, dinding, dan bayangan Key Sun tidak berubah. Ukuran & posisi
# dihitung dari bounding box produk sehingga berlaku untuk produk dan grup lain.
ACCENT_PREFIX = 'Latar / aksen '


def place_accent_lights(scene, preset):
    coll = bpy.data.collections.get(LATAR_COLLECTION)
    for obj in [o for o in bpy.data.objects if o.name.startswith(ACCENT_PREFIX)]:
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is not None and data.users == 0:
            bpy.data.lights.remove(data)
    spec = preset.get('lampu_aksen') or {}
    product = scene.ns_studio.product
    # Produk gantung (cermin) tidak memakai aksen: kacanya akan memantulkan softbox sebagai strip terang.
    if not spec.get('aktif') or coll is None or product is None or wall_mount_height(scene) is not None:
        return
    try:
        lo, hi = product_bounds(scene)
    except ValueError:
        return
    height = hi.z - lo.z
    for side, sign in (('kiri', -1), ('kanan', 1)):
        data = bpy.data.lights.new(ACCENT_PREFIX + side, 'AREA')
        data.shape = 'RECTANGLE'
        data.size = float(spec.get('lebar_m', 0.25))
        data.size_y = height * float(spec.get('tinggi_faktor', 1.3))
        data.energy = float(spec.get('energi', 60))
        data.color = tuple(spec.get('warna', (1.0, 0.97, 0.93)))
        data.spread = math.radians(float(spec.get('sebaran_deg', 90)))
        obj = bpy.data.objects.new(ACCENT_PREFIX + side, data)
        coll.objects.link(obj)
        obj['ns_latar'] = True
        obj['ns_latar_role'] = 'AKSEN'
        edge = Vector(((hi.x if sign > 0 else lo.x), lo.y, lo.z + height * 0.5))   # sisi depan produk
        obj.location = edge + Vector((sign * float(spec.get('samping_m', 0.6)), -float(spec.get('maju_m', 0.8)),
                                      height * float(spec.get('naik_faktor', 0.15))))
        aim(obj, edge)
        obj.visible_camera = False
        obj.light_linking.receiver_collection = product


# --- Lampu gradasi produk (preset latar 'lampu_gradasi') -----------------------------------
# Dua softbox lebar yang hanya menerangi produk, seperti foto studio: 'atas' di atas tepi depan
# (top terang di depan, meredup ke belakang) dan 'depan' di depan-atas menyorot miring ke bawah
# (front terang di atas, meredup ke kaki). Jarak dekat + sebaran sempit membuat gradasinya.
# Ukuran & posisi dari bounding box produk sehingga berlaku untuk semua produk grup.
GRADIENT_PREFIX = 'Latar / gradasi produk '


def place_gradient_lights(scene, preset):
    coll = bpy.data.collections.get(LATAR_COLLECTION)
    for obj in [o for o in bpy.data.objects if o.name.startswith(GRADIENT_PREFIX)]:
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is not None and data.users == 0:
            bpy.data.lights.remove(data)
    spec = preset.get('lampu_gradasi') or {}
    product = scene.ns_studio.product
    if not spec.get('aktif') or coll is None or product is None or wall_mount_height(scene) is not None:
        return
    try:
        lo, hi = product_bounds(scene)
    except ValueError:
        return
    width, depth, height = hi - lo
    cx = (lo.x + hi.x) / 2
    # Pengali per produk di root (mis. produk kecil): root['ns_lampu_gradasi_atas'] = 0.6. Disimpan di file
    # produk, jadi tetap berlaku saat latar dipasang ulang / sinkron grup.
    root = root_for(scene)
    for side in ('atas', 'depan'):
        s = spec.get(side)
        if not s:
            continue
        data = bpy.data.lights.new(GRADIENT_PREFIX + side, 'AREA')
        data.shape = 'RECTANGLE'
        data.size = width * float(s.get('lebar_faktor', 1.1))
        data.size_y = (depth if side == 'atas' else height) * float(s.get('tinggi_faktor', 0.5))
        factor = float(root.get('ns_lampu_gradasi_' + side, 1.0)) if root is not None else 1.0
        data.energy = float(s.get('energi', 40)) * factor
        data.color = tuple(spec.get('warna', (1.0, 0.97, 0.93)))
        data.spread = math.radians(float(s.get('sebaran_deg', 60)))
        # Tanpa pantulan spekular: softbox tidak tampil sebagai kilau terang, hanya gradasi difus.
        data.specular_factor = float(spec.get('spekular', 1.0))
        obj = bpy.data.objects.new(GRADIENT_PREFIX + side, data)
        coll.objects.link(obj)
        obj['ns_latar'] = True
        obj['ns_latar_role'] = 'GRADASI_PRODUK'
        if side == 'atas':     # di atas tepi depan, bidik tengah top
            obj.location = (cx, lo.y - depth * float(s.get('maju_faktor', 0.2)), hi.z + float(s.get('naik_m', 0.5)))
            target = Vector((cx, (lo.y + hi.y) / 2, hi.z))
        else:                  # depan-atas, bidik bagian atas front
            obj.location = (cx, lo.y - float(s.get('maju_m', 0.9)), hi.z + height * float(s.get('naik_faktor', 0.3)))
            target = Vector((cx, lo.y, lo.z + height * float(s.get('bidik_tinggi', 0.7))))
        aim(obj, target)
        obj.visible_camera = False
        obj.light_linking.receiver_collection = product
    # Kunci: softbox besar hangat di kiri-depan (daylight lembut menyebar), hanya menerangi produk.
    k = spec.get('kunci')
    if k and k.get('aktif', True):
        data = bpy.data.lights.new(GRADIENT_PREFIX + 'kunci', 'AREA')
        data.shape = 'SQUARE'
        data.size = max(width, height) * float(k.get('ukuran_faktor', 1.5))
        data.energy = float(k.get('energi', 100)) * (float(root.get('ns_lampu_gradasi_kunci', 1.0)) if root is not None else 1.0)
        data.color = tuple(k.get('warna', (1.0, 0.85, 0.72)))
        data.specular_factor = float(k.get('spekular', 1.0))
        obj = bpy.data.objects.new(GRADIENT_PREFIX + 'kunci', data)
        coll.objects.link(obj)
        obj['ns_latar'] = True
        obj['ns_latar_role'] = 'GRADASI_PRODUK'
        target = Vector((cx, (lo.y + hi.y) / 2, lo.z + height * 0.55))
        side, elev = math.radians(float(k.get('samping_deg', 45))), math.radians(float(k.get('elevasi_deg', 30)))
        dist = float(k.get('jarak_m', 2.0))
        obj.location = target + Vector((-math.sin(side) * math.cos(elev), -math.cos(side) * math.cos(elev), math.sin(elev))) * dist
        aim(obj, target)
        obj.visible_camera = False
        obj.light_linking.receiver_collection = product
    # Strip: softbox panjang tipis di depan-atas. Elevasi tinggi -> cahaya menyapu muka front (redup di bidang
    # datar) tapi kuat di permukaan yang menghadap atas: bibir bawah cekungan handle & punggung batang handle.
    # 'difus'/'spekular' = faktor cahaya difus/kilau (default hanya kilau).
    s = spec.get('strip')
    if s and s.get('aktif', True):
        data = bpy.data.lights.new(GRADIENT_PREFIX + 'strip', 'AREA')
        data.shape = 'RECTANGLE'
        data.size = width * float(s.get('lebar_faktor', 1.3))
        data.size_y = float(s.get('tebal_m', 0.06))
        data.energy = float(s.get('energi', 80)) * (float(root.get('ns_lampu_gradasi_strip', 1.0)) if root is not None else 1.0)
        data.color = tuple(spec.get('warna', (1.0, 0.97, 0.93)))
        data.diffuse_factor = float(s.get('difus', 0.0))
        data.specular_factor = float(s.get('spekular', 1.0))
        data.volume_factor = 0.0
        obj = bpy.data.objects.new(GRADIENT_PREFIX + 'strip', data)
        coll.objects.link(obj)
        obj['ns_latar'] = True
        obj['ns_latar_role'] = 'GRADASI_PRODUK'
        target = Vector((cx, lo.y, lo.z + height * float(s.get('bidik_tinggi', 0.5))))
        elev = math.radians(float(s.get('elevasi_deg', 45)))
        dist = float(s.get('jarak_m', 1.2))
        obj.location = target + Vector((0, -math.cos(elev) * dist, math.sin(elev) * dist))
        aim(obj, target)
        obj.visible_camera = False
        obj.light_linking.receiver_collection = product


# --- Produk gantung dinding (cermin, panel) -----------------------------------------------
# root['ns_gantung'] = tinggi tengah produk dari lantai (m). Produk ditempel ke dinding belakang
# latar; kamera dibingkai ulang oleh pemanggil. Angle samping/belakang/kaki tidak bermakna.
WALL_GAP = 0.01
WALL_HUNG_HEIGHT = 1.5          # tengah cermin di sekitar tinggi mata
WALL_HUNG_SKIP = ('include_side_l', 'include_base')


def wall_mount_height(scene):
    root = root_for(scene)
    return float(root['ns_gantung']) if root is not None and root.get('ns_gantung') else None


def detect_wall_hung(scene):
    """Cermin tipis (peran CERMIN, tebal < 6 cm) dianggap gantung dinding bila belum ditentukan."""
    root = root_for(scene)
    if root is None or 'ns_gantung' in root or not product_slots(scene).get('CERMIN'):
        return False
    lo, hi = product_bounds(scene)
    if min(hi.x - lo.x, hi.y - lo.y) >= 0.06:
        return False
    root['ns_gantung'] = WALL_HUNG_HEIGHT
    for prop in WALL_HUNG_SKIP:
        setattr(scene.ns_studio, prop, False)
    return True


FRONT_WALL = 'Latar / dinding depan (pantulan)'


def _reflection_wall(wall, show):
    """Dinding di belakang kamera agar cermin memantulkan ruangan, bukan langit kosong. Hanya terlihat
    di pantulan (glossy): tidak terlihat kamera, tidak memberi bayangan/pantulan difus -> cahaya tetap."""
    front = bpy.data.objects.get(FRONT_WALL)
    if not show:
        if front is not None:
            bpy.data.objects.remove(front, do_unlink=True)
        return
    if front is None:
        front = bpy.data.objects.new(FRONT_WALL, wall.data)
        for coll in wall.users_collection:
            coll.objects.link(front)
        front['ns_latar'] = True
        front['ns_latar_role'] = 'DEPAN'
    front.rotation_euler = (math.radians(90), 0, math.radians(180))   # menghadap ke dalam ruang
    front.location = (0, float(wall.get('ns_depan_y', LIFESTYLE_FRONT)), wall.location.z)
    front.scale = wall.scale
    front.visible_camera = front.visible_shadow = front.visible_diffuse = False
    front.visible_transmission = front.visible_volume_scatter = False
    front.visible_glossy = True


def mount_on_wall(scene):
    """Tempel produk gantung ke dinding belakang pada tinggi ns_gantung (pusat produk)."""
    height, wall, root = wall_mount_height(scene), latar_object('DINDING'), root_for(scene)
    if wall is not None:
        _reflection_wall(wall, height is not None)
    if height is None or wall is None or root is None:
        return False
    lo, hi = product_bounds(scene)
    root.location.y += (wall.location.y - WALL_GAP) - hi.y
    root.location.z += height - (lo.z + hi.z) / 2
    bpy.context.view_layer.update()
    return True


def _set_wood_grain(mat, grain):
    """Arah serat tekstur di material: 'U' (serat sepanjang U) atau 'V' (putar 90°)."""
    node = mat.node_tree.nodes.get('Arah serat') if mat and mat.use_nodes else None
    if node is not None:
        node.inputs['Rotation'].default_value[2] = math.radians(90) if grain == 'V' else 0.0


def product_grain(scene):
    """Arah serat UV produk: dari tekstur dasar finish kayu bawaan (finishes.json 'serat_gambar')."""
    path = package_root() / FINISH_MANIFEST if package_root() else None
    bases = json.loads(path.read_text(encoding='utf-8')).get('tekstur_dasar', {}) if path and path.is_file() else {}
    for obj, index in product_slots(scene).get('WOOD_A', []):
        mat = obj.material_slots[index].material
        base = str(mat.get('ns_finish_dasar', '')) if mat else ''
        if mat and mat.get('ns_grain'):
            continue
        if base in bases:
            return bases[base].get('serat_gambar', 'U')
    root = root_for(scene)
    return str(root.get('ns_grain', 'U')) if root is not None else 'U'


def _library_material(preset, name, finish_id):
    """Material finish dari file latar. Preset 'sinkron_material': true -> versi library selalu
    menggantikan versi di file (semua pemakai dipindah, nama tetap), jadi revisi tekstur di library
    berlaku ke semua produk grup saat latar dipasang ulang. Tanpa itu: versi di file dipakai bila ada."""
    current = next((m for m in bpy.data.materials if m.get('ns_finish_id') == finish_id and not m.library), None)
    if current is not None and not preset.get('sinkron_material'):
        return current
    with bpy.data.libraries.load(str(_latar_blend_path(preset)), link=False) as (src, dst):
        dst.materials = [name] if name in src.materials else []
    fresh = dst.materials[0] if dst.materials else None
    if fresh is None:
        return current
    if current is not None:
        keep = current.name
        current.user_remap(fresh)
        bpy.data.materials.remove(current)
        fresh.name = keep
    fresh.use_fake_user = False
    return fresh


def apply_latar_handle(scene, preset):
    """Samakan semua handle (peran HANDLE) produk aktif ke satu material logam dari preset 'finish_handle'."""
    spec = preset.get('finish_handle')
    if not spec or not scene.ns_studio.product:
        return 0
    targets = product_slots(scene).get('HANDLE', [])
    if not targets:
        return 0
    name = 'HW | ' + spec.get('nama', spec['id'])
    mat = next((m for m in bpy.data.materials if m.get('ns_finish_id') == spec['id'] and not m.library), None)
    if spec.get('material') and preset.get('tipe') == 'blend':
        # Handle bertekstur (mis. kayu hitam Beechwood) disimpan di file latar, seperti finish kayu.
        mat = _library_material(preset, spec['material'], spec['id'])
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
    color = tuple(spec.get('warna', (0.55, 0.37, 0.13)))
    bsdf.inputs['Base Color'].default_value = (*color, 1)      # tidak berefek bila warna dari tekstur
    bsdf.inputs['Metallic'].default_value = float(spec.get('metallic', 1.0))
    bsdf.inputs['Roughness'].default_value = float(spec.get('roughness', 0.18))
    mat.diffuse_color, mat.metallic, mat.roughness = (*color, 1), bsdf.inputs['Metallic'].default_value, bsdf.inputs['Roughness'].default_value
    mat['ns_finish_id'], mat['ns_role'], mat['ns_finish_nama'] = spec['id'], 'HANDLE', spec.get('nama', name)
    for obj, index in targets:
        obj.material_slots[index].material = mat
    root = root_for(scene)
    if root is not None:
        root['ns_finish_handle'] = spec['id']
    return len(targets)


def apply_latar_mirror(scene, preset):
    """Kaca cermin (peran CERMIN) mengikuti preset 'finish_cermin': lapisan perak + kaca depan
    (coat ber-IOR kaca, sedikit hijau) sehingga pantulan tidak putih sempurna seperti logam krom."""
    spec = preset.get('finish_cermin')
    if not spec or not scene.ns_studio.product:
        return 0
    targets = product_slots(scene).get('CERMIN', [])
    for mat in {obj.material_slots[index].material for obj, index in targets}:
        if mat is None or not mat.use_nodes:
            continue
        bsdf = next(n for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
        bsdf.inputs['Base Color'].default_value = (*spec.get('perak', (0.86, 0.87, 0.87)), 1)
        bsdf.inputs['Metallic'].default_value = 1.0
        bsdf.inputs['Roughness'].default_value = float(spec.get('roughness', 0.0))
        bsdf.inputs['Coat Weight'].default_value = 1.0
        bsdf.inputs['Coat IOR'].default_value = float(spec.get('ior_kaca', 1.52))
        bsdf.inputs['Coat Roughness'].default_value = 0.0
        bsdf.inputs['Coat Tint'].default_value = (*spec.get('warna_kaca', (0.92, 0.96, 0.94)), 1)
        mat['ns_finish_id'] = spec.get('id', 'cermin')
    return len(targets)


LINEN_GROUP = 'NS | Tenun linen'


def _srgb_lin(c):
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def linen_group():
    """Node group tenun linen: benang silang halus (~0.9 mm) + slub tak beraturan (benang tebal)
    dalam koordinat objek (meter). Keluaran: Height (relief) dan Heather (variasi warna 0..1)."""
    group = bpy.data.node_groups.get(LINEN_GROUP)
    if group is not None and 'Kerut' in group.interface.items_tree:
        return group
    if group is not None:
        bpy.data.node_groups.remove(group)        # versi lama tanpa kerut
    group = bpy.data.node_groups.new(LINEN_GROUP, 'ShaderNodeTree')
    group.interface.new_socket('Height', in_out='OUTPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket('Heather', in_out='OUTPUT', socket_type='NodeSocketFloat')
    group.interface.new_socket('Kerut', in_out='OUTPUT', socket_type='NodeSocketFloat')
    N, L = group.nodes, group.links
    out = N.new('NodeGroupOutput'); out.location = (900, 0)
    tc = N.new('ShaderNodeTexCoord'); tc.location = (-900, 0)
    waves = []
    for axis, y in (('X', 150), ('Y', -50)):
        w = N.new('ShaderNodeTexWave'); w.location = (-500, y)
        w.wave_type, w.bands_direction = 'BANDS', axis
        w.inputs['Scale'].default_value = 1100.0          # ~0.9 mm per benang (koordinat objek, meter)
        w.inputs['Distortion'].default_value = 1.5
        w.inputs['Detail'].default_value = 1.0
        L.new(tc.outputs['Object'], w.inputs['Vector']); waves.append(w)
    weave = N.new('ShaderNodeMath'); weave.operation = 'MULTIPLY'; weave.location = (-250, 50)
    L.new(waves[0].outputs['Fac'], weave.inputs[0]); L.new(waves[1].outputs['Fac'], weave.inputs[1])
    slub = N.new('ShaderNodeTexNoise'); slub.location = (-500, -300)   # benang tebal acak memanjang
    slub.inputs['Scale'].default_value = 140.0; slub.inputs['Detail'].default_value = 4.0
    stretch = N.new('ShaderNodeMapping'); stretch.location = (-700, -300)
    stretch.inputs['Scale'].default_value = (1.0, 8.0, 1.0)
    L.new(tc.outputs['Object'], stretch.inputs['Vector']); L.new(stretch.outputs['Vector'], slub.inputs['Vector'])
    height = N.new('ShaderNodeMath'); height.operation = 'MULTIPLY_ADD'; height.location = (0, 0)
    L.new(slub.outputs['Fac'], height.inputs[0]); height.inputs[1].default_value = 0.6
    L.new(weave.outputs['Value'], height.inputs[2])
    heather = N.new('ShaderNodeTexNoise'); heather.location = (-250, -450)
    heather.inputs['Scale'].default_value = 35.0; heather.inputs['Detail'].default_value = 6.0
    L.new(tc.outputs['Object'], heather.inputs['Vector'])
    L.new(height.outputs['Value'], out.inputs['Height']); L.new(heather.outputs['Fac'], out.inputs['Heather'])
    # Kerut kain linen: lipatan lembut acak ~5-15 cm dengan garis kusut kecil.
    fold = N.new('ShaderNodeTexNoise'); fold.location = (-250, -650)
    fold.inputs['Scale'].default_value = 9.0; fold.inputs['Detail'].default_value = 3.0
    fold.inputs['Distortion'].default_value = 1.8
    L.new(tc.outputs['Object'], fold.inputs['Vector'])
    crease = N.new('ShaderNodeMath'); crease.operation = 'PINGPONG'; crease.location = (0, -650)
    crease.inputs[1].default_value = 0.08                     # punggung lipatan tajam-lembut
    L.new(fold.outputs['Fac'], crease.inputs[0])
    L.new(crease.outputs['Value'], out.inputs['Kerut'])
    return group


BOUCLE_GROUP = 'NS | Boucle'


def boucle_group():
    """Node group boucle: gumpalan benang ikal rapat (~2-3 mm, Voronoi halus) dengan kelompok gumpalan
    lebih besar; keluaran sama dengan tenun linen (Height, Heather, Kerut) agar bisa saling ganti."""
    group = bpy.data.node_groups.get(BOUCLE_GROUP)
    if group is not None:
        return group
    group = bpy.data.node_groups.new(BOUCLE_GROUP, 'ShaderNodeTree')
    for name in ('Height', 'Heather', 'Kerut'):
        group.interface.new_socket(name, in_out='OUTPUT', socket_type='NodeSocketFloat')
    N, L = group.nodes, group.links
    out = N.new('NodeGroupOutput'); out.location = (800, 0)
    tc = N.new('ShaderNodeTexCoord'); tc.location = (-900, 0)
    warp = N.new('ShaderNodeTexNoise'); warp.location = (-650, -250)
    warp.inputs['Scale'].default_value = 60.0
    mix = N.new('ShaderNodeVectorMath'); mix.operation = 'MULTIPLY_ADD'; mix.location = (-450, 0)
    L.new(warp.outputs['Color'], mix.inputs[0]); mix.inputs[1].default_value = (0.004, 0.004, 0.004)
    L.new(tc.outputs['Object'], mix.inputs[2]); L.new(tc.outputs['Object'], warp.inputs['Vector'])
    loops = N.new('ShaderNodeTexVoronoi'); loops.location = (-250, 100)
    loops.feature = 'SMOOTH_F1'; loops.inputs['Scale'].default_value = 300.0
    L.new(mix.outputs['Vector'], loops.inputs['Vector'])
    bump = N.new('ShaderNodeMath'); bump.operation = 'SUBTRACT'; bump.location = (0, 100)
    bump.inputs[0].default_value = 1.0; L.new(loops.outputs['Distance'], bump.inputs[1])
    clump = N.new('ShaderNodeTexNoise'); clump.location = (-250, -150)
    clump.inputs['Scale'].default_value = 60.0; clump.inputs['Detail'].default_value = 3.0
    L.new(tc.outputs['Object'], clump.inputs['Vector'])
    height = N.new('ShaderNodeMath'); height.operation = 'MULTIPLY_ADD'; height.location = (250, 50)
    L.new(clump.outputs['Fac'], height.inputs[0]); height.inputs[1].default_value = 0.8
    L.new(bump.outputs['Value'], height.inputs[2])
    L.new(height.outputs['Value'], out.inputs['Height'])
    L.new(clump.outputs['Fac'], out.inputs['Heather'])
    soft = N.new('ShaderNodeTexNoise'); soft.location = (250, -250)
    soft.inputs['Scale'].default_value = 6.0
    L.new(tc.outputs['Object'], soft.inputs['Vector']); L.new(soft.outputs['Fac'], out.inputs['Kerut'])
    return group


# Jenis tekstur kain: relief tenun, kerut, dan sheen per jenis (dipilih per peran lewat preset 'tekstur').
FABRIC_TYPES = {
    'linen': {'group': linen_group, 'relief': 1.0, 'kerut': 1.0, 'distance': 0.0006, 'sheen': None},
    'katun': {'group': linen_group, 'relief': 0.25, 'kerut': 0.8, 'distance': 0.0006, 'sheen': 0.2},
    'boucle': {'group': boucle_group, 'relief': 2.2, 'kerut': 0.3, 'distance': 0.002, 'sheen': 0.15},
}


def apply_latar_fabric(scene, preset):
    """Kain produk aktif (peran dari preset 'finish_kain') jadi linen: warna per peran (sRGB), sheen
    linen, tenun & slub sebagai relief, dan heather tipis pada warna. Material produk diubah di tempat."""
    spec = preset.get('finish_kain')
    if not spec or not scene.ns_studio.product:
        return 0
    slots = product_slots(scene)
    done = set()
    for role, color in spec.get('warna', {}).items():
        for obj, index in slots.get(role, []):
            mat = obj.material_slots[index].material
            if mat is None or mat.name in done or not mat.use_nodes:
                continue
            done.add(mat.name)
            kind = FABRIC_TYPES[spec.get('tekstur', {}).get(role, 'linen')]
            N, L = mat.node_tree.nodes, mat.node_tree.links
            bsdf = next(n for n in N if n.bl_idname == 'ShaderNodeBsdfPrincipled')
            # Sumber normal asli (kerutan bawaan produk), juga saat dijalankan ulang di atas tenun lama.
            prev = bsdf.inputs['Normal'].links[0].from_socket if bsdf.inputs['Normal'].is_linked else None
            while prev is not None and prev.node.name.startswith('Linen |'):
                old_in = prev.node.inputs['Normal']
                prev = old_in.links[0].from_socket if old_in.is_linked else None
            for n in [n for n in N if n.name.startswith('Linen |')]:
                N.remove(n)
            for link in list(bsdf.inputs['Base Color'].links):
                L.remove(link)
            base = N.new('ShaderNodeRGB'); base.name = base.label = 'Linen | warna'
            base.outputs[0].default_value = (*_srgb_lin(color), 1)
            weave = N.new('ShaderNodeGroup'); weave.name = weave.label = 'Linen | tenun'
            weave.node_tree = kind['group']()
            shade = N.new('ShaderNodeMapRange'); shade.name = 'Linen | heather'
            shade.inputs['To Min'].default_value = 1 - float(spec.get('heather', 0.08))
            shade.inputs['To Max'].default_value = 1 + float(spec.get('heather', 0.08))
            L.new(weave.outputs['Heather'], shade.inputs['Value'])
            tint = N.new('ShaderNodeVectorMath'); tint.name = 'Linen | warna x heather'; tint.operation = 'SCALE'
            L.new(base.outputs[0], tint.inputs[0]); L.new(shade.outputs['Result'], tint.inputs['Scale'])
            L.new(tint.outputs['Vector'], bsdf.inputs['Base Color'])
            bump = N.new('ShaderNodeBump'); bump.name = 'Linen | relief'
            bump.inputs['Strength'].default_value = min(1.0, float(spec.get('relief', 0.35)) * kind['relief'])
            bump.inputs['Distance'].default_value = kind['distance']
            L.new(weave.outputs['Height'], bump.inputs['Height'])
            fold = N.new('ShaderNodeBump'); fold.name = 'Linen | kerut'
            fold.inputs['Strength'].default_value = float(spec.get('kerut', 0.3)) * kind['kerut']
            fold.inputs['Distance'].default_value = 0.01
            L.new(weave.outputs['Kerut'], fold.inputs['Height'])
            if prev is not None:
                L.new(prev, fold.inputs['Normal'])           # kerutan bawaan produk tetap, ditumpuk
            L.new(fold.outputs['Normal'], bump.inputs['Normal'])
            L.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
            bsdf.inputs['Sheen Weight'].default_value = kind['sheen'] if kind['sheen'] is not None else float(spec.get('sheen', 0.3))
            bsdf.inputs['Sheen Roughness'].default_value = 0.6
            bsdf.inputs['Roughness'].default_value = 0.9
            mat['ns_finish_kain'] = role
    return len(done)


def apply_latar_finish(scene, preset):
    """Pasang finish kayu preset ke semua slot WOOD_A produk aktif, arah serat ikut produk."""
    apply_latar_handle(scene, preset)
    apply_latar_mirror(scene, preset)
    apply_latar_fabric(scene, preset)
    spec = preset.get('finish_kayu')
    if not spec or not scene.ns_studio.product:
        return 0
    targets = product_slots(scene).get('WOOD_A', [])
    if not targets:
        return 0
    # 'serat' di preset = konvensi UV satu grup (mis. Beechwood 'V': serat mengikuti V di semua produk).
    grain = spec.get('serat') or product_grain(scene)
    name = spec['material']
    mat = _library_material(preset, name, spec['id'])
    mat['ns_finish_id'], mat['ns_role'] = spec['id'], 'WOOD_A'
    mat['ns_finish_nama'], mat['ns_grain'] = spec.get('nama', name), grain
    _set_wood_grain(mat, grain)
    for obj, index in targets:
        obj.material_slots[index].material = mat
    root = root_for(scene)
    if root is not None:
        root['ns_grain'] = grain
        allowed = [str(v) for v in root.get('ns_finishes', [])]
        if allowed and spec['id'] not in allowed:
            root['ns_finishes'] = allowed + [spec['id']]
        root['ns_finish_wood_a'] = spec['id']
    sync_finish_props(scene)
    return len(targets)


def _apply_latar_render(scene, preset):
    """Warna/exposure dan rig softbox mengikuti preset; preset lain mengembalikan nilai asli."""
    view = scene.view_settings
    render = preset.get('render')
    if render:
        if 'ns_latar_view_asli' not in scene:
            scene['ns_latar_view_asli'] = {'transform': view.view_transform, 'look': view.look, 'exposure': view.exposure,
                                           'wb': view.use_white_balance, 'wb_k': view.white_balance_temperature,
                                           'wb_tint': view.white_balance_tint}
        view.view_transform = render.get('view_transform', view.view_transform)
        view.look = render.get('look', 'None')
        view.exposure = float(render.get('exposure', view.exposure))
        # White balance opsional (K; < 6500 = lebih dingin), mis. preset Beechwood dari editan foto referensi
        view.use_white_balance = 'white_balance_k' in render
        view.white_balance_temperature = float(render.get('white_balance_k', 6500.0))
        view.white_balance_tint = float(render.get('white_balance_tint', 0.0))
    elif 'ns_latar_view_asli' in scene:
        asli = scene['ns_latar_view_asli']
        view.view_transform, view.look, view.exposure = asli['transform'], asli['look'], asli['exposure']
        view.use_white_balance = asli.get('wb', False)
        view.white_balance_temperature = asli.get('wb_k', 6500.0)
        view.white_balance_tint = asli.get('wb_tint', 0.0)
        del scene['ns_latar_view_asli']
    rig = bpy.data.collections.get(RIG_COLLECTION)
    if rig is not None:
        rig.hide_render = rig.hide_viewport = not preset.get('rig_lampu', True)
    # Studio template (dinding ruang, balok plafon, tripod, koper) membayangi ruang lifestyle
    # dari matahari; preset 'studio': false menyembunyikannya di render dan viewport.
    for coll in bpy.data.collections:
        if coll.name.startswith(STUDIO_PREFIX):
            coll.hide_render = coll.hide_viewport = not preset.get('studio', True)


def place_latar(scene):
    """Dinding di belakang produk: jarak preset dari sisi terjauh produk (produk bisa diputar 90°
    untuk angle samping), dan selalu di belakang lampu rim agar lampu tidak tertutup."""
    if (latar_preset(scene.get('ns_latar', '')) or {}).get('tipe') == 'blend':
        place_lifestyle(scene)
        return
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
    elif preset['tipe'] == 'blend':
        if coll is None:
            coll = bpy.data.collections.new(LATAR_COLLECTION)
            scene.collection.children.link(coll)
        if cyc:
            cyc.hide_render = True
            cyc.hide_set(True)
        _append_latar_blend(preset, coll)
        scene['ns_latar'] = latar_id
        bpy.context.view_layer.update()
        place_lifestyle(scene)
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
    _apply_latar_render(scene, preset)
    apply_latar_finish(scene, preset)


def latar_for_product(name):
    """Preset pertama yang kata 'koleksi'-nya ada di nama produk/file (tanpa beda huruf besar).
    Produk tanpa koleksi memakai preset umum pertama (koleksi kosong), bukan latar produk
    sebelumnya, supaya hasil impor tidak bergantung pada urutan impor."""
    low = name.lower()
    catalog = latar_catalog()
    return next((p['id'] for p in catalog if any(k and k.lower() in low for k in p.get('koleksi', []))),
                next((p['id'] for p in catalog if not p.get('koleksi')), None))


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
        elif base['tipe'] == 'blend':
            pass  # ruang, lampu, dan material tersimpan di file latar; ubah lewat file itu
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
            cam['ns_shot_index'] = SHOT_NUMBER[shot]
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
        index = SHOT_NUMBER[shot]
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


# Output 16:9 landscape (lebar × tinggi).
RESOLUTIONS = {'PREVIEW': (960, 540), 'FINAL': (1920, 1080)}


def apply_quality(scene):
    """Set resolusi & samples sesuai kualitas; True bila rasio/ukuran berubah."""
    settings = scene.ns_studio
    size = RESOLUTIONS[settings.quality]
    changed = (scene.render.resolution_x, scene.render.resolution_y) != size
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    if settings.quality == 'PREVIEW':
        scene.cycles.samples = 48
        scene.cycles.adaptive_threshold = 0.08
    else:
        scene.cycles.samples = 192
        scene.cycles.adaptive_threshold = 0.015
    return changed


def quality_updated(settings, context):
    if apply_quality(context.scene):
        # Framing otomatis dihitung dari rasio render; hitung ulang setelah rasio berubah.
        try:
            fit_cameras(context.scene)
        except ValueError:
            pass


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
                         items=[('PREVIEW', 'Preview · 960×540 (16:9)', ''),
                                ('FINAL', 'Final · 1920×1080 (16:9)', '')])
    frame_margin: FloatProperty(name='Ruang tepi', default=1.18, min=1.02, max=2.0,
                                description='Ruang di sekeliling produk pada framing Penuh')
    framing: EnumProperty(name='Framing', default='SQUARE', update=lambda self, context: framing_updated(context),
                          items=[('SQUARE', 'Kotak 1:1 tengah', 'Produk mengisi kotak 1:1 di tengah frame 16:9 (atas-bawah ±70% tinggi); siap dikrop 1:1'),
                                 ('FULL', 'Penuh', 'Produk mengisi frame dengan ruang tepi')])
    actual_width: FloatProperty(name='Lebar nyata (cm)', default=50.0, min=1, max=500)
    import_scale: EnumProperty(name='Faktor setelah impor', default='1', items=[
        ('1', '1 × · pertahankan ukuran', 'Importer FBX/GLTF biasanya sudah membaca unit'),
        ('0.01', '0.01 × · angka mentah cm ke m', ''),
        ('0.001', '0.001 × · angka mentah mm ke m', ''),
    ])
    include_hero: BoolProperty(name='Hero 3/4 kanan', default=True)
    include_front: BoolProperty(name='Depan', default=True)
    include_left: BoolProperty(name='3/4 kiri', default=True)
    include_detail: BoolProperty(name='Detail', default=True)
    include_side_l: BoolProperty(name='Samping kiri', default=True)
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
    return sorted((k for k in root[CAMERA_LOCK].keys() if k in SHOT_IDS), key=SHOT_IDS.index) if root and CAMERA_LOCK in root else []


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


# Framing 1:1: produk mengisi kotak persegi setinggi frame di tengah 16:9.
# Lebar boleh sampai 94% lebar kotak; tinggi dibatasi 70% tinggi frame agar atas-bawah tetap lega.
SQUARE_FILL_X = 0.94
SQUARE_FILL_Y = 0.70


# Arah kamera (dari target ke kamera) yang menimpa ns_direction template. Hero 3/4 lebih rendah
# (~11° menunduk, bukan 22.7°) sesuai posisi kamera Lamp Table yang disetujui.
SHOT_DIRECTIONS = {
    'HERO': (0.4667, -0.8626, 0.1953),
    'LEFT': (-0.4295, -0.8819, 0.1944),
}


# Ranjang (produk rapat dinding): angle referensi dari Beechwood Bed yang disetel manual (31 Okt 2026), dipakai
# semua ranjang. Per angle: 'arah' (target -> kamera), 'lensa' (mm), 'target' (fraksi bbox: x/y dari pusat, z dari
# lantai), 'jarak' (pengali jarak framing otomatis), 'fstop' (bukaan DOF, opsional). Hero/Left rendah & hampir datar dengan lensa 105 mm (perspektif
# datar: kaki depan & belakang sebanding), Front/Side sejajar mata, Base & Close-up detail kepala ranjang.
# Detail & Back tetap otomatis. Per produk bisa ditimpa: root['ns_kamera_<SHOT>'] = {kunci yang sama}.
BED_SHOTS = {
    'HERO': {'arah': (0.4808, -0.8746, 0.0627), 'lensa': 105.0, 'target': (0.001, -0.001, 0.458), 'jarak': 0.836},
    'LEFT': {'arah': (-0.4444, -0.8952, 0.0349), 'lensa': 105.0, 'target': (-0.001, 0.0, 0.465), 'jarak': 0.837},
    'FRONT': {'arah': (-0.014, -0.9999, 0.0065), 'lensa': 70.0, 'target': (0.0, 0.0, 0.489), 'jarak': 0.995},
    'SIDE_L': {'arah': (0.014, -0.9997, -0.0187), 'lensa': 70.0, 'target': (0.0, 0.0, 0.495), 'jarak': 0.998},
    'BASE': {'arah': (0.6097, -0.677, 0.4123), 'lensa': 42.0, 'target': (0.096, -0.129, -0.173), 'jarak': 1.493},
    # Close-up: titik bidik di muka depan jok headboard -> fokus DOF tepat di headboard; f/8 agar bantal ikut tajam.
    'CLOSEUP': {'arah': (-0.015, -0.9998, 0.0164), 'lensa': 53.0, 'target': (0.289, 0.467, 0.7906), 'jarak': 1.0311, 'fstop': 8.0},
}


# Close-up sudut untuk produk gantung (cermin): target sedikit masuk dari sudut kiri-atas bingkai.
CORNER_INSET = 0.05            # x ukuran terkecil produk
CORNER_DIRECTION = (-0.55, -0.62, 0.56)
CORNER_DISTANCE = 0.7          # x ukuran terbesar produk
CORNER_SHIFT = (0.1, 0.08)     # geser bidikan ke kanan / bawah (x lebar / tinggi produk)
CORNER_LENS = 70.0
CORNER_FSTOP = 2.0


def framing_updated(context):
    try:
        fit_cameras(context.scene)
    except ValueError:
        pass


def fit_cameras(scene):
    product_bounds(scene)
    apply_quality(scene)
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
        if shot in SHOT_DIRECTIONS:
            cam['ns_direction'] = list(SHOT_DIRECTIONS[shot])
        # Ranjang: angle referensi BED_SHOTS; per produk ditimpa root['ns_kamera_<SHOT>'] (kunci sama).
        spec = dict(BED_SHOTS.get(shot, {})) if wall_flush(scene) and wall_mount_height(scene) is None else {}
        root = root_for(scene)
        override = root.get('ns_kamera_' + shot) if root is not None else None
        if override:
            spec.update(override.to_dict() if hasattr(override, 'to_dict') else override)
        # Lensa asli kamera template disimpan dulu dan dikembalikan bila angle tanpa lensa khusus.
        if 'lensa' in spec:
            if 'ns_lensa_asli' not in cam:
                cam['ns_lensa_asli'] = cam.data.lens
            cam.data.lens = float(spec['lensa'])
        elif 'ns_lensa_asli' in cam:
            cam.data.lens = float(cam.pop('ns_lensa_asli'))
        if 'arah' in spec:
            cam['ns_direction'] = list(spec['arah'])
        if 'fstop' in spec:
            if 'ns_fstop_asli' not in cam:
                cam['ns_fstop_asli'] = cam.data.dof.aperture_fstop
            cam.data.dof.aperture_fstop = float(spec['fstop'])
        elif 'ns_fstop_asli' in cam:
            cam.data.dof.aperture_fstop = float(cam.pop('ns_fstop_asli'))
        fraction = Vector(spec.get('target', cam.get('ns_target_fraction', (0, 0, 0.5))))
        target = Vector((center.x + size.x * fraction.x,
                         center.y + size.y * fraction.y,
                         lo.z + size.z * fraction.z))
        direction = Vector(cam['ns_direction']).normalized()
        corner_shot = shot == 'CLOSEUP' and wall_mount_height(scene) is not None
        if corner_shot:
            # Cermin gantung: sudut kiri-atas bingkai dari depan-kiri-atas, ruang tajam dangkal
            # (bingkai menjauh diagonal, latar & pantulan blur) seperti foto detail produk.
            inset = min(size.x, size.z) * CORNER_INSET
            # Bidik sedikit ke dalam kaca -> sudut jatuh di kiri-atas frame, batang atas menjauh ke kanan.
            target = Vector((lo.x + inset + size.x * CORNER_SHIFT[0], lo.y, hi.z - inset - size.z * CORNER_SHIFT[1]))
            direction = Vector(CORNER_DIRECTION).normalized()
        cam.location = target + direction
        aim(cam, target)
        if corner_shot:
            distance = max(size.x, size.z) * CORNER_DISTANCE
            cam.data.lens = CORNER_LENS
            cam.data.dof.use_dof = True
            cam.data.dof.aperture_fstop = CORNER_FSTOP
        elif shot == 'DETAIL' or cam.get('ns_fit') == 'detail':
            # Close-up: jarak sebanding ukuran produk, bukan membingkai seluruh produk.
            distance = max(size) * float(cam.get('ns_detail_scale', 1.45))
        else:
            # Solve the pinhole frustum for every world-space bound corner.
            # Vertical FOV follows render aspect, pixel aspect, and sensor fit.
            aspect = (scene.render.resolution_x * scene.render.pixel_aspect_x /
                      (scene.render.resolution_y * scene.render.pixel_aspect_y))
            tan_x = cam.data.sensor_width / (2 * cam.data.lens)
            tan_y = tan_x / aspect
            margin = scene.ns_studio.frame_margin
            if scene.ns_studio.framing == 'SQUARE':
                # Lebar kotak 1:1 = tinggi frame = 1/aspect dari lebar frame, berpusat di target.
                tan_x, tan_y = tan_x * min(1.0, 1 / aspect) * SQUARE_FILL_X, tan_y * SQUARE_FILL_Y
                margin = 1.0
            inverse = cam.rotation_euler.to_matrix().transposed()
            distance = 0.01
            for point in corners:
                local = inverse @ (point - target)
                distance = max(distance, local.z + abs(local.x) / tan_x * margin,
                               local.z + abs(local.y) / tan_y * margin)
        distance *= float(spec.get('jarak', 1.0))
        cam.location = target + direction * distance
        aim(cam, target)
        cam.data.dof.focus_distance = distance
        if corner_shot:
            # Fokus tepat di sudut bingkai (bagian depan), bukan di kaca yang dibidik.
            corner = Vector((lo.x + inset, lo.y, hi.z - inset))
            forward = cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))
            cam.data.dof.focus_distance = (corner - cam.location).dot(forward)
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
            detect_wall_hung(context.scene)
            detect_wall_flush(context.scene)
            fit_cameras(context.scene)
            apply_rig_scale(context.scene, rig_scale_factor(context.scene))
            # Cocokkan koleksi pada path relatif paket saja: nama folder di PC lain tidak ikut menentukan latar.
            pkg = package_root()
            try:
                where = str(Path(filepath).resolve().relative_to(pkg)) if pkg else Path(filepath).name
            except ValueError:
                where = Path(filepath).name
            latar_id = latar_for_product(root.name + ' ' + where) if context.scene.ns_studio.latar_otomatis else None
            if latar_id and latar_id != context.scene.get('ns_latar'):
                select_latar(context.scene, latar_id)
            else:
                place_latar(context.scene)
                apply_latar_finish(context.scene, latar_preset(context.scene.get('ns_latar', '')) or {})
            if wall_flush(context.scene):
                fit_cameras(context.scene)          # produk/dinding sudah dirapatkan
            if (latar_preset(context.scene.get('ns_latar', '')) or {}).get('render'):
                pass  # warna/exposure ditentukan preset latar koleksi (mis. Doheny lifestyle)
            elif root.get('ns_exposure') is not None:
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
            # File lama masih 1:1 -> ubah ke 16:9 dan bingkai ulang sebelum render.
            if apply_quality(context.scene):
                fit_cameras(context.scene)
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


def _is_package(path):
    return (path/'01_STUDIO').is_dir() and (path/'02_PRODUK').is_dir()


def package_root():
    """Folder Studio_Furniture: dari file yang terbuka, lalu dari lokasi add-on ini (dimuat
    mulai_sesi.py dari 99_SISTEM), lalu variabel STUDIO_FURNITURE_ROOT (add-on yang dipasang
    lewat Preferences dan file yang dibuka dari luar paket, mis. di PC lain)."""
    candidates = list(Path(bpy.data.filepath).parents) if bpy.data.filepath else []
    candidates.append(Path(__file__).resolve().parents[1])
    if os.environ.get('STUDIO_FURNITURE_ROOT'):
        candidates.append(Path(os.environ['STUDIO_FURNITURE_ROOT']))
    return next((p for p in candidates if _is_package(p)), None)


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
            box.prop(s, 'shot', text='')
            box.prop(s, 'framing')
            if s.framing == 'FULL':
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


# =========================================================================================
# TALA STUDIO: studio katalog yang bisa dipakai ulang (sweep dinding/lantai, rig lampu relatif
# kamera, preset kamera, finish brushed, batch render per item x angle). Melengkapi Nakas
# Studio: latar/angle Nakas tidak dihapus, hanya dinonaktifkan dari render selama studio aktif.
# Semua angka default ada di TALA_SETTINGS.
# =========================================================================================
TALA_SETTINGS = {
    # Ukuran acuan: lampu & backdrop dirancang untuk produk dengan ukuran terbesar ini (m).
    # Ukuran, jarak lampu ~ s, daya ~ s^2 (s = ukuran terbesar / REF_SIZE) -> eksposur tetap.
    'REF_SIZE': 1.2,
    'FRONT_AXIS': (0.0, -1.0),          # arah muka produk di dunia (x, y)
    # Lampu (relatif kamera: -Y rig = arah kamera, +X = kanan frame). pos = arah x jarak (m @ acuan)
    'KEY':  {'arah': (0.75, -0.85, 0.85), 'jarak': 2.4, 'ukuran': 2.2, 'daya': 900.0, 'warna': (1.0, 0.82, 0.66)},
    'TOP':  {'arah': (0.0, 0.45, 1.0), 'jarak': 1.5, 'ukuran': (2.0, 1.0), 'daya': 380.0, 'warna': (1.0, 0.82, 0.68)},
    'FILL': {'arah': (-1.0, -0.9, 0.3), 'jarak': 2.8, 'ukuran': 1.6, 'daya': 220.0, 'warna': (1.0, 0.95, 0.9)},
    'WORLD': {'warna': (0.80, 0.72, 0.62), 'kuat': 0.35},
    # Backdrop sweep (ukuran x ukuran terbesar produk)
    'WALL_COLOR': '#D8CDB8', 'WALL_TOP_GAIN': 0.18, 'WALL_ROUGH': 0.9,
    'FLOOR_COLOR': '#7F817C', 'FLOOR_ROUGH': 0.85, 'FLOOR_NOISE': 0.08, 'FLOOR_SPECKLE': 0.25,
    'SWEEP': {'lebar': 9.0, 'dinding_jarak': 0.6, 'tinggi': 4.0, 'depan': 6.0, 'radius': 0.35},
    # Kamera
    'LENS': 50.0, 'ELEVATION': 20.0, 'FILL_WIDTH': 0.78, 'FILL_HEIGHT_MAX': 0.86,
    'PRESETS': {'FRONT': (0.0, -14.0), '3Q_LEFT': (-38.0, 0.0), '3Q_RIGHT': (38.0, 0.0),
                'SIDE': (-90.0, 0.0), 'TOP_3Q': (-38.0, 20.0)},       # (azimut, tambahan elevasi) derajat
    # Warna (AgX, kontras sedang-rendah)
    'VIEW': 'AgX', 'LOOK': 'Medium Low Contrast', 'EXPOSURE': -2.72,
    # Finish brushed
    'FINISH': {'kuat': 0.15, 'skala': 1.0, 'rotasi': 0.0, 'pori': 0.5},
    'WOOD_WORDS': ('wood', 'kayu', 'walnut', 'oak', 'teak', 'jati', 'veneer', 'fin |'),
    # Render
    'RES': (1920, 1280), 'SAMPLES': 256, 'NOISE_THRESHOLD': 0.01,
}
TALA_PRESET_ITEMS = [('FRONT', 'Front', ''), ('3Q_LEFT', '3/4 Left', ''), ('3Q_RIGHT', '3/4 Right', ''),
                     ('SIDE', 'Side', ''), ('TOP_3Q', 'Top 3/4', '')]
TALA_COLL = 'TALA_STUDIO'
TALA_RIG, TALA_CAM, TALA_SWEEP = 'TALA | rig', 'TALA | kamera', 'TALA | sweep'
TALA_GROUP = 'TALA_BrushedFinish'


def _hex_lin(hex_color):
    return _srgb_lin([int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)])


def tala_targets(context):
    """Objek produk: objek terpilih (geometri); tanpa pilihan -> produk aktif Nakas."""
    studio = bpy.data.collections.get(TALA_COLL)
    own = set(studio.all_objects) if studio else set()
    sel = [o for o in context.selected_objects if o.type in GEOMETRY_TYPES and o not in own]
    if sel:
        return sel
    coll = context.scene.ns_studio.product
    return [o for o in coll.all_objects if o.type in GEOMETRY_TYPES and not o.hide_render] if coll else []


def tala_bounds(objects):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    pts = []
    for obj in objects:
        ev = obj.evaluated_get(depsgraph)
        pts.extend(ev.matrix_world @ Vector(c) for c in ev.bound_box)
    if not pts:
        raise ValueError('Tidak ada geometri untuk dibingkai.')
    return (Vector([min(p[a] for p in pts) for a in range(3)]),
            Vector([max(p[a] for p in pts) for a in range(3)]))


def tala_collection():
    coll = bpy.data.collections.get(TALA_COLL)
    if coll is None:
        coll = bpy.data.collections.new(TALA_COLL)
        bpy.context.scene.collection.children.link(coll)
    return coll


def _tala_material(name, hex_color, rough, kind):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = rough
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    base = (*_hex_lin(hex_color), 1.0)
    S = TALA_SETTINGS
    if kind == 'WALL':        # sedikit lebih terang ke atas (koordinat Generated Z sweep)
        tc = nt.nodes.new('ShaderNodeTexCoord')
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        rng = nt.nodes.new('ShaderNodeMapRange')
        rng.inputs['From Min'].default_value, rng.inputs['From Max'].default_value = 0.1, 1.0
        rng.inputs['To Min'].default_value, rng.inputs['To Max'].default_value = 1.0, 1.0 + S['WALL_TOP_GAIN']
        mul = nt.nodes.new('ShaderNodeMix'); mul.data_type, mul.blend_type = 'RGBA', 'MULTIPLY'
        mul.inputs['Factor'].default_value = 1.0
        nt.links.new(tc.outputs['Generated'], sep.inputs['Vector'])
        nt.links.new(sep.outputs['Z'], rng.inputs['Value'])
        mul.inputs[6].default_value = base
        comb = nt.nodes.new('ShaderNodeCombineColor')
        for k in ('Red', 'Green', 'Blue'):
            nt.links.new(rng.outputs['Result'], comb.inputs[k])
        nt.links.new(comb.outputs['Color'], mul.inputs[7])
        nt.links.new(mul.outputs[2], bsdf.inputs['Base Color'])
    else:                     # beton: noise lembut + bintik kecil terang/gelap (koordinat objek = meter)
        tc = nt.nodes.new('ShaderNodeTexCoord')
        noise = nt.nodes.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 3.0
        noise.inputs['Detail'].default_value = 6.0
        vor = nt.nodes.new('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value = 140.0
        vor.feature = 'F1'
        spk = nt.nodes.new('ShaderNodeMapRange')
        spk.inputs['From Min'].default_value, spk.inputs['From Max'].default_value = 0.0, 0.12
        spk.inputs['To Min'].default_value, spk.inputs['To Max'].default_value = 1.0 - S['FLOOR_SPECKLE'], 1.0
        var = nt.nodes.new('ShaderNodeMapRange')
        var.inputs['To Min'].default_value, var.inputs['To Max'].default_value = 1.0 - S['FLOOR_NOISE'], 1.0 + S['FLOOR_NOISE']
        mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'
        comb = nt.nodes.new('ShaderNodeCombineColor')
        mix = nt.nodes.new('ShaderNodeMix'); mix.data_type, mix.blend_type = 'RGBA', 'MULTIPLY'
        mix.inputs['Factor'].default_value = 1.0
        mix.inputs[6].default_value = base
        nt.links.new(tc.outputs['Object'], noise.inputs['Vector'])
        nt.links.new(tc.outputs['Object'], vor.inputs['Vector'])
        nt.links.new(noise.outputs['Fac'], var.inputs['Value'])
        nt.links.new(vor.outputs['Distance'], spk.inputs['Value'])
        nt.links.new(var.outputs['Result'], mul.inputs[0]); nt.links.new(spk.outputs['Result'], mul.inputs[1])
        for k in ('Red', 'Green', 'Blue'):
            nt.links.new(mul.outputs['Value'], comb.inputs[k])
        nt.links.new(comb.outputs['Color'], mix.inputs[7])
        nt.links.new(mix.outputs[2], bsdf.inputs['Base Color'])
    mat.diffuse_color = base
    return mat


def tala_sweep_mesh(size):
    """Sweep: lantai (slot 1) -> lengkung -> dinding (slot 0). Rig: -Y = kamera, dinding di +Y."""
    W = TALA_SETTINGS['SWEEP']
    half, back = W['lebar'] * size / 2, W['dinding_jarak'] * size
    r, top, front = W['radius'] * size, W['tinggi'] * size, -W['depan'] * size
    prof = [(front, 0.0), (back - r, 0.0)]
    prof += [(back - r + r * math.sin(math.pi / 2 * i / 10), r - r * math.cos(math.pi / 2 * i / 10)) for i in range(1, 11)]
    prof += [(back, top)]
    me = bpy.data.meshes.get(TALA_SWEEP) or bpy.data.meshes.new(TALA_SWEEP)
    verts = [(x, y, z) for y, z in prof for x in (-half, half)]
    faces = [(2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2) for i in range(len(prof) - 1)]
    me.clear_geometry()
    me.from_pydata(verts, [], faces)
    for p in me.polygons:
        p.material_index = 1 if p.center.z < r * 0.5 else 0        # lantai sampai tengah lengkung
        p.use_smooth = True
    me.update()
    return me


def tala_rig():
    return bpy.data.objects.get(TALA_RIG)


def build_tala_studio(scene):
    S = TALA_SETTINGS
    coll = tala_collection()
    # Simpan keadaan asli sekali (dipulihkan oleh 'Lepas studio')
    if 'tala_asli' not in scene:
        v = scene.view_settings
        latar = bpy.data.collections.get(LATAR_COLLECTION)
        scene['tala_asli'] = {'world': scene.world.name if scene.world else '', 'view': v.view_transform, 'look': v.look,
                              'exposure': v.exposure, 'wb': v.use_white_balance,
                              'camera': scene.camera.name if scene.camera else '',
                              'latar_render': bool(latar.hide_render) if latar else True}
    latar = bpy.data.collections.get(LATAR_COLLECTION)
    if latar:
        latar.hide_render = True             # latar Nakas tidak dihapus, hanya tidak dirender
    rig = tala_rig()
    if rig is None:
        rig = bpy.data.objects.new(TALA_RIG, None)
        rig.empty_display_type, rig.empty_display_size = 'ARROWS', 0.3
        coll.objects.link(rig)
    cam = bpy.data.objects.get(TALA_CAM)
    if cam is None:
        cam = bpy.data.objects.new(TALA_CAM, bpy.data.cameras.new(TALA_CAM))
        coll.objects.link(cam)
    cam['ns_shot_index'] = 0                 # lampu per angle Nakas mati, produk tidak diputar driver
    cam['ns_product_yaw'] = 0.0
    sweep = bpy.data.objects.get(TALA_SWEEP)
    if sweep is None:
        sweep = bpy.data.objects.new(TALA_SWEEP, tala_sweep_mesh(1.0))
        coll.objects.link(sweep)
    sweep.data.materials.clear()
    sweep.data.materials.append(_tala_material('TALA | Dinding beige', S['WALL_COLOR'], S['WALL_ROUGH'], 'WALL'))
    sweep.data.materials.append(_tala_material('TALA | Lantai beton', S['FLOOR_COLOR'], S['FLOOR_ROUGH'], 'FLOOR'))
    sweep.parent = rig
    for role in ('KEY', 'TOP', 'FILL'):
        name = 'TALA | ' + role.lower()
        obj = bpy.data.objects.get(name)
        if obj is None:
            obj = bpy.data.objects.new(name, bpy.data.lights.new(name, 'AREA'))
            coll.objects.link(obj)
        obj.parent = rig
        obj.visible_camera = False
        obj['tala_role'] = role
    world = bpy.data.worlds.get('TALA | World') or bpy.data.worlds.new('TALA | World')
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.bl_idname == 'ShaderNodeBackground')
    bg.inputs['Color'].default_value = (*S['WORLD']['warna'], 1)
    bg.inputs['Strength'].default_value = S['WORLD']['kuat']
    scene.world = world
    v = scene.view_settings
    v.view_transform = S['VIEW']
    for look in (f"{S['VIEW']} - {S['LOOK']}", S['LOOK'], 'None'):     # nama look tergantung view transform
        try:
            v.look = look
            break
        except TypeError:
            continue
    v.exposure = S['EXPOSURE']
    v.use_white_balance = False
    scene.camera = cam
    tala_follow(scene)
    return coll


def tala_follow(scene):
    """Rig mengikuti azimut kamera (Locked Track) atau tetap di dunia."""
    rig, cam = tala_rig(), bpy.data.objects.get(TALA_CAM)
    if rig is None:
        return
    con = rig.constraints.get('TALA ikuti kamera') or rig.constraints.new('LOCKED_TRACK')
    con.name = 'TALA ikuti kamera'
    con.target = scene.camera if scene.camera and scene.camera.type == 'CAMERA' else cam
    con.track_axis, con.lock_axis = 'TRACK_NEGATIVE_Y', 'LOCK_Z'
    follow = scene.tala.follow_camera
    if not follow and not con.mute:          # bekukan arah saat ini
        bpy.context.view_layer.update()
        mw = rig.matrix_world.copy()
        con.mute = True
        rig.matrix_world = mw
    con.mute = not follow


def fit_tala(scene, objects):
    S = TALA_SETTINGS
    lo, hi = tala_bounds(objects)
    size = max(hi - lo)
    s = size / S['REF_SIZE']
    rig = tala_rig()
    if rig is None:
        raise ValueError('Bangun studio dulu.')
    rig.location = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    rig['tala_size'] = size
    rig['tala_bounds'] = [*lo, *hi]
    sweep = bpy.data.objects[TALA_SWEEP]
    tala_sweep_mesh(size)
    sweep.location = (0, 0, 0)
    center_h = (hi.z - lo.z) / 2
    for obj in rig.children:
        role = obj.get('tala_role')
        if not role:
            continue
        L = S[role]
        d = Vector(L['arah']).normalized() * L['jarak'] * s
        obj.location = d + Vector((0, 0, center_h * (0.4 if role == 'FILL' else 1.0)))
        obj.data.shape = 'RECTANGLE'
        sz = L['ukuran'] if isinstance(L['ukuran'], tuple) else (L['ukuran'], L['ukuran'])
        obj.data.size, obj.data.size_y = sz[0] * s, sz[1] * s
        obj.data.energy = L['daya'] * s * s
        obj.data.color = L['warna']
        target = Vector((0, 0, center_h if role != 'TOP' else hi.z - lo.z))
        obj.rotation_euler = (target - obj.location).to_track_quat('-Z', 'Y').to_euler()
    frame_tala(scene, (lo, hi), scene.tala.preset)


def frame_tala(scene, bounds, preset):
    """Kamera tegak (vertikal lurus) + shift; jarak dicari agar produk mengisi FILL_WIDTH lebar frame."""
    S, t = TALA_SETTINGS, scene.tala
    lo, hi = bounds
    cam = bpy.data.objects[TALA_CAM]
    cam.data.lens, cam.data.sensor_fit, cam.data.sensor_width = t.lens, 'HORIZONTAL', 36.0
    az_off, el_add = S['PRESETS'][preset]
    fx, fy = S['FRONT_AXIS']
    az = math.atan2(fy, fx) + math.radians(az_off)        # arah dari pusat ke kamera
    elev = math.radians(t.elevation + el_add)
    center = (lo + hi) / 2
    corners = [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    out = Vector((math.cos(az), math.sin(az), 0))
    fwd = -out
    right = Vector((fwd.y, -fwd.x, 0))
    aspect = scene.render.resolution_y / scene.render.resolution_x
    k = t.lens / 36.0

    def project(D):
        pos = Vector((center.x, center.y, 0)) + out * D
        pos.z = center.z + D * math.tan(elev)
        xs, ys = [], []
        for c in corners:
            q = c - pos
            z = q.dot(fwd)
            xs.append(k * q.dot(right) / z); ys.append(k * q.z / z)
        return pos, xs, ys

    a, b = 0.3, 60.0
    for _ in range(40):
        D = (a + b) / 2
        _, xs, ys = project(D)
        need = max((max(xs) - min(xs)) / S['FILL_WIDTH'], (max(ys) - min(ys)) / (aspect * S['FILL_HEIGHT_MAX']))
        a, b = (D, b) if need > 1 else (a, D)
    pos, xs, ys = project(b)
    cam.location = pos
    cam.rotation_euler = (math.pi / 2, 0, math.atan2(fwd.y, fwd.x) - math.pi / 2)
    cam.data.shift_x, cam.data.shift_y = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    cam.data.clip_end = max(100.0, b * 4)
    scene.camera = cam
    scene.tala.preset = preset
    tala_follow(scene)
    bpy.context.view_layer.update()


def tala_group():
    """TALA_BrushedFinish: goresan halus searah serat + pori sedikit timbul -> Normal & Roughness."""
    g = bpy.data.node_groups.get(TALA_GROUP)
    if g:
        return g
    g = bpy.data.node_groups.new(TALA_GROUP, 'ShaderNodeTree')
    it = g.interface
    for name, typ, val in (('Roughness', 'NodeSocketFloat', 0.4), ('Normal', 'NodeSocketVector', None),
                           ('Strength', 'NodeSocketFloat', 0.15), ('Scale', 'NodeSocketFloat', 1.0),
                           ('Rotation', 'NodeSocketFloat', 0.0), ('Pores', 'NodeSocketFloat', 0.5)):
        sock = it.new_socket(name, in_out='INPUT', socket_type=typ)
        if val is not None:
            sock.default_value = val
    it.new_socket('Roughness', in_out='OUTPUT', socket_type='NodeSocketFloat')
    it.new_socket('Normal', in_out='OUTPUT', socket_type='NodeSocketVector')
    N, L = g.nodes, g.links
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    tc = N.new('ShaderNodeTexCoord')
    rot = N.new('ShaderNodeVectorRotate'); rot.rotation_type = 'Z_AXIS'
    L.new(tc.outputs['UV'], rot.inputs['Vector']); L.new(gi.outputs['Rotation'], rot.inputs['Angle'])
    sc_line = N.new('ShaderNodeCombineXYZ'); sc_line.inputs['X'].default_value = 8.0      # goresan memanjang sepanjang U
    mul_line = N.new('ShaderNodeVectorMath'); mul_line.operation = 'MULTIPLY'
    sc_y = N.new('ShaderNodeMath'); sc_y.operation = 'MULTIPLY'; sc_y.inputs[1].default_value = 900.0
    sc_x = N.new('ShaderNodeMath'); sc_x.operation = 'MULTIPLY'; sc_x.inputs[1].default_value = 12.0
    L.new(gi.outputs['Scale'], sc_y.inputs[0]); L.new(gi.outputs['Scale'], sc_x.inputs[0])
    L.new(sc_x.outputs[0], sc_line.inputs['X']); L.new(sc_y.outputs[0], sc_line.inputs['Y'])
    L.new(rot.outputs['Vector'], mul_line.inputs[0]); L.new(sc_line.outputs['Vector'], mul_line.inputs[1])
    brush = N.new('ShaderNodeTexNoise'); brush.inputs['Detail'].default_value = 4.0
    L.new(mul_line.outputs['Vector'], brush.inputs['Vector'])
    pore_s = N.new('ShaderNodeVectorMath'); pore_s.operation = 'SCALE'
    sc_p = N.new('ShaderNodeMath'); sc_p.operation = 'MULTIPLY'; sc_p.inputs[1].default_value = 600.0
    L.new(gi.outputs['Scale'], sc_p.inputs[0])
    L.new(rot.outputs['Vector'], pore_s.inputs['Vector']); L.new(sc_p.outputs[0], pore_s.inputs['Scale'])
    pore = N.new('ShaderNodeTexNoise'); pore.inputs['Detail'].default_value = 1.0
    L.new(pore_s.outputs['Vector'], pore.inputs['Vector'])
    pmask = N.new('ShaderNodeMapRange')
    pmask.inputs['From Min'].default_value, pmask.inputs['From Max'].default_value = 0.62, 0.72
    L.new(pore.outputs['Fac'], pmask.inputs['Value'])
    pamt = N.new('ShaderNodeMath'); pamt.operation = 'MULTIPLY'
    L.new(pmask.outputs['Result'], pamt.inputs[0]); L.new(gi.outputs['Pores'], pamt.inputs[1])
    height = N.new('ShaderNodeMath'); height.operation = 'ADD'
    L.new(brush.outputs['Fac'], height.inputs[0]); L.new(pamt.outputs[0], height.inputs[1])
    bump = N.new('ShaderNodeBump'); bump.inputs['Distance'].default_value = 0.0005
    L.new(gi.outputs['Strength'], bump.inputs['Strength']); L.new(height.outputs[0], bump.inputs['Height'])
    L.new(gi.outputs['Normal'], bump.inputs['Normal']); L.new(bump.outputs['Normal'], go.inputs['Normal'])
    # roughness: goresan +-0.03, pori sedikit lebih kasar
    dr = N.new('ShaderNodeMath'); dr.operation = 'MULTIPLY_ADD'
    dr.inputs[1].default_value, dr.inputs[2].default_value = 0.06, -0.03
    L.new(brush.outputs['Fac'], dr.inputs[0])
    dp = N.new('ShaderNodeMath'); dp.operation = 'MULTIPLY_ADD'; dp.inputs[1].default_value = 0.05
    L.new(pamt.outputs[0], dp.inputs[0]); L.new(dr.outputs[0], dp.inputs[2])
    r = N.new('ShaderNodeMath'); r.operation = 'ADD'; r.use_clamp = True
    L.new(gi.outputs['Roughness'], r.inputs[0]); L.new(dp.outputs[0], r.inputs[1])
    L.new(r.outputs[0], go.inputs['Roughness'])
    return g


def tala_wood_materials(objects):
    words = TALA_SETTINGS['WOOD_WORDS']
    mats = {}
    for o in objects:
        for sl in getattr(o, 'material_slots', []):
            m = sl.material
            if m and m.node_tree and (m.get('ns_role', '').startswith('WOOD') or any(w in m.name.lower() for w in words)) \
                    and not m.name.startswith('HW |'):
                mats[m.name] = m
    return list(mats.values())


def apply_tala_finish(mat, values):
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'), None)
    if bsdf is None:
        return False
    node = nt.nodes.get(TALA_GROUP)
    if node is None:
        node = nt.nodes.new('ShaderNodeGroup'); node.name = node.label = TALA_GROUP
        node.node_tree = tala_group()
        node.location = bsdf.location + Vector((-250, -400))
        rin, nin = bsdf.inputs['Roughness'], bsdf.inputs['Normal']
        node['asal_rough_nilai'] = rin.default_value
        if rin.is_linked:
            l = rin.links[0]; node['asal_rough'] = [l.from_node.name, l.from_socket.identifier]
            nt.links.new(l.from_socket, node.inputs['Roughness'])
        else:
            node.inputs['Roughness'].default_value = rin.default_value
        if nin.is_linked:
            l = nin.links[0]; node['asal_normal'] = [l.from_node.name, l.from_socket.identifier]
            nt.links.new(l.from_socket, node.inputs['Normal'])
        else:
            geo = nt.nodes.new('ShaderNodeNewGeometry'); geo.name = TALA_GROUP + ' | geometri'
            geo.location = node.location + Vector((-200, 0))
            nt.links.new(geo.outputs['Normal'], node.inputs['Normal'])
        nt.links.new(node.outputs['Roughness'], rin)
        nt.links.new(node.outputs['Normal'], nin)
    for k, sock in (('kuat', 'Strength'), ('skala', 'Scale'), ('rotasi', 'Rotation'), ('pori', 'Pores')):
        node.inputs[sock].default_value = math.radians(values[k]) if k == 'rotasi' else values[k]
    return True


def remove_tala_finish(mat):
    nt = mat.node_tree
    node = nt.nodes.get(TALA_GROUP) if nt else None
    if node is None:
        return False
    bsdf = next(n for n in nt.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
    for key, sock in (('asal_rough', 'Roughness'), ('asal_normal', 'Normal')):
        src = node.get(key)
        if src and src[0] in nt.nodes:
            out = next(o for o in nt.nodes[src[0]].outputs if o.identifier == src[1])
            nt.links.new(out, bsdf.inputs[sock])
        else:
            for l in list(bsdf.inputs[sock].links):
                nt.links.remove(l)
    bsdf.inputs['Roughness'].default_value = node.get('asal_rough_nilai', bsdf.inputs['Roughness'].default_value)
    geo = nt.nodes.get(TALA_GROUP + ' | geometri')
    if geo:
        nt.nodes.remove(geo)
    nt.nodes.remove(node)
    return True


def remove_tala_studio(scene):
    """Lepas studio: koleksi TALA_STUDIO dihapus (dibuat oleh add-on), keadaan asli dipulihkan."""
    asli = scene.get('tala_asli')
    coll = bpy.data.collections.get(TALA_COLL)
    if coll:
        for o in list(coll.all_objects):
            data = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            if data is not None and data.users == 0:
                (bpy.data.lights if isinstance(data, bpy.types.Light) else bpy.data.cameras
                 if isinstance(data, bpy.types.Camera) else bpy.data.meshes).remove(data)
        bpy.data.collections.remove(coll)
    if asli:
        asli = asli.to_dict()
        if asli['world'] in bpy.data.worlds:
            scene.world = bpy.data.worlds[asli['world']]
        v = scene.view_settings
        v.view_transform, v.look, v.exposure, v.use_white_balance = asli['view'], asli['look'], asli['exposure'], asli['wb']
        if asli['camera'] in bpy.data.objects:
            scene.camera = bpy.data.objects[asli['camera']]
        latar = bpy.data.collections.get(LATAR_COLLECTION)
        if latar:
            latar.hide_render = asli['latar_render']
        del scene['tala_asli']


def tala_render_settings(scene):
    t = scene.tala
    scene.render.engine = 'CYCLES'
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = t.res_x, t.res_y, 100
    scene.cycles.samples = t.samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = TALA_SETTINGS['NOISE_THRESHOLD']
    scene.cycles.use_denoising = True
    scene.render.film_transparent = False


def tala_item_objects(item):
    if item.collection:
        return [o for o in item.collection.all_objects if o.type in GEOMETRY_TYPES]
    return [item.object] + [c for c in item.object.children_recursive if c.type in GEOMETRY_TYPES] if item.object else []


def _tala_res_updated(t, context):
    s = context.scene
    if s.camera and s.camera.name == TALA_CAM:
        s.render.resolution_x, s.render.resolution_y = t.res_x, t.res_y


def _tala_cam_updated(t, context):
    rig = tala_rig()
    if rig and 'tala_bounds' in rig and bpy.data.objects.get(TALA_CAM):
        b = list(rig['tala_bounds'])          # bingkai ulang dari bounds produk terakhir
        frame_tala(context.scene, (Vector(b[:3]), Vector(b[3:])), context.scene.tala.preset)


def _tala_follow_updated(t, context):
    tala_follow(context.scene)


class TALA_Item(bpy.types.PropertyGroup):
    object: PointerProperty(type=bpy.types.Object, name='Objek')
    collection: PointerProperty(type=bpy.types.Collection, name='Koleksi')
    use: BoolProperty(name='Render', default=True)


class TALA_Settings(bpy.types.PropertyGroup):
    preset: EnumProperty(name='Angle', items=TALA_PRESET_ITEMS, default='3Q_LEFT')
    lens: FloatProperty(name='Lensa (mm)', default=TALA_SETTINGS['LENS'], min=18, max=200, update=_tala_cam_updated)
    elevation: FloatProperty(name='Elevasi (°)', default=TALA_SETTINGS['ELEVATION'], min=-10, max=60, update=_tala_cam_updated)
    follow_camera: BoolProperty(name='Lampu ikut kamera', default=True, update=_tala_follow_updated,
                                description='Rig lampu & backdrop berputar mengikuti azimut kamera; mati = tetap di dunia')
    strength: FloatProperty(name='Kekuatan', default=TALA_SETTINGS['FINISH']['kuat'], min=0, max=1)
    scale: FloatProperty(name='Skala', default=TALA_SETTINGS['FINISH']['skala'], min=0.05, max=10)
    rotation: FloatProperty(name='Arah serat (°)', default=TALA_SETTINGS['FINISH']['rotasi'], min=-180, max=180)
    pores: FloatProperty(name='Pori', default=TALA_SETTINGS['FINISH']['pori'], min=0, max=2)
    res_x: bpy.props.IntProperty(name='Lebar', default=TALA_SETTINGS['RES'][0], min=64, update=_tala_res_updated)
    res_y: bpy.props.IntProperty(name='Tinggi', default=TALA_SETTINGS['RES'][1], min=64, update=_tala_res_updated)
    samples: bpy.props.IntProperty(name='Samples', default=TALA_SETTINGS['SAMPLES'], min=1)
    items: bpy.props.CollectionProperty(type=TALA_Item)
    item_index: bpy.props.IntProperty()


for _p, _label, _d in TALA_PRESET_ITEMS:
    TALA_Settings.__annotations__['use_' + _p.lower()] = BoolProperty(name=_label, default=_p in ('FRONT', '3Q_LEFT', '3Q_RIGHT'))


class TALA_OT_Build(bpy.types.Operator):
    bl_idname = 'tala.build_studio'
    bl_label = 'Build Studio'
    bl_description = 'Buat/ganti koleksi TALA_STUDIO: sweep dinding beige + lantai beton, rig key/top/fill, world, AgX'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        build_tala_studio(context.scene)
        objs = tala_targets(context)
        if objs:
            try:
                fit_tala(context.scene, objs)
            except ValueError as exc:
                self.report({'WARNING'}, str(exc))
        tala_render_settings(context.scene)
        return {'FINISHED'}


class TALA_OT_Fit(bpy.types.Operator):
    bl_idname = 'tala.fit_selected'
    bl_label = 'Fit to Selected'
    bl_description = 'Skala & posisi backdrop, lampu (ukuran ~ s, daya ~ s²) dan jarak kamera dari bounding box pilihan'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            fit_tala(context.scene, tala_targets(context))
        except (ValueError, KeyError) as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        return {'FINISHED'}


class TALA_OT_Preset(bpy.types.Operator):
    bl_idname = 'tala.camera_preset'
    bl_label = 'Angle kamera'
    bl_options = {'REGISTER', 'UNDO'}
    preset: StringProperty(default='3Q_LEFT')

    def execute(self, context):
        rig = tala_rig()
        if rig is None or 'tala_bounds' not in rig:
            self.report({'ERROR'}, 'Build Studio / Fit to Selected dulu.'); return {'CANCELLED'}
        context.scene.tala.preset = self.preset
        _tala_cam_updated(context.scene.tala, context)
        return {'FINISHED'}


class TALA_OT_ApplyFinish(bpy.types.Operator):
    bl_idname = 'tala.apply_finish'
    bl_label = 'Apply Finish'
    bl_description = 'Sisipkan TALA_BrushedFinish (bump & roughness) ke material kayu produk; warna & tekstur asli tetap'
    bl_options = {'REGISTER', 'UNDO'}
    remove: BoolProperty(default=False)

    def execute(self, context):
        t = context.scene.tala
        values = {'kuat': t.strength, 'skala': t.scale, 'rotasi': t.rotation, 'pori': t.pores}
        mats = tala_wood_materials(tala_targets(context))
        done = [m.name for m in mats if (remove_tala_finish(m) if self.remove else apply_tala_finish(m, values))]
        self.report({'INFO'}, ('Dilepas: ' if self.remove else 'Finish: ') + (', '.join(done) or 'tidak ada material kayu'))
        return {'FINISHED'}


class TALA_OT_Remove(bpy.types.Operator):
    bl_idname = 'tala.remove_studio'
    bl_label = 'Lepas studio'
    bl_description = 'Hapus koleksi TALA_STUDIO buatan add-on dan pulihkan world, warna, kamera & latar sebelumnya'
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        remove_tala_studio(context.scene)
        return {'FINISHED'}


class TALA_OT_ItemAdd(bpy.types.Operator):
    bl_idname = 'tala.item_add'
    bl_label = 'Tambah item'
    bl_description = 'Tambah objek terpilih (root) atau koleksi aktif ke daftar batch'
    kind: StringProperty(default='OBJECT')

    def execute(self, context):
        t = context.scene.tala
        if self.kind == 'COLLECTION':
            coll = context.view_layer.active_layer_collection.collection
            if coll and coll != context.scene.collection:
                it = t.items.add(); it.collection = coll
        else:
            for o in context.selected_objects:
                if o.parent is None or o.parent not in context.selected_objects:
                    it = t.items.add(); it.object = o
        return {'FINISHED'}


class TALA_OT_ItemRemove(bpy.types.Operator):
    bl_idname = 'tala.item_remove'
    bl_label = 'Keluarkan item'

    def execute(self, context):
        t = context.scene.tala
        if 0 <= t.item_index < len(t.items):
            t.items.remove(t.item_index)
        return {'FINISHED'}


class TALA_UL_Items(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
        row = layout.row(align=True)
        row.prop(item, 'use', text='')
        target = item.collection or item.object
        row.label(text=target.name if target else '(hilang)', icon='OUTLINER_COLLECTION' if item.collection else 'OBJECT_DATA')


class TALA_OT_BatchRender(bpy.types.Operator):
    bl_idname = 'tala.batch_render'
    bl_label = 'Batch Render'
    bl_description = 'Setiap item tercentang x angle tercentang: fit, bingkai, render ke //renders/<item>_<angle>.png'

    def execute(self, context):
        scene, t = context.scene, context.scene.tala
        items = [it for it in t.items if it.use and (it.collection or it.object)]
        presets = [p for p, _l, _d in TALA_PRESET_ITEMS if getattr(t, 'use_' + p.lower())]
        if not items or not presets:
            self.report({'ERROR'}, 'Centang minimal satu item dan satu angle.'); return {'CANCELLED'}
        build_tala_studio(scene)
        tala_render_settings(scene)
        all_objs = [tala_item_objects(it) for it in items]
        state = {o.name: o.hide_render for objs in all_objs for o in objs}
        folder = Path(bpy.path.abspath('//renders'))
        folder.mkdir(parents=True, exist_ok=True)
        old_path, done = scene.render.filepath, []
        try:
            for it, mine in zip(items, all_objs):
                for objs in all_objs:            # hanya item ini yang terender
                    for o in objs:
                        o.hide_render = o not in mine or state[o.name]
                visible = [o for o in mine if not state[o.name]]
                fit_tala(scene, visible)
                label = bpy.path.clean_name((it.collection or it.object).name)
                bounds = tala_bounds(visible)
                for p in presets:
                    frame_tala(scene, bounds, p)
                    scene.render.filepath = str(folder / f'{label}_{p.lower()}.png')
                    bpy.ops.render.render(write_still=True)
                    done.append(scene.render.filepath)
        finally:
            for name, hidden in state.items():
                if name in bpy.data.objects:
                    bpy.data.objects[name].hide_render = hidden
            scene.render.filepath = old_path
        self.report({'INFO'}, f'{len(done)} render tersimpan di {folder}')
        return {'FINISHED'}


class TALA_PT_Main(bpy.types.Panel):
    bl_label = 'Studio katalog'
    bl_idname = 'TALA_PT_main'
    bl_space_type, bl_region_type = 'VIEW_3D', 'UI'
    bl_category = 'Tala Studio'

    def draw(self, context):
        t, layout = context.scene.tala, self.layout
        box = layout.box(); box.label(text='Studio', icon='WORLD')
        row = box.row(align=True)
        row.operator('tala.build_studio', icon='SCENE')
        row.operator('tala.fit_selected', icon='SHADING_BBOX')
        box.prop(t, 'follow_camera')
        box.operator('tala.remove_studio', icon='TRASH')
        box = layout.box(); box.label(text='Kamera', icon='CAMERA_DATA')
        grid = box.grid_flow(columns=3, align=True)
        for p, label, _d in TALA_PRESET_ITEMS:
            grid.operator('tala.camera_preset', text=label, depress=t.preset == p).preset = p
        box.prop(t, 'lens'); box.prop(t, 'elevation')
        box = layout.box(); box.label(text='Finish kayu', icon='MATERIAL')
        for prop in ('strength', 'scale', 'rotation', 'pores'):
            box.prop(t, prop)
        row = box.row(align=True)
        row.operator('tala.apply_finish', text='Apply Finish').remove = False
        row.operator('tala.apply_finish', text='Lepas').remove = True
        box = layout.box(); box.label(text='Batch render', icon='RENDER_ANIMATION')
        box.template_list('TALA_UL_Items', '', t, 'items', t, 'item_index', rows=3)
        row = box.row(align=True)
        row.operator('tala.item_add', text='Objek', icon='ADD').kind = 'OBJECT'
        row.operator('tala.item_add', text='Koleksi', icon='ADD').kind = 'COLLECTION'
        row.operator('tala.item_remove', text='', icon='REMOVE')
        grid = box.grid_flow(columns=3, align=True)
        for p, label, _d in TALA_PRESET_ITEMS:
            grid.prop(t, 'use_' + p.lower(), toggle=True)
        row = box.row(align=True); row.prop(t, 'res_x'); row.prop(t, 'res_y')
        box.prop(t, 'samples')
        box.operator('tala.batch_render', icon='RENDER_STILL')


TALA_CLASSES = (TALA_Item, TALA_Settings, TALA_OT_Build, TALA_OT_Fit, TALA_OT_Preset, TALA_OT_ApplyFinish,
                TALA_OT_Remove, TALA_OT_ItemAdd, TALA_OT_ItemRemove, TALA_UL_Items, TALA_OT_BatchRender, TALA_PT_Main)


CLASSES = (NS_Settings, NS_OT_Center, NS_OT_Fit, NS_OT_Scale, NS_OT_Rotate,
           NS_OT_Adopt, NS_OT_Import, NS_OT_Activate, NS_OT_RenderBatch,
           NS_OT_SelectCamera, NS_OT_Overview, NS_OT_ResetLighting, NS_OT_LightingView,
           NS_OT_PreviewMode, NS_OT_QuickAngle, NS_OT_Navigate, NS_OT_LoadExample,
           NS_OT_ApplyFinish, NS_OT_AddBaseTexture, NS_OT_SetFinishTexture,
           NS_OT_RebuildFinishLibrary, NS_OT_SyncLighting, NS_OT_LockCamera,
           NS_OT_UnlockCamera, NS_OT_SaveLatar, NS_PT_Main)


def register():
    for cls in CLASSES + TALA_CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.ns_studio = PointerProperty(type=NS_Settings)
    bpy.types.Scene.tala = PointerProperty(type=TALA_Settings)
    subscribe_light_energy()
    if _load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post)
    for handlers, fn in ((bpy.app.handlers.load_post, _autopack_load_post),
                         (bpy.app.handlers.save_pre, _autopack_save_pre)):
        if fn not in handlers:
            handlers.append(fn)
    enable_autopack()


def unregister():
    bpy.msgbus.clear_by_owner(_msgbus_owner)
    if _load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post)
    for handlers, fn in ((bpy.app.handlers.load_post, _autopack_load_post),
                         (bpy.app.handlers.save_pre, _autopack_save_pre)):
        if fn in handlers:
            handlers.remove(fn)
    if hasattr(bpy.types.Scene, 'ns_studio'):
        del bpy.types.Scene.ns_studio
    if hasattr(bpy.types.Scene, 'tala'):
        del bpy.types.Scene.tala
    for cls in reversed(CLASSES + TALA_CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == '__main__':
    register()
