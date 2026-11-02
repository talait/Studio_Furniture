# Material prosedural Beechwood (warna baru 31-10-2026, ikut foto referensi buffet):
#   ROLE | RATTAN  -> anyaman rotan polos (over/under) jarak helai 8 mm, celah gelap, bump
#   ROLE | WOOD_A  -> serat oak/beech natural terang searah V (UV meter, grain = V)
#   ROLE | WOOD_B  -> sama, lebih terang & kontras rendah (interior)
# Semua bekerja di UV "UV meter" (1 unit = 1 m) dari konstruksi_util.uv_meter.
# Pakai:
#   blender -b "<file>.blend" --python material_buffet.py -- [--simpan]
import bpy, sys

PITCH_ROTAN = 0.008      # m, lebar satu helai/sel anyaman


def baru(mat):
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (900, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (600, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    uv = nt.nodes.new("ShaderNodeUVMap"); uv.location = (-1400, 0); uv.uv_map = "UV meter"
    return nt, bsdf, uv


def math(nt, op, a=None, b=None, loc=(0, 0), v1=None):
    n = nt.nodes.new("ShaderNodeMath"); n.operation = op; n.location = loc
    for i, x in enumerate((a, b)):
        if x is None:
            continue
        if isinstance(x, (int, float)):
            n.inputs[i].default_value = x
        else:
            nt.links.new(x, n.inputs[i])
    return n.outputs[0]


def ramp(nt, fac, stops, loc):
    r = nt.nodes.new("ShaderNodeValToRGB"); r.location = loc
    el = r.color_ramp.elements
    while len(el) > len(stops):
        el.remove(el[-1])
    while len(el) < len(stops):
        el.new(0.5)
    for e, (p, c) in zip(el, stops):
        e.position = p; e.color = (*c, 1)
    nt.links.new(fac, r.inputs["Fac"])
    return r.outputs["Color"]


def bump(nt, h, bsdf, strength, dist, loc):
    b = nt.nodes.new("ShaderNodeBump"); b.location = loc
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = dist
    nt.links.new(h, b.inputs["Height"])
    nt.links.new(b.outputs["Normal"], bsdf.inputs["Normal"])


def rotan(mat):
    nt, bsdf, uv = baru(mat)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); sep.location = (-1200, 0)
    nt.links.new(uv.outputs["UV"], sep.inputs[0])
    u = math(nt, "MULTIPLY", sep.outputs[0], 1 / PITCH_ROTAN, (-1000, 100))
    v = math(nt, "MULTIPLY", sep.outputs[1], 1 / PITCH_ROTAN, (-1000, -100))
    # helai vertikal & horizontal: profil setengah sinus melintang helai
    hu = math(nt, "SINE", math(nt, "MULTIPLY", math(nt, "FRACT", u, loc=(-800, 200)), 3.14159265, (-650, 200)), loc=(-500, 200))
    hv = math(nt, "SINE", math(nt, "MULTIPLY", math(nt, "FRACT", v, loc=(-800, -200)), 3.14159265, (-650, -200)), loc=(-500, -200))
    # paritas sel -> helai mana yang di atas (anyaman polos over/under)
    par = math(nt, "FLOORED_MODULO", math(nt, "ADD", math(nt, "FLOOR", u, loc=(-800, 0)), math(nt, "FLOOR", v, loc=(-800, -60)), (-650, 0)), 2.0, (-500, 0))
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "FLOAT"; mix.location = (-300, 0)
    nt.links.new(par, mix.inputs["Factor"])
    nt.links.new(hu, mix.inputs["A"]); nt.links.new(hv, mix.inputs["B"])
    h = mix.outputs["Result"]
    # variasi warna per helai + serat halus memanjang
    noi = nt.nodes.new("ShaderNodeTexNoise"); noi.location = (-300, -300)
    noi.inputs["Scale"].default_value = 180.0; noi.inputs["Detail"].default_value = 4.0
    nt.links.new(uv.outputs["UV"], noi.inputs["Vector"])
    warna = ramp(nt, h, [(0.0, (0.05, 0.03, 0.015)), (0.22, (0.22, 0.14, 0.06)), (0.55, (0.47, 0.33, 0.15)), (1.0, (0.64, 0.48, 0.24))], (0, 100))
    var = nt.nodes.new("ShaderNodeMix"); var.data_type = "RGBA"; var.blend_type = "MULTIPLY"; var.location = (300, 100)
    var.inputs["Factor"].default_value = 0.25
    nt.links.new(warna, var.inputs["A"]); nt.links.new(noi.outputs["Color"], var.inputs["B"])
    nt.links.new(var.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.55
    bump(nt, h, bsdf, 0.6, 0.0015, (300, -250))


def kayu(mat, terang, gelap, kontras_bump):
    nt, bsdf, uv = baru(mat)
    mp = nt.nodes.new("ShaderNodeMapping"); mp.location = (-1200, 0)
    mp.inputs["Scale"].default_value = (1.0, 0.08, 1.0)          # serat memanjang sepanjang V (arah grain)
    nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])
    wv = nt.nodes.new("ShaderNodeTexWave"); wv.location = (-900, 100)
    wv.wave_type = "BANDS"; wv.bands_direction = "X"
    wv.inputs["Scale"].default_value = 70.0
    wv.inputs["Distortion"].default_value = 6.0
    wv.inputs["Detail"].default_value = 3.0
    wv.inputs["Detail Scale"].default_value = 1.5
    nt.links.new(mp.outputs["Vector"], wv.inputs["Vector"])
    noi = nt.nodes.new("ShaderNodeTexNoise"); noi.location = (-900, -200)
    noi.inputs["Scale"].default_value = 25.0; noi.inputs["Detail"].default_value = 6.0
    nt.links.new(mp.outputs["Vector"], noi.inputs["Vector"])
    f = math(nt, "MULTIPLY", wv.outputs["Fac"], noi.outputs["Fac"], (-600, 0))
    f = math(nt, "POWER", f, 0.7, (-450, 0))
    warna = ramp(nt, f, [(0.0, terang), (0.55, tuple((a + b) / 2 for a, b in zip(terang, gelap))), (1.0, gelap)], (-250, 100))
    nt.links.new(warna, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.48
    bump(nt, f, bsdf, kontras_bump, 0.0004, (300, -250))


rotan(bpy.data.materials["ROLE | RATTAN"])
kayu(bpy.data.materials["ROLE | WOOD_A"], (0.60, 0.50, 0.35), (0.42, 0.31, 0.19), 0.15)
kayu(bpy.data.materials["ROLE | WOOD_B"], (0.64, 0.55, 0.41), (0.52, 0.42, 0.29), 0.08)
for m in ("ROLE | RATTAN", "ROLE | WOOD_A", "ROLE | WOOD_B"):
    bpy.data.materials[m]["catatan"] = "prosedural material_buffet.py 2026-10-31 (UV meter)"
print("[material] RATTAN anyaman 8 mm, WOOD_A/WOOD_B serat oak terang")
if "--simpan" in sys.argv:
    bpy.ops.wm.save_mainfile(compress=True)
    print("[material] Disimpan")
