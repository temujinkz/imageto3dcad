"""Image-to-3D provider abstraction.

Every provider takes a single prepared image and returns a *raw* mesh file
(GLB/OBJ/STL/PLY) plus metadata. Downstream, ``mesh_postprocess`` cleans and
re-exports it into the canonical mesh.glb / mesh.obj / mesh.stl trio.

The whole point of this layer is that no code path ever falls back to a plain
``.box()`` again: cloud providers run reconstruction on their own GPUs, and the
local ``silhouette`` provider is an always-available offline safety net that
still produces a real, rounded 3D shape.
"""

from __future__ import annotations

import base64
import io
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

import httpx
from PIL import Image

from ...config import Settings

MESH_SUFFIXES = {".glb", ".gltf", ".obj", ".stl", ".ply"}

# Blips that say "try again", not "this request is wrong": DNS hiccups, refused
# or reset connections, read timeouts, and raw socket errors such as macOS
# EADDRNOTAVAIL ([Errno 49] Can't assign requested address). Without a retry a
# single one of these silently demotes the whole job to the local silhouette
# fallback, which loses the cloud provider's colour/texture.
TRANSIENT_NETWORK_ERRORS = (httpx.TransportError, OSError)


def post_with_retry(
    client: httpx.Client,
    url: str,
    *,
    headers: dict,
    json: dict,
    attempts: int = 3,
    backoff_seconds: float = 2.0,
) -> httpx.Response:
    """POST, retrying only transient transport failures with linear backoff.

    HTTP error *responses* (4xx/5xx) are returned as-is for the caller to judge;
    only connection-level failures are retried.
    """
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return client.post(url, headers=headers, json=json)
        except TRANSIENT_NETWORK_ERRORS as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(backoff_seconds * (attempt + 1))
    raise last_error  # type: ignore[misc]


def resized_data_uri(path: Path, max_dimension: int = 1536) -> str:
    """Base64 data URI of an image, downscaled so its longest side is at most
    ``max_dimension`` px.

    Full-resolution phone photos (10 MB+) balloon once base64-encoded, which is
    slow to upload and, on some SSL stacks (e.g. macOS LibreSSL), corrupts the
    request body mid-flight ("bad record mac"). 1536 px keeps ample detail for
    these reconstruction models while keeping the payload small and reliable.
    """
    with Image.open(path) as image:
        image = image.convert("RGBA")
        if max(image.size) > max_dimension:
            scale = max_dimension / max(image.size)
            image = image.resize(
                (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                Image.LANCZOS,
            )
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode('ascii')}"


@dataclass
class GeneratedMesh:
    """A raw mesh produced by a provider, before post-processing."""

    source: str
    mesh_path: str
    is_high_fidelity: bool
    warnings: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


@runtime_checkable
class ImageTo3DProvider(Protocol):
    name: str

    def available(self, settings: Settings) -> bool:
        ...

    def generate(self, image_path: str, output_dir: str, settings: Settings) -> GeneratedMesh | None:
        ...


def download_mesh_file(url: str, output_dir: Path, timeout: int = 180) -> Path | None:
    """Download a remote mesh to ``output_dir/raw_mesh.<ext>``.

    The suffix is inferred from the URL so trimesh can later load it by format.
    Returns None on any network/HTTP error (callers treat that as "provider
    failed" and move to the next provider).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = _infer_suffix(url)
    destination = output_dir / f"raw_mesh{suffix}"
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            destination.write_bytes(response.content)
    except Exception:
        return None
    if destination.stat().st_size == 0:
        return None
    return destination


def _infer_suffix(url: str) -> str:
    lowered = url.split("?")[0].lower()
    for suffix in (".glb", ".gltf", ".obj", ".stl", ".ply", ".fbx"):
        if lowered.endswith(suffix):
            return suffix
    return ".glb"
