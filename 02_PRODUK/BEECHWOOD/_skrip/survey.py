"""Ringkas isi JSON dwgread: tipe entity, layer, block, 3DSOLID."""
import json
import sys
from collections import Counter, defaultdict

path = sys.argv[1]
with open(path, encoding="utf-8", errors="replace") as f:
    js = json.load(f)
objs = js["OBJECTS"]
hdr = js.get("HEADER", {})
print("INSUNITS", hdr.get("INSUNITS"), "LUNITS", hdr.get("LUNITS"), "EXTMIN", hdr.get("EXTMIN"), "EXTMAX", hdr.get("EXTMAX"))

# handle -> nama layer / block
layers = {}
blocks = {}
for o in objs:
    if o.get("object") == "LAYER":
        layers[o["handle"][2]] = o.get("name")
    if o.get("object") == "BLOCK_HEADER":
        blocks[o["handle"][2]] = (o.get("name"), o.get("num_owned"))
print("LAYERS:", sorted(layers.values(), key=str))
print("BLOCKS:", [b for b in blocks.values() if b[0] not in ("*Model_Space", "*Paper_Space")][:40], "...total", len(blocks))

ents = [o for o in objs if "entity" in o]
cnt = Counter(o["entity"] for o in ents)
print("ENTITY COUNT:", dict(cnt.most_common()))

# per entity: owner block (ownerhandle) & layer
by_owner = defaultdict(Counter)
for o in ents:
    own = o.get("ownerhandle", [0, 0, 0])
    oh = own[2] if isinstance(own, list) else None
    by_owner[blocks.get(oh, ("?" + str(oh),))[0]][o["entity"]] += 1
for k, v in by_owner.items():
    print("  owner", k, dict(v))

sol = [o for o in ents if o["entity"] in ("3DSOLID", "BODY", "REGION")]
lay_cnt = Counter(layers.get(o.get("layer", [0, 0, 0])[2], "?") for o in sol)
print("SOLID layers:", dict(lay_cnt))
col_cnt = Counter(json.dumps(o.get("color")) for o in sol)
print("SOLID colors:", dict(col_cnt))
inserts = [o for o in ents if o["entity"] == "INSERT"]
for o in inserts[:30]:
    bh = o.get("block_header", [0, 0, 0])[2]
    print("  INSERT", blocks.get(bh), "at", o.get("ins_pt"), "scale", o.get("scale"), "rot", o.get("rotation"), "layer", layers.get(o.get("layer", [0, 0, 0])[2]))
texts = [o for o in ents if o["entity"] in ("TEXT", "MTEXT")]
for o in texts[:40]:
    print("  TEXT:", (o.get("text_value") or o.get("text") or "")[:80])
dims = [o for o in ents if o["entity"].startswith("DIMENSION")]
for o in dims[:40]:
    print("  DIM:", o.get("user_text"), round(o.get("act_measurement", 0) or 0, 1))
