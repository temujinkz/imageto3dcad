from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image


@lru_cache(maxsize=1)
def _load_rembg_session():
    from rembg import new_session

    try:
        # isnet-general-use gives materially cleaner edges than the default
        # u2net model on non-human subjects, which matters because every
        # stray background pixel becomes noise geometry in the 3D reconstruction.
        return new_session("isnet-general-use")
    except Exception:
        return new_session("u2net")


@lru_cache(maxsize=1)
def _load_birefnet():
    import torch
    from transformers import AutoModelForImageSegmentation

    model = AutoModelForImageSegmentation.from_pretrained("ZhengPeng7/BiRefNet", trust_remote_code=True)
    model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return model.to(device), device


def create_masked_image(
    input_path: Path,
    output_path: Path,
    enable_background_removal: bool,
    backend: str = "rembg",
) -> list[str]:
    warnings: list[str] = []
    original = Image.open(input_path).convert("RGBA")
    image = original

    if enable_background_removal:
        remover = _remove_background_birefnet if backend == "birefnet" else _remove_background_rembg
        try:
            image = remover(image)
        except Exception as exc:  # pragma: no cover - optional runtime
            if backend == "birefnet":
                warnings.append(f"birefnet background removal failed, falling back to rembg: {exc}")
                try:
                    image = _remove_background_rembg(image)
                except Exception as fallback_exc:
                    warnings.append(f"Background removal skipped: {fallback_exc}")
                    image = original
            else:
                warnings.append(f"Background removal skipped: {exc}")
                image = original

        sanity_warning = _mask_sanity_warning(image)
        if sanity_warning:
            # The model erased the subject along with the background (common
            # on transparent/glass/reflective objects, where there's no clean
            # edge for it to find) or kept almost the whole frame. Either way
            # the removal did more harm than good, so use the original photo
            # instead of handing the reconstruction an empty/unmasked image.
            warnings.append(f"{sanity_warning} Using the original photo without background removal instead.")
            image = original

    image = isolate_on_padded_canvas(image)
    image.save(output_path)
    return warnings


def _remove_background_rembg(image: Image.Image) -> Image.Image:
    from rembg import remove

    return remove(
        image,
        session=_load_rembg_session(),
        alpha_matting=True,
        alpha_matting_foreground_threshold=240,
        alpha_matting_background_threshold=10,
        alpha_matting_erode_size=8,
    )


def _remove_background_birefnet(image: Image.Image) -> Image.Image:
    """Higher-fidelity background removal via BiRefNet, for subjects where rembg
    leaves visible edge noise (fine detail, thin structures, low contrast).
    Requires the optional `torch` + `transformers` dependencies; see README."""
    import torch
    from torchvision import transforms

    model, device = _load_birefnet()
    rgb = image.convert("RGB")
    preprocess = transforms.Compose(
        [
            transforms.Resize((1024, 1024)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )
    tensor = preprocess(rgb).unsqueeze(0).to(device)
    with torch.no_grad():
        result = model(tensor)[-1].sigmoid().cpu()[0].squeeze()
    mask = transforms.ToPILImage()(result).resize(rgb.size)
    output = rgb.convert("RGBA")
    output.putalpha(mask)
    return output


def _mask_sanity_warning(image: Image.Image) -> str | None:
    """Detects likely-failed segmentation: if the foreground mask covers
    almost the entire frame or almost none of it, background removal didn't
    find a sensible subject boundary (common on transparent, glass, or
    reflective objects where there's no solid edge to detect)."""
    alpha = np.array(image.split()[-1])
    foreground_ratio = float((alpha > 8).mean())
    if foreground_ratio > 0.98:
        return "Background removal may have failed: the mask covers almost the entire frame."
    if foreground_ratio < 0.02:
        return "Background removal may have failed: little to no foreground subject was detected."
    return None


def isolate_on_padded_canvas(image: Image.Image, padding_ratio: float = 0.12) -> Image.Image:
    """Crop to the subject's alpha bounding box and center it on a padded square canvas.

    Image-to-3D reconstruction is sensitive to framing: an off-center or
    tightly-cropped subject biases the model's scale/pose estimate and shows
    up as distorted or skewed geometry. A centered subject with uniform
    padding on a transparent background is the framing every major
    image-to-3D API (TripoSR, Meshy, CSM, Luma) is tuned to expect.
    """
    alpha = np.array(image.split()[-1])
    mask = alpha > 8
    if not mask.any():
        return image

    ys, xs = np.where(mask)
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    subject = image.crop((x0, y0, x1, y1))

    subject_w, subject_h = subject.size
    longest_side = max(subject_w, subject_h)
    canvas_size = max(int(round(longest_side * (1 + 2 * padding_ratio))), 1)
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    offset = ((canvas_size - subject_w) // 2, (canvas_size - subject_h) // 2)
    canvas.paste(subject, offset, subject)
    return canvas
