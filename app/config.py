from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_BACKEND_ROOT / ".env")
load_dotenv(_BACKEND_ROOT / ".env.local", override=True)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _env_list(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    project_name: str
    api_prefix: str
    storage_root: Path
    backend_base_url: str | None
    cors_origins: list[str]
    image_to_3d_provider: str
    use_triposr: bool
    triposr_run_py: str | None
    triposr_python_bin: str
    triposr_extra_args: str
    triposr_timeout_seconds: int
    default_thickness_mm: float
    default_width_mm: float
    default_height_mm: float
    enable_rembg: bool
    background_removal_backend: str
    opencv_timeout_seconds: int
    luma_api_key: str | None
    luma_api_base: str
    csm_api_key: str | None
    csm_api_base: str
    tripo_api_key: str | None
    tripo_api_base: str
    meshy_api_key: str | None
    meshy_api_base: str
    meshy_ai_model: str
    meshy_target_polycount: int
    wavespeed_api_key: str | None
    wavespeed_api_base: str
    wavespeed_model: str
    wavespeed_multiview_model: str
    fal_api_key: str | None
    fal_model: str
    gemini_api_key: str | None
    gemini_model: str
    enable_gemini_cad: bool
    reconstruction_timeout_seconds: int
    max_upload_images: int
    max_video_frames: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    backend_root = Path(__file__).resolve().parents[1]
    storage_root = Path(
        os.getenv("STORAGE_DIR", str(backend_root / "storage" / "jobs"))
    ).expanduser().resolve()
    return Settings(
        project_name="Photo2CAD Backend",
        api_prefix="/api",
        storage_root=storage_root,
        backend_base_url=os.getenv("BACKEND_BASE_URL"),
        cors_origins=_env_list("CORS_ORIGINS", ["*"]),
        # "auto" = first available provider wins (cloud first, then the local
        # offline silhouette engine). Never falls back to a plain box.
        image_to_3d_provider=os.getenv("IMAGE_TO_3D_PROVIDER", "auto").strip().lower(),
        use_triposr=_env_bool("USE_TRIPOSR", True),
        triposr_run_py=os.getenv("PHOTO2CAD_TRIPOSR_RUN_PY"),
        triposr_python_bin=os.getenv("PHOTO2CAD_TRIPOSR_PYTHON_BIN", "python"),
        triposr_extra_args=os.getenv("PHOTO2CAD_TRIPOSR_EXTRA_ARGS", ""),
        triposr_timeout_seconds=int(os.getenv("PHOTO2CAD_TRIPOSR_TIMEOUT_SECONDS", "420")),
        default_thickness_mm=float(os.getenv("DEFAULT_THICKNESS_MM", "5")),
        default_width_mm=float(os.getenv("DEFAULT_WIDTH_MM", "80")),
        default_height_mm=float(os.getenv("DEFAULT_HEIGHT_MM", "50")),
        enable_rembg=_env_bool("ENABLE_REMBG", True),
        background_removal_backend=os.getenv("BACKGROUND_REMOVAL_BACKEND", "rembg").strip().lower(),
        opencv_timeout_seconds=int(os.getenv("PHOTO2CAD_OPENCV_TIMEOUT_SECONDS", "5")),
        luma_api_key=os.getenv("LUMA_API_KEY"),
        luma_api_base=os.getenv("LUMA_API_BASE", "https://api.lumalabs.ai/dream-machine/v1"),
        csm_api_key=os.getenv("CSM_API_KEY"),
        csm_api_base=os.getenv("CSM_API_BASE", "https://api.csm.ai/v1"),
        tripo_api_key=os.getenv("TRIPO_API_KEY"),
        tripo_api_base=os.getenv("TRIPO_API_BASE", "https://api.tripo3d.ai/v2"),
        meshy_api_key=os.getenv("MESHY_API_KEY"),
        meshy_api_base=os.getenv("MESHY_API_BASE", "https://api.meshy.ai/openapi/v1"),
        meshy_ai_model=os.getenv("MESHY_AI_MODEL", "latest"),
        meshy_target_polycount=int(os.getenv("MESHY_TARGET_POLYCOUNT", "300000")),
        wavespeed_api_key=os.getenv("WAVESPEED_API_KEY"),
        wavespeed_api_base=os.getenv("WAVESPEED_API_BASE", "https://api.wavespeed.ai/api/v3"),
        # Hunyuan3D on WaveSpeed. Override with e.g.
        # "wavespeed-ai/hunyuan-3d-v3.1/image-to-3d-rapid" for the faster/cheaper model.
        wavespeed_model=os.getenv("WAVESPEED_MODEL", "wavespeed-ai/hunyuan3d-v3/image-to-3d"),
        # Multi-view model used automatically when several angle photos are
        # uploaded: fuses named front/back/left views into one mesh.
        wavespeed_multiview_model=os.getenv(
            "WAVESPEED_MULTIVIEW_MODEL", "wavespeed-ai/hunyuan3d-v2-multi-view"
        ),
        fal_api_key=os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY"),
        # fal.ai hosted image-to-3D model. Hunyuan3D-2 gives strong geometry;
        # swap for "fal-ai/trellis" or "fal-ai/triposr" via env if preferred.
        fal_model=os.getenv("FAL_MODEL", "fal-ai/hunyuan3d/v2"),
        gemini_api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        enable_gemini_cad=_env_bool("ENABLE_GEMINI_CAD", True),
        reconstruction_timeout_seconds=int(os.getenv("RECONSTRUCTION_TIMEOUT_SECONDS", "600")),
        max_upload_images=int(os.getenv("MAX_UPLOAD_IMAGES", "20")),
        max_video_frames=int(os.getenv("MAX_VIDEO_FRAMES", "12")),
    )
