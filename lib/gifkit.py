"""GIF creation and inspection via ffmpeg and PIL.

Core features:
- video-to-GIF conversion (with optional looping)
- GIF-to-WebP/MP4 re-encode
- GIF duration calculation (encoded frame durations, not wall-clock)
- GIF integrity check (decodability + frame count + dimensions)
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image


# ---------------------------------------------------------------------------
# ffmpeg helpers
# ---------------------------------------------------------------------------

def _run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit {result.returncode}):\n{result.stderr[-2000:]}"
        )


def video_to_gif(
    input_path: Path,
    output_path: Path,
    *,
    width: int = 480,
    fps: int = 10,
    loop: int = 0,
    duration: float | None = None,
    palette: bool = True,
) -> Path:
    """Convert a video file to a GIF using ffmpeg.

    :param input_path: source video (mp4, webm, mov, ...)
    :param output_path: destination .gif
    :param width: target width (height auto-scaled, even)
    :param fps: target frame rate
    :param loop: number of loops to force into the GIF (0 = use source)
    :param duration: optional max duration in seconds (``-t``)
    :param palette: if True, use a 2-pass palette for better quality
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    filters: list[str] = []
    if loop > 0:
        filters.append(f"loop=loop={loop}:size=150000:start=0")
    filters.append(f"scale={width}:-2:flags=lanczos")
    filters.append(f"fps={fps}")

    with tempfile.TemporaryDirectory(prefix="giftool_") as tmp:
        tmp_path = Path(tmp)
        palette_path = tmp_path / "palette.png"

        if palette:
            # pass 1: generate palette
            _run_ffmpeg([
                "ffmpeg", "-y", "-i", str(input_path),
                "-vf", ",".join(filters + [
                    "palettegen=stats_mode=diff"]),
                str(palette_path),
            ])
            # pass 2: apply palette
            palette_filter = f"split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
            vf = ",".join(filters + [palette_filter])
        else:
            vf = ",".join(filters)

        cmd = ["ffmpeg", "-y", "-i", str(input_path), "-vf", vf]
        if duration:
            cmd += ["-t", str(duration)]
        cmd.append(str(output_path))
        _run_ffmpeg(cmd)

    return output_path


def gif_to_mp4(
    input_path: Path,
    output_path: Path,
    *,
    width: int | None = None,
) -> Path:
    """Re-encode a GIF to an H.264 MP4."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
    ]
    if width:
        cmd += ["-vf", f"scale={width}:-2:flags=lanczos"]
    cmd.append(str(output_path))
    _run_ffmpeg(cmd)
    return output_path


def images_to_gif(
    frame_paths: list[Path],
    output_path: Path,
    *,
    fps: int = 10,
    width: int = 480,
) -> Path:
    """Stitch a list of images into a single animated GIF."""
    if not frame_paths:
        raise ValueError("no frames provided")
    for p in frame_paths:
        if not p.exists():
            raise FileNotFoundError(f"missing frame: {p}")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    frames: list[Image.Image] = []
    for p in frame_paths:
        with Image.open(p) as im:
            if im.mode != "RGBA":
                im = im.convert("RGBA")
            if width and im.width > width:
                ratio = width / im.width
                im = im.resize((width, max(2, int(im.height * ratio) // 2 * 2)), Image.LANCZOS)
            frames.append(im)
    if not frames:
        raise ValueError("no frames could be read")

    # Flatten to opaque when no frame carries real transparency.
    def _has_alpha(im: Image.Image) -> bool:
        try:
            return im.getchannel("A").getextrema() != (255, 255)
        except Exception:
            return False

    frames = [f if _has_alpha(f) else f.convert("RGB") for f in frames]
    duration_ms = int(round(1000 / fps))
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
        disposal=2,
    )
    return output_path


# ---------------------------------------------------------------------------
# GIF inspection (PIL — no ffmpeg needed)
# ---------------------------------------------------------------------------

def gif_duration_seconds(path: Path) -> float:
    """Return the complete encoded playback duration of a GIF in seconds."""
    total_milliseconds = 0
    try:
        image = Image.open(path)
    except Exception as exc:
        raise ValueError(f"not a readable GIF: {path} ({exc})") from exc
    with image:
        if image.format != "GIF":
            raise ValueError(f"not a GIF: {path}")
        for frame_index in range(image.n_frames):
            image.seek(frame_index)
            total_milliseconds += int(image.info.get("duration", 0) or 0)

    if total_milliseconds <= 0:
        raise ValueError(f"GIF has no positive frame duration: {path}")
    return total_milliseconds / 1000


def gif_info(path: Path) -> dict:
    """Return basic info about a GIF file."""
    with Image.open(path) as image:
        info = {
            "format": image.format,
            "width": image.width,
            "height": image.height,
            "frames": image.n_frames,
        }
    try:
        info["duration_seconds"] = gif_duration_seconds(path)
    except ValueError:
        info["duration_seconds"] = None
    info["size_bytes"] = path.stat().st_size
    return info


def is_valid_gif(path: Path) -> bool:
    """Quick check: can PIL open and seek all frames?"""
    try:
        with Image.open(path) as image:
            if image.format != "GIF":
                return False
            for i in range(image.n_frames):
                image.seek(i)
        return True
    except Exception:
        return False
