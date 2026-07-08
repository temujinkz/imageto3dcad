"""Quality gates, debug artifacts, and the per-job pipeline log.

Turns silent bad output into loud, honest signals: a box-shaped mesh, a
degenerate bounding box, or a missing mesh are all surfaced (or fail the job)
instead of being reported as success.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


def has_any_mesh(mesh_result: dict) -> bool:
    return any(mesh_result.get(k) for k in ("glb_path", "obj_path", "stl_path"))


def is_degenerate(mesh_result: dict) -> bool:
    size = mesh_result.get("bbox_size")
    if not size:
        return False
    return min(abs(float(d)) for d in size) < 1e-4


def evaluate_mesh(mesh_result: dict) -> list[str]:
    """Non-fatal warnings about mesh quality."""
    warnings: list[str] = []
    source = mesh_result.get("source")
    faces = mesh_result.get("face_count")
    if faces is not None and faces <= 12 and source != "mock":
        warnings.append(
            "The generated mesh has 12 or fewer faces — that is box-shaped and almost certainly "
            "means reconstruction failed. Check your provider/API key."
        )
    size = mesh_result.get("bbox_size")
    if size and source not in {"mock"}:
        dims = sorted(abs(float(d)) for d in size)
        if dims[0] > 1e-4 and dims[0] / dims[-1] < 0.02:
            warnings.append("The generated mesh is nearly flat (one dimension ~0) — depth may be missing.")
    return warnings


def save_debug_images(job_dir: Path) -> None:
    """Ensure the debug image set exists (original + masked/normalized)."""
    masked = job_dir / "masked.png"
    normalized = job_dir / "normalized.png"
    # masked.png is already the cropped + padded + centered canvas; expose it
    # under the documented debug name too.
    if masked.exists() and not normalized.exists():
        try:
            shutil.copyfile(masked, normalized)
        except Exception:
            pass


def write_pipeline_log(job_dir: Path, payload: dict) -> None:
    logs = job_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    try:
        (logs / "pipeline.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    except Exception:
        pass
