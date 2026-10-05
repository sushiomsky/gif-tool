"""Tests for lib.tags, lib.discovery, lib.metadata, lib.hashing."""
import pytest
from pathlib import Path

from lib.tags import normalize_tags
from lib.discovery import discover_gifs
from lib.metadata import describe_gif, derive_tags
from lib.hashing import file_hash


def test_normalize_tags_lowercases_and_dedupes():
    assert normalize_tags(["Duck", "duck", "OMG"]) == ["duck", "omg", "duckdice"]


def test_normalize_tags_strips_hash():
    assert normalize_tags(["#Tenor", "tenor"]) == ["tenor", "duckdice"]


def test_normalize_tags_preserves_duckdice_once():
    assert normalize_tags(["DUCKDICE"]) == ["duckdice"]


def test_normalize_tags_empty():
    assert normalize_tags([]) == ["duckdice"]


def test_discover_gifs_recurses(tmp_path):
    (tmp_path / "sub").mkdir()
    a = tmp_path / "duck-meme.gif"
    b = tmp_path / "sub" / "other.gif"
    c = tmp_path / "sub" / "notgif.png"
    for p in (a, b, c):
        p.write_bytes(b"x")
    found = discover_gifs(tmp_path)
    assert found == sorted([a, b])


def test_discover_gifs_missing_dir(tmp_path):
    with pytest.raises(FileNotFoundError):
        discover_gifs(tmp_path / "nope")


def test_discover_gifs_file_not_dir(tmp_path):
    f = tmp_path / "a.gif"
    f.write_bytes(b"x")
    with pytest.raises(NotADirectoryError):
        discover_gifs(f)


def test_describe_gif(tmp_path):
    p = tmp_path / "casino-duck-panic.gif"
    p.write_bytes(b"x")
    desc = describe_gif(p)
    assert desc.title == "casino"
    assert "duckdice" in desc.tags
    assert desc.file_hash == file_hash(p)


def test_derive_tags_uses_stem(tmp_path):
    p = tmp_path / "my-great-meme.gif"
    p.write_bytes(b"x")
    tags = derive_tags(p)
    assert tags[:3] == ["my", "great", "meme"]
