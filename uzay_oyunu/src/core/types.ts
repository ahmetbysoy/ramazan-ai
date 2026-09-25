export interface Vector2DData {
  readonly x: number;
  readonly y: number;
}

export interface GameObject {
  readonly id: string;
  readonly position: Vector2DData;
  readonly velocity: Vector2DData;
  readonly rotation: number;
}

export interface InputState {
  readonly keysPressed: ReadonlySet<string>;
  readonly mousePosition: Vector2DData;
  readonly mouseDown: boolean;
}

export interface GameState {
  readonly timestamp: number;
  readonly entities: ReadonlyMap<string, GameObject>;
  readonly input: InputState;
}
