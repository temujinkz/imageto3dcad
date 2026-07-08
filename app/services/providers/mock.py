"""Mock provider — a clearly-labeled synthetic bottle for testing the pipeline.

Ignores the image content on purpose. It exists only to prove the
generate -> post-process -> export -> preview flow end to end, and it is a
bottle (body + shoulder + neck + cap) rather than a cube so a "box" output can
never be mistaken for success.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh

from ...config import Settings
from .base import GeneratedMesh

# (radius, height) profile of a generic perfume bottle in normalized units
_BOTTLE_PROFILE = [
    [0.00, 0.00], [0.42, 0.00], [0.45, 0.05], [0.45, 0.55],
    [0.40, 0.68], [0.20, 0.74], [0.16, 0.80], [0.16, 0.90],
    [0.22, 0.92], [0.22, 1.02], [0.00, 1.02],
]


class MockProvider:
    name = "mock"

    def available(self, settings: Settings) -> bool:
        return True

    def generate(self, image_path: str, output_dir: str, settings: Settings) -> GeneratedMesh | None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        mesh = trimesh.creation.revolve(np.array(_BOTTLE_PROFILE), sections=72)
        mesh.fix_normals()
        raw = out / "raw_mesh.glb"
        mesh.export(raw)
        return GeneratedMesh(
            source=self.name,
            mesh_path=str(raw),
            is_high_fidelity=False,
            warnings=[
                "This is MOCK geometry (a synthetic bottle), NOT reconstructed from the image. "
                "Set IMAGE_TO_3D_PROVIDER=auto and add a MESHY_API_KEY for real reconstruction."
            ],
            meta={"mock": True},
        )
