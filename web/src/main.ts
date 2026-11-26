import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { GTAOPass } from 'three/examples/jsm/postprocessing/GTAOPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import { PROPERTY_CONFIG } from './config/property-config';
import { AssetManager, type LoadedArchitecture } from './engine/AssetManager';
import { LightingSystem } from './engine/LightingSystem';
import { CameraController } from './engine/CameraController';
import { InteractionSystem } from './engine/InteractionSystem';
import { TourController } from './engine/TourController';
import { AmbientAudioEngine } from './engine/AmbientAudioEngine';
import { PerformanceManager } from './engine/PerformanceManager';
import { MiniMap } from './ui/MiniMap';
import { DimensionOverlay } from './ui/DimensionOverlay';
import type { CameraMode, FloorFilter, FloorplanSpec, InteriorStyle, QualityLevel, SceneConfig } from './types';

function formatHour(hour: number): string {
  const h = Math.floor(hour) % 24;
  const m = Math.round((hour - Math.floor(hour)) * 60) % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

function syncSliderCSS(slider: HTMLInputElement, valueText?: string): void {
  slider.style.setProperty('--attr-min', slider.min || '0');
  slider.style.setProperty('--attr-max', slider.max || '100');
  slider.style.setProperty('--control-value', slider.value);
  if (valueText) slider.setAttribute('aria-valuetext', valueText);
}

function installDialogClosedByFallback(): void {
  if ('closedBy' in HTMLDialogElement.prototype) return;
  const outside = (e: PointerEvent, dialog: HTMLDialogElement) => {
    const r = dialog.getBoundingClientRect();
    return e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom;
  };
  for (const dialog of document.querySelectorAll<HTMLDialogElement>('dialog[closedby="any"]')) {
    let pressedOutside = false;
    dialog.addEventListener('pointerdown', (e) => {
      pressedOutside = outside(e, dialog);
    });
    dialog.addEventListener('pointerup', (e) => {
      if (pressedOutside && outside(e, dialog)) dialog.close();
    });
  }
}

async function bootstrap(): Promise<void> {
  installDialogClosedByFallback();

  // Populate editable Welcome & Contact metadata from PROPERTY_CONFIG
  const el = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
  el('welcome-badge').textContent = PROPERTY_CONFIG.statusBadge;
  el('welcome-title').textContent = PROPERTY_CONFIG.projectName;
  el('welcome-tagline').textContent = PROPERTY_CONFIG.tagline;
  el('welcome-address').textContent = PROPERTY_CONFIG.address;
  el('welcome-price').textContent = PROPERTY_CONFIG.price;
  el('contact-agent-card').textContent =
    `${PROPERTY_CONFIG.agent.name} · ${PROPERTY_CONFIG.agent.title} (${PROPERTY_CONFIG.agent.agency}) — ${PROPERTY_CONFIG.agent.phone} · ${PROPERTY_CONFIG.agent.email}`;

  const canvas = el<HTMLCanvasElement>('scene-canvas');
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    powerPreference: 'high-performance',
  });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.98;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  // On-demand shadow map caching: re-render sun shadows ONLY when sun, doors, roof, or style change
  renderer.shadowMap.autoUpdate = false;
  renderer.shadowMap.needsUpdate = true;
  renderer.info.autoReset = false;

  const markShadowsDirty = () => {
    if (renderer.shadowMap.enabled) {
      renderer.shadowMap.needsUpdate = true;
    }
  };

  const scene = new THREE.Scene();

  // Grounded photorealistic tropical residential neighborhood outside the 123.44 m² property (auto-hidden in Dollhouse/Floor Plan)
  const contextGroup = new THREE.Group();
  contextGroup.name = 'Context_Neighborhood';

  // Synthesize organic tileable procedural canvas textures using seeded Mulberry32 PRNG (ZERO diagonal lattice stripes!)
  const makeMicroCanvasTex = (
    baseHex: string,
    speckA: string,
    speckB: string,
    repeatX: number,
    repeatY: number,
    grid = 0,
    seedInit = 1337
  ): THREE.CanvasTexture => {
    const c = document.createElement('canvas');
    c.width = 256;
    c.height = 256;
    const g = c.getContext('2d')!;
    g.fillStyle = baseHex;
    g.fillRect(0, 0, 256, 256);
    let s = seedInit >>> 0;
    const rand = () => {
      s = (s + 0x6d2b79f5) >>> 0;
      let t = Math.imul(s ^ (s >>> 15), 1 | s);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    // Soft large organic variation blotches (wrapped cleanly across edges)
    for (let i = 0; i < 95; i++) {
      const rx = rand() * 256;
      const ry = rand() * 256;
      const rad = 14 + rand() * 28;
      g.fillStyle = i % 2 === 0 ? speckA : speckB;
      g.globalAlpha = 0.055;
      for (const ox of [-256, 0, 256]) {
        for (const oy of [-256, 0, 256]) {
          if (rx + ox + rad < 0 || rx + ox - rad > 256 || ry + oy + rad < 0 || ry + oy - rad > 256) continue;
          g.beginPath();
          g.arc(rx + ox, ry + oy, rad, 0, Math.PI * 2);
          g.fill();
        }
      }
    }
    // Fine micro-mineral / grass-blade organic stipple
    for (let i = 0; i < 3600; i++) {
      g.fillStyle = i % 2 === 0 ? speckA : speckB;
      g.globalAlpha = 0.11;
      const sx = Math.floor(rand() * 256);
      const sy = Math.floor(rand() * 256);
      g.fillRect(sx, sy, 1 + Math.floor(rand() * 2), 1 + Math.floor(rand() * 2));
    }
    if (grid > 0) {
      g.globalAlpha = 0.24;
      g.strokeStyle = '#6c6860';
      g.lineWidth = 2;
      const step = 256 / grid;
      for (let k = 0; k <= grid; k++) {
        g.beginPath();
        g.moveTo(k * step, 0);
        g.lineTo(k * step, 256);
        g.stroke();
        g.beginPath();
        g.moveTo(0, k * step);
        g.lineTo(256, k * step);
        g.stroke();
      }
    }
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    t.wrapS = THREE.RepeatWrapping;
    t.wrapT = THREE.RepeatWrapping;
    t.repeat.set(repeatX, repeatY);
    t.anisotropy = 4;
    return t;
  };

  const turfTex = makeMicroCanvasTex('#495e3a', '#354829', '#617a4c', 26, 26, 0, 101);
  const sidewalkTex = makeMicroCanvasTex('#c4c0b7', '#9e9a91', '#ddd9d0', 18, 2, 2, 202);
  const asphaltTex = makeMicroCanvasTex('#2c3037', '#202329', '#3d424b', 16, 4, 0, 303);
  const stuccoCtxTex = makeMicroCanvasTex('#eae5dc', '#dad4c9', '#f5f2eb', 3, 2, 0, 404);
  const darkStuccoTex = makeMicroCanvasTex('#393d44', '#2a2d33', '#4c515a', 2, 2, 0, 505);
  const woodCtxTex = makeMicroCanvasTex('#6e4b32', '#523622', '#875f40', 2, 3, 0, 606);

  const horizonMesh = new THREE.Mesh(
    new THREE.PlaneGeometry(180, 180),
    new THREE.MeshStandardMaterial({ map: turfTex, roughness: 0.95, metalness: 0.0 })
  );
  horizonMesh.rotation.x = -Math.PI / 2;
  horizonMesh.position.set(4.57, -0.04, -6.75);
  horizonMesh.receiveShadow = true;
  contextGroup.add(horizonMesh);

  // Concrete sidewalk & curb along South street frontage (Y_cad < 0 => Z > 0)
  const sidewalkMat = new THREE.MeshStandardMaterial({ map: sidewalkTex, roughness: 0.86 });
  const sidewalkMesh = new THREE.Mesh(new THREE.BoxGeometry(52, 0.08, 1.65), sidewalkMat);
  sidewalkMesh.position.set(4.57, -0.04, 0.825);
  sidewalkMesh.receiveShadow = true;
  contextGroup.add(sidewalkMesh);

  const curbMesh = new THREE.Mesh(
    new THREE.BoxGeometry(52, 0.12, 0.16),
    new THREE.MeshStandardMaterial({ color: 0x99958d, roughness: 0.84 })
  );
  curbMesh.position.set(4.57, -0.04, 1.68);
  curbMesh.receiveShadow = true;
  contextGroup.add(curbMesh);

  const streetMesh = new THREE.Mesh(
    new THREE.PlaneGeometry(52, 7.5),
    new THREE.MeshStandardMaterial({ map: asphaltTex, roughness: 0.88 })
  );
  streetMesh.rotation.x = -Math.PI / 2;
  streetMesh.position.set(4.57, -0.08, 5.5);
  streetMesh.receiveShadow = true;
  contextGroup.add(streetMesh);

  // Photorealistic neighboring modern tropical villas (natural setbacks, warm interior-lit multi-pane glass, sunshades & teak louvers)
  const neighborWallMat = new THREE.MeshStandardMaterial({ map: stuccoCtxTex, roughness: 0.90 });
  const neighborDarkMat = new THREE.MeshStandardMaterial({ map: darkStuccoTex, roughness: 0.70, metalness: 0.25 });
  const neighborGlassMat = new THREE.MeshStandardMaterial({
    color: 0x5c7388,
    roughness: 0.06,
    metalness: 0.48,
    transparent: true,
    opacity: 0.68,
    envMapIntensity: 1.55,
  });
  const neighborInteriorMat = new THREE.MeshStandardMaterial({ color: 0x9f927e, roughness: 0.90 });
  const neighborWoodMat = new THREE.MeshStandardMaterial({ map: woodCtxTex, roughness: 0.62 });

  const addArchitecturalNeighbor = (cx: number, cz: number, w: number, h: number, d: number, faceSouth: boolean) => {
    const dir = faceSouth ? 1 : -1;
    const body = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), neighborWallMat);
    body.position.set(cx, h * 0.5 - 0.02, cz);
    body.receiveShadow = true;
    body.castShadow = true;
    contextGroup.add(body);
    // Overhanging architectural roof slab + dark fascia
    const fascia = new THREE.Mesh(new THREE.BoxGeometry(w + 0.45, 0.26, d + 0.45), neighborDarkMat);
    fascia.position.set(cx, h + 0.10, cz);
    fascia.castShadow = true;
    contextGroup.add(fascia);
    // Mid-level horizontal concrete canopy overhang between L1 and L2
    const midBand = new THREE.Mesh(new THREE.BoxGeometry(w + 0.30, 0.16, d + 0.30), neighborDarkMat);
    midBand.position.set(cx, 3.22, cz);
    midBand.castShadow = true;
    contextGroup.add(midBand);
    // Recessed multi-pane architectural windows with interior curtain backing, mullions & slim sunhoods
    const fz = cz + dir * (d * 0.5);
    for (const wy of [1.65, 4.45]) {
      if (wy + 0.85 > h) continue;
      const wx = cx - w * 0.15;
      // Warm interior room backing so glass never looks like a flat black sticker!
      const back = new THREE.Mesh(new THREE.BoxGeometry(2.42, 1.38, 0.04), neighborInteriorMat);
      back.position.set(wx, wy, fz + dir * 0.015);
      contextGroup.add(back);
      // Reflective sky-tinted architectural window glass
      const pane = new THREE.Mesh(new THREE.BoxGeometry(2.46, 1.42, 0.03), neighborGlassMat);
      pane.position.set(wx, wy, fz + dir * 0.055);
      contextGroup.add(pane);
      // Crisp 4-sided perimeter aluminum frame + 2 vertical mullions
      const topBar = new THREE.Mesh(new THREE.BoxGeometry(2.62, 0.09, 0.14), neighborDarkMat);
      topBar.position.set(wx, wy + 0.72, fz + dir * 0.06);
      contextGroup.add(topBar);
      const botBar = new THREE.Mesh(new THREE.BoxGeometry(2.62, 0.09, 0.14), neighborDarkMat);
      botBar.position.set(wx, wy - 0.72, fz + dir * 0.06);
      contextGroup.add(botBar);
      for (const mx of [-1.26, -0.42, 0.42, 1.26]) {
        const mull = new THREE.Mesh(new THREE.BoxGeometry(0.06, 1.44, 0.10), neighborDarkMat);
        mull.position.set(wx + mx, wy, fz + dir * 0.06);
        contextGroup.add(mull);
      }
      // Subtle concrete rain hood above each window
      const hood = new THREE.Mesh(new THREE.BoxGeometry(2.74, 0.08, 0.36), neighborWallMat);
      hood.position.set(wx, wy + 0.80, fz + dir * 0.18);
      hood.castShadow = true;
      contextGroup.add(hood);
    }
    // Vertical teak timber slat screen accent
    for (let sl = 0; sl < 7; sl++) {
      const slat = new THREE.Mesh(new THREE.BoxGeometry(0.08, h * 0.82, 0.14), neighborWoodMat);
      slat.position.set(cx + w * 0.18 + sl * 0.18, h * 0.44, fz + dir * 0.07);
      slat.castShadow = true;
      contextGroup.add(slat);
    }
  };

  // Realistic 3.0m landscaped side setbacks so neighboring luxury villas frame Villa Aurelia naturally without crowding it!
  addArchitecturalNeighbor(-6.4, -7.8, 7.6, 5.8, 10.2, true);
  addArchitecturalNeighbor(15.6, -7.8, 7.6, 5.8, 10.2, true);

  // Opposite-side luxury residential garden wall with teak slats, modern 2-story villa & lush botanical trees (seen through Studio W2 & L2 Balcony!)
  const oppSidewalk = new THREE.Mesh(new THREE.BoxGeometry(52, 0.08, 1.35), sidewalkMat);
  oppSidewalk.position.set(4.57, -0.04, 9.15);
  oppSidewalk.receiveShadow = true;
  contextGroup.add(oppSidewalk);

  const oppWall = new THREE.Mesh(new THREE.BoxGeometry(34, 1.85, 0.28), neighborWallMat);
  oppWall.position.set(4.57, 0.92, 9.95);
  oppWall.receiveShadow = true;
  oppWall.castShadow = true;
  contextGroup.add(oppWall);

  const oppWallCap = new THREE.Mesh(new THREE.BoxGeometry(34.1, 0.08, 0.34), neighborDarkMat);
  oppWallCap.position.set(4.57, 1.88, 9.95);
  contextGroup.add(oppWallCap);
  // Warm teak accent pilasters along opposite garden wall for architectural continuity
  for (const px of [-2.0, 2.2, 6.4, 10.6]) {
    const pil = new THREE.Mesh(new THREE.BoxGeometry(0.55, 1.82, 0.32), neighborWoodMat);
    pil.position.set(px, 0.91, 9.93);
    contextGroup.add(pil);
  }

  addArchitecturalNeighbor(7.8, 14.4, 11.4, 6.2, 5.4, false);
  addArchitecturalNeighbor(-4.6, 14.6, 8.6, 5.6, 5.2, false);

  // Lush Botanical Tropical Street Trees using high-detail alpha-cutout multi-leaf spray sprites!
  const trunkMat = new THREE.MeshStandardMaterial({ color: 0x453526, roughness: 0.94 });
  const foliageB64 = window.__EMBEDDED_ASSETS__?.['foliage_branch_rgba.webp'];
  const foliageUrl = foliageB64 ? `data:image/webp;base64,${foliageB64}` : './assets/foliage_branch_rgba.webp';
  const foliageTex = new THREE.TextureLoader().load(foliageUrl);
  foliageTex.colorSpace = THREE.SRGBColorSpace;
  const foliageMat = new THREE.MeshStandardMaterial({
    map: foliageTex,
    alphaTest: 0.45,
    roughness: 0.78,
    metalness: 0.0,
    side: THREE.DoubleSide,
  });
  const treeSpecs: Array<[number, number, number, number]> = [
    [5.8, 9.30, 4.1, 1],
    [9.4, 9.40, 4.5, 2],
    [1.4, 9.35, 3.8, 3],
    [-1.4, -0.6, 4.2, 4],
    [10.9, -0.8, 4.4, 5],
  ];
  const trunkInst = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.052, 0.105, 1.0, 8), trunkMat, treeSpecs.length);
  trunkInst.castShadow = true;
  const limbInst = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.014, 0.040, 1.0, 6), trunkMat, treeSpecs.length * 6);
  const branchCardGeo = new THREE.PlaneGeometry(1.15, 1.15);
  const branchMatrices: THREE.Matrix4[] = [];
  const dummy = new THREE.Object3D();

  let tIdx = 0;
  let lIdx = 0;
  for (const [tx, tz, th, seed] of treeSpecs) {
    dummy.position.set(tx, th * 0.27, tz);
    dummy.rotation.set(0, 0, 0);
    dummy.scale.set(1, th * 0.54, 1);
    dummy.updateMatrix();
    trunkInst.setMatrixAt(tIdx++, dummy.matrix);

    for (let b = 0; b < 6; b++) {
      const ang = (b * Math.PI * 2) / 6 + seed * 0.63;
      const limbLen = 1.05 + (b % 3) * 0.26;
      dummy.position.set(
        tx + Math.cos(ang) * limbLen * 0.36,
        th * 0.48 + limbLen * 0.36,
        tz + Math.sin(ang) * limbLen * 0.36
      );
      dummy.rotation.set(Math.sin(ang) * 0.55, 0, -Math.cos(ang) * 0.55);
      dummy.scale.set(1, limbLen, 1);
      dummy.updateMatrix();
      limbInst.setMatrixAt(lIdx++, dummy.matrix);

      const tipX = tx + Math.cos(ang) * limbLen * 0.68;
      const tipY = th * 0.48 + limbLen * 0.68;
      const tipZ = tz + Math.sin(ang) * limbLen * 0.68;
      // 9 multi-angle dense botanical leaf-branch sprays per limb for rich, airy natural silhouettes
      for (let lf = 0; lf < 9; lf++) {
        const a2 = lf * 2.39996 + seed + b;
        const r2 = 0.12 + (lf % 4) * 0.20;
        const sc = 0.80 + (lf % 3) * 0.26;
        dummy.position.set(
          tipX + Math.cos(a2) * r2,
          tipY + ((lf % 4) - 1.5) * 0.20,
          tipZ + Math.sin(a2) * r2
        );
        dummy.rotation.set((lf % 3) * 0.50 - 0.50, a2, ((lf + b) % 4) * 0.40 - 0.55);
        dummy.scale.set(sc, sc, sc);
        dummy.updateMatrix();
        branchMatrices.push(dummy.matrix.clone());
      }
    }
  }
  trunkInst.instanceMatrix.needsUpdate = true;
  limbInst.instanceMatrix.needsUpdate = true;
  contextGroup.add(trunkInst, limbInst);
  const foliageInst = new THREE.InstancedMesh(branchCardGeo, foliageMat, branchMatrices.length);
  for (let i = 0; i < branchMatrices.length; i++) foliageInst.setMatrixAt(i, branchMatrices[i]);
  foliageInst.instanceMatrix.needsUpdate = true;
  contextGroup.add(foliageInst);
  // Freeze static neighborhood matrices so Three.js skips redundant CPU matrix recalculations every frame
  contextGroup.traverse((obj) => {
    if (obj !== contextGroup) {
      obj.matrixAutoUpdate = false;
      obj.updateMatrix();
    }
  });
  scene.add(contextGroup);

  let syncPostProcessingSizingRef: (() => void) | null = null;
  const lighting = new LightingSystem(scene, renderer);
  const perf = new PerformanceManager(renderer, (preset) => {
    lighting.setShadowMapSize(preset.shadowMapSize);
    lighting.setEnvUpdateInterval(preset.envUpdateIntervalMs);
    syncPostProcessingSizingRef?.();
    markShadowsDirty();
  });

  const assets = new AssetManager(renderer);
  const audio = new AmbientAudioEngine();

  const setProgress = (pct: number, msg: string) => {
    el('progress-fill').style.width = `${Math.round(pct)}%`;
    el('progress-pct').textContent = `${Math.round(pct)}%`;
    el('progress-status').textContent = msg;
  };

  let sceneConfig: SceneConfig;
  let floorplan: FloorplanSpec;
  let arch: LoadedArchitecture;
  let activeStyle: InteriorStyle = 'warm_luxury';
  let activeStyleGroup: THREE.Group | null = null;

  try {
    setProgress(12, 'Loading architectural configs & tour waypoints…');
    const configs = await assets.loadConfigs();
    sceneConfig = configs.sceneConfig;
    floorplan = configs.floorplan;
    const waypointsData = configs.waypoints;

    setProgress(35, 'Loading verified Blender architecture.glb…');
    arch = await assets.loadArchitecture(sceneConfig, (r) =>
      setProgress(35 + r * 30, 'Loading verified Blender architecture.glb…')
    );
    scene.add(arch.root);

    setProgress(68, 'Loading collision meshes & Warm Luxury interior…');
    const [collisionBoxes, initialStyleGroup] = await Promise.all([
      assets.loadCollisionBoxes(sceneConfig),
      assets.loadInteriorStyle('warm_luxury', sceneConfig),
    ]);
    activeStyleGroup = initialStyleGroup;
    scene.add(activeStyleGroup);
    markShadowsDirty();

    setProgress(100, 'Verified 123.44 m² residence ready');

    // Initialize Controllers
    const camCtrl = new CameraController(
      canvas,
      floorplan,
      arch.roofObjects,
      arch.ceilingObjects,
      arch.level2Objects,
      (mode) => syncCameraModeUI(mode)
    );
    camCtrl.setCollisionBoxes(collisionBoxes);
    camCtrl.setActiveStyleGroup(activeStyleGroup);

    const interaction = new InteractionSystem(scene, arch, sceneConfig, floorplan);
    interaction.registerStyleCurtains(activeStyleGroup);
    lighting.bindSceneLightMeshes(arch.root);
    lighting.bindSceneLightMeshes(activeStyleGroup);
    camCtrl.setDynamicColliderProvider(() => interaction.getClosedDoorCollisionBoxes());

    const dimOverlay = new DimensionOverlay(el('dimension-overlay'), floorplan, (roomId) => {
      tour.stop();
      camCtrl.enterRoom(roomId);
      showToast(`Entered ${getRoomLabel(roomId)}`);
    });

    const miniMap = new MiniMap(el<HTMLCanvasElement>('minimap-canvas'), floorplan, (roomId) => {
      tour.stop();
      camCtrl.enterRoom(roomId);
      showToast(`Teleported to ${getRoomLabel(roomId)}`);
    });

    const tour = new TourController(waypointsData.waypoints, camCtrl, interaction, (status) => {
      const card = el('tour-card');
      card.hidden = !status.active;
      el('btn-dock-tour').classList.toggle('is-active', status.active);
      el('btn-tour-playpause').textContent = status.paused ? 'Resume' : 'Pause';
      if (status.active) {
        dimOverlay.setVisible(false);
        el('btn-dims').classList.remove('is-active');
        document.querySelectorAll<HTMLButtonElement>('[data-cam]').forEach((btn) => {
          btn.classList.remove('is-active');
        });
      }
      if (status.active && status.waypoint) {
        const nar = PROPERTY_CONFIG.tourNarratives[status.waypoint.id];
        el('tour-step').textContent = `Stop ${status.index + 1} of ${status.total} · ${status.waypoint.id}`;
        el('tour-room-name').textContent = nar?.roomName ?? status.waypoint.name;
        el('tour-room-area').textContent = nar
          ? `${nar.areaM2.toFixed(2)} m² · ${nar.areaSqft.toFixed(1)} sq ft`
          : '123.44 m² Residence';
        el('tour-feature').textContent = nar?.designFeature ?? '';
        el('tour-selling').textContent = nar?.sellingPoint ?? '';
      }
    });

    // Helper functions
    let toastTimer: number | null = null;
    const showToast = (msg: string) => {
      const t = el('toast');
      t.textContent = msg;
      t.classList.add('is-visible');
      if (toastTimer) clearTimeout(toastTimer);
      toastTimer = window.setTimeout(() => t.classList.remove('is-visible'), 2400);
    };

    const getRoomLabel = (id: string) =>
      floorplan.rooms.find((r) => r.id === id)?.name ??
      floorplan.outdoor_zones.find((z) => z.id === id)?.name ??
      id;

    // Populate Room Navigator list
    const roomListEl = el('room-list');
    const navItems = [
      ...floorplan.rooms.map((r) => ({ id: r.id, name: r.name, area: r.area_m2 })),
      ...floorplan.outdoor_zones.map((z) => ({ id: z.id, name: z.name, area: z.area_m2 })),
    ];
    for (const item of navItems) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'room-item';
      b.dataset.roomId = item.id;
      b.innerHTML = `<span>${item.name}</span><span class="room-item__area">${item.area.toFixed(1)} m²</span>`;
      b.addEventListener('click', () => {
        tour.stop();
        camCtrl.enterRoom(item.id);
        showToast(`Navigating to ${item.name}`);
      });
      roomListEl.appendChild(b);
    }

    // Sync UI for Camera Mode & Floor Filter changes
    const syncFloorFilterUI = (filter: FloorFilter) => {
      document.querySelectorAll<HTMLButtonElement>('[data-floor]').forEach((btn) => {
        btn.classList.toggle('is-active', btn.dataset.floor === filter);
      });
    };

    const syncCameraModeUI = (mode: CameraMode) => {
      document.querySelectorAll<HTMLButtonElement>('[data-cam]').forEach((btn) => {
        btn.classList.toggle('is-active', btn.dataset.cam === mode);
      });
      syncFloorFilterUI(camCtrl.floorFilter);
      el('btn-roof').classList.toggle('is-active', camCtrl.isRoofVisible());
      const showContext = mode === 'exterior' || mode === 'firstperson';
      contextGroup.visible = showContext;
      lighting.setStudioBackdrop(!showContext);
      markShadowsDirty();
      const showDims = mode === 'floorplan' || manualDimsOn;
      dimOverlay.setVisible(showDims);
      el('btn-dims').classList.toggle('is-active', showDims);

      const isTouchOrNarrow = 'ontouchstart' in window || navigator.maxTouchPoints > 0 || window.innerWidth < 900;
      el('mobile-joystick').hidden = !(mode === 'firstperson' && isTouchOrNarrow);
      el('wasd-door-hud').hidden = mode !== 'firstperson';
    };

    document.querySelectorAll<HTMLButtonElement>('[data-floor]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const f = (btn.dataset.floor || 'all') as FloorFilter;
        camCtrl.setFloorFilter(f);
        syncFloorFilterUI(f);
        markShadowsDirty();
        showToast(
          f === '1'
            ? 'Viewing Lantai 1 (Ground Floor Cutaway)'
            : f === '2'
              ? 'Viewing Lantai 2 (Tempat Jemuran & Sky Lounge)'
              : 'Viewing Full 2-Story Residence (All Floors)'
        );
      });
    });

    let manualDimsOn = false;

    // Enable Welcome CTA buttons
    const btnStartExploring = el<HTMLButtonElement>('btn-start-exploring');
    const btnStartTour = el<HTMLButtonElement>('btn-start-tour');
    btnStartExploring.disabled = false;
    btnStartTour.disabled = false;
    el('welcome-progress').style.display = 'none';

    const dismissWelcome = () => el('welcome-overlay').classList.add('is-hidden');

    btnStartExploring.addEventListener('click', () => {
      dismissWelcome();
      camCtrl.setMode('exterior', false);
      showToast('Explore freely · Click any door or room to interact');
    });

    btnStartTour.addEventListener('click', () => {
      dismissWelcome();
      audio.start();
      syncAudioBtn();
      tour.start();
    });

    // Camera mode buttons
    document.querySelectorAll<HTMLButtonElement>('[data-cam]').forEach((btn) => {
      btn.addEventListener('click', () => {
        tour.stop();
        const mode = btn.dataset.cam as CameraMode;
        camCtrl.setMode(mode, false);
        showToast(`Camera: ${btn.textContent?.trim()}`);
      });
    });

    // Interior Style Switcher (lazy-loads style GLBs smoothly)
    let switchingStyle = false;
    const switchStyle = async (nextStyle: InteriorStyle) => {
      if (switchingStyle || nextStyle === activeStyle) return;
      switchingStyle = true;
      showToast(`Loading ${sceneConfig.assets.interior_styles[nextStyle].label} style…`);
      try {
        const prevGroup = activeStyleGroup;
        const nextGroup = await assets.loadInteriorStyle(nextStyle, sceneConfig);
        if (prevGroup) prevGroup.visible = false;
        if (!nextGroup.parent) scene.add(nextGroup);
        nextGroup.visible = true;
        activeStyleGroup = nextGroup;
        activeStyle = nextStyle;
        camCtrl.setActiveStyleGroup(nextGroup);
        interaction.activeStyle = nextStyle;
        interaction.registerStyleCurtains(nextGroup);
        lighting.bindSceneLightMeshes(nextGroup);
        assets.applyFloorStyle(nextStyle, arch);
        // Free GPU VRAM from previously loaded style GLB so memory stays lean
        if (prevGroup) lighting.unbindSceneLightMeshes(prevGroup);
        assets.disposeUnusedStyles(nextStyle, scene);
        markShadowsDirty();

        document.querySelectorAll<HTMLButtonElement>('[data-style]').forEach((b) => {
          b.classList.toggle('is-active', b.dataset.style === nextStyle);
        });
        showToast(`Interior Style: ${sceneConfig.assets.interior_styles[nextStyle].label}`);
      } catch (err) {
        showToast(`Failed to switch style: ${String(err)}`);
      } finally {
        switchingStyle = false;
      }
    };

    document.querySelectorAll<HTMLButtonElement>('[data-style]').forEach((btn) => {
      btn.addEventListener('click', () => {
        void switchStyle(btn.dataset.style as InteriorStyle);
      });
    });

    // Time-of-Day Slider (06:00 to 24:00)
    const todSlider = el<HTMLInputElement>('tod-slider');
    const todReadout = el('tod-readout');
    const applyHourUI = (hr: number, forceEnv = false) => {
      const st = lighting.setTimeOfDay(hr, forceEnv);
      markShadowsDirty();
      const label = `${formatHour(st.hour)} · ${st.phaseLabel}`;
      todReadout.textContent = label;
      todSlider.value = String(st.hour);
      syncSliderCSS(todSlider, label);
      el('btn-lights').classList.toggle('is-active', st.interiorLightsActive);
    };
    applyHourUI(14.5, true);

    todSlider.addEventListener('input', () => {
      applyHourUI(parseFloat(todSlider.value), false);
    });
    todSlider.addEventListener('change', () => {
      applyHourUI(parseFloat(todSlider.value), true);
    });

    document.querySelectorAll<HTMLButtonElement>('[data-tod]').forEach((btn) => {
      btn.addEventListener('click', () => {
        applyHourUI(parseFloat(btn.dataset.tod || '14.5'), true);
      });
    });

    // Top Bar & Toolbar Interactive Features
    el('btn-toggle-panel').addEventListener('click', () => {
      const panel = el('side-panel');
      const collapsed = panel.classList.toggle('is-collapsed');
      el('btn-toggle-panel').setAttribute('aria-expanded', String(!collapsed));
    });

    el('btn-doors').addEventListener('click', () => {
      const open = interaction.toggleAllDoors();
      el('btn-doors').classList.toggle('is-active', open);
      el('btn-wasd-all-doors').classList.toggle('is-active', open);
      showToast(open ? 'All 10 interactive doors opened' : 'All 10 interactive doors closed');
    });

    const triggerNearestOrAllDoors = () => {
      const near = interaction.toggleNearestDoor(camCtrl.perspCamera.position, 2.8);
      if (near) {
        el('btn-doors').classList.toggle('is-active', interaction.areAllDoorsOpen());
        el('btn-wasd-all-doors').classList.toggle('is-active', interaction.areAllDoorsOpen());
        showToast(`Door ${near.id} (${near.label}) ${near.isOpen ? 'opened' : 'closed'}`);
      } else {
        const open = interaction.toggleAllDoors();
        el('btn-doors').classList.toggle('is-active', open);
        el('btn-wasd-all-doors').classList.toggle('is-active', open);
        showToast(open ? 'All 10 interactive doors opened' : 'All 10 interactive doors closed');
      }
    };

    el('btn-wasd-near-door').addEventListener('click', triggerNearestOrAllDoors);
    el('btn-wasd-all-doors').addEventListener('click', () => {
      const open = interaction.toggleAllDoors();
      el('btn-doors').classList.toggle('is-active', open);
      el('btn-wasd-all-doors').classList.toggle('is-active', open);
      showToast(open ? 'All 10 interactive doors opened' : 'All 10 interactive doors closed');
    });

    // Keyboard shortcuts for WASD Walkthrough door & curtain interaction ([E]/[F]: Nearest Door, [O]: All Doors, [C]: Curtains)
    window.addEventListener('keydown', (e) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.repeat) return;
      if (e.code === 'KeyE' || e.code === 'KeyF') {
        triggerNearestOrAllDoors();
      } else if (e.code === 'KeyO') {
        const open = interaction.toggleAllDoors();
        el('btn-doors').classList.toggle('is-active', open);
        el('btn-wasd-all-doors').classList.toggle('is-active', open);
        showToast(open ? 'All 8 interactive doors opened [O]' : 'All 8 interactive doors closed [O]');
      } else if (e.code === 'KeyC') {
        const open = interaction.toggleCurtains();
        el('btn-curtains').classList.toggle('is-active', open);
        showToast(open ? 'Sheer curtains drawn open [C]' : 'Sheer curtains closed [C]');
      }
    });

    el('btn-curtains').addEventListener('click', () => {
      const open = interaction.toggleCurtains();
      el('btn-curtains').classList.toggle('is-active', open);
      showToast(open ? 'Sheer curtains drawn open' : 'Sheer curtains closed');
    });

    el('btn-lights').addEventListener('click', () => {
      const on = lighting.toggleManualInteriorLights();
      el('btn-lights').classList.toggle('is-active', on);
      showToast(on ? 'Interior architectural lighting ON' : 'Interior architectural lighting OFF');
    });

    el('btn-roof').classList.add('is-active');
    el('btn-roof').addEventListener('click', () => {
      const vis = camCtrl.toggleRoofCeiling();
      el('btn-roof').classList.toggle('is-active', vis);
      markShadowsDirty();
      showToast(vis ? 'Roof & ceilings visible' : 'Roof & ceilings hidden (cutaway)');
    });

    el('btn-dims').addEventListener('click', () => {
      manualDimsOn = !manualDimsOn;
      const show = manualDimsOn || camCtrl.mode === 'floorplan';
      dimOverlay.setVisible(show);
      el('btn-dims').classList.toggle('is-active', show);
    });

    interaction.setMeasureCallback((txt) => {
      el('measure-text').textContent = txt ?? 'Click first point in 3D space to measure';
    });

    el('btn-measure').addEventListener('click', () => {
      const next = !interaction.measureMode;
      interaction.setMeasureMode(next);
      el('btn-measure').classList.toggle('is-active', next);
      el('measure-hud').hidden = !next;
      if (next) showToast('Measure Mode: click two points on any surface');
    });

    el('btn-measure-clear').addEventListener('click', () => interaction.clearMeasurements());

    const syncAudioBtn = () => {
      const btn = el('btn-audio');
      btn.textContent = audio.isMuted ? 'Sound Off' : 'Sound On';
      btn.classList.toggle('is-active', !audio.isMuted);
    };

    el('btn-audio').addEventListener('click', () => {
      audio.toggleMute();
      syncAudioBtn();
      showToast(audio.isMuted ? 'Ambient soundtrack muted' : 'Playing procedural ambient soundtrack');
    });

    el('btn-reset').addEventListener('click', () => {
      tour.stop();
      camCtrl.resetCamera();
      showToast('Camera reset');
    });

    el('btn-fullscreen').addEventListener('click', () => {
      if (!document.fullscreenElement) {
        void document.documentElement.requestFullscreen();
      } else {
        void document.exitFullscreen();
      }
    });

    // Tour controls
    el('btn-dock-tour').addEventListener('click', () => {
      if (tour.active) tour.stop();
      else tour.start();
    });
    el('btn-tour-playpause').addEventListener('click', () => tour.togglePlayPause());
    el('btn-tour-prev').addEventListener('click', () => tour.skipPrev());
    el('btn-tour-next').addEventListener('click', () => tour.skipNext());
    el('btn-tour-restart').addEventListener('click', () => tour.restart());
    el('btn-tour-exit').addEventListener('click', () => tour.stop());

    // Inspector close
    el('btn-insp-close').addEventListener('click', () => {
      el('inspector-card').hidden = true;
    });

    // Settings & Contact Native <dialog> wiring
    const settingsDialog = el<HTMLDialogElement>('settings-dialog');
    const contactDialog = el<HTMLDialogElement>('contact-dialog');
    settingsDialog.addEventListener('close', () => {
      settingsDialog.returnValue = '';
    });
    contactDialog.addEventListener('close', () => {
      contactDialog.returnValue = '';
    });

    el('btn-settings').addEventListener('click', () => settingsDialog.showModal());
    el('btn-contact').addEventListener('click', () => contactDialog.showModal());
    el('btn-welcome-contact').addEventListener('click', () => contactDialog.showModal());
    el('btn-contact-cancel').addEventListener('click', () => contactDialog.close());

    el('contact-form').addEventListener('submit', (e) => {
      e.preventDefault();
      contactDialog.close('submitted');
      showToast(`Inquiry sent to ${PROPERTY_CONFIG.agent.name}`);
      (e.target as HTMLFormElement).reset();
    });

    const qualitySelect = el<HTMLSelectElement>('quality-select');
    qualitySelect.value = perf.level;
    qualitySelect.addEventListener('change', () => {
      const q = qualitySelect.value as QualityLevel;
      perf.apply(q);
      showToast(`Graphics quality: ${q.toUpperCase()}`);
    });

    const volSlider = el<HTMLInputElement>('audio-volume');
    syncSliderCSS(volSlider, '28 percent');
    volSlider.addEventListener('input', () => {
      const v = parseFloat(volSlider.value);
      audio.setVolume(v);
      const pct = `${Math.round(v * 100)}%`;
      el('audio-vol-label').textContent = pct;
      syncSliderCSS(volSlider, `${Math.round(v * 100)} percent`);
    });

    // Canvas click-vs-drag detection for clean Raycast interactions
    let downX = 0;
    let downY = 0;
    canvas.addEventListener('pointerdown', (e) => {
      downX = e.clientX;
      downY = e.clientY;
    });
    canvas.addEventListener('pointerup', (e) => {
      if (Math.hypot(e.clientX - downX, e.clientY - downY) > 6) return;
      const targets: THREE.Object3D[] = [arch.root];
      if (activeStyleGroup) targets.push(activeStyleGroup);
      interaction.handleClick(
        e.clientX,
        e.clientY,
        canvas,
        camCtrl.activeCamera,
        camCtrl.mode,
        targets,
        {
          onDoorToggled: (doorId, isOpen) => showToast(`Door ${doorId} ${isOpen ? 'opened' : 'closed'}`),
          onLightToggled: (hitObj) => {
            const grpId = lighting.resolveLightGroupForObject(hitObj);
            if (!grpId) return false;
            const res = lighting.toggleLightGroup(grpId);
            if (!res) return false;
            el('btn-lights').classList.toggle('is-active', lighting.getState().interiorLightsActive);
            showToast(`${res.label} — ${res.enabled ? 'ON' : 'OFF'}`);
            return true;
          },
          onRoomClicked: (roomId) => {
            tour.stop();
            camCtrl.enterRoom(roomId);
            showToast(`Entered ${getRoomLabel(roomId)}`);
          },
          onInspect: (info) => {
            el('insp-category').textContent = info.category;
            el('insp-title').textContent = info.title;
            el('insp-room').textContent = info.roomName;
            el('insp-dims').textContent = info.dimensions;
            el('insp-mat').textContent = info.materialName;
            el('insp-style').textContent = info.styleLabel;
            el('insp-notes').textContent = info.notes ?? '';
            el('inspector-card').hidden = false;
          },
        }
      );
    });

    // Mobile Virtual Joystick Binding
    const joyZone = el('mobile-joystick');
    const joyKnob = el('joystick-knob');
    let joyPointerId: number | null = null;
    const updateJoy = (clientX: number, clientY: number) => {
      const r = joyZone.getBoundingClientRect();
      const cx = r.left + r.width * 0.5;
      const cy = r.top + r.height * 0.5;
      const maxR = r.width * 0.36;
      let dx = clientX - cx;
      let dy = clientY - cy;
      const dist = Math.hypot(dx, dy);
      if (dist > maxR) {
        dx = (dx / dist) * maxR;
        dy = (dy / dist) * maxR;
      }
      joyKnob.style.transform = `translate(${dx.toFixed(1)}px, ${dy.toFixed(1)}px)`;
      camCtrl.joystickInput.x = dx / maxR;
      camCtrl.joystickInput.y = dy / maxR;
    };
    joyZone.addEventListener('pointerdown', (e) => {
      joyPointerId = e.pointerId;
      joyZone.setPointerCapture(e.pointerId);
      updateJoy(e.clientX, e.clientY);
    });
    joyZone.addEventListener('pointermove', (e) => {
      if (joyPointerId === e.pointerId) updateJoy(e.clientX, e.clientY);
    });
    const resetJoy = () => {
      joyPointerId = null;
      joyKnob.style.transform = 'translate(0px, 0px)';
      camCtrl.joystickInput.x = 0;
      camCtrl.joystickInput.y = 0;
    };
    joyZone.addEventListener('pointerup', resetJoy);
    joyZone.addEventListener('pointercancel', resetJoy);

    // Architectural Post-Processing Pipeline: 4x Hardware MSAA RenderTarget -> Scaled GTAOPass -> Half-Res Fixture Bloom -> ACES OutputPass
    // Hardware WebGL2 MSAA eliminates all staircase jagged aliasing on thin pergola slats, louvers & window mullions!
    const msaaRT = new THREE.WebGLRenderTarget(window.innerWidth, window.innerHeight, {
      type: THREE.HalfFloatType,
      samples: 4,
    });
    const composer = new EffectComposer(renderer, msaaRT);
    const renderPass = new RenderPass(scene, camCtrl.activeCamera);
    const initGtaoScale = Math.max(0.35, perf.getPreset().gtaoScale || 0.55);
    const gtaoPass = new GTAOPass(
      scene,
      camCtrl.activeCamera,
      Math.max(256, Math.round(window.innerWidth * initGtaoScale)),
      Math.max(256, Math.round(window.innerHeight * initGtaoScale))
    );
    gtaoPass.output = GTAOPass.OUTPUT.Default;
    gtaoPass.blendIntensity = 0.78;
    gtaoPass.updateGtaoMaterial({
      radius: 0.36,
      distanceExponent: 1.9,
      thickness: 0.85,
      scale: 1.04,
      samples: 5,
      distanceFallOff: 0.90,
    });
    gtaoPass.updatePdMaterial({
      lumaPhi: 10,
      depthPhi: 2,
      normalPhi: 3,
      radius: 4,
      radiusExponent: 1,
      rings: 1,
      samples: 5,
    });
    const bloomPass = new UnrealBloomPass(
      new THREE.Vector2(
        Math.max(256, Math.round(window.innerWidth * 0.5)),
        Math.max(256, Math.round(window.innerHeight * 0.5))
      ),
      0.11, // ultra-subtle glow strictly on true emissive fixtures
      0.42,
      1.60  // prevents sunlit white plaster walls from ever washing out
    );
    const outputPass = new OutputPass();
    composer.addPass(renderPass);
    composer.addPass(gtaoPass);
    composer.addPass(bloomPass);
    composer.addPass(outputPass);

    const syncPostProcessingSizing = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      const preset = perf.getPreset();
      const dpr = Math.min(window.devicePixelRatio || 1, preset.maxPixelRatio);
      composer.setPixelRatio(dpr);
      composer.setSize(w, h);
      const gScale = Math.max(0.35, preset.gtaoScale || 0.55);
      gtaoPass.setSize(Math.max(256, Math.round(w * gScale)), Math.max(256, Math.round(h * gScale)));
      bloomPass.resolution.set(Math.max(256, Math.round(w * 0.5)), Math.max(256, Math.round(h * 0.5)));
    };
    syncPostProcessingSizingRef = syncPostProcessingSizing;
    syncPostProcessingSizing();

    // Resize handling
    window.addEventListener('resize', () => {
      renderer.setSize(window.innerWidth, window.innerHeight);
      syncPostProcessingSizing();
      camCtrl.resize(window.innerWidth, window.innerHeight);
    });

    // Render Loop
    const clock = new THREE.Clock();
    const fpsBadge = el('fps-badge');

    // Expose safe runtime inspection hook for automated verification
    (window as unknown as Record<string, unknown>).__VILLA_APP__ = {
      setMode: (m: CameraMode) => camCtrl.setMode(m, true),
      setFloorFilter: (f: FloorFilter) => {
        camCtrl.setFloorFilter(f);
        syncFloorFilterUI(f);
        markShadowsDirty();
      },
      switchStyle,
      setTimeOfDay: (h: number) => applyHourUI(h, true),
      setQuality: (q: QualityLevel) => {
        qualitySelect.value = q;
        perf.apply(q);
      },
      startTour: () => {
        dismissWelcome();
        tour.start();
      },
      toggleDoors: (forceOpen?: boolean) => {
        const open = interaction.toggleAllDoors(forceOpen);
        el('btn-doors').classList.toggle('is-active', open);
        el('btn-wasd-all-doors').classList.toggle('is-active', open);
        markShadowsDirty();
        return open;
      },
      toggleLightGroup: (groupId: string, forceState?: boolean) => {
        const res = lighting.toggleLightGroup(groupId, forceState);
        el('btn-lights').classList.toggle('is-active', lighting.getState().interiorLightsActive);
        return res;
      },
      teleportTo: (x: number, y: number, z: number, lx: number, ly: number, lz: number) => {
        camCtrl.setMode('firstperson', true);
        camCtrl.teleportFirstPerson(new THREE.Vector3(x, y, z), new THREE.Vector3(lx, ly, lz), true);
      },
      getDoorStates: () => interaction.getDoorStatesSummary(),
      getState: () => ({
        mode: camCtrl.mode,
        style: activeStyle,
        hour: lighting.hour,
        quality: perf.level,
        tourActive: tour.active,
        fps: perf.currentFps,
        drawCalls: renderer.info.render.calls,
        triangles: renderer.info.render.triangles,
        geometries: renderer.info.memory.geometries,
        textures: renderer.info.memory.textures,
        roofVisible: camCtrl.isRoofVisible(),
        doors: interaction.getDoorStatesSummary(),
      }),
    };

    const wasdDoorText = el('wasd-door-text');
    const btnWasdNearDoor = el('btn-wasd-near-door');
    let lastMiniX = Number.NaN;
    let lastMiniY = Number.NaN;
    let lastMiniH = Number.NaN;
    let lastMiniRoom: string | null = '__init__';
    let lastMiniFloor: 1 | 2 = 1;

    const animate = (now: number) => {
      requestAnimationFrame(animate);
      const dt = Math.min(0.05, clock.getDelta());

      tour.update(dt);
      camCtrl.update(dt, tour.active);

      // In WASD First-Person mode, automatically open approached doors & update live door HUD prompt
      const nearbyDoor = interaction.updateWalkthroughDoors(
        camCtrl.perspCamera.position,
        camCtrl.mode === 'firstperson' && !tour.active,
        (doorId, label) => {
          el('btn-doors').classList.toggle('is-active', interaction.areAllDoorsOpen());
          el('btn-wasd-all-doors').classList.toggle('is-active', interaction.areAllDoorsOpen());
          showToast(`Auto-opened ${doorId} (${label})`);
        }
      );
      if (camCtrl.mode === 'firstperson') {
        const nextHudText = nearbyDoor
          ? `Door ${nearbyDoor.id} (${nearbyDoor.label}) — ${nearbyDoor.isOpen ? 'OPEN' : 'CLOSED'} (${nearbyDoor.dist.toFixed(1)}m)`
          : 'WASD: Walk & Climb Stairs · Shift: Run · Auto-Open Doors · [E] Nearest Door · [O] All 10 Doors';
        const nextBtnText = nearbyDoor
          ? `${nearbyDoor.isOpen ? 'Close' : 'Open'} ${nearbyDoor.id} [E]`
          : 'Nearest Door [E]';
        if (wasdDoorText.textContent !== nextHudText) wasdDoorText.textContent = nextHudText;
        if (btnWasdNearDoor.textContent !== nextBtnText) btnWasdNearDoor.textContent = nextBtnText;
      }

      if (interaction.update(dt)) {
        markShadowsDirty();
      }

      const planState = camCtrl.getCameraPlanState();
      const activeFloor: 1 | 2 =
        camCtrl.floorFilter === '2'
          ? 2
          : camCtrl.floorFilter === '1'
            ? 1
            : camCtrl.activeCamera.position.y >= 2.85 && camCtrl.mode === 'firstperson'
              ? 2
              : 1;
      const curRoomId = interaction.resolveRoomIdAtPoint(
        planState.x,
        planState.yCad,
        activeFloor === 2 ? 4.8 : 1.6
      );
      if (
        Math.abs(planState.x - lastMiniX) > 0.015 ||
        Math.abs(planState.yCad - lastMiniY) > 0.015 ||
        Math.abs(planState.headingRad - lastMiniH) > 0.01 ||
        curRoomId !== lastMiniRoom ||
        activeFloor !== lastMiniFloor
      ) {
        miniMap.render(planState.x, planState.yCad, planState.headingRad, curRoomId, activeFloor);
        lastMiniX = planState.x;
        lastMiniY = planState.yCad;
        lastMiniH = planState.headingRad;
        lastMiniRoom = curRoomId;
        lastMiniFloor = activeFloor;
      }
      dimOverlay.update(camCtrl.activeCamera, window.innerWidth, window.innerHeight, camCtrl.floorFilter);

      lighting.updatePooledLights(camCtrl.activeCamera.position, camCtrl.mode);

      const preset = perf.getPreset();
      renderer.info.reset();
      if (preset.postProcessing) {
        renderPass.camera = camCtrl.activeCamera;
        gtaoPass.camera = camCtrl.activeCamera;
        gtaoPass.enabled = preset.gtaoScale > 0 && camCtrl.mode !== 'floorplan';
        // Smart Daytime Bloom Bypass: skips 11 full-screen Gaussian passes in bright daylight while preserving sunset/night lamp halation
        bloomPass.enabled = perf.level === 'ultra' || lighting.hour >= 17.15 || lighting.hour < 7.0;
        composer.render();
      } else {
        renderer.render(scene, camCtrl.activeCamera);
      }

      const sampledFps = perf.tick(now);
      if (sampledFps !== null) {
        fpsBadge.textContent = `${sampledFps} FPS`;
      }
    };

    requestAnimationFrame(animate);
  } catch (err) {
    setProgress(0, `Asset validation error: ${err instanceof Error ? err.message : String(err)}`);
    console.error(err);
  }
}

void bootstrap();
