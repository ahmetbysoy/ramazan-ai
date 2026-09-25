from pathlib import Path
import subprocess
import json
import shutil
import pytest

@pytest.fixture
def py_node_available():
    return shutil.which("node") is not None

def test_audio_manager_runtime(py_node_available):
    if not py_node_available:
        pytest.skip("Node.js not available to execute JS tests")

    # JavaScript test harness that mocks AudioContext and tests AudioManager runtime behavior
    js_test_code = """
    const { AudioManager } = require('./src/js/audio.js');

    class MockAudioContext {
        constructor() {
            this.state = 'suspended';
            this.currentTime = 0;
            this.destination = {};
            this.createdNodes = [];
        }
        resume() {
            this.state = 'running';
            return Promise.resolve();
        }
        createOscillator() {
            const osc = {
                type: 'sine',
                frequency: {
                    setValueAtTime: (val, t) => { osc.freqVal = val; },
                    exponentialRampToValueAtTime: (val, t) => {},
                    linearRampToValueAtTime: (val, t) => {}
                },
                connect: (node) => { osc.connectedTo = node; },
                start: (t) => { osc.started = true; },
                stop: (t) => { osc.stopped = true; }
            };
            this.createdNodes.push(osc);
            return osc;
        }
        createGain() {
            const gain = {
                gain: {
                    setValueAtTime: (val, t) => { gain.gainVal = val; },
                    linearRampToValueAtTime: (val, t) => {}
                },
                connect: (node) => { gain.connectedTo = node; }
            };
            this.createdNodes.push(gain);
            return gain;
        }
    }

    const results = {};

    // Test mute configuration
    const manager = new AudioManager();
    results.initialMuted = manager.isMuted();
    results.setMutedTrue = manager.setMuted(true);
    results.isMutedTrue = manager.isMuted();
    results.setMutedFalse = manager.setMuted(false);
    results.isMutedFalse = manager.isMuted();

    // Test AudioContext init and sound triggers with mock
    const mockCtx = new MockAudioContext();
    global.window = { AudioContext: function() { return mockCtx; } };
    manager.init();
    results.contextRunning = mockCtx.state === 'running';

    // Test playJump
    manager.playJump();
    results.jumpNodesCount = mockCtx.createdNodes.length;

    // Test playScore
    mockCtx.createdNodes = [];
    manager.playScore();
    results.scoreNodesCount = mockCtx.createdNodes.length;

    // Test playHit
    mockCtx.createdNodes = [];
    manager.playHit();
    results.hitNodesCount = mockCtx.createdNodes.length;

    // Test muted behavior (should not create nodes)
    manager.setMuted(true);
    mockCtx.createdNodes = [];
    manager.playJump();
    results.mutedNodesCount = mockCtx.createdNodes.length;

    console.log(JSON.stringify(results));
    """

    result = subprocess.run(["node", "-e", js_test_code], capture_output=True, text=True, check=True)
    data = json.loads(result.stdout.strip())

    assert data["initialMuted"] is False
    assert data["setMutedTrue"] is True
    assert data["isMutedTrue"] is True
    assert data["setMutedFalse"] is False
    assert data["isMutedFalse"] is False
    assert data["contextRunning"] is True
    assert data["jumpNodesCount"] == 2
    assert data["scoreNodesCount"] == 2
    assert data["hitNodesCount"] == 2
    assert data["mutedNodesCount"] == 0
