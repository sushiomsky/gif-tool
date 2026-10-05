"""Derive titles and tags from local GIF filenames.

Extracted from gifsync/metadata.py.
"""
from __future__ import annotations

import re
from pathlib import Path

from .hashing import file_hash
from .models import GifDescriptor
from .tags import normalize_tags

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def derive_tags(file_path: Path) -> list[str]:
    stem = file_path.stem
    tokens = [match.group(0).lower() for match in _TOKEN_RE.finditer(stem)]
    return normalize_tags(tokens)


def derive_title(tags: list[str], fallback: str) -> str:
    if tags:
        return tags[0]
    return fallback


def describe_gif(file_path: Path) -> GifDescriptor:
    tags = derive_tags(file_path)
    title = derive_title(tags, file_path.stem)
    return GifDescriptor(
        file_path=file_path,
        file_hash=file_hash(file_path),
        title=title,
        tags=tags,
    )
