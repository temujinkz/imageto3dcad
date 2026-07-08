"""WaveSpeed AI image-to-3D provider (Hunyuan3D V3 by default).

High-fidelity reconstruction on WaveSpeed's GPUs via their REST API:
submit a task -> poll predictions/{id}/result -> download the GLB from
``data.outputs[0]``. Pay-per-use (the user supplies WAVESPEED_API_KEY).

The image is sent as a base64 data URI in the ``image`` field. WaveSpeed accepts
data URIs on most models; if a given model rejects it, this provider returns a
warning and the chain falls back to the local silhouette engine.
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from ...config import Settings
from .base import GeneratedMesh, download_mesh_file, resized_data_uri


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
        data_uri = resized_data_uri(Path(image_path))

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

    def generate_multiview(
        self, image_paths: list[str], output_dir: str, settings: Settings
    ) -> GeneratedMesh | None:
        """Fuse several angle photos into one mesh via WaveSpeed's Hunyuan3D V2
        Multi-View model (named front/back/left views), rather than guessing the
        hidden sides from a single image. Falls back to single-image ``generate``
        if only one view is available."""
        if not settings.wavespeed_api_key:
            return None
        views = [p for p in image_paths if p and Path(p).exists()]
        if len(views) < 2:
            return self.generate(views[0], output_dir, settings) if views else None

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        headers = {"Authorization": f"Bearer {settings.wavespeed_api_key}"}
        base = settings.wavespeed_api_base.rstrip("/")
        submit_url = f"{base}/{settings.wavespeed_multiview_model.strip('/')}"

        front = Path(views[0])
        back = Path(views[1])
        left = Path(views[2]) if len(views) > 2 else front

        try:
            with httpx.Client(timeout=settings.reconstruction_timeout_seconds) as client:
                submit = client.post(
                    submit_url,
                    headers={**headers, "Content-Type": "application/json"},
                    json={
                        "front_image_url": resized_data_uri(front),
                        "back_image_url": resized_data_uri(back),
                        "left_image_url": resized_data_uri(left),
                        "textured_mesh": True,
                    },
                )
                if submit.status_code >= 400:
                    return GeneratedMesh(
                        self.name, "", True,
                        [f"WaveSpeed multi-view submit failed (HTTP {submit.status_code}): {submit.text[:200]}"],
                    )
                data = submit.json().get("data") or {}
                request_id = data.get("id")
                if not request_id:
                    return GeneratedMesh(self.name, "", True, ["WaveSpeed multi-view returned no prediction id."])

                # Construct the poll URL ourselves: WaveSpeed's returned
                # data.urls.get has a malformed double slash that 404s.
                poll_url = f"{base}/predictions/{request_id}/result"
                url = _poll(client, headers, poll_url, settings)
                if not url:
                    return GeneratedMesh(self.name, "", True, ["WaveSpeed multi-view task did not produce a model."])

                mesh_path = download_mesh_file(url, out)
                if mesh_path is None:
                    return GeneratedMesh(self.name, "", True, ["WaveSpeed multi-view model download failed."])
                return GeneratedMesh(
                    self.name, str(mesh_path), True,
                    meta={"request_id": request_id, "views": len(views), "multiview": True},
                )
        except Exception as exc:
            return GeneratedMesh(self.name, "", True, [f"WaveSpeed multi-view error: {exc}"])


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
