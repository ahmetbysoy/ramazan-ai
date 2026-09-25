import { InputState } from '../core/types';
import { Vector2D } from '../core/vector';

export class InputManager {
  private state: InputState = {
    vector: { x: 0, y: 0 },
    action: false,
  };

  private keysPressed: Set<string> = new Set();
  private activePointerId: number | null = null;
  private touchStartPos: Vector2D | null = null;
  private currentTouchPos: Vector2D | null = null;
  private maxJoystickRadius: number = 50;

  private boundOnKeyDown: (e: KeyboardEvent) => void;
  private boundOnKeyUp: (e: KeyboardEvent) => void;
  private boundOnPointerDown: (e: PointerEvent) => void;
  private boundOnPointerMove: (e: PointerEvent) => void;
  private boundOnPointerUp: (e: PointerEvent) => void;

  constructor(private targetWindow: Window & typeof globalThis = window) {
    this.boundOnKeyDown = this.handleKeyDown.bind(this);
    this.boundOnKeyUp = this.handleKeyUp.bind(this);
    this.boundOnPointerDown = this.handlePointerDown.bind(this);
    this.boundOnPointerMove = this.handlePointerMove.bind(this);
    this.boundOnPointerUp = this.handlePointerUp.bind(this);

    if (this.targetWindow && this.targetWindow.addEventListener) {
      this.targetWindow.addEventListener('keydown', this.boundOnKeyDown);
      this.targetWindow.addEventListener('keyup', this.boundOnKeyUp);
      this.targetWindow.addEventListener('pointerdown', this.boundOnPointerDown);
      this.targetWindow.addEventListener('pointermove', this.boundOnPointerMove);
      this.targetWindow.addEventListener('pointerup', this.boundOnPointerUp);
      this.targetWindow.addEventListener('pointercancel', this.boundOnPointerUp);
    }
  }

  public getState(): Readonly<InputState> {
    return {
      vector: { ...this.state.vector },
      action: this.state.action,
    };
  }

  public update(): void {
    let x = 0;
    let y = 0;

    // Keyboard priority or combination
    if (this.keysPressed.has('ArrowLeft') || this.keysPressed.has('KeyA')) x -= 1;
    if (this.keysPressed.has('ArrowRight') || this.keysPressed.has('KeyD')) x += 1;
    if (this.keysPressed.has('ArrowUp') || this.keysPressed.has('KeyW')) y -= 1;
    if (this.keysPressed.has('ArrowDown') || this.keysPressed.has('KeyS')) y += 1;

    const action = this.keysPressed.has('Space');

    if (x !== 0 || y !== 0) {
      // Normalize keyboard vector if diagonal
      const len = Math.sqrt(x * x + y * y);
      if (len > 0) {
        this.state = {
          vector: { x: x / len, y: y / len },
          action,
        };
      }
    } else if (this.touchStartPos && this.currentTouchPos) {
      const dx = this.currentTouchPos.x - this.touchStartPos.x;
      const dy = this.currentTouchPos.y - this.touchStartPos.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      
      if (dist === 0) {
        this.state = { vector: { x: 0, y: 0 }, action };
      } else {
        const clampedDist = Math.min(dist, this.maxJoystickRadius);
        const nx = (dx / dist) * (clampedDist / this.maxJoystickRadius);
        const ny = (dy / dist) * (clampedDist / this.maxJoystickRadius);
        this.state = {
          vector: { x: nx, y: ny },
          action,
        };
      }
    } else {
      this.state = {
        vector: { x: 0, y: 0 },
        action,
      };
    }
  }

  private handleKeyDown(e: KeyboardEvent): void {
    this.keysPressed.add(e.code);
  }

  private handleKeyUp(e: KeyboardEvent): void {
    this.keysPressed.delete(e.code);
  }

  private handlePointerDown(e: PointerEvent): void {
    if (this.activePointerId === null) {
      this.activePointerId = e.pointerId;
      this.touchStartPos = { x: e.clientX, y: e.clientY };
      this.currentTouchPos = { x: e.clientX, y: e.clientY };
    }
  }

  private handlePointerMove(e: PointerEvent): void {
    if (this.activePointerId === e.pointerId && this.touchStartPos) {
      this.currentTouchPos = { x: e.clientX, y: e.clientY };
    }
  }

  private handlePointerUp(e: PointerEvent): void {
    if (this.activePointerId === e.pointerId) {
      this.activePointerId = null;
      this.touchStartPos = null;
      this.currentTouchPos = null;
    }
  }

  public destroy(): void {
    if (this.targetWindow && this.targetWindow.removeEventListener) {
      this.targetWindow.removeEventListener('keydown', this.boundOnKeyDown);
      this.targetWindow.removeEventListener('keyup', this.boundOnKeyUp);
      this.targetWindow.removeEventListener('pointerdown', this.boundOnPointerDown);
      this.targetWindow.removeEventListener('pointermove', this.boundOnPointerMove);
      this.targetWindow.removeEventListener('pointerup', this.boundOnPointerUp);
      this.targetWindow.removeEventListener('pointercancel', this.boundOnPointerUp);
    }
  }
}
