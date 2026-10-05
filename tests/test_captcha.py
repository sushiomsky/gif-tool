"""Tests for lib.captcha — cell geometry and IconCaptcha JS payload."""
import pytest

from lib.captcha import (
    TwoCaptcha,
    TwoCaptchaError,
    cell_center,
    iconcaptcha_click_script,
    iconcaptcha_verify_script,
)


def test_cell_center_first_cell():
    rect = {"x": 0, "y": 0, "width": 100, "height": 50}
    x, y = cell_center(rect, 1, 5)
    assert x == 10  # 100 * 0.5 / 5
    assert y == 25  # 50 / 2


def test_cell_center_last_cell():
    rect = {"x": 100, "y": 200, "width": 500, "height": 100}
    x, y = cell_center(rect, 5, 5)
    assert x == 100 + 500 * 4.5 / 5  # 550
    assert y == 250


def test_cell_center_middle_of_even_row():
    rect = {"x": 0, "y": 0, "width": 8, "height": 8}
    x, y = cell_center(rect, 2, 4)
    assert x == 8 * 1.5 / 4  # 3.0
    assert y == 4


def test_two_captcha_requires_key():
    with pytest.raises(TwoCaptchaError, match="API key is required"):
        TwoCaptcha("")


def test_two_captcha_stores_key():
    solver = TwoCaptcha("test-key-123")
    assert solver._api_key == "test-key-123"


def test_image_b64_from_bytes():
    raw = b"\x00\x01\x02"
    result = TwoCaptcha._image_b64(raw)
    import base64
    assert result == base64.b64encode(raw).decode("ascii")


def test_image_b64_from_data_uri():
    b64 = "QUJD"  # "ABC"
    uri = f"data:image/png;base64,{b64}"
    result = TwoCaptcha._image_b64(uri)
    assert result == b64


def test_image_b64_from_path(tmp_path):
    p = tmp_path / "x.png"
    p.write_bytes(b"\x89PNG-data")
    result = TwoCaptcha._image_b64(p)
    import base64
    assert result == base64.b64encode(b"\x89PNG-data").decode("ascii")


def test_image_b64_from_string_path(tmp_path):
    p = tmp_path / "y.png"
    p.write_bytes(b"binary-content")
    result = TwoCaptcha._image_b64(str(p))
    import base64
    assert result == base64.b64encode(b"binary-content").decode("ascii")


def test_cliclick_script_references_overlay():
    script = iconcaptcha_click_script(3, 5)
    assert ".iconcaptcha-modal__body-selection" in script
    assert "mouseenter" in script  # hoverProtection
    assert "clientX" in script
    assert "clientY" in script


def test_cliclick_script_embeds_index_and_total():
    script = iconcaptcha_click_script(4, 6)
    # the index and total should be baked into the arithmetic
    assert "4" in script
    assert "6" in script


def test_verify_script_checks_completion_text():
    script = iconcaptcha_verify_script()
    assert "VERIFICATION COMPLETE" in script
