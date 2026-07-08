from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from ..config import Settings
from ..jobs import JobStore
from ..models import GenerateMeshRequest, JobAcceptedResponse
from .upload import _file_url, _prepare_image, _run_generation_job, _start_thread


def build_router(store: JobStore, settings: Settings) -> APIRouter:
    router = APIRouter(tags=["mesh"])

    @router.post("/generate-mesh", status_code=200)
    async def generate_mesh_legacy(
        request: Request,
        payload: GenerateMeshRequest,
    ) -> dict:
        job = store.get(payload.job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Invalid job ID")
        await run_in_threadpool(_prepare_image, payload.job_id, store, settings)
        result = await run_in_threadpool(
            _run_generation_job,
            store,
            settings,
            payload.job_id,
            run_mesh=True,
            run_cad=False,
        )
        if result["status"] != "completed":
            raise HTTPException(status_code=500, detail=result.get("error") or "Mesh generation failed")
        files: dict[str, str] = {}
        outputs = result.get("outputs", {})
        if "mesh.stl" in outputs:
            files["stl"] = _file_url(payload.job_id, "mesh.stl", request, settings)
        if "mesh.obj" in outputs:
            files["obj"] = _file_url(payload.job_id, "mesh.obj", request, settings)
        if "mesh.glb" in outputs:
            files["glb"] = _file_url(payload.job_id, "mesh.glb", request, settings)
        preview_name = Path(result.get("preview_model_path") or "").name if result.get("preview_model_path") else None
        preview_url = _file_url(payload.job_id, preview_name, request, settings) if preview_name else next(iter(files.values()), None)
        return {
            "job_id": payload.job_id,
            "status": "completed",
            "preview_model_url": preview_url,
            "files": files,
        }

    @router.post("/jobs/{job_id}/generate-mesh", response_model=JobAcceptedResponse, status_code=202)
    async def generate_mesh(
        request: Request,
        job_id: str,
    ) -> JobAcceptedResponse:
        job = store.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Invalid job ID")
        await run_in_threadpool(_prepare_image, job_id, store, settings)
        store.update(job_id, status="queued", progress=0.1, message="Mesh generation queued")
        _start_thread(store, settings, job_id, run_mesh=True, run_cad=False)
        return JobAcceptedResponse(
            job_id=job_id,
            status="queued",
            progress=0.1,
            message="Mesh generation queued",
            status_url=str(request.url_for("get_job", job_id=job_id)),
        )

    return router
