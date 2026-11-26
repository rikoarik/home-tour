#!/usr/bin/env python3
"""
Renders photorealistic architectural presentation images directly from `house.blend`
using Cycles Metal GPU + OpenImageDenoise + AgX color management:
  - Exterior Hero (Afternoon Daylight)
  - Exterior Rear Terrace & Garden (Golden Sunset)
  - Interior Living/Dining/Kitchen (Warm Luxury, Scandinavian, Modern styles)
  - Interior Master Suite (Warm Luxury)
  - Orthographic 3D Dollhouse Cutaway (Roof & Ceilings hidden)
"""

import json
import math
from pathlib import Path
import bpy

OUT_DIR = Path("/Users/macbookm2/.gemini/antigravity/scratch/luxury-residence-floorplan/blender")
RENDER_DIR = OUT_DIR / "renders"
RENDER_DIR.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=str(OUT_DIR / "house.blend"))
scene = bpy.context.scene
cfg = json.loads((OUT_DIR / "scene-config.json").read_text(encoding="utf-8"))

# Ensure Cycles Metal GPU + denoiser
scene.render.engine = "CYCLES"
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for d in prefs.devices:
        if d.type == "METAL":
            d.use = True
    scene.cycles.device = "GPU"
except Exception:
    scene.cycles.device = "CPU"

scene.cycles.use_denoising = True
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.025
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"

# Store original light energies so presets scale cleanly
orig_energies = {}
for obj in bpy.data.collections["Lighting"].objects:
    if obj.type == "LIGHT":
        orig_energies[obj.name] = obj.data.energy


def apply_lighting(preset_name):
    p = cfg["lighting_presets"][preset_name]
    wnt = scene.world.node_tree
    sky = next(n for n in wnt.nodes if n.type == "TEX_SKY")
    bg = next(n for n in wnt.nodes if n.type == "BACKGROUND")
    sky.sun_elevation = math.radians(max(p["sun_elevation_deg"], 1.5))
    sky.sun_rotation = math.radians(p["sun_azimuth_deg"])
    bg.inputs["Strength"].default_value = p["sky_intensity"]
    scene.view_settings.exposure = p["exposure"]

    for obj in bpy.data.collections["Lighting"].objects:
        if obj.type == "LIGHT":
            base = orig_energies[obj.name]
            mult = p["outdoor_lights_multiplier"] if "Outdoor" in obj.name else p["interior_lights_multiplier"]
            obj.data.energy = base * mult


def set_style(style_key):
    col_map = {
        "Modern": "Furniture_Modern",
        "Scandinavian": "Furniture_Scandinavian",
        "WarmLuxury": "Furniture_WarmLuxury",
    }
    for k, cname in col_map.items():
        show = (k == style_key)
        c = bpy.data.collections[cname]
        c.hide_render = not show
        c.hide_viewport = not show
        for obj in c.objects:
            obj.hide_render = not show
            obj.hide_viewport = not show

    # Swap main living/dining/kitchen floor finish per interior style for unmistakable visual distinction!
    floor_mat_name = {
        "Modern": "Mat_Floor_ModernStone",
        "Scandinavian": "Mat_Floor_WhiteOak",
        "WarmLuxury": "Mat_Floor_Limestone",
    }[style_key]
    fmat = bpy.data.materials.get(floor_mat_name)
    if fmat:
        for obj in bpy.data.collections["Floors"].objects:
            if any(tag in obj.name for tag in ("RM-07", "RM-08", "RM-09", "RM-10", "RM-11")):
                if obj.data.materials:
                    obj.data.materials[0] = fmat


def set_dollhouse_cutaway(enabled):
    for cname in ("Roof", "Ceilings"):
        c = bpy.data.collections[cname]
        c.hide_render = enabled
        c.hide_viewport = enabled
        for obj in c.objects:
            obj.hide_render = enabled
            obj.hide_viewport = enabled
    # Also hide exterior neighbor backdrop & street during clean dollhouse cutaway
    for obj in bpy.data.collections["Landscape"].objects:
        if obj.name.startswith("Context_"):
            obj.hide_render = enabled


def render_shot(filename, cam_name, style, lighting, width=1600, height=1000, samples=72, dollhouse=False, open_rear_door=False):
    set_style(style)
    apply_lighting(lighting)
    set_dollhouse_cutaway(dollhouse)

    # Optionally slide open D8 rear terrace door panels for seamless indoor-outdoor shot!
    d8_p1 = bpy.data.objects.get("Door_Interactive_D8_Panel1")
    d8_p2 = bpy.data.objects.get("Door_Interactive_D8_Panel2")
    orig_x1 = d8_p1.location.x if d8_p1 else None
    orig_x2 = d8_p2.location.x if d8_p2 else None
    if open_rear_door and d8_p1 and d8_p2:
        d8_p1.location.x = orig_x1 + 1.55
        d8_p2.location.x = orig_x2 + 0.80

    scene.camera = bpy.data.objects[cam_name]
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.cycles.samples = samples
    out_path = RENDER_DIR / filename
    scene.render.filepath = str(out_path)
    print(f"Rendering {filename} ({width}x{height}, {samples} spp, style={style}, light={lighting})...")
    bpy.ops.render.render(write_still=True)

    # Restore door position
    if open_rear_door and d8_p1 and d8_p2:
        d8_p1.location.x = orig_x1
        d8_p2.location.x = orig_x2


# Render all required views (crisp 1440x900 & 1440x1080 Cycles Metal GPU + OIDN)
render_shot("render_exterior_afternoon.png", "Cam_Exterior_Hero", "WarmLuxury", "afternoon", width=1440, height=900, samples=40)
render_shot("render_exterior_sunset.png", "Cam_Exterior_Rear", "WarmLuxury", "sunset", width=1440, height=900, samples=40, open_rear_door=True)
render_shot("render_interior_living_warm_luxury.png", "Cam_Interior_Living", "WarmLuxury", "morning", width=1440, height=900, samples=44, open_rear_door=True)
render_shot("render_interior_living_scandinavian.png", "Cam_Interior_Living", "Scandinavian", "morning", width=1440, height=900, samples=40, open_rear_door=True)
render_shot("render_interior_living_modern.png", "Cam_Interior_Living", "Modern", "morning", width=1440, height=900, samples=40, open_rear_door=True)
render_shot("render_interior_master_suite.png", "Cam_Interior_Master", "WarmLuxury", "morning", width=1440, height=900, samples=44)
render_shot("render_dollhouse_ortho.png", "Cam_Dollhouse_Ortho", "WarmLuxury", "afternoon", width=1440, height=1080, samples=40, dollhouse=True)

print("ALL 7 PHOTOREALISTIC RENDERS COMPLETE!")
