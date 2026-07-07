from __future__ import annotations

import shutil
import threading
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from PIL import Image

from ..config import Settings
from ..jobs import JobStore
from ..models import JobAcceptedResponse, JobStatusResponse
from ..services.background import create_masked_image
from ..services.cad_service import generate_flat_part_cad
from ..services.mesh_service import generate_mesh_assets


def build_router(store: JobStore, settings: Settings) -> APIRouter:
    router = APIRouter(tags=["jobs"])

    @router.post("/jobs", response_model=JobAcceptedResponse, status_code=202)
    async def create_job(
        request: Request,
        image: UploadFile = File(...),
        mode: str = Form("both"),
        background_removal: bool = Form(True),
        known_width_mm: float | None = Form(None),
        known_height_mm: float | None = Form(None),
        thickness_mm: float | None = Form(None),
    ) -> JobAcceptedResponse:
        if mode not in {"mesh", "cad", "both"}:
            raise HTTPException(status_code=400, detail="mode must be mesh, cad, or both")
        if not image.filename:
            raise HTTPException(status_code=400, detail="Missing file name")

        job = store.create_job(
            mode=mode,
            filename=image.filename,
            options={
                "background_removal": background_removal,
                "known_width_mm": known_width_mm,
                "known_height_mm": known_height_mm,
                "thickness_mm": thickness_mm,
            },
        )
        _save_upload_as_png(image, Path(job["input_path"]))
        thread = threading.Thread(
            target=_process_job,
            args=(store, settings, job["job_id"]),
            daemon=True,
        )
        thread.start()
        return JobAcceptedResponse(
            job_id=job["job_id"],
            status="queued",
            progress=0.0,
            message="Job queued",
            status_url=str(request.url_for("get_job", job_id=job["job_id"])),
        )

    @router.get("/jobs/{job_id}", response_model=JobStatusResponse, name="get_job")
    def get_job(job_id: str, request: Request) -> JobStatusResponse:
        job = store.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Invalid job ID")
        return _serialize_job(job, request, settings)

    return router


def _save_upload_as_png(upload: UploadFile, destination: Path) -> None:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(".upload")
    with temp_path.open("wb") as handle:
        shutil.copyfileobj(upload.file, handle)
    image = Image.open(temp_path)
    image.convert("RGBA").save(destination)
    temp_path.unlink(missing_ok=True)


def _process_job(store: JobStore, settings: Settings, job_id: str) -> None:
    job = store.update(job_id, status="processing", progress=0.05, message="Preparing image")
    input_path = Path(job["input_path"])
    masked_path = Path(job["masked_path"])
    options = job["options"]
    warnings = create_masked_image(
        input_path=input_path,
        output_path=masked_path,
        enable_background_removal=bool(options.get("background_removal", True)) and settings.enable_rembg,
    )
    for warning in warnings:
        store.append_warning(job_id, warning)

    known_width_mm = options.get("known_width_mm")
    known_height_mm = options.get("known_height_mm")
    thickness_mm = float(options.get("thickness_mm") or settings.default_thickness_mm)

    try:
        outputs: dict[str, str] = {}
        cad_summary = None
        preview_model_path = None

        if job["mode"] in {"mesh", "both"}:
            store.update(job_id, progress=0.35, message="Generating mesh")
            mesh = generate_mesh_assets(
                image_path=masked_path,
                output_dir=Path(job["job_dir"]),
                settings=settings,
                known_width_mm=known_width_mm,
                known_height_mm=known_height_mm,
                thickness_mm=thickness_mm,
            )
            for warning in mesh.get("warnings", []):
                store.append_warning(job_id, warning)
            outputs.update(
                {
                    key: value
                    for key, value in {
                        "mesh.stl": mesh.get("stl_path"),
                        "mesh.obj": mesh.get("obj_path"),
                        "mesh.glb": mesh.get("glb_path"),
                    }.items()
                    if value
                }
            )
            preview_model_path = mesh.get("preview_model_path")

        if job["mode"] in {"cad", "both"}:
            store.update(job_id, progress=0.7 if job["mode"] == "both" else 0.35, message="Generating CAD")
            cad = generate_flat_part_cad(
                image_path=masked_path,
                output_dir=Path(job["job_dir"]),
                known_width_mm=known_width_mm,
                known_height_mm=known_height_mm,
                thickness_mm=thickness_mm,
                settings=settings,
            )
            for warning in cad.get("warnings", []):
                store.append_warning(job_id, warning)
            outputs.update(
                {
                    key: value
                    for key, value in {
                        "cad.step": cad.get("step_path"),
                        "cad.stl": cad.get("stl_path"),
                        "cad.dxf": cad.get("dxf_path"),
                    }.items()
                    if value
                }
            )
            cad_summary = cad.get("cad_summary")
            preview_model_path = preview_model_path or cad.get("preview_model_path")

        store.set_outputs(job_id, outputs)
        store.update(
            job_id,
            status="completed",
            progress=1.0,
            message="Job completed",
            cad_summary=cad_summary,
            preview_model_path=preview_model_path,
        )
    except Exception as exc:
        store.update(
            job_id,
            status="failed",
            progress=1.0,
            message="Processing failed",
            error=str(exc),
        )


def _serialize_job(job: dict, request: Request, settings: Settings) -> JobStatusResponse:
    outputs = job.get("outputs", {})
    files: dict[str, str] = {}
    mode = job["mode"]
    if "cad.step" in outputs:
        files["step"] = _file_url(job["job_id"], "cad.step", request, settings)
    if "cad.dxf" in outputs:
        files["dxf"] = _file_url(job["job_id"], "cad.dxf", request, settings)
    if "cad.stl" in outputs:
        files["stl"] = _file_url(job["job_id"], "cad.stl", request, settings)
    if "mesh.stl" in outputs:
        files["mesh_stl" if mode == "both" else "stl"] = _file_url(
            job["job_id"], "mesh.stl", request, settings
        )
    if "mesh.obj" in outputs:
        files["obj"] = _file_url(job["job_id"], "mesh.obj", request, settings)
    if "mesh.glb" in outputs:
        files["glb"] = _file_url(job["job_id"], "mesh.glb", request, settings)

    preview_model_url = None
    if job.get("preview_model_path"):
        preview_model_url = _file_url(
            job["job_id"],
            Path(job["preview_model_path"]).name,
            request,
            settings,
        )

    return JobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        progress=job["progress"],
        message=job["message"],
        created_at=job["created_at"],
        preview_model_url=preview_model_url,
        files=files,
        cad_summary=job.get("cad_summary"),
        warnings=job.get("warnings", []),
        mode=job["mode"],
        input_image_url=_file_url(job["job_id"], "input.png", request, settings),
        masked_image_url=_file_url(job["job_id"], "masked.png", request, settings),
        error=job.get("error"),
    )


def _file_url(job_id: str, filename: str, request: Request, settings: Settings) -> str:
    base_url = settings.backend_base_url.rstrip("/") if settings.backend_base_url else str(request.base_url).rstrip("/")
    return f"{base_url}{settings.api_prefix}/files/{job_id}/{filename}"
