import { Vector2D } from '../core/vector';
import { GameObject } from '../core/types';

export interface Projectile extends GameObject {
  velocity: Vector2D;
  radius: number;
  active: boolean;
}

export function createProjectile(x: number, y: number, angle: number, speed: number = 600): Projectile {
  const velocity: Vector2D = {
    x: Math.cos(angle) * speed,
    y: Math.sin(angle) * speed,
  };
  return {
    id: `proj_${Math.random().toString(36).substr(2, 9)}`,
    position: { x, y },
    velocity,
    radius: 4,
    active: true,
  };
}

export function updateProjectile(projectile: Projectile, dt: number, canvasWidth: number, canvasHeight: number): Projectile {
  if (!projectile.active) return projectile;

  const newX = projectile.position.x + projectile.velocity.x * dt;
  const newY = projectile.position.y + projectile.velocity.y * dt;

  const active =
    newX >= 0 && newX <= canvasWidth && newY >= 0 && newY <= canvasHeight;

  return {
    ...projectile,
    position: { x: newX, y: newY },
    active,
  };
}
