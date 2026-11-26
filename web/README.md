# Villa Aurelia 123 — Interactive 3D Luxury Real Estate Experience

Production Three.js + TypeScript + Vite web application integrating the verified CADCraft 2D floor plan and Blender 5.3 GLB assets (`123.44 m²` plot, `80.17 m²` building footprint, `69.43 m²` usable interior).

## Quick Start

```bash
npm install
npm run dev
```

Open the local Vite URL printed in the terminal (default `http://localhost:5173`).

## Production Build & Single-HTML Distribution

```bash
# Type-check & build optimized static bundle to dist/
npm run build

# Preview production build locally
npm run preview

# Build self-contained portable single-HTML file to dist-single/villa-aurelia-123-standalone.html
npm run build:standalone
```

## Deployment Instructions

- **Cloudflare Pages / Netlify / Vercel / Firebase Hosting**: Set the build command to `npm run build` and publish directory to `dist`. All GLBs (`architecture.glb`, `furniture-*.glb`, `collision.glb`) and JSON configs (`scene-config.json`, `tour-waypoints.json`, `floorplan-spec.json`) are served from `dist/assets/`.
- **Offline / Portable Single-HTML**: Distribute `dist-single/villa-aurelia-123-standalone.html` directly (or serve over any static HTTP host); all JS, CSS, JSON, and GLB assets are embedded.
- **Customizing Property Info**: Edit `src/config/property-config.ts` to update property address, asking price, and agent contact details without affecting the architectural geometry.

## Documentation
- [Technical Requirements (TRD)](./docs/TRD.md)
- [Application Flow](./docs/app-flow.md)
- [Implementation Plan](./docs/implementation-plan.md)
- [Testing & Verification Guide](./docs/testing-guide.md)
