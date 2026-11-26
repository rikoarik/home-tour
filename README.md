# home-tour

Interactive photorealistic **2-Story** 3D real estate walkthrough & architectural visualization for **Villa Aurelia 123** (`123.44 m²` plot · `9.144 × 13.500 m` · `143.8 m²` 2-story gross area · **Lantai 1**: 2 Bedrooms + Aesthetic Programmer Studio + Carport with GT Coupe · **Lantai 2**: Semi-Open **Tempat Jemuran & Service Deck**, **Sky Lounge**, **Front Sky Balcony**, and **Walkable Floating Rear Staircase**).

Built from a single dimensionally verified architectural specification (`floorplan-spec.json`), modeled in **Blender 5.3** with **Cycles Metal GPU Baked Local Architectural AO (`UVMap_AO`)**, compressed with **WebP + Meshopt (`EXT_meshopt_compression`)**, and rendered at **60 FPS** with **Three.js + TypeScript + Vite**.

## Key Features

- **Complete 2-Story Architecture (`All / L1 / L2` Floor Switcher)**:
  - **Lantai 1 (`80.17 m²` footprint)**: Master Suite (`RM-01`/`RM-02`), Bedroom 2 (`RM-03`), Aesthetic Programmer Studio by Window W2 (`RM-04`), Shared Bath (`RM-05`), Laundry (`RM-06`), Foyer (`RM-07`), Gallery (`RM-08`), Open-Plan Living, Dining & Kitchen with **3D recessed stainless double sink & recessed glass oven** (`RM-09`–`RM-11`), Carport with **Catmull-Clark subdivided GT Coupe & EV Wallbox** (`EXT-01`), Front Garden (`EXT-02`), Rear Garden & Oiled Teak Terrace (`EXT-03`–`EXT-04`).
  - **Walkable Floating Rear Staircase (`L1 → L2`)**: 16 walnut treads on twin matte-black steel stringers with recessed under-tread LEDs, angled glass guard, and rainproof skylight canopy — walk smoothly up and down using **WASD**!
  - **Lantai 2 (`63.63 m²` area)**:
    - **`RM-12` Tempat Jemuran & Sky Service Deck (`21.92 m²`)**: Semi-open teak-louver + clear laminated glass skylight rain roof, horizontal/vertical teak privacy breeze-screens, **2 brushed-stainless drying racks** with sculpted draped laundry & wooden clothespins, wall-mounted clothes rail with 5 hangers, stone folding counter with **recessed 3D stainless slop sink & gooseneck tap**, woven rattan hamper, and folding ironing board + steam iron.
    - **`RM-13` L2 Sky Lounge & Family Room (`24.95 m²`)**: Panoramic garden Window `W7`, L-shaped lounge sofa, round travertine coffee table, fluted media wall + 55" OLED, coffee bar credenza, S-fold drapery, and direct access to both Tempat Jemuran (`D9`) and Front Balcony (`D10`).
    - **`EXT-05` L2 Front Sky Balcony (`16.76 m²`)**: Frameless glass railings, teak deck, 2 resort lounge chairs, bistro table, and built-in architectural stone planter.
- **Photorealistic Real-Time WebGL Pipeline (`60 FPS` Desktop & Mobile)**:
  - **Single-Pass Cycles Metal GPU Local Architectural AO (`UVMap_AO` / `TEXCOORD_1`)**: Ray-traced soft contact shadows in wall-ceiling/wall-floor crevices at zero runtime FPS cost.
  - **4x Hardware WebGL2 MSAA + Half-Res `GTAOPass` + `2048×2048` On-Demand Cached Sun Shadows**: Razor-clean pergola slats, louver screens, and window mullions with zero aliasing or z-fighting.
  - **Cloudy Equirectangular Sky Panoramas & PMREM IBL**: Natural tropical blue sky with sunlit cumulus clouds, sunset glow, and starry night reflections across glass, metallic car clearcoat, and brushed brass.
  - **Dynamic 6-Light GPU Pool + 19 Clickable Light Zones & 12 Physical Wall Switches**: Click any lamp, pergola LED bar, mirror halo, sconce, or switch plate in 3D to toggle lights ON/OFF individually.
  - **10 Interactive Doors (`D1`–`D10`)**: Floor-aware proximity auto-open in WASD walkthrough (`[E]` nearest door, `[O]` all 10 doors, `[C]` curtains).
  - **3 Switchable Interior Styles** (`Warm Luxury`, `Scandinavian Natural`, `Modern Minimalist`) with automatic GPU VRAM cleanup.
- **Guided 12-Stop Cinematic Tour + Procedural Ambient Audio**: Automated tour spanning Lantai 1 & Lantai 2 with Web Audio API soundtrack (no external audio files).

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

- `floorplan-spec.json` — Single source of truth for site boundaries, L1 & L2 walls, 10 doors (`D1`–`D10`), 7 windows (`W1`–`W7`), 13 interior rooms + 5 outdoor zones, furniture, and 12 tour waypoints.
- `floorplan-blueprint-v1.*` / `floorplan-presentation-v2.*` / `luxury-residence-floorplan.dwg` — Verified 1:50 2D architectural drawings & CAD exports.
- `blender/` — Procedural PBR texture + cloudy sky + botanical foliage synthesizer (`generate_textures.py`), Blender 5.3 2-story 3D builder, Cycles Metal GPU AO baker & Meshopt GLB exporter (`build_house.py`), and Cycles render script (`render_views.py`).
- `web/` — Interactive Three.js + TypeScript + Vite web experience (`web/public/assets/` includes ready-to-run Meshopt GLBs, cloudy sky WebPs, foliage sprites, and JSON configs).
