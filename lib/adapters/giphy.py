"""Giphy upload adapter — adapted from gifsync/adapters/giphy.py."""
from __future__ import annotations

from pathlib import Path

import requests

from ..models import UploadResult


class GiphyClient:
    name = "giphy"

    def __init__(self, api_key: str, auth_token: str):
        self._api_key = api_key
        self._auth_token = auth_token

    def upload(self, file_path: Path, title: str, tags: list[str]) -> UploadResult:
        upload_url = f"https://upload.giphy.com/v1/upload?api_key={self._api_key}"
        headers = {
            "Authorization": self._auth_token,
            "Origin": "https://giphy.com",
            "Referer": "https://giphy.com/",
        }
        with file_path.open("rb") as handle:
            response = requests.post(
                upload_url,
                headers=headers,
                files={"file": (file_path.name, handle, "image/gif")},
                data={"tags": ",".join(tags), "title": title},
                timeout=60,
            )
        response.raise_for_status()
        payload = response.json()
        remote_id = payload.get("data", {}).get("id")
        if not remote_id:
            raise RuntimeError(f"giphy upload did not return an id: {payload}")
        return UploadResult(service=self.name, remote_id=str(remote_id), remote_url=None)