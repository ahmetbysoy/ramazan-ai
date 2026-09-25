import pytest
from ramazan.ui.games import MONKEY_GAME_HTML


def test_monkey_game_template_validity():
    content = MONKEY_GAME_HTML
    assert len(content) > 1000

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
