"""Tests for lib.state (SQLite ledger) and lib.sync (orchestration)."""
import pytest
from pathlib import Path

from lib.state import has_upload, record_upload, list_uploads
from lib.models import GifDescriptor, UploadResult
from lib.sync import sync_directory
from lib.hashing import file_hash
from lib.discovery import discover_gifs


class MockClient:
    def __init__(self, name: str, fail: bool = False):
        self.name = name
        self._fail = fail
        self.uploads = []

    def upload(self, file_path: Path, title: str, tags: list[str]) -> UploadResult:
        if self._fail:
            raise RuntimeError(f"mock upload failed for {self.name}")
        result = UploadResult(
            service=self.name,
            remote_id=f"{self.name}-{file_path.stem}",
            remote_url=f"https://{self.name}.com/{file_path.stem}",
        )
        self.uploads.append((file_path, title, tags, result))
        return result


def test_state_roundtrip(tmp_path):
    db = tmp_path / "state.sqlite"
    h = "hash-" + "a" * 10
    assert not has_upload(db, h, "klipy")
    record_upload(
        db, file_hash=h, service="klipy", file_path=Path("a.gif"),
        title="Test", tags=["test"], remote_id="rid", remote_url="url"
    )
    assert has_upload(db, h, "klipy")
    records = list_uploads(db)
    assert len(records) == 1
    assert records[0]["service"] == "klipy"
    assert records[0]["remote_id"] == "rid"


def test_state_service_isolation(tmp_path):
    db = tmp_path / "state.sqlite"
    h = "abc123"
    record_upload(
        db, file_hash=h, service="klipy", file_path=Path("a.gif"),
        title="Test", tags=[], remote_id="rid", remote_url="url"
    )
    assert has_upload(db, h, "klipy")
    assert not has_upload(db, h, "tenor")


def test_sync_plans_dry_run(tmp_path):
    gif = tmp_path / "duck.gif"
    gif.write_bytes(b"x")
    db = tmp_path / "state.sqlite"
    client = MockClient("klipy")
    events = sync_directory(tmp_path, [client], db, dry_run=True)
    assert len(events) == 1
    assert events[0].status == "planned"
    assert not client.uploads


def test_sync_skips_existing(tmp_path):
    gif = tmp_path / "duck.gif"
    gif.write_bytes(b"x")
    db = tmp_path / "state.sqlite"
    h = file_hash(gif)
    record_upload(
        db, file_hash=h, service="klipy", file_path=gif,
        title="Test", tags=["duck"], remote_id="rid", remote_url="url"
    )
    client = MockClient("klipy")
    events = sync_directory(tmp_path, [client], db, dry_run=False)
    assert len(events) == 1
    assert events[0].status == "skipped"
    assert not client.uploads


def test_sync_uploads_new(tmp_path):
    gif = tmp_path / "duck.gif"
    gif.write_bytes(b"x")
    db = tmp_path / "state.sqlite"
    client = MockClient("klipy")
    events = sync_directory(tmp_path, [client], db, dry_run=False)
    assert len(events) == 1
    assert events[0].status == "uploaded"
    assert client.uploads
    assert events[0].remote_id == client.uploads[0][3].remote_id
    # should be recorded now
    assert has_upload(db, file_hash(gif), "klipy")


def test_sync_reports_error(tmp_path):
    gif = tmp_path / "duck.gif"
    gif.write_bytes(b"x")
    db = tmp_path / "state.sqlite"
    client = MockClient("klipy", fail=True)
    events = sync_directory(tmp_path, [client], db, dry_run=False)
    assert len(events) == 1
    assert events[0].status == "error"
    assert events[0].reason


def test_sync_multiple_services(tmp_path):
    gif = tmp_path / "duck.gif"
    gif.write_bytes(b"x")
    db = tmp_path / "state.sqlite"
    klipy = MockClient("klipy")
    tenor = MockClient("tenor")
    events = sync_directory(tmp_path, [klipy, tenor], db, dry_run=False)
    assert len(events) == 2
    services = {e.service for e in events}
    assert services == {"klipy", "tenor"}
    assert all(e.status == "uploaded" for e in events)


def test_discover_gifs_sorted(tmp_path):
    (tmp_path / "b.gif").write_bytes(b"x")
    (tmp_path / "a.gif").write_bytes(b"x")
    found = discover_gifs(tmp_path)
    assert [p.name for p in found] == ["a.gif", "b.gif"]