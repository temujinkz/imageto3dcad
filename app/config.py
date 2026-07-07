from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


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
    use_triposr: bool
    triposr_run_py: str | None
    triposr_python_bin: str
    triposr_extra_args: str
    triposr_timeout_seconds: int
    default_thickness_mm: float
    default_width_mm: float
    default_height_mm: float
    enable_rembg: bool
    opencv_timeout_seconds: int


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
        cors_origins=_env_list(
            "CORS_ORIGINS",
            ["http://localhost:3000", "http://127.0.0.1:3000"],
        ),
        use_triposr=_env_bool("USE_TRIPOSR", True),
        triposr_run_py=os.getenv("PHOTO2CAD_TRIPOSR_RUN_PY"),
        triposr_python_bin=os.getenv("PHOTO2CAD_TRIPOSR_PYTHON_BIN", "python"),
        triposr_extra_args=os.getenv("PHOTO2CAD_TRIPOSR_EXTRA_ARGS", ""),
        triposr_timeout_seconds=int(os.getenv("PHOTO2CAD_TRIPOSR_TIMEOUT_SECONDS", "420")),
        default_thickness_mm=float(os.getenv("DEFAULT_THICKNESS_MM", "5")),
        default_width_mm=float(os.getenv("DEFAULT_WIDTH_MM", "80")),
        default_height_mm=float(os.getenv("DEFAULT_HEIGHT_MM", "50")),
        enable_rembg=_env_bool("ENABLE_REMBG", True),
        opencv_timeout_seconds=int(os.getenv("PHOTO2CAD_OPENCV_TIMEOUT_SECONDS", "5")),
    )
