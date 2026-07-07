from __future__ import annotations

import importlib.util

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .jobs import JobStore
from .routers import files, generate_cad, generate_mesh, upload
from .services.image_convert import SUPPORTED_EXTENSIONS, VIDEO_EXTENSIONS


settings = get_settings()
store = JobStore(settings)

app = FastAPI(title=settings.project_name, version="0.2.0")

if "*" in settings.cors_origins:
    # Wildcard origins are incompatible with allow_credentials=True per the CORS
    # spec; the frontend never sends cookies/credentials, so this is safe.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.include_router(upload.build_router(store, settings), prefix=settings.api_prefix)
app.include_router(generate_mesh.build_router(store, settings), prefix=settings.api_prefix)
app.include_router(generate_cad.build_router(store, settings), prefix=settings.api_prefix)
app.include_router(files.build_router(store, settings), prefix=settings.api_prefix)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get(f"{settings.api_prefix}/capabilities")
def capabilities() -> dict:
    return {
        "triposr_enabled": settings.use_triposr,
        "triposr_configured": bool(settings.triposr_run_py),
        "rembg_available": importlib.util.find_spec("rembg") is not None,
        "birefnet_available": importlib.util.find_spec("transformers") is not None
        and importlib.util.find_spec("torch") is not None,
        "background_removal_backend": settings.background_removal_backend,
        "cadquery_available": importlib.util.find_spec("cadquery") is not None,
        "trimesh_available": importlib.util.find_spec("trimesh") is not None,
        "opencv_available": importlib.util.find_spec("cv2") is not None,
        "luma_configured": bool(settings.luma_api_key),
        "csm_configured": bool(settings.csm_api_key),
        "tripo_api_configured": bool(settings.tripo_api_key),
        "meshy_configured": bool(settings.meshy_api_key),
        "supported_image_formats": sorted(SUPPORTED_EXTENSIONS),
        "supported_video_formats": sorted(VIDEO_EXTENSIONS),
    }
