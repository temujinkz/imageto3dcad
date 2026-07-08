"""Tripo AI image-to-3D provider (https://platform.tripo3d.ai / API v2).

Automatic fallback when Meshy is unavailable or out of credits. Flow:
upload image -> create image_to_model task -> poll -> download GLB.
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from ...config import Settings
from .base import GeneratedMesh, download_mesh_file


class TripoProvider:
    name = "tripo-api"

    def available(self, settings: Settings) -> bool:
        return bool(settings.tripo_api_key)

    def generate(self, image_path: str, output_dir: str, settings: Settings) -> GeneratedMesh | None:
        if not settings.tripo_api_key:
            return None
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        headers = {"Authorization": f"Bearer {settings.tripo_api_key}"}
        base = settings.tripo_api_base.rstrip("/")

        try:
            with httpx.Client(timeout=settings.reconstruction_timeout_seconds) as client:
                image = Path(image_path)
                suffix = image.suffix.lower().lstrip(".") or "png"
                upload = client.post(
                    f"{base}/openapi/upload",
                    headers=headers,
                    files={"file": (image.name, image.read_bytes(), f"image/{suffix}")},
                )
                if upload.status_code >= 400:
                    return GeneratedMesh(self.name, "", True, [f"Tripo upload failed (HTTP {upload.status_code})."])
                image_token = (upload.json().get("data") or {}).get("image_token")
                if not image_token:
                    return GeneratedMesh(self.name, "", True, ["Tripo upload returned no image_token."])

                create = client.post(
                    f"{base}/openapi/task",
                    headers={**headers, "Content-Type": "application/json"},
                    json={
                        "type": "image_to_model",
                        "file": {"type": suffix, "file_token": image_token},
                    },
                )
                if create.status_code >= 400:
                    return GeneratedMesh(self.name, "", True, [f"Tripo task create failed (HTTP {create.status_code})."])
                task_id = (create.json().get("data") or {}).get("task_id")
                if not task_id:
                    return GeneratedMesh(self.name, "", True, ["Tripo returned no task_id."])

                url = _poll(client, headers, base, task_id, settings)
                if not url:
                    return GeneratedMesh(self.name, "", True, ["Tripo task did not produce a model."])

                mesh_path = download_mesh_file(url, out)
                if mesh_path is None:
                    return GeneratedMesh(self.name, "", True, ["Tripo model download failed."])
                return GeneratedMesh(self.name, str(mesh_path), True, meta={"task_id": task_id})
        except Exception as exc:
            return GeneratedMesh(self.name, "", True, [f"Tripo error: {exc}"])


def _poll(client: httpx.Client, headers: dict, base: str, task_id: str, settings: Settings) -> str | None:
    deadline = time.time() + settings.reconstruction_timeout_seconds
    while time.time() < deadline:
        response = client.get(f"{base}/openapi/task/{task_id}", headers=headers)
        if response.status_code >= 400:
            return None
        data = (response.json().get("data") or {})
        status = (data.get("status") or "").lower()
        if status in {"success", "completed"}:
            output = data.get("output", {}) or {}
            return output.get("pbr_model") or output.get("model") or output.get("base_model")
        if status in {"failed", "error", "cancelled", "banned", "expired"}:
            return None
        time.sleep(4)
    return None
