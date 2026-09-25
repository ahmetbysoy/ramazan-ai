import { describe, it, expect, vi } from 'vitest';
import {
  checkCircleCollision,
  checkAABBCollision,
  checkCircleAABBCollision,
  SpatialGrid,
  processCollisions,
  Collidable
} from '../../src/engine/collision';

describe('Collision Detection System', () => {
  describe('Circle Collision', () => {
    it('detects overlapping circles', () => {
      const c1 = { x: 0, y: 0, radius: 10 };
      const c2 = { x: 15, y: 0, radius: 10 };
      expect(checkCircleCollision(c1, c2)).toBe(true);
    });

    it('detects non-overlapping circles', () => {
      const c1 = { x: 0, y: 0, radius: 10 };
      const c2 = { x: 25, y: 0, radius: 10 };
      expect(checkCircleCollision(c1, c2)).toBe(false);
    });

    it('detects touching circles', () => {
      const c1 = { x: 0, y: 0, radius: 10 };
      const c2 = { x: 20, y: 0, radius: 10 };
      expect(checkCircleCollision(c1, c2)).toBe(true);
    });
  });

  describe('AABB Collision', () => {
    it('detects overlapping bounding boxes', () => {
      const b1 = { x: 0, y: 0, width: 10, height: 10 };
      const b2 = { x: 5, y: 5, width: 10, height: 10 };
      expect(checkAABBCollision(b1, b2)).toBe(true);
    });

    it('detects non-overlapping bounding boxes', () => {
      const b1 = { x: 0, y: 0, width: 10, height: 10 };
      const b2 = { x: 15, y: 15, width: 10, height: 10 };
      expect(checkAABBCollision(b1, b2)).toBe(false);
    });
  });

  describe('Circle-AABB Collision', () => {
    it('detects circle overlapping box', () => {
      const circle = { x: 12, y: 5, radius: 5 };
      const box = { x: 0, y: 0, width: 10, height: 10 };
      expect(checkCircleAABBCollision(circle, box)).toBe(true);
    });

    it('detects circle not overlapping box', () => {
      const circle = { x: 20, y: 20, radius: 5 };
      const box = { x: 0, y: 0, width: 10, height: 10 };
      expect(checkCircleAABBCollision(circle, box)).toBe(false);
    });
  });

  describe('Spatial Grid Partitioning', () => {
    it('bins and retrieves potential collisions correctly', () => {
      const grid = new SpatialGrid<Collidable>(50);
      const item1: Collidable = { id: '1', type: 'asteroid', x: 25, y: 25, radius: 10, active: true };
      const item2: Collidable = { id: '2', type: 'projectile', x: 30, y: 30, radius: 2, active: true };
      const item3: Collidable = { id: '3', type: 'asteroid', x: 200, y: 200, radius: 10, active: true };

      grid.insert(item1);
      grid.insert(item2);
      grid.insert(item3);

      const pairs = grid.getPotentialCollisions();
      expect(pairs.length).toBe(1);
      expect(pairs[0]).toEqual([item1, item2]);
    });

    it('ignores inactive items', () => {
      const grid = new SpatialGrid<Collidable>(50);
      const item1: Collidable = { id: '1', type: 'asteroid', x: 25, y: 25, radius: 10, active: false };
      const item2: Collidable = { id: '2', type: 'projectile', x: 30, y: 30, radius: 2, active: true };

      grid.insert(item1);
      grid.insert(item2);

      const pairs = grid.getPotentialCollisions();
      expect(pairs.length).toBe(0);
    });
  });

  describe('Collision Processing and Callbacks', () => {
    it('triggers projectile-asteroid collision callbacks', () => {
      const projectile: Collidable = { id: 'p1', type: 'projectile', x: 100, y: 100, radius: 2, active: true };
      const asteroid: Collidable = { id: 'a1', type: 'asteroid', x: 102, y: 100, radius: 15, active: true };

      const onProjectileAsteroid = vi.fn();
      processCollisions([projectile, asteroid], { onProjectileAsteroid });

      expect(onProjectileAsteroid).toHaveBeenCalledWith(projectile, asteroid);
    });

    it('triggers player-asteroid collision callbacks (loss of life / game over)', () => {
      const player: Collidable = { id: 'player1', type: 'player', x: 500, y: 500, radius: 12, active: true };
      const asteroid: Collidable = { id: 'a2', type: 'asteroid', x: 505, y: 500, radius: 20, active: true };

      const onPlayerAsteroid = vi.fn();
      processCollisions([player, asteroid], { onPlayerAsteroid });

      expect(onPlayerAsteroid).toHaveBeenCalledWith(player, asteroid);
    });
  });
});
