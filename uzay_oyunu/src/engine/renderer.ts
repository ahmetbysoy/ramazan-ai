export interface RendererConfig {
  width: number;
  height: number;
  scale?: number;
}

export interface DrawOptions {
  fillStyle?: string;
  strokeStyle?: string;
  lineWidth?: number;
  font?: string;
  textAlign?: CanvasTextAlign;
  textBaseline?: CanvasTextBaseline;
}

export class Renderer {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private width: number;
  private height: number;
  private scale: number;
  private dpr: number;

  constructor(canvas: HTMLCanvasElement, config: RendererConfig) {
    this.canvas = canvas;
    const context = canvas.getContext('2d');
    if (!context) {
      throw new Error('Failed to get 2D context from canvas');
    }
    this.ctx = context;
    this.width = config.width;
    this.height = config.height;
    this.scale = config.scale ?? 1;
    this.dpr = (typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1) * this.scale;

    this.initCanvas();
  }

  public initCanvas(): void {
    this.canvas.width = this.width * this.dpr;
    this.canvas.height = this.height * this.dpr;
    this.canvas.style.width = `${this.width}px`;
    this.canvas.style.height = `${this.height}px`;
    this.ctx.scale(this.dpr, this.dpr);
  }

  public getContext(): CanvasRenderingContext2D {
    return this.ctx;
  }

  public getWidth(): number {
    return this.width;
  }

  public getHeight(): number {
    return this.height;
  }

  public clear(color: string = '#000000'): void {
    this.ctx.save();
    this.ctx.fillStyle = color;
    this.ctx.fillRect(0, 0, this.width, this.height);
    this.ctx.restore();
  }

  public drawRect(x: number, y: number, w: number, h: number, options: DrawOptions = {}): void {
    this.ctx.save();
    if (options.fillStyle) {
      this.ctx.fillStyle = options.fillStyle;
      this.ctx.fillRect(x, y, w, h);
    }
    if (options.strokeStyle && options.lineWidth) {
      this.ctx.strokeStyle = options.strokeStyle;
      this.ctx.lineWidth = options.lineWidth;
      this.ctx.strokeRect(x, y, w, h);
    }
    this.ctx.restore();
  }

  public drawCircle(x: number, y: number, radius: number, options: DrawOptions = {}): void {
    this.ctx.save();
    this.ctx.beginPath();
    this.ctx.arc(x, y, radius, 0, Math.PI * 2);
    if (options.fillStyle) {
      this.ctx.fillStyle = options.fillStyle;
      this.ctx.fill();
    }
    if (options.strokeStyle && options.lineWidth) {
      this.ctx.strokeStyle = options.strokeStyle;
      this.ctx.lineWidth = options.lineWidth;
      this.ctx.stroke();
    }
    this.ctx.restore();
  }

  public drawLine(x1: number, y1: number, x2: number, y2: number, options: DrawOptions = {}): void {
    this.ctx.save();
    this.ctx.beginPath();
    this.ctx.moveTo(x1, y1);
    this.ctx.lineTo(x2, y2);
    if (options.strokeStyle && options.lineWidth) {
      this.ctx.strokeStyle = options.strokeStyle;
      this.ctx.lineWidth = options.lineWidth;
      this.ctx.stroke();
    }
    this.ctx.restore();
  }

  public drawText(text: string, x: number, y: number, options: DrawOptions = {}): void {
    this.ctx.save();
    if (options.font) this.ctx.font = options.font;
    if (options.textAlign) this.ctx.textAlign = options.textAlign;
    if (options.textBaseline) this.ctx.textBaseline = options.textBaseline;
    if (options.fillStyle) {
      this.ctx.fillStyle = options.fillStyle;
      this.ctx.fillText(text, x, y);
    }
    if (options.strokeStyle && options.lineWidth) {
      this.ctx.strokeStyle = options.strokeStyle;
      this.ctx.lineWidth = options.lineWidth;
      this.ctx.strokeText(text, x, y);
    }
    this.ctx.restore();
  }

  public drawSprite(
    image: CanvasImageSource,
    sx: number,
    sy: number,
    sw: number,
    sh: number,
    dx: number,
    dy: number,
    dw: number,
    dh: number
  ): void {
    this.ctx.drawImage(image, sx, sy, sw, sh, dx, dy, dw, dh);
  }
}
