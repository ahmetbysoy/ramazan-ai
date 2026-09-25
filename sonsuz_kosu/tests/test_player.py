import os
import subprocess
import json

def test_player_js_exists():
    assert os.path.exists("src/js/player.js")

def test_player_runtime_physics_and_immutability():
    # Run a node script that imports and tests player.js functions and immutability
    node_script = '''
        import { createPlayer, setupPlayerControls } from './src/js/player.js';

        const p1 = createPlayer({ x: 50, y: 50, vy: 0, gravity: 0.5, jumpStrength: -8 });
        const state1 = p1.getState();

        // Test immutability
        let frozenCaught = false;
        try {
            state1.y = 100;
        } catch (e) {
            frozenCaught = true;
        }

        // Test update (gravity)
        const p2 = p1.update();
        const state2 = p2.getState();

        // Test jump
        const p3 = p2.jump();
        const state3 = p3.getState();

        // Test controls
        let current = createPlayer();
        const fakeCanvas = {
            listeners: {},
            addEventListener(event, cb) {
                this.listeners[event] = cb;
            },
            removeEventListener(event, cb) {
                delete this.listeners[event];
            }
        };

        const cleanup = setupPlayerControls(fakeCanvas, () => current, (np) => { current = np; });
        
        let prevented = false;
        fakeCanvas.listeners.click({
            cancelable: true,
            preventDefault() { prevented = true; }
        });

        const jumpStateAfterClick = current.getState();
        cleanup();

        console.log(JSON.stringify({
            initialY: state1.y,
            updatedY: state2.y,
            updatedVy: state2.vy,
            jumpVy: state3.vy,
            controlJumpVy: jumpStateAfterClick.vy,
            prevented,
            isFrozen: Object.isFrozen(state1)
        }));
    '''

    result = subprocess.run(["node", "--input-type=module", "-e", node_script], capture_output=True, text=True)
    assert result.returncode == 0, f"Node execution failed: {result.stderr}"
    
    data = json.loads(result.stdout.strip())
    assert data["initialY"] == 50
    assert data["updatedY"] == 50.5
    assert data["updatedVy"] == 0.5
    assert data["jumpVy"] == -8
    assert data["controlJumpVy"] == -10  # default jumpStrength
    assert data["prevented"] is True
    assert data["isFrozen"] is True
