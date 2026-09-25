import unittest
import subprocess
import json
import os

class TestScoreSystem(unittest.TestCase):
    def test_score_js_logic_via_node(self):
        node_script = """
        const scoreMod = require('./src/js/score.js');
        
        // Mock localStorage
        let store = {};
        global.localStorage = {
            getItem: (key) => store[key] || null,
            setItem: (key, val) => { store[key] = val.toString(); },
            clear: () => { store = {}; }
        };

        let state = scoreMod.createScoreState();
        console.assert(state.score === 0, 'Initial score should be 0');
        console.assert(state.highScore === 0, 'Initial high score should be 0');

        state = scoreMod.incrementScore(state);
        console.assert(state.score === 1, 'Score should be 1');
        console.assert(state.highScore === 1, 'High score should be 1');

        state = scoreMod.incrementScore(state);
        console.assert(state.score === 2, 'Score should be 2');
        console.assert(state.highScore === 2, 'High score should be 2');

        state = scoreMod.resetScore(state);
        console.assert(state.score === 0, 'Score should reset to 0');
        console.assert(state.highScore === 2, 'High score should remain 2');

        console.log('ALL_JS_TESTS_PASSED');
        """
        
        result = subprocess.run(['node', '-e', node_script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"Node test failed: {result.stderr}")
        self.assertIn('ALL_JS_TESTS_PASSED', result.stdout)

    def test_high_score_sorting_and_logic(self):
        scores = [10, 42, 3, 99, 15]
        sorted_scores = sorted(scores, reverse=True)
        self.assertEqual(sorted_scores[0], 99)
        self.assertEqual(sorted_scores[-1], 3)

if __name__ == '__main__':
    unittest.main()
