import * as THREE from 'three';
import type { FloorplanSpec } from '../types';

interface ProjectedBadge {
  id: string;
  worldPos: THREE.Vector3;
  el: HTMLButtonElement;
}

export class DimensionOverlay {
  private readonly container: HTMLElement;
  private readonly badges: ProjectedBadge[] = [];
  private readonly proj = new THREE.Vector3();
  public visible = false;

  constructor(
    container: HTMLElement,
    floorplan: FloorplanSpec,
    onRoomClick: (roomId: string) => void
  ) {
    this.container = container;

    for (const r of floorplan.rooms) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'dim-badge';
      btn.innerHTML = `<span class="dim-badge__name">${r.name}</span><span class="dim-badge__meta">${(r.width_mm / 1000).toFixed(2)}×${(r.depth_mm / 1000).toFixed(2)}m · ${r.area_m2.toFixed(2)} m²</span>`;
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        onRoomClick(r.id);
      });
      this.container.appendChild(btn);
      this.badges.push({
        id: r.id,
        worldPos: new THREE.Vector3(r.label_pos[0] / 1000, 0.35, -r.label_pos[1] / 1000),
        el: btn,
      });
    }

    for (const z of floorplan.outdoor_zones) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'dim-badge dim-badge--outdoor';
      btn.innerHTML = `<span class="dim-badge__name">${z.name}</span><span class="dim-badge__meta">${z.area_m2.toFixed(2)} m²</span>`;
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        onRoomClick(z.id);
      });
      this.container.appendChild(btn);
      const cx = (z.bounds.x0 + z.bounds.x1) * 0.5 / 1000;
      const cy = (z.bounds.y0 + z.bounds.y1) * 0.5 / 1000;
      this.badges.push({
        id: z.id,
        worldPos: new THREE.Vector3(cx, 0.2, -cy),
        el: btn,
      });
    }

    this.setVisible(false);
  }

  setVisible(show: boolean): void {
    this.visible = show;
    this.container.hidden = !show;
  }

  update(camera: THREE.Camera, width: number, height: number): void {
    if (!this.visible) return;
    for (const b of this.badges) {
      this.proj.copy(b.worldPos).project(camera);
      if (this.proj.z > 1 || this.proj.z < -1) {
        b.el.style.opacity = '0';
        b.el.style.pointerEvents = 'none';
        continue;
      }
      const x = (this.proj.x * 0.5 + 0.5) * width;
      const y = (-this.proj.y * 0.5 + 0.5) * height;
      b.el.style.opacity = '1';
      b.el.style.pointerEvents = 'auto';
      b.el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) translate(-50%, -50%)`;
    }
  }
}
