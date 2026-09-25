import pytest
from pathlib import Path


def test_monkey_game_file_exists():
    game_path = Path("monkey_game.html")
    assert game_path.exists(), "monkey_game.html should exist"
    content = game_path.read_text(encoding="utf-8")

    # 1. Mobile Responsiveness Checks
    assert "<meta name=\"viewport\"" in content
    assert "user-scalable=no" in content

    # 2. Canvas & Structure Checks
    assert 'id="gameCanvas"' in content
    assert 'id="btnLeft"' in content
    assert 'id="btnRight"' in content
    assert 'id="scoreVal"' in content

    # 3. Game Mechanics & JavaScript Logic
    assert "monkey" in content
    assert "gravity" in content
    assert "jumpStrength" in content
    assert "bananas" in content
    assert "platforms" in content
    assert "touchstart" in content
    assert "requestAnimationFrame" in content
