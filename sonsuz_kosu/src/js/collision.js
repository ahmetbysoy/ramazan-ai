'use strict';

const GameState = Object.freeze({
  START: 'START',
  PLAYING: 'PLAYING',
  GAME_OVER: 'GAME_OVER'
});

class GameStateManager {
  constructor() {
    this._state = GameState.START;
  }

  setState(newState) {
    if (Object.values(GameState).includes(newState) && newState !== this._state) {
      this._state = newState;
    }
    return this._state;
  }

  getState() {
    return this._state;
  }

  reset() {
    this._state = GameState.START;
    return this._state;
  }
}

function checkAABB(box1, box2) {
  return (
    box1.x < box2.x + box2.width &&
    box1.x + box1.width > box2.x &&
    box1.y < box2.y + box2.height &&
    box1.y + box1.height > box2.y
  );
}

function checkCanvasCollision(player, canvasHeight) {
  if (player.y < 0 || player.y + player.height > canvasHeight) {
    return true;
  }
  return false;
}

function checkCollisions(player, pipes, canvasHeight) {
  if (checkCanvasCollision(player, canvasHeight)) {
    return true;
  }
  for (const pipe of pipes) {
    const topBox = { x: pipe.x, y: 0, width: pipe.width, height: pipe.topHeight };
    const bottomBox = { x: pipe.x, y: pipe.bottomY, width: pipe.width, height: pipe.bottomHeight };
    if (checkAABB(player, topBox) || checkAABB(player, bottomBox)) {
      return true;
    }
  }
  return false;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    GameState,
    GameStateManager,
    checkAABB,
    checkCanvasCollision,
    checkCollisions
  };
}
