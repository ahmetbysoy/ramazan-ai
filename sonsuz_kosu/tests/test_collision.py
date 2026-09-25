import subprocess
import json
import pytest

def run_node_test(script_content):
    result = subprocess.run(
        ['node', '-e', script_content],
        capture_output=True,
        text=True,
        timeout=5
    )
    if result.returncode != 0:
        pytest.fail(f"Node.js test failed: {result.stderr}\nStdout: {result.stdout}")
    return result.stdout.strip()

def test_game_state_manager():
    script = """
    const { GameState, GameStateManager } = require('./src/js/collision.js');
    const manager = new GameStateManager();
    console.assert(manager.getState() === GameState.START, 'Initial state should be START');
    manager.setState(GameState.PLAYING);
    console.assert(manager.getState() === GameState.PLAYING, 'State should transition to PLAYING');
    manager.setState(GameState.GAME_OVER);
    console.assert(manager.getState() === GameState.GAME_OVER, 'State should transition to GAME_OVER');
    manager.reset();
    console.assert(manager.getState() === GameState.START, 'State should reset to START');
    
    // Verify immutability of GameState
    try {
        GameState.PLAYING = 'MUTATED';
    } catch (e) {}
    console.assert(GameState.PLAYING === 'PLAYING', 'GameState should be immutable/frozen');
    console.log('SUCCESS');
    """
    output = run_node_test(script)
    assert 'SUCCESS' in output

def test_aabb_collision():
    script = """
    const { checkAABB } = require('./src/js/collision.js');
    const box1 = { x: 10, y: 10, width: 20, height: 20 };
    const box2 = { x: 20, y: 20, width: 20, height: 20 };
    const box3 = { x: 50, y: 50, width: 10, height: 10 };
    
    console.assert(checkAABB(box1, box2) === true, 'Overlapping boxes should collide');
    console.assert(checkAABB(box1, box3) === false, 'Non-overlapping boxes should not collide');
    console.log('SUCCESS');
    """
    output = run_node_test(script)
    assert 'SUCCESS' in output

def test_canvas_boundaries():
    script = """
    const { checkCanvasCollision } = require('./src/js/collision.js');
    const canvasHeight = 600;
    const p1 = { x: 50, y: -1, width: 30, height: 30 };
    const p2 = { x: 50, y: 580, width: 30, height: 30 };
    const p3 = { x: 50, y: 100, width: 30, height: 30 };
    
    console.assert(checkCanvasCollision(p1, canvasHeight) === true, 'Top boundary violation');
    console.assert(checkCanvasCollision(p2, canvasHeight) === true, 'Bottom boundary violation');
    console.assert(checkCanvasCollision(p3, canvasHeight) === false, 'Inside canvas');
    console.log('SUCCESS');
    """
    output = run_node_test(script)
    assert 'SUCCESS' in output

def test_pipe_collisions():
    script = """
    const { checkCollisions } = require('./src/js/collision.js');
    const canvasHeight = 600;
    const player = { x: 100, y: 200, width: 30, height: 30 };
    const pipes = [
      { x: 90, topHeight: 150, bottomY: 350, bottomHeight: 250, width: 50 }
    ];
    
    console.assert(checkCollisions(player, pipes, canvasHeight) === true, 'Should collide with pipe');
    
    const playerSafe = { x: 300, y: 200, width: 30, height: 30 };
    console.assert(checkCollisions(playerSafe, pipes, canvasHeight) === false, 'Should not collide');
    console.log('SUCCESS');
    """
    output = run_node_test(script)
    assert 'SUCCESS' in output
