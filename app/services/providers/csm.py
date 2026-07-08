"""CSM.ai image-to-3D provider (key-gated; ported from the legacy code)."""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from ...config import Settings
from .base import GeneratedMesh, download_mesh_file


class CsmProvider:
    name = "csm"

    def available(self, settings: Settings) -> bool:
        return bool(settings.csm_api_key)

    def generate(self, image_path: str, output_dir: str, settings: Settings) -> GeneratedMesh | None:
        if not settings.csm_api_key:
            return None
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        headers = {"x-api-key": settings.csm_api_key}
        image = Path(image_path)
        files = [("file", (image.name, image.read_bytes(), "image/png"))]
        try:
            with httpx.Client(timeout=settings.reconstruction_timeout_seconds) as client:
                create = client.post(f"{settings.csm_api_base}/sessions", headers=headers, files=files)
                if create.status_code >= 400:
                    return GeneratedMesh(self.name, "", True, [f"CSM create failed (HTTP {create.status_code})."])
                session_id = create.json().get("session_id") or create.json().get("id")
                if not session_id:
                    return GeneratedMesh(self.name, "", True, ["CSM returned no session id."])
                url = _poll(client, headers, session_id, settings)
                if not url:
                    return GeneratedMesh(self.name, "", True, ["CSM session did not produce a model."])
                mesh_path = download_mesh_file(url, out)
                if mesh_path is None:
                    return GeneratedMesh(self.name, "", True, ["CSM model download failed."])
                return GeneratedMesh(self.name, str(mesh_path), True, meta={"session_id": session_id})
        except Exception as exc:
            return GeneratedMesh(self.name, "", True, [f"CSM error: {exc}"])


def _poll(client: httpx.Client, headers: dict, session_id: str, settings: Settings) -> str | None:
    deadline = time.time() + settings.reconstruction_timeout_seconds
    while time.time() < deadline:
        response = client.get(f"{settings.csm_api_base}/sessions/{session_id}", headers=headers)
        if response.status_code >= 400:
            return None
        payload = response.json()
        status = (payload.get("status") or "").lower()
        if status in {"complete", "completed", "ready"}:
            return payload.get("model_url") or payload.get("glb_url")
        if status in {"failed", "error"}:
            return None
        time.sleep(4)
    return None
