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
    """Prepare FreeCAD-friendly STEP and OBJ exports from generated assets."""
    output_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    freecad_step = output_dir / "freecad.step"
    freecad_obj = output_dir / "freecad.obj"

    step_source = Path(cad_step_path) if cad_step_path and Path(cad_step_path).exists() else None
    if step_source:
        freecad_step.write_bytes(step_source.read_bytes())
    elif mesh_stl_path and Path(mesh_stl_path).exists():
        converted = _mesh_to_step(Path(mesh_stl_path), freecad_step)
        if not converted:
            warnings.append("STEP export unavailable; FreeCAD can still import OBJ/STL.")
    else:
        warnings.append("No mesh available for FreeCAD STEP export.")

    obj_source = Path(mesh_obj_path) if mesh_obj_path and Path(mesh_obj_path).exists() else None
    if obj_source:
        freecad_obj.write_bytes(obj_source.read_bytes())
    elif mesh_stl_path and Path(mesh_stl_path).exists():
        converted = _stl_to_obj(Path(mesh_stl_path), freecad_obj)
        if not converted:
            warnings.append("OBJ export for FreeCAD failed.")
    else:
        warnings.append("No mesh available for FreeCAD OBJ export.")

    result: dict = {"warnings": warnings}
    if freecad_step.exists():
        result["step_path"] = str(freecad_step)
    if freecad_obj.exists():
        result["obj_path"] = str(freecad_obj)
    return result


def _mesh_to_step(mesh_path: Path, step_path: Path) -> bool:
    try:
        cadquery = importlib.import_module("cadquery")
        trimesh = importlib.import_module("trimesh")
        mesh = trimesh.load_mesh(mesh_path, force="mesh")
        # CadQuery cannot import arbitrary meshes directly in all builds;
        # use bounding box solid as a FreeCAD-openable fallback STEP.
        bounds = mesh.bounds
        size = bounds[1] - bounds[0]
        center = (bounds[0] + bounds[1]) / 2
        solid = (
            cadquery.Workplane("XY")
            .box(float(size[0]), float(size[1]), float(max(size[2], 1.0)))
            .translate((float(center[0]), float(center[1]), float(center[2])))
        )
        cadquery.exporters.export(solid, str(step_path))
        return step_path.exists()
    except Exception:
        return False


def _stl_to_obj(stl_path: Path, obj_path: Path) -> bool:
    try:
        trimesh = importlib.import_module("trimesh")
        mesh = trimesh.load_mesh(stl_path, force="mesh")
        mesh.export(obj_path)
        return obj_path.exists()
    except Exception:
        return False
