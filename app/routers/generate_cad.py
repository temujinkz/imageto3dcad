from __future__ import annotations

from fastapi import APIRouter, File, Form, Request, UploadFile

from ..config import Settings
from ..jobs import JobStore
from ..models import JobAcceptedResponse
from .upload import _process_job, _save_upload_as_png


def build_router(store: JobStore, settings: Settings) -> APIRouter:
    router = APIRouter(tags=["cad"])

    @router.post("/generate-cad", response_model=JobAcceptedResponse, status_code=202)
    async def generate_cad(
        request: Request,
        image: UploadFile = File(...),
        background_removal: bool = Form(True),
        known_width_mm: float | None = Form(None),
        known_height_mm: float | None = Form(None),
        thickness_mm: float | None = Form(None),
    ) -> JobAcceptedResponse:
        job = store.create_job(
            mode="cad",
            filename=image.filename or "upload.png",
            options={
                "background_removal": background_removal,
                "known_width_mm": known_width_mm,
                "known_height_mm": known_height_mm,
                "thickness_mm": thickness_mm,
            },
        )
        _save_upload_as_png(image, job["input_path"])
        import threading

        threading.Thread(
            target=_process_job,
            args=(store, settings, job["job_id"]),
            daemon=True,
        ).start()
        return JobAcceptedResponse(
            job_id=job["job_id"],
            status="queued",
            progress=0.0,
            message="CAD job queued",
            status_url=str(request.url_for("get_job", job_id=job["job_id"])),
        )

    return router
