import { GameLoop, GameState } from '../../src/engine/gameloop';

describe('GameLoop and State Controller', () => {
  let requestAnimationFrameSpy: jest.SpyInstance;
  let cancelAnimationFrameSpy: jest.SpyInstance;
  let performanceNowSpy: jest.SpyInstance;

  beforeEach(() => {
    requestAnimationFrameSpy = jest.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
      return 123;
    });
    cancelAnimationFrameSpy = jest.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {});
    performanceNowSpy = jest.spyOn(performance, 'now').mockReturnValue(1000);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('initializes with Start state', () => {
    const loop = new GameLoop();
    expect(loop.getState()).toBe('Start');
  });

  test('allows changing states and triggers onStateChange callback', () => {
    const onStateChange = jest.fn();
    const loop = new GameLoop({ onStateChange });

    expect(loop.getState()).toBe('Start');

    loop.setState('Playing');
    expect(loop.getState()).toBe('Playing');
    expect(onStateChange).toHaveBeenCalledWith('Playing', 'Start');

    // Setting same state should not trigger callback
    loop.setState('Playing');
    expect(onStateChange).toHaveBeenCalledTimes(1);

    loop.setState('Paused');
    expect(loop.getState()).toBe('Paused');
    expect(onStateChange).toHaveBeenCalledWith('Paused', 'Playing');

    loop.setState('GameOver');
    expect(loop.getState()).toBe('GameOver');
    expect(onStateChange).toHaveBeenCalledWith('GameOver', 'Paused');
  });

  test('starts and stops correctly', () => {
    const loop = new GameLoop();
    loop.start();
    expect(requestAnimationFrameSpy).toHaveBeenCalled();

    loop.stop();
    expect(cancelAnimationFrameSpy).toHaveBeenCalledWith(123);

    // Calling stop/start multiple times safely
    loop.stop();
    loop.start();
  });

  test('executes continuous requestAnimationFrame loop asynchronously', () => {
    let rafCallback: ((time: number) => void) | null = null;
    requestAnimationFrameSpy.mockImplementation((cb) => {
      rafCallback = cb;
      return 456;
    });

    const onUpdate = jest.fn();
    const onRender = jest.fn();
    const loop = new GameLoop({ onUpdate, onRender });
    loop.setState('Playing');

    performanceNowSpy.mockReturnValue(1000);
    loop.start();

    expect(requestAnimationFrameSpy).toHaveBeenCalled();
    expect(rafCallback).not.toBeNull();

    // Simulate first frame at 1016ms
    if (rafCallback) {
      (rafCallback as (time: number) => void)(1016);
    }

    expect(onUpdate).toHaveBeenCalledWith(0.016);
    expect(onRender).toHaveBeenCalled();

    // Simulate second frame continuing the loop
    if (rafCallback) {
      (rafCallback as (time: number) => void)(1032);
    }

    expect(onUpdate).toHaveBeenCalledTimes(2);

    loop.stop();
  });

  test('tick updates and renders correctly when Playing', () => {
    const onUpdate = jest.fn();
    const onRender = jest.fn();
    const loop = new GameLoop({ onUpdate, onRender });

    loop.setState('Playing');

    performanceNowSpy.mockReturnValue(1000);
    loop.tick(1000);

    performanceNowSpy.mockReturnValue(1016); // 16ms delta
    loop.tick(1016);

    expect(onUpdate).toHaveBeenCalledWith(0.016);
    expect(onRender).toHaveBeenCalled();
  });

  test('tick renders but does not update when not Playing', () => {
    const onUpdate = jest.fn();
    const onRender = jest.fn();
    const loop = new GameLoop({ onUpdate, onRender });

    loop.setState('Start');

    performanceNowSpy.mockReturnValue(1000);
    loop.tick(1000);
    performanceNowSpy.mockReturnValue(1016);
    loop.tick(1016);

    expect(onUpdate).not.toHaveBeenCalled();
    expect(onRender).toHaveBeenCalled();
  });

  test('caps delta time to prevent spiral of death', () => {
    const onUpdate = jest.fn();
    const loop = new GameLoop({ onUpdate });

    loop.setState('Playing');

    performanceNowSpy.mockReturnValue(1000);
    loop.tick(1000);

    // Huge gap of 500ms (0.5s), should be capped at maxDelta (0.1s)
    performanceNowSpy.mockReturnValue(1500);
    loop.tick(1500);

    expect(onUpdate).toHaveBeenCalledWith(0.1);
  });
});
