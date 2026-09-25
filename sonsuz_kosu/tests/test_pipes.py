import os
import subprocess
import json
import pytest

def test_pipes_file_exists():
    assert os.path.exists('src/js/pipes.js'), 'src/js/pipes.js must exist'

def test_pipes_js_content():
    with open('src/js/pipes.js', 'r') as f:
        content = f.read()
    
    assert 'PipeManager' in content
    assert 'spawnPipe' in content
    assert 'update' in content
    assert 'render' in content
    assert 'pipeGap' in content
    assert 'speed' in content

def run_js_snippet(snippet):
    code = f"""
    const PipeManager = require('./src/js/pipes.js');
    {snippet}
    """
    result = subprocess.run(['node', '-e', code], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Node.js execution failed: {{result.stderr}}")
    return result.stdout.strip()

def test_pipe_generation_logic_node():
    if subprocess.run(['which', 'node'], capture_output=True).returncode != 0:
        pytest.skip("Node.js not available for running JS tests")

    snippet = """
    const pm = new PipeManager({ canvasWidth: 400, speed: 3, spawnInterval: 200 });
    pm.update(1);
    console.log(JSON.stringify({
        length: pm.pipes.length,
        x: pm.pipes[0].x,
        validGap: pm.pipes[0].topHeight + pm.pipeGap === pm.pipes[0].bottomY
    }));
    """
    out = run_js_snippet(snippet)
    data = json.loads(out)
    assert data['length'] == 1
    assert data['x'] == 400
    assert data['validGap'] is True

def test_pipe_movement_and_dt_node():
    if subprocess.run(['which', 'node'], capture_output=True).returncode != 0:
        pytest.skip("Node.js not available for running JS tests")

    snippet = """
    const pm = new PipeManager({ canvasWidth: 400, speed: 3, spawnInterval: 200 });
    pm.update(1);
    const initialX = pm.pipes[0].x;
    pm.update(2); // dt = 2 -> moves by 3 * 2 = 6
    console.log(JSON.stringify({
        x: pm.pipes[0].x,
        expected: initialX - 6
    }));
    """
    out = run_js_snippet(snippet)
    data = json.loads(out)
    assert data['x'] == data['expected']

def test_pipe_recycling_node():
    if subprocess.run(['which', 'node'], capture_output=True).returncode != 0:
        pytest.skip("Node.js not available for running JS tests")

    snippet = """
    const pm = new PipeManager({ canvasWidth: 400, pipeWidth: 60, speed: 3, spawnInterval: 200 });
    pm.update(1);
    pm.pipes[0].x = -65;
    pm.update(1);
    console.log(JSON.stringify({
        length: pm.pipes.length
    }));
    """
    out = run_js_snippet(snippet)
    data = json.loads(out)
    assert data['length'] == 1
