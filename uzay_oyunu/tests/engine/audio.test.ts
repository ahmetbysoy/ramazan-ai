import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AudioManager } from '../../src/engine/audio';

class MockAudioContext {
  currentTime = 0;
  sampleRate = 44100;
  state = 'suspended';
  destination = {};

  resume = vi.fn().mockResolvedValue(undefined);
  createOscillator = vi.fn().mockReturnValue({
    type: 'sine',
    frequency: {
      setValueAtTime: vi.fn(),
      exponentialRampToValueAtTime: vi.fn(),
    },
    connect: vi.fn(),
    start: vi.fn(),
    stop: vi.fn(),
  });

  createGain = vi.fn().mockReturnValue({
    gain: {
      setValueAtTime: vi.fn(),
      exponentialRampToValueAtTime: vi.fn(),
    },
    connect: vi.fn(),
  });

  createBuffer = vi.fn().mockReturnValue({
    getChannelData: vi.fn().mockReturnValue(new Float32Array(44100 * 0.5)),
  });

  createBufferSource = vi.fn().mockReturnValue({
    buffer: null,
    loop: false,
    connect: vi.fn(),
    start: vi.fn(),
    stop: vi.fn(),
  });

  createBiquadFilter = vi.fn().mockReturnValue({
    type: 'lowpass',
    frequency: {
      setValueAtTime: vi.fn(),
      exponentialRampToValueAtTime: vi.fn(),
    },
    connect: vi.fn(),
  });
}

describe('AudioManager', () => {
  let audioManager: AudioManager;
  let mockContext: MockAudioContext;

  beforeEach(() => {
    vi.restoreAllMocks();
    mockContext = new MockAudioContext();
    vi.stubGlobal('AudioContext', vi.fn().mockImplementation(() => mockContext));
    audioManager = new AudioManager();
  });

  it('should initialize AudioContext correctly on interaction', () => {
    audioManager.init();
    expect(global.AudioContext).toHaveBeenCalledTimes(1);
    expect(mockContext.resume).toHaveBeenCalled();
    expect(mockContext.createBuffer).toHaveBeenCalledTimes(1);
  });

  it('should handle mute and unmute states', () => {
    expect(audioManager.isMuted()).toBe(false);
    audioManager.setMuted(true);
    expect(audioManager.isMuted()).toBe(true);
    audioManager.playLaser();
    expect(mockContext.createOscillator).not.toHaveBeenCalled();
  });

  it('should execute playLaser without throwing errors', () => {
    expect(() => audioManager.playLaser()).not.toThrow();
    expect(mockContext.createOscillator).toHaveBeenCalled();
    expect(mockContext.createGain).toHaveBeenCalled();
  });

  it('should execute playAsteroidExplosion without throwing errors', () => {
    expect(() => audioManager.playAsteroidExplosion()).not.toThrow();
    expect(mockContext.createBuffer).toHaveBeenCalledTimes(1); // Shared buffer only
    expect(mockContext.createBufferSource).toHaveBeenCalled();
    expect(mockContext.createBiquadFilter).toHaveBeenCalled();
  });

  it('should execute playPlayerDestruction without throwing errors', () => {
    expect(() => audioManager.playPlayerDestruction()).not.toThrow();
    expect(mockContext.createOscillator).toHaveBeenCalled();
    expect(mockContext.createBuffer).toHaveBeenCalledTimes(1); // Shared buffer only
    expect(mockContext.createBufferSource).toHaveBeenCalled();
  });
});
