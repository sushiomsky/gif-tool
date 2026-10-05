"""gif-tool CLI — one entry point, subcommands for every feature.

Commands
========
  create-gif      video -> GIF via ffmpeg
  frames-to-gif   image sequence -> GIF
  gif-to-mp4      GIF -> H.264 MP4
  info            print GIF metadata (frames, duration, size)
  sync            upload a local GIF directory to services (JSONL events)
  prompt          build image/animation prompts from DNA + request
  templates       render {{placeholder}} templates into image/video prompts
  generate-image  OpenRouter image generation (server-side key)
  generate-video  OpenRouter image-to-video + auto GIF conversion
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from . import gifkit, prompting, state, sync as sync_mod
from .discovery import discover_gifs
from .metadata import describe_gif

DEFAULT_STATE_DB = Path(".giftool/state.sqlite")


# ---------------------------------------------------------------------------
# OpenRouter helpers (from duckling-studio server.py)
# ---------------------------------------------------------------------------

def _or_base_url() -> str:
    return os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/") + "/"


def _or_token() -> str:
    return os.environ.get("OPENROUTER_API_KEY", os.environ.get("OMNIROUTE_TOKEN", ""))


def _or_upstream(path: str, method: str = "GET", body: bytes | None = None, content_type: str | None = None):
    headers = {
        "Authorization": f"Bearer {_or_token()}",
        "Accept": "application/json",
    }
    if content_type:
        headers["Content-Type"] = content_type
    request = Request(_or_base_url().rstrip("/") + "/" + path, data=body, headers=headers, method=method)
    with urlopen(request, timeout=600) as response:
        return response.status, response.headers.get_content_type(), response.read()


def _or_json(body: bytes) -> dict:
    return json.loads(body)


def _extract_asset(payload: dict) -> dict:
    data = payload.get("data") or payload.get("output") or []
    if isinstance(data, dict):
        data = [data]
    first = data[0] if data else payload
    if isinstance(first, str):
        return {"url": first, "type": "image"}
    if not isinstance(first, dict):
        raise ValueError("provider returned no media result")
    url = first.get("url") or first.get("video_url") or first.get("image_url")
    if not url and first.get("b64_json"):
        mime = first.get("mime_type") or first.get("media_type", "image/png")
        url = f"data:{mime};base64,{first['b64_json']}"
    if not url:
        raise ValueError("response contains neither URL nor image data")
    return {"url": url, "type": "video" if "video" in url or first.get("video_url") else "image"}


def _image_reference(data: bytes, mime: str) -> dict:
    encoded = base64.b64encode(data).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}


def _download_to(url: str, output_path: Path) -> Path:
    if url.startswith("data:"):
        header, encoded = url.split(",", 1)
        mime = header.split(":", 1)[1].split(";", 1)[0]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(base64.b64decode(encoded))
        return output_path
    request = Request(url, headers={"User-Agent": "gif-tool/1.0"})
    with urlopen(request, timeout=300) as response:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.read())
    return output_path


def _poll_video_job(job: dict, poll_seconds: int = 5, max_polls: int = 36) -> dict:
    job_url = job.get("polling_url") or f"videos/{job['id']}"
    for _ in range(max_polls):
        _, _, body = _or_upstream(job_url)
        state = _or_json(body)
        status = state.get("status")
        if status == "completed":
            content_url = (state.get("unsigned_urls") or [None])[0] or f"{job_url}/content?index=0"
            _, content_type, video = _or_upstream(content_url)
            return {"video_bytes": video, "content_type": content_type or "video/mp4"}
        if status in {"failed", "cancelled", "expired"}:
            raise RuntimeError(state.get("error") or f"video job ended: {status}")
        time.sleep(poll_seconds)
    raise TimeoutError("video generation exceeded the time limit")


# ---------------------------------------------------------------------------
# command handlers
# ---------------------------------------------------------------------------


def cmd_create_gif(args: argparse.Namespace) -> int:
    output = gifkit.video_to_gif(
        Path(args.input),
        Path(args.output),
        width=args.width,
        fps=args.fps,
        loop=args.loop,
        duration=args.duration,
        palette=not args.no_palette,
    )
    print(json.dumps({"status": "ok", "output": str(output), **gifkit.gif_info(output)}, indent=2))
    return 0


def cmd_frames_to_gif(args: argparse.Namespace) -> int:
    output = gifkit.images_to_gif(
        [Path(p) for p in args.frames],
        Path(args.output),
        fps=args.fps,
        width=args.width,
    )
    print(json.dumps({"status": "ok", "output": str(output), **gifkit.gif_info(output)}, indent=2))
    return 0


def cmd_gif_to_mp4(args: argparse.Namespace) -> int:
    output = gifkit.gif_to_mp4(Path(args.input), Path(args.output), width=args.width)
    print(json.dumps({"status": "ok", "output": str(output)}, indent=2))
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    path = Path(args.path)
    result = gifkit.gif_info(path)
    result["valid"] = gifkit.is_valid_gif(path)
    print(json.dumps(result, indent=2))
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    from .adapters import GiphyClient, KlipyClient, TenorClient

    services = args.service or ["klipy"]
    clients = []
    for service in services:
        if service == "klipy":
            if not args.klipy_token and not args.klipy_cookie:
                print("--klipy-token or --klipy-cookie is required for klipy", file=sys.stderr)
                return 2
            clients.append(KlipyClient(auth_token=args.klipy_token, cookie_header=args.klipy_cookie))
        elif service == "tenor":
            if not args.tenor_creds:
                print("--tenor-creds is required for tenor", file=sys.stderr)
                return 2
            clients.append(TenorClient(Path(args.tenor_creds)))
        elif service == "giphy":
            if not args.giphy_api_key or not args.giphy_auth_token:
                print("--giphy-api-key and --giphy-auth-token required for giphy", file=sys.stderr)
                return 2
            clients.append(GiphyClient(args.giphy_api_key, args.giphy_auth_token))
        else:
            print(f"unknown service: {service}", file=sys.stderr)
            return 2

    try:
        events = sync_mod.sync_directory(
            Path(args.source_dir), clients, Path(args.state_db), dry_run=args.dry_run
        )
    except (FileNotFoundError, NotADirectoryError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    failures = 0
    for event in events:
        print(json.dumps(sync_mod.event_to_dict(event), ensure_ascii=True))
        if event.status == "error":
            failures += 1
    return 1 if failures else 0


def cmd_prompt(args: argparse.Namespace) -> int:
    dna_path = Path(args.dna) if args.dna else None
    if dna_path:
        dna = prompting.load_dna(dna_path)
        image_prompt = prompting.build_image_prompt(dna, args.request)
        print(json.dumps({"image_prompt": image_prompt}, ensure_ascii=False, indent=2))
    if args.motion:
        print(json.dumps({"animation_prompt": prompting.build_animation_prompt(args.motion)}, ensure_ascii=False, indent=2))
    return 0


def cmd_templates(args: argparse.Namespace) -> int:
    templates = prompting.load_templates(Path(args.templates_dir))
    params = json.loads(args.params) if args.params else None
    result = prompting.generate_prompts(templates, params)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_generate_image(args: argparse.Namespace) -> int:
    if not _or_token():
        print("OPENROUTER_API_KEY (server-side) is required", file=sys.stderr)
        return 2
    style = ""
    if args.style:
        styles = prompting.load_styles(Path(args.styles_config) if args.styles_config else Path("config/duckdice_styles.json"))
        style = prompting.style_prompt(styles, args.style)
    prompt = (style + "\n\n" + args.prompt).strip() if style else args.prompt
    if args.dna:
        dna = prompting.load_dna(Path(args.dna))
        prompt = prompting.build_image_prompt(dna, prompt)
    payload = {
        "model": args.model,
        "prompt": prompt,
        "output_format": "webp",
    }
    if args.seed is not None:
        payload["seed"] = args.seed
    _, _, body = _or_upstream("images", "POST", json.dumps(payload).encode(), "application/json")
    result = _extract_asset(_or_json(body))
    out = Path(args.output)
    _download_to(result["url"], out)
    print(json.dumps({"status": "ok", "output": str(out), "url": result["url"]}, indent=2))
    return 0


def cmd_generate_video(args: argparse.Namespace) -> int:
    """OpenRouter image-to-video; converts the result to a GIF when --gif is set."""
    if not _or_token():
        print("OPENROUTER_API_KEY (server-side) is required", file=sys.stderr)
        return 2
    source = Path(args.image)
    if not source.exists():
        print(f"image not found: {source}", file=sys.stderr)
        return 1
    mime = "image/png" if source.suffix.lower() == ".png" else "image/webp"
    prompt = prompting.build_animation_prompt(args.motion) if args.motion else "Subtle natural idle motion, seamless loop."
    payload = {
        "model": args.model,
        "prompt": prompt,
        "frame_images": [{**_image_reference(source.read_bytes(), mime), "frame_type": "first_frame"}],
        "duration": max(3, min(6, args.duration)),
        "aspect_ratio": "1:1",
    }
    print(json.dumps({"status": "submitted", "prompt": prompt}), file=sys.stderr)
    _, _, body = _or_upstream("videos", "POST", json.dumps(payload).encode(), "application/json")
    job = _or_json(body)
    print("polling video job…", file=sys.stderr)
    video = _poll_video_job(job)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    mp4 = out_dir / "clip.mp4"
    mp4.write_bytes(video["video_bytes"])
    result = {"status": "ok", "mp4": str(mp4)}
    if args.gif:
        gif = out_dir / "clip.gif"
        gifkit.video_to_gif(mp4, gif, width=args.gif_width, fps=args.fps)
        result["gif"] = str(gif)
        result.update(gifkit.gif_info(gif))
    print(json.dumps(result, indent=2))
    return 0


def cmd_captcha_grid(args: argparse.Namespace) -> int:
    """Solve a grid/icon-pick captcha via 2captcha GridTask."""
    from .captcha import TwoCaptcha
    key = args.api_key or os.environ.get("APIKEY_2CAPTCHA", "")
    if not key:
        print("2captcha API key required (--api-key or APIKEY_2CAPTCHA)", file=sys.stderr)
        return 2
    solver = TwoCaptcha(key)
    try:
        tiles = solver.grid(
            Path(args.image),
            comment=args.comment,
            rows=args.rows,
            columns=args.columns,
            min_clicks=args.min_clicks,
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps({"status": "ok", "click": tiles}, indent=2))
    return 0


def cmd_captcha_js(args: argparse.Namespace) -> int:
    """Emit the in-browser JS payload for IconCaptcha (no service key needed).

    The agent runs the emitted script via browser evaluate after
    screenshotting the widget and picking the odd cell with vision.
    """
    from .captcha import cell_center, iconcaptcha_click_script, iconcaptcha_verify_script

    if args.verify:
        print(iconcaptcha_verify_script())
        return 0
    rect = json.loads(args.rect) if args.rect else None
    if rect:
        x, y = cell_center(rect, args.index, args.total)
        print(f"# target cell {args.index}/{args.total} center: ({x:.1f}, {y:.1f})", file=sys.stderr)
    print(iconcaptcha_click_script(args.index, args.total))
    return 0


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gif-tool", description="Unified GIF creation and automation toolkit.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-gif", help="convert a video to a GIF")
    p.add_argument("input", help="source video (mp4/webm/mov)")
    p.add_argument("output", help="output .gif path")
    p.add_argument("--width", type=int, default=480)
    p.add_argument("--fps", type=int, default=10)
    p.add_argument("--loop", type=int, default=0, help="force N loops into the GIF")
    p.add_argument("--duration", type=float, default=None, help="cap duration in seconds")
    p.add_argument("--no-palette", action="store_true", help="skip 2-pass palette (faster, lower quality)")
    p.set_defaults(func=cmd_create_gif)

    p = sub.add_parser("frames-to-gif", help="stitch images into an animated GIF")
    p.add_argument("frames", nargs="+", help="frame files, in order")
    p.add_argument("output")
    p.add_argument("--fps", type=int, default=10)
    p.add_argument("--width", type=int, default=480)
    p.set_defaults(func=cmd_frames_to_gif)

    p = sub.add_parser("gif-to-mp4", help="re-encode a GIF to H.264 MP4")
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--width", type=int, default=None)
    p.set_defaults(func=cmd_gif_to_mp4)

    p = sub.add_parser("info", help="print GIF metadata")
    p.add_argument("path")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("sync", help="upload local GIFs to services")
    p.add_argument("--source-dir", required=True)
    p.add_argument("--state-db", default=str(DEFAULT_STATE_DB))
    p.add_argument("--service", action="append", choices=["klipy", "tenor", "giphy"])
    p.add_argument("--klipy-token")
    p.add_argument("--klipy-cookie")
    p.add_argument("--tenor-creds")
    p.add_argument("--giphy-api-key")
    p.add_argument("--giphy-auth-token")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("prompt", help="build image/animation prompts")
    p.add_argument("--dna", help="path to DNA contract .md file")
    p.add_argument("--request", help="one-scene image request")
    p.add_argument("--motion", help="one-line motion description")
    p.set_defaults(func=cmd_prompt)

    p = sub.add_parser("templates", help="render {{placeholder}} template files")
    p.add_argument("--templates-dir", default="templates")
    p.add_argument("--params", help="JSON string of placeholder values")
    p.set_defaults(func=cmd_templates)

    p = sub.add_parser("generate-image", help="generate an image via OpenRouter")
    p.add_argument("prompt")
    p.add_argument("--model", default=os.environ.get("OPENROUTER_IMAGE_MODEL", "google/gemini-2.5-flash-image"))
    p.add_argument("--style", help="style group id from duckdice_styles.json")
    p.add_argument("--styles-config", help="path to styles json (default config/duckdice_styles.json)")
    p.add_argument("--dna", help="prepend DNA contract")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--output", default="generated.webp")
    p.set_defaults(func=cmd_generate_image)

    p = sub.add_parser("generate-video", help="image-to-video via OpenRouter, optional GIF")
    p.add_argument("image", help="first-frame image (png/webp/jpg)")
    p.add_argument("--model", default=os.environ.get("OPENROUTER_VIDEO_MODEL", "x-ai/grok-imagine-video-1.5"))
    p.add_argument("--motion", help="motion description (else default idle motion)")
    p.add_argument("--duration", type=int, default=4, help="3-6 seconds")
    p.add_argument("--output-dir", default="generated")
    p.add_argument("--gif", action="store_true", help="also convert the result to GIF")
    p.add_argument("--gif-width", type=int, default=480)
    p.add_argument("--fps", type=int, default=10)
    p.set_defaults(func=cmd_generate_video)

    p = sub.add_parser("captcha-grid", help="solve grid/icon-pick captcha via 2captcha GridTask")
    p.add_argument("image", help="challenge image file or data: URI")
    p.add_argument("--comment", required=True, help="instruction shown to workers")
    p.add_argument("--rows", type=int, default=4)
    p.add_argument("--columns", type=int, default=4)
    p.add_argument("--min-clicks", type=int, default=1)
    p.add_argument("--api-key", help="2captcha API key (or APIKEY_2CAPTCHA env)")
    p.set_defaults(func=cmd_captcha_grid)

    p = sub.add_parser("captcha-js", help="emit in-browser JS for IconCaptcha click/verify")
    p.add_argument("--index", type=int, required=True, help="1-based cell index to click")
    p.add_argument("--total", type=int, default=5, help="total cells in the row")
    p.add_argument("--rect", help="JSON widget rect from getBoundingClientRect() for center coords")
    p.add_argument("--verify", action="store_true", help="emit verification check script instead of click")
    p.set_defaults(func=cmd_captcha_js)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    except HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "ignore")[:300]
        except Exception:
            pass
        if exc.code == 402:
            print(f"upstream billing error (402): API key has no credits for this model. "
                  f"Pick a free model or add credits. Detail: {detail}", file=sys.stderr)
        else:
            print(f"HTTP {exc.code} from upstream: {detail}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
