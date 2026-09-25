export class Vector2D {
  public readonly x: number;
  public readonly y: number;

  constructor(x: number = 0, y: number = 0) {
    this.x = x;
    this.y = y;
    Object.freeze(this);
  }

  public add(v: Vector2D): Vector2D {
    return new Vector2D(this.x + v.x, this.y + v.y);
  }

  public subtract(v: Vector2D): Vector2D {
    return new Vector2D(this.x - v.x, this.y - v.y);
  }

  public multiply(scalar: number): Vector2D {
    return new Vector2D(this.x * scalar, this.y * scalar);
  }

  public divide(scalar: number): Vector2D {
    if (scalar === 0) {
      throw new Error("Division by zero");
    }
    return new Vector2D(this.x / scalar, this.y / scalar);
  }

  public magnitude(): number {
    return Math.sqrt(this.x * this.x + this.y * this.y);
  }

  public normalize(): Vector2D {
    const mag = this.magnitude();
    if (mag === 0) {
      return new Vector2D(0, 0);
    }
    return this.divide(mag);
  }

  public dot(v: Vector2D): number {
    return this.x * v.x + this.y * v.y;
  }

  public distance(v: Vector2D): number {
    return this.subtract(v).magnitude();
  }

  public clone(): Vector2D {
    return new Vector2D(this.x, this.y);
  }
}
