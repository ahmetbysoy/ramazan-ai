import { describe, it, expect } from 'vitest';
import { AsteroidSize, createAsteroid, updateAsteroid, spawnAsteroidAtBoundary, splitAsteroid, checkAsteroidCollision, ASTEROID_PROPERTIES } from '../../src/entities/asteroid';
import { createVector } from '../../src/core/vector';

describe('Asteroid Entity System', () => {
  it('should create an asteroid with correct properties and immutability', () => {
    const pos = createVector(100, 200);
    const asteroid = createAsteroid(pos, AsteroidSize.LARGE);

    expect(asteroid.id).toBeDefined();
    expect(typeof asteroid.id).toBe('string');
    expect(asteroid.size).toBe(AsteroidSize.LARGE);
    expect(asteroid.radius).toBe(ASTEROID_PROPERTIES[AsteroidSize.LARGE].radius);
    expect(asteroid.active).toBe(true);
    expect(Object.isFrozen(asteroid)).toBe(true);
    expect(Object.isFrozen(asteroid.position)).toBe(true);
    expect(Object.isFrozen(asteroid.velocity)).toBe(true);
  });

  it('should update position and handle screen wrapping correctly', () => {
    const pos = createVector(790, 590);
    const vel = createVector(100, 100);
    const asteroid = createAsteroid(pos, AsteroidSize.SMALL, vel);

    const updated = updateAsteroid(asteroid, 0.5, 800, 600);
    expect(updated.position.x).toBeLessThan(800);
    expect(updated.position.y).toBeLessThan(600);
  });

  it('should handle left screen wrap correctly when crossing negative boundary', () => {
    const pos = createVector(-5, 100);
    const vel = createVector(-50, 0);
    const asteroid = createAsteroid(pos, AsteroidSize.SMALL, vel);

    const updated = updateAsteroid(asteroid, 0.5, 800, 600);
    expect(updated.position.x).toBeCloseTo(800 + asteroid.radius);
  });

  it('should spawn asteroids at canvas boundaries with inward directed velocities', () => {
    const canvasWidth = 800;
    const canvasHeight = 600;
    const asteroid = spawnAsteroidAtBoundary(canvasWidth, canvasHeight, AsteroidSize.LARGE);

    expect(asteroid.active).toBe(true);
    expect(asteroid.size).toBe(AsteroidSize.LARGE);
    
    // Verify spawn is outside or at boundary
    const isOutside = asteroid.position.x < 0 || asteroid.position.x > canvasWidth ||
                      asteroid.position.y < 0 || asteroid.position.y > canvasHeight;
    expect(isOutside).toBe(true);

    // Verify velocity is directed inward (dot product of velocity and vector to center is positive)
    const centerX = canvasWidth / 2;
    const centerY = canvasHeight / 2;
    const toCenterX = centerX - asteroid.position.x;
    const toCenterY = centerY - asteroid.position.y;
    const dotProduct = asteroid.velocity.x * toCenterX + asteroid.velocity.y * toCenterY;
    expect(dotProduct).toBeGreaterThan(0);
  });

  it('should split large and medium asteroids into two rotated child asteroids', () => {
    const pos = createVector(400, 300);
    const vel = createVector(100, 0);
    const largeAsteroid = createAsteroid(pos, AsteroidSize.LARGE, vel);
    const children = splitAsteroid(largeAsteroid);

    expect(children.length).toBe(2);
    expect(children[0].size).toBe(AsteroidSize.MEDIUM);
    expect(children[1].size).toBe(AsteroidSize.MEDIUM);
    expect(children[0].position.x).toBe(pos.x);
    expect(children[0].position.y).toBe(pos.y);

    // Verify children have rotated divergence (speeds preserved/scaled and non-zero)
    const speed0 = Math.hypot(children[0].velocity.x, children[0].velocity.y);
    const speed1 = Math.hypot(children[1].velocity.x, children[1].velocity.y);
    expect(speed0).toBeGreaterThan(0);
    expect(speed1).toBeGreaterThan(0);

    const mediumAsteroid = createAsteroid(pos, AsteroidSize.MEDIUM);
    const smallChildren = splitAsteroid(mediumAsteroid);
    expect(smallChildren.length).toBe(2);
    expect(smallChildren[0].size).toBe(AsteroidSize.SMALL);
  });

  it('should not split small asteroids', () => {
    const pos = createVector(400, 300);
    const smallAsteroid = createAsteroid(pos, AsteroidSize.SMALL);
    const children = splitAsteroid(smallAsteroid);
    expect(children.length).toBe(0);
  });

  it('should correctly detect collisions using bounding radius', () => {
    const pos = createVector(100, 100);
    const asteroid = createAsteroid(pos, AsteroidSize.MEDIUM);

    // Inside radius
    expect(checkAsteroidCollision(asteroid, createVector(105, 105))).toBe(true);
    // Exactly on center
    expect(checkAsteroidCollision(asteroid, createVector(100, 100))).toBe(true);
    // Outside radius
    expect(checkAsteroidCollision(asteroid, createVector(200, 200))).toBe(false);
  });
});
