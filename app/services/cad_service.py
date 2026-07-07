from __future__ import annotations

import importlib
import shutil
from pathlib import Path

from ..config import Settings, get_settings
from .image_geometry import analyze_image_geometry
from .mesh_service import generate_mesh_assets


def generate_flat_part_cad(
    image_path,
    output_dir,
    known_width_mm=None,
    known_height_mm=None,
    thickness_mm=5,
    settings: Settings | None = None,
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

    if not geometry["detected_outline"]:
        width_mm = float(known_width_mm or settings.default_width_mm)
        height_mm = float(known_height_mm or settings.default_height_mm)
        warnings.append(
            "Contour detection failed, using a simple rectangular fallback plate with two holes."
        )

    dxf_path = output_dir / "cad.dxf"
    _write_dxf(dxf_path, width_mm, height_mm, _holes_in_mm(geometry, width_mm, height_mm))

    result = {
        "step_path": None,
        "stl_path": None,
        "dxf_path": str(dxf_path),
        "warnings": warnings,
    }

    try:
        cadquery = importlib.import_module("cadquery")
        model = _build_model(
            cadquery=cadquery,
            width_mm=width_mm,
            height_mm=height_mm,
            thickness_mm=thickness_value,
            holes=_holes_in_mm(geometry, width_mm, height_mm),
        )
        step_path = output_dir / "cad.step"
        stl_path = output_dir / "cad.stl"
        cadquery.exporters.export(model, str(step_path))
        cadquery.exporters.export(model, str(stl_path))
        result["step_path"] = str(step_path)
        result["stl_path"] = str(stl_path)
    except Exception as exc:
        warnings.append(f"CadQuery export failed, using STL mesh fallback only: {exc}")
        mesh = generate_mesh_assets(
            image_path=image_path,
            output_dir=output_dir,
            settings=settings,
            known_width_mm=known_width_mm or width_mm,
            known_height_mm=known_height_mm or height_mm,
            thickness_mm=thickness_value,
        )
        if mesh.get("stl_path"):
            fallback_stl = output_dir / "cad.stl"
            shutil.copyfile(mesh["stl_path"], fallback_stl)
            result["stl_path"] = str(fallback_stl)

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


def _build_model(cadquery, width_mm: float, height_mm: float, thickness_mm: float, holes: list[dict]):
    model = cadquery.Workplane("XY").box(width_mm, height_mm, thickness_mm)
    if holes:
        points = [(hole["x"], hole["y"]) for hole in holes]
        diameter = max(min(hole["diameter"] for hole in holes), 1.0)
        model = model.faces(">Z").workplane().pushPoints(points).hole(diameter)
    return model


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
    if not holes and not geometry.get("detected_outline"):
        holes = [
            {"x": round(-width_mm * 0.25, 2), "y": 0.0, "diameter": round(width_mm * 0.12, 2)},
            {"x": round(width_mm * 0.25, 2), "y": 0.0, "diameter": round(width_mm * 0.12, 2)},
        ]
    return holes


def _write_dxf(path: Path, width_mm: float, height_mm: float, holes: list[dict]) -> None:
    left = -width_mm / 2
    right = width_mm / 2
    bottom = -height_mm / 2
    top = height_mm / 2
    rows = [
        "0",
        "SECTION",
        "2",
        "ENTITIES",
        "0",
        "LWPOLYLINE",
        "8",
        "0",
        "90",
        "4",
        "70",
        "1",
    ]
    for x, y in [(left, bottom), (right, bottom), (right, top), (left, top)]:
        rows.extend(["10", f"{x:.6f}", "20", f"{y:.6f}"])
    for hole in holes:
        rows.extend(
            [
                "0",
                "CIRCLE",
                "8",
                "0",
                "10",
                f"{hole['x']:.6f}",
                "20",
                f"{hole['y']:.6f}",
                "40",
                f"{(hole['diameter'] / 2):.6f}",
            ]
        )
    rows.extend(["0", "ENDSEC", "0", "EOF"])
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
