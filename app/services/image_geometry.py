from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from ..config import Settings


def analyze_image_geometry(
    image_path: str | Path,
    settings: Settings,
    known_width_mm: float | None = None,
    known_height_mm: float | None = None,
    thickness_mm: float | None = None,
) -> dict:
    image_path = Path(image_path)
    geometry = _run_opencv_worker(image_path, settings)
    warnings: list[str] = []

    if not geometry.get("ok"):
        geometry = _basic_geometry(image_path)
        warnings.extend(geometry.pop("warnings", []))

    bbox = geometry["bounding_box"]
    width_px = max(float(bbox["width"]), 1.0)
    height_px = max(float(bbox["height"]), 1.0)

    if known_width_mm:
        pixels_to_mm = known_width_mm / width_px
    elif known_height_mm:
        pixels_to_mm = known_height_mm / height_px
    else:
        pixels_to_mm = settings.default_width_mm / width_px

    width_mm = round(width_px * pixels_to_mm, 2)
    height_mm = round(height_px * pixels_to_mm, 2)
    thickness_value = round(float(thickness_mm or settings.default_thickness_mm), 2)

    geometry["warnings"] = warnings + geometry.get("warnings", [])
    geometry["pixels_to_mm"] = pixels_to_mm
    geometry["estimated_dimensions_mm"] = {
        "width": width_mm,
        "height": height_mm,
        "thickness": thickness_value,
    }
    geometry["detected_holes"] = len(geometry.get("holes", []))
    geometry["detected_outline"] = bool(geometry.get("outline_points"))
    return geometry


def _run_opencv_worker(image_path: Path, settings: Settings) -> dict:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        str(image_path),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=settings.opencv_timeout_seconds,
            check=False,
        )
    except Exception as exc:
        return {"ok": False, "warnings": [f"OpenCV worker failed: {exc}"]}
    if completed.returncode != 0 or not completed.stdout.strip():
        return {"ok": False, "warnings": ["OpenCV worker returned no geometry."]}
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "warnings": ["OpenCV worker returned invalid JSON."]}


def _basic_geometry(image_path: Path) -> dict:
    image = Image.open(image_path).convert("RGBA")
    array = np.array(image)
    alpha = array[:, :, 3]
    if alpha.max() > 8:
        mask = alpha > 16
    else:
        mask = np.mean(array[:, :, :3], axis=2) < 245
    ys, xs = np.where(mask)
    if not len(xs):
        return {
            "ok": True,
            "outline_points": [],
            "holes": [],
            "bounding_box": {"x": 0, "y": 0, "width": settings_default_width(), "height": settings_default_height()},
            "backend": "default-plate",
            "warnings": [
                "No clear object contour detected; using default fallback plate dimensions."
            ],
        }
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    outline_points = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
    return {
        "ok": True,
        "outline_points": outline_points,
        "holes": [],
        "bounding_box": {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0},
        "backend": "basic-bbox",
        "warnings": ["OpenCV unavailable, using the largest bounding box approximation."],
    }


def settings_default_width() -> int:
    return 80


def settings_default_height() -> int:
    return 50


def _worker(image_path: Path) -> int:
    import cv2  # type: ignore

    image = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if image is None:
        print(json.dumps({"ok": False, "error": "Image could not be loaded"}))
        return 0

    if len(image.shape) == 3 and image.shape[2] == 4:
        alpha = image[:, :, 3]
        mask = np.where(alpha > 16, 255, 0).astype(np.uint8)
    elif len(image.shape) == 3:
        grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(grayscale, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:
        grayscale = image
        _, mask = cv2.threshold(grayscale, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        print(json.dumps({"ok": False, "error": "No contours found"}))
        return 0

    hierarchy_data = hierarchy[0] if hierarchy is not None else []
    outer_candidates = [
        index
        for index, _ in enumerate(contours)
        if not len(hierarchy_data) or hierarchy_data[index][3] == -1
    ]
    outer_index = max(outer_candidates, key=lambda idx: cv2.contourArea(contours[idx]))
    contour = contours[outer_index]
    perimeter = cv2.arcLength(contour, True)
    approximated = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
    x, y, w, h = cv2.boundingRect(contour)

    holes: list[dict] = []
    if len(hierarchy_data):
        child_index = hierarchy_data[outer_index][2]
        while child_index != -1:
            hole_contour = contours[child_index]
            area = cv2.contourArea(hole_contour)
            if area > 20:
                (cx, cy), radius = cv2.minEnclosingCircle(hole_contour)
                holes.append(
                    {
                        "center_px": [float(cx), float(cy)],
                        "radius_px": float(radius),
                    }
                )
            child_index = hierarchy_data[child_index][0]

    points = [[int(point[0][0]), int(point[0][1])] for point in approximated]
    print(
        json.dumps(
            {
                "ok": True,
                "outline_points": points,
                "holes": holes,
                "bounding_box": {"x": int(x), "y": int(y), "width": int(w), "height": int(h)},
                "backend": "opencv",
            }
        )
    )
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        raise SystemExit(_worker(Path(sys.argv[2])))
