from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np
from PIL import Image

from ..config import Settings
from .image_geometry import analyze_image_geometry
from .triposr_service import generate_mesh_from_image


def generate_mesh_assets(
    image_path: str | Path,
    output_dir: str | Path,
    settings: Settings,
    known_width_mm: float | None = None,
    known_height_mm: float | None = None,
    thickness_mm: float | None = None,
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

    tripo = generate_mesh_from_image(str(image_path), str(output_dir / "triposr"), settings=settings)
    if any(tripo.get(key) for key in ("stl_path", "obj_path", "glb_path")):
        return {
            "source": tripo.get("source", "triposr"),
            "stl_path": tripo.get("stl_path"),
            "obj_path": tripo.get("obj_path"),
            "glb_path": tripo.get("glb_path"),
            "preview_model_path": tripo.get("glb_path") or tripo.get("obj_path") or tripo.get("stl_path"),
            "warnings": warnings + tripo.get("warnings", []),
            "geometry": geometry,
        }

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
