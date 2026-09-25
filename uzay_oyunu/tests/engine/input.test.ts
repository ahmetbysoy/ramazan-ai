import { InputManager } from '../../src/engine/input';

describe('InputManager', () => {
  let mockWindow: any;
  let listeners: { [key: string]: EventListener[] };

  beforeEach(() => {
    listeners = {};
    mockWindow = {
      addEventListener: (event: string, cb: EventListener) => {
        if (!listeners[event]) listeners[event] = [];
        listeners[event].push(cb);
      },
      removeEventListener: (event: string, cb: EventListener) => {
        if (listeners[event]) {
          listeners[event] = listeners[event].filter(l => l !== cb);
        }
      },
    };
  });

  const triggerEvent = (event: string, data: any) => {
    if (listeners[event]) {
      listeners[event].forEach(cb => cb(data as any));
    }
  };

  test('should initialize with zero state and immutable getState return', () => {
    const manager = new InputManager(mockWindow);
    const state1 = manager.getState();
    const state2 = manager.getState();

    expect(state1).toEqual({ vector: { x: 0, y: 0 }, action: false });
    expect(state1).not.toBe(state2); // Immutability check
    manager.destroy();
  });

  test('should handle keyboard input (WASD / Arrows and Space)', () => {
    const manager = new InputManager(mockWindow);

    triggerEvent('keydown', { code: 'KeyW' });
    triggerEvent('keydown', { code: 'Space' });
    manager.update();

    let state = manager.getState();
    expect(state.vector.y).toBeLessThan(0);
    expect(state.action).toBe(true);

    triggerEvent('keyup', { code: 'KeyW' });
    triggerEvent('keyup', { code: 'Space' });
    manager.update();

    state = manager.getState();
    expect(state.vector).toEqual({ x: 0, y: 0 });
    expect(state.action).toBe(false);

    manager.destroy();
  });

  test('should normalize diagonal keyboard input vectors', () => {
    const manager = new InputManager(mockWindow);

    triggerEvent('keydown', { code: 'KeyW' });
    triggerEvent('keydown', { code: 'KeyD' });
    manager.update();

    const state = manager.getState();
    const length = Math.sqrt(state.vector.x * state.vector.x + state.vector.y * state.vector.y);
    expect(length).toBeCloseTo(1, 5);

    manager.destroy();
  });

  test('should handle touch/pointer input correctly as virtual joystick', () => {
    const manager = new InputManager(mockWindow);

    triggerEvent('pointerdown', { pointerId: 1, clientX: 100, clientY: 100 });
    triggerEvent('pointermove', { pointerId: 1, clientX: 130, clientY: 140 });
    manager.update();

    const state = manager.getState();
    // dx = 30, dy = 40, dist = 50 -> normalized vector (0.6, 0.8)
    expect(state.vector.x).toBeCloseTo(0.6, 2);
    expect(state.vector.y).toBeCloseTo(0.8, 2);

    triggerEvent('pointerup', { pointerId: 1, clientX: 130, clientY: 140 });
    manager.update();

    const releasedState = manager.getState();
    expect(releasedState.vector).toEqual({ x: 0, y: 0 });

    manager.destroy();
  });
});
