"""Dataclasses shared across gif-tool modules."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GifDescriptor:
    file_path: Path
    file_hash: str
    title: str
    tags: list[str]


@dataclass(frozen=True)
class UploadResult:
    service: str
    remote_id: str
    remote_url: str | None = None


@dataclass(frozen=True)
class SyncEvent:
    service: str
    file_path: str
    file_hash: str
    status: str
    title: str
    tags: list[str]
    remote_id: str | None = None
    remote_url: str | None = None
    reason: str | None = None
