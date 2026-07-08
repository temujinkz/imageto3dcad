"""Normalize any provider's raw mesh into the canonical mesh.glb/obj/stl trio.

Handles the failure modes called out in the brief: multi-geometry scenes (never
export just the first tiny piece), off-center / mis-scaled meshes, flipped
normals, tiny disconnected junk components, and holes. GLB is exported from the
original scene when possible so cloud textures/materials survive; OBJ/STL are
exported from the cleaned, concatenated solid.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh

_TARGET_SIZE = 100.0  # longest bbox edge, in mesh units, after normalization
_MAX_FACES = 200_000


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

    final_bounds = mesh.bounds
    return {
        "glb_path": str(glb_path),
        "obj_path": str(obj_path),
        "stl_path": str(stl_path),
        "vertex_count": int(len(mesh.vertices)),
        "face_count": int(len(mesh.faces)),
        "bbox": [final_bounds[0].tolist(), final_bounds[1].tolist()],
        "bbox_size": (final_bounds[1] - final_bounds[0]).tolist(),
        "watertight": bool(mesh.is_watertight),
        "warnings": warnings,
    }


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
