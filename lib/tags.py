"""Tag normalization: lowercase, dedupe, append 'duckdice'."""
from __future__ import annotations


def normalize_tags(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []

    for tag in tags:
        value = tag.strip().lstrip("#").lower()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)

    if "duckdice" not in seen:
        normalized.append("duckdice")

    return normalized