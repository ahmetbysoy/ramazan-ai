import { Vector2D } from '../core/vector';
import { GameObject, InputState } from '../core/types';
import { Projectile, createProjectile } from './projectile';

export interface Spaceship extends GameObject {
  velocity: Vector2D;
  rotation: number;
  radius: number;
  cooldown: number;
  cooldownMax: number;
  speed: number;
}

export function createSpaceship(x: number, y: number): Spaceship {
  return {
    id: 'player_spaceship',
    position: { x, y },
    velocity: { x: 0, y: 0 },
    rotation: -Math.PI / 2,
    radius: 20,
    cooldown: 0,
    cooldownMax: 0.15,
    speed: 300,
  };
}

export interface UpdateResult {
  spaceship: Spaceship;
  projectiles: Projectile[];
}

export function updateSpaceship(
  ship: Spaceship,
  input: InputState,
  dt: number,
  canvasWidth: number,
  canvasHeight: number
):
  UpdateResult {
  let newRotation = ship.rotation;
  if (input.keys['ArrowLeft'] || input.keys['KeyA']) {
    newRotation -= Math.PI * 2 * dt;
  }
  if (input.keys['ArrowRight'] || input.keys['KeyD']) {
    newRotation += Math.PI * 2 * dt;
  }

  let moveX = 0;
  let moveY = 0;
  if (input.keys['ArrowUp'] || input.keys['KeyW']) {
    moveX += Math.cos(newRotation);
    moveY += Math.sin(newRotation);
  }
  if (input.keys['ArrowDown'] || input.keys['KeyS']) {
    moveX -= Math.cos(newRotation);
    moveY -= Math.sin(newRotation);
  }

  const velocity: Vector2D = {
    x: moveX * ship.speed,
    y: moveY * ship.speed,
  };

  let newX = ship.position.x + velocity.x * dt;
  let newY = ship.position.y + velocity.y * dt;

  newX = Math.max(ship.radius, Math.min(canvasWidth - ship.radius, newX));
  newY = Math.max(ship.radius, Math.min(canvasHeight - ship.radius, newY));

  let newCooldown = Math.max(0, ship.cooldown - dt);
  const newProjectiles: Projectile[] = [];

  if (input.keys['Space'] && newCooldown <= 0) {
    const noseX = newX + Math.cos(newRotation) * ship.radius;
    const noseY = newY + Math.sin(newRotation) * ship.radius;
    newProjectiles.push(createProjectile(noseX, noseY, newRotation));
    newCooldown = ship.cooldownMax;
  }

  const updatedShip: Spaceship = {
    ...ship,
    position: { x: newX, y: newY },
    velocity,
    rotation: newRotation,
    cooldown: newCooldown,
  };

  return {
    spaceship: updatedShip,
    projectiles: newProjectiles,
  };
}
