"""Luma AI image-to-3D provider (key-gated; ported from the legacy code)."""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from ...config import Settings
from .base import GeneratedMesh, download_mesh_file


class LumaProvider:
    name = "luma"

    def available(self, settings: Settings) -> bool:
        return bool(settings.luma_api_key)

    def generate(self, image_path: str, output_dir: str, settings: Settings) -> GeneratedMesh | None:
        if not settings.luma_api_key:
            return None
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        headers = {"Authorization": f"Bearer {settings.luma_api_key}"}
        image = Path(image_path)
        files = [("images", (image.name, image.read_bytes(), "image/png"))]
        try:
            with httpx.Client(timeout=settings.reconstruction_timeout_seconds) as client:
                create = client.post(f"{settings.luma_api_base}/capture", headers=headers, files=files)
                if create.status_code >= 400:
                    return GeneratedMesh(self.name, "", True, [f"Luma create failed (HTTP {create.status_code})."])
                payload = create.json()
                capture_id = payload.get("id") or payload.get("capture_id")
                if not capture_id:
                    return GeneratedMesh(self.name, "", True, ["Luma returned no capture id."])
                url = _poll(client, headers, capture_id, settings)
                if not url:
                    return GeneratedMesh(self.name, "", True, ["Luma capture did not produce a model."])
                mesh_path = download_mesh_file(url, out)
                if mesh_path is None:
                    return GeneratedMesh(self.name, "", True, ["Luma model download failed."])
                return GeneratedMesh(self.name, str(mesh_path), True, meta={"capture_id": capture_id})
        except Exception as exc:
            return GeneratedMesh(self.name, "", True, [f"Luma error: {exc}"])


def _poll(client: httpx.Client, headers: dict, capture_id: str, settings: Settings) -> str | None:
    deadline = time.time() + settings.reconstruction_timeout_seconds
    while time.time() < deadline:
        response = client.get(f"{settings.luma_api_base}/capture/{capture_id}", headers=headers)
        if response.status_code >= 400:
            return None
        payload = response.json()
        status = (payload.get("status") or "").lower()
        if status in {"completed", "finished", "ready"}:
            return (payload.get("model_urls", {}) or {}).get("glb") or payload.get("download_url")
        if status in {"failed", "error"}:
            return None
        time.sleep(4)
    return None
