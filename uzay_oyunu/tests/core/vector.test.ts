import { describe, it, expect } from 'vitest';
import { Vector2D } from '../../src/core/vector';
import { GameObject, InputState, GameState, Vector2DData } from '../../src/core/types';

describe('Vector2D', () => {
  it('should initialize with default values', () => {
    const v = new Vector2D();
    expect(v.x).toBe(0);
    expect(v.y).toBe(0);
  });

  it('should enforce immutability', () => {
    const v = new Vector2D(1, 2);
    expect(Object.isFrozen(v)).toBe(true);
    expect(() => {
      (v as any).x = 5;
    }).toThrow();
  });

  it('should add vectors without mutating operands', () => {
    const v1 = new Vector2D(1, 2);
    const v2 = new Vector2D(3, 4);
    const result = v1.add(v2);

    expect(result.x).toBe(4);
    expect(result.y).toBe(6);
    expect(v1.x).toBe(1);
    expect(v1.y).toBe(2);
    expect(v2.x).toBe(3);
    expect(v2.y).toBe(4);
  });

  it('should subtract vectors without mutating operands', () => {
    const v1 = new Vector2D(5, 7);
    const v2 = new Vector2D(2, 3);
    const result = v1.subtract(v2);

    expect(result.x).toBe(3);
    expect(result.y).toBe(4);
    expect(v1.x).toBe(5);
    expect(v1.y).toBe(7);
  });

  it('should multiply by scalar without mutating operand', () => {
    const v = new Vector2D(2, 3);
    const result = v.multiply(3);

    expect(result.x).toBe(6);
    expect(result.y).toBe(9);
    expect(v.x).toBe(2);
    expect(v.y).toBe(3);
  });

  it('should divide by scalar without mutating operand', () => {
    const v = new Vector2D(6, 9);
    const result = v.divide(3);

    expect(result.x).toBe(2);
    expect(result.y).toBe(3);
    expect(v.x).toBe(6);
    expect(v.y).toBe(9);
  });

  it('should throw error on division by zero', () => {
    const v = new Vector2D(1, 1);
    expect(() => v.divide(0)).toThrow('Division by zero');
  });

  it('should calculate magnitude correctly', () => {
    const v = new Vector2D(3, 4);
    expect(v.magnitude()).toBe(5);
  });

  it('should normalize vector correctly', () => {
    const v = new Vector2D(3, 4);
    const result = v.normalize();

    expect(result.x).toBe(0.6);
    expect(result.y).toBe(0.8);
    expect(result.magnitude()).toBeCloseTo(1);
  });

  it('should handle normalization of zero vector', () => {
    const v = new Vector2D(0, 0);
    const result = v.normalize();
    expect(result.x).toBe(0);
    expect(result.y).toBe(0);
  });

  it('should calculate dot product correctly', () => {
    const v1 = new Vector2D(1, 2);
    const v2 = new Vector2D(3, 4);
    expect(v1.dot(v2)).toBe(11);
  });

  it('should calculate distance correctly', () => {
    const v1 = new Vector2D(1, 1);
    const v2 = new Vector2D(4, 5);
    expect(v1.distance(v2)).toBe(5);
  });

  it('should clone vector correctly', () => {
    const v = new Vector2D(1, 2);
    const clone = v.clone();
    expect(clone).not.toBe(v);
    expect(clone.x).toBe(v.x);
    expect(clone.y).toBe(v.y);
  });
});

describe('Core Types Structure and Immutability', () => {
  it('should correctly structure and type GameObject, InputState, and GameState', () => {
    const pos: Vector2DData = { x: 10, y: 20 };
    const vel: Vector2DData = { x: 1, y: 2 };
    
    const gameObject: GameObject = {
      id: 'obj-1',
      position: pos,
      velocity: vel,
      rotation: 0.5,
    };

    expect(gameObject.id).toBe('obj-1');
    expect(gameObject.position.x).toBe(10);
    expect(gameObject.velocity.y).toBe(2);
    expect(gameObject.rotation).toBe(0.5);

    const inputState: InputState = {
      keysPressed: new Set(['ArrowUp', 'Space']),
      mousePosition: { x: 100, y: 200 },
      mouseDown: false,
    };

    expect(inputState.keysPressed.has('ArrowUp')).toBe(true);
    expect(inputState.mousePosition.x).toBe(100);
    expect(inputState.mouseDown).toBe(false);

    const entitiesMap = new Map<string, GameObject>();
    entitiesMap.set(gameObject.id, gameObject);

    const gameState: GameState = {
      timestamp: 123456789,
      entities: entitiesMap,
      input: inputState,
    };

    expect(gameState.timestamp).toBe(123456789);
    expect(gameState.entities.get('obj-1')).toEqual(gameObject);
    expect(gameState.input).toEqual(inputState);
  });
});
