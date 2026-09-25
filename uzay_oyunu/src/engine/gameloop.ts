export type GameState = 'Start' | 'Playing' | 'Paused' | 'GameOver';

export interface GameLoopCallbacks {
  onUpdate?: (dt: number) => void;
  onRender?: () => void;
  onStateChange?: (newState: GameState, oldState: GameState) => void;
}

export class GameLoop {
  private state: GameState = 'Start';
  private lastTime: number = 0;
  private animationFrameId: number | null = null;
  private isRunning: boolean = false;
  private callbacks: GameLoopCallbacks;
  private maxDelta: number = 0.1; // Cap delta time to prevent spiral of death

  constructor(callbacks: GameLoopCallbacks = {}) {
    this.callbacks = callbacks;
  }

  public getState(): GameState {
    return this.state;
  }

  public setState(newState: GameState): void {
    if (this.state !== newState) {
      const oldState = this.state;
      this.state = newState;
      if (this.callbacks.onStateChange) {
        this.callbacks.onStateChange(newState, oldState);
      }
    }
  }

  public start(): void {
    if (this.isRunning) return;
    this.isRunning = true;
    this.lastTime = performance.now();
    this.animationFrameId = requestAnimationFrame(this.loop);
  }

  public stop(): void {
    if (!this.isRunning) return;
    this.isRunning = false;
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
  }

  private loop = (currentTime: number): void => {
    if (!this.isRunning) return;

    this.tick(currentTime);

    this.animationFrameId = requestAnimationFrame(this.loop);
  };

  public tick(currentTime: number): void {
    let dt = (currentTime - this.lastTime) / 1000;
    this.lastTime = currentTime;

    if (dt > this.maxDelta) {
      dt = this.maxDelta;
    }

    if (this.state === 'Playing') {
      if (this.callbacks.onUpdate) {
        this.callbacks.onUpdate(dt);
      }
    }

    if (this.callbacks.onRender) {
      this.callbacks.onRender();
    }
  }
}
