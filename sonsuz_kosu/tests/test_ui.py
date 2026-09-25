import pytest
import subprocess
import json
import os

@pytest.fixture
def py_node_available():
    try:
        subprocess.run(["node", "-v"], check=True, capture_output=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        pytest.skip("Node.js is not available")

def test_ui_manager_dom(py_node_available):
    script = """
    class MockElement {
        constructor(tag) {
            this.tagName = tag;
            this.id = '';
            this.style = {};
            this.children = [];
            this.textContent = '';
            this._listeners = {};
        }
        appendChild(child) {
            this.children.push(child);
            return child;
        }
        addEventListener(event, cb) {
            this._listeners[event] = cb;
        }
        click() {
            if (this._listeners['click']) {
                this._listeners['click']();
            }
        }
        set innerHTML(val) {
            if (val === '') this.children = [];
        }
    }

    global.document = {
        createElement: (tag) => new MockElement(tag),
        body: new MockElement('body')
    };

    const UIManager = require('./src/js/ui.js');
    const ui = new UIManager(document.body);

    console.log(JSON.stringify({
        hasScore: !!ui.scoreDisplay,
        hasStart: !!ui.startScreen,
        hasGameOver: !!ui.gameOverScreen,
        hasRestart: !!ui.restartButton
    }));
    """

    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    data = json.loads(result.stdout.strip())

    assert data["hasScore"] is True
    assert data["hasStart"] is True
    assert data["hasGameOver"] is True
    assert data["hasRestart"] is True

def test_ui_state_transitions_and_callbacks(py_node_available):
    script = """
    class MockElement {
        constructor(tag) {
            this.tagName = tag;
            this.id = '';
            this.style = {};
            this.children = [];
            this.textContent = '';
            this._listeners = {};
        }
        appendChild(child) {
            this.children.push(child);
            return child;
        }
        addEventListener(event, cb) {
            this._listeners[event] = cb;
        }
        click() {
            if (this._listeners['click']) {
                this._listeners['click']();
            }
        }
        set innerHTML(val) {
            if (val === '') this.children = [];
        }
    }

    global.document = {
        createElement: (tag) => new MockElement(tag),
        body: new MockElement('body')
    };

    const UIManager = require('./src/js/ui.js');
    const ui = new UIManager(document.body);

    let started = false;
    let restarted = false;

    ui.bindStart(() => { started = true; });
    ui.bindRestart(() => { restarted = true; });

    ui.startButton.click();
    ui.updateScore(42);
    ui.showGameOverScreen(42, [{score: 100, date: Date.now()}]);
    ui.restartButton.click();

    console.log(JSON.stringify({
        started: started,
        restarted: restarted,
        scoreText: ui.scoreDisplay.textContent,
        finalScoreText: ui.finalScoreDisplay.textContent,
        tableItems: ui.highScoreTable.children.length,
        gameOverVisible: ui.gameOverScreen.style.display === 'flex'
    }));
    """

    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    data = json.loads(result.stdout.strip())

    assert data["started"] is True
    assert data["restarted"] is True
    assert data["scoreText"] == "42"
    assert data["finalScoreText"] == "Score: 42"
    assert data["tableItems"] == 1
    assert data["gameOverVisible"] is True
