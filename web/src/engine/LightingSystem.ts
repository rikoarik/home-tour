import * as THREE from 'three';
import { Sky } from 'three/examples/jsm/objects/Sky.js';

export interface LightingState {
  hour: number;
  phaseLabel: string;
  interiorLightsActive: boolean;
  manualInteriorOverride: boolean | null;
}

export interface LogicalLightSource {
  groupId: string;
  isExterior: boolean;
  pos: THREE.Vector3;
  color: number;
  baseIntensity: number;
  currentIntensity: number;
  distance: number;
  decay: number;
}

export interface LightZoneGroup {
  id: string;
  label: string;
  isExterior: boolean;
  enabled: boolean;
  manualToggled: boolean;
  sources: LogicalLightSource[];
  emissiveMats: Set<THREE.MeshStandardMaterial>;
}

/**
 * Pure name-based resolver mapping any 3D lamp, ceiling downlight, chandelier, monitor lightbar,
 * LED strip, backlit mirror, sconce, bollard, wall switch plate, or batched light-zone mesh
 * to its interactive LightZoneGroup ID. Shared by AssetManager (for per-zone batching) & LightingSystem.
 */
export function resolveLightGroupIdFromName(n: string): string | null {
  if (!n) return null;
  const batchMatch = n.match(/^Batch_(?:CEIL_)?LIGHT_([A-Za-z0-9_]+?)__/);
  if (batchMatch) return batchMatch[1];

  // 1. Wall Light Switch Plates
  if (n.includes('SwitchPlate_Living')) return 'Living_Main';
  if (n.includes('SwitchPlate_Dining')) return 'Dining_Pendant';
  if (n.includes('SwitchPlate_Kitchen')) return 'Kitchen_Task';
  if (n.includes('SwitchPlate_Foyer')) return 'Foyer_Entry';
  if (n.includes('SwitchPlate_Studio')) return 'Studio_Desk';
  if (n.includes('SwitchPlate_Master')) return 'Master_Bedroom';
  if (n.includes('SwitchPlate_Ensuite')) return 'Master_Ensuite';
  if (n.includes('SwitchPlate_Bed2')) return 'Bedroom_2';
  if (n.includes('SwitchPlate_SharedBath')) return 'Shared_Bath';
  if (n.includes('SwitchPlate_Laundry')) return 'Laundry';

  // 2. Ceiling Recessed Downlights
  if (n.includes('Fixture_DL_Living')) return 'Living_Main';
  if (n.includes('Fixture_DL_Dining')) return 'Dining_Pendant';
  if (n.includes('Fixture_DL_Kitchen')) return 'Kitchen_Task';
  if (n.includes('Fixture_DL_Foyer')) return 'Foyer_Entry';
  if (n.includes('Fixture_DL_Hall')) return 'Gallery_Hall';
  if (n.includes('Fixture_DL_Bed3')) return 'Studio_Main';
  if (n.includes('Fixture_DL_Master')) return 'Master_Bedroom';
  if (n.includes('Fixture_DL_Ensuite')) return 'Master_Ensuite';
  if (n.includes('Fixture_DL_Bed2')) return 'Bedroom_2';
  if (n.includes('Fixture_DL_SharedBath')) return 'Shared_Bath';
  if (n.includes('Fixture_DL_Laundry')) return 'Laundry';

  // 3. Lamps, Chandeliers, Task Bars, Shelf LEDs & Backlit Mirrors
  if (n.includes('Decor_Living_Lamp') || n.includes('F-LV-TV_UnderGlow') || n.includes('F-LV-CTBL_Candle')) return 'Living_Lamp';
  if (n.includes('F-DN-TBL_Pendant') || n.includes('F-DN-TBL_Rod') || n.includes('Decor_Dining_Pic') || n.includes('Decor_Dining_Flame') || n.includes('Decor_Dining_Taper') || n.includes('Decor_Dining_Holder')) return 'Dining_Pendant';
  if (n.includes('F-KT-E_LEDStrip') || n.includes('F-KT-S_LEDStrip') || n.includes('Decor_Kitchen_Hood')) return 'Kitchen_Task';
  if (n.includes('Decor_Foyer_MirrorHalo')) return 'Foyer_Entry';
  if (n.includes('ScreenBar_') || n.includes('LED_BiasStrip') || n.includes('F-ST-SHELF_LED_') || n.includes('HomelabPC_GPU_LED') || n.includes('HomelabPC_AIO_LED')) return 'Studio_Desk';
  if (n.includes('Decor_Master_Pend') || n.includes('F-MB-NS1_Lamp') || n.includes('F-MB-NS2_Lamp')) return 'Master_Bedside';
  if (n.includes('Decor_Master_VanityHalo')) return 'Master_Bedroom';
  if (n.includes('F-ME-VAN_MirrorHalo')) return 'Master_Ensuite';
  if (n.includes('F-B2-NS_Lamp')) return 'Bedroom_2';
  if (n.includes('F-SB-VAN_MirrorHalo')) return 'Shared_Bath';

  // 4. Exterior Sconces, Bollards & Terrace Lantern
  if (n.includes('Arch_Sconce_Front') || n.includes('Arch_Bollard_Front') || n.includes('Arch_HouseNumber_Backlight')) return 'Exterior_Front';
  if (n.includes('Arch_Sconce_Rear') || n.includes('Arch_Bollard_Rear') || n.includes('Decor_Terrace_Lantern')) return 'Exterior_Rear';
  return null;
}

export class LightingSystem {
  private static readonly LIGHT_POOL_SIZE = 6;
  public readonly sunLight: THREE.DirectionalLight;
  public readonly fillLight: THREE.DirectionalLight;
  public readonly hemiLight: THREE.HemisphereLight;
  private readonly sky: Sky;
  private readonly envScene: THREE.Scene;
  private readonly envGround: THREE.Mesh;
  private readonly envHorizon: THREE.Mesh;
  private readonly pmrem: THREE.PMREMGenerator;
  private envRT: THREE.WebGLRenderTarget | null = null;
  private readonly lightPool: THREE.PointLight[] = [];
  private readonly allSources: LogicalLightSource[] = [];
  private readonly lightGroups = new Map<string, LightZoneGroup>();
  private readonly boundMeshes = new WeakSet<THREE.Mesh>();
  private readonly sunVec = new THREE.Vector3();
  private readonly lastPoolCamPos = new THREE.Vector3(6.0, 1.65, -7.0);
  private lastPoolMode = 'exterior';
  private poolDirty = true;

  private readonly scene: THREE.Scene;
  private readonly renderer: THREE.WebGLRenderer;

  public hour = 14.5; // 14:30 bright tropical afternoon default
  public manualInteriorOverride: boolean | null = null;
  private studioBackdrop = false;
  private lastEnvUpdate = 0;
  private envUpdateIntervalMs = 200;

  setStudioBackdrop(enabled: boolean): void {
    this.studioBackdrop = enabled;
    if (enabled) {
      this.sky.visible = false;
      this.scene.background = new THREE.Color(0x101622);
      if (this.scene.fog instanceof THREE.FogExp2) this.scene.fog.density = 0.0;
    } else {
      this.setTimeOfDay(this.hour, false);
    }
  }

  constructor(scene: THREE.Scene, renderer: THREE.WebGLRenderer) {
    this.scene = scene;
    this.renderer = renderer;

    // Physical Atmospheric Sky
    this.sky = new Sky();
    this.sky.scale.setScalar(180);
    const u = this.sky.material.uniforms;
    u['turbidity'].value = 3.0;
    u['rayleigh'].value = 1.60;
    u['mieCoefficient'].value = 0.005;
    u['mieDirectionalG'].value = 0.82;
    this.scene.add(this.sky);

    // Rich Architectural PMREM environment: warm travertine/oak lower dome + sunlit architectural horizon ring
    // Gives metallic car clearcoat, brass faucets, windows, and honed marble lifelike gradient reflections at 0 ms/frame!
    this.envScene = new THREE.Scene();
    this.envGround = new THREE.Mesh(
      new THREE.SphereGeometry(170, 24, 12, 0, Math.PI * 2, Math.PI * 0.5, Math.PI * 0.5),
      new THREE.MeshBasicMaterial({ color: 0x5c5042, side: THREE.BackSide })
    );
    this.envHorizon = new THREE.Mesh(
      new THREE.CylinderGeometry(165, 165, 20, 24, 1, true),
      new THREE.MeshBasicMaterial({ color: 0xede5d8, side: THREE.BackSide })
    );
    this.envHorizon.position.y = 1.5;
    this.envScene.add(this.envGround);
    this.envScene.add(this.envHorizon);
    this.pmrem = new THREE.PMREMGenerator(renderer);
    this.pmrem.compileEquirectangularShader();

    // Primary Sun Directional Light with crisp 2048x2048 on-demand cached shadows tightly fitted to the 9.144 x 13.500 m plot
    this.sunLight = new THREE.DirectionalLight(0xfff4e4, 3.35);
    this.sunLight.castShadow = true;
    this.sunLight.shadow.mapSize.set(2048, 2048);
    this.sunLight.shadow.camera.near = 2;
    this.sunLight.shadow.camera.far = 42;
    const d = 9.6;
    this.sunLight.shadow.camera.left = -d;
    this.sunLight.shadow.camera.right = d;
    this.sunLight.shadow.camera.top = d;
    this.sunLight.shadow.camera.bottom = -d;
    this.sunLight.shadow.bias = -0.0002;
    this.sunLight.shadow.normalBias = 0.011;
    this.sunLight.shadow.radius = 2.2;
    this.sunLight.target.position.set(4.57, 1.2, -6.75);
    this.scene.add(this.sunLight);
    this.scene.add(this.sunLight.target);

    // Zero-shadow Cool-Sky Architectural Bounce Fill Light (opposite sun azimuth) for photographic warm-sun / cool-shadow depth
    this.fillLight = new THREE.DirectionalLight(0xcfe4ff, 0.42);
    this.fillLight.castShadow = false;
    this.fillLight.target.position.set(4.57, 1.2, -6.75);
    this.scene.add(this.fillLight);
    this.scene.add(this.fillLight.target);

    // Subtle physical sky/ground ambient bounce (kept restrained so shadows & GTAO remain crisp and rich)
    this.hemiLight = new THREE.HemisphereLight(0xdcecff, 0x736350, 0.36);
    this.scene.add(this.hemiLight);
    this.scene.fog = new THREE.FogExp2(0xd8e6f2, 0.0016);

    // Fixed 6-light WebGL PointLight pool (#define NUM_POINT_LIGHTS 6 instead of 18 => 3x lighter PBR fragment shader!)
    for (let i = 0; i < LightingSystem.LIGHT_POOL_SIZE; i++) {
      const pl = new THREE.PointLight(0xffd6a6, 0, 5.0, 2.0);
      pl.name = `Pooled_Light_${i}`;
      pl.castShadow = false;
      this.scene.add(pl);
      this.lightPool.push(pl);
    }

    this.createPracticalLights();
    this.setTimeOfDay(this.hour, true);
  }

  private registerGroup(id: string, label: string, isExterior = false): LightZoneGroup {
    let g = this.lightGroups.get(id);
    if (!g) {
      g = {
        id,
        label,
        isExterior,
        enabled: true,
        manualToggled: false,
        sources: [],
        emissiveMats: new Set<THREE.MeshStandardMaterial>(),
      };
      this.lightGroups.set(id, g);
    }
    return g;
  }

  private createPracticalLights(): void {
    // 16 individually clickable warm 2950K architectural light zones dynamically mapped onto the 6-light GPU pool
    // Mapping: threeX = x_m, threeY = z_m, threeZ = -y_m
    const indoorSpecs: Array<[string, string, number, number, number, number, number]> = [
      ['Living_Main', 'Living Room Ceiling Downlights', 7.2, 2.88, -9.85, 2.15, 5.0],
      ['Living_Lamp', 'Living Room Arched Floor Lamp & TV Underglow', 6.08, 1.85, -8.46, 1.85, 3.8],
      ['Dining_Pendant', 'Dining Linear Chandelier & Picture Light', 6.15, 2.08, -6.8, 2.55, 4.6],
      ['Kitchen_Task', 'Kitchen Ceiling, Hood & Under-Cabinet LEDs', 7.95, 2.35, -6.4, 2.05, 4.0],
      ['Foyer_Entry', 'Foyer Ceiling & Backlit Entry Mirror', 4.65, 2.82, -2.85, 1.85, 3.8],
      ['Gallery_Hall', 'Private Gallery Hall Ceiling Downlight', 4.65, 2.82, -8.4, 1.35, 3.6],
      ['Studio_Main', 'Programmer Studio Ceiling Downlight', 7.5, 2.82, -3.6, 1.85, 4.2],
      ['Studio_Desk', 'Programmer Desk ScreenBar, Bias LED & Homelab Shelf LEDs', 7.5, 1.34, -2.55, 1.65, 3.1],
      ['Master_Bedroom', 'Master Suite Ceiling & Vanity Mirror Lights', 2.2, 2.82, -9.9, 2.15, 4.6],
      ['Master_Bedside', 'Master Bedside Table Lamps & Hanging Pendants', 0.45, 1.15, -10.15, 1.55, 3.4],
      ['Master_Ensuite', 'Master Ensuite Ceiling & Vanity Halo', 4.6, 2.70, -10.3, 1.55, 3.3],
      ['Bedroom_2', 'Bedroom 2 Ceiling & Bedside Lamp', 1.65, 2.80, -6.7, 1.85, 4.0],
      ['Shared_Bath', 'Shared Bathroom Ceiling & Vanity Halo', 4.0, 2.70, -6.1, 1.45, 3.1],
      ['Laundry', 'Laundry & Utility Ceiling Light', 4.0, 2.70, -4.3, 1.35, 2.9],
    ];

    for (const [id, label, x, y, z, intensity, distance] of indoorSpecs) {
      const grp = this.registerGroup(id, label, false);
      const src: LogicalLightSource = {
        groupId: id,
        isExterior: false,
        pos: new THREE.Vector3(x, y, z),
        color: 0xffd6a6,
        baseIntensity: intensity,
        currentIntensity: 0,
        distance,
        decay: 2.0,
      };
      grp.sources.push(src);
      this.allSources.push(src);
    }

    const outdoorSpecs: Array<[string, string, number, number, number, number, number]> = [
      ['Exterior_Front', 'Front Porch, Facade Sconces & Garden Bollards', 4.7, 2.85, -1.6, 2.5, 6.4],
      ['Exterior_Front', 'Front Porch, Facade Sconces & Garden Bollards', 1.55, 2.65, -2.5, 2.2, 6.2],
      ['Exterior_Rear', 'Rear Terrace, Courtyard Sconces, Bollards & Lantern', 6.8, 2.85, -12.3, 2.7, 6.4],
      ['Exterior_Rear', 'Rear Terrace, Courtyard Sconces, Bollards & Lantern', 8.2, 2.85, -12.3, 2.3, 6.0],
    ];

    for (const [id, label, x, y, z, intensity, distance] of outdoorSpecs) {
      const grp = this.registerGroup(id, label, true);
      const src: LogicalLightSource = {
        groupId: id,
        isExterior: true,
        pos: new THREE.Vector3(x, y, z),
        color: 0xffcd94,
        baseIntensity: intensity,
        currentIntensity: 0,
        distance,
        decay: 1.9,
      };
      grp.sources.push(src);
      this.allSources.push(src);
    }
  }

  /**
   * Dynamically binds the 6 closest / highest-impact active architectural light zones
   * to our fixed 6-light WebGL pool — keeping PBR shading 3x lighter with zero shader recompiles.
   */
  updatePooledLights(cameraPos: THREE.Vector3, mode: string, force = false): void {
    if (
      !force &&
      !this.poolDirty &&
      mode === this.lastPoolMode &&
      cameraPos.distanceToSquared(this.lastPoolCamPos) < 0.04
    ) {
      return;
    }
    this.lastPoolCamPos.copy(cameraPos);
    this.lastPoolMode = mode;
    this.poolDirty = false;

    const candidates: Array<{ src: LogicalLightSource; score: number }> = [];
    for (const src of this.allSources) {
      if (src.currentIntensity <= 0.01) continue;
      const distSq = cameraPos.distanceToSquared(src.pos);
      let score: number;
      if (mode === 'exterior') {
        score = (src.currentIntensity * (src.isExterior ? 4.0 : 0.75)) / (1.0 + distSq * 0.08);
      } else if (mode === 'dollhouse' || mode === 'floorplan') {
        score = src.currentIntensity * (src.isExterior ? 0.45 : 1.15);
      } else {
        // First-person: strongly prioritize the viewer's current room & adjacent open-plan space
        score = src.currentIntensity / (0.55 + distSq * 0.30);
      }
      candidates.push({ src, score });
    }

    candidates.sort((a, b) => b.score - a.score);
    for (let i = 0; i < this.lightPool.length; i++) {
      const pl = this.lightPool[i];
      const pick = candidates[i];
      if (pick) {
        pl.position.copy(pick.src.pos);
        pl.color.setHex(pick.src.color);
        pl.intensity = pick.src.currentIntensity;
        pl.distance = pick.src.distance;
        pl.decay = pick.src.decay;
      } else {
        pl.intensity = 0;
      }
    }
  }

  updateDynamicIndoorShadows(_cameraPos: THREE.Vector3, _enableIndoorShadows: boolean): void {
    // Contact shadows are delivered cleanly by half-res GTAOPass (1 pass vs 6 cubemap shadow passes)
  }

  /**
   * Maps any clicked 3D lamp, ceiling downlight, chandelier, monitor lightbar, LED strip,
   * backlit mirror, sconce, bollard, or wall switch plate to its interactive light group ID.
   */
  resolveLightGroupForObject(obj: THREE.Object3D): string | null {
    let cur: THREE.Object3D | null = obj;
    while (cur) {
      const id = resolveLightGroupIdFromName(cur.name || '');
      if (id && this.lightGroups.has(id)) return id;
      cur = cur.parent;
    }
    return null;
  }

  /**
   * Binds emissive 3D fixture materials in architecture.glb and furniture-*.glb to their
   * specific LightZoneGroup so clicking a lamp turns both the PointLight AND the 3D bulb/shade glow ON/OFF.
   */
  bindSceneLightMeshes(root: THREE.Object3D): void {
    root.traverse((obj) => {
      if (!(obj instanceof THREE.Mesh) || this.boundMeshes.has(obj)) return;
      const groupId = this.resolveLightGroupForObject(obj);
      if (!groupId) return;
      const grp = this.lightGroups.get(groupId);
      if (!grp) return;

      const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
      let clonedAny = false;
      const nextMats = mats.map((m) => {
        if (!(m instanceof THREE.MeshStandardMaterial)) return m;
        const mName = m.name || '';
        if (mName.includes('Light_Warm') || mName.includes('Light_Shade') || mName.includes('Light_EV')) {
          const cloned = m.clone();
          cloned.userData.baseEmissiveHex = cloned.emissive.getHex() || 0xffa84c;
          cloned.userData.baseColorHex = cloned.color.getHex() || 0xfff3df;
          cloned.userData.baseEmissiveIntensity = Math.max(1.4, cloned.emissiveIntensity || 1.65);
          grp.emissiveMats.add(cloned);
          clonedAny = true;
          return cloned;
        }
        return m;
      });
      if (clonedAny) {
        obj.material = Array.isArray(obj.material) ? nextMats : nextMats[0];
        this.boundMeshes.add(obj);
      }
    });
    this.syncPracticalLightOutputs();
  }

  /** Removes disposed style emissive material references when freeing unused style GLBs */
  unbindSceneLightMeshes(root: THREE.Object3D): void {
    root.traverse((obj) => {
      if (!(obj instanceof THREE.Mesh)) return;
      const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
      for (const grp of this.lightGroups.values()) {
        for (const m of mats) {
          if (m instanceof THREE.MeshStandardMaterial) {
            grp.emissiveMats.delete(m);
          }
        }
      }
    });
  }

  /** Toggles an individual clicked lamp / room light zone ON or OFF */
  toggleLightGroup(groupId: string, forceState?: boolean): { id: string; label: string; enabled: boolean } | null {
    const grp = this.lightGroups.get(groupId);
    if (!grp) return null;
    grp.enabled = forceState !== undefined ? forceState : !grp.enabled;
    grp.manualToggled = true;
    this.syncPracticalLightOutputs();
    return { id: grp.id, label: grp.label, enabled: grp.enabled };
  }

  setShadowMapSize(size: number): void {
    if (this.sunLight.shadow.mapSize.x === size) return;
    this.sunLight.shadow.mapSize.set(size, size);
    if (this.sunLight.shadow.map) {
      this.sunLight.shadow.map.dispose();
      this.sunLight.shadow.map = null;
    }
  }

  setEnvUpdateInterval(ms: number): void {
    this.envUpdateIntervalMs = ms;
  }

  toggleManualInteriorLights(): boolean {
    const anyOn = Array.from(this.lightGroups.values()).some((g) => !g.isExterior && g.enabled);
    const nextState = !anyOn;
    this.manualInteriorOverride = nextState;
    for (const g of this.lightGroups.values()) {
      g.enabled = nextState;
      g.manualToggled = true;
    }
    this.syncPracticalLightOutputs();
    return nextState;
  }

  getPhaseLabel(hour: number): string {
    if (hour < 7.5) return 'Early Morning';
    if (hour < 11.0) return 'Morning Sunlight';
    if (hour < 16.25) return 'Bright Afternoon';
    if (hour < 18.25) return 'Golden Hour';
    if (hour < 19.6) return 'Blue Hour';
    return 'Night Architecture';
  }

  getState(): LightingState {
    const anyIndoorOn = Array.from(this.lightGroups.values()).some((g) => !g.isExterior && g.enabled);
    return {
      hour: this.hour,
      phaseLabel: this.getPhaseLabel(this.hour),
      interiorLightsActive: anyIndoorOn,
      manualInteriorOverride: this.manualInteriorOverride,
    };
  }

  private syncPracticalLightOutputs(): void {
    const duskFactor =
      this.hour >= 17.0
        ? THREE.MathUtils.smoothstep(this.hour, 17.0, 19.2)
        : this.hour < 7.2
          ? 1.0 - THREE.MathUtils.smoothstep(this.hour, 6.0, 7.2)
          : 0.0;

    // Balanced warm indoor practical lighting: subtle in daylight so crisp sunlight shadows dominate, rich in evening/night!
    const dayOnMult = 0.42 + duskFactor * 1.38;
    const outdoorOnMult = Math.max(0.28, duskFactor * 1.75);

    for (const grp of this.lightGroups.values()) {
      const mult = grp.enabled ? (grp.isExterior ? outdoorOnMult : dayOnMult) : 0.0;
      for (const src of grp.sources) {
        src.currentIntensity = src.baseIntensity * mult;
      }
      for (const mat of grp.emissiveMats) {
        if (grp.enabled) {
          const baseEmit = (mat.userData.baseEmissiveHex as number) || 0xffa84c;
          const baseCol = (mat.userData.baseColorHex as number) || 0xfff3df;
          const baseInt = (mat.userData.baseEmissiveIntensity as number) || 1.65;
          mat.emissive.setHex(baseEmit);
          mat.color.setHex(baseCol);
          mat.emissiveIntensity = baseInt * (0.85 + 0.35 * duskFactor);
        } else {
          // Turned OFF: completely unlit matte shade / lens
          mat.emissive.setHex(0x000000);
          mat.emissiveIntensity = 0.0;
          mat.color.setHex(0xaba59c);
        }
        mat.needsUpdate = true;
      }
    }
    this.poolDirty = true;
    this.updatePooledLights(this.lastPoolCamPos, this.lastPoolMode, true);
  }

  setTimeOfDay(hour: number, forceEnvUpdate = false): LightingState {
    this.hour = THREE.MathUtils.clamp(hour, 6, 24);

    // Solar arc from 06:00 sunrise (East +X) to 12:30 zenith to 18:30 sunset (West -X)
    const daylightProgress = (this.hour - 6.0) / 12.5;
    const isDay = this.hour >= 6.0 && this.hour <= 19.2;
    const elevDeg = isDay
      ? Math.max(-4, Math.sin(Math.min(1, Math.max(0, daylightProgress)) * Math.PI) * 64 - 2)
      : -18;
    const azimDeg = 78 + daylightProgress * 204;

    const phi = THREE.MathUtils.degToRad(90 - elevDeg);
    const theta = THREE.MathUtils.degToRad(azimDeg);
    this.sunVec.setFromSphericalCoords(1, phi, theta);

    const center = new THREE.Vector3(4.57, 1.2, -6.75);
    this.sunLight.position.copy(center).addScaledVector(this.sunVec, 24);
    // Position cool-sky architectural fill opposite the sun azimuth for photographic warm/cool relief
    const fillDir = new THREE.Vector3(-this.sunVec.x, Math.max(0.55, this.sunVec.y * 0.85), -this.sunVec.z).normalize();
    this.fillLight.position.copy(center).addScaledVector(fillDir, 20);

    const sinElev = Math.max(0, Math.sin(THREE.MathUtils.degToRad(Math.max(0, elevDeg))));
    const transmittance = Math.sqrt(sinElev);

    const horizonColor = new THREE.Color(0xff9b54);
    const middayColor = new THREE.Color(0xfff7ec);
    const nightMoon = new THREE.Color(0x4b6a9b);

    if (elevDeg > 0) {
      this.sunLight.color.copy(horizonColor).lerp(middayColor, transmittance);
      this.sunLight.intensity = 0.65 + 3.35 * transmittance;
    } else {
      this.sunLight.color.copy(nightMoon);
      this.sunLight.intensity = 0.24;
      this.sunLight.position.set(14, 18, 8);
    }

    const u = this.sky.material.uniforms;
    u['sunPosition'].value.copy(this.sunVec);

    const isBlueHour = this.hour >= 18.2 && this.hour < 19.7;
    const isNight = this.hour >= 19.7;

    if (isNight) {
      u['turbidity'].value = 1.2;
      u['rayleigh'].value = 0.25;
      this.fillLight.color.setHex(0x283e66);
      this.fillLight.intensity = 0.12;
      this.hemiLight.color.setHex(0x1f3054);
      this.hemiLight.groundColor.setHex(0x161412);
      this.hemiLight.intensity = 0.24;
      this.scene.background = new THREE.Color(0x09101e);
      if (this.scene.fog instanceof THREE.FogExp2) {
        this.scene.fog.color.setHex(0x09101e);
        this.scene.fog.density = 0.0042;
      }
      this.sky.visible = false;
      this.renderer.toneMappingExposure = 1.02;
    } else if (isBlueHour) {
      const t = (this.hour - 18.2) / 1.5;
      u['turbidity'].value = THREE.MathUtils.lerp(5.5, 2.0, t);
      u['rayleigh'].value = THREE.MathUtils.lerp(2.6, 0.8, t);
      this.fillLight.color.setHex(0x6382b8);
      this.fillLight.intensity = THREE.MathUtils.lerp(0.28, 0.14, t);
      this.hemiLight.color.setHex(0x4c6794);
      this.hemiLight.groundColor.setHex(0x3a2e25);
      this.hemiLight.intensity = THREE.MathUtils.lerp(0.42, 0.26, t);
      if (this.scene.fog instanceof THREE.FogExp2) {
        this.scene.fog.color.setHex(0x283652).lerp(new THREE.Color(0x131c30), t);
        this.scene.fog.density = 0.0032;
      }
      this.sky.visible = true;
      this.scene.background = null;
      this.renderer.toneMappingExposure = 1.00;
    } else {
      u['turbidity'].value = THREE.MathUtils.lerp(5.0, 2.5, transmittance);
      u['rayleigh'].value = THREE.MathUtils.lerp(2.3, 1.30, transmittance);
      this.fillLight.color.setHex(0xcfe4ff);
      this.fillLight.intensity = 0.22 + 0.24 * transmittance;
      this.hemiLight.color.setHex(0xdcecff);
      this.hemiLight.groundColor.setHex(0x766652);
      this.hemiLight.intensity = 0.24 + 0.18 * transmittance;
      if (this.scene.fog instanceof THREE.FogExp2) {
        this.scene.fog.color.setHex(0xf2cfb0).lerp(new THREE.Color(0xd8e6f2), transmittance);
        this.scene.fog.density = 0.0016;
      }
      this.sky.visible = true;
      this.scene.background = null;
      this.renderer.toneMappingExposure = THREE.MathUtils.lerp(1.04, 0.96, transmittance);
    }

    if (this.studioBackdrop) {
      this.sky.visible = false;
      this.scene.background = new THREE.Color(0x101622);
      if (this.scene.fog instanceof THREE.FogExp2) this.scene.fog.density = 0.0;
    }

    this.syncPracticalLightOutputs();

    const now = performance.now();
    if (forceEnvUpdate || now - this.lastEnvUpdate >= this.envUpdateIntervalMs) {
      this.updateEnvironmentIBL(isNight);
      this.lastEnvUpdate = now;
    }

    return this.getState();
  }

  private updateEnvironmentIBL(isNight: boolean): void {
    if (isNight) {
      this.scene.environmentIntensity = 0.18;
      return;
    }
    this.scene.environmentIntensity = 0.36;
    const skyVisibleBefore = this.sky.visible;
    this.sky.visible = true;
    this.envScene.add(this.sky);
    const nextRT = this.pmrem.fromScene(this.envScene, 0.04);
    if (this.envRT) this.envRT.dispose();
    this.envRT = nextRT;
    this.scene.environment = this.envRT.texture;
    this.scene.add(this.sky);
    this.sky.visible = skyVisibleBefore;
  }

  dispose(): void {
    this.envRT?.dispose();
    this.pmrem.dispose();
  }
}
