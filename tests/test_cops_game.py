import pytest
from ramazan.ui.games import COPS_ROBBERS_GAME_HTML


def test_cops_game_template_validity():
    content = COPS_ROBBERS_GAME_HTML
    assert len(content) > 1000

    # 1. Mobile Responsiveness Checks
    assert "<meta name=\"viewport\"" in content
    assert "user-scalable=no" in content

    # 2. Canvas & Structure Checks
    assert 'id="gameCanvas"' in content
    assert 'id="btnLeft"' in content
    assert 'id="btnRight"' in content
    assert 'id="btnUp"' in content
    assert 'id="btnDown"' in content
    assert 'id="btnBoost"' in content

    # 3. Audio & Game Loop
    assert "AudioContext" in content
    assert "cops" in content
    assert "boost" in content
    assert "score" in content
