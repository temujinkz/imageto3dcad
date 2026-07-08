"""Normalize any provider's raw mesh into the canonical mesh.glb/obj/stl trio.

Handles the failure modes called out in the brief: multi-geometry scenes (never
export just the first tiny piece), off-center / mis-scaled meshes, flipped
normals, tiny disconnected junk components, and holes. GLB is exported from the
original scene when possible so cloud textures/materials survive; OBJ/STL are
exported from the cleaned, concatenated solid.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import trimesh

_TARGET_SIZE = 100.0  # longest bbox edge, in mesh units, after normalization
_MAX_FACES = 200_000
# Target vertex budget for the fast, low-poly proxy shown while the full-res
# textured mesh downloads in the background. ~25k verts -> ~50k faces, ~1 MB.
_PROXY_TARGET_VERTS = int(os.getenv("MESH_PREVIEW_VERTS", "25000"))


def process(raw_mesh_path: str | Path, output_dir: str | Path) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    loaded = trimesh.load(str(raw_mesh_path), process=False)
    scene = loaded if isinstance(loaded, trimesh.Scene) else None
    mesh = _as_single_mesh(loaded)
    if mesh is None or mesh.faces.shape[0] == 0:
        raise ValueError("Loaded mesh has no faces.")

    mesh = _clean(mesh, warnings)

    # centering + uniform scale transform (applied identically to mesh + scene)
    bounds = mesh.bounds
    center = bounds.mean(axis=0)
    extent = float((bounds[1] - bounds[0]).max())
    scale = _TARGET_SIZE / extent if extent > 1e-9 else 1.0
    transform = np.eye(4)
    transform[:3, :3] *= scale
    transform[:3, 3] = -center * scale
    mesh.apply_transform(transform)

    stl_path = output_dir / "mesh.stl"
    obj_path = output_dir / "mesh.obj"
    glb_path = output_dir / "mesh.glb"
    mesh.export(stl_path)
    mesh.export(obj_path)

    # Prefer exporting the transformed original scene to GLB (keeps materials);
    # fall back to the cleaned single mesh if that fails.
    glb_exported = False
    if scene is not None and len(scene.geometry) > 0:
        try:
            scene_copy = scene.copy()
            scene_copy.apply_transform(transform)
            scene_copy.export(glb_path)
            glb_exported = True
        except Exception:
            glb_exported = False
    if not glb_exported:
        mesh.export(glb_path)

    # Low-poly, vertex-colored proxy for an instant preview. It carries the same
    # colors (sampled from the texture) so the object looks right immediately,
    # then the full textured GLB above swaps in once it finishes downloading.
    proxy_path = output_dir / "mesh_preview.glb"
    proxy_glb_path = _build_proxy(mesh, proxy_path, _PROXY_TARGET_VERTS)

    final_bounds = mesh.bounds
    return {
        "glb_path": str(glb_path),
        "proxy_glb_path": str(proxy_glb_path) if proxy_glb_path else None,
        "obj_path": str(obj_path),
        "stl_path": str(stl_path),
        "vertex_count": int(len(mesh.vertices)),
        "face_count": int(len(mesh.faces)),
        "bbox": [final_bounds[0].tolist(), final_bounds[1].tolist()],
        "bbox_size": (final_bounds[1] - final_bounds[0]).tolist(),
        "watertight": bool(mesh.is_watertight),
        "warnings": warnings,
    }


def _sample_vertex_colors(mesh: trimesh.Trimesh) -> np.ndarray | None:
    """Per-vertex RGBA for ``mesh``: reads existing vertex colors, otherwise
    samples the material's texture at each vertex's UV coordinate."""
    visual = getattr(mesh, "visual", None)
    if visual is None:
        return None
    try:
        if isinstance(visual, trimesh.visual.ColorVisuals):
            colors = visual.vertex_colors
        else:
            colors = visual.to_color().vertex_colors
    except Exception:
        return None
    colors = np.asarray(colors)
    if colors.ndim != 2 or colors.shape[0] != len(mesh.vertices):
        return None
    return colors


def _build_proxy(mesh: trimesh.Trimesh, out_path: Path, target_verts: int) -> Path | None:
    """Vertex-clustering decimation (Rossignac-style): collapse vertices onto a
    grid sized so the surface yields ~``target_verts`` clusters, averaging
    position and color per cell. Dependency-free (numpy only) so it works where
    quadric-decimation backends fail, and fast enough to add ~30 ms.
    """
    try:
        if len(mesh.faces) <= target_verts * 2:
            # Already light enough — reuse the full mesh as its own proxy.
            mesh.export(out_path)
            return out_path

        colors = _sample_vertex_colors(mesh)
        vertices = np.asarray(mesh.vertices, dtype=np.float64)
        faces = np.asarray(mesh.faces)
        origin = vertices.min(axis=0)
        size = np.maximum(vertices.max(axis=0) - origin, 1e-6)

        # Cell edge from surface area keeps resolution even for thin shells,
        # where a volume-based estimate would collapse the mesh too far.
        area = float(mesh.area) if mesh.area > 0 else float(np.prod(size))
        cell = (area / max(target_verts, 1)) ** 0.5
        dims = np.maximum(np.ceil(size / max(cell, 1e-6)).astype(int), 1)
        step = size / dims

        ijk = np.clip(((vertices - origin) / step).astype(int), 0, dims - 1)
        keys = (ijk[:, 0] * dims[1] + ijk[:, 1]) * dims[2] + ijk[:, 2]
        _, inv = np.unique(keys, return_inverse=True)
        counts = np.bincount(inv)

        new_vertices = np.zeros((counts.shape[0], 3))
        np.add.at(new_vertices, inv, vertices)
        new_vertices /= counts[:, None]

        new_colors = None
        if colors is not None:
            acc = np.zeros((counts.shape[0], colors.shape[1]))
            np.add.at(acc, inv, colors.astype(np.float64))
            new_colors = (acc / counts[:, None]).astype(np.uint8)

        new_faces = inv[faces]
        keep = (
            (new_faces[:, 0] != new_faces[:, 1])
            & (new_faces[:, 1] != new_faces[:, 2])
            & (new_faces[:, 0] != new_faces[:, 2])
        )
        new_faces = new_faces[keep]
        if new_faces.shape[0] == 0:
            return None

        proxy = trimesh.Trimesh(
            vertices=new_vertices,
            faces=new_faces,
            vertex_colors=new_colors,
            process=False,
        )
        proxy.export(out_path)
        return out_path
    except Exception:
        return None


def _as_single_mesh(loaded) -> trimesh.Trimesh | None:
    if isinstance(loaded, trimesh.Trimesh):
        return loaded
    if isinstance(loaded, trimesh.Scene):
        meshes = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not meshes:
            return None
        return trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
    return None


def _clean(mesh: trimesh.Trimesh, warnings: list[str]) -> trimesh.Trimesh:
    mesh.remove_infinite_values()
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.update_faces(mesh.unique_faces())
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()

    mesh = _drop_tiny_components(mesh, warnings)

    try:
        mesh.fill_holes()
    except Exception:
        pass
    mesh.fix_normals()

    if len(mesh.faces) > _MAX_FACES:
        try:
            mesh = mesh.simplify_quadric_decimation(face_count=_MAX_FACES)
            warnings.append(f"Mesh decimated to ~{_MAX_FACES} faces for a lighter download.")
        except Exception:
            pass  # decimation backend not installed; keep full-res mesh
    return mesh


def _drop_tiny_components(mesh: trimesh.Trimesh, warnings: list[str]) -> trimesh.Trimesh:
    try:
        parts = mesh.split(only_watertight=False)
    except Exception:
        return mesh
    if len(parts) <= 1:
        return mesh
    biggest = max(len(p.faces) for p in parts)
    kept = [p for p in parts if len(p.faces) >= max(biggest * 0.02, 8)]
    if kept and len(kept) < len(parts):
        warnings.append(f"Removed {len(parts) - len(kept)} tiny disconnected mesh fragment(s).")
    return trimesh.util.concatenate(kept) if kept else mesh
