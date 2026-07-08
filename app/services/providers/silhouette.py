"""Local, offline, zero-network image-to-3D provider.

This is the safety net that makes "perfume -> box" impossible even with no API
keys and no GPU. It turns the (already background-removed) silhouette into a
genuine 3D solid:

* **revolve** — if the silhouette is left/right symmetric and mostly solid
  (bottle, cup, vase, can, glass), it is treated as a surface of revolution:
  radius = half the silhouette width at each height, lathed 360° about the
  vertical axis. A perfume photo becomes a real rounded bottle.
* **inflate** — otherwise the mask is "puffed" into a rounded pillow using a
  distance transform as a thickness field (marching cubes), so arbitrary shapes
  still get believable depth instead of a flat slab.

Only depends on numpy / scipy / scikit-image / trimesh — all already installed.
Output is stylized, not photoreal; it reports ``is_high_fidelity=False`` so the
UI shows an honest "rough estimate" badge.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh
from PIL import Image
from scipy import ndimage
from skimage import measure

from ...config import Settings
from .base import GeneratedMesh

_TARGET_WIDTH = 160  # mask working resolution (px); keeps meshes light + fast


class SilhouetteProvider:
    name = "silhouette"

    def available(self, settings: Settings) -> bool:  # always runnable
        return True

    def generate(self, image_path: str, output_dir: str, settings: Settings) -> GeneratedMesh | None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        mask = _load_mask(Path(image_path))
        if mask is None or mask.sum() < 20:
            return GeneratedMesh(self.name, "", False, ["Silhouette engine found no subject in the image."])

        mode = _choose_mode(mask)
        try:
            if mode == "revolve":
                mesh = _revolve(mask)
            else:
                mesh = _inflate(mask)
        except Exception as exc:
            # Never crash the pipeline; fall back to the inflate path, then bail.
            try:
                mesh = _inflate(mask)
                mode = "inflate"
            except Exception:
                return GeneratedMesh(self.name, "", False, [f"Silhouette engine failed: {exc}"])

        mesh = _finish(mesh)
        raw = out / "raw_mesh.glb"
        mesh.export(raw)
        return GeneratedMesh(
            source=self.name,
            mesh_path=str(raw),
            is_high_fidelity=False,
            warnings=[
                "Generated locally from the photo's silhouette (no 3D API configured). "
                f"Mode: {mode}. This is a stylized 3D estimate, not a photoreal reconstruction."
            ],
            meta={"mode": mode, "faces": int(len(mesh.faces))},
        )


# --------------------------------------------------------------------------- #
# mask handling                                                               #
# --------------------------------------------------------------------------- #
def _load_mask(image_path: Path) -> np.ndarray | None:
    image = Image.open(image_path).convert("RGBA")
    scale = _TARGET_WIDTH / max(image.width, 1)
    if scale < 1.0:
        image = image.resize((max(int(image.width * scale), 1), max(int(image.height * scale), 1)))
    array = np.array(image)
    alpha = array[:, :, 3]
    if alpha.max() > 8:
        mask = alpha > 32
    else:  # opaque image with no alpha channel -> threshold on brightness
        mask = np.mean(array[:, :, :3], axis=2) < 245
    if not mask.any():
        return None
    # keep only the largest connected component (drops stray mask speckles)
    labels, count = ndimage.label(mask)
    if count > 1:
        largest = 1 + int(np.argmax(ndimage.sum(mask, labels, range(1, count + 1))))
        mask = labels == largest
    return _crop(mask)


def _crop(mask: np.ndarray) -> np.ndarray:
    ys, xs = np.where(mask)
    return mask[ys.min(): ys.max() + 1, xs.min(): xs.max() + 1]


def _choose_mode(mask: np.ndarray) -> str:
    """Pick revolve for surface-of-revolution-like silhouettes, else inflate."""
    h, w = mask.shape
    aspect = h / max(w, 1)
    fill_ratio = float(mask.sum()) / float(h * w)

    # horizontal symmetry: how well the left half mirrors the right half
    mirrored = mask[:, ::-1]
    overlap = np.logical_and(mask, mirrored).sum()
    union = np.logical_or(mask, mirrored).sum()
    symmetry = float(overlap) / float(max(union, 1))

    # a solid of revolution is symmetric, fairly "filled" (few concavities),
    # and not extremely wide/flat
    if symmetry > 0.86 and fill_ratio > 0.55 and 0.5 <= aspect <= 5.0:
        return "revolve"
    return "inflate"


# --------------------------------------------------------------------------- #
# revolve (solid of revolution)                                               #
# --------------------------------------------------------------------------- #
def _revolve(mask: np.ndarray) -> trimesh.Trimesh:
    h, w = mask.shape
    # sample ~120 rows bottom->top; radius = half the run of foreground per row
    rows = np.linspace(0, h - 1, num=min(h, 120)).astype(int)
    unit = 2.0 / max(w, 1)  # normalize the widest possible radius to ~1.0
    profile: list[list[float]] = []
    for r in rows:
        xs = np.where(mask[r])[0]
        radius = ((xs.max() - xs.min()) / 2.0) * unit if len(xs) else 0.0
        # y: flip so the image top becomes +y; scale to normalized units
        y = (h - 1 - r) * unit
        profile.append([max(radius, 1e-4), y])

    profile = _smooth_profile(profile)
    # close the outline on the axis at both ends so the solid caps top & bottom
    y_bottom = profile[0][1]
    y_top = profile[-1][1]
    linestring = np.array([[0.0, y_bottom]] + profile + [[0.0, y_top]])
    mesh = trimesh.creation.revolve(linestring, sections=64)
    return mesh


def _smooth_profile(profile: list[list[float]]) -> list[list[float]]:
    radii = np.array([p[0] for p in profile], dtype=float)
    if len(radii) >= 5:  # light moving-average so the lathe isn't jagged
        kernel = np.ones(3) / 3.0
        radii = np.convolve(radii, kernel, mode="same")
    return [[float(radii[i]), float(profile[i][1])] for i in range(len(profile))]


# --------------------------------------------------------------------------- #
# inflate (distance-transform pillow)                                         #
# --------------------------------------------------------------------------- #
def _inflate(mask: np.ndarray, depth_voxels: int = 48, inflate: float = 1.15) -> trimesh.Trimesh:
    dist = ndimage.distance_transform_edt(mask)
    if dist.max() <= 0:
        raise ValueError("empty mask")
    height = (dist / dist.max()) ** 0.65  # 0..1, rounded falloff toward edges
    half = (height * (depth_voxels / 2.0) * inflate).astype(int)

    h, w = mask.shape
    depth = depth_voxels + 2
    volume = np.zeros((h, w, depth), dtype=np.float32)
    center = depth // 2
    ys, xs = np.where(mask)
    for y, x in zip(ys, xs):
        t = int(half[y, x])
        if t <= 0:
            t = 1
        volume[y, x, center - t: center + t + 1] = 1.0

    verts, faces, _normals, _values = measure.marching_cubes(volume, level=0.5)
    unit = 2.0 / max(w, 1)
    # (row, col, z) -> (x, y, z) with image top mapped to +y
    xyz = np.column_stack([
        verts[:, 1] * unit,
        (h - 1 - verts[:, 0]) * unit,
        (verts[:, 2] - center) * unit,
    ])
    mesh = trimesh.Trimesh(vertices=xyz, faces=faces, process=True)
    if hasattr(trimesh, "smoothing"):
        try:
            trimesh.smoothing.filter_humphrey(mesh, iterations=6)
        except Exception:
            pass
    return mesh


def _finish(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    mesh.fix_normals()
    return mesh
