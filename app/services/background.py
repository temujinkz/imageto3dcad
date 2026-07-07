from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image


@lru_cache(maxsize=1)
def _load_rembg():
    from rembg import remove  # type: ignore

    return remove


def create_masked_image(
    input_path: Path,
    output_path: Path,
    enable_background_removal: bool,
) -> list[str]:
    warnings: list[str] = []
    image = Image.open(input_path).convert("RGBA")
    if enable_background_removal:
        try:
            remove = _load_rembg()
            image = remove(image)
        except Exception as exc:  # pragma: no cover - optional runtime
            warnings.append(f"Background removal skipped: {exc}")
    image.save(output_path)
    return warnings
