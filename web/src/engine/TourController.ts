import * as THREE from 'three';
import type { TourWaypoint } from '../types';
import type { CameraController } from './CameraController';
import type { InteractionSystem } from './InteractionSystem';

export interface TourStatus {
  active: boolean;
  paused: boolean;
  index: number;
  total: number;
  waypoint: TourWaypoint | null;
  progress: number;
}

export class TourController {
  private readonly waypoints: TourWaypoint[];
  private readonly camera: CameraController;
  private readonly interaction: InteractionSystem;
  private readonly onStatusChange: (status: TourStatus) => void;

  public active = false;
  public paused = false;
  private index = 0;
  private segmentTime = 0;
  private readonly moveDuration = 3.2;
  private readonly dwellDuration = 4.2;

  private readonly startPos = new THREE.Vector3();
  private readonly startLook = new THREE.Vector3();
  private readonly curLook = new THREE.Vector3();

  constructor(
    waypoints: TourWaypoint[],
    camera: CameraController,
    interaction: InteractionSystem,
    onStatusChange: (status: TourStatus) => void
  ) {
    this.waypoints = waypoints;
    this.camera = camera;
    this.interaction = interaction;
    this.onStatusChange = onStatusChange;
  }

  start(): void {
    if (this.waypoints.length === 0) return;
    this.active = true;
    this.paused = false;
    this.index = 0;
    this.camera.setRoofCeilingVisible(true);
    this.camera.orbit.enabled = false;
    this.camera.perspCamera.fov = 56;
    this.camera.perspCamera.updateProjectionMatrix();

    // Open entrance & rear terrace doors slightly ahead for smooth walkthrough feel
    this.interaction.toggleDoor('D1', true);
    this.beginSegment(0, true);
    this.emitStatus();
  }

  pause(): void {
    if (!this.active) return;
    this.paused = true;
    this.emitStatus();
  }

  resume(): void {
    if (!this.active) return;
    this.paused = false;
    this.emitStatus();
  }

  togglePlayPause(): void {
    if (!this.active) {
      this.start();
    } else if (this.paused) {
      this.resume();
    } else {
      this.pause();
    }
  }

  skipNext(): void {
    if (!this.active) return;
    if (this.index + 1 >= this.waypoints.length) {
      this.finishToDollhouse();
    } else {
      this.beginSegment(this.index + 1, false);
    }
  }

  skipPrev(): void {
    if (!this.active) return;
    this.beginSegment(Math.max(0, this.index - 1), false);
  }

  restart(): void {
    this.start();
  }

  stop(): void {
    if (!this.active) return;
    this.active = false;
    this.paused = false;
    this.emitStatus();
  }

  private beginSegment(nextIdx: number, snapFirst: boolean): void {
    this.index = nextIdx;
    this.segmentTime = 0;
    const wp = this.waypoints[this.index];
    const targetPos = new THREE.Vector3(...wp.threejs_position);
    const targetLook = new THREE.Vector3(...wp.threejs_look_at);

    // Open relevant doors gracefully as tour visits Rear Terrace & Bedrooms
    if (wp.id === 'WP-05' || wp.id === 'WP-06') this.interaction.toggleDoor('D8', true);
    if (wp.id === 'WP-07') this.interaction.toggleDoor('D2', true);
    if (wp.id === 'WP-08') this.interaction.toggleDoor('D6', true);
    if (wp.id === 'WP-09') this.interaction.toggleDoor('D3', true);
    if (wp.id === 'WP-10') this.interaction.toggleDoor('D4', true);

    if (snapFirst) {
      this.startPos.copy(targetPos).add(new THREE.Vector3(1.6, 0.35, 2.2));
      this.startLook.copy(targetLook);
      this.curLook.copy(targetLook);
    } else {
      this.startPos.copy(this.camera.perspCamera.position);
      this.startLook.copy(this.curLook);
    }
    this.emitStatus();
  }

  private finishToDollhouse(): void {
    this.active = false;
    this.paused = false;
    this.emitStatus();
    // Cinematic finale: glide cleanly into Dollhouse View!
    this.camera.setMode('dollhouse', false);
  }

  private emitStatus(): void {
    this.onStatusChange({
      active: this.active,
      paused: this.paused,
      index: this.index,
      total: this.waypoints.length,
      waypoint: this.active ? this.waypoints[this.index] : null,
      progress: this.waypoints.length > 0 ? (this.index + 1) / this.waypoints.length : 0,
    });
  }

  update(dt: number): void {
    if (!this.active || this.paused) return;
    const wp = this.waypoints[this.index];
    if (!wp) return;

    this.segmentTime += dt;
    const endPos = new THREE.Vector3(...wp.threejs_position);
    const endLook = new THREE.Vector3(...wp.threejs_look_at);

    if (this.segmentTime <= this.moveDuration) {
      const t = this.segmentTime / this.moveDuration;
      const ease = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
      const pos = new THREE.Vector3().lerpVectors(this.startPos, endPos, ease);
      // Subtle natural breathing arc during glide
      pos.y += Math.sin(t * Math.PI) * 0.04;
      this.curLook.lerpVectors(this.startLook, endLook, ease);
      this.camera.setCinematicPose(pos, this.curLook);
    } else {
      // Gentle slow cinematic pan while dwelling in the room
      const dwellT = (this.segmentTime - this.moveDuration) / this.dwellDuration;
      const sway = Math.sin(dwellT * Math.PI) * 0.14;
      const look = endLook.clone();
      look.x += sway;
      this.curLook.copy(look);
      this.camera.setCinematicPose(endPos, look);

      if (dwellT >= 1.0) {
        if (this.index + 1 >= this.waypoints.length) {
          this.finishToDollhouse();
        } else {
          this.beginSegment(this.index + 1, false);
        }
      }
    }
  }
}
