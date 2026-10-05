"""Klipy upload adapter — adapted from gifsync/adapters/klipy.py."""
from __future__ import annotations

import time
from pathlib import Path

import requests

from ..models import UploadResult
from ..gifkit import gif_duration_seconds


class DailyUploadLimitReached(RuntimeError):
    pass


class KlipyDurationLimitExceeded(ValueError):
    pass


class KlipyClient:
    name = "klipy"

    def __init__(self, auth_token: str | None = None, cookie_header: str | None = None):
        self._auth_token = auth_token
        self._cookie_header = cookie_header

    def upload(
        self,
        file_path: Path,
        title: str,
        tags: list[str],
        description: str = "",
    ) -> UploadResult:
        if self._cookie_header:
            api_base = "https://klipy.com/api/proxy"
        else:
            api_base = "https://api-us-east4.klipy.com/api/v1"
        upload_url = f"{api_base}/file/simple-file-upload"
        meta_url = f"{api_base}/file/upload-by-url"
        headers = {
            "Origin": "https://klipy.com",
            "Referer": "https://klipy.com/",
        }
        if self._auth_token:
            headers["Authorization"] = _authorization_header(self._auth_token)
        if self._cookie_header:
            headers["Cookie"] = self._cookie_header

        duration_seconds = gif_duration_seconds(file_path)
        if duration_seconds > 15:
            raise KlipyDurationLimitExceeded(
                f"GIF is {duration_seconds} seconds; Klipy accepts at most 15 seconds"
            )
        upload_response = self._post_file_with_retry(upload_url, file_path, headers)
        upload_payload = upload_response.json()
        if not upload_payload.get("result"):
            if _payload_is_daily_limit(upload_payload):
                raise DailyUploadLimitReached(str(upload_payload))
            raise RuntimeError(f"klipy upload failed: {upload_payload}")

        static_url = upload_payload.get("data", {}).get("url")
        if not static_url:
            raise RuntimeError(f"klipy upload did not return a url: {upload_payload}")

        meta_payload = {
            "url": static_url,
            "title": title,
            "description": description,
            "source": "",
            "tags": tags,
            "status": 1,
            "seconds_from": 0,
            "seconds_to": duration_seconds,
            "rotate": 0,
            "crop_start_x": 0,
            "crop_start_y": 0,
            "crop_width": 0,
            "crop_height": 0,
            "type": "gif",
            "collections": [],
        }
        meta_response = self._post_json_with_retry(
            meta_url, meta_payload, {**headers, "Content-Type": "application/json"}
        )
        meta_response.raise_for_status()
        meta_result = meta_response.json()
        if not isinstance(meta_result, dict) or not meta_result.get("result"):
            if isinstance(meta_result, dict) and _payload_is_daily_limit(meta_result):
                raise DailyUploadLimitReached(str(meta_result))
            raise RuntimeError(f"klipy metadata creation failed: {meta_result}")

        return UploadResult(service=self.name, remote_id=static_url, remote_url=static_url)

    def _post_file_with_retry(
        self, url: str, file_path: Path, headers: dict[str, str]
    ) -> requests.Response:
        last_exc: Exception | None = None
        for attempt in range(4):
            try:
                with file_path.open("rb") as handle:
                    response = requests.post(
                        url,
                        headers=headers,
                        files={"file": (file_path.name, handle, "image/gif")},
                        data={"type": "gif"},
                        timeout=60,
                    )
                if response.status_code in {429, 500, 502, 503, 504}:
                    if response.status_code == 429 and _is_daily_limit_response(
                        response.text
                    ):
                        raise DailyUploadLimitReached(response.text)
                    last_exc = RuntimeError(f"{response.status_code} {response.text[:200]}")
                    time.sleep(1.5 * (attempt + 1))
                    continue
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_exc = exc
                if attempt == 3:
                    raise
                time.sleep(1.5 * (attempt + 1))
        assert last_exc is not None
        raise last_exc

    def _post_json_with_retry(
        self, url: str, json_payload: dict[str, object], headers: dict[str, str]
    ) -> requests.Response:
        last_exc: Exception | None = None
        for attempt in range(4):
            try:
                response = requests.post(url, headers=headers, json=json_payload, timeout=60)
                if response.status_code in {429, 500, 502, 503, 504}:
                    if response.status_code == 429 and _is_daily_limit_response(
                        response.text
                    ):
                        raise DailyUploadLimitReached(response.text)
                    last_exc = RuntimeError(f"{response.status_code} {response.text[:200]}")
                    time.sleep(1.5 * (attempt + 1))
                    continue
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_exc = exc
                if attempt == 3:
                    raise
                time.sleep(1.5 * (attempt + 1))
        assert last_exc is not None
        raise last_exc


def _is_daily_limit_response(text: str) -> bool:
    return _text_is_daily_limit(text)


def _authorization_header(auth_token: str) -> str:
    if auth_token.lower().startswith("bearer "):
        return auth_token
    return f"Bearer {auth_token}"


def _payload_is_daily_limit(payload: dict[str, object]) -> bool:
    errors = payload.get("errors")
    if isinstance(errors, dict):
        for value in errors.values():
            if isinstance(value, list):
                if any(
                    isinstance(item, str) and _text_is_daily_limit(item) for item in value
                ):
                    return True
            elif isinstance(value, str) and _text_is_daily_limit(value):
                return True
    text = str(payload)
    return _text_is_daily_limit(text)


def _text_is_daily_limit(text: str) -> bool:
    normalized = text.lower()
    return "daily upload limit" in normalized or "daily publish limit" in normalized