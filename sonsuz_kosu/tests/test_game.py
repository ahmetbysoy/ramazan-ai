import os
import pytest
from bs4 import BeautifulSoup

@pytest.fixture
def html_content():
    index_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/index.html'))
    assert os.path.exists(index_path), f"index.html not found at {index_path}"
    with open(index_path, 'r', encoding='utf-8') as f:
        return f.read()

@pytest.fixture
def js_content():
    js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/js/game.js'))
    assert os.path.exists(js_path), f"game.js not found at {js_path}"
    with open(js_path, 'r', encoding='utf-8') as f:
        return f.read()

def test_canvas_element_exists(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    canvas = soup.find('canvas', id='gameCanvas')
    assert canvas is not None, "Canvas element with id 'gameCanvas' is missing from index.html"
    assert canvas.get('width') == '800'
    assert canvas.get('height') == '600'

def test_script_inclusion(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    script = soup.find('script', src='js/game.js')
    assert script is not None, "game.js script tag is not correctly included in index.html"

def test_game_js_structure(js_content):
    assert 'class Game' in js_content
    assert 'requestAnimationFrame' in js_content
    assert 'clearRect' in js_content
    assert 'constructor(canvasId)' in js_content
    assert 'start()' in js_content
