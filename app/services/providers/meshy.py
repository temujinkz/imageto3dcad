"""Meshy AI image-to-3D provider (https://docs.meshy.ai).

Primary cloud engine: reconstruction runs on Meshy's GPUs, so the user's Mac
does no neural work. Free tier grants monthly credits.
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from ...config import Settings
from .base import GeneratedMesh, download_mesh_file, resized_data_uri


class MeshyProvider:
    name = "meshy"

    def available(self, settings: Settings) -> bool:
        return bool(settings.meshy_api_key)

    def generate(self, image_path: str, output_dir: str, settings: Settings) -> GeneratedMesh | None:
        if not settings.meshy_api_key:
            return None
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        headers = {"Authorization": f"Bearer {settings.meshy_api_key}"}
        data_uri = _data_uri(Path(image_path))

        # Three tiers (texturing is Meshy's real time sink, ~3x the geometry step):
        #   turbo   -> no texture, light mesh        (~1 min, geometry only)
        #   fast    -> base-color texture, light mesh (~3-4 min, keeps color/text)
        #   quality -> PBR texture, dense mesh        (~4 min, maximum detail)
        mode = settings.meshy_mode
        quality = mode == "quality"
        turbo = mode == "turbo"
        body = {
            "image_url": data_uri,
            "ai_model": settings.meshy_ai_model,
            "should_texture": not turbo,
            "should_remesh": True,
            "topology": "triangle",
            "symmetry_mode": "auto",
            # Only ask for GLB — OBJ/STL are derived locally in postprocess. Fewer
            # requested formats measurably reduces Meshy task time.
            "target_formats": ["glb"],
            "enable_pbr": quality,
            "target_polycount": settings.meshy_target_polycount if quality else 30000,
        }

        try:
            with httpx.Client(timeout=settings.reconstruction_timeout_seconds) as client:
                create = client.post(
                    f"{settings.meshy_api_base}/image-to-3d",
                    headers=headers,
                    json=body,
                )
                if create.status_code >= 400:
                    return GeneratedMesh(
                        source=self.name,
                        mesh_path="",
                        is_high_fidelity=True,
                        warnings=[f"Meshy create failed (HTTP {create.status_code}): {create.text[:200]}"],
                    )
                task_id = create.json().get("result") or create.json().get("id")
                if not task_id:
                    return GeneratedMesh(self.name, "", True, ["Meshy returned no task id."])

                url = _poll(client, headers, task_id, settings)
                if not url:
                    return GeneratedMesh(self.name, "", True, ["Meshy task did not produce a model."])

                mesh_path = download_mesh_file(url, out)
                if mesh_path is None:
                    return GeneratedMesh(self.name, "", True, ["Meshy model download failed."])
                return GeneratedMesh(
                    source=self.name,
                    mesh_path=str(mesh_path),
                    is_high_fidelity=True,
                    meta={"task_id": task_id},
                )
        except Exception as exc:  # network/timeouts -> fall through to next provider
            return GeneratedMesh(self.name, "", True, [f"Meshy error: {exc}"])


def _data_uri(path: Path) -> str:
    # Downscale before base64 to keep the request body small and reliable
    # (large phone photos can corrupt over some SSL stacks). See base.resized_data_uri.
    return resized_data_uri(path)


def _poll(client: httpx.Client, headers: dict, task_id: str, settings: Settings) -> str | None:
    deadline = time.time() + settings.reconstruction_timeout_seconds
    while time.time() < deadline:
        response = client.get(f"{settings.meshy_api_base}/image-to-3d/{task_id}", headers=headers)
        if response.status_code >= 400:
            return None
        payload = response.json()
        status = (payload.get("status") or "").upper()
        if status in {"SUCCEEDED", "SUCCESS", "COMPLETED"}:
            urls = payload.get("model_urls", {}) or {}
            return urls.get("glb") or urls.get("obj") or urls.get("fbx") or payload.get("model_url")
        if status in {"FAILED", "ERROR", "CANCELED", "EXPIRED"}:
            return None
        time.sleep(4)
    return None
