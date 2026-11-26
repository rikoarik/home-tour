# Application Flow — Villa Aurelia 123 Interactive 3D Real Estate Experience

## 1. Entry & Welcome Experience
1. App initializes WebGL renderer + loads `scene-config.json`, `tour-waypoints.json`, `floorplan-spec.json`, `architecture.glb`, `collision.glb`, and the default interior style (`furniture-warm-luxury.glb`) with a subtle progress bar while orbiting the sunlit exterior in the background.
2. **Cinematic Welcome Overlay** presents:
   - Project Name: *Villa Aurelia 123*
   - Editable Property Address & Asking Price (sourced from `src/config/property-config.ts`)
   - Verified Property Metrics: `123.44 m²` Land · `80.17 m²` Footprint · `69.43 m²` Usable Interior · `3` Bedrooms · `2` Bathrooms · `1` Carport
   - Primary Actions: **Start Exploring** (enters interactive Exterior/Walkthrough mode), **Start Guided Tour** (starts cinematic automated walkthrough + optional ambient music), **Contact Agent** (opens inquiry dialog).

## 2. Core User Flows

### Flow A — Seamless 4-Mode Camera Switching
- **Exterior**: Smooth `OrbitControls` around the full building, carport, front garden, and rear terrace (`Roof` & `Ceilings` visible).
- **Dollhouse**: Smoothly transitions camera to elevated isometric orbit, automatically hides `Roof` and `Ceilings` meshes, displays the fully furnished interior; clicking any room smoothly enters **First-Person** inside that room.
- **Floor Plan**: Switches to true **Orthographic** top-down camera (`Roof` & `Ceilings` hidden), reveals floating room labels with exact dimensions (`mm`) and calculated areas (`m²` / `sq ft`); clicking any room label or floor enters **First-Person** in that room.
- **First-Person Walkthrough**: Places camera at `1.65 m` eye height above floor (`Y = 1.80 m` inside, `Y = 1.70 m` outside). Desktop: `WASD`/Arrows + click-drag look (or Pointer Lock). Mobile: bottom-left virtual touch joystick + right-side look swipe. AABB collision meshes prevent walking through walls/closed boundaries while keeping all 8 doorways passable.

### Flow B — Interchangeable Interior Style Switcher
- User clicks **Modern**, **Scandinavian**, or **Warm Luxury** in the floating bottom dock.
- `AssetManager` lazily fetches the requested style GLB (if not cached), smoothly cross-fades visibility, updates the living/dining/kitchen floor material (`Mat_Floor_ModernStone` / `Mat_Floor_WhiteOak` / `Mat_Floor_Limestone`), and retains architectural geometry untouched.

### Flow C — Dynamic Time-of-Day Lighting (`06:00` – `24:00`)
- Dragging the Time-of-Day slider (or clicking Morning / Afternoon / Golden Hour / Blue Hour / Night quick chips) continuously updates:
  - Physical Sun elevation & azimuth arc (`Sky` shader + `DirectionalLight` position, color temperature, intensity, soft shadows).
  - Throttled `PMREMGenerator` sky environment map refresh for realistic glass & floor reflections.
  - Automatic warm architectural interior downlights, pendant, bedside lamps, and exterior porch/terrace/carport lights fading in smoothly after `17:15`.

### Flow D — Interactive Property Features
- **Click any Door (`D1`–`D8`)**: Smoothly animates hinged doors (`0° ↔ 90°`) around exact Blender hinge pivots, pocket door `D7`, and 3-panel rear terrace sliding glass door `D8`.
- **Toggle Curtains**: Animates floor-to-ceiling living room & master bedroom sheer curtains open/closed.
- **Toggle Room Lights**: Manual override for interior architectural lights on/off.
- **Inspect Furniture & Materials**: Clicking any furnished element highlights it and opens a clean specification card (item name, dimensions, room, material finish, style).
- **Distance Measurement Tool**: Toggle Measure Mode → click Point A & Point B in 3D → renders crisp 3D line + endpoint pins + floating distance pill in meters and millimeters (`e.g., 3.45 m / 3,454 mm`).
- **Dimensions Overlay Toggle**: Shows/hides live 3D-projected room dimension & area badges.
- **Mini-Map & Room Navigator**: Live top-down architectural mini-map showing camera position + view cone; clicking any room in the Room Navigator or Mini-Map teleports cleanly into that space.

### Flow E — Cinematic Guided Tour & Ambient Audio
- Starts at `WP-01` (Street Approach & Front Garden) and smoothly glides sequentially through `WP-02` (Foyer) → `WP-03` (Gallery) → `WP-04` (Dining & Kitchen) → `WP-05` (Living Room) → `WP-06` (Rear Terrace & Garden) → `WP-07` (Master Suite) → `WP-08` (Master Ensuite) → `WP-09` (Bedroom 2) → `WP-10` (Bedroom 3), automatically sliding open `D8` when visiting the Rear Terrace.
- Displays a refined floating narration card for every room (`name`, `m²` & `sq ft`, primary design feature, selling point) with **Play / Pause / Prev / Next / Restart** controls and Web Audio ambient music volume/mute controls.
- Concludes with a cinematic aerial pull-back directly into **Dollhouse View**.
