from __future__ import annotations

import shutil
import threading
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from PIL import Image

from ..config import Settings
from ..jobs import JobStore
from ..models import JobAcceptedResponse, JobStatusResponse, ProcessRequest, ProcessResponse, UploadImageResponse
from ..services.background import create_masked_image
from ..services.cad_service import generate_flat_part_cad
from ..services.freecad_service import prepare_freecad_exports
from ..services.image_convert import SUPPORTED_EXTENSIONS, VIDEO_EXTENSIONS, save_upload_as_png
from ..services.mesh_service import generate_mesh_assets
from ..services.video_frames import extract_key_frames


def build_router(store: JobStore, settings: Settings) -> APIRouter:
    router = APIRouter(tags=["jobs"])

    @router.post("/upload", response_model=UploadImageResponse, status_code=200)
    async def upload_media(
        request: Request,
        image: UploadFile | None = File(None),
        images: list[UploadFile] | None = File(None),
        video: UploadFile | None = File(None),
        background_removal: bool = Form(True),
    ) -> UploadImageResponse:
        uploads = _collect_uploads(image=image, images=images, video=video)
        if not uploads:
            raise HTTPException(status_code=400, detail="Upload at least one image or video.")

        primary = uploads[0]
        if not primary.filename:
            raise HTTPException(status_code=400, detail="Missing file name")

        job = store.create_job(
            mode="upload",
            filename=primary.filename,
            options={"background_removal": background_removal},
        )
        job_dir = Path(job["job_dir"])
        warnings: list[str] = []

        if _is_video(primary.filename):
            video_path = job_dir / f"input{Path(primary.filename).suffix.lower()}"
            _save_raw_upload(primary, video_path)
            frames, frame_warnings = extract_key_frames(
                video_path,
                job_dir / "frames",
                max_frames=settings.max_video_frames,
            )
            warnings.extend(frame_warnings)
            if not frames:
                raise HTTPException(status_code=400, detail="Could not extract frames from video.")
            _save_frame_as_primary(frames[0], Path(job["input_path"]))
            extra_paths = [_save_extra_image(frame, job_dir, index) for index, frame in enumerate(frames[1:], start=1)]
            store.update(job["job_id"], extra_image_paths=[str(path) for path in extra_paths if path])
        else:
            temp_path = job_dir / f"upload{Path(primary.filename).suffix.lower() or '.bin'}"
            _save_raw_upload(primary, temp_path)
            warnings.extend(save_upload_as_png(temp_path, Path(job["input_path"])))

            extra_paths: list[str] = []
            for index, upload in enumerate(uploads[1:], start=1):
                if not upload.filename:
                    continue
                if _is_video(upload.filename):
                    warnings.append(f"Skipped video in multi-upload slot {index + 1}; use a single video upload.")
                    continue
                extra = _save_uploaded_image(upload, job_dir, index)
                if extra:
                    extra_paths.append(str(extra))
            if extra_paths:
                store.update(job["job_id"], extra_image_paths=extra_paths)

        prepared = _prepare_image(job["job_id"], store, settings)
        if prepared["status"] == "failed":
            raise HTTPException(status_code=400, detail=prepared.get("error") or "Could not read that file as an image.")
        for warning in warnings:
            store.append_warning(job["job_id"], warning)

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

    @router.post("/upload-image", response_model=UploadImageResponse, status_code=200)
    async def upload_image_alias(
        request: Request,
        image: UploadFile = File(...),
        background_removal: bool = Form(True),
    ) -> UploadImageResponse:
        return await upload_media(
            request=request, image=image, images=None, video=None, background_removal=background_removal
        )

    @router.post("/process", response_model=ProcessResponse, status_code=200)
    async def process_job(request: Request, payload: ProcessRequest) -> ProcessResponse:
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

        result = _run_generation_job(
            store,
            settings,
            payload.job_id,
            run_mesh=payload.generate_mesh,
            run_cad=payload.generate_cad,
            run_freecad=payload.generate_freecad,
        )
        if result["status"] == "failed":
            raise HTTPException(status_code=500, detail=result.get("error") or "Processing failed")

        return _serialize_process(result, request, settings)

    @router.post("/jobs", response_model=JobAcceptedResponse, status_code=202)
    async def create_job_and_run_all(
        request: Request,
        image: UploadFile = File(...),
        background_removal: bool = Form(True),
    ) -> JobAcceptedResponse:
        upload_response = await upload_media(
            request=request, image=image, images=None, video=None, background_removal=background_removal
        )
        store.update(upload_response.job_id, status="queued", progress=0.1, message="Processing queued")
        _start_thread(store, settings, upload_response.job_id, run_mesh=True, run_cad=True, run_freecad=True)
        return JobAcceptedResponse(
            job_id=upload_response.job_id,
            status="queued",
            progress=0.1,
            message="Upload complete. Full pipeline queued.",
            status_url=str(request.url_for("get_job", job_id=upload_response.job_id)),
        )

    @router.get("/jobs/{job_id}", response_model=JobStatusResponse, name="get_job")
    def get_job(job_id: str, request: Request) -> JobStatusResponse:
        job = store.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Invalid job ID")
        return _serialize_job(job, request, settings)

    return router


def _collect_uploads(
    *,
    image: UploadFile | None,
    images: list[UploadFile] | None,
    video: UploadFile | None,
) -> list[UploadFile]:
    collected: list[UploadFile] = []
    if video and video.filename:
        collected.append(video)
    if image and image.filename:
        collected.append(image)
    if images:
        collected.extend(item for item in images if item.filename)
    return collected


def _is_video(filename: str) -> bool:
    return Path(filename).suffix.lower() in VIDEO_EXTENSIONS


def _save_raw_upload(upload: UploadFile, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        shutil.copyfileobj(upload.file, handle)


def _save_uploaded_image(upload: UploadFile, job_dir: Path, index: int) -> Path | None:
    if not upload.filename:
        return None
    temp_path = job_dir / f"upload_{index}{Path(upload.filename).suffix.lower() or '.bin'}"
    _save_raw_upload(upload, temp_path)
    png_path = job_dir / f"angle_{index:02d}.png"
    save_upload_as_png(temp_path, png_path)
    return png_path


def _save_extra_image(source: Path, job_dir: Path, index: int) -> Path | None:
    destination = job_dir / f"angle_{index:02d}.png"
    try:
        with Image.open(source) as image:
            image.convert("RGBA").save(destination, format="PNG")
        return destination
    except Exception:
        return None


def _save_frame_as_primary(frame: Path, destination: Path) -> None:
    with Image.open(frame) as image:
        image.convert("RGBA").save(destination, format="PNG")


def _prepare_image(job_id: str, store: JobStore, settings: Settings) -> dict:
    job = store.get(job_id)
    if job is None:
        raise ValueError("Invalid job ID")
    input_path = Path(job["input_path"])
    if not input_path.exists():
        raise ValueError("Missing file")
    if Path(job["masked_path"]).exists():
        return job

    job = store.update(job_id, status="processing", progress=0.05, message="Removing background")
    masked_path = Path(job["masked_path"])
    options = job["options"]
    enable_bg = bool(options.get("background_removal", True)) and settings.enable_rembg
    try:
        warnings = create_masked_image(
            input_path=input_path,
            output_path=masked_path,
            enable_background_removal=enable_bg,
            backend=settings.background_removal_backend,
        )
    except Exception as exc:
        return store.update(
            job_id,
            status="failed",
            progress=1.0,
            message="Upload failed",
            error=f"Could not read that file as an image: {exc}",
        )
    for warning in warnings:
        store.append_warning(job_id, warning)

    # Background-remove every extra angle too, so multi-view reconstruction
    # isn't polluted by the floor/background of the non-primary views (which
    # otherwise show up as stray geometry around the object).
    extra_paths = job.get("extra_image_paths", [])
    if enable_bg and extra_paths:
        masked_extras: list[str] = []
        for angle_path in extra_paths:
            src = Path(angle_path)
            if not src.exists():
                continue
            masked_angle = src.with_name(f"{src.stem}_masked.png")
            try:
                create_masked_image(
                    input_path=src,
                    output_path=masked_angle,
                    enable_background_removal=True,
                    backend=settings.background_removal_backend,
                )
                masked_extras.append(str(masked_angle))
            except Exception:
                masked_extras.append(str(src))  # keep the raw angle if masking fails
        store.update(job_id, extra_image_paths=masked_extras)

    return store.update(
        job_id,
        status="completed",
        progress=max(float(job["progress"]), 0.15),
        message="Background removed and image prepared",
    )


def _start_thread(
    store: JobStore,
    settings: Settings,
    job_id: str,
    *,
    run_mesh: bool,
    run_cad: bool,
    run_freecad: bool = True,
) -> None:
    thread = threading.Thread(
        target=_process_job,
        args=(store, settings, job_id, run_mesh, run_cad, run_freecad),
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
    run_freecad: bool = True,
) -> dict:
    """Runs the pipeline and always returns a job dict, even on failure.

    Every caller (the synchronous /api/process route, the legacy generate-mesh
    and generate-cad routes, and the background-thread path) relies on
    inspecting result["status"] rather than catching exceptions, so any error
    here must be turned into a "failed" job update rather than propagating.
    """
    try:
        return _run_generation_job_unsafe(
            store, settings, job_id, run_mesh=run_mesh, run_cad=run_cad, run_freecad=run_freecad
        )
    except Exception as exc:
        return store.update(
            job_id,
            status="failed",
            progress=1.0,
            message="Processing failed",
            error=str(exc),
        )


def _run_generation_job_unsafe(
    store: JobStore,
    settings: Settings,
    job_id: str,
    *,
    run_mesh: bool,
    run_cad: bool,
    run_freecad: bool = True,
) -> dict:
    prepared = _prepare_image(job_id, store, settings)
    if prepared["status"] == "failed":
        return prepared
    job = store.update(job_id, status="processing", progress=0.2, message="Starting 3D reconstruction")
    masked_path = Path(job["masked_path"])
    options = job["options"]
    known_width_mm = options.get("known_width_mm")
    known_height_mm = options.get("known_height_mm")
    thickness_mm = float(options.get("thickness_mm") or settings.default_thickness_mm)
    extra_image_paths = job.get("extra_image_paths", [])

    outputs = dict(job.get("outputs", {}))
    cad_summary = job.get("cad_summary")
    preview_model_path = job.get("preview_model_path")
    mesh_stl_path: str | None = None
    mesh_obj_path: str | None = None
    cad_step_path: str | None = None
    freecad_exports: dict[str, str] = {}
    mesh_source = job.get("mesh_source")

    if run_mesh:
        job = store.update(job_id, progress=0.45, message="Generating 3D mesh")
        mesh = generate_mesh_assets(
            image_path=masked_path,
            output_dir=Path(job["job_dir"]),
            settings=settings,
            known_width_mm=known_width_mm,
            known_height_mm=known_height_mm,
            thickness_mm=thickness_mm,
            extra_image_paths=extra_image_paths,
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
        mesh_stl_path = mesh.get("stl_path")
        mesh_obj_path = mesh.get("obj_path")
        preview_model_path = mesh.get("preview_model_path") or preview_model_path
        mesh_source = mesh.get("source")

    if run_cad:
        job = store.update(job_id, progress=0.7, message="Generating CAD draft")
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
        cad_step_path = cad.get("step_path")
        preview_model_path = preview_model_path or cad.get("preview_model_path")

    if run_freecad:
        job = store.update(job_id, progress=0.85, message="Preparing FreeCAD exports")
        freecad = prepare_freecad_exports(
            mesh_stl_path=mesh_stl_path,
            mesh_obj_path=mesh_obj_path,
            cad_step_path=cad_step_path,
            output_dir=Path(job["job_dir"]),
        )
        for warning in freecad.get("warnings", []):
            store.append_warning(job_id, warning)
        if freecad.get("step_path"):
            outputs["freecad.step"] = freecad["step_path"]
            freecad_exports["step"] = freecad["step_path"]
        if freecad.get("obj_path"):
            outputs["freecad.obj"] = freecad["obj_path"]
            freecad_exports["obj"] = freecad["obj_path"]

    store.set_outputs(job_id, outputs)
    return store.update(
        job_id,
        status="completed",
        progress=1.0,
        message=_completion_message(run_mesh=run_mesh, run_cad=run_cad),
        cad_summary=cad_summary,
        preview_model_path=preview_model_path,
        mode=_result_mode(run_mesh=run_mesh, run_cad=run_cad, current_mode=job["mode"]),
        freecad=freecad_exports,
        error=None,
        mesh_source=mesh_source,
    )


def _process_job(
    store: JobStore,
    settings: Settings,
    job_id: str,
    run_mesh: bool,
    run_cad: bool,
    run_freecad: bool,
) -> None:
    _run_generation_job(
        store,
        settings,
        job_id,
        run_mesh=run_mesh,
        run_cad=run_cad,
        run_freecad=run_freecad,
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
        return "3D model and CAD exports are ready"
    if run_mesh:
        return "3D mesh generation completed"
    if run_cad:
        return "CAD generation completed"
    return "Job completed"


HIGH_FIDELITY_MESH_SOURCES = {"triposr", "luma", "csm", "tripo-api", "meshy", "wavespeed"}


def _serialize_process(job: dict, request: Request, settings: Settings) -> ProcessResponse:
    serialized = _serialize_job(job, request, settings)
    return ProcessResponse(
        job_id=serialized.job_id,
        status=serialized.status,
        progress=serialized.progress,
        message=serialized.message,
        preview_model_url=serialized.preview_model_url,
        files=serialized.files,
        cad_summary=serialized.cad_summary,
        warnings=serialized.warnings,
        freecad=serialized.freecad,
        mesh_source=serialized.mesh_source,
        mesh_is_high_fidelity=serialized.mesh_is_high_fidelity,
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
        files["cad_stl"] = _file_url(job["job_id"], "cad.stl", request, settings)
    if "mesh.stl" in outputs:
        files["stl"] = _file_url(job["job_id"], "mesh.stl", request, settings)
    if "mesh.obj" in outputs:
        files["obj"] = _file_url(job["job_id"], "mesh.obj", request, settings)
    if "mesh.glb" in outputs:
        files["glb"] = _file_url(job["job_id"], "mesh.glb", request, settings)
    if "freecad.step" in outputs:
        files["freecad_step"] = _file_url(job["job_id"], "freecad.step", request, settings)
    if "freecad.obj" in outputs:
        files["freecad_obj"] = _file_url(job["job_id"], "freecad.obj", request, settings)

    preview_model_url = None
    if job.get("preview_model_path"):
        preview_model_url = _file_url(
            job["job_id"],
            Path(job["preview_model_path"]).name,
            request,
            settings,
        )

    freecad_urls: dict[str, str] = {}
    if "freecad.step" in outputs:
        freecad_urls["step"] = _file_url(job["job_id"], "freecad.step", request, settings)
    if "freecad.obj" in outputs:
        freecad_urls["obj"] = _file_url(job["job_id"], "freecad.obj", request, settings)

    mesh_source = job.get("mesh_source")
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
        mesh_source=mesh_source,
        mesh_is_high_fidelity=mesh_source in HIGH_FIDELITY_MESH_SOURCES,
        error=job.get("error"),
        freecad=freecad_urls,
    )


def _file_url(job_id: str, filename: str, request: Request, settings: Settings) -> str:
    base_url = settings.backend_base_url.rstrip("/") if settings.backend_base_url else str(request.base_url).rstrip("/")
    return f"{base_url}{settings.api_prefix}/files/{job_id}/{filename}"
