"""Ekstrak POLYLINE_PFACE (+ LINE) dari JSON dwgread R14 -> OBJ (satuan gambar) + ringkasan.
python -I credenza_extract.py out.json keluaran.obj
"""
import json
import math
import sys
from collections import Counter, defaultdict

src, out = sys.argv[1], sys.argv[2]
js = json.load(open(src, encoding="utf-8", errors="replace"))
objs = js["OBJECTS"]

blocks = {}
for o in objs:
    if o.get("object") == "BLOCK_HEADER":
        blocks[o["handle"][2]] = o.get("name")
print("BLOCK_HEADER:", blocks)
for o in objs:
    if o.get("entity") == "INSERT":
        print("INSERT:", {k: o.get(k) for k in ("handle", "ins_pt", "scale", "rotation", "block_header", "ownerhandle", "color", "layer")})
    if o.get("entity") == "LWPOLYLINE":
        print("LWPOLYLINE:", {k: o.get(k) for k in ("handle", "num_points", "ownerhandle", "flag")}, str(o.get("points"))[:300])

# Kumpulkan pface: iterasi berurutan; VERTEX_PFACE / VERTEX_PFACE_FACE mengikuti POLYLINE_PFACE sampai SEQEND
meshes = []  # dict(handle, owner, color, verts, faces)
cur = None
owner_cnt = Counter()
for o in objs:
    e = o.get("entity")
    if e == "POLYLINE_PFACE":
        own = o.get("ownerhandle")
        cur = {"handle": o["handle"][2], "owner": own[2] if isinstance(own, list) and len(own) > 2 else None,
               "color": json.dumps(o.get("color")), "verts": [], "faces": [], "numverts": o.get("numverts"), "numfaces": o.get("numfaces")}
        meshes.append(cur)
    elif e == "VERTEX_PFACE" and cur is not None:
        cur["verts"].append(tuple(o["point"]))
    elif e == "VERTEX_PFACE_FACE" and cur is not None:
        idx = [o.get(k, 0) for k in ("vertind[0]", "vertind[1]", "vertind[2]", "vertind[3]")]
        if "vertind" in o:
            idx = list(o["vertind"]) + [0] * (4 - len(o["vertind"]))
        idx = [(65536 - v) if v > 32767 else v for v in idx]
        cur["faces"].append(idx)
    elif e == "SEQEND":
        cur = None

print("pface meshes:", len(meshes))
if meshes:
    print("contoh keys VERTEX_PFACE_FACE:", [k for k in next(o for o in objs if o.get("entity") == "VERTEX_PFACE_FACE").keys()])
    print("contoh mesh:", {k: (v if k not in ("verts", "faces") else v[:4]) for k, v in meshes[0].items()})
print("owner count:", Counter(m["owner"] for m in meshes))
print("color count:", Counter(m["color"] for m in meshes).most_common(20))
vc = Counter(len(m["verts"]) for m in meshes)
print("verts per mesh:", vc.most_common(10))

# LINE
lines = [o for o in objs if o.get("entity") == "LINE"]
lo = [min(min(o["start"][i], o["end"][i]) for o in lines) for i in range(3)] if lines else None
hi = [max(max(o["start"][i], o["end"][i]) for o in lines) for i in range(3)] if lines else None
print("LINE count", len(lines), "bbox", lo, hi, "owners", Counter((o.get("ownerhandle") or [0, 0, None])[2] if len(o.get("ownerhandle") or []) > 2 else None for o in lines))
lens = Counter(round(math.dist(o["start"], o["end"]), 0) for o in lines)
print("LINE panjang umum:", lens.most_common(12))

# Tulis OBJ: satu objek per warna (gabungan), vertex global
meshes = [m for m in meshes if m["owner"] == 119]
for m in meshes:
    m["bad"] = {i + 1 for i, v in enumerate(m["verts"]) if not all(abs(c) < 1e6 for c in v)}
    m["verts"] = [v if all(abs(c) < 1e6 for c in v) else (0.0, 0.0, 0.0) for v in m["verts"]]
allv = [v for m in meshes for v in m["verts"]]
if allv:
    print("PFACE bbox", [min(v[i] for v in allv) for i in range(3)], [max(v[i] for v in allv) for i in range(3)])
with open(out, "w") as f:
    voff = 1
    bycol = defaultdict(list)
    for m in meshes:
        bycol[m["color"]].append(m)
    for ci, (col, ms) in enumerate(bycol.items()):
        f.write(f"o warna_{ci}\n# {col}\n")
        for m in ms:
            for v in m["verts"]:
                f.write("v %.4f %.4f %.4f\n" % v)
            for face in m["faces"]:
                ids = [abs(i) for i in face if i]
                if any(i in m["bad"] or all(abs(c) < 1e-6 for c in m["verts"][i - 1]) for i in ids if 0 < i <= len(m["verts"])):
                    continue
                ids = [voff + i - 1 for i in ids if 0 < i <= len(m["verts"])]
                if len(ids) >= 3 and len(set(ids)) == len(ids):
                    f.write("f " + " ".join(str(i) for i in ids) + "\n")
            voff += len(m["verts"])
print("OK", out)
