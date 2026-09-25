/**
 * Score Manager and LocalStorage High Score Table
 */

const HIGH_SCORE_KEY = 'flappy_bird_high_score';

/**
 * Creates an initial score state object.
 * @returns {Object} Frozen score state
 */
function createScoreState() {
  return Object.freeze({
    score: 0,
    highScore: loadHighScore()
  });
}

/**
 * Increments the current score.
 * @param {Object} state - Current score state
 * @returns {Object} New score state with incremented score and updated high score
 */
function incrementScore(state) {
  const newScore = state.score + 1;
  const newHighScore = Math.max(newScore, state.highScore);
  saveHighScore(newHighScore);
  return Object.freeze({
    score: newScore,
    highScore: newHighScore
  });
}

/**
 * Resets the current score while preserving or updating high score.
 * @param {Object} state - Current score state
 * @returns {Object} New score state with score reset to 0
 */
function resetScore(state) {
  return Object.freeze({
    score: 0,
    highScore: state.highScore
  });
}

/**
 * Loads high score from localStorage safely.
 * @returns {number}
 */
function loadHighScore() {
  try {
    if (typeof localStorage !== 'undefined') {
      const stored = localStorage.getItem(HIGH_SCORE_KEY);
      return stored !== null ? parseInt(stored, 10) || 0 : 0;
    }
  } catch (e) {
    // Fallback if localStorage is unavailable
  }
  return 0;
}

/**
 * Saves high score to localStorage safely.
 * @param {number} highScore 
 */
function saveHighScore(highScore) {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(HIGH_SCORE_KEY, highScore.toString());
    }
  } catch (e) {
    // Fallback if localStorage is unavailable
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    createScoreState,
    incrementScore,
    resetScore,
    loadHighScore,
    saveHighScore
  };
}
