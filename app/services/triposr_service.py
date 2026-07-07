from __future__ import annotations

import importlib
import shlex
import subprocess
from pathlib import Path

from ..config import Settings, get_settings


def generate_mesh_from_image(
    image_path: str,
    output_dir: str,
    settings: Settings | None = None,
) -> dict:
    settings = settings or get_settings()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not settings.use_triposr:
        return {"source": "disabled", "warnings": ["TripoSR disabled via USE_TRIPOSR=false."]}

    if not settings.triposr_run_py:
        return {"source": "unconfigured", "warnings": ["TripoSR run.py path is not configured."]}

    run_path = Path(settings.triposr_run_py).expanduser()
    if not run_path.exists():
        return {"source": "missing", "warnings": ["Configured TripoSR run.py was not found."]}

    command = [
        settings.triposr_python_bin,
        str(run_path),
        image_path,
        "--output-dir",
        str(output_path),
        "--no-remove-bg",
    ]
    if settings.triposr_extra_args:
        command.extend(shlex.split(settings.triposr_extra_args))

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=settings.triposr_timeout_seconds,
            check=False,
        )
    except Exception as exc:
        return {"source": "error", "warnings": [f"TripoSR launch failed: {exc}"]}

    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "Unknown TripoSR error."
        return {"source": "error", "warnings": [f"TripoSR failed: {message}"]}

    candidates = list(output_path.rglob("*"))
    mesh_source = next(
        (path for path in candidates if path.suffix.lower() in {".obj", ".glb", ".stl", ".ply"}),
        None,
    )
    if mesh_source is None:
        return {"source": "error", "warnings": ["TripoSR finished without producing a mesh file."]}

    result = {"source": "triposr", "warnings": []}
    try:
        trimesh = importlib.import_module("trimesh")
        mesh = trimesh.load_mesh(mesh_source, force="mesh")
        stl_path = output_path / "mesh.stl"
        obj_path = output_path / "mesh.obj"
        glb_path = output_path / "mesh.glb"
        mesh.export(stl_path)
        mesh.export(obj_path)
        mesh.export(glb_path)
        result.update(
            {
                "stl_path": str(stl_path),
                "obj_path": str(obj_path),
                "glb_path": str(glb_path),
            }
        )
        return result
    except Exception:
        suffix = mesh_source.suffix.lower()
        if suffix == ".stl":
            result["stl_path"] = str(mesh_source)
        elif suffix == ".obj":
            result["obj_path"] = str(mesh_source)
        elif suffix == ".glb":
            result["glb_path"] = str(mesh_source)
        result["warnings"].append("Trimesh not available, returning raw TripoSR output only.")
        return result
