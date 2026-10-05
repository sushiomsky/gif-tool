"""Orchestration: scan directory, derive metadata, upload to services.

Simplified from gifsync/sync.py — uses a protocol for service clients.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Protocol

from .discovery import discover_gifs
from .metadata import describe_gif
from .models import SyncEvent
from . import state


class ServiceClient(Protocol):
    name: str

    def upload(self, file_path: Path, title: str, tags: list[str]) -> UploadResult:
        ...


# local to avoid circular import
from .models import UploadResult


def sync_directory(
    source_dir: Path,
    service_clients: list[ServiceClient],
    db_path: Path,
    dry_run: bool = False,
) -> list[SyncEvent]:
    events: list[SyncEvent] = []
    gifs = discover_gifs(source_dir)

    for file_path in gifs:
        descriptor = describe_gif(file_path)
        for client in service_clients:
            if state.has_upload(db_path, descriptor.file_hash, client.name):
                events.append(
                    SyncEvent(
                        service=client.name,
                        file_path=str(file_path),
                        file_hash=descriptor.file_hash,
                        status="skipped",
                        title=descriptor.title,
                        tags=descriptor.tags,
                        reason="already uploaded",
                    )
                )
                continue

            if dry_run:
                events.append(
                    SyncEvent(
                        service=client.name,
                        file_path=str(file_path),
                        file_hash=descriptor.file_hash,
                        status="planned",
                        title=descriptor.title,
                        tags=descriptor.tags,
                    )
                )
                continue

            try:
                upload_result = client.upload(file_path, descriptor.title, descriptor.tags)
                state.record_upload(
                    db_path,
                    file_hash=descriptor.file_hash,
                    service=client.name,
                    file_path=file_path,
                    title=descriptor.title,
                    tags=descriptor.tags,
                    remote_id=upload_result.remote_id,
                    remote_url=upload_result.remote_url,
                )
                events.append(
                    SyncEvent(
                        service=client.name,
                        file_path=str(file_path),
                        file_hash=descriptor.file_hash,
                        status="uploaded",
                        title=descriptor.title,
                        tags=descriptor.tags,
                        remote_id=upload_result.remote_id,
                        remote_url=upload_result.remote_url,
                    )
                )
            except Exception as exc:
                events.append(
                    SyncEvent(
                        service=client.name,
                        file_path=str(file_path),
                        file_hash=descriptor.file_hash,
                        status="error",
                        title=descriptor.title,
                        tags=descriptor.tags,
                        reason=str(exc),
                    )
                )

    return events


def event_to_dict(event: SyncEvent) -> dict:
    return asdict(event)