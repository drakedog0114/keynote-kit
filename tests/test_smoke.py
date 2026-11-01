"""冒烟测试：需要 Keynote，缺失时整体跳过。

    pytest tests/
"""

import shutil
import subprocess

import pytest

keynote = shutil.which("osascript")


def keynote_available() -> bool:
    if not keynote:
        return False
    try:
        subprocess.run(
            ["osascript", "-e", 'tell application "Keynote" to count documents'],
            capture_output=True, timeout=15, check=False)
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not keynote_available(), reason="Keynote / osascript 不可用")


def test_cli_help():
    from keynote_kit.cli import build_parser

    parser = build_parser()
    assert parser.prog == "keynote-kit"


def test_parse_rgb():
    from keynote_kit.deck import _rgb

    assert _rgb("#FFFFFF") == [65535, 65535, 65535]
    assert _rgb("#000000") == [0, 0, 0]


def test_create_and_verify():
    from keynote_kit import Deck

    deck = Deck.create(theme="白色")
    try:
        slide = deck.add_slide("空白")
        deck.add_text(slide, "smoke-test", 100, 100, 600, 80, size=40, color="#000000")
        info = deck.verify(slide, expect=1)
        assert info["count"] == 1
    finally:
        deck.close()


def test_missing_image_raises():
    from keynote_kit import Deck

    deck = Deck.create(theme="白色")
    try:
        slide = deck.add_slide("空白")
        with pytest.raises(FileNotFoundError):
            deck.add_image(slide, "/tmp/definitely-not-here.png")
    finally:
        deck.close()


def test_diagram_render(tmp_path):
    from keynote_kit import diagrams

    out = diagrams.swimlane(
        stages=["① A", "② B"],
        lanes=[("角色", ["x", "y"])],
        title="t", out=str(tmp_path / "d.png"))
    assert (tmp_path / "d.png").exists()
