from __future__ import annotations

from pathlib import Path

from PIL import Image

SUPPORTED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
    ".gif",
    ".heic",
    ".heif",
    ".avif",
}

VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".m4v", ".avi", ".mkv"}


def _register_heif() -> None:
    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
    except Exception:
        pass


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def is_video_file(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def convert_to_png(source: Path, destination: Path) -> None:
    """Convert any supported image format to PNG with alpha preserved."""
    _register_heif()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(".tmp")
    with Image.open(source) as image:
        image.convert("RGBA").save(temp_path, format="PNG")
    temp_path.replace(destination)


def save_upload_as_png(upload_path: Path, destination: Path) -> list[str]:
    """Save an uploaded file as PNG, handling HEIC and other formats."""
    warnings: list[str] = []
    suffix = upload_path.suffix.lower()

    if suffix in {".png"}:
        upload_path.replace(destination)
        return warnings

    try:
        convert_to_png(upload_path, destination)
        upload_path.unlink(missing_ok=True)
    except Exception as exc:
        warnings.append(f"Format conversion failed ({suffix or 'unknown'}): {exc}")
        upload_path.replace(destination)
    return warnings
