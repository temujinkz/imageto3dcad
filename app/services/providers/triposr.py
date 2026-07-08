"""Local TripoSR provider — wraps the existing subprocess service.

Only active when PHOTO2CAD_TRIPOSR_RUN_PY points at an installed TripoSR
checkout (needs torch). Left available for users who set it up; not part of the
default path on a no-GPU Mac.
"""

from __future__ import annotations

from pathlib import Path

from ...config import Settings
from ..triposr_service import generate_mesh_from_image
from .base import GeneratedMesh


class TriposrProvider:
    name = "triposr"

    def available(self, settings: Settings) -> bool:
        return bool(settings.use_triposr and settings.triposr_run_py and Path(settings.triposr_run_py).expanduser().exists())

    def generate(self, image_path: str, output_dir: str, settings: Settings) -> GeneratedMesh | None:
        result = generate_mesh_from_image(image_path, str(Path(output_dir) / "triposr"), settings=settings)
        raw = result.get("glb_path") or result.get("obj_path") or result.get("stl_path")
        if not raw:
            return GeneratedMesh(self.name, "", True, result.get("warnings", ["TripoSR produced no mesh."]))
        return GeneratedMesh(self.name, raw, True, result.get("warnings", []))
