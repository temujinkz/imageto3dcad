"""WaveSpeed AI image-to-3D provider (Hunyuan3D V3 by default).

High-fidelity reconstruction on WaveSpeed's GPUs via their REST API:
submit a task -> poll predictions/{id}/result -> download the GLB from
``data.outputs[0]``. Pay-per-use (the user supplies WAVESPEED_API_KEY).

The image is sent as a base64 data URI in the ``image`` field. WaveSpeed accepts
data URIs on most models; if a given model rejects it, this provider returns a
warning and the chain falls back to the local silhouette engine.
"""

from __future__ import annotations

import base64
import time
from pathlib import Path

import httpx

from ...config import Settings
from .base import GeneratedMesh, download_mesh_file


class WaveSpeedProvider:
    name = "wavespeed-hunyuan3d"

    def available(self, settings: Settings) -> bool:
        return bool(settings.wavespeed_api_key)

    def generate(self, image_path: str, output_dir: str, settings: Settings) -> GeneratedMesh | None:
        if not settings.wavespeed_api_key:
            return None
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        headers = {"Authorization": f"Bearer {settings.wavespeed_api_key}"}
        base = settings.wavespeed_api_base.rstrip("/")
        submit_url = f"{base}/{settings.wavespeed_model.strip('/')}"
        data_uri = _data_uri(Path(image_path))

        try:
            with httpx.Client(timeout=settings.reconstruction_timeout_seconds) as client:
                submit = client.post(
                    submit_url,
                    headers={**headers, "Content-Type": "application/json"},
                    json={
                        "image": data_uri,
                        "enable_pbr": True,
                        "polygon_type": "triangle",
                        "generate_type": "Normal",
                    },
                )
                if submit.status_code >= 400:
                    return GeneratedMesh(self.name, "", True, [f"WaveSpeed submit failed (HTTP {submit.status_code}): {submit.text[:200]}"])
                data = submit.json().get("data") or {}
                request_id = data.get("id")
                poll_url = ((data.get("urls") or {}).get("get")) or (f"{base}/predictions/{request_id}/result" if request_id else None)
                if not poll_url:
                    return GeneratedMesh(self.name, "", True, ["WaveSpeed returned no prediction id."])

                url = _poll(client, headers, poll_url, settings)
                if not url:
                    return GeneratedMesh(self.name, "", True, ["WaveSpeed task did not produce a model."])

                mesh_path = download_mesh_file(url, out)
                if mesh_path is None:
                    return GeneratedMesh(self.name, "", True, ["WaveSpeed model download failed."])
                return GeneratedMesh(self.name, str(mesh_path), True, meta={"request_id": request_id})
        except Exception as exc:
            return GeneratedMesh(self.name, "", True, [f"WaveSpeed error: {exc}"])


def _data_uri(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _poll(client: httpx.Client, headers: dict, poll_url: str, settings: Settings) -> str | None:
    deadline = time.time() + settings.reconstruction_timeout_seconds
    while time.time() < deadline:
        response = client.get(poll_url, headers=headers)
        if response.status_code >= 400:
            return None
        data = response.json().get("data") or {}
        status = (data.get("status") or "").lower()
        if status in {"completed", "succeeded", "success"}:
            outputs = data.get("outputs") or []
            if outputs:
                return outputs[0]
            return (data.get("output") or {}).get("model") if isinstance(data.get("output"), dict) else None
        if status in {"failed", "error", "canceled", "cancelled"}:
            return None
        time.sleep(3)
    return None
