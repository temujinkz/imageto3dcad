"""Prepare FreeCAD-friendly exports from generated assets.

Reuses the real STEP produced by ``cad_service`` (Track 1/2). It no longer
fabricates a bounding-box cube when no STEP exists — that was a source of the
"everything is a box" bug. When there is no real STEP, it exports OBJ (which
FreeCAD imports fine) and says so.
"""

from __future__ import annotations

import importlib
from pathlib import Path


def prepare_freecad_exports(
    *,
    mesh_stl_path: str | None,
    mesh_obj_path: str | None,
    cad_step_path: str | None,
    output_dir: Path,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    freecad_step = output_dir / "freecad.step"
    freecad_obj = output_dir / "freecad.obj"

    step_source = Path(cad_step_path) if cad_step_path and Path(cad_step_path).exists() else None
    if step_source:
        freecad_step.write_bytes(step_source.read_bytes())
    else:
        warnings.append("No STEP available for FreeCAD; import the OBJ/STL mesh instead.")

    obj_source = Path(mesh_obj_path) if mesh_obj_path and Path(mesh_obj_path).exists() else None
    if obj_source:
        freecad_obj.write_bytes(obj_source.read_bytes())
    elif mesh_stl_path and Path(mesh_stl_path).exists():
        if not _stl_to_obj(Path(mesh_stl_path), freecad_obj):
            warnings.append("OBJ export for FreeCAD failed.")
    else:
        warnings.append("No mesh available for FreeCAD OBJ export.")

    result: dict = {"warnings": warnings}
    if freecad_step.exists():
        result["step_path"] = str(freecad_step)
    if freecad_obj.exists():
        result["obj_path"] = str(freecad_obj)
    return result


def _stl_to_obj(stl_path: Path, obj_path: Path) -> bool:
    try:
        trimesh = importlib.import_module("trimesh")
        mesh = trimesh.load_mesh(stl_path, force="mesh")
        mesh.export(obj_path)
        return obj_path.exists()
    except Exception:
        return False
