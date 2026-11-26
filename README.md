# home-tour

Interactive photorealistic 3D real estate walkthrough & architectural visualization for **Villa Aurelia 123** (`123.44 m²` plot · `9.144 × 13.500 m` · `80.17 m²` building footprint · 2 Bedrooms + Aesthetic Programmer Studio + Carport with GT Coupe).

Built from a single dimensionally verified architectural specification (`floorplan-spec.json`), modeled in **Blender 5.3**, compressed with **WebP + Meshopt (`EXT_meshopt_compression`)**, and rendered in real time with **Three.js + TypeScript + Vite**.

## Key Features

- **4 Interactive Camera Modes**:
  - **First-Person Walkthrough (`WASD` + Mouse / Mobile Touch Joystick)**: `1.65 m` eye-level height, wall & closed-door collision detection, proximity auto-open doors (`[E]` nearest door, `[O]` all 8 doors, `[C]` curtains).
  - **Dollhouse Cutaway**: Auto-hides roof & ceiling downlights cleanly; click any room to jump straight into walkthrough mode.
  - **Orthographic Floor Plan**: Live projected room dimensions & areas with click-to-enter navigation.
  - **Cinematic Exterior**: Full residence, carport GT car, EV wallbox, and tropical residential neighborhood context.
- **3 Switchable Interior Styles** (with automatic GPU VRAM cleanup):
  - **Warm Luxury** (Walnut, limestone, travertine, brushed brass)
  - **Scandinavian Natural** (White oak, linen, fluted timber)
  - **Modern Minimalist** (Matte charcoal quartz, honed stone)
- **Dynamic Time-of-Day & Clickable Per-Lamp Lighting**:
  - Continuous `06:00–24:00` solar arc, atmospheric sky, cool-sky bounce fill, and `2048×2048` on-demand cached shadows.
  - Click any of **16 lighting zones** or **10 physical wall switch plates** in 3D to toggle individual lamps & emissive bulbs ON/OFF instantly.
- **Real-Time WebGL Optimization**:
  - Semantic static geometry batching & GPU instanced foliage (`~1,214` source meshes → `252` active batches/meshes).
  - Dynamic **6-Light GPU Pool** (`3×` lighter PBR fragment shader with zero shader recompilations).
  - On-demand directional shadow caching (`autoUpdate = false`), half-resolution `GTAOPass` contact ambient occlusion, and smart daytime bloom bypass.
  - Configurable Quality Presets (`Low`, `Medium`, `High`, `Ultra`) in **Settings**.
- **Guided Cinematic Tour + Procedural Ambient Audio**: Automated waypoint tour with room narratives and Web Audio API soundtrack (no external audio files).

## Quick Start

```bash
cd web
npm install
npm run dev
```

Open `http://127.0.0.1:5173/` (or `http://localhost:5173/`).

### Build & Offline Single-HTML Export

```bash
cd web
npm run build            # Type-check + Vite production bundle (web/dist/)
npm run build:standalone # Self-contained offline single HTML (web/dist-single/)
```

## Project Structure

- `floorplan-spec.json` — Single source of truth for site boundaries, walls, doors (`D1`–`D8`), windows (`W1`–`W6`), rooms, furniture, and waypoints.
- `floorplan-blueprint-v1.*` / `floorplan-presentation-v2.*` / `luxury-residence-floorplan.dwg` — Verified 1:50 2D architectural drawings & CAD exports.
- `blender/` — Procedural PBR texture synthesizer (`generate_textures.py`), Blender 5.3 3D builder & Meshopt GLB exporter (`build_house.py`), and Cycles render script (`render_views.py`).
- `web/` — Interactive Three.js + TypeScript + Vite web experience (`web/public/assets/` includes ready-to-run Meshopt GLBs and JSON configs).
