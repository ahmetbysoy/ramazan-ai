export interface Vector2D {
  x: number;
  y: number;
}

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface CircleCollider {
  x: number;
  y: number;
  radius: number;
}

export interface Collidable {
  id: string;
  type: 'player' | 'asteroid' | 'projectile';
  x: number;
  y: number;
  radius: number;
  width?: number;
  height?: number;
  active: boolean;
}

export class SpatialGrid<T extends Collidable> {
  private cellSize: number;
  private cells: Map<string, Set<T>>;

  constructor(cellSize: number = 100) {
    this.cellSize = cellSize;
    this.cells = new Map();
  }

  public clear(): void {
    this.cells.clear();
  }

  private getKey(x: number, y: number): string {
    const cx = Math.floor(x / this.cellSize);
    const cy = Math.floor(y / this.cellSize);
    return `${cx},${cy}`;
  }

  public insert(item: T): void {
    if (!item.active) return;
    const minX = item.x - item.radius;
    const maxX = item.x + item.radius;
    const minY = item.y - item.radius;
    const maxY = item.y + item.radius;

    const startX = Math.floor(minX / this.cellSize);
    const endX = Math.floor(maxX / this.cellSize);
    const startY = Math.floor(minY / this.cellSize);
    const endY = Math.floor(maxY / this.cellSize);

    for (let x = startX; x <= endX; x++) {
      for (let y = startY; y <= endY; y++) {
        const key = `${x},${y}`;
        if (!this.cells.has(key)) {
          this.cells.set(key, new Set());
        }
        this.cells.get(key)!.add(item);
      }
    }
  }

  public getPotentialCollisions(): [T, T][] {
    const pairs = new Set<string>();
    const results: [T, T][] = [];

    for (const cell of this.cells.values()) {
      const items = Array.from(cell);
      for (let i = 0; i < items.length; i++) {
        for (let j = i + 1; j < items.length; j++) {
          const a = items[i];
          const b = items[j];
          if (a.id === b.id) continue;

          const id1 = a.id < b.id ? a.id : b.id;
          const id2 = a.id < b.id ? b.id : a.id;
          const pairKey = `${id1}-${id2}`;

          if (!pairs.has(pairKey)) {
            pairs.add(pairKey);
            results.push(a.id === id1 ? [a, b] : [b, a]);
          }
        }
      }
    }

    return results;
  }
}

export function checkCircleCollision(c1: CircleCollider, c2: CircleCollider): boolean {
  const dx = c1.x - c2.x;
  const dy = c1.y - c2.y;
  const distanceSquared = dx * dx + dy * dy;
  const radiusSum = c1.radius + c2.radius;
  return distanceSquared <= radiusSum * radiusSum;
}

export function checkAABBCollision(b1: BoundingBox, b2: BoundingBox): boolean {
  return (
    b1.x < b2.x + b2.width &&
    b1.x + b1.width > b2.x &&
    b1.y < b2.y + b2.height &&
    b1.y + b1.height > b2.y
  );
}

export function checkCircleAABBCollision(circle: CircleCollider, box: BoundingBox): boolean {
  const closestX = Math.max(box.x, Math.min(circle.x, box.x + box.width));
  const closestY = Math.max(box.y, Math.min(circle.y, box.y + box.height));

  const dx = circle.x - closestX;
  const dy = circle.y - closestY;

  return (dx * dx + dy * dy) <= (circle.radius * circle.radius);
}

export interface CollisionCallback {
  onProjectileAsteroid?: (projectile: Collidable, asteroid: Collidable) => void;
  onPlayerAsteroid?: (player: Collidable, asteroid: Collidable) => void;
}

export function processCollisions<T extends Collidable>(
  items: T[],
  callbacks: CollisionCallback,
  cellSize: number = 100
): void {
  const grid = new SpatialGrid<T>(cellSize);
  for (const item of items) {
    grid.insert(item);
  }

  const potentialPairs = grid.getPotentialCollisions();

  for (const [a, b] of potentialPairs) {
    if (!a.active || !b.active) continue;

    if (checkCircleCollision(a, b)) {
      const types = [a.type, b.type].sort();

      if (types[0] === 'asteroid' && types[1] === 'projectile') {
        const asteroid = a.type === 'asteroid' ? a : b;
        const projectile = a.type === 'projectile' ? a : b;
        callbacks.onProjectileAsteroid?.(projectile, asteroid);
      } else if (types[0] === 'asteroid' && types[1] === 'player') {
        const asteroid = a.type === 'asteroid' ? a : b;
        const player = a.type === 'player' ? a : b;
        callbacks.onPlayerAsteroid?.(player, asteroid);
      }
    }
  }
}
