"""Tenor upload adapter — adapted from gifsync/adapters/tenor.py."""
from __future__ import annotations

import json
import mimetypes
from pathlib import Path

import requests

from ..models import UploadResult


class TenorClient:
    name = "tenor"

    def __init__(self, credentials_path: Path):
        self._credentials = self._read_credentials(credentials_path)
        self._session = requests.Session()

    @staticmethod
    def _read_credentials(credentials_path: Path) -> dict[str, str]:
        with credentials_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        required = [
            "api_key",
            "client_key",
            "profile_id",
            "auth_token",
            "upload_url_base",
        ]
        missing = [key for key in required if key not in payload]
        if missing:
            raise ValueError(
                f"missing Tenor credential fields: {', '.join(missing)}"
            )
        return payload

    def upload(self, file_path: Path, title: str, tags: list[str]) -> UploadResult:
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "image/gif"

        upload_url = self._credentials["upload_url_base"]
        params = {
            "appversion": "browser-r260311-1",
            "prettyPrint": "false",
            "key": self._credentials["api_key"],
            "client_key": self._credentials["client_key"],
            "locale": "de",
            "profile_id": self._credentials["profile_id"],
            "tags": ",".join(tags),
            "title": title,
        }
        headers = {
            "Authorization": self._credentials["auth_token"],
            "Referer": "https://tenor.com/",
            "User-Agent": "Mozilla/5.0",
            "Content-Type": mime_type,
        }

        with file_path.open("rb") as handle:
            response = self._session.post(
                upload_url, params=params, headers=headers, data=handle, timeout=60
            )
        response.raise_for_status()
        payload = response.json()
        remote_id = payload.get("rid") or payload.get("results", [{}])[0].get("id")
        if not remote_id:
            raise RuntimeError(f"tenor upload did not return an id: {payload}")

        return UploadResult(service=self.name, remote_id=str(remote_id), remote_url=None)
