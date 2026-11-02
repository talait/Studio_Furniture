"""python -I ringkas_laporan.py <folder_laporan> [nama ...] : ringkasan laporan build."""
import json, sys, os, glob
folder = sys.argv[1]
names = sys.argv[2:] or [os.path.basename(f)[:-5] for f in sorted(glob.glob(os.path.join(folder, "*.json")))]
for n in names:
    L = json.load(open(os.path.join(folder, n + ".json"), encoding="utf-8"))
    aktif = [p for p in L["part"] if not p["arsip"]]
    bersih = [p for p in aktif if p["sesudah"]["nonmanifold"] == 0 and p["sesudah"]["islands"] == 1]
    print("=====", L["nama"], L["ukuran_cm"], "objek", L["jumlah_objek_mesh"], f"| aktif {len(aktif)}, manifold bersih {len(bersih)}")
    for p in L["part"]:
        s = p["sesudah"]
        flag = "" if (s["nonmanifold"] == 0 and s["islands"] == 1) else "  <--"
        ars = " [ARSIP]" if p["arsip"] else ""
        print(f'  {p["nama"]:44s} {p["grup"]:9s} {str(p["ukuran_mm"]):26s} f{s["faces"]:6d} nonman {s["nonmanifold"]:5d} bnd {s["boundary"]:5d} zero {s["zero_area"]:3d} isl {s["islands"]} {p.get("tjunc_split")}{flag}{ars}')
    for m in L["masalah"]:
        if m["jenis"] == "tembus":
            print("  TEMBUS:", m["a"], "<->", m["b"], m["bbox_mm"], m["vertex_a_di_dalam_b"], m["vertex_b_di_dalam_a"])
    for c in L["catatan"]:
        print("  catatan:", c)
