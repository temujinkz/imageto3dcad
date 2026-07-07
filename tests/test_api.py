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

    def test_job_flow(self) -> None:
        create = self.client.post(
            "/api/jobs",
            files={"image": ("sample.png", sample_image(), "image/png")},
            data={"mode": "both", "background_removal": "false"},
        )
        self.assertEqual(create.status_code, 202)
        job_id = create.json()["job_id"]

        payload = None
        for _ in range(100):
            status = self.client.get(f"/api/jobs/{job_id}")
            self.assertEqual(status.status_code, 200)
            payload = status.json()
            if payload["status"] in {"completed", "failed"}:
                break
            time.sleep(0.1)

        self.assertIsNotNone(payload)
        self.assertEqual(payload["status"], "completed", payload)
        self.assertIn("stl", payload["files"])
        self.assertIn("dxf", payload["files"])
        self.assertIn("obj", payload["files"])
        self.assertIsNotNone(payload["cad_summary"])

        file_response = self.client.get(f"/api/files/{job_id}/cad.dxf")
        self.assertEqual(file_response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
