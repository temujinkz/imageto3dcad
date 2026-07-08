from __future__ import annotations

import importlib
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

from ..config import Settings
from .image_geometry import analyze_image_geometry
from .reconstruction_api import reconstruct_from_images


def generate_mesh_assets(
    image_path: str | Path,
    output_dir: str | Path,
    settings: Settings,
    known_width_mm: float | None = None,
    known_height_mm: float | None = None,
    thickness_mm: float | None = None,
    extra_image_paths: list[str | Path] | None = None,
) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    thickness_value = float(thickness_mm or settings.default_thickness_mm)
    geometry = analyze_image_geometry(
        image_path=image_path,
        settings=settings,
        known_width_mm=known_width_mm,
        known_height_mm=known_height_mm,
        thickness_mm=thickness_value,
    )
    warnings = list(geometry.get("warnings", []))

    image_paths = [Path(image_path)]
    if extra_image_paths:
        image_paths.extend(Path(path) for path in extra_image_paths if Path(path).exists())

    tripo = reconstruct_from_images(image_paths, output_dir / "reconstruction", settings)
    if any(tripo.get(key) for key in ("stl_path", "obj_path", "glb_path")):
        # Reconstruction writes into output_dir/reconstruction/, but the file
        # endpoint and job serializer serve mesh.* from the job root, so
        # promote the produced meshes up to the root under their canonical names.
        promoted = {
            "stl_path": _promote_to_root(tripo.get("stl_path"), output_dir, "mesh.stl"),
            "obj_path": _promote_to_root(tripo.get("obj_path"), output_dir, "mesh.obj"),
            "glb_path": _promote_to_root(tripo.get("glb_path"), output_dir, "mesh.glb"),
        }
        return {
            "source": tripo.get("source", "triposr"),
            "stl_path": promoted["stl_path"],
            "obj_path": promoted["obj_path"],
            "glb_path": promoted["glb_path"],
            "preview_model_path": promoted["glb_path"] or promoted["obj_path"] or promoted["stl_path"],
            "warnings": warnings + tripo.get("warnings", []),
            "geometry": geometry,
        }

    cadquery_fallback = _generate_cadquery_fallback_mesh(
        output_dir=output_dir,
        width_mm=float(geometry["estimated_dimensions_mm"]["width"]),
        height_mm=float(geometry["estimated_dimensions_mm"]["height"]),
        thickness_mm=thickness_value,
        holes=geometry.get("holes", []),
        bbox=geometry.get("bounding_box", {}),
    )
    if cadquery_fallback is not None:
        cadquery_fallback["warnings"] = (
            warnings
            + tripo.get("warnings", [])
            + ["TripoSR failed, using simple CadQuery-generated fallback mesh."]
            + cadquery_fallback.get("warnings", [])
        )
        cadquery_fallback["geometry"] = geometry
        return cadquery_fallback

    fallback = _generate_fallback_mesh(
        image_path=Path(image_path),
        output_dir=output_dir,
        width_mm=float(geometry["estimated_dimensions_mm"]["width"]),
        height_mm=float(geometry["estimated_dimensions_mm"]["height"]),
        thickness_mm=thickness_value,
    )
    fallback["warnings"] = warnings + tripo.get("warnings", []) + fallback.get("warnings", [])
    fallback["geometry"] = geometry
    return fallback


def _promote_to_root(src_path: str | None, output_dir: Path, dest_name: str) -> str | None:
    """Copies a reconstruction output up to the job root under a canonical
    name, so the file endpoint (which serves job_dir/<name>) can find it.
    Returns the new path, or None if there was nothing to copy."""
    if not src_path:
        return None
    src = Path(src_path)
    if not src.exists():
        return None
    dest = output_dir / dest_name
    if src.resolve() == dest.resolve():
        return str(dest)
    shutil.copyfile(src, dest)
    return str(dest)


def _generate_cadquery_fallback_mesh(
    output_dir: Path,
    width_mm: float,
    height_mm: float,
    thickness_mm: float,
    holes: list[dict],
    bbox: dict,
) -> dict | None:
    try:
        cadquery = importlib.import_module("cadquery")
    except Exception:
        return None

    stl_path = output_dir / "mesh.stl"
    model = cadquery.Workplane("XY").box(width_mm, height_mm, thickness_mm)
    points, diameter = _hole_points_in_mm(holes, bbox, width_mm, height_mm)
    if points:
        model = model.faces(">Z").workplane().pushPoints(points).hole(diameter)

    try:
        cadquery.exporters.export(model, str(stl_path))
    except Exception:
        return None

    result = {
        "source": "cadquery-fallback",
        "stl_path": str(stl_path),
        "obj_path": None,
        "glb_path": None,
        "preview_model_path": str(stl_path),
        "warnings": [],
    }
    try:
        trimesh = importlib.import_module("trimesh")
        mesh = trimesh.load_mesh(stl_path, force="mesh")
        obj_path = output_dir / "mesh.obj"
        glb_path = output_dir / "mesh.glb"
        mesh.export(obj_path)
        mesh.export(glb_path)
        result["obj_path"] = str(obj_path)
        result["glb_path"] = str(glb_path)
        result["preview_model_path"] = str(glb_path)
    except Exception:
        result["warnings"].append("Trimesh unavailable, preview falls back to STL only.")
    return result


def _generate_fallback_mesh(
    image_path: Path,
    output_dir: Path,
    width_mm: float,
    height_mm: float,
    thickness_mm: float,
) -> dict:
    mask = _load_binary_mask(image_path)
    image = Image.fromarray(np.where(mask, 255, 0).astype(np.uint8))
    image.thumbnail((96, 96))
    small_mask = np.array(image) > 0
    vertices, faces = _voxel_mesh(
        small_mask,
        max_dimension_mm=max(width_mm, height_mm, 1.0),
        thickness_mm=thickness_mm,
    )
    stl_path = output_dir / "mesh.stl"
    obj_path = output_dir / "mesh.obj"
    _write_stl(stl_path, vertices, faces)
    _write_obj(obj_path, vertices, faces)
    result = {
        "source": "fallback",
        "stl_path": str(stl_path),
        "obj_path": str(obj_path),
        "glb_path": None,
        "preview_model_path": str(obj_path),
        "warnings": ["Using contour-based fallback mesh extrusion."],
    }
    try:
        trimesh = importlib.import_module("trimesh")
        glb_path = output_dir / "mesh.glb"
        trimesh.Trimesh(vertices=vertices, faces=faces, process=False).export(glb_path)
        result["glb_path"] = str(glb_path)
        result["preview_model_path"] = str(glb_path)
    except Exception:
        pass
    return result


def _load_binary_mask(image_path: Path) -> np.ndarray:
    image = Image.open(image_path).convert("RGBA")
    array = np.array(image)
    alpha = array[:, :, 3]
    if alpha.max() > 8:
        return alpha > 16
    return np.mean(array[:, :, :3], axis=2) < 245


def _hole_points_in_mm(
    holes: list[dict],
    bbox: dict,
    width_mm: float,
    height_mm: float,
) -> tuple[list[tuple[float, float]], float]:
    bbox_width = max(float(bbox.get("width", 1.0)), 1.0)
    bbox_height = max(float(bbox.get("height", 1.0)), 1.0)
    points: list[tuple[float, float]] = []
    diameters: list[float] = []
    for hole in holes:
        center_x_px, center_y_px = hole["center_px"]
        radius_px = float(hole["radius_px"])
        x = ((center_x_px - (bbox_width / 2)) / bbox_width) * width_mm
        y = (((bbox_height / 2) - center_y_px) / bbox_height) * height_mm
        points.append((round(x, 2), round(y, 2)))
        diameters.append(max((radius_px * 2 / bbox_width) * width_mm, 1.0))
    return points, min(diameters) if diameters else 0.0


def _voxel_mesh(mask: np.ndarray, max_dimension_mm: float, thickness_mm: float):
    ys, xs = np.where(mask)
    if not len(xs):
        raise ValueError("Image processing failed: no foreground object found.")

    depth_voxels = max(1, int(round(thickness_mm / max(max_dimension_mm / max(mask.shape), 0.1))))
    voxel_size = max_dimension_mm / max(mask.shape)
    x_center = mask.shape[1] / 2
    y_center = mask.shape[0] / 2
    filled = np.repeat(mask[:, :, None], depth_voxels, axis=2)

    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    vertex_index: dict[tuple[float, float, float], int] = {}

    def index_for(coord: tuple[float, float, float]) -> int:
        cached = vertex_index.get(coord)
        if cached is not None:
            return cached
        vertex_index[coord] = len(vertices)
        vertices.append(coord)
        return vertex_index[coord]

    quads = [
        ((0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)),
        ((1, 0, 0), (1, 0, 1), (1, 1, 1), (1, 1, 0)),
        ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)),
        ((0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)),
        ((0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)),
        ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)),
    ]
    directions = [(-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 1, 0), (0, 0, -1), (0, 0, 1)]

    for y, x, z in np.argwhere(filled):
        for direction, quad in zip(directions, quads):
            ny, nx, nz = y + direction[1], x + direction[0], z + direction[2]
            if (
                0 <= ny < filled.shape[0]
                and 0 <= nx < filled.shape[1]
                and 0 <= nz < filled.shape[2]
                and filled[ny, nx, nz]
            ):
                continue
            quad_indices: list[int] = []
            for dx, dy, dz in quad:
                quad_indices.append(
                    index_for(
                        (
                            ((x + dx) - x_center) * voxel_size,
                            (y_center - (y + dy)) * voxel_size,
                            (z + dz) * voxel_size,
                        )
                    )
                )
            faces.append((quad_indices[0], quad_indices[1], quad_indices[2]))
            faces.append((quad_indices[0], quad_indices[2], quad_indices[3]))

    return np.array(vertices, dtype=float), np.array(faces, dtype=int)


def _write_obj(path: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for x, y, z in vertices:
            handle.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
        for a, b, c in faces:
            handle.write(f"f {a + 1} {b + 1} {c + 1}\n")


def _write_stl(path: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    lines = ["solid photo2cad"]
    for face in faces:
        tri = vertices[face]
        normal = np.cross(tri[1] - tri[0], tri[2] - tri[0])
        length = np.linalg.norm(normal)
        normal = normal / length if length else np.array([0.0, 0.0, 0.0], dtype=float)
        lines.append(f"  facet normal {normal[0]:.6f} {normal[1]:.6f} {normal[2]:.6f}")
        lines.append("    outer loop")
        for vertex in tri:
            lines.append(f"      vertex {vertex[0]:.6f} {vertex[1]:.6f} {vertex[2]:.6f}")
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append("endsolid photo2cad")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
