"""Build STEP files from either a parametric primitive spec (Track 1, clean CAD)
or a reconstructed mesh (Track 2, faithful tessellated solid).

Neither path ever emits a bounding-box cube: Track 1 rebuilds the actual
primitive stack, Track 2 sews the real mesh into a STEP solid, and if both fail
the caller falls back to STL/OBJ only with ``step_generated: False``.
"""

from __future__ import annotations

from pathlib import Path


# --------------------------------------------------------------------------- #
# Track 1: parametric primitives -> clean STEP                                #
# --------------------------------------------------------------------------- #
def build_from_primitives(spec: dict, output_dir: str | Path) -> dict | None:
    try:
        import cadquery as cq
    except Exception:
        return None

    output_dir = Path(output_dir)
    solids = []
    for prim in spec.get("primitives", []):
        solid = _primitive(cq, prim)
        if solid is not None:
            solids.append(solid)
    if not solids:
        return None

    result = solids[0]
    for solid in solids[1:]:
        try:
            result = result.union(solid)
        except Exception:
            try:
                result = result.add(solid)  # keep as compound if boolean union fails
            except Exception:
                continue

    step_path = output_dir / "cad.step"
    stl_path = output_dir / "cad.stl"

    # STEP is the critical output. Try the merged solid, then a plain compound of
    # all primitives (OCC boolean unions can fail nondeterministically).
    if not _export(cq, result, step_path):
        compound = _compound(cq, solids)
        if compound is None or not _export(cq, compound, step_path):
            return None
        result = compound

    _export(cq, result, stl_path)  # STL is best-effort; never blocks the STEP
    return {
        "step_path": str(step_path),
        "stl_path": str(stl_path) if stl_path.exists() else None,
        "step_generated": True,
        "step_quality": "parametric_approximate",
        "step_method": "gemini_vlm_primitive_fit",
        "object_class": spec.get("object_class"),
        "warnings": [],
    }


def _export(cq, model, path: Path) -> bool:
    try:
        cq.exporters.export(model, str(path))
        return path.exists()
    except Exception:
        return False


def _compound(cq, solids):
    try:
        shapes = []
        for wp in solids:
            shapes.extend(wp.vals())
        return cq.Compound.makeCompound(shapes)
    except Exception:
        return None


def _primitive(cq, prim: dict):
    kind = prim.get("type")
    z0 = float(prim.get("offset_z_mm", 0.0))
    try:
        if kind == "cylinder":
            r = float(prim["diameter_mm"]) / 2.0
            h = float(prim["height_mm"])
            return cq.Workplane("XY").workplane(offset=z0).circle(r).extrude(h)
        if kind == "frustum":
            r1 = float(prim["bottom_diameter_mm"]) / 2.0
            r2 = float(prim["top_diameter_mm"]) / 2.0
            h = float(prim["height_mm"])
            if abs(r1 - r2) < 1e-3:
                return cq.Workplane("XY").workplane(offset=z0).circle(r1).extrude(h)
            return (
                cq.Workplane("XY").workplane(offset=z0).circle(r1)
                .workplane(offset=h).circle(r2)
                .loft(combine=True)
            )
        if kind == "box":
            w = float(prim["width_mm"])
            d = float(prim["depth_mm"])
            h = float(prim["height_mm"])
            return cq.Workplane("XY").workplane(offset=z0).box(w, d, h, centered=(True, True, False))
        if kind == "sphere":
            r = float(prim["diameter_mm"]) / 2.0
            return cq.Workplane("XY").workplane(offset=z0 + r).sphere(r)
    except Exception:
        return None
    return None


# --------------------------------------------------------------------------- #
# Track 2: reconstructed mesh -> tessellated STEP solid                       #
# --------------------------------------------------------------------------- #
def mesh_to_step(mesh_path: str | Path, output_dir: str | Path, max_faces: int = 6000, hard_cap: int = 90000) -> dict | None:
    try:
        import trimesh
        from OCP.BRepBuilderAPI import (
            BRepBuilderAPI_MakeFace,
            BRepBuilderAPI_MakePolygon,
            BRepBuilderAPI_MakeSolid,
            BRepBuilderAPI_Sewing,
        )
        from OCP.gp import gp_Pnt
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
        from OCP.TopoDS import TopoDS
    except Exception:
        return None

    try:
        mesh = trimesh.load(str(mesh_path), force="mesh")
    except Exception:
        return None
    if mesh is None or len(mesh.faces) == 0:
        return None
    if len(mesh.faces) > max_faces:
        try:
            mesh = mesh.simplify_quadric_decimation(face_count=max_faces)
        except Exception:
            pass  # no decimation backend installed — proceed unless truly huge
    if len(mesh.faces) > hard_cap:
        return None  # too heavy to tessellate in-request; caller uses STL only

    verts = mesh.vertices
    try:
        sewing = BRepBuilderAPI_Sewing(1e-3)
        for tri in mesh.faces:
            a, b, c = (gp_Pnt(*[float(v) for v in verts[i]]) for i in tri)
            poly = BRepBuilderAPI_MakePolygon(a, b, c, True)
            if not poly.IsDone():
                continue
            face = BRepBuilderAPI_MakeFace(poly.Wire())
            if face.IsDone():
                sewing.Add(face.Face())
        sewing.Perform()
        shape = sewing.SewedShape()
        try:
            shape = BRepBuilderAPI_MakeSolid(TopoDS.Shell_s(shape)).Solid()
        except Exception:
            pass  # keep the open shell if a closed solid can't be made

        step_path = Path(output_dir) / "cad.step"
        writer = STEPControl_Writer()
        writer.Transfer(shape, STEPControl_AsIs)
        if writer.Write(str(step_path)) != IFSelect_RetDone or not step_path.exists():
            return None
    except Exception:
        return None

    return {
        "step_path": str(step_path),
        "stl_path": None,
        "step_generated": True,
        "step_quality": "tessellated",
        "step_method": "mesh_to_brep",
        "object_class": None,
        "warnings": ["STEP is a tessellated (faceted) solid from the reconstructed mesh, not a parametric CAD model."],
    }
