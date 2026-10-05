# gif-tool

Unified GIF creation toolkit, refactored from the mixed code in `/root/gif`
(`gif/gifsync`, `gif/app`, `gif-automation-tool-v4`, `imgtovidplugin`).

One CLI, 11 commands. Python 3.13, stdlib + `requests` + `Pillow` + `ffmpeg`.

## Features

| Command | What it does | Source |
|---|---|---|
| `create-gif` | video → GIF (ffmpeg, 2-pass palette, scale/fps/loop/duration) | automation_host `process_video` + gifsync |
| `frames-to-gif` | image sequence → animated GIF | new |
| `gif-to-mp4` | GIF → H.264 MP4 re-encode | automation_host |
| `info` | frames, dimensions, encoded duration, size, validity | gifsync `gif_duration`/`integrity` |
| `sync` | upload a local GIF dir to Klipy/Tenor/Giphy, JSONL events, SQLite dedup ledger | gifsync `sync`/`state`/`adapters` |
| `prompt` | build image/animation prompts from DNA contract + request | gifsync `prompting` |
| `templates` | render `{{placeholder}}` template files into image/video prompts | automation_host `generate_prompts` |
| `generate-image` | OpenRouter image generation (server-side key, style presets, DNA, seed) | duckling-studio `server.py` |
| `generate-video` | OpenRouter image-to-video + polling + auto GIF conversion | duckling-studio `server.py` |
| `captcha-grid` | 2captcha `GridTask` client for grid/icon-pick captchas | 2captcha API + guarded-login skill |
| `captcha-js` | emit in-browser synthetic-click / verify JS for IconCaptcha widgets | guarded-login IconCaptcha solve |

## Install

```bash
ln -sf /root/gif-tool/bin/gif-tool /usr/local/bin/gif-tool
cd /root/gif-tool && python3 -m pytest tests/ -q   # 55 tests
```

## Usage

```bash
# Convert a video to a 480px @ 10fps GIF
gif-tool create-gif input.mp4 out.gif --width 480 --fps 10

# Stitch frames
gif-tool frames-to-gif frame1.png frame2.png frame3.gif out.gif

# Inspect
gif-tool info out.gif

# Build prompts from the Duckling DNA contract
gif-tool prompt --dna config/duckling_dna.md --request "duckling at the craps table" --motion "nervous blink"

# Render the German template pack
gif-tool templates --params '{"character":"Duckling"}'

# Sync local GIFs (dry-run plans without network)
gif-tool sync --source-dir ./gifs --service klipy --klipy-token "$KLIPY_AUTH_TOKEN" --dry-run

# Generate via OpenRouter (needs OPENROUTER_API_KEY)
gif-tool generate-image "duckling celebrating a win" --style casino-meme --dna config/duckling_dna.md
gif-tool generate-video duckling.webp --motion "happy bounce" --gif --gif-width 480

# Captcha solving
gif-tool captcha-grid challenge.png --comment "click the odd icon out" --rows 1 --columns 5 --api-key "$APIKEY_2CAPTCHA"
gif-tool captcha-js --index 3 --total 5 --rect '{"x":100,"y":200,"width":500,"height":100}'
gif-tool captcha-js --verify
```

Exit codes: `0` ok, `1` runtime failure, `2` argument/credential error.

## Layout

```
bin/gif-tool            CLI entry point
lib/                    library package (cli imports nothing from bin)
  cli.py                all subcommands + OpenRouter helpers
  gifkit.py             ffmpeg/PIL conversion & inspection
  prompting.py          DNA + template + style prompt builders
  metadata.py, tags.py, discovery.py, hashing.py
  state.py              SQLite upload ledger
  sync.py               orchestration (events: planned/skipped/uploaded/error)
  captcha.py            TwoCaptcha client + IconCaptcha JS payloads
  adapters/             klipy.py, tenor.py, giphy.py
config/                 duckling_dna.md, duckdice_styles.json
templates/              base_character/scene/motion/negative .txt templates
tests/                  55 pytest tests
```

## Notes

- `generate-image`/`generate-video` read `OPENROUTER_API_KEY` server-side; no
  key ever leaves the process. Paid models return 402 when the key has no
  credits — pick a `:free` model via `--model`.
- IconCaptcha: prefer the in-browser solve (`captcha-js` + screenshot/vision
  + browser evaluate) over the 2captcha path; the widget's overlay div needs
  positional MouseEvents with `mouseenter` first. See
  `~/.hermes/skills/web/guarded-login/references/iconcaptcha-solve.md`.
- Klipy refuses GIFs over 15 s of encoded duration (checked before upload).
