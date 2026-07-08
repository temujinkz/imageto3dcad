"""Generate the 3D mesh (mesh.glb / mesh.obj / mesh.stl) for a job.

Delegates reconstruction to the provider chain (cloud GPU first, local offline
silhouette engine last), then normalizes the result. The old ``.box()`` and
flat-extrusion fallbacks are gone: ``providers.generate`` always returns a real
3D shape.
"""

from __future__ import annotations

from pathlib import Path

from ..config import Settings
from . import providers
from .image_geometry import analyze_image_geometry
from .mesh_postprocess import process as postprocess_mesh


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

    # Still analyze the silhouette — it feeds the CAD summary + dimension estimate
    # shown in the UI (not used to build the mesh anymore).
    geometry = analyze_image_geometry(
        image_path=image_path,
        settings=settings,
        known_width_mm=known_width_mm,
        known_height_mm=known_height_mm,
        thickness_mm=thickness_value,
    )
    warnings = list(geometry.get("warnings", []))

    existing_extras = [str(p) for p in (extra_image_paths or []) if Path(p).exists()]

    recon_dir = output_dir / "reconstruction"
    generated = providers.generate(
        str(image_path), str(recon_dir), settings, extra_image_paths=existing_extras
    )

    if existing_extras and not (generated and generated.meta.get("multiview")):
        warnings.append(
            f"{len(existing_extras)} extra angle photo(s) were uploaded, but the active provider "
            "reconstructs from the single primary image; the others were not used. "
            "Set a WaveSpeed key to fuse multiple angles into one model."
        )

    if generated is None or not generated.mesh_path or not Path(generated.mesh_path).exists():
        return {
            "source": "none",
            "stl_path": None,
            "obj_path": None,
            "glb_path": None,
            "preview_model_path": None,
            "is_high_fidelity": False,
            "warnings": warnings + (generated.warnings if generated else ["3D generation produced no mesh."]),
            "geometry": geometry,
        }

    warnings += generated.warnings
    post = postprocess_mesh(generated.mesh_path, output_dir)
    warnings += post.get("warnings", [])

    return {
        "source": generated.source,
        "is_high_fidelity": generated.is_high_fidelity,
        "stl_path": post["stl_path"],
        "obj_path": post["obj_path"],
        "glb_path": post["glb_path"],
        "preview_model_path": post["glb_path"] or post["obj_path"] or post["stl_path"],
        "vertex_count": post["vertex_count"],
        "face_count": post["face_count"],
        "bbox": post["bbox"],
        "bbox_size": post["bbox_size"],
        "warnings": warnings,
        "geometry": geometry,
    }
