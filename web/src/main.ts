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
import type { CameraMode, FloorplanSpec, InteriorStyle, QualityLevel, SceneConfig } from './types';

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

  // Grounded tropical residential context outside the 123.44 m² property (auto-hidden in Dollhouse/Floor Plan)
  const contextGroup = new THREE.Group();
  contextGroup.name = 'Context_Neighborhood';
  const horizonMesh = new THREE.Mesh(
    new THREE.PlaneGeometry(180, 180),
    new THREE.MeshStandardMaterial({ color: 0x566948, roughness: 0.94, metalness: 0.0 })
  );
  horizonMesh.rotation.x = -Math.PI / 2;
  horizonMesh.position.set(4.57, -0.04, -6.75);
  horizonMesh.receiveShadow = true;
  contextGroup.add(horizonMesh);

  // Concrete sidewalk & curb along South street frontage (Y_cad < 0 => Z > 0)
  const sidewalkMesh = new THREE.Mesh(
    new THREE.BoxGeometry(46, 0.08, 1.65),
    new THREE.MeshStandardMaterial({ color: 0xbcb8af, roughness: 0.86 })
  );
  sidewalkMesh.position.set(4.57, -0.04, 0.825);
  sidewalkMesh.receiveShadow = true;
  contextGroup.add(sidewalkMesh);

  const curbMesh = new THREE.Mesh(
    new THREE.BoxGeometry(46, 0.12, 0.16),
    new THREE.MeshStandardMaterial({ color: 0x99958d, roughness: 0.84 })
  );
  curbMesh.position.set(4.57, -0.04, 1.68);
  curbMesh.receiveShadow = true;
  contextGroup.add(curbMesh);

  const streetMesh = new THREE.Mesh(
    new THREE.PlaneGeometry(46, 7.5),
    new THREE.MeshStandardMaterial({ color: 0x26292f, roughness: 0.88 })
  );
  streetMesh.rotation.x = -Math.PI / 2;
  streetMesh.position.set(4.57, -0.08, 5.5);
  streetMesh.receiveShadow = true;
  contextGroup.add(streetMesh);

  // Neighboring modern architectural privacy volumes flanking left & right lots
  const neighborMat = new THREE.MeshStandardMaterial({ color: 0xe6e2d9, roughness: 0.88 });
  const neighborW = new THREE.Mesh(new THREE.BoxGeometry(7.2, 3.6, 10.2), neighborMat);
  neighborW.position.set(-3.95, 1.76, -7.4);
  neighborW.receiveShadow = true;
  neighborW.castShadow = true;
  contextGroup.add(neighborW);

  const neighborE = new THREE.Mesh(new THREE.BoxGeometry(7.2, 3.6, 10.2), neighborMat);
  neighborE.position.set(13.1, 1.76, -7.4);
  neighborE.receiveShadow = true;
  neighborE.castShadow = true;
  contextGroup.add(neighborE);

  // Opposite-side luxury residential garden wall, villa & tropical street trees visible through Programmer Studio Window W2
  const oppSidewalk = new THREE.Mesh(
    new THREE.BoxGeometry(46, 0.08, 1.35),
    new THREE.MeshStandardMaterial({ color: 0xbcb8af, roughness: 0.88 })
  );
  oppSidewalk.position.set(4.57, -0.04, 9.15);
  oppSidewalk.receiveShadow = true;
  contextGroup.add(oppSidewalk);

  const oppWall = new THREE.Mesh(
    new THREE.BoxGeometry(30, 1.85, 0.28),
    new THREE.MeshStandardMaterial({ color: 0xded9cf, roughness: 0.92 })
  );
  oppWall.position.set(4.57, 0.92, 9.95);
  oppWall.receiveShadow = true;
  oppWall.castShadow = true;
  contextGroup.add(oppWall);

  const oppWallCap = new THREE.Mesh(
    new THREE.BoxGeometry(30.1, 0.08, 0.34),
    new THREE.MeshStandardMaterial({ color: 0x2a2d33, roughness: 0.65 })
  );
  oppWallCap.position.set(4.57, 1.88, 9.95);
  contextGroup.add(oppWallCap);

  const oppVilla = new THREE.Mesh(new THREE.BoxGeometry(11.5, 3.7, 5.2), neighborMat);
  oppVilla.position.set(7.2, 1.85, 13.0);
  oppVilla.receiveShadow = true;
  oppVilla.castShadow = true;
  contextGroup.add(oppVilla);

  // Organic branching tropical street trees along opposite garden wall — GPU-instanced (5 draw calls instead of 228!)
  const trunkMat = new THREE.MeshStandardMaterial({ color: 0x4b3b2c, roughness: 0.94 });
  const leafMats = [
    new THREE.MeshStandardMaterial({ color: 0x385328, roughness: 0.80, side: THREE.DoubleSide }),
    new THREE.MeshStandardMaterial({ color: 0x4b6a34, roughness: 0.78, side: THREE.DoubleSide }),
    new THREE.MeshStandardMaterial({ color: 0x617f42, roughness: 0.78, side: THREE.DoubleSide }),
  ];
  const treeSpecs: Array<[number, number, number, number]> = [
    [5.6, 9.25, 3.6, 1],
    [9.3, 9.35, 4.0, 2],
    [1.6, 9.3, 3.5, 3],
  ];
  const trunkInst = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.045, 0.09, 1.0, 7), trunkMat, treeSpecs.length);
  trunkInst.castShadow = true;
  const limbInst = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.014, 0.036, 1.0, 5), trunkMat, treeSpecs.length * 5);
  const leafBladeGeo = new THREE.PlaneGeometry(0.24, 0.42);
  const leafMatrices: THREE.Matrix4[][] = [[], [], []];
  const dummy = new THREE.Object3D();

  let tIdx = 0;
  let lIdx = 0;
  for (const [tx, tz, th, seed] of treeSpecs) {
    dummy.position.set(tx, th * 0.26, tz);
    dummy.rotation.set(0, 0, 0);
    dummy.scale.set(1, th * 0.52, 1);
    dummy.updateMatrix();
    trunkInst.setMatrixAt(tIdx++, dummy.matrix);

    for (let b = 0; b < 5; b++) {
      const ang = (b * Math.PI * 2) / 5 + seed * 0.7;
      const limbLen = 0.95 + (b % 2) * 0.35;
      dummy.position.set(
        tx + Math.cos(ang) * limbLen * 0.36,
        th * 0.50 + limbLen * 0.38,
        tz + Math.sin(ang) * limbLen * 0.36
      );
      dummy.rotation.set(Math.sin(ang) * 0.55, 0, -Math.cos(ang) * 0.55);
      dummy.scale.set(1, limbLen, 1);
      dummy.updateMatrix();
      limbInst.setMatrixAt(lIdx++, dummy.matrix);

      const tipX = tx + Math.cos(ang) * limbLen * 0.72;
      const tipY = th * 0.50 + limbLen * 0.72;
      const tipZ = tz + Math.sin(ang) * limbLen * 0.72;
      for (let lf = 0; lf < 14; lf++) {
        const a2 = lf * 2.39996 + seed;
        const r2 = 0.14 + (lf % 4) * 0.13;
        dummy.position.set(
          tipX + Math.cos(a2) * r2,
          tipY + ((lf % 5) - 2) * 0.11,
          tipZ + Math.sin(a2) * r2
        );
        dummy.rotation.set((lf % 3) * 0.5 - 0.5, a2, ((lf + b) % 4) * 0.4 - 0.6);
        dummy.scale.set(1, 1, 1);
        dummy.updateMatrix();
        leafMatrices[(lf + b) % leafMats.length].push(dummy.matrix.clone());
      }
    }
  }
  trunkInst.instanceMatrix.needsUpdate = true;
  limbInst.instanceMatrix.needsUpdate = true;
  contextGroup.add(trunkInst, limbInst);
  for (let m = 0; m < leafMats.length; m++) {
    const mats = leafMatrices[m];
    const leafInst = new THREE.InstancedMesh(leafBladeGeo, leafMats[m], mats.length);
    for (let i = 0; i < mats.length; i++) leafInst.setMatrixAt(i, mats[i]);
    leafInst.instanceMatrix.needsUpdate = true;
    contextGroup.add(leafInst);
  }
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
      (mode) => syncCameraModeUI(mode)
    );
    camCtrl.setCollisionBoxes(collisionBoxes);

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

    // Sync UI for Camera Mode changes
    const syncCameraModeUI = (mode: CameraMode) => {
      document.querySelectorAll<HTMLButtonElement>('[data-cam]').forEach((btn) => {
        btn.classList.toggle('is-active', btn.dataset.cam === mode);
      });
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
      showToast(open ? 'All 8 interactive doors opened' : 'All 8 interactive doors closed');
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
        showToast(open ? 'All 8 interactive doors opened' : 'All 8 interactive doors closed');
      }
    };

    el('btn-wasd-near-door').addEventListener('click', triggerNearestOrAllDoors);
    el('btn-wasd-all-doors').addEventListener('click', () => {
      const open = interaction.toggleAllDoors();
      el('btn-doors').classList.toggle('is-active', open);
      el('btn-wasd-all-doors').classList.toggle('is-active', open);
      showToast(open ? 'All 8 interactive doors opened' : 'All 8 interactive doors closed');
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

    // Architectural Post-Processing Pipeline: RenderPass -> Scaled GTAOPass (Contact AO) -> Half-Res Fixture Bloom -> ACES OutputPass
    const composer = new EffectComposer(renderer);
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
          : 'WASD: Walk · Shift: Run · Auto-Open Doors Active · [E] Nearest Door · [O] All 8 Doors';
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
      const curRoomId = interaction.resolveRoomIdAtPoint(planState.x, planState.yCad);
      if (
        Math.abs(planState.x - lastMiniX) > 0.015 ||
        Math.abs(planState.yCad - lastMiniY) > 0.015 ||
        Math.abs(planState.headingRad - lastMiniH) > 0.01 ||
        curRoomId !== lastMiniRoom
      ) {
        miniMap.render(planState.x, planState.yCad, planState.headingRad, curRoomId);
        lastMiniX = planState.x;
        lastMiniY = planState.yCad;
        lastMiniH = planState.headingRad;
        lastMiniRoom = curRoomId;
      }
      dimOverlay.update(camCtrl.activeCamera, window.innerWidth, window.innerHeight);

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
