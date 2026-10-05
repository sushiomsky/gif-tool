"""2captcha service client + IconCaptcha helpers.

Two solve paths for the IconCaptcha widget (odd-one-out icon pick) that
appears on upload flows:

1. 2captcha GridTask path (module-level, key required):
   send the challenge image to api.2captcha.com as a GridTask, get back
   1-based tile indexes, click the mapped cell.

2. In-browser visual solve (no service key):
   screenshot the widget, let a vision model pick the odd cell, dispatch
   synthetic positional MouseEvents on the overlay div. The JS payload
   produced here runs inside a browser context.

Based on:
- 2captcha GridTask API (https://2captcha.com/api-docs/grid)
- guarded-login skill: IconCaptcha in-browser solve sequence
"""
from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen


class TwoCaptchaError(RuntimeError):
    pass


class TwoCaptcha:
    """Minimal 2captcha REST client for GridTask (icon-pick / grid captchas)."""

    BASE = "https://api.2captcha.com"

    def __init__(self, api_key: str):
        if not api_key:
            raise TwoCaptchaError("2captcha API key is required")
        self._api_key = api_key

    # -- wire --------------------------------------------------------------

    def _post(self, method: str, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.BASE}/{method}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=60) as response:
            data = json.loads(response.read())
        if data.get("errorId"):
            raise TwoCaptchaError(f"{method} failed: {data.get('errorCode') or data}")
        return data

    # -- tasks ---------------------------------------------------------------

    def grid(
        self,
        image: Path | str | bytes,
        *,
        comment: str,
        rows: int = 4,
        columns: int = 4,
        min_clicks: int = 1,
        max_clicks: int | None = None,
        timeout_seconds: int = 300,
        poll_seconds: float = 5.0,
    ) -> list[int]:
        """Solve a grid/icon-pick captcha. Returns 1-based tile indexes."""
        body = self._image_b64(image)
        task = {
            "type": "GridTask",
            "body": body,
            "comment": comment,
            "rows": rows,
            "columns": columns,
            "minClicks": min_clicks,
            "maxClicks": max_clicks or rows * columns,
        }
        task_id = self._post("createTask", {"clientKey": self._api_key, "task": task})["taskId"]
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            result = self._post("getTaskResult", {"clientKey": self._api_key, "taskId": task_id})
            status = result.get("status")
            if status == "ready":
                click = result["solution"]["click"]
                if isinstance(click, str):
                    # e.g. "No_matching_images" or "4,7"
                    return [] if click.lower().startswith("no") else [int(x) for x in click.split(",")]
                return [int(x) for x in click]
            if status in {"failed", "expired", "notReady"} and status == "failed":
                raise TwoCaptchaError(f"grid task failed: {result}")
            time.sleep(poll_seconds)
        raise TwoCaptchaError(f"grid task {task_id} timed out after {timeout_seconds}s")

    def balance(self) -> float:
        return float(self._post("getBalance", {"clientKey": self._api_key})["balance"])

    @staticmethod
    def _image_b64(image: Path | str | bytes) -> str:
        if isinstance(image, bytes):
            raw = image
        elif isinstance(image, str):
            if image.startswith("data:"):
                return image.split(",", 1)[1]
            raw = Path(image).read_bytes()
        else:
            raw = image.read_bytes()
        return base64.b64encode(raw).decode("ascii")


# ---------------------------------------------------------------------------
# IconCaptcha: cell geometry + in-browser synthetic click script
# ---------------------------------------------------------------------------

def cell_center(rect: dict, index: int, total: int) -> tuple[float, float]:
    """Client coordinates for the center of cell `index` (1-based, left to right).

    `rect` is the widget's getBoundingClientRect() dict.
    """
    width = rect["width"]
    height = rect["height"]
    x = rect["x"] + width * (index - 0.5) / total
    y = rect["y"] + height / 2
    return x, y


def iconcaptcha_click_script(index: int, total: int) -> str:
    """JavaScript to run in the page that clicks cell `index` of an
    IconCaptcha widget via synthetic positional events on the overlay div.

    Pitfalls encoded here (from the guarded-login skill):
    - dispatch on `.iconcaptcha-modal__body-selection` (the overlay), NOT
      the canvas — the click listener lives on the overlay
    - send mouseenter first: hoverProtection drops clicks until a hover
      registered
    - synthetic MouseEvents must carry real clientX/clientY
    """
    return """
(() => {
  const overlay = document.querySelector('.iconcaptcha-modal__body-selection')
              || document.querySelector('.iconcaptcha-modal__body');
  if (!overlay) return {ok: false, reason: 'overlay not found'};
  const rect = overlay.getBoundingClientRect();
  const x = rect.x + rect.width * (%(index)s - 0.5) / %(total)s;
  const y = rect.y + rect.height / 2;
  const opts = {bubbles: true, cancelable: true, view: window,
                 clientX: x, clientY: y, button: 0};
  overlay.dispatchEvent(new MouseEvent('mouseenter', opts));
  overlay.dispatchEvent(new MouseEvent('mousemove', opts));
  overlay.dispatchEvent(new MouseEvent('mousedown', opts));
  overlay.dispatchEvent(new MouseEvent('mouseup', opts));
  overlay.dispatchEvent(new MouseEvent('click', opts));
  return {ok: true, x, y};
})()
""" % {"index": index, "total": total}


def iconcaptcha_verify_script() -> str:
    """Check whether the widget reached VERIFICATION COMPLETE state."""
    return """
(() => {
  const modal = document.querySelector('.iconcaptcha-modal');
  if (!modal) return {done: false, reason: 'no modal'};
  const text = (modal.innerText || '').toUpperCase();
  if (text.includes('VERIFICATION COMPLETE')) return {done: true};
  if (/WRONG|TRY AGAIN|ERROR/i.test(text)) return {done: false, error: true};
  return {done: false, waiting: true};
})()
"""
