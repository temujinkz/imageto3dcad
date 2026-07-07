from __future__ import annotations

import shutil
import threading
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from PIL import Image

from ..config import Settings
from ..jobs import JobStore
from ..models import JobAcceptedResponse, JobStatusResponse, UploadImageResponse
from ..services.background import create_masked_image
from ..services.cad_service import generate_flat_part_cad
from ..services.mesh_service import generate_mesh_assets


def build_router(store: JobStore, settings: Settings) -> APIRouter:
    router = APIRouter(tags=["jobs"])

    @router.post("/upload-image", response_model=JobAcceptedResponse, status_code=202)
    async def upload_image(
        request: Request,
        image: UploadFile = File(...),
        background_removal: bool = Form(True),
        known_width_mm: float | None = Form(None),
        known_height_mm: float | None = Form(None),
        thickness_mm: float | None = Form(None),
    ) -> JobAcceptedResponse:
        if not image.filename:
            raise HTTPException(status_code=400, detail="Missing file name")

        job = store.create_job(
            mode="upload",
            filename=image.filename,
            options={
                "background_removal": background_removal,
                "known_width_mm": known_width_mm,
                "known_height_mm": known_height_mm,
                "thickness_mm": thickness_mm,
            },
        )
        _save_upload_as_png(image, Path(job["input_path"]))
        _prepare_image(job["job_id"], store, settings)
        return JobAcceptedResponse(
            job_id=job["job_id"],
            status="completed",
            progress=0.1,
            message="Image uploaded and prepared",
            status_url=str(request.url_for("get_job", job_id=job["job_id"])),
        )

    @router.post("/upload", response_model=UploadImageResponse, status_code=200)
    async def upload_image_legacy(
        request: Request,
        image: UploadFile = File(...),
        background_removal: bool = Form(True),
        known_width_mm: float | None = Form(None),
        known_height_mm: float | None = Form(None),
        thickness_mm: float | None = Form(None),
    ) -> UploadImageResponse:
        if not image.filename:
            raise HTTPException(status_code=400, detail="Missing file name")

        job = store.create_job(
            mode="upload",
            filename=image.filename,
            options={
                "background_removal": background_removal,
                "known_width_mm": known_width_mm,
                "known_height_mm": known_height_mm,
                "thickness_mm": thickness_mm,
            },
        )
        _save_upload_as_png(image, Path(job["input_path"]))
        _prepare_image(job["job_id"], store, settings)
        saved = store.get(job["job_id"])
        if saved is None:
            raise HTTPException(status_code=500, detail="Image processing failed")

        return UploadImageResponse(
            job_id=job["job_id"],
            image_url=_file_url(job["job_id"], "input.png", request, settings),
            masked_image_url=_file_url(job["job_id"], "masked.png", request, settings)
            if Path(saved["masked_path"]).exists()
            else None,
        )

    @router.post("/jobs", response_model=JobAcceptedResponse, status_code=202)
    async def create_job_and_run_all(
        request: Request,
        image: UploadFile = File(...),
        background_removal: bool = Form(True),
        known_width_mm: float | None = Form(None),
        known_height_mm: float | None = Form(None),
        thickness_mm: float | None = Form(None),
    ) -> JobAcceptedResponse:
        if not image.filename:
            raise HTTPException(status_code=400, detail="Missing file name")
        job = store.create_job(
            mode="both",
            filename=image.filename,
            options={
                "background_removal": background_removal,
                "known_width_mm": known_width_mm,
                "known_height_mm": known_height_mm,
                "thickness_mm": thickness_mm,
            },
        )
        _save_upload_as_png(image, Path(job["input_path"]))
        _start_thread(store, settings, job["job_id"], run_mesh=True, run_cad=True)
        return JobAcceptedResponse(
            job_id=job["job_id"],
            status="queued",
            progress=0.0,
            message="Image uploaded. Mesh and CAD generation queued.",
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


def _prepare_image(job_id: str, store: JobStore, settings: Settings) -> dict:
    job = store.get(job_id)
    if job is None:
        raise ValueError("Invalid job ID")
    input_path = Path(job["input_path"])
    if not input_path.exists():
        raise ValueError("Missing file")
    if Path(job["masked_path"]).exists():
        return job

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
    return store.update(
        job_id,
        status="completed",
        progress=max(float(job["progress"]), 0.1),
        message="Image uploaded and prepared",
    )


def _start_thread(
    store: JobStore,
    settings: Settings,
    job_id: str,
    *,
    run_mesh: bool,
    run_cad: bool,
) -> None:
    thread = threading.Thread(
        target=_process_job,
        args=(store, settings, job_id, run_mesh, run_cad),
        daemon=True,
    )
    thread.start()


def _run_generation_job(
    store: JobStore,
    settings: Settings,
    job_id: str,
    *,
    run_mesh: bool,
    run_cad: bool,
) -> dict:
    _prepare_image(job_id, store, settings)
    job = store.update(job_id, status="processing", progress=0.15, message="Starting generation")
    masked_path = Path(job["masked_path"])
    options = job["options"]
    known_width_mm = options.get("known_width_mm")
    known_height_mm = options.get("known_height_mm")
    thickness_mm = float(options.get("thickness_mm") or settings.default_thickness_mm)

    outputs = dict(job.get("outputs", {}))
    cad_summary = job.get("cad_summary")
    preview_model_path = job.get("preview_model_path")

    if run_mesh:
        job = store.update(job_id, progress=0.4 if run_cad else 0.5, message="Generating mesh")
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
        preview_model_path = mesh.get("preview_model_path") or preview_model_path

    if run_cad:
        job = store.update(
            job_id,
            progress=0.75 if run_mesh else 0.5,
            message="Generating CAD",
        )
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
    return store.update(
        job_id,
        status="completed",
        progress=1.0,
        message=_completion_message(run_mesh=run_mesh, run_cad=run_cad),
        cad_summary=cad_summary,
        preview_model_path=preview_model_path,
        mode=_result_mode(run_mesh=run_mesh, run_cad=run_cad, current_mode=job["mode"]),
        error=None,
    )


def _process_job(
    store: JobStore,
    settings: Settings,
    job_id: str,
    run_mesh: bool,
    run_cad: bool,
) -> None:
    try:
        _run_generation_job(
            store,
            settings,
            job_id,
            run_mesh=run_mesh,
            run_cad=run_cad,
        )
    except Exception as exc:
        store.update(
            job_id,
            status="failed",
            progress=1.0,
            message="Processing failed",
            error=str(exc),
        )


def _result_mode(*, run_mesh: bool, run_cad: bool, current_mode: str) -> str:
    if run_mesh and run_cad:
        return "both"
    if run_mesh and current_mode == "cad":
        return "both"
    if run_cad and current_mode == "mesh":
        return "both"
    if run_mesh:
        return "mesh" if current_mode == "upload" else current_mode
    if run_cad:
        return "cad" if current_mode == "upload" else current_mode
    return current_mode


def _completion_message(*, run_mesh: bool, run_cad: bool) -> str:
    if run_mesh and run_cad:
        return "Mesh and CAD generation completed"
    if run_mesh:
        return "Mesh generation completed"
    if run_cad:
        return "CAD generation completed"
    return "Job completed"


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
