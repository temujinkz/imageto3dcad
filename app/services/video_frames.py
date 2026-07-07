from __future__ import annotations

from pathlib import Path


def extract_key_frames(
    video_path: Path,
    output_dir: Path,
    *,
    max_frames: int = 12,
    min_interval_seconds: float = 0.5,
) -> tuple[list[Path], list[str]]:
    """Extract evenly spaced frames from a video for multi-view reconstruction."""
    warnings: list[str] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        import cv2
    except Exception as exc:
        return [], [f"OpenCV unavailable for video processing: {exc}"]

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return [], ["Could not open video file."]

    fps = capture.get(cv2.CAP_PROP_FPS) or 24.0
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frame_step = max(int(fps * min_interval_seconds), 1)
    if total_frames > 0:
        estimated = max(1, total_frames // frame_step)
        if estimated > max_frames:
            frame_step = max(total_frames // max_frames, 1)

    frames: list[Path] = []
    index = 0
    saved = 0

    while saved < max_frames:
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if not ok:
            break
        frame_path = output_dir / f"frame_{saved:03d}.png"
        if cv2.imwrite(str(frame_path), frame):
            frames.append(frame_path)
            saved += 1
        index += frame_step

    capture.release()
    if not frames:
        return [], ["No frames could be extracted from the video."]
    return frames, warnings
