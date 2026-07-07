from __future__ import annotations

import io
import time
import unittest

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.main import app


def sample_image() -> bytes:
    image = Image.new("RGBA", (260, 180), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((40, 45, 220, 135), radius=18, fill=(40, 40, 40, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class BackendApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_frontend_demo_flow(self) -> None:
        upload = self.client.post(
            "/api/upload-image",
            files={"image": ("sample.png", sample_image(), "image/png")},
            data={"background_removal": "false"},
        )
        self.assertEqual(upload.status_code, 200)
        job_id = upload.json()["job_id"]

        uploaded_job = self.client.get(f"/api/jobs/{job_id}")
        self.assertEqual(uploaded_job.status_code, 200)
        self.assertEqual(uploaded_job.json()["job_id"], job_id)
        self.assertIsNotNone(uploaded_job.json()["masked_image_url"])

        mesh = self.client.post(f"/api/jobs/{job_id}/generate-mesh")
        self.assertEqual(mesh.status_code, 202)
        mesh_payload = self._wait_for_job(job_id)
        self.assertEqual(mesh_payload["status"], "completed", mesh_payload)
        self.assertIn("mesh_stl" if "mesh_stl" in mesh_payload["files"] else "stl", mesh_payload["files"])
        self.assertTrue(
            any(key in mesh_payload["files"] for key in ("obj", "glb", "mesh_stl", "stl"))
        )

        cad = self.client.post(f"/api/jobs/{job_id}/generate-cad")
        self.assertEqual(cad.status_code, 202)
        payload = self._wait_for_job(job_id)
        self.assertEqual(payload["status"], "completed", payload)
        self.assertIn("dxf", payload["files"])
        self.assertIn("stl", payload["files"])
        self.assertIsNotNone(payload["cad_summary"])
        self.assertTrue(payload["preview_model_url"] is None or payload["preview_model_url"].startswith("http"))

        file_response = self.client.get(f"/api/files/{job_id}/cad.dxf")
        self.assertEqual(file_response.status_code, 200)
        stl_response = self.client.get(f"/api/files/{job_id}/cad.stl")
        self.assertEqual(stl_response.status_code, 200)

    def test_legacy_combined_job_flow(self) -> None:
        create = self.client.post(
            "/api/jobs",
            files={"image": ("sample.png", sample_image(), "image/png")},
            data={"background_removal": "false"},
        )
        self.assertEqual(create.status_code, 202)
        payload = self._wait_for_job(create.json()["job_id"])
        self.assertEqual(payload["status"], "completed", payload)
        self.assertIn("dxf", payload["files"])
        self.assertTrue(any(key in payload["files"] for key in ("stl", "mesh_stl")))

    def _wait_for_job(self, job_id: str) -> dict:
        payload = None
        for _ in range(120):
            status = self.client.get(f"/api/jobs/{job_id}")
            self.assertEqual(status.status_code, 200)
            payload = status.json()
            if payload["status"] in {"completed", "failed"}:
                break
            time.sleep(0.1)
        self.assertIsNotNone(payload)
        return payload


if __name__ == "__main__":
    unittest.main()
