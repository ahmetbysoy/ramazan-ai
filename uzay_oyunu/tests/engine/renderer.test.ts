import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Renderer } from '../../src/engine/renderer';

describe('Renderer Engine', () => {
  let canvas: HTMLCanvasElement;
  let renderer: Renderer;
  let mockCtx: any;

  beforeEach(() => {
    mockCtx = {
      scale: vi.fn(),
      save: vi.fn(),
      restore: vi.fn(),
      fillRect: vi.fn(),
      strokeRect: vi.fn(),
      beginPath: vi.fn(),
      arc: vi.fn(),
      fill: vi.fn(),
      stroke: vi.fn(),
      moveTo: vi.fn(),
      lineTo: vi.fn(),
      fillText: vi.fn(),
      strokeText: vi.fn(),
      drawImage: vi.fn(),
      fillStyle: '',
      strokeStyle: '',
      lineWidth: 1,
      font: '',
      textAlign: 'left',
      textBaseline: 'alphabetic',
    };

    canvas = {
      width: 0,
      height: 0,
      style: { width: '', height: '' },
      getContext: vi.fn().mockReturnValue(mockCtx),
    } as unknown as HTMLCanvasElement;

    renderer = new Renderer(canvas, { width: 800, height: 600 });
  });

  it('initializes canvas dimensions and high-DPI scaling correctly', () => {
    expect(canvas.getContext).toHaveBeenCalledWith('2d');
    expect(canvas.width).toBe(800 * (window.devicePixelRatio || 1));
    expect(canvas.height).toBe(600 * (window.devicePixelRatio || 1));
    expect(canvas.style.width).toBe('800px');
    expect(canvas.style.height).toBe('600px');
    expect(mockCtx.scale).toHaveBeenCalledWith(
      window.devicePixelRatio || 1,
      window.devicePixelRatio || 1
    );
    expect(renderer.getWidth()).toBe(800);
    expect(renderer.getHeight()).toBe(600);
    expect(renderer.getContext()).toBe(mockCtx);
  });

  it('incorporates custom scale config into scaling calculations', () => {
    const scaleCanvas = {
      width: 0,
      height: 0,
      style: { width: '', height: '' },
      getContext: vi.fn().mockReturnValue(mockCtx),
    } as unknown as HTMLCanvasElement;

    const customRenderer = new Renderer(scaleCanvas, { width: 400, height: 300, scale: 2 });
    const expectedScale = (window.devicePixelRatio || 1) * 2;

    expect(scaleCanvas.width).toBe(400 * expectedScale);
    expect(scaleCanvas.height).toBe(300 * expectedScale);
    expect(mockCtx.scale).toHaveBeenCalledWith(expectedScale, expectedScale);
  });

  it('throws error if canvas 2d context cannot be acquired', () => {
    const badCanvas = {
      getContext: vi.fn().mockReturnValue(null),
    } as unknown as HTMLCanvasElement;

    expect(() => new Renderer(badCanvas, { width: 100, height: 100 })).toThrow(
      'Failed to get 2D context from canvas'
    );
  });

  it('clears canvas correctly', () => {
    renderer.clear('#ff0000');
    expect(mockCtx.save).toHaveBeenCalled();
    expect(mockCtx.fillStyle).toBe('#ff0000');
    expect(mockCtx.fillRect).toHaveBeenCalledWith(0, 0, 800, 600);
    expect(mockCtx.restore).toHaveBeenCalled();
  });

  it('draws rectangles with fill and stroke options', () => {
    renderer.drawRect(10, 20, 100, 50, {
      fillStyle: '#00ff00',
      strokeStyle: '#0000ff',
      lineWidth: 2,
    });
    expect(mockCtx.save).toHaveBeenCalled();
    expect(mockCtx.fillStyle).toBe('#00ff00');
    expect(mockCtx.fillRect).toHaveBeenCalledWith(10, 20, 100, 50);
    expect(mockCtx.strokeStyle).toBe('#0000ff');
    expect(mockCtx.lineWidth).toBe(2);
    expect(mockCtx.strokeRect).toHaveBeenCalledWith(10, 20, 100, 50);
    expect(mockCtx.restore).toHaveBeenCalled();
  });

  it('handles drawRect with missing or partial options gracefully', () => {
    renderer.drawRect(10, 20, 100, 50);
    expect(mockCtx.fillRect).not.toHaveBeenCalled();
    expect(mockCtx.strokeRect).not.toHaveBeenCalled();

    renderer.drawRect(10, 20, 100, 50, { strokeStyle: '#ff0000' });
    expect(mockCtx.strokeRect).not.toHaveBeenCalled();
  });

  it('draws circles correctly', () => {
    renderer.drawCircle(50, 50, 25, { fillStyle: '#ffffff' });
    expect(mockCtx.save).toHaveBeenCalled();
    expect(mockCtx.beginPath).toHaveBeenCalled();
    expect(mockCtx.arc).toHaveBeenCalledWith(50, 50, 25, 0, Math.PI * 2);
    expect(mockCtx.fillStyle).toBe('#ffffff');
    expect(mockCtx.fill).toHaveBeenCalled();
    expect(mockCtx.restore).toHaveBeenCalled();
  });

  it('draws lines correctly', () => {
    renderer.drawLine(0, 0, 100, 100, { strokeStyle: '#111111', lineWidth: 3 });
    expect(mockCtx.save).toHaveBeenCalled();
    expect(mockCtx.beginPath).toHaveBeenCalled();
    expect(mockCtx.moveTo).toHaveBeenCalledWith(0, 0);
    expect(mockCtx.lineTo).toHaveBeenCalledWith(100, 100);
    expect(mockCtx.strokeStyle).toBe('#111111');
    expect(mockCtx.lineWidth).toBe(3);
    expect(mockCtx.stroke).toHaveBeenCalled();
    expect(mockCtx.restore).toHaveBeenCalled();
  });

  it('draws text correctly with styling options', () => {
    renderer.drawText('Hello Engine', 200, 200, {
      font: '16px sans-serif',
      textAlign: 'center',
      textBaseline: 'middle',
      fillStyle: '#123456',
    });
    expect(mockCtx.save).toHaveBeenCalled();
    expect(mockCtx.font).toBe('16px sans-serif');
    expect(mockCtx.textAlign).toBe('center');
    expect(mockCtx.textBaseline).toBe('middle');
    expect(mockCtx.fillStyle).toBe('#123456');
    expect(mockCtx.fillText).toHaveBeenCalledWith('Hello Engine', 200, 200);
    expect(mockCtx.restore).toHaveBeenCalled();
  });

  it('draws sprites correctly', () => {
    const mockImage = {} as CanvasImageSource;
    renderer.drawSprite(mockImage, 0, 0, 32, 32, 10, 10, 64, 64);
    expect(mockCtx.drawImage).toHaveBeenCalledWith(mockImage, 0, 0, 32, 32, 10, 10, 64, 64);
  });
});
