"""Prompt builders for image/video generation pipelines.

Combines two sources:
- gifsync/prompting.py: DNA-contract prompt composition (duckling_dna.md)
- gif-automation-tool-v4/native_host: template file + {{placeholder}} substitution

No external calls — pure string builders.
"""
from __future__ import annotations

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# DNA-contract prompting (from gifsync/prompting.py)
# ---------------------------------------------------------------------------


def load_dna(path: Path) -> str:
    """Load the immutable character/style contract from a text file."""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"DNA prompt is empty: {path}")
    return text


def build_image_prompt(dna: str, request: str) -> str:
    """Combine the DNA contract with one request-specific image idea."""
    request = request.strip()
    if not request:
        raise ValueError("image request must not be empty")
    return f"{dna}\n\n## Request\n\nCreate this one illustration: {request}"


def build_animation_prompt(request: str) -> str:
    """Build a motion-only prompt that preserves the generated image."""
    request = request.strip()
    if not request:
        raise ValueError("animation request must not be empty")
    return (
        "Animate the supplied illustration as a short seamless loop. "
        "Preserve the character design, thick outlines, flat sticker-art "
        "rendering, colors, composition, and any caption exactly. "
        "Do not redesign the character, add characters, change the art "
        "style, or add camera movement. Use only this subtle motion: "
        f"{request}"
    )


# ---------------------------------------------------------------------------
# Template-file prompting (from gif-automation-tool-v4 native_host)
# ---------------------------------------------------------------------------


def load_templates(templates_dir: Path) -> dict[str, str]:
    """Load all text templates from a directory as {filename: text}."""
    templates: dict[str, str] = {}
    if not templates_dir.is_dir():
        return templates
    for path in sorted(templates_dir.iterdir()):
        if path.is_file():
            templates[path.name] = path.read_text(encoding="utf-8")
    return templates


def fill_template(text: str, params: dict[str, str] | None = None) -> str:
    """Replace {{key}} placeholders in template text."""
    if not params:
        return text
    for key, value in params.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text


def generate_prompts(templates: dict[str, str], params: dict[str, str] | None = None) -> dict[str, str]:
    """Combine template files into image and video prompts.

    image_prompt = base_character + scene + motion + negative
    video_prompt = scene + motion
    """
    image_prompt = "\n".join(
        fill_template(templates.get(name, "").strip(), params)
        for name in ("base_character.txt", "scene_template.txt", "motion_template.txt", "negative_template.txt")
        if templates.get(name, "").strip()
    )
    video_prompt = "\n".join(
        fill_template(templates.get(name, "").strip(), params)
        for name in ("scene_template.txt", "motion_template.txt")
        if templates.get(name, "").strip()
    )
    return {"image_prompt": image_prompt, "video_prompt": video_prompt}


# ---------------------------------------------------------------------------
# Style presets (from duckdice_styles.json)
# ---------------------------------------------------------------------------


def load_styles(config_path: Path) -> list[dict]:
    styles = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(styles, list) or not 1 <= len(styles) <= 5:
        raise ValueError("style config needs 1-5 style groups")
    return styles


def style_prompt(styles: list[dict], style_id: str) -> str:
    """Return the prompt preamble for a named style group."""
    for style in styles:
        if style.get("id") == style_id:
            return style.get("prompt", "")
    return styles[0].get("prompt", "")
