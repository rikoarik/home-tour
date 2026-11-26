import * as THREE from 'three';
import type { FloorplanSpec, InspectionInfo, InteractiveDoorConfig, InteriorStyle, SceneConfig } from '../types';
import type { LoadedArchitecture } from './AssetManager';

interface DoorAnimState {
  config: InteractiveDoorConfig;
  obj: THREE.Object3D;
  secondaryObj?: THREE.Object3D;
  isOpen: boolean;
  progress: number; // 0 = closed, 1 = open
  restRotY: number;
  restPos: THREE.Vector3;
  secRestPos?: THREE.Vector3;
  center: THREE.Vector3;
  closedBox: THREE.Box3;
  manualOverrideUntilAway: boolean;
}

export interface NearbyDoorPrompt {
  id: string;
  label: string;
  isOpen: boolean;
  dist: number;
}

export class InteractionSystem {
  private readonly raycaster = new THREE.Raycaster();
  private readonly pointer = new THREE.Vector2();
  private readonly scene: THREE.Scene;
  private readonly floorplan: FloorplanSpec;
  private readonly sceneConfig: SceneConfig;
  private readonly doors = new Map<string, DoorAnimState>();

  public autoOpenDoorsInWalkthrough = true;
  public curtainsOpen = false;
  private curtainProgress = 0;
  private curtainNodes: Array<{ obj: THREE.Object3D; restScaleX: number; restPosX: number; side: number }> = [];

  // 3D Tape Measurement State
  public measureMode = false;
  private measurePoints: THREE.Vector3[] = [];
  private readonly measureGroup = new THREE.Group();
  private measureCallback?: (text: string | null) => void;

  // Hover highlight
  public activeStyle: InteriorStyle = 'warm_luxury';

  constructor(
    scene: THREE.Scene,
    arch: LoadedArchitecture,
    sceneConfig: SceneConfig,
    floorplan: FloorplanSpec
  ) {
    this.scene = scene;
    this.sceneConfig = sceneConfig;
    this.floorplan = floorplan;
    this.measureGroup.name = 'MeasurementOverlay';
    this.scene.add(this.measureGroup);

    // Wire all 10 interactive Blender doors (D1..D10 across L1 & L2) with exact world bounding boxes & centers
    for (const dc of sceneConfig.interactive_doors) {
      const obj = arch.doorObjects.get(dc.object_name);
      if (!obj) continue;
      const secondaryObj =
        dc.id === 'D8'
          ? arch.doorObjects.get('Door_Interactive_D8_Panel2')
          : dc.id === 'D10'
            ? arch.doorObjects.get('Door_Interactive_L2_D10_Panel2')
            : undefined;

      let closedBox = new THREE.Box3();
      if (dc.closed_aabb_threejs && dc.closed_aabb_threejs.length === 6) {
        const [x0, y0, z0, x1, y1, z1] = dc.closed_aabb_threejs;
        closedBox.set(
          new THREE.Vector3(Math.min(x0, x1), Math.min(y0, y1), Math.min(z0, z1)),
          new THREE.Vector3(Math.max(x0, x1), Math.max(y0, y1), Math.max(z0, z1))
        );
      } else {
        closedBox.setFromObject(obj);
      }

      const center = dc.center_threejs
        ? new THREE.Vector3(dc.center_threejs[0], dc.center_threejs[1], dc.center_threejs[2])
        : closedBox.getCenter(new THREE.Vector3());

      this.doors.set(dc.id, {
        config: dc,
        obj,
        secondaryObj,
        isOpen: false,
        progress: 0,
        restRotY: obj.rotation.y,
        restPos: obj.position.clone(),
        secRestPos: secondaryObj?.position.clone(),
        center,
        closedBox,
        manualOverrideUntilAway: false,
      });
    }
  }

  registerStyleCurtains(styleGroup: THREE.Group): void {
    this.curtainNodes = [];
    styleGroup.traverse((obj) => {
      if (obj.name.includes('Curtain_')) {
        const side = obj.name.endsWith('_W') ? -1 : 1;
        this.curtainNodes.push({
          obj,
          restScaleX: obj.scale.x,
          restPosX: obj.position.x,
          side,
        });
      }
    });
    // Reapply current open/closed curtain state immediately
    this.applyCurtainState(this.curtainProgress);
  }

  setMeasureCallback(cb: (text: string | null) => void): void {
    this.measureCallback = cb;
  }

  setMeasureMode(enabled: boolean): void {
    this.measureMode = enabled;
    if (!enabled) this.clearMeasurements();
  }

  clearMeasurements(): void {
    this.measurePoints = [];
    while (this.measureGroup.children.length > 0) {
      const child = this.measureGroup.children[0];
      this.measureGroup.remove(child);
      if (child instanceof THREE.Mesh || child instanceof THREE.Line) {
        child.geometry.dispose();
        if (child.material instanceof THREE.Material) child.material.dispose();
      }
    }
    this.measureCallback?.(null);
  }

  toggleDoor(doorId: string, forceOpen?: boolean, isManual = false): boolean {
    const state = this.doors.get(doorId);
    if (!state) return false;
    state.isOpen = forceOpen !== undefined ? forceOpen : !state.isOpen;
    if (isManual) {
      state.manualOverrideUntilAway = true;
    }
    return state.isOpen;
  }

  toggleAllDoors(forceOpen?: boolean, playerPos?: THREE.Vector3): boolean {
    const anyClosed = Array.from(this.doors.values()).some((d) => !d.isOpen);
    const nextState = forceOpen !== undefined ? forceOpen : anyClosed;
    for (const d of this.doors.values()) {
      d.isOpen = nextState;
      if (nextState) {
        d.manualOverrideUntilAway = false;
      } else if (playerPos) {
        // Only suppress auto-open on a door the player is currently standing right next to
        d.manualOverrideUntilAway = this.distanceToDoorXZ(playerPos.x, playerPos.z, d) < 1.75;
      } else {
        d.manualOverrideUntilAway = false;
      }
    }
    return nextState;
  }

  areAllDoorsOpen(): boolean {
    return Array.from(this.doors.values()).every((d) => d.isOpen);
  }

  getDoorStatesSummary(): Record<string, boolean> {
    const out: Record<string, boolean> = {};
    for (const [id, d] of this.doors.entries()) out[id] = d.isOpen;
    return out;
  }

  private distanceToDoorXZ(x: number, z: number, d: DoorAnimState): number {
    const b = d.closedBox;
    const dx = Math.max(b.min.x - x, 0, x - b.max.x);
    const dz = Math.max(b.min.z - z, 0, z - b.max.z);
    return Math.hypot(dx, dz);
  }

  /**
   * In WASD First-Person Walkthrough mode:
   * - Automatically opens any door (D1..D8) as the player approaches within 1.65 m
   * - Returns the nearest door prompt within 2.25 m so the HUD shows live [E] / [O] controls
   */
  updateWalkthroughDoors(
    playerPos: THREE.Vector3,
    isFirstPerson: boolean,
    onAutoOpened?: (doorId: string, label: string) => void
  ): NearbyDoorPrompt | null {
    let nearest: NearbyDoorPrompt | null = null;

    for (const d of this.doors.values()) {
      if (Math.abs(playerPos.y - d.center.y) > 2.0) continue;
      const dist = this.distanceToDoorXZ(playerPos.x, playerPos.z, d);
      if (dist > 2.25) {
        d.manualOverrideUntilAway = false;
      }
      if (
        isFirstPerson &&
        this.autoOpenDoorsInWalkthrough &&
        dist < 1.65 &&
        !d.isOpen &&
        !d.manualOverrideUntilAway
      ) {
        d.isOpen = true;
        const lbl = d.config.label ?? `Door ${d.config.id}`;
        onAutoOpened?.(d.config.id, lbl);
      }
      if (dist < 2.25 && (!nearest || dist < nearest.dist)) {
        nearest = {
          id: d.config.id,
          label: d.config.label ?? `Door ${d.config.id}`,
          isOpen: d.isOpen,
          dist,
        };
      }
    }
    return nearest;
  }

  /** Toggles the nearest door to the player (triggered by pressing [E] or [F] in WASD mode) */
  toggleNearestDoor(playerPos: THREE.Vector3, maxDist = 2.6): { id: string; label: string; isOpen: boolean } | null {
    let best: DoorAnimState | null = null;
    let bestDist = maxDist;
    for (const d of this.doors.values()) {
      if (Math.abs(playerPos.y - d.center.y) > 2.0) continue;
      const dist = this.distanceToDoorXZ(playerPos.x, playerPos.z, d);
      if (dist < bestDist) {
        bestDist = dist;
        best = d;
      }
    }
    if (!best) return null;
    const isOpen = this.toggleDoor(best.config.id, undefined, true);
    return {
      id: best.config.id,
      label: best.config.label ?? `Door ${best.config.id}`,
      isOpen,
    };
  }

  /** Dynamic collision boxes for any currently closed doors so WASD players don't walk through closed door slabs */
  getClosedDoorCollisionBoxes(): THREE.Box3[] {
    const out: THREE.Box3[] = [];
    for (const d of this.doors.values()) {
      if (d.progress < 0.35 && !d.isOpen) {
        out.push(d.closedBox);
      }
    }
    return out;
  }

  toggleCurtains(forceOpen?: boolean): boolean {
    this.curtainsOpen = forceOpen !== undefined ? forceOpen : !this.curtainsOpen;
    return this.curtainsOpen;
  }

  private applyCurtainState(t: number): void {
    for (const c of this.curtainNodes) {
      // Gather curtain neatly toward window jamb as t goes 0 -> 1
      c.obj.scale.x = c.restScaleX * THREE.MathUtils.lerp(1.0, 0.36, t);
      c.obj.position.x = c.restPosX + c.side * 0.14 * t;
    }
  }

  handleClick(
    clientX: number,
    clientY: number,
    canvas: HTMLCanvasElement,
    camera: THREE.Camera,
    cameraMode: string,
    targets: THREE.Object3D[],
    callbacks: {
      onDoorToggled: (doorId: string, isOpen: boolean) => void;
      onLightToggled?: (hitObject: THREE.Object3D) => boolean;
      onRoomClicked: (roomId: string) => void;
      onInspect: (info: InspectionInfo) => void;
    }
  ): void {
    const rect = canvas.getBoundingClientRect();
    this.pointer.x = ((clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.pointer, camera);
    const hits = this.raycaster.intersectObjects(targets, true).filter((h) => h.object.visible);
    if (hits.length === 0) return;

    const hit = hits[0];

    // 1. Distance Measurement Mode takes top priority
    if (this.measureMode) {
      this.addMeasurePoint(hit.point.clone());
      return;
    }

    // 2. Check if clicked an interactive door (or its child handle/stile across L1 & L2)
    let cur: THREE.Object3D | null = hit.object;
    while (cur) {
      for (const [doorId, state] of this.doors.entries()) {
        if (
          cur === state.obj ||
          cur === state.secondaryObj ||
          cur.name.startsWith(`Door_Interactive_${doorId}`) ||
          cur.name.startsWith(`Door_Interactive_L2_${doorId}`) ||
          cur.name.startsWith(`DoorFrame_${doorId}`) ||
          cur.name.startsWith(`DoorFrame_L2_${doorId}`)
        ) {
          const isOpen = this.toggleDoor(doorId, undefined, true);
          callbacks.onDoorToggled(doorId, isOpen);
          return;
        }
      }
      cur = cur.parent;
    }

    // 2.5 Check if clicked a lamp, ceiling light, chandelier, monitor lightbar, LED strip, sconce, bollard, or wall switch!
    for (const h of hits.slice(0, 3)) {
      if (callbacks.onLightToggled?.(h.object)) {
        return;
      }
    }

    // 3. In Dollhouse or Floor Plan mode, clicking a room floor enters First-Person in that room!
    if (cameraMode === 'dollhouse' || cameraMode === 'floorplan') {
      const roomId = this.resolveRoomIdAtPoint(hit.point.x, -hit.point.z, hit.point.y);
      if (roomId) {
        callbacks.onRoomClicked(roomId);
        return;
      }
    }

    // 4. Inspect clicked furniture or architectural material (supports both individual & GPU-batched meshes via world hitPoint!)
    const info = this.resolveInspectionInfo(hit.object, hit.point);
    if (info) {
      callbacks.onInspect(info);
    }
  }

  private addMeasurePoint(pt: THREE.Vector3): void {
    if (this.measurePoints.length >= 2) {
      this.clearMeasurements();
    }
    this.measurePoints.push(pt);

    const pinGeo = new THREE.SphereGeometry(0.055, 16, 12);
    const pinMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8, depthTest: false });
    const pin = new THREE.Mesh(pinGeo, pinMat);
    pin.position.copy(pt);
    pin.renderOrder = 999;
    this.measureGroup.add(pin);

    if (this.measurePoints.length === 1) {
      this.measureCallback?.('Click second point to measure distance');
      return;
    }

    const [a, b] = this.measurePoints;
    const lineGeo = new THREE.BufferGeometry().setFromPoints([a, b]);
    const lineMat = new THREE.LineBasicMaterial({ color: 0x38bdf8, depthTest: false });
    const line = new THREE.Line(lineGeo, lineMat);
    line.renderOrder = 998;
    this.measureGroup.add(line);

    const distM = a.distanceTo(b);
    const distMm = Math.round(distM * 1000);
    const horizM = Math.hypot(b.x - a.x, b.z - a.z);
    this.measureCallback?.(
      `${distM.toFixed(2)} m (${distMm.toLocaleString()} mm) · Horizontal: ${horizM.toFixed(2)} m`
    );
  }

  resolveRoomIdAtPoint(xM: number, yCadM: number, elevY = 1.6): string | null {
    const xMm = xM * 1000;
    const yMm = yCadM * 1000;
    const targetFloor: 1 | 2 = elevY >= 2.7 ? 2 : 1;

    for (const r of this.floorplan.rooms) {
      if ((r.floor ?? 1) !== targetFloor) continue;
      if (r.sub_rects) {
        for (const [x0, y0, x1, y1] of r.sub_rects) {
          if (xMm >= x0 && xMm <= x1 && yMm >= y0 && yMm <= y1) return r.id;
        }
      } else {
        const xs = r.polygon.map((p) => p[0]);
        const ys = r.polygon.map((p) => p[1]);
        if (xMm >= Math.min(...xs) && xMm <= Math.max(...xs) && yMm >= Math.min(...ys) && yMm <= Math.max(...ys)) {
          return r.id;
        }
      }
    }
    for (const z of this.floorplan.outdoor_zones) {
      if ((z.floor ?? 1) !== targetFloor) continue;
      const b = z.bounds;
      if (xMm >= b.x0 && xMm <= b.x1 && yMm >= b.y0 && yMm <= b.y1) return z.id;
    }
    return null;
  }

  private resolveInspectionInfo(obj: THREE.Object3D, hitPoint?: THREE.Vector3): InspectionInfo | null {
    const name = obj.name || '';
    const styleLabel = this.sceneConfig.assets.interior_styles[this.activeStyle].label;

    let matName = 'Architectural PBR Finish';
    if (obj instanceof THREE.Mesh) {
      const mat = Array.isArray(obj.material) ? obj.material[0] : obj.material;
      if (mat?.name) matName = mat.name.replace(/^Mat_/, '').replace(/_/g, ' ');
    }

    // Spatial lookup for GPU-batched furniture meshes (keeps exact inspection specs at 10x fewer draw calls!)
    if (name.startsWith('Batch_') && hitPoint) {
      const hxMm = hitPoint.x * 1000;
      const hyMm = -hitPoint.z * 1000;
      for (const f of this.floorplan.furniture) {
        if (f.kind === 'rug') continue;
        if (hxMm >= f.rect[0] - 80 && hxMm <= f.rect[2] + 80 && hyMm >= f.rect[1] - 80 && hyMm <= f.rect[3] + 80) {
          const w = Math.round(f.rect[2] - f.rect[0]);
          const d = Math.round(f.rect[3] - f.rect[1]);
          const room =
            this.floorplan.rooms.find((r) => r.id === f.room)?.name ??
            this.floorplan.outdoor_zones.find((z) => z.id === f.room)?.name ??
            f.room;
          return {
            title: f.name,
            category: 'Curated Furnishing',
            roomName: room,
            materialName: matName,
            dimensions: `${w.toLocaleString()} × ${d.toLocaleString()} × ${f.height_mm.toLocaleString()} mm`,
            styleLabel,
          };
        }
      }
      const rid = this.resolveRoomIdAtPoint(hitPoint.x, -hitPoint.z);
      const rname =
        this.floorplan.rooms.find((r) => r.id === rid)?.name ??
        this.floorplan.outdoor_zones.find((z) => z.id === rid)?.name ??
        'Villa Aurelia 123';
      return {
        title: matName,
        category: 'Architectural Finish & Detail',
        roomName: rname,
        materialName: matName,
        dimensions: 'Verified 1:1 Architectural Spec',
        styleLabel,
      };
    }

    // Match against approved floorplan furniture IDs
    for (const f of this.floorplan.furniture) {
      if (name.includes(f.id)) {
        const w = Math.round(f.rect[2] - f.rect[0]);
        const d = Math.round(f.rect[3] - f.rect[1]);
        const room =
          this.floorplan.rooms.find((r) => r.id === f.room)?.name ??
          this.floorplan.outdoor_zones.find((z) => z.id === f.room)?.name ??
          f.room;
        return {
          title: f.name,
          category: 'Curated Furnishing',
          roomName: room,
          materialName: matName,
          dimensions: `${w.toLocaleString()} × ${d.toLocaleString()} × ${f.height_mm.toLocaleString()} mm`,
          styleLabel,
        };
      }
    }

    // Match curtains, artwork, bespoke decorations, EV charger, windows, walls, or floors
    if (name.includes('Decor_') || name.includes('EVWallbox') || name.includes('EVGlass') || name.includes('Bollard')) {
      const cleanTitle = name
        .replace(/^(WarmLuxury|Scandinavian|Modern)_Decor_/, '')
        .replace(/^Arch_/, '')
        .replace(/_/g, ' ');
      return {
        title: cleanTitle,
        category: 'Bespoke Architectural Decor & Detail',
        roomName: 'Villa Aurelia 123',
        materialName: matName,
        dimensions: 'Custom Architectural Spec',
        styleLabel,
      };
    }
    if (name.includes('Art')) {
      return {
        title: 'Framed Architectural Canvas Artwork',
        category: 'Interior Decor',
        roomName: name.includes('Master') ? 'Master Bedroom' : name.includes('Dining') ? 'Dining Area' : 'Living Room',
        materialName: matName,
        dimensions: '1,250 × 1,100 mm',
        styleLabel,
      };
    }
    if (name.includes('Curtain')) {
      return {
        title: 'Floor-to-Ceiling Sheer Linen Drapery',
        category: 'Window Treatment',
        roomName: name.includes('Master') ? 'Master Bedroom' : 'Living Room',
        materialName: matName,
        dimensions: 'Full Height (2,950 mm)',
        styleLabel,
        notes: 'Use the Curtains toggle in the toolbar to draw open or closed.',
      };
    }
    if (name.startsWith('Win')) {
      const wid = name.split('_')[1];
      const wspec = this.floorplan.windows.find((w) => w.id === wid);
      if (wspec) {
        return {
          title: `${wspec.id} — ${wspec.type}`,
          category: 'Architectural Glazing',
          roomName: wspec.orientation,
          materialName: 'Black Anodized Aluminum + Low-E Glass',
          dimensions: `${wspec.width_mm.toLocaleString()} × ${wspec.height_mm.toLocaleString()} mm (Sill ${wspec.sill_height_mm} mm)`,
          styleLabel,
        };
      }
    }
    if (name.startsWith('Wall_') || name.startsWith('Floor_')) {
      const box = new THREE.Box3().setFromObject(obj);
      const sz = new THREE.Vector3();
      box.getSize(sz);
      return {
        title: name.replace(/_/g, ' '),
        category: name.startsWith('Wall_') ? 'Structural Masonry / Partition' : 'Architectural Flooring',
        roomName: 'Villa Aurelia 123',
        materialName: matName,
        dimensions: `${Math.round(sz.x * 1000).toLocaleString()} × ${Math.round(sz.z * 1000).toLocaleString()} × ${Math.round(sz.y * 1000).toLocaleString()} mm`,
        styleLabel,
      };
    }
    return null;
  }

  update(dt: number): boolean {
    let anyMoved = false;
    // Animate doors smoothly around Blender hinge pivots / sliding tracks
    for (const d of this.doors.values()) {
      const target = d.isOpen ? 1 : 0;
      const prev = d.progress;
      if (Math.abs(d.progress - target) < 0.001) {
        d.progress = target;
      } else {
        d.progress = THREE.MathUtils.lerp(d.progress, target, Math.min(1, dt * 6.5));
      }
      if (Math.abs(d.progress - prev) <= 1e-5) continue;
      anyMoved = true;

      if (d.config.kind === 'hinged') {
        // Use exact Three.js swing_sign from Blender scene-config so every door swings INTO its room
        const sign = d.config.swing_sign ?? (d.config.id === 'D3' || d.config.id === 'D6' ? -1 : 1);
        const rad = THREE.MathUtils.degToRad((d.config.open_angle_deg ?? 90) * d.progress * sign);
        d.obj.rotation.y = d.restRotY + rad;
      } else if (d.config.kind === 'sliding_multi') {
        const maxSlide = d.config.max_slide_m ?? 1.55;
        d.obj.position.x = d.restPos.x + maxSlide * d.progress;
        if (d.secondaryObj && d.secRestPos) {
          d.secondaryObj.position.x = d.secRestPos.x + maxSlide * 0.52 * d.progress;
        }
      } else if (d.config.kind === 'pocket_sliding') {
        const maxSlide = d.config.max_slide_m ?? 0.67;
        const dir = d.config.swing_sign ?? -1;
        d.obj.position.z = d.restPos.z + maxSlide * d.progress * dir;
      }
    }

    // Animate sheer curtains smoothly
    const cTarget = this.curtainsOpen ? 1 : 0;
    if (Math.abs(this.curtainProgress - cTarget) > 0.001) {
      this.curtainProgress = THREE.MathUtils.lerp(this.curtainProgress, cTarget, Math.min(1, dt * 5.0));
      this.applyCurtainState(this.curtainProgress);
      anyMoved = true;
    } else if (this.curtainProgress !== cTarget) {
      this.curtainProgress = cTarget;
      this.applyCurtainState(this.curtainProgress);
      anyMoved = true;
    }
    return anyMoved;
  }
}
