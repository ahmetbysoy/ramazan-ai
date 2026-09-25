/**
 * Pipes obstacle management module for Flappy Bird clone.
 */
(function(window) {
    'use strict';

    function PipeManager(options) {
        options = options || {};
        this.canvasWidth = options.canvasWidth || 400;
        this.canvasHeight = options.canvasHeight || 600;
        this.pipeWidth = options.pipeWidth || 60;
        this.pipeGap = options.pipeGap || 150;
        this.spawnInterval = options.spawnInterval || 200; // pixels between pipes
        this.speed = options.speed || 3;
        this.minHeight = 50;
        this.maxHeight = this.canvasHeight - this.pipeGap - 50;

        this.pipes = [];
        this.distanceSinceLastSpawn = this.spawnInterval;
    }

    PipeManager.prototype.reset = function() {
        this.pipes = [];
        this.distanceSinceLastSpawn = this.spawnInterval;
    };

    PipeManager.prototype.update = function(dt) {
        dt = (dt !== undefined && dt !== null) ? dt : 1;

        // Move existing pipes leftwards scaled by dt
        for (var i = 0; i < this.pipes.length; i++) {
            this.pipes[i].x -= this.speed * dt;
        }

        // Recycle off-screen pipes
        if (this.pipes.length > 0 && this.pipes[0].x + this.pipeWidth < 0) {
            this.pipes.shift();
        }

        // Handle spawning scaled by dt
        var moveDist = this.speed * dt;
        this.distanceSinceLastSpawn += moveDist;
        if (this.pipes.length === 0 || this.distanceSinceLastSpawn >= this.spawnInterval) {
            this.spawnPipe();
            this.distanceSinceLastSpawn = 0;
        }
    };

    PipeManager.prototype.spawnPipe = function() {
        var topHeight = Math.floor(Math.random() * (this.maxHeight - this.minHeight + 1)) + this.minHeight;
        var x = this.canvasWidth;
        if (this.pipes.length > 0) {
            var lastPipe = this.pipes[this.pipes.length - 1];
            x = Math.max(this.canvasWidth, lastPipe.x + this.spawnInterval);
        }

        this.pipes.push({
            x: x,
            topHeight: topHeight,
            bottomY: topHeight + this.pipeGap,
            bottomHeight: this.canvasHeight - (topHeight + this.pipeGap),
            passed: false
        });
    };

    PipeManager.prototype.render = function(ctx) {
        if (!ctx) return;
        ctx.fillStyle = '#228B22'; // Forest Green
        for (var i = 0; i < this.pipes.length; i++) {
            var p = this.pipes[i];
            // Top pipe
            ctx.fillRect(p.x, 0, this.pipeWidth, p.topHeight);
            // Bottom pipe
            ctx.fillRect(p.x, p.bottomY, this.pipeWidth, p.bottomHeight);
        }
    };

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = PipeManager;
    } else {
        window.PipeManager = PipeManager;
    }
})(typeof window !== 'undefined' ? window : global);
