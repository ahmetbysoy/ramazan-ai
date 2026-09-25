import { ScoreBoard, AsteroidSizeTier, ASTEROID_SCORES } from '../../src/ui/scoreboard';

class MockStorage implements Storage {
  private store: Record<string, string> = {};
  
  get length(): number {
    return Object.keys(this.store).length;
  }

  clear(): void {
    this.store = {};
  }

  getItem(key: string): string | null {
    return Object.prototype.hasOwnProperty.call(this.store, key) ? this.store[key] : null;
  }

  key(index: number): string | null {
    const keys = Object.keys(this.store);
    return keys[index] !== undefined ? keys[index] : null;
  }

  removeItem(key: string): void {
    delete this.store[key];
  }

  setItem(key: string, value: string): void {
    this.store[key] = value;
  }
}

describe('ScoreBoard', () => {
  let mockStorage: MockStorage;

  beforeEach(() => {
    mockStorage = new MockStorage();
  });

  test('initializes with zero score and high score', () => {
    const sb = new ScoreBoard('test_hs', mockStorage);
    expect(sb.getScore()).toBe(0);
    expect(sb.getHighScore()).toBe(0);
  });

  test('adds points correctly and updates high score', () => {
    const sb = new ScoreBoard('test_hs', mockStorage);
    sb.addScore(50);
    expect(sb.getScore()).toBe(50);
    expect(sb.getHighScore()).toBe(50);
    expect(mockStorage.getItem('test_hs')).toBe('50');
  });

  test('adds scores based on asteroid size tier correctly', () => {
    const sb = new ScoreBoard('test_hs', mockStorage);
    
    sb.addAsteroidScore(AsteroidSizeTier.LARGE);
    expect(sb.getScore()).toBe(ASTEROID_SCORES[AsteroidSizeTier.LARGE]);

    sb.addAsteroidScore(AsteroidSizeTier.MEDIUM);
    expect(sb.getScore()).toBe(ASTEROID_SCORES[AsteroidSizeTier.LARGE] + ASTEROID_SCORES[AsteroidSizeTier.MEDIUM]);

    sb.addAsteroidScore(AsteroidSizeTier.SMALL);
    expect(sb.getScore()).toBe(
      ASTEROID_SCORES[AsteroidSizeTier.LARGE] +
      ASTEROID_SCORES[AsteroidSizeTier.MEDIUM] +
      ASTEROID_SCORES[AsteroidSizeTier.SMALL]
    );
  });

  test('resets current score without resetting high score', () => {
    const sb = new ScoreBoard('test_hs', mockStorage);
    sb.addScore(150);
    expect(sb.getHighScore()).toBe(150);
    
    sb.resetScore();
    expect(sb.getScore()).toBe(0);
    expect(sb.getHighScore()).toBe(150);
  });

  test('loads existing high score from storage on initialization', () => {
    mockStorage.setItem('test_hs', '500');
    const sb = new ScoreBoard('test_hs', mockStorage);
    expect(sb.getHighScore()).toBe(500);
    expect(sb.getScore()).toBe(0);
  });

  test('handles missing or null storage gracefully', () => {
    const sb = new ScoreBoard('test_hs', null);
    sb.addScore(100);
    expect(sb.getScore()).toBe(100);
    expect(sb.getHighScore()).toBe(100);
  });
});
