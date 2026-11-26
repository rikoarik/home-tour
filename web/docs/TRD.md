# Technical Requirements Document (TRD) — Villa Aurelia 123 Interactive 3D Real Estate Experience

## 1. Architectural & Asset Source of Truth
All spatial geometry, material references, interactive doors, collision boundaries, and tour waypoints originate strictly from the approved CADCraft 2D floor plan and Blender 5.3 exports located in `../blender/` and `../floorplan-spec.json`. No architectural dimensions are recreated via arbitrary procedural placeholders.

| Asset | Source | Size | Triangles | Validation Status |
|---|---|---|---|---|
| `architecture.glb` | Blender 5.3 glTF 2.0 Y-up | `2.26 MB` | `14,684` | Verified (`281+` nodes, 8 doors, roof/ceiling toggles, 10 waypoints) |
| `furniture-modern.glb` | Blender 5.3 glTF 2.0 Y-up | `1.67 MB` | `10,170` | Verified (`224` nodes, Modern Minimalist style) |
| `furniture-scandinavian.glb` | Blender 5.3 glTF 2.0 Y-up | `1.77 MB` | `10,170` | Verified (`224` nodes, Scandinavian Natural style) |
| `furniture-warm-luxury.glb` | Blender 5.3 glTF 2.0 Y-up | `1.80 MB` | `10,170` | Verified (`224` nodes, Warm Luxury style) |
| `collision.glb` | Blender 5.3 glTF 2.0 Y-up | `63.8 KB` | `528` | Verified (`44` simplified AABB meshes, open doorways) |
| `scene-config.json` | Blender build pipeline | `7.5 KB` | — | Verified (site bounds, presets, doors, cameras, toggles) |
| `tour-waypoints.json` | Blender build pipeline | `4.3 KB` | — | Verified (10 waypoints, `1.65 m` eye height) |
| `floorplan-spec.json` | CADCraft geometry spec | `47.5 KB` | — | Verified (`123.44 m²` land, `80.17 m²` footprint, `69.43 m²` usable) |

### Coordinate & Unit Contract
- **Metric Scale**: `1 Three.js unit = 1.0 meter`.
- **Site Boundary**: `X ∈ [0.000, 9.144]`, `Z ∈ [-13.500, 0.000]` (right-handed glTF Y-up mapping: `threeX = x_mm / 1000`, `threeY = z_mm / 1000`, `threeZ = -y_mm / 1000`).
- **Finished Interior Floor**: `Y = 0.15 m`. **Clear Ceiling**: `3.00 m` (`2.80 m` wet core). **First-Person Eye Height**: `1.65 m` above active floor (`Y = 1.80 m` indoors, `Y = 1.70 m` outdoors).

## 2. System Architecture
- **Stack**: TypeScript + Vite 6 + Three.js (`GLTFLoader`, `DRACOLoader`, `KTX2Loader`, `MeshoptDecoder`, `OrbitControls`, `Sky`, `PMREMGenerator`).
- **Core Modules (`src/engine/`)**:
  - `AssetManager.ts`: `GLTFLoader` configured with `DRACOLoader`, `KTX2Loader`, and `MeshoptDecoder` readiness; lazy-loads style GLBs on demand, caches parsed scenes, and provides explicit geometry/material/texture disposal on teardown or low-memory mode.
  - `CameraController.ts`: Unified manager for `exterior`, `dollhouse`, `floorplan` (orthographic top-down), and `firstperson` (WASD + pointer drag/lock + smooth acceleration/damping + mobile dual-touch/virtual joystick + AABB collision response).
  - `LightingSystem.ts`: Real-time time-of-day (`06:00`–`24:00`) physical `Sky` + `PMREMGenerator` (single reused render target to avoid shader recompilation) + dynamic directional sun casting soft PCF shadows + automatic interior/exterior practical lights activation during golden hour, blue hour, and night.
  - `InteractionSystem.ts`: Raycasting for interactive hinged/sliding doors (`D1`–`D8` animated around Blender hinge pivots/slide tracks), curtain open/close scaling, room lighting toggle, furniture/material inspection popover, room click-to-enter in Dollhouse/Floorplan modes, and 2-point 3D tape measure tool in meters & millimeters.
  - `TourController.ts`: Catmull-Rom / cubic-eased cinematic guided tour across all 10 verified waypoints (`WP-01`–`WP-10`), synchronized room narration cards (name, `m²` & `sq ft`, key feature, selling point), play/pause/resume/skip/restart controls, ending with a cinematic crane transition into Dollhouse mode.
  - `AmbientAudioEngine.ts`: Zero-dependency Web Audio API procedural luxury ambient soundscape (warm pentatonic pad chords + subtle filtered harmonic shimmer + master gain/mute/volume controls, unlocked on first user gesture).
  - `PerformanceManager.ts`: Adaptive pixel ratio & graphics quality tiers (`low`, `medium`, `high`, `ultra`) controlling shadow map size (`512`–`2048`), antialiasing/DPR, tone-mapping exposure, frustum culling, and live FPS telemetry.

## 3. UI & Accessibility Architecture
- Translucent architectural glass HUD (`backdrop-filter: blur(14px)`), neutral alabaster/obsidian palette, restrained serif + geometric sans + tabular monospace typography.
- Native `<dialog>` modals (Contact Agent, Furniture/Material Inspector, Settings) with `closedby="any"` + fallback backdrop dismiss and keyboard `Esc` support.
- Native `<input type="range">` sliders styled with custom track/thumb tokens and `accent-color` for Time-of-Day (`06:00–24:00`) and Audio Volume.
- Interactive 2D Canvas Mini-Map rendering the exact `floorplan-spec.json` walls/rooms, live camera position + FOV cone, and clickable room teleportation.
- Dedicated `property-config.ts` with clearly editable placeholders for user-customizable metadata (address, price, agent contact).

## 4. Distribution Targets
1. **Standard Production Web Bundle (`dist/`)**: Code-split Vite production bundle + optimized static `/assets/` GLBs & JSONs ready for Cloudflare Pages, Vercel, Netlify, or Firebase Hosting.
2. **Single-HTML Portable Distribution (`dist-single/villa-aurelia-123-standalone.html`)**: Self-contained single HTML file (inlined JS/CSS + base64-embedded GLB/JSON bundle) built via dedicated bundler script for offline/USB/email sharing where practical.
