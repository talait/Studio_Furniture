import bmesh
import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree


def fix_tjunctions(bm, tol):
    """Sambungan-T: vertex lain yang terletak di atas edge batas -> edge dipotong di titik itu."""
    verts = list(bm.verts)
    kd = KDTree(len(verts))
    for i, v in enumerate(verts):
        kd.insert(v.co, i)
    kd.balance()
    n_split = 0
    stack = [e for e in bm.edges if e.is_boundary]
    guard = 0
    while stack and guard < 200000:
        guard += 1
        e = stack.pop()
        if not e.is_valid:
            continue
        a, b = e.verts
        ab = b.co - a.co
        L = ab.length
        if L < 2 * tol:
            continue
        best = None
        for co, idx, dist in kd.find_range((a.co + b.co) / 2, L / 2 + tol):
            v = verts[idx]
            if v is a or v is b or not v.is_valid:
                continue
            t = (v.co - a.co).dot(ab) / (L * L)
            if t <= tol / L or t >= 1 - tol / L:
                continue
            if ((v.co - a.co) - ab * t).length < tol:
                if best is None or abs(t - 0.5) < abs(best[0] - 0.5):
                    best = (t, v)
        if best is None:
            continue
        t, v = best
        ne, nv = bmesh.utils.edge_split(e, a, t)
        nv.co = v.co.copy()
        n_split += 1
        stack.append(e)
        stack.append(ne)
    if n_split:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=tol * 0.5)
    return n_split


def vertex_islands(bm):
    seen, islands = set(), []
    for v in bm.verts:
        if v in seen:
            continue
        isl, stack = [], [v]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            isl.append(cur)
            for e in cur.link_edges:
                stack.append(e.other_vert(cur))
        islands.append(isl)
    return islands


def remove_duplicate_faces(bm):
    seen, dup = set(), []
    for f in bm.faces:
        key = frozenset(v.index for v in f.verts)
        if key in seen:
            dup.append(f)
        else:
            seen.add(key)
    if dup:
        bmesh.ops.delete(bm, geom=dup, context="FACES_ONLY")
    return len(dup)


def drop_loose(bm):
    loose_v = [v for v in bm.verts if not v.link_edges]
    bmesh.ops.delete(bm, geom=loose_v, context="VERTS")
    loose_e = [e for e in bm.edges if not e.link_faces]
    bmesh.ops.delete(bm, geom=loose_e, context="EDGES")


def clean(o, weld, tjunc_tol, max_hole=0.1, junk_m=0.003):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    v0, f0 = len(bm.verts), len(bm.faces)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=weld)
    bmesh.ops.dissolve_degenerate(bm, dist=weld, edges=bm.edges)
    drop_loose(bm)
    n_split = 0
    for _ in range(4):
        k = fix_tjunctions(bm, tjunc_tol)
        n_split += k
        bmesh.ops.dissolve_degenerate(bm, dist=weld, edges=bm.edges)
        if k == 0:
            break
    bm.verts.index_update()
    n_dup = remove_duplicate_faces(bm)
    drop_loose(bm)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # tutup lubang kecil sisa tessellasi (loop batas dengan keliling < max_hole)
    n_fill = 0
    if max_hole > 0:
        bnd = [e for e in bm.edges if e.is_boundary]
        seen, small = set(), []
        for e in bnd:
            if e in seen:
                continue
            loop, stack = [], [e]
            while stack:
                cur = stack.pop()
                if cur in seen:
                    continue
                seen.add(cur)
                loop.append(cur)
                for v in cur.verts:
                    for e2 in v.link_edges:
                        if e2.is_boundary and e2 not in seen:
                            stack.append(e2)
            if sum(x.calc_length() for x in loop) < max_hole:
                small.extend(loop)
        if small:
            res = bmesh.ops.holes_fill(bm, edges=small, sides=0)
            n_fill = len(res.get("faces", []))
            if n_fill:
                bmesh.ops.triangulate(bm, faces=res["faces"])
                bmesh.ops.dissolve_degenerate(bm, dist=weld * 5, edges=bm.edges)
                bm.verts.index_update()
                remove_duplicate_faces(bm)
                drop_loose(bm)
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # buang pulau sampah (bbox diagonal < 3 mm) jika bukan pulau satu-satunya
    n_junk = 0
    islands = vertex_islands(bm) if junk_m > 0 else []
    if len(islands) > 1:
        junk = []
        for isl in islands:
            lo = Vector([min(v.co[i] for v in isl) for i in range(3)])
            hi = Vector([max(v.co[i] for v in isl) for i in range(3)])
            if (hi - lo).length < junk_m:
                junk.extend(isl)
        if junk and len(junk) < len(bm.verts):
            bmesh.ops.delete(bm, geom=junk, context="VERTS")
            n_junk = len(junk)
    bmesh.ops.dissolve_limit(bm, angle_limit=0.001, verts=bm.verts, edges=bm.edges, delimit={"NORMAL"})
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()
    return v0, f0, (n_split, n_dup, n_fill, n_junk)


def vertices_inside(a, b, margin):
    """Jumlah vertex objek a yang berada di dalam mesh tertutup b (lebih dalam dari margin)."""
    bvh = BVHTree.FromObject(b, bpy.context.evaluated_depsgraph_get())
    n = 0
    for v in a.data.vertices:
        co = a.matrix_world @ v.co
        hit = bvh.find_nearest(co)
        if hit is None:
            continue
        loc, nor, idx, dist = hit
        if dist > margin and nor.dot(co - loc) < 0:
            n += 1
    return n


def periksa(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    nonman = sum(1 for e in bm.edges if not e.is_manifold)
    boundary = sum(1 for e in bm.edges if e.is_boundary)
    zero = sum(1 for f in bm.faces if f.calc_area() < 1e-10)
    # shell count via islands
    seen, islands = set(), 0
    for v in bm.verts:
        if v in seen:
            continue
        islands += 1
        stack = [v]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            for e in cur.link_edges:
                stack.append(e.other_vert(cur))
    bm.free()
    return {"nonmanifold": nonman, "boundary": boundary, "zero_area": zero, "islands": islands,
            "verts": len(o.data.vertices), "faces": len(o.data.polygons)}


