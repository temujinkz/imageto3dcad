"""Provider registry + orchestrator.

``generate`` resolves an ordered list of providers (cloud first, then the local
offline silhouette engine) and returns the first one that yields a mesh. There
is intentionally no ``.box()`` fallback anywhere: ``silhouette`` always runs, so
a real 3D shape is always produced.
"""

from __future__ import annotations

from pathlib import Path

from ...config import Settings
from .base import GeneratedMesh, ImageTo3DProvider
from .csm import CsmProvider
from .fal import FalProvider
from .luma import LumaProvider
from .meshy import MeshyProvider
from .mock import MockProvider
from .silhouette import SilhouetteProvider
from .tripo import TripoProvider
from .triposr import TriposrProvider
from .wavespeed import WaveSpeedProvider

# Registration order also defines the "auto" cloud preference order.
_REGISTRY: dict[str, ImageTo3DProvider] = {
    p.name: p
    for p in (
        WaveSpeedProvider(),
        MeshyProvider(),
        TripoProvider(),
        FalProvider(),
        LumaProvider(),
        CsmProvider(),
        TriposrProvider(),
        SilhouetteProvider(),
        MockProvider(),
    )
}

# Cloud/local order tried when IMAGE_TO_3D_PROVIDER=auto. Silhouette is last and
# always available, so the chain never dead-ends.
_AUTO_ORDER = ["wavespeed-hunyuan3d", "meshy", "tripo-api", "fal-hunyuan3d", "luma", "csm", "triposr", "silhouette"]


def resolve_order(settings: Settings) -> list[str]:
    choice = (settings.image_to_3d_provider or "auto").strip().lower()
    if choice in ("", "auto"):
        return _AUTO_ORDER
    # explicit provider first, then always fall back to the offline engine
    if choice == "silhouette":
        return ["silhouette"]
    if choice == "mock":
        return ["mock"]
    return [choice, "silhouette"]


def generate(image_path: str, output_dir: str, settings: Settings) -> GeneratedMesh | None:
    """Try providers in order; return the first real mesh. Collects warnings."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    for name in resolve_order(settings):
        provider = _REGISTRY.get(name)
        if provider is None:
            continue
        if not provider.available(settings):
            continue
        result = provider.generate(image_path, str(out / name), settings)
        if result is None:
            continue
        if result.mesh_path and Path(result.mesh_path).exists():
            result.warnings = warnings + result.warnings
            return result
        # provider ran but produced nothing usable -> record why, try next
        warnings.extend(result.warnings or [f"{name} produced no mesh."])
    return GeneratedMesh("none", "", False, warnings + ["No provider produced a mesh."])
