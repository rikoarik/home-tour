# Testing & Verification Guide — Villa Aurelia 123

## 1. Automated Asset & Build Checks
- **TypeScript Compilation**: `npm run typecheck` must exit with `0` errors.
- **Production Build**: `npm run build` must bundle cleanly into `dist/` with all GLB/JSON assets present.
- **Standalone Build**: `npm run build:standalone` must generate `dist-single/villa-aurelia-123-standalone.html` with embedded assets.

## 2. Functional Test Matrix

| Area | Verification Steps | Acceptance Criteria |
|---|---|---|
| **Asset Integrity** | Open app → check browser console & network tab | `architecture.glb`, `collision.glb`, `furniture-warm-luxury.glb`, `scene-config.json`, `tour-waypoints.json`, `floorplan-spec.json` load `200 OK` with zero WebGL/glTF errors. Site spans `9.144 × 13.500 m`. |
| **Welcome Screen** | Inspect initial overlay | Displays Villa Aurelia 123, editable address/price, `123.44 m²` land, `80.17 m²` footprint, `69.43 m²` usable, 3 Bed / 2 Bath, Start Exploring, Start Guided Tour, Contact Agent. |
| **4 Camera Modes** | Switch Exterior → Dollhouse → Floor Plan → First-Person | Dollhouse hides Roof & Ceilings; Floor Plan switches to orthographic top-down with room areas; First-Person locks eye height at `1.65 m` above floor. |
| **Walkthrough & Collisions** | In First-Person, move with WASD toward exterior wall & through open doorway `D1`/`D2` | Movement accelerates/decelerates smoothly; walls block player cleanly; doorways allow smooth passage; mobile joystick works on touch viewport (`390×844`). |
| **Interior Style Switcher** | Switch Warm Luxury → Scandinavian → Modern → Warm Luxury | Lazy-loads GLBs without UI freeze; updates furniture & main floor material while preserving walls/doors/windows. |
| **Dynamic Lighting (06:00–24:00)** | Drag Time-of-Day slider from `06:00` → `13:00` → `17:45` → `19:00` → `21:30` | Sun angle, sky color, reflections, and shadow direction update live; warm interior & exterior lights activate automatically at sunset/blue-hour/night. |
| **Interactive Features** | Click Door `D1` & `D8`; toggle Curtains; toggle Lights; click Sofa to inspect; enable Measure Mode & click 2 points; toggle Dimensions; click Reset Camera & Fullscreen | Doors swing/slide smoothly; curtains animate; inspector displays accurate specs; tape measure shows exact meters & mm; dimension labels toggle cleanly. |
| **Guided Tour & Web Audio** | Click Start Guided Tour → Pause → Resume → Skip → Restart; unmute audio & adjust volume | Camera smoothly visits `WP-01` through `WP-10`, updates room narration card (`m²` + `sq ft` + selling point), opens `D8` at Terrace, transitions to Dollhouse at end; Web Audio plays soft ambient chords without external MP3s. |
| **Quality Settings & Perf** | Switch Low / Medium / High / Ultra in Settings | Pixel ratio & shadow resolution adapt cleanly; FPS stays smooth (60 FPS desktop target, ≥30 FPS mobile target). |
