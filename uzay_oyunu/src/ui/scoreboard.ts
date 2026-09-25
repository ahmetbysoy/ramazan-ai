export enum AsteroidSizeTier {
  LARGE = 'LARGE',
  MEDIUM = 'MEDIUM',
  SMALL = 'SMALL'
}

export const ASTEROID_SCORES: Record<AsteroidSizeTier, number> = {
  [AsteroidSizeTier.LARGE]: 20,
  [AsteroidSizeTier.MEDIUM]: 50,
  [AsteroidSizeTier.SMALL]: 100
};

export class ScoreBoard {
  private current: number = 0;
  private highScore: number = 0;
  private storageKey: string;
  private storage: Storage | null;

  constructor(storageKey: string = 'space_rocks_high_score', storage: Storage | null = typeof window !== 'undefined' ? window.localStorage : null) {
    this.storageKey = storageKey;
    this.storage = storage;
    this.highScore = this.loadHighScore();
  }

  public getScore(): number {
    return this.current;
  }

  public getHighScore(): number {
    return this.highScore;
  }

  public addScore(points: number): void {
    if (points > 0) {
      this.current += points;
      if (this.current > this.highScore) {
        this.highScore = this.current;
        this.saveHighScore(this.highScore);
      }
    }
  }

  public addAsteroidScore(tier: AsteroidSizeTier): void {
    const points = ASTEROID_SCORES[tier] || 0;
    this.addScore(points);
  }

  public resetScore(): void {
    this.current = 0;
  }

  private loadHighScore(): number {
    if (!this.storage) return 0;
    try {
      const saved = this.storage.getItem(this.storageKey);
      if (saved !== null) {
        const parsed = parseInt(saved, 10);
        return isNaN(parsed) ? 0 : parsed;
      }
    } catch (e) {
      // Fallback if storage is blocked or unavailable
    }
    return 0;
  }

  private saveHighScore(score: number): void {
    if (!this.storage) return;
    try {
      this.storage.setItem(this.storageKey, score.toString());
    } catch (e) {
      // Fallback if storage is blocked or unavailable
    }
  }
}
