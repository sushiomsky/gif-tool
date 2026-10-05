"""Tests for lib.prompting — DNA composition, template rendering, styles."""
import pytest
from pathlib import Path

from lib.prompting import (
    load_dna,
    build_image_prompt,
    build_animation_prompt,
    load_templates,
    fill_template,
    generate_prompts,
    load_styles,
    style_prompt,
)

SAMPLE_DNA = Path("/root/gif/gif/config/duckling_dna.md")
SAMPLE_TEMPLATES = Path("/root/gif/gif-automation-tool-v4/templates")
SAMPLE_STYLES = Path("/root/gif/gif/config/duckdice_styles.json")


# ---- DNA ------------------------------------------------------------------

def test_load_dna():
    dna = load_dna(SAMPLE_DNA)
    assert "duckling" in dna.lower()


def test_load_dna_rejects_empty(tmp_path):
    empty = tmp_path / "empty.md"
    empty.write_text("   \n")
    with pytest.raises(ValueError, match="DNA prompt is empty"):
        load_dna(empty)


def test_build_image_prompt_appends_request():
    dna = load_dna(SAMPLE_DNA)
    prompt = build_image_prompt(dna, "the duckling stares at a slot machine")
    assert "the duckling stares at a slot machine" in prompt
    assert "## Request" in prompt
    assert dna.splitlines()[0] in prompt


def test_build_image_prompt_rejects_empty():
    with pytest.raises(ValueError, match="image request must not be empty"):
        build_image_prompt("dna", "   ")


def test_build_animation_prompt():
    prompt = build_animation_prompt("blink twice and gently wobble")
    assert "blink twice and gently wobble" in prompt
    assert "seamless loop" in prompt


def test_build_animation_prompt_rejects_empty():
    with pytest.raises(ValueError, match="animation request must not be empty"):
        build_animation_prompt("   ")


# ---- Templates ------------------------------------------------------------

def test_load_templates():
    templates = load_templates(SAMPLE_TEMPLATES)
    assert "base_character.txt" in templates
    assert "scene_template.txt" in templates
    assert "motion_template.txt" in templates
    assert "negative_template.txt" in templates


def test_load_templates_missing_dir(tmp_path):
    templates = load_templates(tmp_path / "nope")
    assert templates == {}


def test_fill_template():
    text = "Hello {{name}}, you are in {{scene}}."
    assert fill_template(text, {"name": "Duckling", "scene": "a dock"}) == \
        "Hello Duckling, you are in a dock."


def test_fill_template_no_params():
    text = "unchanged {{name}}"
    assert fill_template(text, None) == "unchanged {{name}}"
    assert fill_template(text, {}) == "unchanged {{name}}"


def test_generate_prompts_image_and_video():
    templates = load_templates(SAMPLE_TEMPLATES)
    result = generate_prompts(templates, {"character": "Duckling"})
    assert "image_prompt" in result
    assert "video_prompt" in result
    # image includes negative template, video does not
    assert "negative" in result["image_prompt"].lower() or "kein Text" in result["image_prompt"]
    # video prompt should be shorter than image prompt (no base_character, no negative)
    assert len(result["image_prompt"]) > len(result["video_prompt"])


def test_generate_prompts_empty_templates():
    result = generate_prompts({}, {"character": "X"})
    assert result["image_prompt"] == ""
    assert result["video_prompt"] == ""


# ---- Styles ----------------------------------------------------------------

def test_load_styles():
    styles = load_styles(SAMPLE_STYLES)
    assert 1 <= len(styles) <= 5
    assert all("id" in s for s in styles)


def test_style_prompt_finds_by_id():
    styles = load_styles(SAMPLE_STYLES)
    first_id = styles[0]["id"]
    prompt = style_prompt(styles, first_id)
    assert prompt == styles[0].get("prompt", "")


def test_style_prompt_falls_back_to_first():
    styles = load_styles(SAMPLE_STYLES)
    prompt = style_prompt(styles, "does-not-exist")
    assert prompt == styles[0].get("prompt", "")
