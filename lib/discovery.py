"""Discover GIF files in a directory."""
from __future__ import annotations

from pathlib import Path


def discover_gifs(source_dir: Path) -> list[Path]:
    if not source_dir.exists():
        raise FileNotFoundError(f"source directory does not exist: {source_dir}")
    if not source_dir.is_dir():
        raise NotADirectoryError(f"source path is not a directory: {source_dir}")

    gifs = [
        path
        for path in source_dir.rglob("*")
        if path.is_file() and path.suffix.lower() == ".gif"
    ]
    return sorted(gifs)