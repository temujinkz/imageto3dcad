"""Gemini VLM -> parametric primitive description (cad3dify-style).

Gemini looks at the (background-removed) photo and returns a stack of CAD
primitives with real millimetre dimensions. ``build_step`` turns that into a
clean, editable STEP solid — the AutoCAD-ready output the user cares about most.

Returns None (with a logged warning) if the SDK isn't installed, no key is set,
or the model output can't be parsed — callers then fall back to a tessellated
STEP so there is always a real solid (never a box).
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import httpx

from ..config import Settings

_API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"

_PROMPT = """You are a CAD engineer. Look at this single product photo (background already removed) and describe the object as a STACK OF SIMPLE 3D PRIMITIVES that approximates its real shape, so it can be rebuilt in CAD.

Rules:
- The object stands upright along the +Z (vertical) axis. Stack primitives bottom to top.
- Use realistic millimetre dimensions inferred from the object type (e.g. a perfume bottle is ~60-120mm tall).
- Prefer few primitives (2-6). Each primitive is centered on the Z axis unless it is a plain box.
- offset_z_mm is the Z height of the BASE of that primitive (the bottom primitive has offset_z_mm=0).

Return ONLY JSON of this exact shape:
{
  "object_class": "<short name, e.g. perfume_bottle, mug, chair, box>",
  "symmetry": "revolve" | "none",
  "overall_height_mm": <number>,
  "primitives": [
    {"type": "cylinder", "diameter_mm": <n>, "height_mm": <n>, "offset_z_mm": <n>},
    {"type": "frustum", "bottom_diameter_mm": <n>, "top_diameter_mm": <n>, "height_mm": <n>, "offset_z_mm": <n>},
    {"type": "box", "width_mm": <n>, "depth_mm": <n>, "height_mm": <n>, "offset_z_mm": <n>},
    {"type": "sphere", "diameter_mm": <n>, "offset_z_mm": <n>}
  ]
}
Only use types: cylinder, frustum, box, sphere. No prose, no markdown fences."""


def analyze_object(image_path: str | Path, settings: Settings) -> dict | None:
    if not settings.enable_gemini_cad or not settings.gemini_api_key:
        return None
    text = _call_gemini_rest(image_path, settings)
    if text is None:
        return None
    return _validate(_parse(text))


def _call_gemini_rest(image_path: str | Path, settings: Settings) -> str | None:
    """Call the Gemini REST API directly via httpx.

    Deliberately SDK-free: the google-genai / google-generativeai SDKs pull a
    heavy dependency tree that clashed with this project's pydantic build, and
    REST needs nothing beyond httpx (already a dependency).
    """
    try:
        image_bytes = Path(image_path).read_bytes()
    except Exception:
        return None
    mime = "image/png" if str(image_path).lower().endswith(".png") else "image/jpeg"
    body = {
        "contents": [
            {
                "parts": [
                    {"text": _PROMPT},
                    {"inline_data": {"mime_type": mime, "data": base64.b64encode(image_bytes).decode("ascii")}},
                ]
            }
        ],
        "generationConfig": {"response_mime_type": "application/json", "temperature": 0.2},
    }
    url = f"{_API_ROOT}/{settings.gemini_model}:generateContent"
    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(url, params={"key": settings.gemini_api_key}, json=body)
            if response.status_code >= 400:
                return None
            payload = response.json()
            candidates = payload.get("candidates") or []
            if not candidates:
                return None
            parts = (candidates[0].get("content") or {}).get("parts") or []
            for part in parts:
                if "text" in part:
                    return part["text"]
    except Exception:
        return None
    return None


def _parse(text: str) -> dict | None:
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):  # strip accidental markdown fences
        text = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return None
    return None


def _validate(spec: dict | None) -> dict | None:
    if not isinstance(spec, dict):
        return None
    prims = spec.get("primitives")
    if not isinstance(prims, list) or not prims:
        return None
    clean: list[dict] = []
    for p in prims:
        if not isinstance(p, dict) or p.get("type") not in {"cylinder", "frustum", "box", "sphere"}:
            continue
        # clamp every dimension into a sane range so a hallucinated value can't
        # produce a degenerate or gigantic solid
        out = {"type": p["type"], "offset_z_mm": _clamp(p.get("offset_z_mm", 0), 0, 2000)}
        for key in ("diameter_mm", "bottom_diameter_mm", "top_diameter_mm", "height_mm", "width_mm", "depth_mm"):
            if key in p:
                out[key] = _clamp(p[key], 0.2, 2000)
        clean.append(out)
    if not clean:
        return None
    return {
        "object_class": str(spec.get("object_class", "object"))[:64],
        "symmetry": spec.get("symmetry", "none"),
        "overall_height_mm": _clamp(spec.get("overall_height_mm", 0), 0, 2000),
        "primitives": clean,
    }


def _clamp(value, low: float, high: float) -> float:
    try:
        return float(min(max(float(value), low), high))
    except Exception:
        return low
