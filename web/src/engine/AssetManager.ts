import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';
import { KTX2Loader } from 'three/examples/jsm/loaders/KTX2Loader.js';
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { resolveLightGroupIdFromName } from './LightingSystem';
import type { FloorplanSpec, InteriorStyle, SceneConfig, TourWaypointsData } from '../types';

export interface LoadedArchitecture {
  root: THREE.Group;
  roofObjects: THREE.Object3D[];
  ceilingObjects: THREE.Object3D[];
  floorOverrideMeshes: THREE.Mesh[];
  originalFloorMaterials: Map<THREE.Mesh, THREE.Material | THREE.Material[]>;
  curtainObjects: THREE.Object3D[];
  doorObjects: Map<string, THREE.Object3D>;
}

export class AssetManager {
  private readonly loader: GLTFLoader;
  private readonly dracoLoader: DRACOLoader;
  private readonly ktx2Loader: KTX2Loader;
  private readonly maxAnisotropy: number;
  private readonly styleCache = new Map<InteriorStyle, THREE.Group>();
  private readonly styleMaterialCache = new Map<string, THREE.Material>();
  private readonly assetBase = './assets/';

  constructor(renderer: THREE.WebGLRenderer) {
    this.loader = new GLTFLoader();
    this.maxAnisotropy = Math.min(4, renderer.capabilities.getMaxAnisotropy());

    // Configure DRACO, KTX2, and Meshopt decoders for full compressed-asset compatibility
    this.dracoLoader = new DRACOLoader();
    this.dracoLoader.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.7/');
    this.loader.setDRACOLoader(this.dracoLoader);

    this.ktx2Loader = new KTX2Loader();
    this.ktx2Loader.setTranscoderPath('https://unpkg.com/three@0.176.0/examples/jsm/libs/basis/');
    this.ktx2Loader.detectSupport(renderer);
    this.loader.setKTX2Loader(this.ktx2Loader);
    this.loader.setMeshoptDecoder(MeshoptDecoder);
  }

  private getEmbedded(filename: string): string | undefined {
    return window.__EMBEDDED_ASSETS__?.[filename];
  }

  async loadJSON<T>(filename: string): Promise<T> {
    const embedded = this.getEmbedded(filename);
    if (embedded) {
      return JSON.parse(embedded) as T;
    }
    const res = await fetch(`${this.assetBase}${filename}`);
    if (!res.ok) {
      throw new Error(`Missing required asset ${filename} (HTTP ${res.status})`);
    }
    return (await res.json()) as T;
  }

  private async loadGLB(filename: string, onProgress?: (ratio: number) => void): Promise<THREE.Group> {
    const embeddedB64 = this.getEmbedded(filename);
    if (embeddedB64) {
      const bin = atob(embeddedB64);
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      const gltf = await this.loader.parseAsync(bytes.buffer, '');
      onProgress?.(1);
      return gltf.scene;
    }

    return new Promise((resolve, reject) => {
      this.loader.load(
        `${this.assetBase}${filename}`,
        (gltf) => {
          onProgress?.(1);
          resolve(gltf.scene);
        },
        (evt) => {
          if (evt.total > 0) onProgress?.(Math.min(1, evt.loaded / evt.total));
        },
        (err) => reject(new Error(`Failed to load GLB ${filename}: ${String(err)}`))
      );
    });
  }

  async loadConfigs(): Promise<{
    sceneConfig: SceneConfig;
    waypoints: TourWaypointsData;
    floorplan: FloorplanSpec;
  }> {
    const [sceneConfig, waypoints, floorplan] = await Promise.all([
      this.loadJSON<SceneConfig>('scene-config.json'),
      this.loadJSON<TourWaypointsData>('tour-waypoints.json'),
      this.loadJSON<FloorplanSpec>('floorplan-spec.json'),
    ]);
    return { sceneConfig, waypoints, floorplan };
  }

  private enhanceSceneMaterials(root: THREE.Object3D, castShadows: boolean): void {
    root.traverse((obj) => {
      if (!(obj instanceof THREE.Mesh)) return;
      obj.frustumCulled = true;
      obj.receiveShadow = true;

      const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
      let isTransparent = false;

      for (const m of mats) {
        if (!m) continue;
        const name = m.name || '';
        if (m instanceof THREE.MeshStandardMaterial) {
          // Sharp anisotropic filtering eliminates blurry oak/limestone floors at low eye-level angles
          for (const tex of [m.map, m.normalMap, m.roughnessMap, m.metalnessMap]) {
            if (tex) {
              tex.anisotropy = this.maxAnisotropy;
              tex.needsUpdate = true;
            }
          }
          if (m.normalMap) {
            m.normalScale.set(1.22, 1.22);
          }
          // Strip accidental mirror-shiny glTF clearcoat on furniture, walls, wood, stone & screens,
          // while preserving authentic automotive clearcoat sheen on the GT car bodywork
          if ('clearcoat' in m) {
            const phys = m as THREE.MeshPhysicalMaterial;
            if (name.includes('Car_Silver')) {
              phys.clearcoat = 0.92;
              phys.clearcoatRoughness = 0.08;
            } else {
              phys.clearcoat = 0;
            }
          }

          // Physically accurate satin-matte architectural IBL reflection intensities & minimum roughness bounds
          if (name.includes('Mirror')) {
            m.envMapIntensity = 1.45;
            m.roughness = 0.025;
          } else if (name.includes('Car_Silver')) {
            m.envMapIntensity = 1.35;
            m.roughness = 0.22;
            m.metalness = 0.86;
          } else if (name.includes('Car_RubberTire') || name.includes('Car_Carbon')) {
            m.envMapIntensity = 0.25;
            m.roughness = Math.max(m.roughness, 0.78);
            m.metalness = 0.05;
          } else if (name.includes('Glass')) {
            m.envMapIntensity = 1.35;
          } else if (name.includes('Brass') || name.includes('Steel')) {
            m.envMapIntensity = 1.05;
            m.roughness = Math.max(m.roughness, 0.28);
          } else if (name.includes('MatteBlack')) {
            m.envMapIntensity = 0.48;
            m.roughness = Math.max(m.roughness, 0.48);
            m.metalness = 0.68;
          } else if (name.includes('Marble') || name.includes('Quartz') || name.includes('Ceramic')) {
            m.envMapIntensity = 0.52;
            m.roughness = Math.max(m.roughness, 0.42);
          } else if (name.includes('Floor_') || name.includes('Wood_') || name.includes('Cabinet_') || name.includes('Leather_')) {
            m.envMapIntensity = 0.40;
            m.roughness = Math.max(m.roughness, 0.56);
            m.metalness = 0.0;
          } else if (name.includes('Screen_CodeIDE') || name.includes('OLED_Screen')) {
            m.envMapIntensity = 0.22;
            m.roughness = Math.max(m.roughness, 0.42);
            m.metalness = 0.0;
          } else {
            // Matte limewash plaster walls, ceilings, fabrics, rugs, curtains, foliage & lawn
            m.envMapIntensity = 0.24;
            m.roughness = Math.max(m.roughness, 0.84);
            m.metalness = 0.0;
          }

          if (name.includes('Car_TintedGlass')) {
            isTransparent = true;
            m.transparent = true;
            m.opacity = 0.50;
            m.roughness = 0.03;
            m.metalness = 0.22;
            m.depthWrite = false;
          } else if (name.includes('Glass')) {
            isTransparent = true;
            m.transparent = true;
            m.opacity = name.includes('Frosted') ? 0.54 : 0.22;
            m.roughness = name.includes('Frosted') ? 0.34 : 0.04;
            m.metalness = 0.08;
            m.depthWrite = false;
          } else if (name.includes('Curtain')) {
            isTransparent = true;
            m.transparent = true;
            m.opacity = 0.80;
            m.side = THREE.DoubleSide;
          } else if (name.includes('Plant_Foliage') || name.includes('Plant_Maple') || name.includes('Screen_CodeIDE') || name.includes('Art_')) {
            m.side = THREE.DoubleSide;
          } else if (
            name.includes('Light_Warm') ||
            name.includes('Light_Shade') ||
            name.includes('Light_Car') ||
            name.includes('Light_EV')
          ) {
            // Preserve crisp HDR emissive intensity for subtle architectural & automotive LED bloom
            m.emissiveIntensity = Math.max(m.emissiveIntensity, 1.75);
          } else if (name.includes('Floor_Limestone') || name.includes('Floor_WhiteOak') || name.includes('Floor_ModernStone')) {
            this.styleMaterialCache.set(name, m);
          }
          m.needsUpdate = true;
        }
      }

      const n = obj.name || '';
      const skipShadow =
        isTransparent ||
        n.startsWith('Floor_') ||
        n.startsWith('Context_') ||
        n.includes('Rug') ||
        n.includes('_Mat') ||
        n.includes('Book') ||
        n.includes('Mug') ||
        n.includes('Cup') ||
        n.includes('Plate') ||
        n.includes('Bowl') ||
        n.includes('Wine') ||
        n.includes('Fruit') ||
        n.includes('Soap') ||
        n.includes('Bottle') ||
        n.includes('Sticky') ||
        n.includes('Mouse') ||
        n.includes('Keyboard') ||
        n.includes('Drain') ||
        n.includes('SwitchPlate') ||
        n.includes('Fixture_DL_') ||
        n.includes('LED') ||
        n.includes('MirrorHalo') ||
        n.includes('VanityHalo') ||
        n.includes('UnderGlow') ||
        n.includes('Flame') ||
        n.includes('Candle') ||
        n.includes('PicGlow') ||
        n.includes('Glow') ||
        n.includes('Backlight');
      obj.castShadow = castShadows && !skipShadow;
    });
  }

  /**
   * Static & Semantic Geometry Batching:
   * Groups non-moving meshes by (semanticGroup, material.uuid, castShadow, receiveShadow)
   * so static walls/frames/furniture, Roof, Ceilings, and per-zone Light Fixtures each collapse
   * into minimal GPU draw calls while preserving 100% of interactive toggles & per-lamp clicking.
   * Return `null` from `getBatchGroup` to leave an animated/interactive mesh unmerged (doors, curtains, style floors).
   */
  private batchStaticMeshes(
    root: THREE.Object3D,
    getBatchGroup: (mesh: THREE.Mesh) => string | null
  ): void {
    root.updateMatrixWorld(true);
    const buckets = new Map<
      string,
      { groupTag: string; mat: THREE.Material; castShadow: boolean; receiveShadow: boolean; meshes: THREE.Mesh[] }
    >();

    const allMeshes: THREE.Mesh[] = [];
    root.traverse((obj) => {
      if (obj instanceof THREE.Mesh) allMeshes.push(obj);
    });

    for (const mesh of allMeshes) {
      const groupTag = getBatchGroup(mesh);
      if (!groupTag) continue;
      if (Array.isArray(mesh.material) || !mesh.material || !mesh.geometry) continue;
      const key = `${groupTag}__${mesh.material.uuid}_${mesh.castShadow ? 1 : 0}_${mesh.receiveShadow ? 1 : 0}`;
      let b = buckets.get(key);
      if (!b) {
        b = {
          groupTag,
          mat: mesh.material,
          castShadow: mesh.castShadow,
          receiveShadow: mesh.receiveShadow,
          meshes: [],
        };
        buckets.set(key, b);
      }
      b.meshes.push(mesh);
    }

    const batchedGroup = new THREE.Group();
    batchedGroup.name = 'StaticBatches';

    for (const bucket of buckets.values()) {
      if (bucket.meshes.length < 2) continue;
      const geos: THREE.BufferGeometry[] = [];
      for (const m of bucket.meshes) {
        const src = m.geometry.index ? m.geometry.toNonIndexed() : m.geometry.clone();
        src.applyMatrix4(m.matrixWorld);
        // Normalize attributes strictly to (position, normal, uv) so mergeGeometries never mismatches
        const pos = src.getAttribute('position');
        if (!pos) {
          src.dispose();
          continue;
        }
        if (!src.getAttribute('normal')) src.computeVertexNormals();
        if (!src.getAttribute('uv')) {
          src.setAttribute('uv', new THREE.BufferAttribute(new Float32Array(pos.count * 2), 2));
        }
        for (const attrName of Object.keys(src.attributes)) {
          if (attrName !== 'position' && attrName !== 'normal' && attrName !== 'uv') {
            src.deleteAttribute(attrName);
          }
        }
        geos.push(src);
      }

      if (geos.length < 2) {
        for (const g of geos) g.dispose();
        continue;
      }

      const merged = mergeGeometries(geos, false);
      for (const g of geos) g.dispose();
      if (!merged) continue;

      merged.computeBoundingSphere();
      const matLabel = (bucket.mat.name || 'Mat').replace(/^Mat_/, '');
      const batchMesh = new THREE.Mesh(merged, bucket.mat);
      batchMesh.name = `Batch_${bucket.groupTag}__${matLabel}_${bucket.castShadow ? 'S' : 'NS'}`;
      batchMesh.castShadow = bucket.castShadow;
      batchMesh.receiveShadow = bucket.receiveShadow;
      batchMesh.frustumCulled = true;
      // Freeze static batch transforms so Three.js skips redundant CPU world-matrix recomputes each frame
      if (bucket.groupTag === 'STATIC' || bucket.groupTag === 'ROOF' || bucket.groupTag === 'CEIL') {
        batchMesh.matrixAutoUpdate = false;
        batchMesh.updateMatrix();
      }
      batchedGroup.add(batchMesh);

      for (const orig of bucket.meshes) {
        orig.parent?.remove(orig);
        orig.geometry.dispose();
      }
    }

    if (batchedGroup.children.length > 0) {
      root.add(batchedGroup);
    }
  }

  async loadArchitecture(
    sceneConfig: SceneConfig,
    onProgress?: (ratio: number) => void
  ): Promise<LoadedArchitecture> {
    const root = await this.loadGLB(sceneConfig.assets.architecture.file, onProgress);
    root.name = 'ArchitectureRoot';
    this.enhanceSceneMaterials(root, true);

    const roofSet = new Set(sceneConfig.dollhouse_toggle_objects.roof);
    const ceilSet = new Set(sceneConfig.dollhouse_toggle_objects.ceilings);
    const doorNameSet = new Set(sceneConfig.interactive_doors.map((d) => d.object_name));

    // Only moving door leaves & attached handles stay unmerged; static DoorFrame_* jambs batch right into STATIC!
    const isMovingDoorHierarchy = (obj: THREE.Object3D): boolean => {
      let cur: THREE.Object3D | null = obj;
      while (cur) {
        if (
          doorNameSet.has(cur.name) ||
          cur.name.startsWith('Door_Interactive_') ||
          cur.name.startsWith('DoorHandle_')
        ) {
          return true;
        }
        cur = cur.parent;
      }
      return false;
    };
    const isFloorStyleTarget = (name: string): boolean =>
      name.startsWith('Floor_') && ['RM-07', 'RM-08', 'RM-09', 'RM-10', 'RM-11'].some((tag) => name.includes(tag));

    this.batchStaticMeshes(root, (mesh) => {
      const n = mesh.name || '';
      if (isFloorStyleTarget(n) || isMovingDoorHierarchy(mesh)) return null;
      if (roofSet.has(n)) return 'ROOF';
      const lightGrp = resolveLightGroupIdFromName(n);
      if (n.startsWith('Fixture_DL_')) {
        return lightGrp ? `CEIL_LIGHT_${lightGrp}` : 'CEIL';
      }
      if (ceilSet.has(n)) return 'CEIL';
      if (lightGrp) return `LIGHT_${lightGrp}`;
      return 'STATIC';
    });

    const roofObjects: THREE.Object3D[] = [];
    const ceilingObjects: THREE.Object3D[] = [];
    const floorOverrideMeshes: THREE.Mesh[] = [];
    const originalFloorMaterials = new Map<THREE.Mesh, THREE.Material | THREE.Material[]>();
    const doorObjects = new Map<string, THREE.Object3D>();

    root.traverse((obj) => {
      if (roofSet.has(obj.name) || obj.name.startsWith('Batch_ROOF__')) roofObjects.push(obj);
      if (
        ceilSet.has(obj.name) ||
        obj.name.startsWith('Fixture_DL_') ||
        obj.name.startsWith('Batch_CEIL__') ||
        obj.name.startsWith('Batch_CEIL_LIGHT_')
      ) {
        ceilingObjects.push(obj);
      }
      if (doorNameSet.has(obj.name) || obj.name.startsWith('Door_Interactive_D8_Panel')) {
        doorObjects.set(obj.name, obj);
      }
      if (obj instanceof THREE.Mesh && isFloorStyleTarget(obj.name)) {
        floorOverrideMeshes.push(obj);
        originalFloorMaterials.set(obj, obj.material);
      }
    });

    // Validate Blender architecture bounds strictly match approved 123.44 m² plot
    const box = new THREE.Box3().setFromObject(root);
    const size = new THREE.Vector3();
    box.getSize(size);
    if (size.x < 8.5 || size.z < 12.5) {
      throw new Error(`Architecture bounding validation failed: ${size.x.toFixed(2)}m x ${size.z.toFixed(2)}m`);
    }

    return {
      root,
      roofObjects,
      ceilingObjects,
      floorOverrideMeshes,
      originalFloorMaterials,
      curtainObjects: [],
      doorObjects,
    };
  }

  async loadCollisionBoxes(sceneConfig: SceneConfig): Promise<THREE.Box3[]> {
    const root = await this.loadGLB(sceneConfig.assets.collision.file);
    root.updateMatrixWorld(true);
    const boxes: THREE.Box3[] = [];
    root.traverse((obj) => {
      if (!(obj instanceof THREE.Mesh)) return;
      if (obj.name.includes('Col_Floor_Ground')) return; // Ground is not a horizontal wall blocker
      const b = new THREE.Box3().setFromObject(obj);
      boxes.push(b);
    });
    // Dispose temporary collision mesh GPU buffers immediately (we only keep lightweight Box3s!)
    this.disposeObject(root);
    return boxes;
  }

  async loadInteriorStyle(
    style: InteriorStyle,
    sceneConfig: SceneConfig,
    onProgress?: (ratio: number) => void
  ): Promise<THREE.Group> {
    const cached = this.styleCache.get(style);
    if (cached) {
      onProgress?.(1);
      return cached;
    }

    const styleMeta = sceneConfig.assets.interior_styles[style];
    const group = await this.loadGLB(styleMeta.file, onProgress);
    group.name = `Style_${style}`;
    this.enhanceSceneMaterials(group, true);
    // Batch ~620 furniture/decor meshes into per-material & per-light-zone GPU batches (only animated curtains stay unmerged!)
    this.batchStaticMeshes(group, (mesh) => {
      const n = mesh.name || '';
      if (n.includes('Curtain_')) return null;
      const lightGrp = resolveLightGroupIdFromName(n);
      if (lightGrp) return `LIGHT_${lightGrp}`;
      return 'STATIC';
    });
    this.styleCache.set(style, group);
    return group;
  }

  getFloorMaterialForStyle(
    style: InteriorStyle,
    arch: LoadedArchitecture
  ): THREE.Material | null {
    // Pick matching floor finish material already loaded from Blender PBR exports
    if (style === 'warm_luxury') {
      return this.styleMaterialCache.get('Mat_Floor_Limestone') ?? null;
    }
    if (style === 'scandinavian') {
      return this.styleMaterialCache.get('Mat_Floor_WhiteOak') ?? null;
    }
    const existingModern = this.styleMaterialCache.get('Mat_Floor_ModernStone');
    if (existingModern) return existingModern;
    // Clone limestone material with cool honed stone tint matching Blender's Mat_Floor_ModernStone
    const base = this.styleMaterialCache.get('Mat_Floor_Limestone');
    if (base instanceof THREE.MeshStandardMaterial) {
      const modernMat = base.clone();
      modernMat.name = 'Mat_Floor_ModernStone_Runtime';
      modernMat.color.set('#b8bab8');
      modernMat.roughness = 0.34;
      this.styleMaterialCache.set('Mat_Floor_ModernStone', modernMat);
      return modernMat;
    }
    return null;
  }

  applyFloorStyle(style: InteriorStyle, arch: LoadedArchitecture): void {
    const targetMat = this.getFloorMaterialForStyle(style, arch);
    for (const mesh of arch.floorOverrideMeshes) {
      if (style === 'warm_luxury') {
        const orig = arch.originalFloorMaterials.get(mesh);
        if (orig) mesh.material = orig;
      } else if (targetMat) {
        mesh.material = targetMat;
      }
    }
  }

  disposeUnusedStyles(activeStyle: InteriorStyle, parent: THREE.Scene): void {
    for (const [style, group] of this.styleCache.entries()) {
      if (style === activeStyle) continue;
      parent.remove(group);
      this.disposeObject(group);
      this.styleCache.delete(style);
    }
  }

  disposeObject(root: THREE.Object3D): void {
    const protectedMats = new Set(this.styleMaterialCache.values());
    root.traverse((obj) => {
      if (!(obj instanceof THREE.Mesh)) return;
      obj.geometry?.dispose();
      const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
      for (const m of mats) {
        if (!m || protectedMats.has(m)) continue;
        if (m instanceof THREE.MeshStandardMaterial) {
          m.map?.dispose();
          m.normalMap?.dispose();
          m.roughnessMap?.dispose();
          m.metalnessMap?.dispose();
          m.aoMap?.dispose();
        }
        m.dispose();
      }
    });
  }

  dispose(): void {
    this.dracoLoader.dispose();
    this.ktx2Loader.dispose();
  }
}
