import { describe, it, expect } from 'vitest';
import { createSpaceship, updateSpaceship } from '../../src/entities/spaceship';
import { createProjectile, updateProjectile } from '../../src/entities/projectile';
import { InputState } from '../../src/core/types';

describe('Spaceship and Projectile Entities', () => {
  const emptyInput: InputState = {
    keys: {},
    pointer: { x: 0, y: 0, isDown: false },
    actions: { fire: false, thrust: false },
  };

  it('should create a spaceship with default properties', () => {
    const ship = createSpaceship(100, 200);
    expect(ship.position).toEqual({ x: 100, y: 200 });
    expect(ship.radius).toBe(20);
    expect(ship.cooldown).toBe(0);
  });

  it('should respect canvas boundaries on movement', () => {
    const ship = createSpaceship(10, 10);
    const input: InputState = {
      ...emptyInput,
      keys: { 'ArrowUp': true, 'ArrowLeft': true },
    };
    // Move violently towards top-left boundary
    const result = updateSpaceship(ship, input, 1.0, 800, 600);
    expect(result.spaceship.position.x).toBeGreaterThanOrEqual(result.spaceship.radius);
    expect(result.spaceship.position.y).toBeGreaterThanOrEqual(result.spaceship.radius);
  });

  it('should fire projectiles respecting cooldown', () => {
    const ship = createSpaceship(400, 300);
    const input: InputState = {
      ...emptyInput,
      keys: { 'Space': true },
    };

    const res1 = updateSpaceship(ship, input, 0.016, 800, 600);
    expect(res1.projectiles.length).toBe(1);
    expect(res1.spaceship.cooldown).toBeGreaterThan(0);

    // Try firing immediately during cooldown
    const res2 = updateSpaceship(res1.spaceship, input, 0.016, 800, 600);
    expect(res2.projectiles.length).toBe(0);
  });

  it('should update and deactivate projectiles outside canvas boundaries', () => {
    const proj = createProjectile(795, 300, 0, 1000);
    const updated = updateProjectile(proj, 0.1, 800, 600);
    expect(updated.active).toBe(false);
  });
});
