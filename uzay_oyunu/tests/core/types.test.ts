import { describe, it, expect } from 'vitest';
import { GameState, GameObject, InputState, Vector2DData } from '../../src/core/types';

describe('Core Types and Interfaces', () => {
  it('should validate Vector2DData structure and readonly properties', () => {
    const data: Vector2DData = { x: 10, y: 20 };
    expect(data.x).toBe(10);
    expect(data.y).toBe(20);

    expect(() => {
      (data as any).x = 30;
    }).toThrow();
  });

  it('should validate GameObject structure and readonly properties', () => {
    const obj: GameObject = {
      id: 'player-1',
      position: { x: 0, y: 0 },
      velocity: { x: 1, y: 1 },
      rotation: 0,
    };

    expect(obj.id).toBe('player-1');
    expect(obj.position.x).toBe(0);
    expect(obj.velocity.y).toBe(1);
    expect(obj.rotation).toBe(0);

    expect(() => {
      (obj as any).id = 'player-2';
    }).toThrow();
  });

  it('should validate InputState structure and readonly properties', () => {
    const keys = new Set(['ArrowUp', 'Space']);
    const input: InputState = {
      keysPressed: keys,
      mousePosition: { x: 100, y: 200 },
      mouseDown: false,
    };

    expect(input.keysPressed.has('ArrowUp')).toBe(true);
    expect(input.mousePosition.x).toBe(100);
    expect(input.mouseDown).toBe(false);

    expect(() => {
      (input as any).mouseDown = true;
    }).toThrow();
  });

  it('should validate GameState structure and readonly properties', () => {
    const entities = new Map<string, GameObject>();
    const state: GameState = {
      timestamp: 123456789,
      entities,
      input: {
        keysPressed: new Set(),
        mousePosition: { x: 0, y: 0 },
        mouseDown: false,
      },
    };

    expect(state.timestamp).toBe(123456789);
    expect(state.entities).toBe(entities);

    expect(() => {
      (state as any).timestamp = 999999;
    }).toThrow();
  });
});
