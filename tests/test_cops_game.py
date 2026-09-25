import pytest
from pathlib import Path


def test_cops_game_file_and_controls():
    game_path = Path("cops_robbers_game.html")
    assert game_path.exists(), "cops_robbers_game.html should exist"
    content = game_path.read_text(encoding="utf-8")

    # 1. Viewport & Canvas
    assert "<meta name=\"viewport\"" in content
    assert 'id="gameCanvas"' in content

    # 2. Touch Controls & HUD
    assert 'id="btnUp"' in content
    assert 'id="btnDown"' in content
    assert 'id="btnLeft"' in content
    assert 'id="btnRight"' in content
    assert 'id="btnBoost"' in content
    assert 'id="scoreText"' in content
    assert 'id="starsText"' in content

    # 3. Game State & Logic
    assert "cops" in content
    assert "lootBags" in content
    assert "spawnCop" in content
    assert "spawnLoot" in content
    assert "playBeep" in content
    assert "AudioContext" in content
