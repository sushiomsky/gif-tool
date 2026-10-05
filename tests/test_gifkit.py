"""Tests for lib.gifkit — ffmpeg conversion and PIL inspection."""
import pytest
from pathlib import Path

from lib.gifkit import (
    gif_duration_seconds,
    gif_info,
    is_valid_gif,
    video_to_gif,
    gif_to_mp4,
    images_to_gif,
)

SAMPLE_GIF = Path("/root/gif/gif/im-not-sorry-sticker.gif")


@pytest.fixture
def sample_gif() -> Path:
    assert SAMPLE_GIF.exists(), "sample GIF must exist for these tests"
    return SAMPLE_GIF


def test_gif_info(sample_gif):
    info = gif_info(sample_gif)
    assert info["format"] == "GIF"
    assert info["width"] > 0
    assert info["height"] > 0
    assert info["frames"] > 0
    assert info["size_bytes"] > 0


def test_gif_duration(sample_gif):
    duration = gif_duration_seconds(sample_gif)
    assert duration > 0
    assert duration < 30  # reasonable for a sticker


def test_is_valid_gif(sample_gif):
    assert is_valid_gif(sample_gif) is True


def test_is_valid_gif_rejects_non_gif(tmp_path):
    fake = tmp_path / "notagif.gif"
    fake.write_text("not a gif at all")
    assert is_valid_gif(fake) is False


def test_video_to_gif(sample_gif, tmp_path):
    out = tmp_path / "converted.gif"
    result = video_to_gif(sample_gif, out, width=200, fps=8)
    assert result.exists()
    info = gif_info(out)
    assert info["width"] == 200
    assert info["frames"] > 0


def test_video_to_gif_no_palette(sample_gif, tmp_path):
    out = tmp_path / "nopalette.gif"
    result = video_to_gif(sample_gif, out, width=200, fps=8, palette=False)
    assert result.exists()


def test_gif_to_mp4(sample_gif, tmp_path):
    out = tmp_path / "converted.mp4"
    result = gif_to_mp4(sample_gif, out, width=200)
    assert result.exists()
    assert result.stat().st_size > 0


def test_images_to_gif(sample_gif, tmp_path):
    out = tmp_path / "stitched.gif"
    # use the same file twice as a "frame sequence"
    result = images_to_gif([sample_gif, sample_gif], out, fps=5)
    assert result.exists()
    info = gif_info(out)
    assert info["frames"] > 0


def test_images_to_gif_rejects_empty(tmp_path):
    with pytest.raises(ValueError, match="no frames"):
        images_to_gif([], tmp_path / "x.gif")


def test_images_to_gif_rejects_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="missing frame"):
        images_to_gif([tmp_path / "nonexistent.png"], tmp_path / "x.gif")


def test_gif_duration_rejects_non_gif(tmp_path):
    fake = tmp_path / "fake.gif"
    fake.write_text("not a gif")
    with pytest.raises(ValueError, match="not a readable GIF|not a GIF"):
        gif_duration_seconds(fake)
