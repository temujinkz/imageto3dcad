from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from ..config import Settings
from ..jobs import JobStore
from ..models import GenerateCadRequest, JobAcceptedResponse
from .upload import _file_url, _prepare_image, _run_generation_job, _start_thread


def build_router(store: JobStore, settings: Settings) -> APIRouter:
    router = APIRouter(tags=["cad"])

    @router.post("/generate-cad", status_code=200)
    async def generate_cad_legacy(
        request: Request,
        payload: GenerateCadRequest,
    ) -> dict:
        job = store.get(payload.job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Invalid job ID")
        options = dict(job.get("options", {}))
        if payload.known_width_mm is not None:
            options["known_width_mm"] = payload.known_width_mm
        if payload.known_height_mm is not None:
            options["known_height_mm"] = payload.known_height_mm
        if payload.thickness_mm is not None:
            options["thickness_mm"] = payload.thickness_mm
        store.update(payload.job_id, options=options)
        await run_in_threadpool(_prepare_image, payload.job_id, store, settings)
        result = await run_in_threadpool(
            _run_generation_job,
            store,
            settings,
            payload.job_id,
            run_mesh=False,
            run_cad=True,
        )
        if result["status"] != "completed":
            raise HTTPException(status_code=500, detail=result.get("error") or "CAD generation failed")
        files: dict[str, str] = {}
        outputs = result.get("outputs", {})
        if "cad.step" in outputs:
            files["step"] = _file_url(payload.job_id, "cad.step", request, settings)
        if "cad.dxf" in outputs:
            files["dxf"] = _file_url(payload.job_id, "cad.dxf", request, settings)
        if "cad.stl" in outputs:
            files["stl"] = _file_url(payload.job_id, "cad.stl", request, settings)
        preview_name = Path(result.get("preview_model_path") or "").name if result.get("preview_model_path") else None
        preview_url = _file_url(payload.job_id, preview_name, request, settings) if preview_name else files.get("stl")
        return {
            "job_id": payload.job_id,
            "status": "completed",
            "preview_model_url": preview_url,
            "files": files,
            "cad_summary": result.get("cad_summary"),
        }

    @router.post("/jobs/{job_id}/generate-cad", response_model=JobAcceptedResponse, status_code=202)
    async def generate_cad(
        request: Request,
        job_id: str,
    ) -> JobAcceptedResponse:
        job = store.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Invalid job ID")
        await run_in_threadpool(_prepare_image, job_id, store, settings)
        store.update(job_id, status="queued", progress=0.1, message="CAD generation queued")
        _start_thread(store, settings, job_id, run_mesh=False, run_cad=True)
        return JobAcceptedResponse(
            job_id=job_id,
            status="queued",
            progress=0.1,
            message="CAD generation queued",
            status_url=str(request.url_for("get_job", job_id=job_id)),
        )

    return router
