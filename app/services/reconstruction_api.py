from __future__ import annotations

import base64
import importlib
import time
from pathlib import Path

import httpx

from ..config import Settings


def reconstruct_from_images(
    image_paths: list[Path],
    output_dir: Path,
    settings: Settings,
) -> dict:
    """Try cloud 3D APIs (Luma, CSM) then local TripoSR for multi-view reconstruction."""
    output_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    if len(image_paths) > 1 or _is_video_source(image_paths):
        for provider in _provider_order(settings):
            result = _try_provider(provider, image_paths, output_dir, settings)
            if result:
                result["warnings"] = warnings + result.get("warnings", [])
                return result
            warnings.append(f"{provider} unavailable or failed.")

    # Single image: prefer TripoSR, then cloud APIs
    primary = image_paths[0]
    from .triposr_service import generate_mesh_from_image

    tripo = generate_mesh_from_image(str(primary), str(output_dir / "triposr"), settings=settings)
    if any(tripo.get(key) for key in ("stl_path", "obj_path", "glb_path")):
        tripo["source"] = tripo.get("source", "triposr")
        tripo["warnings"] = warnings + tripo.get("warnings", [])
        return tripo

    warnings.extend(tripo.get("warnings", []))
    for provider in _provider_order(settings):
        result = _try_provider(provider, image_paths, output_dir, settings)
        if result:
            result["warnings"] = warnings + result.get("warnings", [])
            return result
        warnings.append(f"{provider} unavailable or failed.")

    return {"source": "none", "warnings": warnings}


def _is_video_source(image_paths: list[Path]) -> bool:
    return any(path.name.startswith("frame_") for path in image_paths)


def _provider_order(settings: Settings) -> list[str]:
    order: list[str] = []
    if settings.luma_api_key:
        order.append("luma")
    if settings.csm_api_key:
        order.append("csm")
    if settings.tripo_api_key:
        order.append("tripo")
    if settings.meshy_api_key:
        order.append("meshy")
    return order


def _try_provider(
    provider: str,
    image_paths: list[Path],
    output_dir: Path,
    settings: Settings,
) -> dict | None:
    if provider == "luma":
        return _luma_reconstruct(image_paths, output_dir, settings)
    if provider == "csm":
        return _csm_reconstruct(image_paths, output_dir, settings)
    if provider == "tripo":
        return _tripo_api_reconstruct(image_paths, output_dir, settings)
    if provider == "meshy":
        return _meshy_reconstruct(image_paths, output_dir, settings)
    return None


def _meshy_reconstruct(image_paths: list[Path], output_dir: Path, settings: Settings) -> dict | None:
    if not settings.meshy_api_key:
        return None

    primary = image_paths[0]
    mime = "image/png" if primary.suffix.lower() == ".png" else "image/jpeg"
    data_uri = f"data:{mime};base64,{base64.b64encode(primary.read_bytes()).decode('ascii')}"
    headers = {"Authorization": f"Bearer {settings.meshy_api_key}"}

    try:
        with httpx.Client(timeout=settings.reconstruction_timeout_seconds) as client:
            create = client.post(
                f"{settings.meshy_api_base}/image-to-3d",
                headers=headers,
                json={"image_url": data_uri, "enable_pbr": False},
            )
            if create.status_code >= 400:
                return None
            task_id = create.json().get("result") or create.json().get("id")
            if not task_id:
                return None

            download_url = _poll_meshy(client, headers, task_id, settings)
            if not download_url:
                return None
            return _download_mesh(download_url, output_dir, source="meshy")
    except Exception:
        return None


def _poll_meshy(client: httpx.Client, headers: dict, task_id: str, settings: Settings) -> str | None:
    deadline = time.time() + settings.reconstruction_timeout_seconds
    while time.time() < deadline:
        response = client.get(f"{settings.meshy_api_base}/image-to-3d/{task_id}", headers=headers)
        if response.status_code >= 400:
            return None
        payload = response.json()
        status = (payload.get("status") or "").upper()
        if status in {"SUCCEEDED", "SUCCESS", "COMPLETED"}:
            model_urls = payload.get("model_urls", {})
            return model_urls.get("glb") or model_urls.get("obj") or payload.get("model_url")
        if status in {"FAILED", "ERROR", "CANCELED"}:
            return None
        time.sleep(4)
    return None


def _luma_reconstruct(image_paths: list[Path], output_dir: Path, settings: Settings) -> dict | None:
    if not settings.luma_api_key:
        return None

    headers = {"Authorization": f"Bearer {settings.luma_api_key}"}
    files = [("images", (path.name, path.read_bytes(), "image/png")) for path in image_paths]

    try:
        with httpx.Client(timeout=settings.reconstruction_timeout_seconds) as client:
            create = client.post(
                f"{settings.luma_api_base}/capture",
                headers=headers,
                files=files,
            )
            if create.status_code >= 400:
                return None
            payload = create.json()
            capture_id = payload.get("id") or payload.get("capture_id")
            if not capture_id:
                return None

            download_url = _poll_luma(client, headers, capture_id, settings)
            if not download_url:
                return None
            return _download_mesh(download_url, output_dir, source="luma")
    except Exception:
        return None


def _poll_luma(client: httpx.Client, headers: dict, capture_id: str, settings: Settings) -> str | None:
    deadline = time.time() + settings.reconstruction_timeout_seconds
    while time.time() < deadline:
        response = client.get(f"{settings.luma_api_base}/capture/{capture_id}", headers=headers)
        if response.status_code >= 400:
            return None
        payload = response.json()
        status = (payload.get("status") or "").lower()
        if status in {"completed", "finished", "ready"}:
            return payload.get("model_urls", {}).get("glb") or payload.get("download_url")
        if status in {"failed", "error"}:
            return None
        time.sleep(4)
    return None


def _csm_reconstruct(image_paths: list[Path], output_dir: Path, settings: Settings) -> dict | None:
    if not settings.csm_api_key:
        return None

    headers = {"x-api-key": settings.csm_api_key}
    files = [("file", (path.name, path.read_bytes(), "image/png")) for path in image_paths]

    try:
        with httpx.Client(timeout=settings.reconstruction_timeout_seconds) as client:
            create = client.post(
                f"{settings.csm_api_base}/sessions",
                headers=headers,
                files=files,
            )
            if create.status_code >= 400:
                return None
            session_id = create.json().get("session_id") or create.json().get("id")
            if not session_id:
                return None

            download_url = _poll_csm(client, headers, session_id, settings)
            if not download_url:
                return None
            return _download_mesh(download_url, output_dir, source="csm")
    except Exception:
        return None


def _poll_csm(client: httpx.Client, headers: dict, session_id: str, settings: Settings) -> str | None:
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


def _tripo_api_reconstruct(image_paths: list[Path], output_dir: Path, settings: Settings) -> dict | None:
    if not settings.tripo_api_key:
        return None

    headers = {"Authorization": f"Bearer {settings.tripo_api_key}"}
    files = [("images", (path.name, path.read_bytes(), "image/png")) for path in image_paths]

    try:
        with httpx.Client(timeout=settings.reconstruction_timeout_seconds) as client:
            create = client.post(
                f"{settings.tripo_api_base}/task",
                headers=headers,
                files=files,
            )
            if create.status_code >= 400:
                return None
            task_id = create.json().get("task_id") or create.json().get("id")
            if not task_id:
                return None

            download_url = _poll_tripo(client, headers, task_id, settings)
            if not download_url:
                return None
            return _download_mesh(download_url, output_dir, source="tripo-api")
    except Exception:
        return None


def _poll_tripo(client: httpx.Client, headers: dict, task_id: str, settings: Settings) -> str | None:
    deadline = time.time() + settings.reconstruction_timeout_seconds
    while time.time() < deadline:
        response = client.get(f"{settings.tripo_api_base}/task/{task_id}", headers=headers)
        if response.status_code >= 400:
            return None
        payload = response.json()
        status = (payload.get("status") or "").lower()
        if status in {"success", "completed", "ready"}:
            return payload.get("model_url") or payload.get("output", {}).get("model")
        if status in {"failed", "error"}:
            return None
        time.sleep(4)
    return None


def _download_mesh(url: str, output_dir: Path, source: str) -> dict | None:
    try:
        with httpx.Client(timeout=120, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            suffix = ".glb"
            if ".obj" in url.lower():
                suffix = ".obj"
            elif ".stl" in url.lower():
                suffix = ".stl"
            raw_path = output_dir / f"remote_mesh{suffix}"
            raw_path.write_bytes(response.content)
            return _normalize_mesh(raw_path, output_dir, source=source)
    except Exception:
        return None


def _normalize_mesh(raw_path: Path, output_dir: Path, source: str) -> dict:
    stl_path = output_dir / "mesh.stl"
    obj_path = output_dir / "mesh.obj"
    glb_path = output_dir / "mesh.glb"
    result: dict = {"source": source, "warnings": []}

    try:
        trimesh = importlib.import_module("trimesh")
        mesh = trimesh.load_mesh(raw_path, force="mesh")
        mesh.export(stl_path)
        mesh.export(obj_path)
        mesh.export(glb_path)
        result.update(
            {
                "stl_path": str(stl_path),
                "obj_path": str(obj_path),
                "glb_path": str(glb_path),
                "preview_model_path": str(glb_path),
            }
        )
        return result
    except Exception as exc:
        suffix = raw_path.suffix.lower()
        if suffix == ".stl":
            result["stl_path"] = str(raw_path)
        elif suffix == ".obj":
            result["obj_path"] = str(raw_path)
        elif suffix == ".glb":
            result["glb_path"] = str(raw_path)
        result["preview_model_path"] = str(raw_path)
        result["warnings"].append(f"Trimesh normalization skipped: {exc}")
        return result
