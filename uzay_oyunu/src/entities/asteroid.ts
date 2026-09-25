import { Vector2D, addVector, multiplyVector, createVector } from '../core/vector';
import { GameObject } from '../core/types';

export enum AsteroidSize {
  LARGE = 'LARGE',
  MEDIUM = 'MEDIUM',
  SMALL = 'SMALL'
}

export interface Asteroid extends GameObject {
  size: AsteroidSize;
  radius: number;
  velocity: Vector2D;
  rotationSpeed: number;
  rotation: number;
}

export const ASTEROID_PROPERTIES = {
  [AsteroidSize.LARGE]: { radius: 40, speedMin: 50, speedMax: 100, score: 20 },
  [AsteroidSize.MEDIUM]: { radius: 20, speedMin: 80, speedMax: 140, score: 50 },
  [AsteroidSize.SMALL]: { radius: 10, speedMin: 120, speedMax: 200, score: 100 }
};

export function createAsteroid(position: Vector2D, size: AsteroidSize, velocity?: Vector2D, id?: string): Asteroid {
  const props = ASTEROID_PROPERTIES[size];
  const speed = velocity ? Math.hypot(velocity.x, velocity.y) : (props.speedMin + Math.random() * (props.speedMax - props.speedMin));
  
  let finalVelocity = velocity;
  if (!finalVelocity) {
    const angle = Math.random() * Math.PI * 2;
    finalVelocity = createVector(Math.cos(angle) * speed, Math.sin(angle) * speed);
  }

  return Object.freeze({
    id: id || crypto.randomUUID(),
    position: Object.freeze({ ...position }),
    velocity: Object.freeze({ ...finalVelocity }),
    size,
    radius: props.radius,
    rotationSpeed: (Math.random() - 0.5) * 2,
    rotation: Math.random() * Math.PI * 2,
    active: true
  });
}

export function updateAsteroid(asteroid: Asteroid, dt: number, canvasWidth: number, canvasHeight: number): Asteroid {
  const newPos = addVector(asteroid.position, multiplyVector(asteroid.velocity, dt));
  
  // Robust modulo-based screen wrapping accounting for radius
  const minX = -asteroid.radius;
  const maxX = canvasWidth + asteroid.radius;
  const minY = -asteroid.radius;
  const maxY = canvasHeight + asteroid.radius;

  const widthSpan = maxX - minX;
  const heightSpan = maxY - minY;

  const wrappedX = minX + ((newPos.x - minX) % widthSpan + widthSpan) % widthSpan;
  const wrappedY = minY + ((newPos.y - minY) % heightSpan + heightSpan) % heightSpan;

  return Object.freeze({
    ...asteroid,
    position: createVector(wrappedX, wrappedY),
    rotation: asteroid.rotation + asteroid.rotationSpeed * dt
  });
}

export function spawnAsteroidAtBoundary(canvasWidth: number, canvasHeight: number, size: AsteroidSize = AsteroidSize.LARGE): Asteroid {
  let x = 0;
  let y = 0;
  const side = Math.floor(Math.random() * 4);

  switch (side) {
    case 0: // Top
      x = Math.random() * canvasWidth;
      y = -50;
      break;
    case 1: // Right
      x = canvasWidth + 50;
      y = Math.random() * canvasHeight;
      break;
    case 2: // Bottom
      x = Math.random() * canvasWidth;
      y = canvasHeight + 50;
      break;
    case 3: // Left
      x = -50;
      y = Math.random() * canvasHeight;
      break;
  }

  // Target generally towards center with some randomness
  const centerX = canvasWidth / 2;
  const centerY = canvasHeight / 2;
  const angleToCenter = Math.atan2(centerY - y, centerX - x) + (Math.random() - 0.5) * 0.5;
  
  const props = ASTEROID_PROPERTIES[size];
  const speed = props.speedMin + Math.random() * (props.speedMax - props.speedMin);
  const velocity = createVector(Math.cos(angleToCenter) * speed, Math.sin(angleToCenter) * speed);

  return createAsteroid(createVector(x, y), size, velocity);
}

export function splitAsteroid(asteroid: Asteroid): Asteroid[] {
  if (asteroid.size === AsteroidSize.SMALL) {
    return [];
  }

  const nextSize = asteroid.size === AsteroidSize.LARGE ? AsteroidSize.MEDIUM : AsteroidSize.SMALL;
  const currentSpeed = Math.hypot(asteroid.velocity.x, asteroid.velocity.y);
  const currentAngle = Math.atan2(asteroid.velocity.y, asteroid.velocity.x);

  const angleOffset = Math.PI / 4; // 45 degrees divergence
  const speedMultiplier = 1.2; // Children slightly faster
  const newSpeed = currentSpeed * speedMultiplier;

  const angle1 = currentAngle + angleOffset;
  const angle2 = currentAngle - angleOffset;

  const v1 = createVector(Math.cos(angle1) * newSpeed, Math.sin(angle1) * newSpeed);
  const v2 = createVector(Math.cos(angle2) * newSpeed, Math.sin(angle2) * newSpeed);

  return [
    createAsteroid(asteroid.position, nextSize, v1),
    createAsteroid(asteroid.position, nextSize, v2)
  ];
}

export function checkAsteroidCollision(asteroid: Asteroid, point: Vector2D): boolean {
  const dx = asteroid.position.x - point.x;
  const dy = asteroid.position.y - point.y;
  const distanceSquared = dx * dx + dy * dy;
  return distanceSquared <= asteroid.radius * asteroid.radius;
}
