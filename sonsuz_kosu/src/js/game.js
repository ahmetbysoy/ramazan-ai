class Game {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            throw new Error(`Canvas with id '${canvasId}' not found.`);
        }
        this.ctx = this.canvas.getContext('2d');
        this.isRunning = false;
        this.lastTime = 0;

        this.loop = this.loop.bind(this);
    }

    start() {
        if (this.isRunning) return;
        this.isRunning = true;
        this.lastTime = performance.now();
        requestAnimationFrame(this.loop);
    }

    stop() {
        this.isRunning = false;
    }

    update(dt) {
        // Game update logic placeholder
    }

    render() {
        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }

    loop(timestamp) {
        if (!this.isRunning) return;

        const dt = (timestamp - this.lastTime) / 1000;
        this.lastTime = timestamp;

        this.update(dt);
        this.render();

        requestAnimationFrame(this.loop);
    }
}

// Initialize and start game on window load if canvas exists
if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        try {
            const game = new Game('gameCanvas');
            game.start();
            window.gameInstance = game; // Export for testing/debug
        } catch (e) {
            console.error(e);
        }
    });
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = Game;
}
