/**
 * UI Manager for Game Overlays, Start Screen, Score Display, and High Score Table.
 */
class UIManager {
    constructor(container = document.body) {
        this.container = container;
        this.initDOM();
    }

    initDOM() {
        // Create main UI container overlay
        this.uiRoot = document.createElement('div');
        this.uiRoot.id = 'game-ui';
        this.uiRoot.style.position = 'absolute';
        this.uiRoot.style.top = '0';
        this.uiRoot.style.left = '0';
        this.uiRoot.style.width = '100%';
        this.uiRoot.style.height = '100%';
        this.uiRoot.style.pointerEvents = 'none';
        this.uiRoot.style.fontFamily = 'sans-serif';

        // Live Score Display
        this.scoreDisplay = document.createElement('div');
        this.scoreDisplay.id = 'live-score';
        this.scoreDisplay.style.position = 'absolute';
        this.scoreDisplay.style.top = '20px';
        this.scoreDisplay.style.width = '100%';
        this.scoreDisplay.style.textAlign = 'center';
        this.scoreDisplay.style.fontSize = '32px';
        this.scoreDisplay.style.fontWeight = 'bold';
        this.scoreDisplay.style.color = '#fff';
        this.scoreDisplay.style.textShadow = '2px 2px #000';
        this.scoreDisplay.textContent = '0';
        this.uiRoot.appendChild(this.scoreDisplay);

        // Start Screen Overlay
        this.startScreen = document.createElement('div');
        this.startScreen.id = 'start-screen';
        this.startScreen.style.position = 'absolute';
        this.startScreen.style.top = '0';
        this.startScreen.style.left = '0';
        this.startScreen.style.width = '100%';
        this.startScreen.style.height = '100%';
        this.startScreen.style.backgroundColor = 'rgba(0,0,0,0.5)';
        this.startScreen.style.display = 'flex';
        this.startScreen.style.flexDirection = 'column';
        this.startScreen.style.justifyContent = 'center';
        this.startScreen.style.alignItems = 'center';
        this.startScreen.style.pointerEvents = 'auto';

        const title = document.createElement('h1');
        title.textContent = 'FLAPPY BIRD';
        title.style.color = '#fff';
        title.style.marginBottom = '20px';
        this.startScreen.appendChild(title);

        this.startButton = document.createElement('button');
        this.startButton.id = 'start-button';
        this.startButton.textContent = 'START GAME';
        this.startButton.style.padding = '12px 24px';
        this.startButton.style.fontSize = '18px';
        this.startButton.style.cursor = 'pointer';
        this.startScreen.appendChild(this.startButton);
        this.uiRoot.appendChild(this.startScreen);

        // Game Over Screen Overlay
        this.gameOverScreen = document.createElement('div');
        this.gameOverScreen.id = 'game-over-screen';
        this.gameOverScreen.style.position = 'absolute';
        this.gameOverScreen.style.top = '0';
        this.gameOverScreen.style.left = '0';
        this.gameOverScreen.style.width = '100%';
        this.gameOverScreen.style.height = '100%';
        this.gameOverScreen.style.backgroundColor = 'rgba(0,0,0,0.7)';
        this.gameOverScreen.style.display = 'none';
        this.gameOverScreen.style.flexDirection = 'column';
        this.gameOverScreen.style.justifyContent = 'center';
        this.gameOverScreen.style.alignItems = 'center';
        this.gameOverScreen.style.pointerEvents = 'auto';

        const gameOverTitle = document.createElement('h2');
        gameOverTitle.textContent = 'GAME OVER';
        gameOverTitle.style.color = '#ff4444';
        gameOverTitle.style.marginBottom = '10px';
        this.gameOverScreen.appendChild(gameOverTitle);

        this.finalScoreDisplay = document.createElement('div');
        this.finalScoreDisplay.id = 'final-score';
        this.finalScoreDisplay.style.color = '#fff';
        this.finalScoreDisplay.style.fontSize = '20px';
        this.finalScoreDisplay.style.marginBottom = '20px';
        this.finalScoreDisplay.textContent = 'Score: 0';
        this.gameOverScreen.appendChild(this.finalScoreDisplay);

        const highScoreHeader = document.createElement('h3');
        highScoreHeader.textContent = 'High Scores';
        highScoreHeader.style.color = '#fff';
        highScoreHeader.style.marginBottom = '10px';
        this.gameOverScreen.appendChild(highScoreHeader);

        this.highScoreTable = document.createElement('ol');
        this.highScoreTable.id = 'high-score-table';
        this.highScoreTable.style.color = '#fff';
        this.highScoreTable.style.marginBottom = '20px';
        this.gameOverScreen.appendChild(this.highScoreTable);

        this.restartButton = document.createElement('button');
        this.restartButton.id = 'restart-button';
        this.restartButton.textContent = 'RESTART';
        this.restartButton.style.padding = '10px 20px';
        this.restartButton.style.fontSize = '16px';
        this.restartButton.style.cursor = 'pointer';
        this.gameOverScreen.appendChild(this.restartButton);

        this.uiRoot.appendChild(this.gameOverScreen);
        this.container.appendChild(this.uiRoot);
    }

    showStartScreen() {
        this.startScreen.style.display = 'flex';
        this.gameOverScreen.style.display = 'none';
        this.scoreDisplay.style.display = 'none';
    }

    showGameScreen() {
        this.startScreen.style.display = 'none';
        this.gameOverScreen.style.display = 'none';
        this.scoreDisplay.style.display = 'block';
    }

    showGameOverScreen(finalScore, highScores = []) {
        this.startScreen.style.display = 'none';
        this.scoreDisplay.style.display = 'none';
        this.gameOverScreen.style.display = 'flex';
        this.finalScoreDisplay.textContent = `Score: ${finalScore}`;

        // Populate high score table
        this.highScoreTable.innerHTML = '';
        highScores.forEach(entry => {
            const li = document.createElement('li');
            li.textContent = `${entry.score} - ${new Date(entry.date).toLocaleDateString()}`;
            this.highScoreTable.appendChild(li);
        });
    }

    updateScore(score) {
        this.scoreDisplay.textContent = String(score);
    }

    bindStart(callback) {
        this.startButton.addEventListener('click', callback);
    }

    bindRestart(callback) {
        this.restartButton.addEventListener('click', callback);
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = UIManager;
}
