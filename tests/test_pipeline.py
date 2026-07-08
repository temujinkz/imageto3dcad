"""Tests for the rebuilt image-to-3D pipeline.

Focus: the actual live frontend path (upload -> process), the guarantee that
output is a real 3D shape and never a box, that a STEP is produced (or a clear
reason given), and that a total reconstruction failure fails the job loudly
instead of returning a box as "success". No real network calls are made — the
local silhouette engine runs for the happy path, and provider failure is
simulated with a monkeypatch.
"""

from __future__ import annotations

import io
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

import app.main as main_module
from app.config import get_settings
from app.services.mesh_postprocess import process as postprocess
from app.services.providers.mock import MockProvider
from app.services.providers.silhouette import SilhouetteProvider


def bottle_png() -> bytes:
    """A symmetric perfume-bottle silhouette on a transparent background."""
    h, w = 400, 260
    alpha = np.zeros((h, w), dtype=np.uint8)
    cx = w // 2
    for (y0, y1, hw) in [(60, 300, 90), (40, 60, 34), (20, 40, 26), (4, 20, 40)]:
        for y in range(y0, y1):
            alpha[y, cx - hw: cx + hw] = 255
    rgba = np.dstack([np.full((h, w), 200, np.uint8)] * 3 + [alpha])
    buffer = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buffer, format="PNG")
    return buffer.getvalue()


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(main_module.app)
        # Keep tests offline + fast + deterministic: force the local tessellated
        # STEP path instead of a live Gemini call (which needs a key + network).
        patcher = mock.patch("app.services.cad_service.analyze_object", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _run(self, background_removal: str = "false") -> dict:
        upload = self.client.post(
            "/api/upload",
            files={"image": ("bottle.png", bottle_png(), "image/png")},
            data={"background_removal": background_removal},
        )
        self.assertEqual(upload.status_code, 200)
        job_id = upload.json()["job_id"]
        self.assertTrue(job_id)
        response = self.client.post(
            "/api/process",
            json={"job_id": job_id, "generate_mesh": True, "generate_cad": True, "generate_freecad": True},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        payload["_job_id"] = job_id
        return payload

    def test_output_is_real_3d_not_a_box(self) -> None:
        d = self._run()
        self.assertEqual(d["status"], "completed")
        # a box is exactly 12 faces; a real reconstruction has far more
        self.assertGreater(d["mesh_face_count"], 12, "output collapsed to a box")
        self.assertIn("glb", d["files"])
        self.assertIn("obj", d["files"])
        self.assertIn("stl", d["files"])
        self.assertTrue(d["preview_model_url"].endswith(".glb"))

    def test_step_is_generated(self) -> None:
        d = self._run()
        self.assertTrue(d["step_generated"], d.get("warnings"))
        self.assertIn("step", d["files"])
        self.assertIn(d["step_quality"], {"parametric_approximate", "tessellated"})

    def test_debug_artifacts_and_log_written(self) -> None:
        d = self._run()
        job_dir = Path(main_module.store.get(d["_job_id"])["job_dir"])
        self.assertTrue((job_dir / "input.png").exists())
        self.assertTrue((job_dir / "masked.png").exists())
        self.assertTrue((job_dir / "normalized.png").exists())
        self.assertTrue((job_dir / "logs" / "pipeline.json").exists())

    def test_local_provider_is_honest_about_fidelity(self) -> None:
        d = self._run()
        self.assertEqual(d["mesh_source"], "silhouette")
        self.assertFalse(d["mesh_is_high_fidelity"])

    def test_total_failure_fails_job_not_silent_box(self) -> None:
        """If every provider fails, the job must fail — not return a box."""
        no_mesh = {
            "source": "none", "stl_path": None, "obj_path": None, "glb_path": None,
            "preview_model_path": None, "is_high_fidelity": False,
            "warnings": ["all providers failed"], "geometry": {},
        }
        with mock.patch("app.routers.upload.generate_mesh_assets", return_value=no_mesh):
            upload = self.client.post(
                "/api/upload",
                files={"image": ("bottle.png", bottle_png(), "image/png")},
                data={"background_removal": "false"},
            )
            job_id = upload.json()["job_id"]
            response = self.client.post(
                "/api/process",
                json={"job_id": job_id, "generate_mesh": True, "generate_cad": False, "generate_freecad": False},
            )
        self.assertEqual(response.status_code, 500)  # loud failure, not silent success

    def test_silhouette_revolve_produces_watertight_solid(self) -> None:
        settings = get_settings()
        with io.BytesIO(bottle_png()) as buf:
            img = Image.open(buf).convert("RGBA")
        tmp = Path(main_module.store.settings.storage_root) / "_unit_bottle.png"
        img.save(tmp)
        out = tmp.parent / "_unit_out"
        gm = SilhouetteProvider().generate(str(tmp), str(out), settings)
        self.assertTrue(gm.mesh_path and Path(gm.mesh_path).exists())
        self.assertEqual(gm.meta.get("mode"), "revolve")
        post = postprocess(gm.mesh_path, out)
        self.assertGreater(post["face_count"], 100)
        self.assertTrue(post["watertight"])

    def test_mock_provider_is_a_bottle_not_a_cube(self) -> None:
        settings = get_settings()
        out = Path(main_module.store.settings.storage_root) / "_unit_mock"
        gm = MockProvider().generate("ignored.png", str(out), settings)
        post = postprocess(gm.mesh_path, out)
        self.assertGreater(post["face_count"], 100)  # a cube would be 12


if __name__ == "__main__":
    unittest.main()
