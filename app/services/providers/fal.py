"""fal.ai hosted image-to-3D provider (default model: Hunyuan3D-2).

Optional, highest-fidelity cloud path. Runs SOTA open models (Hunyuan3D-2 /
TRELLIS / TripoSR) on fal's GPUs via the queue REST API — no local GPU, no SDK
dependency (uses httpx + a data-URI image input).
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from ...config import Settings
from .base import GeneratedMesh, download_mesh_file, resized_data_uri

_QUEUE_BASE = "https://queue.fal.run"


class FalProvider:
    name = "fal-hunyuan3d"

    def available(self, settings: Settings) -> bool:
        return bool(settings.fal_api_key)

    def generate(self, image_path: str, output_dir: str, settings: Settings) -> GeneratedMesh | None:
        if not settings.fal_api_key:
            return None
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        headers = {"Authorization": f"Key {settings.fal_api_key}"}
        model = settings.fal_model.strip("/")
        data_uri = _data_uri(Path(image_path))

        try:
            with httpx.Client(timeout=settings.reconstruction_timeout_seconds) as client:
                submit = client.post(
                    f"{_QUEUE_BASE}/{model}",
                    headers={**headers, "Content-Type": "application/json"},
                    json={"input_image_url": data_uri},
                )
                if submit.status_code >= 400:
                    return GeneratedMesh(self.name, "", True, [f"fal submit failed (HTTP {submit.status_code}): {submit.text[:200]}"])
                submitted = submit.json()
                status_url = submitted.get("status_url")
                response_url = submitted.get("response_url")
                if not status_url or not response_url:
                    return GeneratedMesh(self.name, "", True, ["fal returned no status/response url."])

                if not _wait(client, headers, status_url, settings):
                    return GeneratedMesh(self.name, "", True, ["fal task did not complete."])

                result = client.get(response_url, headers=headers)
                if result.status_code >= 400:
                    return GeneratedMesh(self.name, "", True, [f"fal result fetch failed (HTTP {result.status_code})."])
                url = _extract_mesh_url(result.json())
                if not url:
                    return GeneratedMesh(self.name, "", True, ["fal result had no mesh url."])

                mesh_path = download_mesh_file(url, out)
                if mesh_path is None:
                    return GeneratedMesh(self.name, "", True, ["fal mesh download failed."])
                return GeneratedMesh(self.name, str(mesh_path), True, meta={"model": model})
        except Exception as exc:
            return GeneratedMesh(self.name, "", True, [f"fal error: {exc}"])


def _data_uri(path: Path) -> str:
    # Downscale before base64 to keep the request body small and reliable
    # (large phone photos can corrupt over some SSL stacks). See base.resized_data_uri.
    return resized_data_uri(path)


def _wait(client: httpx.Client, headers: dict, status_url: str, settings: Settings) -> bool:
    deadline = time.time() + settings.reconstruction_timeout_seconds
    while time.time() < deadline:
        response = client.get(status_url, headers=headers)
        if response.status_code >= 400:
            return False
        status = (response.json().get("status") or "").upper()
        if status == "COMPLETED":
            return True
        if status in {"FAILED", "ERROR", "CANCELLED"}:
            return False
        time.sleep(3)
    return False


def _extract_mesh_url(payload: dict) -> str | None:
    for key in ("model_mesh", "mesh", "model_glb", "model"):
        value = payload.get(key)
        if isinstance(value, dict) and value.get("url"):
            return value["url"]
        if isinstance(value, str) and value.startswith("http"):
            return value
    return None
