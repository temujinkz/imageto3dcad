"""CAD / STEP generation.

Priority output for this project. Two tracks, best-first, and never a box:
  Track 1 — Gemini VLM -> parametric primitives -> clean, editable STEP (ideal
            for AutoCAD). Requires GEMINI_API_KEY.
  Track 2 — reconstructed mesh -> tessellated STEP solid (faithful, faceted).
  Fallback — STL/OBJ only with step_generated=False and a clear reason.

A 2D DXF outline is always emitted as a bonus (legit flat drawing).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ..cad import build_step
from ..cad.gemini_cad import analyze_object
from ..config import Settings, get_settings
from .image_geometry import analyze_image_geometry


def generate_flat_part_cad(
    image_path,
    output_dir,
    known_width_mm=None,
    known_height_mm=None,
    thickness_mm=5,
    settings: Settings | None = None,
    mesh_path: str | None = None,
) -> dict:
    settings = settings or get_settings()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    geometry = analyze_image_geometry(
        image_path=image_path,
        settings=settings,
        known_width_mm=known_width_mm,
        known_height_mm=known_height_mm,
        thickness_mm=thickness_mm,
    )
    width_mm = float(geometry["estimated_dimensions_mm"]["width"])
    height_mm = float(geometry["estimated_dimensions_mm"]["height"])
    thickness_value = float(geometry["estimated_dimensions_mm"]["thickness"])
    warnings = list(geometry.get("warnings", []))

    # 2D outline drawing (always available, cheap, genuinely useful)
    dxf_path = output_dir / "cad.dxf"
    _write_dxf(dxf_path, width_mm, height_mm, _holes_in_mm(geometry, width_mm, height_mm))

    result: dict = {
        "step_path": None,
        "stl_path": None,
        "dxf_path": str(dxf_path),
        "step_generated": False,
        "step_quality": None,
        "step_method": None,
        "object_class": None,
        "warnings": warnings,
    }

    cad = _build_step(image_path, output_dir, mesh_path, settings)
    if cad:
        result.update({k: cad.get(k, result.get(k)) for k in
                       ("step_path", "stl_path", "step_generated", "step_quality", "step_method", "object_class")})
        result["warnings"] = warnings + cad.get("warnings", [])
    else:
        # No STEP could be produced — still hand back a solid mesh as cad.stl so
        # the CAD download is never empty, and say so honestly.
        fallback_stl = _copy_mesh_stl(output_dir, mesh_path)
        if fallback_stl:
            result["stl_path"] = fallback_stl
        result["warnings"] = warnings + [
            "Could not generate a STEP file (no Gemini key and mesh tessellation unavailable). "
            "Providing STL/OBJ mesh exports instead. Import those into your CAD tool."
        ]

    # Always leave a solid STL alongside the CAD outputs (parametric track already
    # writes one; tessellated/none tracks copy the reconstructed mesh).
    if not result.get("stl_path"):
        copied = _copy_mesh_stl(output_dir, mesh_path)
        if copied:
            result["stl_path"] = copied

    result["cad_summary"] = {
        "detected_outline": bool(geometry["detected_outline"]),
        "detected_holes": int(geometry["detected_holes"]),
        "estimated_dimensions_mm": {
            "width": round(width_mm, 2),
            "height": round(height_mm, 2),
            "thickness": round(thickness_value, 2),
        },
    }
    result["preview_model_path"] = result["step_path"] or result["stl_path"]
    return result


def _build_step(image_path, output_dir: Path, mesh_path: str | None, settings: Settings) -> dict | None:
    # Track 1: Gemini parametric primitives -> clean STEP
    if settings.enable_gemini_cad and settings.gemini_api_key:
        spec = analyze_object(image_path, settings)
        if spec:
            cad = build_step.build_from_primitives(spec, output_dir)
            if cad:
                return cad

    # Track 2: reconstructed mesh -> tessellated STEP solid
    source_mesh = _resolve_mesh_path(output_dir, mesh_path)
    if source_mesh:
        cad = build_step.mesh_to_step(source_mesh, output_dir)
        if cad:
            return cad
    return None


def _resolve_mesh_path(output_dir: Path, mesh_path: str | None) -> str | None:
    if mesh_path and Path(mesh_path).exists():
        return mesh_path
    for name in ("mesh.stl", "mesh.obj", "mesh.glb"):
        candidate = output_dir / name
        if candidate.exists():
            return str(candidate)
    return None


def _copy_mesh_stl(output_dir: Path, mesh_path: str | None) -> str | None:
    source = _resolve_mesh_path(output_dir, mesh_path)
    if not source or not source.endswith(".stl"):
        source = str(output_dir / "mesh.stl") if (output_dir / "mesh.stl").exists() else None
    if not source:
        return None
    destination = output_dir / "cad.stl"
    try:
        shutil.copyfile(source, destination)
        return str(destination)
    except Exception:
        return None


def _holes_in_mm(geometry: dict, width_mm: float, height_mm: float) -> list[dict]:
    bbox = geometry.get("bounding_box", {})
    bbox_width = max(float(bbox.get("width", 1.0)), 1.0)
    bbox_height = max(float(bbox.get("height", 1.0)), 1.0)
    holes: list[dict] = []
    for hole in geometry.get("holes", []):
        center_x_px, center_y_px = hole["center_px"]
        radius_px = float(hole["radius_px"])
        x = ((center_x_px - (bbox_width / 2)) / bbox_width) * width_mm
        y = (((bbox_height / 2) - center_y_px) / bbox_height) * height_mm
        diameter = max((radius_px * 2 / bbox_width) * width_mm, 1.0)
        holes.append({"x": round(x, 2), "y": round(y, 2), "diameter": round(diameter, 2)})
    return holes


def _write_dxf(path: Path, width_mm: float, height_mm: float, holes: list[dict]) -> None:
    left = -width_mm / 2
    right = width_mm / 2
    bottom = -height_mm / 2
    top = height_mm / 2
    rows = ["0", "SECTION", "2", "ENTITIES", "0", "LWPOLYLINE", "8", "0", "90", "4", "70", "1"]
    for x, y in [(left, bottom), (right, bottom), (right, top), (left, top)]:
        rows.extend(["10", f"{x:.6f}", "20", f"{y:.6f}"])
    for hole in holes:
        rows.extend(["0", "CIRCLE", "8", "0", "10", f"{hole['x']:.6f}", "20", f"{hole['y']:.6f}", "40", f"{(hole['diameter'] / 2):.6f}"])
    rows.extend(["0", "ENDSEC", "0", "EOF"])
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
