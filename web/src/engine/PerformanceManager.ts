import * as THREE from 'three';
import type { QualityLevel } from '../types';

export interface QualityPreset {
  label: string;
  maxPixelRatio: number;
  shadowMapSize: number;
  shadowsEnabled: boolean;
  postProcessing: boolean;
  gtaoScale: number;
  toneMappingExposureOffset: number;
  envUpdateIntervalMs: number;
}

export const QUALITY_PRESETS: Record<QualityLevel, QualityPreset> = {
  low: {
    label: 'Low (Ultra Fast)',
    maxPixelRatio: 0.85,
    shadowMapSize: 512,
    shadowsEnabled: false,
    postProcessing: false,
    gtaoScale: 0,
    toneMappingExposureOffset: 0.0,
    envUpdateIntervalMs: 500,
  },
  medium: {
    label: 'Medium (Smooth 60 FPS)',
    maxPixelRatio: 1.0,
    shadowMapSize: 1024,
    shadowsEnabled: true,
    postProcessing: false,
    gtaoScale: 0,
    toneMappingExposureOffset: 0.0,
    envUpdateIntervalMs: 320,
  },
  high: {
    label: 'High (Recommended)',
    maxPixelRatio: 1.25,
    shadowMapSize: 2048,
    shadowsEnabled: true,
    postProcessing: true,
    gtaoScale: 0.50,
    toneMappingExposureOffset: 0.0,
    envUpdateIntervalMs: 240,
  },
  ultra: {
    label: 'Ultra (Architectural)',
    maxPixelRatio: 1.5,
    shadowMapSize: 2048,
    shadowsEnabled: true,
    postProcessing: true,
    gtaoScale: 0.70,
    toneMappingExposureOffset: 0.0,
    envUpdateIntervalMs: 160,
  },
};

export class PerformanceManager {
  public level: QualityLevel;
  public currentFps = 60;
  private frames = 0;
  private lastSampleTime = performance.now();
  private readonly renderer: THREE.WebGLRenderer;
  private readonly onQualityApplied?: (preset: QualityPreset) => void;

  constructor(
    renderer: THREE.WebGLRenderer,
    onQualityApplied?: (preset: QualityPreset) => void
  ) {
    this.renderer = renderer;
    this.onQualityApplied = onQualityApplied;
    const isMobile = /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent) || window.innerWidth < 820;
    this.level = isMobile ? 'medium' : 'high';
    this.apply(this.level);
  }

  apply(level: QualityLevel): void {
    this.level = level;
    const preset = QUALITY_PRESETS[level];
    const dpr = Math.min(window.devicePixelRatio || 1, preset.maxPixelRatio);
    this.renderer.setPixelRatio(dpr);
    this.renderer.shadowMap.enabled = preset.shadowsEnabled;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.onQualityApplied?.(preset);
  }

  getPreset(): QualityPreset {
    return QUALITY_PRESETS[this.level];
  }

  tick(now: number): number | null {
    this.frames++;
    const elapsed = now - this.lastSampleTime;
    if (elapsed >= 600) {
      this.currentFps = Math.round((this.frames * 1000) / elapsed);
      this.frames = 0;
      this.lastSampleTime = now;
      return this.currentFps;
    }
    return null;
  }
}
