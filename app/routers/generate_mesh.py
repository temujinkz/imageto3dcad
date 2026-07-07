from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..config import Settings
from ..jobs import JobStore
from ..models import JobAcceptedResponse
from .upload import _prepare_image, _start_thread


def build_router(store: JobStore, settings: Settings) -> APIRouter:
    router = APIRouter(tags=["mesh"])

    @router.post("/jobs/{job_id}/generate-mesh", response_model=JobAcceptedResponse, status_code=202)
    async def generate_mesh(
        request: Request,
        job_id: str,
    ) -> JobAcceptedResponse:
        job = store.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Invalid job ID")
        _prepare_image(job_id, store, settings)
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
