import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { CameraMode, FloorplanSpec, RoomSpec } from '../types';

export interface CameraTransition {
  fromPos: THREE.Vector3;
  toPos: THREE.Vector3;
  fromTarget: THREE.Vector3;
  toTarget: THREE.Vector3;
  elapsed: number;
  duration: number;
  onComplete?: () => void;
}

export class CameraController {
  public readonly perspCamera: THREE.PerspectiveCamera;
  public readonly orthoCamera: THREE.OrthographicCamera;
  public activeCamera: THREE.Camera;
  public readonly orbit: OrbitControls;

  public mode: CameraMode = 'exterior';
  private readonly dom: HTMLElement;
  private readonly floorplan: FloorplanSpec;
  private collisionBoxes: THREE.Box3[] = [];
  private dynamicColliderProvider?: () => THREE.Box3[];
  private readonly roofObjects: THREE.Object3D[];
  private readonly ceilingObjects: THREE.Object3D[];

  // First-person walkthrough state (eye height strictly 1.65 m above floor)
  private fpYaw = 0;
  private fpPitch = 0;
  private readonly fpVelocity = new THREE.Vector3();
  private readonly keys = new Set<string>();
  private draggingLook = false;
  private lastPointerX = 0;
  private lastPointerY = 0;
  public joystickInput = { x: 0, y: 0 };

  // Smooth camera tween
  private transition: CameraTransition | null = null;
  private readonly onModeChanged?: (mode: CameraMode) => void;
  private readonly siteCenter = new THREE.Vector3(4.572, 1.2, -6.75);
  private orthoFrustumHeight = 16.4;

  constructor(
    dom: HTMLElement,
    floorplan: FloorplanSpec,
    roofObjects: THREE.Object3D[],
    ceilingObjects: THREE.Object3D[],
    onModeChanged?: (mode: CameraMode) => void
  ) {
    this.dom = dom;
    this.floorplan = floorplan;
    this.roofObjects = roofObjects;
    this.ceilingObjects = ceilingObjects;
    this.onModeChanged = onModeChanged;

    const aspect = Math.max(1, dom.clientWidth) / Math.max(1, dom.clientHeight);
    this.perspCamera = new THREE.PerspectiveCamera(48, aspect, 0.06, 280);
    this.perspCamera.position.set(11.4, 3.1, 6.2);

    const halfH = this.orthoFrustumHeight * 0.5;
    const halfW = halfH * aspect;
    this.orthoCamera = new THREE.OrthographicCamera(-halfW, halfW, halfH, -halfH, 0.1, 120);
    this.orthoCamera.position.set(4.572, 24, -6.75);
    this.orthoCamera.up.set(0, 0, -1); // North (+Y in CAD = -Z in Three.js) points UP on screen!
    this.orthoCamera.lookAt(4.572, 0, -6.75);

    this.activeCamera = this.perspCamera;

    this.orbit = new OrbitControls(this.perspCamera, dom);
    this.orbit.enableDamping = true;
    this.orbit.dampingFactor = 0.07;
    this.orbit.target.set(4.5, 1.75, -5.2);
    this.orbit.maxPolarAngle = Math.PI * 0.49;
    this.orbit.minDistance = 2.0;
    this.orbit.maxDistance = 32.0;
    this.orbit.update();

    this.bindInputListeners();
  }

  setCollisionBoxes(boxes: THREE.Box3[]): void {
    this.collisionBoxes = boxes;
  }

  setDynamicColliderProvider(provider: () => THREE.Box3[]): void {
    this.dynamicColliderProvider = provider;
  }

  setRoofCeilingVisible(visible: boolean): void {
    for (const o of this.roofObjects) o.visible = visible;
    for (const o of this.ceilingObjects) o.visible = visible;
  }

  isRoofVisible(): boolean {
    return this.roofObjects.length > 0 ? this.roofObjects[0].visible : true;
  }

  toggleRoofCeiling(): boolean {
    const next = !this.isRoofVisible();
    this.setRoofCeilingVisible(next);
    return next;
  }

  resize(width: number, height: number): void {
    const aspect = Math.max(1, width) / Math.max(1, height);
    this.perspCamera.aspect = aspect;
    this.perspCamera.updateProjectionMatrix();

    const halfH = this.orthoFrustumHeight * 0.5;
    const halfW = halfH * aspect;
    this.orthoCamera.left = -halfW;
    this.orthoCamera.right = halfW;
    this.orthoCamera.top = halfH;
    this.orthoCamera.bottom = -halfH;
    this.orthoCamera.updateProjectionMatrix();
  }

  setMode(mode: CameraMode, instant = false): void {
    this.mode = mode;
    this.fpVelocity.set(0, 0, 0);
    this.transition = null;

    if (mode === 'exterior') {
      this.activeCamera = this.perspCamera;
      this.perspCamera.fov = 46;
      this.perspCamera.updateProjectionMatrix();
      this.setRoofCeilingVisible(true);
      this.orbit.object = this.perspCamera;
      this.orbit.enabled = true;
      this.orbit.enableRotate = true;
      this.orbit.maxPolarAngle = Math.PI * 0.485;
      this.orbit.minDistance = 3.2;
      this.orbit.maxDistance = 32.0;
      const toPos = new THREE.Vector3(11.4, 3.1, 6.2);
      const toTgt = new THREE.Vector3(4.5, 1.75, -5.2);
      this.flyTo(toPos, toTgt, instant ? 0 : 0.95);
    } else if (mode === 'dollhouse') {
      this.activeCamera = this.perspCamera;
      this.perspCamera.fov = 40;
      this.perspCamera.updateProjectionMatrix();
      this.setRoofCeilingVisible(false);
      this.orbit.object = this.perspCamera;
      this.orbit.enabled = true;
      this.orbit.enableRotate = true;
      this.orbit.maxPolarAngle = Math.PI * 0.44;
      this.orbit.minDistance = 4.0;
      this.orbit.maxDistance = 30.0;
      const toPos = new THREE.Vector3(14.5, 14.2, 4.8);
      const toTgt = new THREE.Vector3(4.572, 0.8, -6.75);
      this.flyTo(toPos, toTgt, instant ? 0 : 1.05);
    } else if (mode === 'floorplan') {
      this.setRoofCeilingVisible(false);
      this.activeCamera = this.orthoCamera;
      this.orthoCamera.position.set(4.572, 24, -6.75);
      this.orthoCamera.zoom = 1.0;
      this.orthoCamera.updateProjectionMatrix();
      this.orbit.object = this.orthoCamera;
      this.orbit.target.set(4.572, 0.15, -6.75);
      this.orbit.enabled = true;
      this.orbit.enableRotate = false;
      this.orbit.minZoom = 0.7;
      this.orbit.maxZoom = 3.2;
      this.orbit.update();
    } else if (mode === 'firstperson') {
      this.activeCamera = this.perspCamera;
      this.perspCamera.fov = 60;
      this.perspCamera.updateProjectionMatrix();
      this.setRoofCeilingVisible(true);
      this.orbit.enabled = false;
      // Default start inside Foyer looking toward Open Living/Dining if currently far outside
      const cur = this.perspCamera.position;
      const insideSite = cur.x > 0.3 && cur.x < 8.8 && cur.z < -0.3 && cur.z > -13.2 && cur.y < 3.0;
      if (!insideSite) {
        this.teleportFirstPerson(new THREE.Vector3(4.7, 1.8, -2.8), new THREE.Vector3(6.2, 1.65, -7.8), instant);
      } else {
        const floorY = this.getFloorElevation(cur.x, cur.z);
        cur.y = floorY + 1.65;
        this.syncYawPitchFromCamera();
      }
    }

    this.onModeChanged?.(mode);
  }

  resetCamera(): void {
    this.setMode(this.mode, false);
  }

  enterRoom(roomId: string): void {
    const room = this.floorplan.rooms.find((r) => r.id === roomId);
    if (room) {
      const [lx, ly] = room.label_pos;
      const pos = new THREE.Vector3(lx / 1000, 0.15 + 1.65, -ly / 1000);
      // Aim gracefully toward room focal point or open living center
      const look = this.getRoomLookTarget(room, pos);
      this.mode = 'firstperson';
      this.activeCamera = this.perspCamera;
      this.perspCamera.fov = 60;
      this.perspCamera.updateProjectionMatrix();
      this.setRoofCeilingVisible(true);
      this.orbit.enabled = false;
      this.teleportFirstPerson(pos, look, false);
      this.onModeChanged?.('firstperson');
      return;
    }

    const ext = this.floorplan.outdoor_zones.find((z) => z.id === roomId);
    if (ext) {
      const cx = (ext.bounds.x0 + ext.bounds.x1) * 0.5 / 1000;
      const cy = (ext.bounds.y0 + ext.bounds.y1) * 0.5 / 1000;
      const baseZ = ext.id === 'EXT-04' ? 0.11 : 0.04;
      const pos = new THREE.Vector3(cx, baseZ + 1.65, -cy);
      const look = new THREE.Vector3(4.57, 1.55, -6.75);
      this.mode = 'firstperson';
      this.activeCamera = this.perspCamera;
      this.perspCamera.fov = 60;
      this.perspCamera.updateProjectionMatrix();
      this.setRoofCeilingVisible(true);
      this.orbit.enabled = false;
      this.teleportFirstPerson(pos, look, false);
      this.onModeChanged?.('firstperson');
    }
  }

  private getRoomLookTarget(room: RoomSpec, pos: THREE.Vector3): THREE.Vector3 {
    const targets: Record<string, [number, number, number]> = {
      'RM-01': [1.2, 1.4, -10.4],
      'RM-02': [4.9, 1.4, -10.8],
      'RM-03': [1.2, 1.35, -6.4],
      'RM-04': [7.5, 1.25, -2.30],
      'RM-05': [3.9, 1.4, -5.6],
      'RM-06': [3.8, 1.4, -4.6],
      'RM-07': [5.8, 1.6, -6.8],
      'RM-08': [6.6, 1.55, -9.2],
      'RM-09': [7.4, 1.45, -12.2],
      'RM-10': [8.0, 1.4, -6.5],
      'RM-11': [7.2, 1.45, -9.8],
    };
    const t = targets[room.id];
    return t ? new THREE.Vector3(t[0], t[1], t[2]) : pos.clone().add(new THREE.Vector3(0, -0.1, -2.0));
  }

  teleportFirstPerson(pos: THREE.Vector3, lookAt: THREE.Vector3, instant = false): void {
    const floorY = this.getFloorElevation(pos.x, pos.z);
    const exactPos = new THREE.Vector3(pos.x, floorY + 1.65, pos.z);
    if (instant) {
      this.perspCamera.position.copy(exactPos);
      this.perspCamera.lookAt(lookAt);
      this.syncYawPitchFromCamera();
      this.transition = null;
      return;
    }
    const curTarget = new THREE.Vector3();
    this.perspCamera.getWorldDirection(curTarget).multiplyScalar(3).add(this.perspCamera.position);
    this.flyTo(exactPos, lookAt, 0.85, () => {
      this.perspCamera.position.copy(exactPos);
      this.perspCamera.lookAt(lookAt);
      this.syncYawPitchFromCamera();
    });
  }

  /** Programmatic camera positioning used by TourController */
  setCinematicPose(pos: THREE.Vector3, lookAt: THREE.Vector3): void {
    this.transition = null;
    this.activeCamera = this.perspCamera;
    this.perspCamera.position.copy(pos);
    this.perspCamera.lookAt(lookAt);
    this.orbit.target.copy(lookAt);
    this.syncYawPitchFromCamera();
  }

  flyTo(toPos: THREE.Vector3, toTarget: THREE.Vector3, duration = 0.9, onComplete?: () => void): void {
    if (duration <= 0.01) {
      this.perspCamera.position.copy(toPos);
      this.orbit.target.copy(toTarget);
      this.perspCamera.lookAt(toTarget);
      this.orbit.update();
      onComplete?.();
      return;
    }
    const fromTarget =
      this.mode === 'firstperson'
        ? new THREE.Vector3().set(0, 0, -1).applyQuaternion(this.perspCamera.quaternion).multiplyScalar(3).add(this.perspCamera.position)
        : this.orbit.target.clone();
    this.transition = {
      fromPos: this.perspCamera.position.clone(),
      toPos: toPos.clone(),
      fromTarget,
      toTarget: toTarget.clone(),
      elapsed: 0,
      duration,
      onComplete,
    };
  }

  private getFloorElevation(x: number, z: number): number {
    // Inside building footprint (Y_cad = -z): [3.044..9.144, 1.9..5.0] or [0..9.144, 5.0..11.7]
    const yCad = -z;
    const inMain = x >= 0.05 && x <= 9.1 && yCad >= 5.0 && yCad <= 11.7;
    const inFront = x >= 3.04 && x <= 9.1 && yCad >= 1.9 && yCad <= 5.0;
    if (inMain || inFront) return 0.15;
    if (yCad > 11.7 && x >= 5.49) return 0.11; // Rear timber terrace
    return 0.03;
  }

  private syncYawPitchFromCamera(): void {
    const euler = new THREE.Euler().setFromQuaternion(this.perspCamera.quaternion, 'YXZ');
    this.fpYaw = euler.y;
    this.fpPitch = THREE.MathUtils.clamp(euler.x, -1.2, 1.2);
  }

  private bindInputListeners(): void {
    window.addEventListener('keydown', (e) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      this.keys.add(e.code);
    });
    window.addEventListener('keyup', (e) => {
      this.keys.delete(e.code);
    });

    this.dom.addEventListener('pointerdown', (e) => {
      if (this.mode !== 'firstperson' || e.button !== 0) return;
      this.draggingLook = true;
      this.lastPointerX = e.clientX;
      this.lastPointerY = e.clientY;
    });

    window.addEventListener('pointermove', (e) => {
      if (this.mode !== 'firstperson') return;
      if (document.pointerLockElement === this.dom) {
        this.fpYaw -= e.movementX * 0.0022;
        this.fpPitch = THREE.MathUtils.clamp(this.fpPitch - e.movementY * 0.0022, -1.15, 1.15);
      } else if (this.draggingLook) {
        const dx = e.clientX - this.lastPointerX;
        const dy = e.clientY - this.lastPointerY;
        this.lastPointerX = e.clientX;
        this.lastPointerY = e.clientY;
        this.fpYaw -= dx * 0.0042;
        this.fpPitch = THREE.MathUtils.clamp(this.fpPitch - dy * 0.0036, -1.15, 1.15);
      }
    });

    window.addEventListener('pointerup', () => {
      this.draggingLook = false;
    });
  }

  private collides(nextX: number, nextZ: number, eyeY: number): boolean {
    const r = 0.20; // comfortable human capsule radius that glides smoothly through 700-1000 mm doorways!
    // Site perimeter safety clamp
    if (nextX < 0.24 || nextX > 8.90 || nextZ > -0.20 || nextZ < -13.28) return true;

    const playerMinY = eyeY - 1.5;
    const playerMaxY = eyeY + 0.15;
    for (const b of this.collisionBoxes) {
      if (b.max.y < playerMinY || b.min.y > playerMaxY) continue;
      if (
        nextX + r > b.min.x &&
        nextX - r < b.max.x &&
        nextZ + r > b.min.z &&
        nextZ - r < b.max.z
      ) {
        return true;
      }
    }
    if (this.dynamicColliderProvider) {
      for (const b of this.dynamicColliderProvider()) {
        if (b.max.y < playerMinY || b.min.y > playerMaxY) continue;
        if (
          nextX + r > b.min.x &&
          nextX - r < b.max.x &&
          nextZ + r > b.min.z &&
          nextZ - r < b.max.z
        ) {
          return true;
        }
      }
    }
    return false;
  }

  getCameraPlanState(): { x: number; yCad: number; headingRad: number } {
    const pos = this.activeCamera.position;
    const dir = new THREE.Vector3();
    this.activeCamera.getWorldDirection(dir);
    const headingRad = Math.atan2(dir.x, -dir.z);
    return { x: pos.x, yCad: -pos.z, headingRad };
  }

  update(dt: number, tourActive: boolean): void {
    if (tourActive) return;

    if (this.transition) {
      this.transition.elapsed += dt;
      const t = Math.min(1, this.transition.elapsed / this.transition.duration);
      const ease = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
      this.perspCamera.position.lerpVectors(this.transition.fromPos, this.transition.toPos, ease);
      const tgt = new THREE.Vector3().lerpVectors(this.transition.fromTarget, this.transition.toTarget, ease);
      this.orbit.target.copy(tgt);
      this.perspCamera.lookAt(tgt);
      if (t >= 1) {
        const done = this.transition.onComplete;
        this.transition = null;
        done?.();
      }
      return;
    }

    if (this.mode === 'firstperson') {
      // Orientation
      const euler = new THREE.Euler(this.fpPitch, this.fpYaw, 0, 'YXZ');
      this.perspCamera.quaternion.setFromEuler(euler);

      // Desired planar input (WASD + Arrow keys + Mobile Virtual Joystick)
      let moveFwd = 0;
      let moveRight = 0;
      if (this.keys.has('KeyW') || this.keys.has('ArrowUp')) moveFwd += 1;
      if (this.keys.has('KeyS') || this.keys.has('ArrowDown')) moveFwd -= 1;
      if (this.keys.has('KeyD') || this.keys.has('ArrowRight')) moveRight += 1;
      if (this.keys.has('KeyA') || this.keys.has('ArrowLeft')) moveRight -= 1;

      moveFwd += -this.joystickInput.y;
      moveRight += this.joystickInput.x;

      const forward = new THREE.Vector3(-Math.sin(this.fpYaw), 0, -Math.cos(this.fpYaw));
      const right = new THREE.Vector3(Math.cos(this.fpYaw), 0, -Math.sin(this.fpYaw));

      const walkSpeed = this.keys.has('ShiftLeft') || this.keys.has('ShiftRight') ? 2.6 : 1.55;
      const targetVel = new THREE.Vector3()
        .addScaledVector(forward, moveFwd)
        .addScaledVector(right, moveRight);
      if (targetVel.lengthSq() > 1) targetVel.normalize();
      targetVel.multiplyScalar(walkSpeed);

      // Smooth acceleration & deceleration
      const accel = targetVel.lengthSq() > 0.001 ? 9.0 : 11.0;
      this.fpVelocity.lerp(targetVel, Math.min(1, dt * accel));

      const cur = this.perspCamera.position;
      const stepX = this.fpVelocity.x * dt;
      const stepZ = this.fpVelocity.z * dt;

      // Sliding collision resolution (test X and Z axes independently so player glides along walls!)
      if (Math.abs(stepX) > 1e-5 && !this.collides(cur.x + stepX, cur.z, cur.y)) {
        cur.x += stepX;
      } else {
        this.fpVelocity.x = 0;
      }
      if (Math.abs(stepZ) > 1e-5 && !this.collides(cur.x, cur.z + stepZ, cur.y)) {
        cur.z += stepZ;
      } else {
        this.fpVelocity.z = 0;
      }

      // Smooth eye height locked to 1.65 m above local finished floor elevation
      const targetEyeY = this.getFloorElevation(cur.x, cur.z) + 1.65;
      cur.y = THREE.MathUtils.lerp(cur.y, targetEyeY, Math.min(1, dt * 10));
    } else {
      this.orbit.update();
    }
  }
}
