from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import Settings
from ..jobs import JobStore


ALLOWED_SUFFIXES = {".stl", ".obj", ".glb", ".gltf", ".step", ".dxf", ".png", ".jpg", ".jpeg", ".json"}


def build_router(store: JobStore, settings: Settings) -> APIRouter:
    router = APIRouter(tags=["files"])

    def _serve(job_id: str, filename: str) -> FileResponse:
        job = store.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Invalid job ID")
        job_dir = Path(job["job_dir"]).resolve()
        path = (job_dir / filename).resolve()
        if job_dir not in path.parents and path != job_dir:
            raise HTTPException(status_code=400, detail="Invalid file path")
        if path.suffix.lower() not in ALLOWED_SUFFIXES:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        if not path.exists():
            raise HTTPException(status_code=404, detail="Missing file")
        return FileResponse(path, media_type=_media_type(path), filename=path.name)

    @router.get("/files/{job_id}/{filename}")
    def get_file(job_id: str, filename: str) -> FileResponse:
        return _serve(job_id, filename)

    # Alias requested in the brief: GET /api/jobs/{id}/artifacts/{filename}
    @router.get("/jobs/{job_id}/artifacts/{filename}")
    def get_artifact(job_id: str, filename: str) -> FileResponse:
        return _serve(job_id, filename)

    return router


def _media_type(path: Path) -> str:
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".stl": "model/stl",
        ".obj": "model/obj",
        ".glb": "model/gltf-binary",
        ".gltf": "model/gltf+json",
        ".step": "model/step",
        ".dxf": "image/vnd.dxf",
        ".json": "application/json",
    }.get(path.suffix.lower(), "application/octet-stream")
