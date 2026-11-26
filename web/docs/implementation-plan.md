# Implementation Plan — Villa Aurelia 123 Interactive 3D Real Estate Web App

## Phase 1 — Asset Validation & Workspace Setup
1. Copy verified Blender GLBs (`architecture.glb`, `furniture-modern.glb`, `furniture-scandinavian.glb`, `furniture-warm-luxury.glb`, `collision.glb`) and JSON specs (`scene-config.json`, `tour-waypoints.json`, `floorplan-spec.json`) into `web/public/assets/`.
2. Initialize Vite + TypeScript + Three.js project in `web/` with strict TypeScript checking.
3. Verify zero missing files and exact coordinate consistency before writing rendering code.

## Phase 2 — Core 3D Engine (`src/engine/`)
1. `AssetManager.ts`: Configure `GLTFLoader` with `DRACOLoader`, `KTX2Loader`, and `MeshoptDecoder`; load `architecture.glb` + `collision.glb` + default `WarmLuxury` style; implement lazy loading + memory caching + safe disposal for style switching.
2. `LightingSystem.ts`: Implement continuous `06:00`–`24:00` physical `Sky`, reused `PMREMGenerator` IBL target, dynamic directional sun with soft shadows, and automatic interior/exterior architectural lights.
3. `CameraController.ts`: Build all 4 camera modes (`Exterior`, `Dollhouse`, `Floor Plan` orthographic, `First-Person` at `1.65 m` with WASD + mouse look + mobile virtual joystick + AABB collision detection against `collision.glb`).
4. `InteractionSystem.ts`: Implement raycasted door open/close animations (`D1`–`D8`), curtain open/close toggle, furniture/material inspector, click-room-to-enter, 3D distance measurement tool, and projected room dimension badges.
5. `TourController.ts` & `AmbientAudioEngine.ts`: Implement automated cinematic tour through `WP-01`–`WP-10` ending in Dollhouse view, paired with zero-asset procedural Web Audio ambient music.
6. `PerformanceManager.ts`: Implement `Low`, `Medium`, `High`, `Ultra` quality presets, adaptive DPR, frustum culling, and live FPS counter.

## Phase 3 — Luxury Architectural UI (`src/ui/` & `src/styles/`)
1. Build minimalist translucent glass HUD, responsive desktop + mobile layout, Welcome cinematic overlay (`property-config.ts`), Room Navigator, Live 2D Canvas Mini-Map, Style Switcher, Time-of-Day Slider, Guided Tour Bar, Measure HUD, Inspector Popover, Settings Dialog, and Contact Agent Dialog.
2. Apply modern web accessibility practices (native `<dialog>` with `closedby="any"` + fallback, accessible `<input type="range">` styling, keyboard navigation, `prefers-reduced-motion`).

## Phase 4 — Production Build, Single-HTML Distribution & Verification
1. Run TypeScript check (`npx tsc --noEmit`) and Vite production build (`npm run build`).
2. Generate standalone single-HTML distribution (`scripts/build-standalone.mjs` → `dist-single/villa-aurelia-123-standalone.html`).
3. Verify live rendered app in headless Chromium across desktop & mobile viewports: check zero console errors, WebGL canvas rendering, camera mode switching, style switching, time-of-day lighting, guided tour, doors, and performance.
