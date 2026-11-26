import type { FloorplanSpec } from '../types';

export class MiniMap {
  private readonly canvas: HTMLCanvasElement;
  private readonly ctx: CanvasRenderingContext2D;
  private readonly floorplan: FloorplanSpec;
  private readonly onRoomSelect: (roomId: string) => void;
  private readonly pad = 12;
  private scale = 1;
  private ox = 0;
  private oy = 0;

  constructor(
    canvas: HTMLCanvasElement,
    floorplan: FloorplanSpec,
    onRoomSelect: (roomId: string) => void
  ) {
    this.canvas = canvas;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('2D context unavailable for MiniMap');
    this.ctx = ctx;
    this.floorplan = floorplan;
    this.onRoomSelect = onRoomSelect;

    this.computeTransform();
    this.canvas.addEventListener('click', (e) => this.handleClick(e));
  }

  private computeTransform(): void {
    const w = this.canvas.width;
    const h = this.canvas.height;
    const siteW = this.floorplan.site.width_mm / 1000;
    const siteD = this.floorplan.site.depth_mm / 1000;
    this.scale = Math.min((w - this.pad * 2) / siteW, (h - this.pad * 2) / siteD);
    this.ox = (w - siteW * this.scale) * 0.5;
    this.oy = h - (h - siteD * this.scale) * 0.5;
  }

  private toPx(xM: number, yCadM: number): [number, number] {
    return [this.ox + xM * this.scale, this.oy - yCadM * this.scale];
  }

  private activeFloor: 1 | 2 = 1;

  private handleClick(e: MouseEvent): void {
    const rect = this.canvas.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * this.canvas.width;
    const py = ((e.clientY - rect.top) / rect.height) * this.canvas.height;
    const xMm = ((px - this.ox) / this.scale) * 1000;
    const yMm = ((this.oy - py) / this.scale) * 1000;

    for (const r of this.floorplan.rooms) {
      if ((r.floor ?? 1) !== this.activeFloor) continue;
      if (r.sub_rects) {
        for (const [x0, y0, x1, y1] of r.sub_rects) {
          if (xMm >= x0 && xMm <= x1 && yMm >= y0 && yMm <= y1) {
            this.onRoomSelect(r.id);
            return;
          }
        }
      } else {
        const xs = r.polygon.map((p) => p[0]);
        const ys = r.polygon.map((p) => p[1]);
        if (xMm >= Math.min(...xs) && xMm <= Math.max(...xs) && yMm >= Math.min(...ys) && yMm <= Math.max(...ys)) {
          this.onRoomSelect(r.id);
          return;
        }
      }
    }
    for (const z of this.floorplan.outdoor_zones) {
      if ((z.floor ?? 1) !== this.activeFloor) continue;
      const b = z.bounds;
      if (xMm >= b.x0 && xMm <= b.x1 && yMm >= b.y0 && yMm <= b.y1) {
        this.onRoomSelect(z.id);
        return;
      }
    }
  }

  render(camX: number, camYCad: number, headingRad: number, activeRoomId: string | null, floor: 1 | 2 = 1): void {
    this.activeFloor = floor;
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;
    ctx.clearRect(0, 0, w, h);

    // Site background
    const [sx0, sy1] = this.toPx(0, 0);
    const [sx1, sy0] = this.toPx(this.floorplan.site.width_mm / 1000, this.floorplan.site.depth_mm / 1000);
    ctx.fillStyle = 'rgba(15, 23, 36, 0.72)';
    ctx.fillRect(sx0, sy0, sx1 - sx0, sy1 - sy0);

    // Outdoor zones for active floor
    for (const z of this.floorplan.outdoor_zones) {
      if ((z.floor ?? 1) !== floor) continue;
      const b = z.bounds;
      const [x0, y1] = this.toPx(b.x0 / 1000, b.y0 / 1000);
      const [x1, y0] = this.toPx(b.x1 / 1000, b.y1 / 1000);
      const isGarden = z.type.includes('garden');
      ctx.fillStyle =
        activeRoomId === z.id
          ? 'rgba(212, 175, 118, 0.35)'
          : isGarden
            ? 'rgba(74, 130, 82, 0.30)'
            : 'rgba(120, 113, 102, 0.28)';
      ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
    }

    // Interior rooms for active floor
    for (const r of this.floorplan.rooms) {
      if ((r.floor ?? 1) !== floor) continue;
      const active = activeRoomId === r.id;
      ctx.fillStyle = active ? 'rgba(212, 175, 118, 0.36)' : 'rgba(232, 226, 215, 0.16)';
      if (r.sub_rects) {
        for (const [rx0, ry0, rx1, ry1] of r.sub_rects) {
          const [x0, y1] = this.toPx(rx0 / 1000, ry0 / 1000);
          const [x1, y0] = this.toPx(rx1 / 1000, ry1 / 1000);
          ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
        }
      } else {
        ctx.beginPath();
        r.polygon.forEach(([px, py], i) => {
          const [mx, my] = this.toPx(px / 1000, py / 1000);
          if (i === 0) ctx.moveTo(mx, my);
          else ctx.lineTo(mx, my);
        });
        ctx.closePath();
        ctx.fill();
      }
    }

    // Rear staircase indicator on both floors
    const [stX0, stY1] = this.toPx(1.85, 12.50);
    const [stX1, stY0] = this.toPx(5.55, 13.38);
    ctx.fillStyle = 'rgba(212, 175, 118, 0.28)';
    ctx.fillRect(stX0, stY0, stX1 - stX0, stY1 - stY0);

    // Structural walls (L1 walls on floor 1, L2 perimeter partitions on floor 2)
    ctx.fillStyle = 'rgba(244, 241, 234, 0.85)';
    if (floor === 1) {
      for (const wall of this.floorplan.walls) {
        const [wx0, wy0, wx1, wy1] = wall.rect;
        const [x0, y1] = this.toPx(wx0 / 1000, wy0 / 1000);
        const [x1, y0] = this.toPx(wx1 / 1000, wy1 / 1000);
        ctx.fillRect(x0, y0, Math.max(1.5, x1 - x0), Math.max(1.5, y1 - y0));
      }
    } else {
      ctx.strokeStyle = 'rgba(244, 241, 234, 0.85)';
      ctx.lineWidth = 1.6;
      for (const [rx0, ry0, rx1, ry1] of [
        [0.2, 6.8, 4.864, 11.5],
        [4.984, 5.2, 8.944, 11.5],
        [3.164, 2.04, 8.944, 5.0],
      ]) {
        const [x0, y1] = this.toPx(rx0, ry0);
        const [x1, y0] = this.toPx(rx1, ry1);
        ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
      }
    }

    // Floor indicator pill in corner of minimap
    ctx.fillStyle = 'rgba(212, 175, 118, 0.92)';
    ctx.font = 'bold 10px ui-monospace, SFMono-Regular, monospace';
    ctx.fillText(floor === 2 ? 'LANTAI 2' : 'LANTAI 1', sx0 + 6, sy0 + 14);

    // Site perimeter hairline
    ctx.strokeStyle = 'rgba(212, 175, 118, 0.65)';
    ctx.lineWidth = 1;
    ctx.strokeRect(sx0, sy0, sx1 - sx0, sy1 - sy0);

    // Camera position & viewing cone (clamped nicely if outside plot)
    const cxClamped = Math.max(-1.0, Math.min(10.1, camX));
    const cyClamped = Math.max(-1.5, Math.min(14.5, camYCad));
    const [cx, cy] = this.toPx(cxClamped, cyClamped);

    // FOV directional cone (headingRad=0 points +Y_cad = UP on canvas = -PI/2 in canvas angles)
    const canvasAng = -Math.PI / 2 + headingRad;
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, 24, canvasAng - 0.45, canvasAng + 0.45);
    ctx.closePath();
    const grad = ctx.createRadialGradient(cx, cy, 2, cx, cy, 24);
    grad.addColorStop(0, 'rgba(56, 189, 248, 0.65)');
    grad.addColorStop(1, 'rgba(56, 189, 248, 0.02)');
    ctx.fillStyle = grad;
    ctx.fill();

    // Camera dot
    ctx.beginPath();
    ctx.arc(cx, cy, 4.2, 0, Math.PI * 2);
    ctx.fillStyle = '#38bdf8';
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.4;
    ctx.stroke();
    ctx.restore();
  }
}
