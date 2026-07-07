from __future__ import annotations

import importlib.util

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .jobs import JobStore
from .routers import files, generate_cad, generate_mesh, upload


settings = get_settings()
store = JobStore(settings)

app = FastAPI(title=settings.project_name, version="0.2.0")
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
        "cadquery_available": importlib.util.find_spec("cadquery") is not None,
        "trimesh_available": importlib.util.find_spec("trimesh") is not None,
        "opencv_available": importlib.util.find_spec("cv2") is not None,
    }
