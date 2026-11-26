#!/usr/bin/env python3
"""
Villa Aurelia 123 — Photorealistic 3D Architectural Builder, Validator & GLB Exporter
for Blender 5.3+ (bpy).

Upgraded archviz realism edition:
  - True branching organic trees with hundreds of individual botanical leaf blades
  - Tropical bamboo courtyard privacy screen, fanning frond shrubs, fiddle-leaf figs
  - Softly lofted smooth-shaded cushions, mattresses, folded duvets & throw pillows
  - Sinusoidal S-fold pleated floor-to-ceiling sheer drapery
  - Curved-back upholstered dining chairs, fluted drum coffee table, kitchen door reveals
  - Bookmatched wood veneers on furniture (no floor plank lines) + fBm geological stones
  - Sculpted modern luxury car with alloy wheels & LED lightbar
  - Architectural exterior sconces, timber courtyard slats, carport drain grate
  - Strict 1:1 fidelity to `floorplan-spec.json` (123.44 m², 9.144 x 13.500 m)
"""

import json
import math
import random
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector, Euler, Matrix

BASE_DIR = Path("/Users/macbookm2/.gemini/antigravity/scratch/luxury-residence-floorplan")
SPEC_PATH = BASE_DIR / "floorplan-spec.json"
OUT_DIR = BASE_DIR / "blender"
TEX_DIR = OUT_DIR / "textures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))

M = 0.001
SITE_W = spec["site"]["width_mm"] * M      # 9.144 m
SITE_D = spec["site"]["depth_mm"] * M      # 13.500 m
FLOOR_Z = 0.15                             # 150 mm plinth finished floor
CEIL_H = spec["meta"]["ceiling_height_mm"] * M  # 3.000 m
WET_CEIL_H = 2.80
WALL_TOP_Z = FLOOR_Z + CEIL_H              # 3.150 m
FLOOR2_Z = WALL_TOP_Z + 0.20               # 3.350 m (200 mm inter-floor reinforced concrete slab)
CEIL2_H = 2.85                             # 2.850 m L2 clear height
WALL2_TOP_Z = FLOOR2_Z + CEIL2_H           # 6.200 m
ROOF_SLAB_TOP_Z = FLOOR2_Z                 # L1 roof plate = L2 subfloor datum (3.350 m)
ROOF2_SLAB_TOP_Z = WALL2_TOP_Z + 0.28      # 6.480 m
PARAPET_TOP_Z = ROOF2_SLAB_TOP_Z + 0.28    # 6.760 m

# ---------------------------------------------------------------------------
# 1. CLEAN SCENE & CYCLES METAL GPU SETUP
# ---------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 1.0
scene.unit_settings.length_unit = "METERS"

scene.render.engine = "CYCLES"
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for dev in prefs.devices:
        if dev.type == "METAL":
            dev.use = True
    scene.cycles.device = "GPU"
except Exception as exc:
    print("Metal GPU fallback warning:", exc)
    scene.cycles.device = "CPU"

scene.cycles.use_denoising = True
scene.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
scene.cycles.max_bounces = 8
scene.cycles.diffuse_bounces = 4
scene.cycles.glossy_bounces = 4
scene.cycles.transmission_bounces = 6
scene.cycles.transparent_max_bounces = 8
scene.view_settings.view_transform = "AgX"
try:
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass
scene.view_settings.exposure = 0.0

# ---------------------------------------------------------------------------
# 2. 15 REQUIRED BLENDER COLLECTIONS
# ---------------------------------------------------------------------------
COLLECTION_NAMES = [
    "Architecture",
    "Walls",
    "Floors",
    "Ceilings",
    "Roof",
    "Doors",
    "Windows",
    "Furniture_Modern",
    "Furniture_Scandinavian",
    "Furniture_WarmLuxury",
    "Lighting",
    "Landscape",
    "Cameras",
    "Collision_Meshes",
    "Tour_Waypoints",
]

cols = {}
for cname in COLLECTION_NAMES:
    c = bpy.data.collections.new(cname)
    scene.collection.children.link(c)
    cols[cname] = c

# ---------------------------------------------------------------------------
# 3. PHOTOREALISTIC PBR MATERIAL LIBRARY (glTF 2.0 COMPATIBLE)
# ---------------------------------------------------------------------------
_img_cache = {}


def load_img(filename, colorspace="sRGB"):
    key = (filename, colorspace)
    if key not in _img_cache:
        path = TEX_DIR / filename
        img = bpy.data.images.load(str(path), check_existing=True)
        img.colorspace_settings.name = colorspace
        img.pack()
        _img_cache[key] = img
    return _img_cache[key]


def make_pbr_mat(
    name,
    tex_prefix=None,
    base_color=(0.8, 0.8, 0.8, 1.0),
    roughness=0.65,
    metallic=0.0,
    uv_scale=(1.0, 1.0),
    normal_strength=0.45,
    transmission=0.0,
    alpha=1.0,
    emission=None,
    emission_strength=0.0,
    coat=0.0,
    coat_roughness=0.35,
    sheen=0.0,
    albedo_file=None,
    double_sided=False,
):
    mat = bpy.data.materials.new(name=name)
    mat.use_backface_culling = not double_sided
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (620, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (250, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    bsdf.inputs["Base Color"].default_value = base_color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.38
    if "Transmission Weight" in bsdf.inputs and transmission > 0:
        bsdf.inputs["Transmission Weight"].default_value = transmission
    if "IOR" in bsdf.inputs:
        bsdf.inputs["IOR"].default_value = 1.48
    if "Alpha" in bsdf.inputs and alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
    if "Coat Weight" in bsdf.inputs and coat > 0:
        bsdf.inputs["Coat Weight"].default_value = coat
    if "Coat Roughness" in bsdf.inputs:
        bsdf.inputs["Coat Roughness"].default_value = coat_roughness
    if "Sheen Weight" in bsdf.inputs and sheen > 0:
        bsdf.inputs["Sheen Weight"].default_value = sheen
    if "Sheen Roughness" in bsdf.inputs:
        bsdf.inputs["Sheen Roughness"].default_value = 0.75
    if emission is not None and "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = emission
        bsdf.inputs["Emission Strength"].default_value = emission_strength

    if tex_prefix or albedo_file:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        tc.location = (-750, 0)
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.location = (-550, 0)
        mp.inputs["Scale"].default_value = (uv_scale[0], uv_scale[1], 1.0)
        nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])

        alb_name = albedo_file if albedo_file else f"{tex_prefix}_albedo.png"
        if (TEX_DIR / alb_name).exists():
            t_alb = nt.nodes.new("ShaderNodeTexImage")
            t_alb.location = (-250, 260)
            t_alb.image = load_img(alb_name, "sRGB")
            nt.links.new(mp.outputs["Vector"], t_alb.inputs["Vector"])
            nt.links.new(t_alb.outputs["Color"], bsdf.inputs["Base Color"])

        if tex_prefix and (TEX_DIR / f"{tex_prefix}_roughness.png").exists():
            t_rgh = nt.nodes.new("ShaderNodeTexImage")
            t_rgh.location = (-250, -20)
            t_rgh.image = load_img(f"{tex_prefix}_roughness.png", "Non-Color")
            nt.links.new(mp.outputs["Vector"], t_rgh.inputs["Vector"])
            nt.links.new(t_rgh.outputs["Color"], bsdf.inputs["Roughness"])

        if tex_prefix and (TEX_DIR / f"{tex_prefix}_normal.png").exists():
            t_nrm = nt.nodes.new("ShaderNodeTexImage")
            t_nrm.location = (-250, -320)
            t_nrm.image = load_img(f"{tex_prefix}_normal.png", "Non-Color")
            nt.links.new(mp.outputs["Vector"], t_nrm.inputs["Vector"])
            nm = nt.nodes.new("ShaderNodeNormalMap")
            nm.location = (20, -320)
            nm.inputs["Strength"].default_value = normal_strength
            nt.links.new(t_nrm.outputs["Color"], nm.inputs["Color"])
            nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])

    return mat


mats = {
    # Architectural Surfaces (Smooth Luxury Venetian Limewash Plaster & Clean Exterior Render)
    "ext_stucco": make_pbr_mat("Mat_Exterior_Stucco", "stucco_exterior", roughness=0.92, uv_scale=(0.45, 0.45), normal_strength=0.18),
    "int_wall_warm": make_pbr_mat("Mat_Interior_Wall_Warm", "stucco_warm_white", roughness=0.91, uv_scale=(0.45, 0.45), normal_strength=0.10),
    "int_wall_white": make_pbr_mat("Mat_Interior_Wall_White", "stucco_pure_white", roughness=0.90, uv_scale=(0.45, 0.45), normal_strength=0.09),
    "ceiling_white": make_pbr_mat("Mat_Ceiling_MatteWhite", base_color=(0.95, 0.94, 0.92, 1.0), roughness=0.94),
    "plinth_concrete": make_pbr_mat("Mat_Plinth_Concrete", "basalt_paver", roughness=0.84, uv_scale=(0.55, 0.55), normal_strength=0.42),
    "roof_membrane": make_pbr_mat("Mat_Roof_Membrane", base_color=(0.22, 0.23, 0.25, 1.0), roughness=0.90),
    "roof_coping": make_pbr_mat("Mat_Roof_Coping_Metal", base_color=(0.10, 0.105, 0.115, 1.0), roughness=0.48, metallic=0.80),
    "skirting": make_pbr_mat("Mat_Skirting_WarmWhite", base_color=(0.90, 0.88, 0.85, 1.0), roughness=0.68),

    # Flooring (Natural Satin Oiled Timber & Honed Geological Stones with grazing sheen)
    "floor_oak": make_pbr_mat("Mat_Floor_WhiteOak", "white_oak", roughness=0.50, uv_scale=(0.65, 0.65), normal_strength=0.42),
    "floor_limestone": make_pbr_mat("Mat_Floor_Limestone", "limestone_tile", roughness=0.54, uv_scale=(0.55, 0.55), normal_strength=0.38),
    "floor_travertine": make_pbr_mat("Mat_Floor_Travertine", "travertine_tile", roughness=0.58, uv_scale=(0.60, 0.60), normal_strength=0.40),
    "floor_porcelain": make_pbr_mat("Mat_Floor_PorcelainGrey", "porcelain_grey", roughness=0.60, uv_scale=(0.65, 0.65), normal_strength=0.38),
    "floor_modern_stone": make_pbr_mat("Mat_Floor_ModernStone", "modern_stone", roughness=0.52, uv_scale=(0.55, 0.55), normal_strength=0.38),
    "floor_basalt": make_pbr_mat("Mat_Floor_BasaltPaver", "basalt_paver", roughness=0.76, uv_scale=(0.65, 0.65), normal_strength=0.55),
    "floor_teak": make_pbr_mat("Mat_Floor_TeakDeck", "teak_deck", roughness=0.60, uv_scale=(0.90, 0.90), normal_strength=0.48),
    "lawn": make_pbr_mat("Mat_Landscape_Lawn", "tropical_lawn", roughness=0.92, uv_scale=(0.55, 0.55), normal_strength=0.65),
    "pebbles": make_pbr_mat("Mat_Landscape_Pebbles", "basalt_paver", base_color=(0.58, 0.56, 0.52, 1.0), roughness=0.88, uv_scale=(1.8, 1.8), normal_strength=0.70),
    "stepping_stone": make_pbr_mat("Mat_Stepping_Stone", "limestone_tile", roughness=0.72, uv_scale=(0.8, 0.8), normal_strength=0.35),
    "soil": make_pbr_mat("Mat_Plant_Soil", base_color=(0.14, 0.10, 0.07, 1.0), roughness=0.96),

    # Bookmatched Satin Furniture Woods & Honed Stones
    "walnut": make_pbr_mat("Mat_Wood_Walnut", "walnut_wood", roughness=0.48, uv_scale=(0.65, 0.65), normal_strength=0.36),
    "fluted_walnut": make_pbr_mat("Mat_Wood_FlutedWalnut", "fluted_walnut", roughness=0.56, uv_scale=(1.1, 1.0), normal_strength=0.78),
    "light_oak": make_pbr_mat("Mat_Wood_LightOak", "light_oak_veneer", roughness=0.52, uv_scale=(0.65, 0.65), normal_strength=0.34),
    "fluted_oak": make_pbr_mat("Mat_Wood_FlutedOak", "fluted_oak", roughness=0.58, uv_scale=(1.1, 1.0), normal_strength=0.74),
    "marble": make_pbr_mat("Mat_Stone_CalacattaMarble", "calacatta_marble", roughness=0.38, uv_scale=(0.55, 0.55), normal_strength=0.22),
    "travertine": make_pbr_mat("Mat_Stone_Travertine", "travertine_tile", roughness=0.58, uv_scale=(0.75, 0.75), normal_strength=0.36),
    "charcoal_quartz": make_pbr_mat("Mat_Stone_CharcoalQuartz", "charcoal_quartz", roughness=0.44, uv_scale=(0.75, 0.75), normal_strength=0.20),
    "white_lacquer": make_pbr_mat("Mat_Cabinet_WhiteLacquer", base_color=(0.91, 0.90, 0.87, 1.0), roughness=0.44),
    "matte_charcoal": make_pbr_mat("Mat_Cabinet_MatteCharcoal", base_color=(0.14, 0.15, 0.17, 1.0), roughness=0.56),

    # Metals & Glass (Powder-Coated Matte Black & Satin Brushed Brass/Steel)
    "black_metal": make_pbr_mat("Mat_Metal_MatteBlack", base_color=(0.08, 0.085, 0.095, 1.0), roughness=0.46, metallic=0.80),
    "brushed_brass": make_pbr_mat("Mat_Metal_BrushedBrass", base_color=(0.78, 0.60, 0.31, 1.0), roughness=0.30, metallic=0.90),
    "brushed_steel": make_pbr_mat("Mat_Metal_BrushedSteel", base_color=(0.74, 0.76, 0.78, 1.0), roughness=0.28, metallic=0.92),
    "ceramic_white": make_pbr_mat("Mat_Sanitary_CeramicWhite", base_color=(0.94, 0.93, 0.91, 1.0), roughness=0.26),
    "mirror": make_pbr_mat("Mat_Mirror", base_color=(0.92, 0.94, 0.95, 1.0), roughness=0.03, metallic=0.98),
    "glass_clear": make_pbr_mat("Mat_Glass_Architectural", base_color=(0.86, 0.93, 0.95, 1.0), roughness=0.04, transmission=0.88, alpha=0.22),
    "glass_frosted": make_pbr_mat("Mat_Glass_Frosted", base_color=(0.88, 0.91, 0.92, 1.0), roughness=0.40, transmission=0.65, alpha=0.55),
    "tv_screen": make_pbr_mat("Mat_OLED_Screen", base_color=(0.025, 0.028, 0.034, 1.0), roughness=0.20),

    # Tactile Matte Fabrics, Drapery, Laundry Garments & Woven Rattan
    "boucle_beige": make_pbr_mat("Mat_Fabric_BoucleBeige", "boucle_beige", roughness=0.93, uv_scale=(2.4, 2.4), normal_strength=0.52, sheen=0.35),
    "linen_oatmeal": make_pbr_mat("Mat_Fabric_LinenOatmeal", "linen_oatmeal", roughness=0.94, uv_scale=(2.4, 2.4), normal_strength=0.45, sheen=0.32),
    "fabric_charcoal": make_pbr_mat("Mat_Fabric_Charcoal", "fabric_charcoal", roughness=0.92, uv_scale=(2.2, 2.2), normal_strength=0.48, sheen=0.30),
    "linen_sage": make_pbr_mat("Mat_Fabric_LinenSage", "linen_sage", roughness=0.93, uv_scale=(2.2, 2.2), normal_strength=0.45, sheen=0.32),
    "linen_white": make_pbr_mat("Mat_Fabric_LinenWhite", "linen_white_crisp", roughness=0.90, uv_scale=(2.6, 2.6), normal_strength=0.42, sheen=0.30, double_sided=True),
    "cotton_navy": make_pbr_mat("Mat_Fabric_CottonNavy", "cotton_navy_denim", roughness=0.92, uv_scale=(2.4, 2.4), normal_strength=0.46, sheen=0.28, double_sided=True),
    "rattan": make_pbr_mat("Mat_Woven_Rattan", "rattan_weave", roughness=0.82, uv_scale=(2.8, 2.8), normal_strength=0.65),
    "rug_ivory": make_pbr_mat("Mat_Rug_IvoryWool", "rug_ivory", roughness=0.96, uv_scale=(2.0, 2.0), normal_strength=0.68, sheen=0.40),
    "curtain_sheer": make_pbr_mat("Mat_Curtain_Sheer", "linen_oatmeal", base_color=(0.94, 0.92, 0.88, 1.0), roughness=0.92, alpha=0.78, sheen=0.30, double_sided=True),
    "fabric_terracotta": make_pbr_mat("Mat_Fabric_Terracotta", "fabric_terracotta", roughness=0.92, uv_scale=(2.2, 2.2), normal_strength=0.48, sheen=0.35),
    "leather_cognac": make_pbr_mat("Mat_Leather_Cognac", base_color=(0.42, 0.23, 0.12, 1.0), roughness=0.48),

    # Curated Hardcover Book Spines
    "book_navy": make_pbr_mat("Mat_Book_Navy", base_color=(0.11, 0.16, 0.25, 1.0), roughness=0.82),
    "book_olive": make_pbr_mat("Mat_Book_Olive", base_color=(0.22, 0.27, 0.19, 1.0), roughness=0.84),
    "book_ochre": make_pbr_mat("Mat_Book_Ochre", base_color=(0.64, 0.44, 0.22, 1.0), roughness=0.82),
    "book_slate": make_pbr_mat("Mat_Book_Slate", base_color=(0.28, 0.31, 0.35, 1.0), roughness=0.84),
    "book_burgundy": make_pbr_mat("Mat_Book_Burgundy", base_color=(0.38, 0.14, 0.14, 1.0), roughness=0.82),

    # Botanical Foliage (3 natural tones + maple + bamboo)
    "foliage_dark": make_pbr_mat("Mat_Plant_FoliageDark", base_color=(0.11, 0.20, 0.09, 1.0), roughness=0.68, double_sided=True),
    "foliage_mid": make_pbr_mat("Mat_Plant_FoliageMid", base_color=(0.18, 0.30, 0.13, 1.0), roughness=0.65, double_sided=True),
    "foliage_sun": make_pbr_mat("Mat_Plant_FoliageSun", base_color=(0.26, 0.39, 0.17, 1.0), roughness=0.64, double_sided=True),
    "foliage_maple": make_pbr_mat("Mat_Plant_Maple", base_color=(0.36, 0.20, 0.12, 1.0), roughness=0.66, double_sided=True),
    "bamboo_culm": make_pbr_mat("Mat_Plant_Bamboo", base_color=(0.38, 0.44, 0.23, 1.0), roughness=0.58),
    "bark": make_pbr_mat("Mat_Plant_Bark", base_color=(0.22, 0.16, 0.11, 1.0), roughness=0.92),
    "planter_ceramic": make_pbr_mat("Mat_Planter_Ceramic", base_color=(0.74, 0.69, 0.62, 1.0), roughness=0.72),
    "planter_terracotta": make_pbr_mat("Mat_Planter_Terracotta", base_color=(0.54, 0.32, 0.21, 1.0), roughness=0.78),

    # Luxury Vehicle & Context (Metallic Titanium Silver Showroom Clearcoat)
    "car_paint": make_pbr_mat("Mat_Car_SilverMetallic", base_color=(0.56, 0.60, 0.65, 1.0), roughness=0.18, metallic=0.88, coat=0.92, coat_roughness=0.06),
    "car_glass": make_pbr_mat("Mat_Car_TintedGlass", base_color=(0.06, 0.09, 0.12, 1.0), roughness=0.06, transmission=0.68, alpha=0.54),
    "car_tire": make_pbr_mat("Mat_Car_RubberTire", base_color=(0.045, 0.047, 0.052, 1.0), roughness=0.88),
    "car_caliper": make_pbr_mat("Mat_Car_BrakeCaliper", base_color=(0.72, 0.11, 0.08, 1.0), roughness=0.34, metallic=0.55),
    "car_carbon": make_pbr_mat("Mat_Car_CarbonTrim", base_color=(0.06, 0.065, 0.07, 1.0), roughness=0.44, metallic=0.35),
    "street_asphalt": make_pbr_mat("Mat_Context_Asphalt", "basalt_paver", base_color=(0.16, 0.17, 0.18, 1.0), roughness=0.90, uv_scale=(0.35, 0.35), normal_strength=0.55),
    "sidewalk": make_pbr_mat("Mat_Context_Sidewalk", "limestone_tile", base_color=(0.62, 0.60, 0.57, 1.0), roughness=0.86, uv_scale=(0.45, 0.45), normal_strength=0.38),

    # Emissive Lighting & Art
    "emit_warm": make_pbr_mat("Mat_Light_Warm3000K", base_color=(1.0, 0.91, 0.76, 1.0), roughness=0.35, emission=(1.0, 0.84, 0.60, 1.0), emission_strength=8.5),
    "emit_lamp": make_pbr_mat("Mat_Light_ShadeGlow", base_color=(0.96, 0.91, 0.82, 1.0), roughness=0.72, emission=(1.0, 0.85, 0.62, 1.0), emission_strength=4.2),
    "emit_headlight": make_pbr_mat("Mat_Light_CarHeadlight", base_color=(0.96, 0.98, 1.0, 1.0), roughness=0.15, emission=(0.90, 0.96, 1.0, 1.0), emission_strength=11.0),
    "emit_taillight": make_pbr_mat("Mat_Light_CarTaillight", base_color=(0.92, 0.08, 0.06, 1.0), roughness=0.20, emission=(1.0, 0.07, 0.05, 1.0), emission_strength=9.5),
    "emit_ev_green": make_pbr_mat("Mat_Light_EVStatus", base_color=(0.15, 0.92, 0.62, 1.0), roughness=0.35, emission=(0.12, 0.88, 0.58, 1.0), emission_strength=6.0),
    "art_warm": make_pbr_mat("Mat_Art_WarmLuxury", albedo_file="art_warm_luxury.png", roughness=0.84),
    "art_scandi": make_pbr_mat("Mat_Art_Scandinavian", albedo_file="art_scandinavian.png", roughness=0.86),
    "art_modern": make_pbr_mat("Mat_Art_Modern", albedo_file="art_modern.png", roughness=0.82),
    "ide_screen": make_pbr_mat("Mat_Screen_CodeIDE", albedo_file="code_ide_screen.png", roughness=0.42, emission=(0.14, 0.24, 0.36, 1.0), emission_strength=0.60, double_sided=True),
}

# ---------------------------------------------------------------------------
# 4. ADVANCED ORGANIC & ARCHITECTURAL GEOMETRY HELPERS
# ---------------------------------------------------------------------------
def apply_box_uv(bm, scale=1.0, align_long_grain=False):
    uv_layer = bm.loops.layers.uv.verify()
    for face in bm.faces:
        n = face.normal
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        for loop in face.loops:
            co = loop.vert.co
            if az >= ax and az >= ay:
                # When align_long_grain=True on horizontal tabletops/shelves, run wood fibers along X
                u, v = (co.y * scale, co.x * scale) if align_long_grain else (co.x * scale, co.y * scale)
            elif ax >= ay and ax >= az:
                u, v = co.y * scale, co.z * scale
            else:
                u, v = co.x * scale, co.z * scale
            loop[uv_layer].uv = (u, v)


def link_obj(obj, col_name):
    cols[col_name].objects.link(obj)
    return obj


def make_box(name, x0, y0, z0, x1, y1, z1, col_name, mat=None, uv_scale=1.0, bevel=0.0, smooth=False, origin_mode="center"):
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    if dx <= 1e-5 or dy <= 1e-5 or dz <= 1e-5:
        return None
    if origin_mode == "center":
        ox, oy, oz = (x0 + x1) * 0.5, (y0 + y1) * 0.5, (z0 + z1) * 0.5
    elif origin_mode == "bottom_center":
        ox, oy, oz = (x0 + x1) * 0.5, (y0 + y1) * 0.5, z0
    elif origin_mode == "world":
        ox, oy, oz = 0.0, 0.0, 0.0
    else:
        ox, oy, oz = origin_mode

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        wx = x0 if v.co.x < 0 else x1
        wy = y0 if v.co.y < 0 else y1
        wz = z0 if v.co.z < 0 else z1
        v.co = Vector((wx - ox, wy - oy, wz - oz))
    if bevel > 0.0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, min(dx, dy, dz) * 0.30), segments=1, affect="EDGES")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if smooth:
        split_sharp_edges(bm, 42.0)
    is_wood_horiz = (mat in (mats.get("walnut"), mats.get("light_oak"))) and (dx > dy * 1.25)
    apply_box_uv(bm, scale=uv_scale, align_long_grain=is_wood_horiz)

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    if smooth:
        for poly in mesh.polygons:
            poly.use_smooth = True
    if mat is not None:
        mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (ox, oy, oz)
    return link_obj(obj, col_name)


def make_plush_cushion(name, x0, y0, z0, x1, y1, z1, col_name, mat, puff=0.18, rot_z=0.0):
    """Creates a realistic softly lofted, smooth-shaded fabric cushion/mattress/pillow (zero Lego edges!)."""
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    ox, oy, oz = (x0 + x1) * 0.5, (y0 + y1) * 0.5, (z0 + z1) * 0.5
    bm = bmesh.new()
    # 3x3x3 subdivided grid deformed into a gently puffed smooth-shaded cushion (4x lighter than cuts=3, identical silhouette!)
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=2, use_grid_fill=True)
    for v in bm.verts:
        u = v.co.x * 2.0  # -1..1
        w = v.co.y * 2.0
        h = v.co.z * 2.0
        # Soft pillow superellipsoid rounding + gentle center loft
        r2 = min(1.0, (u * u + w * w) * 0.45)
        edge_taper = 1.0 - 0.24 * (u * u * w * w)
        loft = 1.0 + puff * (1.0 - r2)
        v.co = Vector((
            u * 0.5 * dx * (0.94 + 0.06 * math.cos(h * math.pi * 0.5)),
            w * 0.5 * dy * (0.94 + 0.06 * math.cos(h * math.pi * 0.5)),
            h * 0.5 * dz * loft * edge_taper,
        ))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    apply_box_uv(bm, scale=1.5)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (ox, oy, oz)
    if rot_z:
        obj.rotation_euler = (0.0, 0.0, rot_z)
    return link_obj(obj, col_name)


def make_pleated_curtain(name, x0, x1, y_center, z0, z1, col_name, mat, waves=6):
    """Creates realistic sinusoidal S-fold floor-to-ceiling sheer architectural drapery."""
    bm = bmesh.new()
    cols_n = waves * 6
    rows_n = 4
    verts = []
    amp = 0.048
    for r in range(rows_n + 1):
        row = []
        tz = r / rows_n
        z = z0 + (z1 - z0) * tz
        # Slight relaxed billow toward bottom hem
        billow = 1.0 + 0.16 * (1.0 - tz)
        for c in range(cols_n + 1):
            tx = c / cols_n
            x = x0 + (x1 - x0) * tx
            y = y_center + math.sin(tx * waves * 2.0 * math.pi) * amp * billow
            row.append(bm.verts.new((x, y, z)))
        verts.append(row)
    for r in range(rows_n):
        for c in range(cols_n):
            bm.faces.new((verts[r][c], verts[r][c + 1], verts[r + 1][c + 1], verts[r + 1][c]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    apply_box_uv(bm, scale=1.2)
    ox, oy, oz = (x0 + x1) * 0.5, y_center, (z0 + z1) * 0.5
    for v in bm.verts:
        v.co -= Vector((ox, oy, oz))
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (ox, oy, oz)
    return link_obj(obj, col_name)


def make_poly_slab(name, pts_2d_m, z0, z1, col_name, mat=None, uv_scale=1.0):
    bm = bmesh.new()
    verts_bot = [bm.verts.new((x, y, z0)) for x, y in pts_2d_m]
    face_bot = bm.faces.new(verts_bot)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    res = bmesh.ops.extrude_face_region(bm, geom=[face_bot])
    ext_verts = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=ext_verts, vec=(0.0, 0.0, z1 - z0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    apply_box_uv(bm, scale=uv_scale)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    if mat is not None:
        mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    return link_obj(obj, col_name)


def split_sharp_edges(bm, angle_deg=36.0):
    """Splits edges sharper than angle_deg so smooth shading never bleeds across 90-deg corners in glTF/WebGL."""
    thresh = math.radians(angle_deg)
    bm.edges.ensure_lookup_table()
    sharp = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > thresh]
    if sharp:
        bmesh.ops.split_edges(bm, edges=sharp)


def make_cylinder(name, cx, cy, z0, radius, height, col_name, mat=None, segs=14, radius_top=None):
    segs = min(segs, 16)
    r2 = radius if radius_top is None else radius_top
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs, radius1=radius, radius2=r2, depth=height)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, height * 0.5))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    split_sharp_edges(bm, 38.0)
    apply_box_uv(bm, scale=1.0)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    if mat is not None:
        mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (cx, cy, z0)
    return link_obj(obj, col_name)


def make_swept_tube(name, points, radius, col_name, mat, segs=8, radius_end=None, cap=True):
    """Sweeps a silky-smooth circular tube along a 3D list of curve points (for gooseneck faucets, arched lamps, mug handles, curved chair spokes)."""
    segs = min(segs, 10)
    pts = [Vector(p) for p in points]
    if len(pts) < 2:
        return None
    r_end = radius if radius_end is None else radius_end
    bm = bmesh.new()
    rings = []
    prev_n = None
    for idx, p in enumerate(pts):
        if idx == 0:
            tan = (pts[1] - pts[0]).normalized()
        elif idx == len(pts) - 1:
            tan = (pts[-1] - pts[-2]).normalized()
        else:
            tan = (pts[idx + 1] - pts[idx - 1]).normalized()
        if tan.length < 1e-6:
            tan = Vector((0, 0, 1))
        if prev_n is None:
            ref = Vector((1, 0, 0)) if abs(tan.x) < 0.85 else Vector((0, 1, 0))
            n_vec = (ref - tan * ref.dot(tan)).normalized()
        else:
            # Parallel transport to prevent twist along 3D curves
            n_vec = (prev_n - tan * prev_n.dot(tan))
            if n_vec.length < 1e-5:
                ref = Vector((1, 0, 0)) if abs(tan.x) < 0.85 else Vector((0, 1, 0))
                n_vec = (ref - tan * ref.dot(tan)).normalized()
            else:
                n_vec.normalize()
        prev_n = n_vec
        b_vec = tan.cross(n_vec).normalized()
        t_frac = idx / max(1, len(pts) - 1)
        r_cur = radius * (1.0 - t_frac) + r_end * t_frac
        ring = []
        for k in range(segs):
            ang = 2.0 * math.pi * k / segs
            v_pos = p + (n_vec * math.cos(ang) + b_vec * math.sin(ang)) * r_cur
            ring.append(bm.verts.new(v_pos))
        rings.append(ring)

    for i in range(len(rings) - 1):
        r0, r1 = rings[i], rings[i + 1]
        for k in range(segs):
            kn = (k + 1) % segs
            bm.faces.new((r0[k], r0[kn], r1[kn], r1[k]))
    if cap:
        bm.faces.new(rings[0][::-1])
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    split_sharp_edges(bm, 42.0)
    apply_box_uv(bm, scale=2.0)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    mesh.materials.append(mat)
    return link_obj(bpy.data.objects.new(name, mesh), col_name)


def make_lathed_mesh(name, cx, cy, z0, profile_rz, col_name, mat, segs=14):
    """Revolves a list of (radius, z_offset) profile points 360° into an organic curved ceramic vessel, wine glass, mug, or vase."""
    segs = min(segs, 16)
    bm = bmesh.new()
    rings = []
    for r, zh in profile_rz:
        r_safe = max(0.001, r)
        ring = [bm.verts.new((r_safe * math.cos(2.0 * math.pi * k / segs), r_safe * math.sin(2.0 * math.pi * k / segs), zh)) for k in range(segs)]
        rings.append(ring)
    for i in range(len(rings) - 1):
        r0, r1 = rings[i], rings[i + 1]
        for k in range(segs):
            kn = (k + 1) % segs
            bm.faces.new((r0[k], r0[kn], r1[kn], r1[k]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    split_sharp_edges(bm, 44.0)
    apply_box_uv(bm, scale=2.0)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (cx, cy, z0)
    return link_obj(obj, col_name)


def make_rounded_slab(name, x0, y0, z0, x1, y1, z1, corner_r, col_name, mat, segs=5, uv_scale=1.0):
    """Creates a sculpted luxury rounded-corner tabletop/slab with smooth bullnose arc corners and crisp normals."""
    segs = min(segs, 5)
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    r = min(corner_r, dx * 0.45, dy * 0.45)
    ox, oy, oz = (x0 + x1) * 0.5, (y0 + y1) * 0.5, (z0 + z1) * 0.5
    corners = [
        (x1 - r, y1 - r, 0.0, math.pi * 0.5),
        (x0 + r, y1 - r, math.pi * 0.5, math.pi),
        (x0 + r, y0 + r, math.pi, math.pi * 1.5),
        (x1 - r, y0 + r, math.pi * 1.5, math.pi * 2.0),
    ]
    pts_2d = []
    for ccx, ccy, a0, a1 in corners:
        for k in range(segs + 1):
            a = a0 + (a1 - a0) * (k / segs)
            pts_2d.append((ccx + r * math.cos(a) - ox, ccy + r * math.sin(a) - oy))

    bm = bmesh.new()
    v_bot = [bm.verts.new((px, py, z0 - oz)) for px, py in pts_2d]
    f_bot = bm.faces.new(v_bot)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    res = bmesh.ops.extrude_face_region(bm, geom=[f_bot])
    ext_v = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=ext_v, vec=(0.0, 0.0, dz))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # Bevel ONLY horizontal top/bottom perimeter edges (never vertical corner-arc edges!) to prevent self-intersection
    if dz >= 0.016:
        horiz_edges = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-4]
        b_off = min(0.005, dz * 0.20, r * 0.22)
        if horiz_edges and b_off > 0.001:
            bmesh.ops.bevel(bm, geom=horiz_edges, offset=b_off, segments=2, affect="EDGES")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    split_sharp_edges(bm, 40.0)
    is_wood_horiz = (mat in (mats.get("walnut"), mats.get("light_oak"))) and (dx > dy * 1.25)
    apply_box_uv(bm, scale=uv_scale, align_long_grain=is_wood_horiz)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (ox, oy, oz)
    return link_obj(obj, col_name)


def make_arched_mirror(prefix, wall_x, wall_y, z0, width, height, normal_dir, col_name, frame_mat, mirror_mat, emit_mat):
    """
    Creates an architectural arched-top backlit mirror (smooth 16-segment semicircular arch, slim bezel & warm halo).
    normal_dir: '-X' (mounted on East wall facing West) or '-Y' (mounted on North wall facing South).
    """
    hw = width * 0.5
    arch_r = hw
    straight_h = max(0.10, height - arch_r)
    segs = 16

    def build_arch_panel(name, w_scale, h_inset, thick, offset_out, mat):
        bm = bmesh.new()
        r_a = arch_r * w_scale
        sh = straight_h
        # 2D profile (u across width, v along height)
        pts = [(-r_a, h_inset), (r_a, h_inset)]
        for k in range(segs + 1):
            ang = math.pi * (k / segs)
            pts.append((r_a * math.cos(ang), sh + r_a * math.sin(ang)))
        if normal_dir == "-X":
            v_back = [bm.verts.new((wall_x - offset_out, wall_y + u, z0 + v)) for u, v in pts]
            f_back = bm.faces.new(v_back)
            res = bmesh.ops.extrude_face_region(bm, geom=[f_back])
            bmesh.ops.translate(bm, verts=[g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)], vec=(-thick, 0, 0))
        else:  # '-Y'
            v_back = [bm.verts.new((wall_x + u, wall_y - offset_out, z0 + v)) for u, v in pts]
            f_back = bm.faces.new(v_back)
            res = bmesh.ops.extrude_face_region(bm, geom=[f_back])
            bmesh.ops.translate(bm, verts=[g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)], vec=(0, -thick, 0))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        split_sharp_edges(bm, 40.0)
        apply_box_uv(bm, scale=1.0)
        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        bm.free()
        for poly in mesh.polygons:
            poly.use_smooth = True
        mesh.materials.append(mat)
        return link_obj(bpy.data.objects.new(name, mesh), col_name)

    build_arch_panel(f"{prefix}Halo", 0.96, 0.02, 0.012, 0.002, emit_mat)
    build_arch_panel(f"{prefix}Frame", 1.00, 0.0, 0.018, 0.014, frame_mat)
    build_arch_panel(f"{prefix}", 0.95, 0.016, 0.006, 0.032, mirror_mat)


def make_curved_mug(prefix, cx, cy, z0, col_name, mat, handle_angle=0.4):
    """Builds a realistic hollow lathed ceramic mug with dark coffee inside and a smooth curved C-handle."""
    make_lathed_mesh(
        f"{prefix}_Body", cx, cy, z0,
        [(0.031, 0.0), (0.036, 0.008), (0.037, 0.082), (0.035, 0.088), (0.031, 0.088), (0.030, 0.014), (0.001, 0.014)],
        col_name, mat, segs=18
    )
    make_cylinder(f"{prefix}_Coffee", cx, cy, z0 + 0.068, 0.030, 0.004, col_name, mats["walnut"], segs=16)
    ca, sa = math.cos(handle_angle), math.sin(handle_angle)
    h_pts = []
    for k in range(9):
        t = k / 8.0
        ang = -math.pi * 0.48 + math.pi * 0.96 * t
        hr = 0.035 + 0.022 * math.cos(ang)
        hz = z0 + 0.048 + 0.026 * math.sin(ang)
        h_pts.append((cx + hr * ca, cy + hr * sa, hz))
    make_swept_tube(f"{prefix}_Handle", h_pts, 0.0048, col_name, mat, segs=8)


def make_realistic_tree(prefix, cx, cy, radius, height, col_name, maple=False, seed=101):
    """Builds a true branching botanical tree with curved trunk, twigs, and ~260 angled leaf blades."""
    rng = random.Random(seed)
    bm_wood = bmesh.new()
    bm_leaves = bmesh.new()

    def add_tapered_segment(bm, p0, p1, r0, r1, segs=8):
        vec = p1 - p0
        length = vec.length
        if length < 1e-4:
            return
        quat = Vector((0, 0, 1)).rotation_difference(vec.normalized())
        ring0, ring1 = [], []
        for k in range(segs):
            ang = 2.0 * math.pi * k / segs
            d = Vector((math.cos(ang), math.sin(ang), 0.0))
            ring0.append(bm.verts.new(p0 + quat @ (d * r0)))
            ring1.append(bm.verts.new(p1 + quat @ (d * r1)))
        for k in range(segs):
            kn = (k + 1) % segs
            bm.faces.new((ring0[k], ring0[kn], ring1[kn], ring1[k]))

    # Natural subtly curving 3-segment trunk
    p0 = Vector((0, 0, 0))
    p1 = Vector((rng.uniform(-0.04, 0.04), rng.uniform(-0.04, 0.04), height * 0.25))
    p2 = Vector((rng.uniform(-0.06, 0.06), rng.uniform(-0.06, 0.06), height * 0.48))
    add_tapered_segment(bm_wood, p0, p1, 0.075, 0.056, 10)
    add_tapered_segment(bm_wood, p1, p2, 0.056, 0.042, 10)

    leaf_anchors = []
    # 5 primary diverging limbs + secondary twigs
    for i in range(5):
        az = i * (2.0 * math.pi / 5.0) + rng.uniform(-0.25, 0.25)
        spread = radius * rng.uniform(0.55, 0.85)
        b_end = p2 + Vector((math.cos(az) * spread, math.sin(az) * spread, height * rng.uniform(0.24, 0.38)))
        add_tapered_segment(bm_wood, p2, b_end, 0.030, 0.014, 7)
        leaf_anchors.append(b_end)
        for sub in range(3):
            s_az = az + rng.uniform(-0.9, 0.9)
            s_len = radius * rng.uniform(0.28, 0.50)
            s_end = b_end + Vector((math.cos(s_az) * s_len, math.sin(s_az) * s_len, rng.uniform(0.10, 0.36)))
            add_tapered_segment(bm_wood, b_end, s_end, 0.013, 0.005, 5)
            leaf_anchors.append(s_end)
    # Crown central spire branch
    crown_top = p2 + Vector((0.02, -0.02, height * 0.44))
    add_tapered_segment(bm_wood, p2, crown_top, 0.024, 0.008, 6)
    leaf_anchors.append(crown_top)

    # Add 260 crisp curved diamond/lanceolate botanical leaves around branch tips (3 material slots!)
    leaf_mats = (
        [mats["foliage_maple"], mats["foliage_dark"], mats["foliage_sun"]]
        if maple
        else [mats["foliage_dark"], mats["foliage_mid"], mats["foliage_sun"]]
    )
    for anchor in leaf_anchors:
        for _ in range(13):
            center = anchor + Vector((rng.gauss(0, radius * 0.24), rng.gauss(0, radius * 0.24), rng.gauss(0.03, radius * 0.17)))
            yaw = rng.uniform(0, 2.0 * math.pi)
            pitch = rng.uniform(-0.75, 0.85)
            roll = rng.uniform(-0.6, 0.6)
            rot = Euler((pitch, roll, yaw)).to_matrix()
            L = rng.uniform(0.12, 0.21)
            W = L * rng.uniform(0.42, 0.56)
            v0 = bm_leaves.verts.new(center + rot @ Vector((0, -L * 0.45, 0)))
            v1 = bm_leaves.verts.new(center + rot @ Vector((W * 0.5, 0, 0.015)))
            v2 = bm_leaves.verts.new(center + rot @ Vector((0, L * 0.55, -0.01)))
            v3 = bm_leaves.verts.new(center + rot @ Vector((-W * 0.5, 0, 0.015)))
            f = bm_leaves.faces.new((v0, v1, v2, v3))
            f.material_index = rng.randint(0, 2)

    # Finalize wood mesh
    bmesh.ops.recalc_face_normals(bm_wood, faces=bm_wood.faces)
    apply_box_uv(bm_wood, scale=2.0)
    m_wood = bpy.data.meshes.new(f"{prefix}_Trunk")
    bm_wood.to_mesh(m_wood)
    bm_wood.free()
    for p in m_wood.polygons:
        p.use_smooth = True
    m_wood.materials.append(mats["bark"])
    o_wood = bpy.data.objects.new(f"{prefix}_Trunk", m_wood)
    o_wood.location = (cx, cy, 0.0)
    link_obj(o_wood, col_name)

    # Finalize foliage mesh
    bmesh.ops.recalc_face_normals(bm_leaves, faces=bm_leaves.faces)
    apply_box_uv(bm_leaves, scale=3.0)
    m_leaf = bpy.data.meshes.new(f"{prefix}_Foliage")
    bm_leaves.to_mesh(m_leaf)
    bm_leaves.free()
    for lm in leaf_mats:
        m_leaf.materials.append(lm)
    o_leaf = bpy.data.objects.new(f"{prefix}_Foliage", m_leaf)
    o_leaf.location = (cx, cy, 0.0)
    link_obj(o_leaf, col_name)


def make_tropical_shrub(prefix, cx, cy, radius, col_name, seed=201):
    """Builds a realistic fanning tropical agave / fern / ornamental blade cluster."""
    rng = random.Random(seed)
    bm = bmesh.new()
    for i in range(28):
        az = i * (2.0 * math.pi / 28.0) + rng.uniform(-0.15, 0.15)
        tilt = rng.uniform(0.32, 1.08)
        L = radius * rng.uniform(0.75, 1.35)
        W = L * rng.uniform(0.16, 0.24)
        rot = Euler((0, 0, az)).to_matrix()
        # 2-segment gracefully arching frond
        p0 = Vector((0, 0, 0.03))
        p_mid_l = rot @ Vector((-W * 0.5, L * 0.45 * math.sin(tilt), L * 0.55 * math.cos(tilt) + 0.08))
        p_mid_r = rot @ Vector((W * 0.5, L * 0.45 * math.sin(tilt), L * 0.55 * math.cos(tilt) + 0.08))
        p_tip = rot @ Vector((0, L * math.sin(tilt + 0.25), max(0.05, L * math.cos(tilt + 0.35))))
        v0 = bm.verts.new(p0)
        vl = bm.verts.new(p_mid_l)
        vr = bm.verts.new(p_mid_r)
        vt = bm.verts.new(p_tip)
        f = bm.faces.new((v0, vr, vt, vl))
        f.material_index = rng.randint(0, 2)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    apply_box_uv(bm, scale=2.0)
    mesh = bpy.data.meshes.new(prefix)
    bm.to_mesh(mesh)
    bm.free()
    for m in (mats["foliage_dark"], mats["foliage_mid"], mats["foliage_sun"]):
        mesh.materials.append(m)
    obj = bpy.data.objects.new(prefix, mesh)
    obj.location = (cx, cy, 0.01)
    return link_obj(obj, col_name)


def make_bamboo_screen(prefix, x0, x1, y_pos, col_name, count=14):
    """Lush resort-style tropical bamboo privacy grove along the rear garden wall."""
    rng = random.Random(303)
    bm_culms = bmesh.new()
    bm_leaves = bmesh.new()
    for i in range(count):
        bx = x0 + (x1 - x0) * (i + 0.5) / count + rng.uniform(-0.08, 0.08)
        by = y_pos + rng.uniform(-0.14, 0.08)
        bh = rng.uniform(2.35, 3.15)
        lean_x = rng.uniform(-0.06, 0.06)
        lean_y = rng.uniform(-0.12, -0.02)
        r = rng.uniform(0.018, 0.026)
        # 6-sided bamboo stalk
        p0 = Vector((bx, by, 0.0))
        p1 = Vector((bx + lean_x, by + lean_y, bh))
        vec = p1 - p0
        q = Vector((0, 0, 1)).rotation_difference(vec.normalized())
        r0, r1 = [], []
        for k in range(6):
            ang = 2 * math.pi * k / 6
            d = Vector((math.cos(ang), math.sin(ang), 0))
            r0.append(bm_culms.verts.new(p0 + q @ (d * r)))
            r1.append(bm_culms.verts.new(p1 + q @ (d * (r * 0.65))))
        for k in range(6):
            kn = (k + 1) % 6
            bm_culms.faces.new((r0[k], r0[kn], r1[kn], r1[k]))
        # Delicate slender bamboo leaf clusters in upper half
        for _ in range(16):
            t_h = rng.uniform(0.42, 0.98)
            base = p0.lerp(p1, t_h) + Vector((rng.gauss(0, 0.14), rng.gauss(0, 0.14), rng.gauss(0, 0.08)))
            rot = Euler((rng.uniform(-0.6, 0.7), rng.uniform(-0.5, 0.5), rng.uniform(0, 6.28))).to_matrix()
            L = rng.uniform(0.14, 0.22)
            W = 0.042
            v0 = bm_leaves.verts.new(base)
            v1 = bm_leaves.verts.new(base + rot @ Vector((W, L * 0.4, 0.01)))
            v2 = bm_leaves.verts.new(base + rot @ Vector((0, L, -0.02)))
            v3 = bm_leaves.verts.new(base + rot @ Vector((-W, L * 0.4, 0.01)))
            f = bm_leaves.faces.new((v0, v1, v2, v3))
            f.material_index = rng.randint(0, 2)

    bmesh.ops.recalc_face_normals(bm_culms, faces=bm_culms.faces)
    apply_box_uv(bm_culms, scale=2.0)
    mc = bpy.data.meshes.new(f"{prefix}_Culms")
    bm_culms.to_mesh(mc)
    bm_culms.free()
    for p in mc.polygons:
        p.use_smooth = True
    mc.materials.append(mats["bamboo_culm"])
    link_obj(bpy.data.objects.new(f"{prefix}_Culms", mc), col_name)

    bmesh.ops.recalc_face_normals(bm_leaves, faces=bm_leaves.faces)
    apply_box_uv(bm_leaves, scale=3.0)
    ml = bpy.data.meshes.new(f"{prefix}_Leaves")
    bm_leaves.to_mesh(ml)
    bm_leaves.free()
    for m in (mats["foliage_dark"], mats["foliage_mid"], mats["foliage_sun"]):
        ml.materials.append(m)
    link_obj(bpy.data.objects.new(f"{prefix}_Leaves", ml), col_name)


def build_potted_plant(prefix, cx, cy, z0, radius, height, col_name, pot_mat):
    """Realistic indoor Fiddle-Leaf Fig in tapered ceramic vessel with soil & broad curved leaves."""
    rng = random.Random(hash(prefix) & 0xFFFF)
    pot_h = height * 0.26
    make_cylinder(f"{prefix}_Pot", cx, cy, z0, radius * 0.56, pot_h, col_name, pot_mat, segs=18, radius_top=radius * 0.68)
    make_cylinder(f"{prefix}_Soil", cx, cy, z0 + pot_h - 0.03, radius * 0.62, 0.035, col_name, mats["soil"], segs=14)
    make_cylinder(f"{prefix}_Stem", cx, cy, z0 + pot_h - 0.02, 0.016, height * 0.62, col_name, mats["bark"], segs=10, radius_top=0.009)

    bm = bmesh.new()
    for i in range(18):
        t = 0.28 + 0.72 * (i / 17.0)
        az = i * 2.39996 + rng.uniform(-0.2, 0.2)  # Golden angle spiral phyllotaxis!
        lz = pot_h + (height - pot_h) * t * 0.88
        tilt = 0.45 + 0.45 * (1.0 - t)
        L = radius * rng.uniform(0.85, 1.25)
        W = L * 0.62
        rot = Euler((0, 0, az)).to_matrix()
        p0 = Vector((0, 0, lz))
        p_l = rot @ Vector((-W * 0.5, L * 0.48 * math.sin(tilt), lz + L * 0.35 * math.cos(tilt)))
        p_r = rot @ Vector((W * 0.5, L * 0.48 * math.sin(tilt), lz + L * 0.35 * math.cos(tilt)))
        p_t = rot @ Vector((0, L * math.sin(tilt + 0.22), lz + L * 0.20 * math.cos(tilt) - 0.02))
        f = bm.faces.new((bm.verts.new(p0), bm.verts.new(p_r), bm.verts.new(p_t), bm.verts.new(p_l)))
        f.material_index = i % 2
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    apply_box_uv(bm, scale=2.5)
    mesh = bpy.data.meshes.new(f"{prefix}_Leaves")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mats["foliage_dark"])
    mesh.materials.append(mats["foliage_mid"])
    obj = bpy.data.objects.new(f"{prefix}_Leaves", mesh)
    obj.location = (cx, cy, z0)
    link_obj(obj, col_name)


def make_plane_uv(name, x0, y0, z0, x1, y1, z1, col_name, mat, flip_u=False):
    bm = bmesh.new()
    if abs(x1 - x0) < abs(y1 - y0):
        v0 = bm.verts.new((x0, y0, z0))
        v1 = bm.verts.new((x0, y1, z0))
        v2 = bm.verts.new((x0, y1, z1))
        v3 = bm.verts.new((x0, y0, z1))
    elif flip_u:
        # Facing +Y (viewed looking South -Y): viewer's left is x1 (+X) and right is x0 (-X)
        v0 = bm.verts.new((x1, y0, z0))
        v1 = bm.verts.new((x0, y0, z0))
        v2 = bm.verts.new((x0, y0, z1))
        v3 = bm.verts.new((x1, y0, z1))
    else:
        v0 = bm.verts.new((x0, y0, z0))
        v1 = bm.verts.new((x1, y0, z0))
        v2 = bm.verts.new((x1, y0, z1))
        v3 = bm.verts.new((x0, y0, z1))
    f = bm.faces.new((v0, v1, v2, v3))
    uv = bm.loops.layers.uv.verify()
    for loop, uv_co in zip(f.loops, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        loop[uv].uv = uv_co
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)
    return link_obj(bpy.data.objects.new(name, mesh), col_name)


# ---------------------------------------------------------------------------
# 5. ARCHITECTURE: PLINTH, FLOORS, WALLS, FACADE DETAILING & SKIRTING
# ---------------------------------------------------------------------------
fp_pts = [(x * M, y * M) for x, y in spec["building_footprint_polygon"]]
make_poly_slab("Arch_Building_Plinth", fp_pts, 0.0, FLOOR_Z - 0.02, "Architecture", mats["plinth_concrete"])

# Front entry architectural floating steps, fluted walnut feature cladding, dark bronze entry portal & house plaque
make_box("Arch_Entry_Step", 3.95, 1.54, 0.0, 5.45, 1.90, 0.08, "Architecture", mats["stepping_stone"], bevel=0.008)
make_box("Arch_Entry_StepShadowRecess", 4.02, 1.58, 0.0, 5.38, 1.90, 0.03, "Architecture", mats["black_metal"])
make_box("Arch_Facade_TeakCladding", 3.044, 1.872, FLOOR_Z, 4.12, 1.902, WALL_TOP_Z, "Architecture", mats["fluted_walnut"])
make_box("Arch_Facade_TeakCladding_Corner", 3.024, 1.872, FLOOR_Z, 3.046, 2.102, WALL_TOP_Z, "Architecture", mats["fluted_walnut"])
make_box("Arch_Facade_EntryPortal_Top", 4.12, 1.78, FLOOR_Z + 2.22, 5.84, 1.905, FLOOR_Z + 2.34, "Architecture", mats["black_metal"])
make_box("Arch_Facade_EntryPortal_L", 4.12, 1.78, FLOOR_Z, 4.19, 1.905, FLOOR_Z + 2.24, "Architecture", mats["black_metal"])
make_box("Arch_Facade_EntryPortal_R", 5.77, 1.78, FLOOR_Z, 5.84, 1.905, FLOOR_Z + 2.24, "Architecture", mats["black_metal"])
make_box("Arch_Facade_FasciaBand", 2.93, 1.29, ROOF_SLAB_TOP_Z - 0.065, SITE_W + 0.01, 1.32, ROOF_SLAB_TOP_Z, "Architecture", mats["black_metal"])
# Sculptural backlit house number plate on front facade
make_box("Arch_HouseNumber_Plaque", 3.45, 1.845, 1.62, 3.88, 1.872, 1.84, "Architecture", mats["black_metal"], bevel=0.004)
make_box("Arch_HouseNumber_Backlight", 3.47, 1.868, 1.64, 3.86, 1.874, 1.82, "Architecture", mats["emit_warm"])
# Architectural exterior wall sconces (front facade & rear courtyard)
for sc_name, sx, sy, sz in [
    ("Arch_Sconce_FrontL", 3.66, 1.84, 2.25),
    ("Arch_Sconce_FrontR", 6.18, 1.84, 2.25),
    ("Arch_Sconce_Rear1", 3.65, 11.73, 2.15),
    ("Arch_Sconce_Rear2", 5.60, 11.73, 2.15),
]:
    make_cylinder(sc_name, sx, sy, sz - 0.14, 0.036, 0.28, "Architecture", mats["black_metal"], segs=14)
    make_cylinder(f"{sc_name}_GlowT", sx, sy, sz + 0.135, 0.032, 0.012, "Architecture", mats["emit_warm"], segs=12)
    make_cylinder(f"{sc_name}_GlowB", sx, sy, sz - 0.148, 0.032, 0.012, "Architecture", mats["emit_warm"], segs=12)
# Recessed steel linear drainage grate across carport entrance
make_box("Arch_Carport_DrainGrate", 0.08, 0.04, 0.02, 2.98, 0.18, 0.034, "Architecture", mats["black_metal"])
# Wall-mounted Smart EV Wallbox Charger & holster on Carport East wall
make_box("Arch_Carport_EVWallbox", 3.005, 2.72, 1.12, 3.044, 2.98, 1.54, "Architecture", mats["black_metal"], bevel=0.012, smooth=True)
make_box("Arch_Carport_EVGlassFace", 2.998, 2.74, 1.15, 3.006, 2.96, 1.51, "Architecture", mats["tv_screen"], bevel=0.006)
make_box("Arch_Carport_EVStatusLED", 2.995, 2.77, 1.44, 3.001, 2.93, 1.465, "Architecture", mats["emit_ev_green"])
make_cylinder("Arch_Carport_EVCableCoil", 3.015, 2.85, 0.88, 0.095, 0.04, "Architecture", mats["car_tire"], segs=18)
# Low-voltage architectural landscape bollard path lights (Front Garden & Rear Courtyard)
for bol_name, bx, by in [
    ("Arch_Bollard_Front1", 4.10, 0.55),
    ("Arch_Bollard_Front2", 5.38, 1.25),
    ("Arch_Bollard_Front3", 7.35, 0.55),
    ("Arch_Bollard_Rear1", 1.15, 12.88),
    ("Arch_Bollard_Rear2", 3.15, 12.88),
    ("Arch_Bollard_Rear3", 5.20, 12.88),
]:
    make_cylinder(bol_name, bx, by, 0.01, 0.034, 0.52, "Architecture", mats["black_metal"], segs=14)
    make_cylinder(f"{bol_name}_Glow", bx, by, 0.45, 0.036, 0.045, "Architecture", mats["emit_warm"], segs=14)
    make_cylinder(f"{bol_name}_Cap", bx, by, 0.495, 0.040, 0.030, "Architecture", mats["black_metal"], segs=14)

# Interior Floors
floor_mat_map = {
    "engineered_white_oak": mats["floor_oak"],
    "large_format_limestone": mats["floor_limestone"],
    "honed_travertine_tile": mats["floor_travertine"],
    "matte_porcelain_grey": mats["floor_porcelain"],
}
for rm in spec["rooms"]:
    if rm.get("floor", 1) != 1:
        continue
    fmat = floor_mat_map.get(rm["floor_material"], mats["floor_limestone"])
    if "sub_rects" in rm:
        for idx, sr in enumerate(rm["sub_rects"]):
            make_box(f"Floor_{rm['id']}_{idx+1}", sr[0]*M, sr[1]*M, FLOOR_Z - 0.02, sr[2]*M, sr[3]*M, FLOOR_Z, "Floors", fmat)
    else:
        pts = [(x * M, y * M) for x, y in rm["polygon"]]
        make_poly_slab(f"Floor_{rm['id']}_{rm['name'].replace(' ', '_')}", pts, FLOOR_Z - 0.02, FLOOR_Z, "Floors", fmat)

# Outdoor Floors
make_box("Floor_EXT01_Carport_Basalt", 0.0, 0.0, -0.02, 3.044, 5.000, 0.03, "Floors", mats["floor_basalt"])
make_box("Floor_EXT02_FrontGarden_Lawn", 3.044, 0.0, -0.02, SITE_W, 1.900, 0.01, "Floors", mats["lawn"])
make_box("Floor_EXT03_RearGarden_Lawn", 0.0, 11.700, -0.02, 5.490, SITE_D, 0.01, "Floors", mats["lawn"])
make_box("Floor_EXT03_RearPebbleBorder", 0.0, 13.050, 0.005, 5.490, SITE_D, 0.028, "Floors", mats["pebbles"])
make_box("Floor_EXT04_RearTerrace_TeakDeck", 5.490, 11.700, 0.0, SITE_W, SITE_D, 0.11, "Floors", mats["floor_teak"], bevel=0.005)
make_box("Arch_Terrace_EdgeTrim", 5.45, 11.70, 0.0, 5.49, SITE_D, 0.115, "Architecture", mats["plinth_concrete"])
make_box("Arch_Pebble_Curb", 0.0, 13.02, 0.0, 5.46, 13.06, 0.045, "Architecture", mats["plinth_concrete"])

# Walls with exact Door & Window Openings + Collision Meshes
openings_by_wall = {}
for d in spec["doors"]:
    openings_by_wall.setdefault(d["host_wall"], []).append({
        "id": d["id"], "kind": "door",
        "rect": d["opening"], "sill_z": FLOOR_Z, "head_z": FLOOR_Z + d["height_mm"] * M,
    })
for w in spec["windows"]:
    openings_by_wall.setdefault(w["host_wall"], []).append({
        "id": w["id"], "kind": "window",
        "rect": w["opening"],
        "sill_z": FLOOR_Z + w["sill_height_mm"] * M,
        "head_z": FLOOR_Z + (w["sill_height_mm"] + w["height_mm"]) * M,
    })

for wall in spec["walls"]:
    wx0, wy0, wx1, wy1 = [c * M for c in wall["rect"]]
    wmat = mats["ext_stucco"] if wall["category"] == "exterior" else mats["int_wall_warm"]
    ops = openings_by_wall.get(wall["id"], [])
    orient = wall["orientation"]

    if not ops:
        make_box(f"Wall_{wall['id']}", wx0, wy0, FLOOR_Z, wx1, wy1, WALL_TOP_Z, "Walls", wmat)
        make_box(f"Col_Wall_{wall['id']}", wx0, wy0, FLOOR_Z, wx1, wy1, WALL_TOP_Z, "Collision_Meshes")
    else:
        if orient == "H":
            ops_sorted = sorted(ops, key=lambda o: o["rect"][0])
            cur_x = wx0
            seg_i = 1
            for op in ops_sorted:
                ox0, oy0, ox1, oy1 = [c * M for c in op["rect"]]
                if ox0 - cur_x > 1e-4:
                    make_box(f"Wall_{wall['id']}_P{seg_i}", cur_x, wy0, FLOOR_Z, ox0, wy1, WALL_TOP_Z, "Walls", wmat)
                    make_box(f"Col_Wall_{wall['id']}_P{seg_i}", cur_x, wy0, FLOOR_Z, ox0, wy1, WALL_TOP_Z, "Collision_Meshes")
                    seg_i += 1
                if op["sill_z"] > FLOOR_Z + 1e-4:
                    make_box(f"Wall_{wall['id']}_Sill_{op['id']}", ox0, wy0, FLOOR_Z, ox1, wy1, op["sill_z"], "Walls", wmat)
                    make_box(f"Col_Wall_{wall['id']}_Win_{op['id']}", ox0, wy0, FLOOR_Z, ox1, wy1, WALL_TOP_Z, "Collision_Meshes")
                elif op["kind"] == "window":
                    make_box(f"Col_Wall_{wall['id']}_Win_{op['id']}", ox0, wy0, FLOOR_Z, ox1, wy1, WALL_TOP_Z, "Collision_Meshes")
                if WALL_TOP_Z - op["head_z"] > 1e-4:
                    make_box(f"Wall_{wall['id']}_Head_{op['id']}", ox0, wy0, op["head_z"], ox1, wy1, WALL_TOP_Z, "Walls", wmat)
                cur_x = max(cur_x, ox1)
            if wx1 - cur_x > 1e-4:
                make_box(f"Wall_{wall['id']}_P{seg_i}", cur_x, wy0, FLOOR_Z, wx1, wy1, WALL_TOP_Z, "Walls", wmat)
                make_box(f"Col_Wall_{wall['id']}_P{seg_i}", cur_x, wy0, FLOOR_Z, wx1, wy1, WALL_TOP_Z, "Collision_Meshes")
        else:
            ops_sorted = sorted(ops, key=lambda o: o["rect"][1])
            cur_y = wy0
            seg_i = 1
            for op in ops_sorted:
                ox0, oy0, ox1, oy1 = [c * M for c in op["rect"]]
                if oy0 - cur_y > 1e-4:
                    make_box(f"Wall_{wall['id']}_P{seg_i}", wx0, cur_y, FLOOR_Z, wx1, oy0, WALL_TOP_Z, "Walls", wmat)
                    make_box(f"Col_Wall_{wall['id']}_P{seg_i}", wx0, cur_y, FLOOR_Z, wx1, oy0, WALL_TOP_Z, "Collision_Meshes")
                    seg_i += 1
                if op["sill_z"] > FLOOR_Z + 1e-4:
                    make_box(f"Wall_{wall['id']}_Sill_{op['id']}", wx0, oy0, FLOOR_Z, wx1, oy1, op["sill_z"], "Walls", wmat)
                    make_box(f"Col_Wall_{wall['id']}_Win_{op['id']}", wx0, oy0, FLOOR_Z, wx1, oy1, WALL_TOP_Z, "Collision_Meshes")
                elif op["kind"] == "window":
                    make_box(f"Col_Wall_{wall['id']}_Win_{op['id']}", wx0, oy0, FLOOR_Z, wx1, oy1, WALL_TOP_Z, "Collision_Meshes")
                if WALL_TOP_Z - op["head_z"] > 1e-4:
                    make_box(f"Wall_{wall['id']}_Head_{op['id']}", wx0, oy0, op["head_z"], wx1, oy1, WALL_TOP_Z, "Walls", wmat)
                cur_y = max(cur_y, oy1)
            if wy1 - cur_y > 1e-4:
                make_box(f"Wall_{wall['id']}_P{seg_i}", wx0, cur_y, FLOOR_Z, wx1, wy1, WALL_TOP_Z, "Walls", wmat)
                make_box(f"Col_Wall_{wall['id']}_P{seg_i}", wx0, cur_y, FLOOR_Z, wx1, wy1, WALL_TOP_Z, "Collision_Meshes")

# Skirting Boards
skirting_runs = [
    ("Skirt_EastWall", 8.929, 2.10, 8.944, 11.50),
    ("Skirt_WestWall_Master", 0.200, 8.20, 0.215, 11.50),
    ("Skirt_WestWall_Bed2", 0.200, 5.20, 0.215, 8.08),
    ("Skirt_Master_Bed2_N", 0.20, 8.20, 3.80, 8.215),
    ("Skirt_Master_Bed2_S", 0.20, 8.065, 3.124, 8.08),
    ("Skirt_Bed3_Kitchen_S", 6.084, 5.065, 8.944, 5.08),
    ("Skirt_Bed3_Kitchen_N", 6.084, 5.20, 8.944, 5.215),
    ("Skirt_Foyer_West", 3.244, 2.10, 3.259, 3.52),
    ("Skirt_Living_Ensuite", 5.490, 9.32, 5.505, 11.50),
]
for sk_name, x0, y0, x1, y1 in skirting_runs:
    make_box(sk_name, x0, y0, FLOOR_Z, x1, y1, FLOOR_Z + 0.095, "Walls", mats["skirting"])

# ---------------------------------------------------------------------------
# 6. LEVEL 1 CEILINGS, INTER-FLOOR SLAB, FLOATING STAIRCASE & COMPLETE LEVEL 2
#    (RM-12 TEMPAT JEMURAN & SERVICE DECK · RM-13 SKY LOUNGE · EXT-05 FRONT BALCONY)
# ---------------------------------------------------------------------------
# Level 1 Ceilings (toggled when viewing Level 1 Dollhouse cutaway)
make_poly_slab("Ceiling_Main_Interior", fp_pts, WALL_TOP_Z, WALL_TOP_Z + 0.08, "Ceilings", mats["ceiling_white"])
make_box("Ceiling_Wet_MasterEnsuite", 3.92, 9.32, FLOOR_Z + WET_CEIL_H, 5.37, 11.50, WALL_TOP_Z, "Ceilings", mats["ceiling_white"])
make_box("Ceiling_Wet_SharedBath", 3.244, 5.12, FLOOR_Z + WET_CEIL_H, 4.744, 7.04, WALL_TOP_Z, "Ceilings", mats["ceiling_white"])
make_box("Ceiling_Wet_Laundry", 3.244, 3.64, FLOOR_Z + WET_CEIL_H, 4.744, 5.00, WALL_TOP_Z, "Ceilings", mats["ceiling_white"])

# Inter-Floor Structural Concrete Slab (L2 Base Plate) + Warm Oiled Teak Entry & Terrace Soffits
slab_l2_pts = [
    (2.944, 1.45), (SITE_W, 1.45), (SITE_W, 12.45),
    (0.0, 12.45), (0.0, 4.78), (2.944, 4.78),
]
make_poly_slab("L2_Slab_StructuralPlate", slab_l2_pts, WALL_TOP_Z + 0.08, FLOOR2_Z - 0.02, "Architecture", mats["ext_stucco"])
make_box("L2_Slab_FasciaBand_Front", 2.935, 1.435, FLOOR2_Z - 0.065, SITE_W + 0.01, 1.46, FLOOR2_Z - 0.01, "Architecture", mats["black_metal"])
make_box("L2_Slab_Soffit_FrontEntry", 2.98, 1.48, WALL_TOP_Z + 0.06, SITE_W - 0.04, 1.90, WALL_TOP_Z + 0.08, "Architecture", mats["floor_teak"])
make_box("L2_Slab_Soffit_RearTerrace", 5.45, 11.70, WALL_TOP_Z + 0.06, SITE_W - 0.04, 12.42, WALL_TOP_Z + 0.08, "Architecture", mats["floor_teak"])

# L2 Finished Floors (strictly inside 9.144 x 13.500 m site bounds!)
make_box("Floor_L2_RM12_Jemuran", 0.20, 6.80, FLOOR2_Z - 0.02, 4.864, 11.50, FLOOR2_Z, "Floors", mats["floor_porcelain"])
make_box("L2_Jemuran_LinearDrain", 0.40, 7.06, FLOOR2_Z - 0.005, 4.66, 7.13, FLOOR2_Z + 0.004, "Architecture", mats["brushed_steel"])
make_box("Floor_L2_RM13_SkyLounge", 4.984, 5.20, FLOOR2_Z - 0.02, 8.944, 11.50, FLOOR2_Z, "Floors", mats["floor_oak"])
make_box("Floor_L2_EXT05_FrontBalcony", 3.164, 2.04, FLOOR2_Z - 0.03, 8.944, 5.00, FLOOR2_Z - 0.006, "Floors", mats["floor_teak"], bevel=0.004)
make_box("Floor_L2_WestPlanterRoof", 0.20, 4.96, FLOOR2_Z - 0.03, 3.164, 6.80, FLOOR2_Z - 0.01, "Floors", mats["pebbles"])
# L2 Upper Stair Landing connecting Rear Staircase cleanly to RM-12 Tempat Jemuran
make_box("Floor_L2_StairLanding", 0.18, 11.70, FLOOR2_Z - 0.16, 1.92, 13.40, FLOOR2_Z, "Floors", mats["floor_porcelain"], bevel=0.006)
make_box("L2_StairLanding_ColW", 0.20, 13.26, 0.0, 0.32, 13.38, FLOOR2_Z - 0.16, "Architecture", mats["black_metal"])
make_box("L2_StairLanding_ColE", 1.78, 13.26, 0.0, 1.90, 13.38, FLOOR2_Z - 0.16, "Architecture", mats["black_metal"])

# --- SCULPTURAL COVERED FLOATING STAIRCASE (L1 Rear Terrace X=5.50 -> L2 Landing X=1.90, Y=12.52..13.38) ---
# Twin angled structural steel stringers (custom clean extruded beams)
for st_idx, sy_beam in enumerate((12.68, 13.22)):
    bm_st = bmesh.new()
    p_bot = Vector((5.58, sy_beam, 0.11))
    p_top = Vector((1.88, sy_beam, FLOOR2_Z - 0.08))
    hw_b, hh_b = 0.032, 0.13
    r_b = [
        bm_st.verts.new((p_bot.x, sy_beam - hw_b, p_bot.z)),
        bm_st.verts.new((p_bot.x, sy_beam + hw_b, p_bot.z)),
        bm_st.verts.new((p_bot.x, sy_beam + hw_b, p_bot.z + hh_b)),
        bm_st.verts.new((p_bot.x, sy_beam - hw_b, p_bot.z + hh_b)),
    ]
    r_t = [
        bm_st.verts.new((p_top.x, sy_beam - hw_b, p_top.z - hh_b)),
        bm_st.verts.new((p_top.x, sy_beam + hw_b, p_top.z - hh_b)),
        bm_st.verts.new((p_top.x, sy_beam + hw_b, p_top.z)),
        bm_st.verts.new((p_top.x, sy_beam - hw_b, p_top.z)),
    ]
    for k in range(4):
        kn = (k + 1) % 4
        bm_st.faces.new((r_b[k], r_b[kn], r_t[kn], r_t[k]))
    bm_st.faces.new(r_b[::-1])
    bm_st.faces.new(r_t)
    bmesh.ops.recalc_face_normals(bm_st, faces=bm_st.faces)
    apply_box_uv(bm_st, scale=1.0)
    m_st = bpy.data.meshes.new(f"L2_Stair_Stringer_{st_idx}")
    bm_st.to_mesh(m_st)
    bm_st.free()
    m_st.materials.append(mats["black_metal"])
    link_obj(bpy.data.objects.new(f"L2_Stair_Stringer_{st_idx}", m_st), "Architecture")

# 16 Floating Solid American Walnut Treads + Warm Under-Tread LED Accent Strips
n_steps = 16
for step_i in range(n_steps):
    frac = (step_i + 1) / float(n_steps)
    tx_center = 5.52 - step_i * 0.225
    tz_top = 0.11 + frac * (FLOOR2_Z - 0.11)
    make_box(
        f"L2_Stair_Tread_{step_i+1:02d}",
        tx_center - 0.135, 12.52, tz_top - 0.048,
        tx_center + 0.135, 13.38, tz_top,
        "Architecture", mats["walnut"], bevel=0.005
    )
    if step_i % 2 == 0:
        make_box(
            f"L2_Stair_LED_{step_i+1:02d}",
            tx_center + 0.115, 12.60, tz_top - 0.056,
            tx_center + 0.130, 13.30, tz_top - 0.046,
            "Lighting", mats["emit_warm"]
        )

# Angled Tempered Glass Balustrade & Matte-Black Handrail along South side of Staircase (Y=12.52)
bm_sg = bmesh.new()
sg_pts = [
    (5.58, 12.52, 0.18), (1.90, 12.52, FLOOR2_Z - 0.02),
    (1.90, 12.52, FLOOR2_Z + 1.02), (5.58, 12.52, 1.18),
]
v_sg0 = [bm_sg.verts.new((px, py - 0.007, pz)) for px, py, pz in sg_pts]
v_sg1 = [bm_sg.verts.new((px, py + 0.007, pz)) for px, py, pz in sg_pts]
bm_sg.faces.new(v_sg0)
bm_sg.faces.new(v_sg1[::-1])
for k in range(4):
    kn = (k + 1) % 4
    bm_sg.faces.new((v_sg0[k], v_sg0[kn], v_sg1[kn], v_sg1[k]))
bmesh.ops.recalc_face_normals(bm_sg, faces=bm_sg.faces)
apply_box_uv(bm_sg, scale=1.0)
m_sg = bpy.data.meshes.new("L2_Stair_GlassGuard")
bm_sg.to_mesh(m_sg)
bm_sg.free()
m_sg.materials.append(mats["glass_clear"])
link_obj(bpy.data.objects.new("L2_Stair_GlassGuard", m_sg), "Architecture")
make_swept_tube("L2_Stair_Handrail", [(5.60, 12.52, 1.19), (1.88, 12.52, FLOOR2_Z + 1.03)], 0.022, "Architecture", mats["black_metal"], segs=10)
make_swept_tube("L2_Stair_HandrailWall", [(5.58, 13.35, 1.16), (1.92, 13.35, FLOOR2_Z + 1.00)], 0.018, "Architecture", mats["black_metal"], segs=10)

# Upper Landing & Rear Drying Deck Frameless Glass Balustrades (H = 1.05 m)
for rg_name, rx0, ry0, rx1, ry1 in [
    ("L2_Rail_Landing_N", 0.20, 13.36, 1.90, 13.385),
    ("L2_Rail_Landing_W", 0.20, 11.70, 0.225, 13.38),
    ("L2_Rail_Jemuran_N", 1.85, 11.54, 4.864, 11.565),
    ("L2_Rail_Balcony_S", 3.164, 2.02, 8.95, 2.045),
    ("L2_Rail_Balcony_W", 3.164, 2.04, 3.189, 6.80),
]:
    make_box(f"{rg_name}_Glass", rx0, ry0, FLOOR2_Z, rx1, ry1, FLOOR2_Z + 1.03, "Architecture", mats["glass_clear"])
    make_box(f"{rg_name}_Cap", rx0 - 0.012, ry0 - 0.012, FLOOR2_Z + 1.02, rx1 + 0.012, ry1 + 0.012, FLOOR2_Z + 1.06, "Architecture", mats["black_metal"])
    make_box(f"{rg_name}_Base", rx0 - 0.015, ry0 - 0.015, FLOOR2_Z - 0.01, rx1 + 0.015, ry1 + 0.015, FLOOR2_Z + 0.055, "Architecture", mats["black_metal"])

# --- LEVEL 2 WALLS, PRIVACY BREEZE-SCREENS & WINDOWS ---
# RM-12 Tempat Jemuran West Wall (solid masonry half-wall + horizontal breathable teak privacy louvers!)
make_box("Wall_L2_Jemuran_WestBase", 0.0, 6.80, FLOOR2_Z, 0.20, 11.70, FLOOR2_Z + 1.20, "Walls", mats["ext_stucco"])
make_box("Wall_L2_Jemuran_WestCap", -0.01, 6.80, FLOOR2_Z + 1.20, 0.21, 11.70, FLOOR2_Z + 1.24, "Architecture", mats["roof_coping"])
for wl_i in range(11):
    lz = FLOOR2_Z + 1.34 + wl_i * 0.135
    make_box(f"L2_Jemuran_WestLouver_{wl_i:02d}", 0.05, 6.88, lz, 0.15, 11.62, lz + 0.068, "Architecture", mats["walnut"], bevel=0.004)
for wp_y in (6.84, 9.25, 11.64):
    make_box(f"L2_Jemuran_WestPost_{wp_y:.2f}", 0.03, wp_y - 0.04, FLOOR2_Z + 1.20, 0.17, wp_y + 0.04, WALL2_TOP_Z, "Architecture", mats["black_metal"])

# RM-12 Tempat Jemuran South Privacy Breeze-Screen (screens hanging clothes elegantly from street view!)
make_box("Wall_L2_Jemuran_SouthBase", 0.20, 6.80, FLOOR2_Z, 4.864, 7.00, FLOOR2_Z + 1.08, "Walls", mats["ext_stucco"])
make_box("Wall_L2_Jemuran_SouthCap", 0.19, 6.79, FLOOR2_Z + 1.08, 4.87, 7.01, FLOOR2_Z + 1.12, "Architecture", mats["roof_coping"])
make_box("L2_Jemuran_SouthBeam", 0.18, 6.82, WALL2_TOP_Z - 0.16, 4.88, 6.98, WALL2_TOP_Z, "Architecture", mats["black_metal"])
# Vertical architectural teak privacy slats spaced cleanly for full tropical airflow!
for sl_x_i in range(28):
    sx = 0.30 + sl_x_i * 0.162
    if sx < 4.78:
        make_box(f"L2_Jemuran_SouthSlat_{sl_x_i:02d}", sx, 6.86, FLOOR2_Z + 1.12, sx + 0.055, 6.94, WALL2_TOP_Z - 0.16, "Architecture", mats["walnut"], bevel=0.004)

# Low architectural parapet rim around West roof planter deck (X=0..3.16, Y=4.78..6.80)
make_box("Wall_L2_WestPlanterParapet_S", 0.0, 4.78, FLOOR2_Z - 0.02, 3.164, 4.96, FLOOR2_Z + 0.42, "Walls", mats["ext_stucco"])
make_box("Wall_L2_WestPlanterParapet_W", 0.0, 4.96, FLOOR2_Z - 0.02, 0.20, 6.80, FLOOR2_Z + 0.42, "Walls", mats["ext_stucco"])
make_box("L2_WestPlanterParapet_CapS", -0.01, 4.77, FLOOR2_Z + 0.42, 3.17, 4.97, FLOOR2_Z + 0.455, "Architecture", mats["roof_coping"])
make_box("L2_WestPlanterParapet_CapW", -0.01, 4.96, FLOOR2_Z + 0.42, 0.21, 6.80, FLOOR2_Z + 0.455, "Architecture", mats["roof_coping"])

# RM-13 L2 Sky Lounge Structural Walls (East, West w/ Door D9, North w/ Window W7, South w/ Sliding Door D10)
make_box("Wall_L2_Lounge_East", 8.944, 5.00, FLOOR2_Z, SITE_W, 11.70, WALL2_TOP_Z, "Walls", mats["ext_stucco"])
make_box("Wall_L2_Balcony_EastWing", 8.944, 2.00, FLOOR2_Z - 0.02, SITE_W, 5.00, FLOOR2_Z + 1.15, "Walls", mats["ext_stucco"])
make_box("L2_Balcony_EastWing_Cap", 8.93, 1.99, FLOOR2_Z + 1.15, SITE_W + 0.01, 5.01, FLOOR2_Z + 1.185, "Architecture", mats["roof_coping"])
# West Partition separating RM-12 Tempat Jemuran <-> RM-13 Sky Lounge (with Door D9 opening at Y = 8.20..9.10, H = 2.15 m)
make_box("Wall_L2_Lounge_West_S", 4.864, 5.00, FLOOR2_Z, 4.984, 8.20, WALL2_TOP_Z, "Walls", mats["int_wall_warm"])
make_box("Wall_L2_Lounge_West_N", 4.864, 9.10, FLOOR2_Z, 4.984, 11.70, WALL2_TOP_Z, "Walls", mats["int_wall_warm"])
make_box("Wall_L2_Lounge_West_HeadD9", 4.864, 8.20, FLOOR2_Z + 2.15, 4.984, 9.10, WALL2_TOP_Z, "Walls", mats["int_wall_warm"])
# North Rear Wall of Sky Lounge with Panoramic Window W7 (X = 5.65..8.25, sill 0.65m, H = 1.85m)
make_box("Wall_L2_Lounge_North_W", 4.984, 11.50, FLOOR2_Z, 5.65, 11.70, WALL2_TOP_Z, "Walls", mats["ext_stucco"])
make_box("Wall_L2_Lounge_North_E", 8.25, 11.50, FLOOR2_Z, 8.944, 11.70, WALL2_TOP_Z, "Walls", mats["ext_stucco"])
make_box("Wall_L2_Lounge_North_SillW7", 5.65, 11.50, FLOOR2_Z, 8.25, 11.70, FLOOR2_Z + 0.65, "Walls", mats["ext_stucco"])
make_box("Wall_L2_Lounge_North_HeadW7", 5.65, 11.50, FLOOR2_Z + 2.50, 8.25, 11.70, WALL2_TOP_Z, "Walls", mats["ext_stucco"])
# Window W7 Frame, Mullion & Low-E Glass
make_box("WinSill_L2_W7", 5.635, 11.47, FLOOR2_Z + 0.62, 8.265, 11.73, FLOOR2_Z + 0.65, "Windows", mats["floor_limestone"], bevel=0.003)
make_box("WinFrame_L2_W7_B", 5.65, 11.56, FLOOR2_Z + 0.65, 8.25, 11.64, FLOOR2_Z + 0.70, "Windows", mats["black_metal"])
make_box("WinFrame_L2_W7_T", 5.65, 11.56, FLOOR2_Z + 2.45, 8.25, 11.64, FLOOR2_Z + 2.50, "Windows", mats["black_metal"])
make_box("WinFrame_L2_W7_L", 5.65, 11.56, FLOOR2_Z + 0.65, 5.70, 11.64, FLOOR2_Z + 2.50, "Windows", mats["black_metal"])
make_box("WinFrame_L2_W7_R", 8.20, 11.56, FLOOR2_Z + 0.65, 8.25, 11.64, FLOOR2_Z + 2.50, "Windows", mats["black_metal"])
make_box("WinMullion_L2_W7", 6.93, 11.565, FLOOR2_Z + 0.70, 6.97, 11.635, FLOOR2_Z + 2.45, "Windows", mats["black_metal"])
make_box("WinGlass_L2_W7", 5.70, 11.593, FLOOR2_Z + 0.70, 8.20, 11.607, FLOOR2_Z + 2.45, "Windows", mats["glass_clear"])

# South Balcony Facade Wall of Sky Lounge with 2.80m 3-Panel Sliding Glass Door D10 (X = 5.55..8.35, H = 2.40m)
make_box("Wall_L2_Lounge_South_W", 4.984, 5.00, FLOOR2_Z, 5.55, 5.20, WALL2_TOP_Z, "Walls", mats["ext_stucco"])
make_box("Wall_L2_Lounge_South_E", 8.35, 5.00, FLOOR2_Z, 8.944, 5.20, WALL2_TOP_Z, "Walls", mats["ext_stucco"])
make_box("Wall_L2_Lounge_South_HeadD10", 5.55, 5.00, FLOOR2_Z + 2.40, 8.35, 5.20, WALL2_TOP_Z, "Walls", mats["ext_stucco"])
# Fluted walnut exterior architectural accent on Sky Lounge South-West pier
make_box("L2_Facade_TeakAccent", 4.984, 4.972, FLOOR2_Z, 5.55, 5.002, WALL2_TOP_Z, "Architecture", mats["fluted_walnut"])

# L2 Front Balcony Built-In Stone Planter Trough
make_box("L2_Balcony_PlanterBox", 6.20, 2.08, FLOOR2_Z - 0.006, 8.90, 2.52, FLOOR2_Z + 0.42, "Architecture", mats["ext_stucco"], bevel=0.008)
make_box("L2_Balcony_PlanterSoil", 6.26, 2.14, FLOOR2_Z + 0.34, 8.84, 2.46, FLOOR2_Z + 0.39, "Architecture", mats["soil"])

# --- LEVEL 2 CEILINGS, SKYLIGHT PERGOLA ROOF (TEMPAT JEMURAN) & CANTILEVERED MAIN ROOF ---
make_box("Ceiling_L2_SkyLounge", 4.984, 5.20, WALL2_TOP_Z - 0.04, 8.944, 11.50, WALL2_TOP_Z + 0.04, "Ceilings", mats["ceiling_white"])

# Cantilevered Upper Main Roof over RM-13 Sky Lounge & Front Balcony Overhang
make_box("Roof_L2_Lounge_Slab", 4.80, 4.10, WALL2_TOP_Z + 0.04, SITE_W, 12.10, ROOF2_SLAB_TOP_Z, "Roof", mats["ext_stucco"])
make_box("Roof_L2_Lounge_Membrane", 4.98, 4.28, ROOF2_SLAB_TOP_Z, SITE_W - 0.18, 11.92, ROOF2_SLAB_TOP_Z + 0.03, "Roof", mats["roof_membrane"])
make_box("Roof_L2_Lounge_SoffitFront", 4.86, 4.14, WALL2_TOP_Z + 0.02, SITE_W - 0.04, 5.02, WALL2_TOP_Z + 0.045, "Roof", mats["floor_teak"])
make_box("Roof_L2_Lounge_FasciaBand", 4.79, 4.085, ROOF2_SLAB_TOP_Z - 0.06, SITE_W + 0.01, 4.11, ROOF2_SLAB_TOP_Z, "Roof", mats["black_metal"])
for p2n, x0, y0, x1, y1 in [
    ("Roof_L2_Parapet_S", 4.80, 4.10, SITE_W, 4.30),
    ("Roof_L2_Parapet_E", SITE_W - 0.20, 4.30, SITE_W, 12.10),
    ("Roof_L2_Parapet_N", 4.80, 11.90, SITE_W - 0.20, 12.10),
    ("Roof_L2_Parapet_W", 4.80, 4.30, 5.00, 11.90),
]:
    make_box(p2n, x0, y0, ROOF2_SLAB_TOP_Z, x1, y1, PARAPET_TOP_Z, "Roof", mats["ext_stucco"])
    make_box(f"{p2n}_Coping", x0 - 0.015, y0 - 0.015, PARAPET_TOP_Z, x1 + 0.015, y1 + 0.015, PARAPET_TOP_Z + 0.035, "Roof", mats["roof_coping"])

# Semi-Open Rainproof Skylight Pergola Roof over RM-12 Tempat Jemuran + Rear Staircase Canopy!
make_box("Roof_L2_Jemuran_BeamW", 0.04, 6.80, WALL2_TOP_Z - 0.14, 0.18, 13.44, WALL2_TOP_Z + 0.06, "Roof", mats["black_metal"])
make_box("Roof_L2_Jemuran_BeamE", 4.74, 6.80, WALL2_TOP_Z - 0.14, 4.88, 11.70, WALL2_TOP_Z + 0.06, "Roof", mats["black_metal"])
make_box("Roof_L2_Jemuran_BeamS", 0.04, 6.80, WALL2_TOP_Z - 0.14, 4.88, 6.96, WALL2_TOP_Z + 0.06, "Roof", mats["black_metal"])
make_box("Roof_L2_Jemuran_BeamMid", 0.04, 11.58, WALL2_TOP_Z - 0.14, 4.88, 11.72, WALL2_TOP_Z + 0.06, "Roof", mats["black_metal"])
make_box("Roof_L2_StairCanopy_BeamN", 0.04, 13.30, WALL2_TOP_Z - 0.14, 5.64, 13.44, WALL2_TOP_Z + 0.06, "Roof", mats["black_metal"])
make_box("Roof_L2_StairCanopy_BeamE", 5.50, 11.70, WALL2_TOP_Z - 0.14, 5.64, 13.44, WALL2_TOP_Z + 0.06, "Roof", mats["black_metal"])
# Spaced warm teak skylight louvers over Tempat Jemuran (bevelled timber + 28mm clean gap below glass to prevent z-fighting!)
for jl_i in range(14):
    jy = 7.12 + jl_i * 0.32
    if jy < 11.50:
        make_box(f"Roof_L2_Jemuran_Slat_{jl_i+1:02d}", 0.18, jy, WALL2_TOP_Z - 0.08, 4.74, jy + 0.055, WALL2_TOP_Z + 0.015, "Roof", mats["walnut"], bevel=0.004)
# Clear UV-filtering laminated glass rain shields mounted on slim glazing standoffs cleanly above rafters (zero z-fighting!)
make_box("Roof_L2_Jemuran_GlassRoof", 0.20, 6.98, WALL2_TOP_Z + 0.048, 4.72, 11.56, WALL2_TOP_Z + 0.066, "Roof", mats["glass_clear"])
make_box("Roof_L2_StairCanopy_GlassRoof", 0.20, 11.74, WALL2_TOP_Z + 0.048, 5.48, 13.28, WALL2_TOP_Z + 0.066, "Roof", mats["glass_clear"])
# Support steel column at North-East corner of Staircase Canopy
make_box("L2_StairCanopy_PostNE", 5.50, 13.30, 0.0, 5.62, 13.42, WALL2_TOP_Z - 0.14, "Architecture", mats["black_metal"])

# Carport Steel & Timber-Slat Pergola (Bevelled 4-sided structural steel frame + 30mm standoff glass rain shield — ZERO z-fighting!)
make_box("Arch_Carport_Beam_West", 0.04, 0.18, 2.75, 0.18, 5.00, 2.95, "Architecture", mats["black_metal"], bevel=0.005)
make_box("Arch_Carport_Beam_East", 2.904, 0.18, 2.75, 3.044, 5.00, 2.95, "Architecture", mats["black_metal"], bevel=0.005)
make_box("Arch_Carport_Beam_Front", 0.04, 0.18, 2.75, 3.044, 0.34, 2.95, "Architecture", mats["black_metal"], bevel=0.005)
make_box("Arch_Carport_Beam_Rear", 0.04, 4.86, 2.75, 3.044, 5.00, 2.95, "Architecture", mats["black_metal"], bevel=0.005)
make_box("Arch_Carport_Col_Front", 0.05, 0.20, 0.03, 0.17, 0.32, 2.75, "Architecture", mats["black_metal"], bevel=0.004)
make_box("Arch_Carport_Col_Mid", 0.05, 2.60, 0.03, 0.17, 2.72, 2.75, "Architecture", mats["black_metal"], bevel=0.004)
make_box("Arch_Carport_Col_FrontEast", 2.914, 1.90, 0.03, 3.034, 2.02, 2.75, "Architecture", mats["black_metal"], bevel=0.004)
slat_mesh = None
for i, ys in enumerate([0.55 + k * 0.34 for k in range(13)]):
    if slat_mesh is None:
        s_obj = make_box(f"Roof_Carport_Slat_{i+1:02d}", 0.18, ys, 2.78, 2.904, ys + 0.055, 2.895, "Roof", mats["walnut"], bevel=0.004)
        slat_mesh = s_obj.data
    else:
        inst = bpy.data.objects.new(f"Roof_Carport_Slat_{i+1:02d}", slat_mesh)
        inst.location = (1.542, ys + 0.0275, 2.8375)
        link_obj(inst, "Roof")
# Slim glazing purlins supporting the glass roof cleanly 30mm above the walnut slats
make_box("Roof_Carport_GlazingBar_W", 0.20, 0.35, 2.900, 0.24, 4.85, 2.928, "Roof", mats["black_metal"])
make_box("Roof_Carport_GlazingBar_M", 1.52, 0.35, 2.900, 1.56, 4.85, 2.928, "Roof", mats["black_metal"])
make_box("Roof_Carport_GlazingBar_E", 2.84, 0.35, 2.900, 2.88, 4.85, 2.928, "Roof", mats["black_metal"])
make_box("Roof_Carport_RainShield", 0.195, 0.350, 2.930, 2.889, 4.850, 2.948, "Roof", mats["glass_clear"])

# ---------------------------------------------------------------------------
# 7. INTERACTIVE DOORS (EXACT BLENDER HINGE PIVOTS + HARDWARE)
# ---------------------------------------------------------------------------
door_interactive_meta = []

for d in spec["doors"]:
    did = d["id"]
    ox0, oy0, ox1, oy1 = [c * M for c in d["opening"]]
    dh = d["height_mm"] * M
    dw = d["width_mm"] * M
    is_h = (ox1 - ox0) > (oy1 - oy0)

    ft = 0.045
    frame_mat = mats["black_metal"] if did in ("D1", "D8") else mats["walnut"]
    if is_h:
        make_box(f"DoorFrame_{did}_L", ox0, oy0 - 0.01, FLOOR_Z, ox0 + ft, oy1 + 0.01, FLOOR_Z + dh, "Doors", frame_mat)
        make_box(f"DoorFrame_{did}_R", ox1 - ft, oy0 - 0.01, FLOOR_Z, ox1, oy1 + 0.01, FLOOR_Z + dh, "Doors", frame_mat)
        make_box(f"DoorFrame_{did}_Top", ox0, oy0 - 0.01, FLOOR_Z + dh - ft, ox1, oy1 + 0.01, FLOOR_Z + dh, "Doors", frame_mat)
    else:
        make_box(f"DoorFrame_{did}_S", ox0 - 0.01, oy0, FLOOR_Z, ox1 + 0.01, oy0 + ft, FLOOR_Z + dh, "Doors", frame_mat)
        make_box(f"DoorFrame_{did}_N", ox0 - 0.01, oy1 - ft, FLOOR_Z, ox1 + 0.01, oy1, FLOOR_Z + dh, "Doors", frame_mat)
        make_box(f"DoorFrame_{did}_Top", ox0 - 0.01, oy0, FLOOR_Z + dh - ft, ox1 + 0.01, oy1, FLOOR_Z + dh, "Doors", frame_mat)

    if d["swing_arc"]:
        hx, hy = d["hinge"][0] * M, d["hinge"][1] * M
        leaf_mat = mats["fluted_walnut"] if did == "D1" else mats["walnut"]
        handle_mat = mats["brushed_brass"] if did == "D1" else mats["black_metal"]
        leaf_t = 0.048
        if is_h:
            lx0, lx1 = ox0 + ft, ox1 - ft
            ly0, ly1 = hy - leaf_t * 0.5, hy + leaf_t * 0.5
            leaf = make_box(f"Door_Interactive_{did}", lx0, ly0, FLOOR_Z + 0.006, lx1, ly1, FLOOR_Z + dh - ft,
                            "Doors", leaf_mat, bevel=0.004, origin_mode=(hx, hy, FLOOR_Z))
            hnd_x = lx1 - 0.11 if abs(hx - ox0) < abs(hx - ox1) else lx0 + 0.11
            # Vertical architectural brass pull bar for main pivot door D1!
            if did == "D1":
                h1 = make_box(f"DoorHandle_{did}_Out", hnd_x - 0.018, ly0 - 0.055, FLOOR_Z + 0.72, hnd_x + 0.018, ly0, FLOOR_Z + 1.52, "Doors", handle_mat, bevel=0.004)
                h2 = make_box(f"DoorHandle_{did}_In", hnd_x - 0.018, ly1, FLOOR_Z + 0.72, hnd_x + 0.018, ly1 + 0.055, FLOOR_Z + 1.52, "Doors", handle_mat, bevel=0.004)
            else:
                h1 = make_box(f"DoorHandle_{did}_Out", hnd_x - 0.06, ly0 - 0.05, FLOOR_Z + 1.02, hnd_x + 0.06, ly0, FLOOR_Z + 1.045, "Doors", handle_mat)
                h2 = make_box(f"DoorHandle_{did}_In", hnd_x - 0.06, ly1, FLOOR_Z + 1.02, hnd_x + 0.06, ly1 + 0.05, FLOOR_Z + 1.045, "Doors", handle_mat)
        else:
            ly0, ly1 = oy0 + ft, oy1 - ft
            lx0, lx1 = hx - leaf_t * 0.5, hx + leaf_t * 0.5
            leaf = make_box(f"Door_Interactive_{did}", lx0, ly0, FLOOR_Z + 0.006, lx1, ly1, FLOOR_Z + dh - ft,
                            "Doors", leaf_mat, bevel=0.004, origin_mode=(hx, hy, FLOOR_Z))
            hnd_y = ly1 - 0.11 if abs(hy - oy0) < abs(hy - oy1) else ly0 + 0.11
            h1 = make_box(f"DoorHandle_{did}_W", lx0 - 0.05, hnd_y - 0.06, FLOOR_Z + 1.02, lx0, hnd_y + 0.06, FLOOR_Z + 1.045, "Doors", handle_mat)
            h2 = make_box(f"DoorHandle_{did}_E", lx1, hnd_y - 0.06, FLOOR_Z + 1.02, lx1 + 0.05, hnd_y + 0.06, FLOOR_Z + 1.045, "Doors", handle_mat)

        bpy.context.view_layer.update()
        for h_obj in (h1, h2):
            h_obj.parent = leaf
            h_obj.matrix_parent_inverse = leaf.matrix_world.inverted()

        # Exact Three.js Y-up rotation sign so every hinged door swings INTO its target room
        swing_sign_map = {"D1": 1, "D2": 1, "D3": -1, "D4": 1, "D5": 1, "D6": -1}
        cx_d = (ox0 + ox1) * 0.5
        cy_d = (oy0 + oy1) * 0.5
        door_interactive_meta.append({
            "id": did,
            "label": d["type"],
            "connects": d["connects"],
            "object_name": leaf.name,
            "kind": "hinged",
            "pivot_blender": [round(hx, 4), round(hy, 4), round(FLOOR_Z, 4)],
            "pivot_threejs": [round(hx, 4), round(FLOOR_Z, 4), round(-hy, 4)],
            "center_threejs": [round(cx_d, 4), round(FLOOR_Z + 1.0, 4), round(-cy_d, 4)],
            "closed_aabb_threejs": [
                round(min(ox0, ox1), 4), round(FLOOR_Z, 4), round(-max(oy0, oy1), 4),
                round(max(ox0, ox1), 4), round(FLOOR_Z + dh, 4), round(-min(oy0, oy1), 4),
            ],
            "open_angle_deg": 90,
            "swing_sign": swing_sign_map.get(did, 1),
            "swing_direction": d["swing_direction"],
        })

    elif d.get("sliding_panels"):
        make_box(f"DoorTrack_{did}_Bot", ox0, oy0, FLOOR_Z, ox1, oy1, FLOOR_Z + 0.025, "Doors", mats["black_metal"])
        n = d["sliding_panels"]
        pw = (ox1 - ox0) / n
        ym = (oy0 + oy1) * 0.5
        for i in range(n):
            px0 = ox0 + i * pw
            px1 = px0 + pw
            py_c = ym + (i - 1) * 0.034
            panel_name = f"Door_Interactive_{did}_Panel{i+1}"
            p_st = 0.048
            glass = make_box(panel_name, px0 + p_st, py_c - 0.008, FLOOR_Z + 0.06, px1 - p_st, py_c + 0.008, FLOOR_Z + dh - 0.07,
                             "Doors", mats["glass_clear"])
            sL = make_box(f"{panel_name}_StileL", px0, py_c - 0.022, FLOOR_Z + 0.025, px0 + p_st, py_c + 0.022, FLOOR_Z + dh - 0.045, "Doors", mats["black_metal"])
            sR = make_box(f"{panel_name}_StileR", px1 - p_st, py_c - 0.022, FLOOR_Z + 0.025, px1, py_c + 0.022, FLOOR_Z + dh - 0.045, "Doors", mats["black_metal"])
            rB = make_box(f"{panel_name}_RailB", px0, py_c - 0.022, FLOOR_Z + 0.025, px1, py_c + 0.022, FLOOR_Z + 0.075, "Doors", mats["black_metal"])
            rT = make_box(f"{panel_name}_RailT", px0, py_c - 0.022, FLOOR_Z + dh - 0.09, px1, py_c + 0.022, FLOOR_Z + dh - 0.045, "Doors", mats["black_metal"])
            bpy.context.view_layer.update()
            for part in (sL, sR, rB, rT):
                part.parent = glass
                part.matrix_parent_inverse = glass.matrix_world.inverted()
            if i in (0, 1):
                ph = make_box(f"{panel_name}_Pull", px0 + 0.06, py_c - 0.042, FLOOR_Z + 0.95, px0 + 0.088, py_c + 0.042, FLOOR_Z + 1.25, "Doors", mats["black_metal"])
                bpy.context.view_layer.update()
                ph.parent = glass
                ph.matrix_parent_inverse = glass.matrix_world.inverted()
        cx_d = (ox0 + ox1) * 0.5
        cy_d = (oy0 + oy1) * 0.5
        door_interactive_meta.append({
            "id": did,
            "label": d["type"],
            "connects": d["connects"],
            "object_name": f"Door_Interactive_{did}_Panel1",
            "kind": "sliding_multi",
            "center_threejs": [round(cx_d, 4), round(FLOOR_Z + 1.0, 4), round(-cy_d, 4)],
            "closed_aabb_threejs": [
                round(min(ox0, ox1), 4), round(FLOOR_Z, 4), round(-max(oy0, oy1), 4),
                round(max(ox0, ox1), 4), round(FLOOR_Z + dh, 4), round(-min(oy0, oy1), 4),
            ],
            "slide_axis_threejs": [1, 0, 0],
            "max_slide_m": round(pw * 1.85, 3),
            "swing_sign": 1,
            "swing_direction": d["swing_direction"],
        })

    elif d.get("sliding_track"):
        xm = (ox0 + ox1) * 0.5
        leaf = make_box(f"Door_Interactive_{did}", xm - 0.02, oy0 + ft, FLOOR_Z + 0.008, xm + 0.02, oy1 - ft, FLOOR_Z + dh - ft,
                        "Doors", mats["white_lacquer"])
        # Flush recessed pocket door pulls on both sides
        p1 = make_box(f"DoorHandle_{did}_W", xm - 0.028, oy0 + 0.14, FLOOR_Z + 0.96, xm - 0.018, oy0 + 0.17, FLOOR_Z + 1.14, "Doors", mats["black_metal"])
        p2 = make_box(f"DoorHandle_{did}_E", xm + 0.018, oy0 + 0.14, FLOOR_Z + 0.96, xm + 0.028, oy0 + 0.17, FLOOR_Z + 1.14, "Doors", mats["black_metal"])
        bpy.context.view_layer.update()
        for p_obj in (p1, p2):
            p_obj.parent = leaf
            p_obj.matrix_parent_inverse = leaf.matrix_world.inverted()
        cx_d = (ox0 + ox1) * 0.5
        cy_d = (oy0 + oy1) * 0.5
        door_interactive_meta.append({
            "id": did,
            "label": d["type"],
            "connects": d["connects"],
            "object_name": leaf.name,
            "kind": "pocket_sliding",
            "center_threejs": [round(cx_d, 4), round(FLOOR_Z + 1.0, 4), round(-cy_d, 4)],
            "closed_aabb_threejs": [
                round(min(ox0, ox1), 4), round(FLOOR_Z, 4), round(-max(oy0, oy1), 4),
                round(max(ox0, ox1), 4), round(FLOOR_Z + dh, 4), round(-min(oy0, oy1), 4),
            ],
            "slide_axis_threejs": [0, 0, -1],
            "max_slide_m": round(dw - 0.08, 3),
            "swing_sign": 1,
            "swing_direction": "Pocket Slide North into IW-04 Wall Cavity (zero swing clearance)",
        })

# --- LEVEL 2 INTERACTIVE DOORS (D9: Tempat Jemuran <-> Sky Lounge | D10: Sky Lounge <-> Front Sky Balcony) ---
# D9: Hinged Glass-and-Walnut Architectural Door (X=4.864..4.984, Y=8.20..9.10, Z=FLOOR2_Z..+2.15)
d9_x0, d9_y0, d9_x1, d9_y1, d9_h = 4.864, 8.20, 4.984, 9.10, 2.15
ft2 = 0.045
make_box("DoorFrame_L2_D9_S", d9_x0 - 0.01, d9_y0, FLOOR2_Z, d9_x1 + 0.01, d9_y0 + ft2, FLOOR2_Z + d9_h, "Doors", mats["walnut"])
make_box("DoorFrame_L2_D9_N", d9_x0 - 0.01, d9_y1 - ft2, FLOOR2_Z, d9_x1 + 0.01, d9_y1, FLOOR2_Z + d9_h, "Doors", mats["walnut"])
make_box("DoorFrame_L2_D9_Top", d9_x0 - 0.01, d9_y0, FLOOR2_Z + d9_h - ft2, d9_x1 + 0.01, d9_y1, FLOOR2_Z + d9_h, "Doors", mats["walnut"])
d9_hx, d9_hy = d9_x1, d9_y0 + ft2
d9_leaf = make_box(
    "Door_Interactive_L2_D9",
    d9_hx - 0.024, d9_y0 + ft2, FLOOR2_Z + 0.008,
    d9_hx + 0.024, d9_y1 - ft2, FLOOR2_Z + d9_h - ft2,
    "Doors", mats["walnut"], bevel=0.004, origin_mode=(d9_hx, d9_hy, FLOOR2_Z)
)
d9_glass = make_box(
    "Door_Interactive_L2_D9_Glass",
    d9_hx - 0.028, d9_y0 + 0.14, FLOOR2_Z + 0.25,
    d9_hx + 0.028, d9_y1 - 0.14, FLOOR2_Z + d9_h - 0.16,
    "Doors", mats["glass_frosted"]
)
d9_h1 = make_box("DoorHandle_L2_D9_W", d9_hx - 0.07, d9_y1 - 0.17, FLOOR2_Z + 1.02, d9_hx - 0.02, d9_y1 - 0.06, FLOOR2_Z + 1.045, "Doors", mats["black_metal"])
d9_h2 = make_box("DoorHandle_L2_D9_E", d9_hx + 0.02, d9_y1 - 0.17, FLOOR2_Z + 1.02, d9_hx + 0.07, d9_y1 - 0.06, FLOOR2_Z + 1.045, "Doors", mats["black_metal"])
bpy.context.view_layer.update()
for child in (d9_glass, d9_h1, d9_h2):
    child.parent = d9_leaf
    child.matrix_parent_inverse = d9_leaf.matrix_world.inverted()
door_interactive_meta.append({
    "id": "D9",
    "label": "L2 Glass-Panel Drying Deck Door",
    "connects": ["RM-12", "RM-13"],
    "object_name": d9_leaf.name,
    "kind": "hinged",
    "pivot_blender": [round(d9_hx, 4), round(d9_hy, 4), round(FLOOR2_Z, 4)],
    "pivot_threejs": [round(d9_hx, 4), round(FLOOR2_Z, 4), round(-d9_hy, 4)],
    "center_threejs": [round((d9_x0 + d9_x1) * 0.5, 4), round(FLOOR2_Z + 1.0, 4), round(-(d9_y0 + d9_y1) * 0.5, 4)],
    "closed_aabb_threejs": [
        round(d9_x0, 4), round(FLOOR2_Z, 4), round(-d9_y1, 4),
        round(d9_x1, 4), round(FLOOR2_Z + d9_h, 4), round(-d9_y0, 4),
    ],
    "open_angle_deg": 90,
    "swing_sign": -1,
    "swing_direction": "Inward into L2 Sky Lounge",
})

# D10: L2 3-Panel Aluminum Sliding Glass Door (X=5.55..8.35, Y=5.00..5.20, Z=FLOOR2_Z..+2.40)
d10_x0, d10_y0, d10_x1, d10_y1, d10_h = 5.55, 5.00, 8.35, 5.20, 2.40
make_box("DoorFrame_L2_D10_L", d10_x0, d10_y0 - 0.01, FLOOR2_Z, d10_x0 + ft2, d10_y1 + 0.01, FLOOR2_Z + d10_h, "Doors", mats["black_metal"])
make_box("DoorFrame_L2_D10_R", d10_x1 - ft2, d10_y0 - 0.01, FLOOR2_Z, d10_x1, d10_y1 + 0.01, FLOOR2_Z + d10_h, "Doors", mats["black_metal"])
make_box("DoorFrame_L2_D10_Top", d10_x0, d10_y0 - 0.01, FLOOR2_Z + d10_h - ft2, d10_x1, d10_y1 + 0.01, FLOOR2_Z + d10_h, "Doors", mats["black_metal"])
make_box("DoorTrack_L2_D10_Bot", d10_x0, d10_y0, FLOOR2_Z, d10_x1, d10_y1, FLOOR2_Z + 0.025, "Doors", mats["black_metal"])
d10_pw = (d10_x1 - d10_x0) / 3.0
d10_ym = (d10_y0 + d10_y1) * 0.5
for i in range(3):
    px0 = d10_x0 + i * d10_pw
    px1 = px0 + d10_pw
    py_c = d10_ym + (i - 1) * 0.034
    pname = f"Door_Interactive_L2_D10_Panel{i+1}"
    p_st = 0.048
    g_obj = make_box(pname, px0 + p_st, py_c - 0.008, FLOOR2_Z + 0.06, px1 - p_st, py_c + 0.008, FLOOR2_Z + d10_h - 0.07, "Doors", mats["glass_clear"])
    sL = make_box(f"{pname}_StileL", px0, py_c - 0.022, FLOOR2_Z + 0.025, px0 + p_st, py_c + 0.022, FLOOR2_Z + d10_h - 0.045, "Doors", mats["black_metal"])
    sR = make_box(f"{pname}_StileR", px1 - p_st, py_c - 0.022, FLOOR2_Z + 0.025, px1, py_c + 0.022, FLOOR2_Z + d10_h - 0.045, "Doors", mats["black_metal"])
    rB = make_box(f"{pname}_RailB", px0, py_c - 0.022, FLOOR2_Z + 0.025, px1, py_c + 0.022, FLOOR2_Z + 0.075, "Doors", mats["black_metal"])
    rT = make_box(f"{pname}_RailT", px0, py_c - 0.022, FLOOR2_Z + d10_h - 0.09, px1, py_c + 0.022, FLOOR2_Z + d10_h - 0.045, "Doors", mats["black_metal"])
    bpy.context.view_layer.update()
    for part in (sL, sR, rB, rT):
        part.parent = g_obj
        part.matrix_parent_inverse = g_obj.matrix_world.inverted()
    if i in (0, 1):
        ph = make_box(f"{pname}_Pull", px0 + 0.06, py_c - 0.042, FLOOR2_Z + 0.95, px0 + 0.088, py_c + 0.042, FLOOR2_Z + 1.25, "Doors", mats["black_metal"])
        bpy.context.view_layer.update()
        ph.parent = g_obj
        ph.matrix_parent_inverse = g_obj.matrix_world.inverted()
door_interactive_meta.append({
    "id": "D10",
    "label": "L2 Balcony 3-Panel Sliding Glass Door",
    "connects": ["RM-13", "EXT-05"],
    "object_name": "Door_Interactive_L2_D10_Panel1",
    "kind": "sliding_multi",
    "center_threejs": [round((d10_x0 + d10_x1) * 0.5, 4), round(FLOOR2_Z + 1.0, 4), round(-d10_ym, 4)],
    "closed_aabb_threejs": [
        round(d10_x0, 4), round(FLOOR2_Z, 4), round(-d10_y1, 4),
        round(d10_x1, 4), round(FLOOR2_Z + d10_h, 4), round(-d10_y0, 4),
    ],
    "slide_axis_threejs": [1, 0, 0],
    "max_slide_m": round(d10_pw * 1.85, 3),
    "swing_sign": 1,
    "swing_direction": "Multi-track Slide East (to L2 Front Sky Balcony)",
})

# ---------------------------------------------------------------------------
# 8. WINDOWS (DEEP ARCHITECTURAL REVEALS, SLIM BLACK FRAMES & LOW-E GLASS)
# ---------------------------------------------------------------------------
for win in spec["windows"]:
    wid = win["id"]
    ox0, oy0, ox1, oy1 = [c * M for c in win["opening"]]
    wz0 = FLOOR_Z + win["sill_height_mm"] * M
    wz1 = wz0 + win["height_mm"] * M
    is_h = (ox1 - ox0) > (oy1 - oy0)
    ft = 0.048
    gmat = mats["glass_frosted"] if "frosted" in win["glazing"] else mats["glass_clear"]

    if is_h:
        ym = (oy0 + oy1) * 0.5
        if win["sill_height_mm"] > 0:
            make_box(f"WinSill_{wid}", ox0 - 0.015, oy0 - 0.032, wz0 - 0.028, ox1 + 0.015, oy1 + 0.02, wz0, "Windows", mats["floor_limestone"], bevel=0.003)
        make_box(f"WinFrame_{wid}_B", ox0, ym - 0.04, wz0, ox1, ym + 0.04, wz0 + ft, "Windows", mats["black_metal"])
        make_box(f"WinFrame_{wid}_T", ox0, ym - 0.04, wz1 - ft, ox1, ym + 0.04, wz1, "Windows", mats["black_metal"])
        make_box(f"WinFrame_{wid}_L", ox0, ym - 0.04, wz0, ox0 + ft, ym + 0.04, wz1, "Windows", mats["black_metal"])
        make_box(f"WinFrame_{wid}_R", ox1 - ft, ym - 0.04, wz0, ox1, ym + 0.04, wz1, "Windows", mats["black_metal"])
        if win["width_mm"] >= 1400:
            xm = (ox0 + ox1) * 0.5
            make_box(f"WinMullion_{wid}", xm - 0.02, ym - 0.035, wz0 + ft, xm + 0.02, ym + 0.035, wz1 - ft, "Windows", mats["black_metal"])
        make_box(f"WinGlass_{wid}", ox0 + ft, ym - 0.007, wz0 + ft, ox1 - ft, ym + 0.007, wz1 - ft, "Windows", gmat)
    else:
        xm = (ox0 + ox1) * 0.5
        make_box(f"WinSill_{wid}", ox0 - 0.032, oy0 - 0.015, wz0 - 0.028, ox1 + 0.02, oy1 + 0.015, wz0, "Windows", mats["floor_limestone"], bevel=0.003)
        make_box(f"WinFrame_{wid}_B", xm - 0.04, oy0, wz0, xm + 0.04, oy1, wz0 + ft, "Windows", mats["black_metal"])
        make_box(f"WinFrame_{wid}_T", xm - 0.04, oy0, wz1 - ft, xm + 0.04, oy1, wz1, "Windows", mats["black_metal"])
        make_box(f"WinFrame_{wid}_S", xm - 0.04, oy0, wz0, xm + 0.04, oy0 + ft, wz1, "Windows", mats["black_metal"])
        make_box(f"WinFrame_{wid}_N", xm - 0.04, oy1 - ft, wz0, xm + 0.04, oy1, wz1, "Windows", mats["black_metal"])
        make_box(f"WinGlass_{wid}", xm - 0.007, oy0 + ft, wz0 + ft, xm + 0.007, oy1 - ft, wz1 - ft, "Windows", gmat)

# ---------------------------------------------------------------------------
# 9. THREE INTERCHANGEABLE PHOTOREALISTIC INTERIOR STYLES
# ---------------------------------------------------------------------------
STYLE_PALETTES = {
    "Modern": {
        "col": "Furniture_Modern",
        "wood": mats["matte_charcoal"],
        "wood_accent": mats["walnut"],
        "upholstery": mats["fabric_charcoal"],
        "bed_linen": mats["linen_oatmeal"],
        "accent_pillow": mats["matte_charcoal"],
        "stone_top": mats["charcoal_quartz"],
        "cabinet": mats["matte_charcoal"],
        "metal": mats["black_metal"],
        "rug": mats["floor_modern_stone"],
        "art": mats["art_modern"],
        "curtain": mats["curtain_sheer"],
        "pot": mats["matte_charcoal"],
    },
    "Scandinavian": {
        "col": "Furniture_Scandinavian",
        "wood": mats["light_oak"],
        "wood_accent": mats["fluted_oak"],
        "upholstery": mats["linen_oatmeal"],
        "bed_linen": mats["linen_sage"],
        "accent_pillow": mats["linen_sage"],
        "stone_top": mats["floor_limestone"],
        "cabinet": mats["white_lacquer"],
        "metal": mats["black_metal"],
        "rug": mats["rug_ivory"],
        "art": mats["art_scandi"],
        "curtain": mats["curtain_sheer"],
        "pot": mats["planter_ceramic"],
    },
    "WarmLuxury": {
        "col": "Furniture_WarmLuxury",
        "wood": mats["walnut"],
        "wood_accent": mats["fluted_walnut"],
        "upholstery": mats["boucle_beige"],
        "bed_linen": mats["boucle_beige"],
        "accent_pillow": mats["fabric_terracotta"],
        "stone_top": mats["marble"],
        "cabinet": mats["walnut"],
        "metal": mats["brushed_brass"],
        "rug": mats["rug_ivory"],
        "art": mats["art_warm"],
        "curtain": mats["curtain_sheer"],
        "pot": mats["planter_terracotta"],
    },
}


def build_luxury_car(fid, x0, y0, x1, y1, z_base, col, pal):
    """
    Builds a flagship photorealistic 3D Luxury Grand Tourer (Porsche Taycan / Audi e-tron GT style)
    facing South (y0 = front bumper, y1 = rear diffuser):
      - 3D multi-station lofted lower fuselage with plan-view bumper curvature, wide-body fender flares,
        pinched door waist, power-dome hood creases, and raised wheel well cutouts
      - Separate clear-tinted curved glasshouse (windshield, side windows, panoramic roof, fastback rear glass)
        with gloss-black A/B/C pillars and anodized window trim
      - Fully modeled visible Cognac Nappa leather interior cabin (4 sport bucket seats, headrests,
        center console, dashboard, curved OLED dual cockpit display, and RHD sport steering wheel)
      - Matrix quad-LED projector headlights + full-width DRL lightbar + crimson 3D rear taillight bar
      - Carbon front splitter, slated intake grille, side skirts, multi-fin rear diffuser, dual wing mirrors,
        flush door handles, and 'B 123 AUR' luxury acrylic license plates
      - 4 open-spoke 10-blade alloy wheels with ventilated steel brake rotors and crimson Brembo calipers
    """
    cx = (x0 + x1) * 0.5
    L = y1 - y0
    yf = y0 + 0.84
    yr = y1 - 0.86
    wheel_r = 0.345
    wz = z_base + wheel_r

    # 1. 3D Multi-Station Lofted Lower Body Fuselage (scaled across full L = 4.40 m)
    # Each station: (frac_L, half_w_bot, half_w_mid, half_w_top, z_bot, z_mid, z_top, hood_center_z)
    stations = [
        (0.008, 0.64, 0.70, 0.66, 0.20, 0.44, 0.60, 0.58),  # Front nose tip
        (0.035, 0.78, 0.84, 0.80, 0.18, 0.48, 0.68, 0.66),  # Front bumper curve
        (0.090, 0.86, 0.90, 0.85, 0.19, 0.54, 0.76, 0.74),  # Front fender lead
        (0.135, 0.88, 0.92, 0.87, 0.46, 0.64, 0.81, 0.79),  # Front wheel arch front
        (0.191, 0.89, 0.93, 0.88, 0.68, 0.75, 0.85, 0.82),  # Front wheel arch apex
        (0.246, 0.88, 0.92, 0.87, 0.46, 0.66, 0.88, 0.85),  # Front wheel arch rear
        (0.286, 0.86, 0.89, 0.85, 0.18, 0.55, 0.91, 0.89),  # Base of A-pillar / cowl
        (0.400, 0.84, 0.87, 0.83, 0.18, 0.54, 0.92, 0.34),  # Front door waist (open cockpit tub inside!)
        (0.540, 0.84, 0.87, 0.83, 0.18, 0.55, 0.93, 0.34),  # B-pillar waist (open cockpit tub inside!)
        (0.675, 0.86, 0.90, 0.85, 0.18, 0.57, 0.95, 0.36),  # Rear door / haunch lead
        (0.750, 0.88, 0.92, 0.87, 0.46, 0.68, 0.97, 0.88),  # Rear wheel arch front
        (0.805, 0.90, 0.94, 0.88, 0.69, 0.78, 0.99, 0.96),  # Rear wheel arch apex (wide rear haunch!)
        (0.860, 0.88, 0.92, 0.87, 0.46, 0.68, 0.98, 0.97),  # Rear wheel arch rear
        (0.925, 0.84, 0.88, 0.82, 0.24, 0.60, 0.95, 0.94),  # Rear quarter panel
        (0.972, 0.76, 0.80, 0.74, 0.26, 0.58, 0.90, 0.89),  # Rear ducktail spoiler lip
        (0.992, 0.66, 0.70, 0.65, 0.28, 0.52, 0.78, 0.77),  # Rear tail fascia
    ]

    bm_body = bmesh.new()
    rings = []
    for t_l, hwb, hwm, hwt, zb, zm, zt, zc in stations:
        py = y0 + t_l * L
        # 8-vertex closed transverse ring at station py
        pts = [
            (cx - hwb, py, z_base + zb),
            (cx - hwm, py, z_base + zm),
            (cx - hwt, py, z_base + zt),
            (cx - hwt * 0.45, py, z_base + zc),
            (cx + hwt * 0.45, py, z_base + zc),
            (cx + hwt, py, z_base + zt),
            (cx + hwm, py, z_base + zm),
            (cx + hwb, py, z_base + zb),
        ]
        rings.append([bm_body.verts.new(p) for p in pts])

    for r_i in range(len(rings) - 1):
        r0, r1 = rings[r_i], rings[r_i + 1]
        for k in range(len(r0)):
            kn = (k + 1) % len(r0)
            bm_body.faces.new((r0[k], r0[kn], r1[kn], r1[k]))
    # Cap front nose & rear tail + Catmull-Clark Subdivision (level 2) for truly sleek automotive bodywork!
    bm_body.faces.new(rings[0][::-1])
    bm_body.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm_body, faces=bm_body.faces)
    apply_box_uv(bm_body, scale=0.6)
    m_body = bpy.data.meshes.new(f"{fid}_Body")
    bm_body.to_mesh(m_body)
    bm_body.free()
    for poly in m_body.polygons:
        poly.use_smooth = True
    m_body.materials.append(mats["car_paint"])
    o_body = link_obj(bpy.data.objects.new(f"{fid}_Body", m_body), col)
    sub_mod = o_body.modifiers.new("AutoSmoothSubsurf", "SUBSURF")
    sub_mod.levels = 2
    sub_mod.render_levels = 2

    # Dark inner wheel well housings + dark chassis undertray so no gaps appear behind wheels
    make_box(f"{fid}_Undertray", cx - 0.78, y0 + 0.25, z_base + 0.16, cx + 0.78, y1 - 0.25, z_base + 0.34, col, mats["car_carbon"])
    for wx_s, side_tag in [(-1, "L"), (1, "R")]:
        for wy_p, ax_tag in [(yf, "F"), (yr, "R")]:
            arch_x = cx + wx_s * 0.68
            arch = make_cylinder(f"{fid}_WheelWell_{ax_tag}{side_tag}", arch_x, wy_p, wz, 0.355, 0.30, col, mats["car_tire"], segs=24)
            arch.rotation_euler = (0.0, math.pi * 0.5, 0.0)
            arch.location = (arch_x - 0.15, wy_p, wz)

    # 2. Visible Cognac Nappa Leather Interior Cockpit (seen through clear-tinted glasshouse!)
    # Dark charcoal cabin tub floor & inner door sills
    make_box(f"{fid}_CabinFloor", cx - 0.74, y0 + 1.25, z_base + 0.28, cx + 0.74, y1 - 0.92, z_base + 0.35, col, mats["matte_charcoal"])
    # Center transmission console & Cognac leather armrest
    make_box(f"{fid}_CenterConsole", cx - 0.13, y0 + 1.30, z_base + 0.35, cx + 0.13, y0 + 2.95, z_base + 0.64, col, mats["matte_charcoal"], bevel=0.015)
    make_plush_cushion(f"{fid}_ConsoleArmrest", cx - 0.11, y0 + 1.88, z_base + 0.63, cx + 0.11, y0 + 2.38, z_base + 0.70, col, mats["leather_cognac"], puff=0.14)
    # Sculpted Dashboard & Curved Dual-OLED Cockpit Display
    make_box(f"{fid}_Dashboard", cx - 0.74, y0 + 1.24, z_base + 0.62, cx + 0.74, y0 + 1.62, z_base + 0.90, col, mats["matte_charcoal"], bevel=0.025, smooth=True)
    make_box(f"{fid}_DashTrim", cx - 0.72, y0 + 1.61, z_base + 0.77, cx + 0.72, y0 + 1.635, z_base + 0.80, col, mats["brushed_steel"])
    make_box(f"{fid}_CockpitOLED", cx - 0.48, y0 + 1.59, z_base + 0.79, cx + 0.56, y0 + 1.63, z_base + 0.93, col, mats["tv_screen"], bevel=0.006)
    # Sport Steering Wheel (Right-Hand Drive — cx + 0.34)
    sw_col = make_cylinder(f"{fid}_SteeringCol", cx + 0.34, y0 + 1.62, z_base + 0.78, 0.032, 0.16, col, mats["black_metal"], segs=12)
    sw_col.rotation_euler = (math.radians(-68), 0, 0)
    sw_rim = make_cylinder(f"{fid}_SteeringWheel", cx + 0.34, y0 + 1.75, z_base + 0.83, 0.165, 0.028, col, mats["leather_cognac"], segs=22)
    sw_rim.rotation_euler = (math.radians(-68), 0, 0)
    sw_hub = make_cylinder(f"{fid}_SteeringHub", cx + 0.34, y0 + 1.74, z_base + 0.83, 0.065, 0.034, col, mats["black_metal"], segs=16)
    sw_hub.rotation_euler = (math.radians(-68), 0, 0)

    # 4 Sculpted Cognac Leather Sport Bucket Seats (Front Left, Front Right, Rear Left, Rear Right)
    for sx_c, s_side in [(cx - 0.38, "L"), (cx + 0.38, "R")]:
        for sy_c, s_row in [(y0 + 2.02, "F"), (y0 + 2.86, "R")]:
            sid = f"{fid}_Seat_{s_row}{s_side}"
            make_plush_cushion(f"{sid}_Cush", sx_c - 0.22, sy_c - 0.24, z_base + 0.38, sx_c + 0.22, sy_c + 0.22, z_base + 0.52, col, mats["leather_cognac"], puff=0.16)
            make_plush_cushion(f"{sid}_Back", sx_c - 0.21, sy_c + 0.12, z_base + 0.50, sx_c + 0.21, sy_c + 0.28, z_base + 0.98, col, mats["leather_cognac"], puff=0.18)
            make_plush_cushion(f"{sid}_Headrest", sx_c - 0.12, sy_c + 0.15, z_base + 0.96, sx_c + 0.12, sy_c + 0.27, z_base + 1.15, col, mats["leather_cognac"], puff=0.22)

    # 3. 3D Sculpted Curved Tinted Glasshouse + Fastback Panoramic Roof & Gloss-Black Pillars
    glass_stations = [
        (1.24, 0.74, 0.90, 0.90),  # Windshield bottom cowl
        (1.56, 0.68, 1.12, 1.14),  # Windshield mid
        (1.86, 0.62, 1.32, 1.35),  # Windshield top header
        (2.42, 0.61, 1.35, 1.38),  # Cabin roof apex
        (3.02, 0.60, 1.27, 1.30),  # Fastback C-pillar top
        (3.68, 0.56, 1.00, 1.01),  # Rear glass base
    ]
    bm_glass = bmesh.new()
    g_rings = []
    for dy, g_hw, gz_side, gz_top in glass_stations:
        py = y0 + dy
        b_hw = g_hw + 0.14
        pts = [
            (cx - b_hw, py, z_base + 0.90),
            (cx - g_hw, py, z_base + gz_side),
            (cx - g_hw * 0.42, py, z_base + gz_top),
            (cx + g_hw * 0.42, py, z_base + gz_top),
            (cx + g_hw, py, z_base + gz_side),
            (cx + b_hw, py, z_base + 0.90),
        ]
        g_rings.append([bm_glass.verts.new(p) for p in pts])
    for r_i in range(len(g_rings) - 1):
        r0, r1 = g_rings[r_i], g_rings[r_i + 1]
        for k in range(len(r0) - 1):
            bm_glass.faces.new((r0[k], r0[k + 1], r1[k + 1], r1[k]))
    bmesh.ops.recalc_face_normals(bm_glass, faces=bm_glass.faces)
    apply_box_uv(bm_glass, scale=0.8)
    m_glass = bpy.data.meshes.new(f"{fid}_Glasshouse")
    bm_glass.to_mesh(m_glass)
    bm_glass.free()
    for poly in m_glass.polygons:
        poly.use_smooth = True
    m_glass.materials.append(mats["car_glass"])
    link_obj(bpy.data.objects.new(f"{fid}_Glasshouse", m_glass), col)

    # Body-colored Smooth Continuous Lofted A-Pillar -> Roof Arch -> Fastback C-Pillar + Panoramic Carbon Roof
    make_box(f"{fid}_WindshieldHeader", cx - 0.62, y0 + 1.80, z_base + 1.31, cx + 0.62, y0 + 1.94, z_base + 1.355, col, mats["car_paint"], bevel=0.012, smooth=True)
    make_box(f"{fid}_PanoramicCarbonRoof", cx - 0.58, y0 + 1.92, z_base + 1.33, cx + 0.58, y0 + 3.04, z_base + 1.372, col, mats["car_carbon"], bevel=0.015, smooth=True)
    make_box(f"{fid}_RearRoofCrossbar", cx - 0.58, y0 + 3.00, z_base + 1.26, cx + 0.58, y0 + 3.14, z_base + 1.315, col, mats["car_paint"], bevel=0.012, smooth=True)
    arch_profile_pts = [
        (1.24, 0.75, 0.90, 0.026, 0.024),
        (1.54, 0.68, 1.12, 0.025, 0.024),
        (1.84, 0.62, 1.32, 0.028, 0.026),
        (2.42, 0.61, 1.35, 0.030, 0.026),
        (3.02, 0.60, 1.28, 0.032, 0.026),
        (3.38, 0.66, 1.14, 0.038, 0.028),
        (3.72, 0.72, 0.98, 0.042, 0.028),
    ]
    for sx_s, s_tag in [(-1, "L"), (1, "R")]:
        bm_ar = bmesh.new()
        ar_rings = []
        for dy_a, x_off_a, z_off_a, hw_a, hz_a in arch_profile_pts:
            px_a = cx + sx_s * x_off_a
            py_a = y0 + dy_a
            pz_a = z_base + z_off_a
            r_pts = [
                (px_a - hw_a, py_a, pz_a - hz_a),
                (px_a + hw_a, py_a, pz_a - hz_a),
                (px_a + hw_a, py_a, pz_a + hz_a),
                (px_a - hw_a, py_a, pz_a + hz_a),
            ]
            ar_rings.append([bm_ar.verts.new(p) for p in r_pts])
        for ri in range(len(ar_rings) - 1):
            r0, r1 = ar_rings[ri], ar_rings[ri + 1]
            for k in range(4):
                kn = (k + 1) % 4
                bm_ar.faces.new((r0[k], r0[kn], r1[kn], r1[k]))
        bm_ar.faces.new(ar_rings[0][::-1])
        bm_ar.faces.new(ar_rings[-1])
        bmesh.ops.recalc_face_normals(bm_ar, faces=bm_ar.faces)
        apply_box_uv(bm_ar, scale=1.0)
        m_ar = bpy.data.meshes.new(f"{fid}_RoofArch_{s_tag}")
        bm_ar.to_mesh(m_ar)
        bm_ar.free()
        for poly in m_ar.polygons:
            poly.use_smooth = True
        m_ar.materials.append(mats["car_paint"])
        link_obj(bpy.data.objects.new(f"{fid}_RoofArch_{s_tag}", m_ar), col)
        make_box(f"{fid}_BPillar_{s_tag}", cx + sx_s * 0.69 - 0.016, y0 + 2.34, z_base + 0.91, cx + sx_s * 0.69 + 0.016, y0 + 2.46, z_base + 1.33, col, mats["black_metal"])
        # Aerodynamic sculpted wing mirrors on dual-stalk mounts + mirror glass + LED repeater
        mx0 = cx + sx_s * 0.85
        mx1 = cx + sx_s * 1.01
        m_min, m_max = min(mx0, mx1), max(mx0, mx1)
        make_box(f"{fid}_MirrorStalk_{s_tag}", min(cx + sx_s * 0.80, m_min + 0.05), y0 + 1.64, z_base + 0.91, max(cx + sx_s * 0.80, m_min + 0.05), y0 + 1.72, z_base + 0.96, col, mats["black_metal"], bevel=0.006)
        make_box(f"{fid}_MirrorCap_{s_tag}", m_min, y0 + 1.60, z_base + 0.94, m_max, y0 + 1.75, z_base + 1.03, col, mats["car_paint"], bevel=0.018, smooth=True)
        make_box(f"{fid}_MirrorGlass_{s_tag}", m_min + 0.01, y0 + 1.745, z_base + 0.95, m_max - 0.01, y0 + 1.755, z_base + 1.02, col, mats["mirror"])
        make_box(f"{fid}_MirrorLED_{s_tag}", m_min + 0.01, y0 + 1.596, z_base + 0.98, m_max - 0.01, y0 + 1.604, z_base + 0.992, col, mats["emit_warm"])
        # 2 Flush Brushed-Metal Door Handles + Carbon Side Skirt per side
        for hy_off, h_tag in [(2.12, "F"), (2.78, "R")]:
            hx_p = cx + sx_s * 0.855
            make_box(f"{fid}_DoorHandle_{h_tag}{s_tag}", hx_p - 0.012, y0 + hy_off, z_base + 0.81, hx_p + 0.012, y0 + hy_off + 0.16, z_base + 0.835, col, mats["brushed_steel"], bevel=0.004)
        sk_x = cx + sx_s * 0.845
        make_box(f"{fid}_SideSkirt_{s_tag}", sk_x - 0.03, y0 + 1.16, z_base + 0.17, sk_x + 0.03, y1 - 1.16, z_base + 0.23, col, mats["car_carbon"], bevel=0.006)

    # 4. Millimeter-Flush Sculpted Front Aero Splitter, Grille, Angled Matrix LED Headlights & Plate
    make_box(f"{fid}_FrontSplitter", cx - 0.68, y0 + 0.036, z_base + 0.16, cx + 0.68, y0 + 0.22, z_base + 0.205, col, mats["car_carbon"], bevel=0.008)
    make_box(f"{fid}_FrontGrille", cx - 0.46, y0 + 0.042, z_base + 0.22, cx + 0.46, y0 + 0.18, z_base + 0.40, col, mats["black_metal"], bevel=0.008)
    for g_z in (0.26, 0.31, 0.36):
        make_box(f"{fid}_GrilleSlat_{g_z:.2f}", cx - 0.44, y0 + 0.037, z_base + g_z, cx + 0.44, y0 + 0.08, z_base + g_z + 0.012, col, mats["car_carbon"])
    # Flush Curved-Contour Slim Matrix LED Headlights (angled ±11° to follow the sculpted Subsurf fender corners!)
    for sx_s, s_tag in [(-1, "L"), (1, "R")]:
        hl_cx = cx + sx_s * 0.49
        ang_z = sx_s * math.radians(11.0)
        hl_h = make_rounded_slab(f"{fid}_HeadlightHousing_{s_tag}", hl_cx - 0.145, y0 + 0.068, z_base + 0.525, hl_cx + 0.145, y0 + 0.21, z_base + 0.595, 0.020, col, mats["black_metal"], segs=4)
        hl_h.rotation_euler = (0.0, 0.0, ang_z)
        for p_off, p_tag in [(-0.052, "In"), (0.052, "Out")]:
            prj = make_cylinder(f"{fid}_HeadlightProj_{s_tag}{p_tag}", hl_cx + p_off, y0 + 0.072, z_base + 0.556, 0.016, 0.028, col, mats["brushed_steel"], segs=12)
            prj.rotation_euler = (math.pi * 0.5, 0.0, ang_z)
        hl_drl = make_box(f"{fid}_HeadlightDRL1_{s_tag}", hl_cx - 0.125, y0 + 0.058, z_base + 0.568, hl_cx + 0.125, y0 + 0.11, z_base + 0.580, col, mats["emit_headlight"])
        hl_drl.rotation_euler = (0.0, 0.0, ang_z)
        hl_lens = make_rounded_slab(f"{fid}_HeadlightLens_{s_tag}", hl_cx - 0.148, y0 + 0.054, z_base + 0.522, hl_cx + 0.148, y0 + 0.13, z_base + 0.598, 0.020, col, mats["glass_clear"], segs=4)
        hl_lens.rotation_euler = (0.0, 0.0, ang_z)
    make_box(f"{fid}_FrontHorizonLightbar", cx - 0.36, y0 + 0.048, z_base + 0.564, cx + 0.36, y0 + 0.10, z_base + 0.576, col, mats["emit_headlight"])
    # Front License Plate ('B 123 AUR')
    make_box(f"{fid}_PlateFront_Holder", cx - 0.21, y0 + 0.032, z_base + 0.27, cx + 0.21, y0 + 0.055, z_base + 0.37, col, mats["black_metal"], bevel=0.003)
    make_box(f"{fid}_PlateFront_Face", cx - 0.19, y0 + 0.028, z_base + 0.285, cx + 0.19, y0 + 0.040, z_base + 0.355, col, mats["white_lacquer"])

    # 5. Rear 3D Crimson LED Taillight Blade, Multi-Fin Diffuser, Exhausts & Rear Plate
    make_box(f"{fid}_RearTaillightHousing", cx - 0.74, y1 - 0.11, z_base + 0.74, cx + 0.74, y1 - 0.02, z_base + 0.84, col, mats["black_metal"], bevel=0.01)
    make_box(f"{fid}_RearTaillightLED", cx - 0.72, y1 - 0.03, z_base + 0.775, cx + 0.72, y1 - 0.008, z_base + 0.815, col, mats["emit_taillight"])
    for sx_s, s_tag in [(-1, "L"), (1, "R")]:
        make_box(f"{fid}_RearTailWing_{s_tag}", cx + sx_s * 0.58 - 0.14, y1 - 0.035, z_base + 0.745, cx + sx_s * 0.58 + 0.14, y1 - 0.006, z_base + 0.77, col, mats["emit_taillight"])
    make_box(f"{fid}_RearDiffuser", cx - 0.72, y1 - 0.16, z_base + 0.20, cx + 0.72, y1 - 0.02, z_base + 0.38, col, mats["car_carbon"], bevel=0.01)
    for df_x in (-0.42, -0.14, 0.14, 0.42):
        make_box(f"{fid}_DiffuserFin_{df_x:.2f}", cx + df_x - 0.012, y1 - 0.14, z_base + 0.18, cx + df_x + 0.012, y1 - 0.005, z_base + 0.36, col, mats["black_metal"])
    for ex_x in (-0.56, 0.56):
        ex = make_cylinder(f"{fid}_Exhaust_{ex_x:.2f}", cx + ex_x, y1 - 0.08, z_base + 0.27, 0.048, 0.10, col, mats["brushed_steel"], segs=16)
        ex.rotation_euler = (math.pi * 0.5, 0, 0)
    make_box(f"{fid}_PlateRear_Holder", cx - 0.22, y1 - 0.03, z_base + 0.50, cx + 0.22, y1 - 0.005, z_base + 0.61, col, mats["black_metal"], bevel=0.003)
    make_box(f"{fid}_PlateRear_Face", cx - 0.20, y1 - 0.012, z_base + 0.515, cx + 0.20, y1 - 0.001, z_base + 0.595, col, mats["white_lacquer"])

    # 6. Four 10-Spoke Twin-V Diamond-Cut Alloy Wheels (Hollow Annular Tire + Exposed Spokes, Rotors & Brembo Calipers!)
    for wx_s, s_tag in [(-1, "L"), (1, "R")]:
        wx_outer = cx + wx_s * 0.91
        for wy_p, ax_tag in [(yf, "F"), (yr, "R")]:
            wid = f"{fid}_Wheel_{ax_tag}{s_tag}"
            tire_w = 0.24
            # True hollow annular tire (tread + outer sidewall + inner rim bead) so spokes & brake discs are NEVER occluded!
            bm_tr = bmesh.new()
            t_segs = 32
            r_t_out, r_t_in = wheel_r, 0.242
            x_out_face = 0.0
            x_in_face = -wx_s * tire_w
            ring_out_o, ring_in_o, ring_out_i, ring_in_i = [], [], [], []
            for k in range(t_segs):
                a = 2.0 * math.pi * k / t_segs
                ca, sa = math.cos(a), math.sin(a)
                ring_out_o.append(bm_tr.verts.new((x_out_face, r_t_out * ca, r_t_out * sa)))
                ring_in_o.append(bm_tr.verts.new((x_out_face, r_t_in * ca, r_t_in * sa)))
                ring_out_i.append(bm_tr.verts.new((x_in_face, r_t_out * ca, r_t_out * sa)))
                ring_in_i.append(bm_tr.verts.new((x_in_face, r_t_in * ca, r_t_in * sa)))
            for k in range(t_segs):
                kn = (k + 1) % t_segs
                bm_tr.faces.new((ring_out_o[k], ring_out_o[kn], ring_out_i[kn], ring_out_i[k]))
                bm_tr.faces.new((ring_in_o[k], ring_in_o[kn], ring_out_o[kn], ring_out_o[k]))
                bm_tr.faces.new((ring_out_i[k], ring_out_i[kn], ring_in_i[kn], ring_in_i[k]))
                bm_tr.faces.new((ring_in_i[k], ring_in_i[kn], ring_in_o[kn], ring_in_o[k]))
            bmesh.ops.recalc_face_normals(bm_tr, faces=bm_tr.faces)
            apply_box_uv(bm_tr, scale=1.5)
            m_tr = bpy.data.meshes.new(f"{wid}_Tire")
            bm_tr.to_mesh(m_tr)
            bm_tr.free()
            for poly in m_tr.polygons:
                poly.use_smooth = True
            m_tr.materials.append(mats["car_tire"])
            o_tr = bpy.data.objects.new(f"{wid}_Tire", m_tr)
            o_tr.location = (wx_outer, wy_p, wz)
            link_obj(o_tr, col)

            # Dark inner wheel well backdrop disc recessed 90 mm behind the spokes
            back_x = wx_outer - wx_s * 0.095
            barrel = make_cylinder(f"{wid}_InnerBack", back_x, wy_p, wz, 0.242, 0.02, col, mats["black_metal"], segs=24)
            barrel.rotation_euler = (0.0, math.pi * 0.5, 0.0)
            barrel.location = (back_x - 0.01, wy_p, wz)

            # Ventilated steel brake disc rotor & Crimson 6-piston Brembo caliper visible right behind spokes!
            disc_x = wx_outer - wx_s * 0.046
            disc = make_cylinder(f"{wid}_BrakeDisc", disc_x, wy_p, wz, 0.198, 0.020, col, mats["brushed_steel"], segs=24)
            disc.rotation_euler = (0.0, math.pi * 0.5, 0.0)
            disc.location = (disc_x - 0.010, wy_p, wz)

            cal_y = wy_p - 0.12 if ax_tag == "F" else wy_p + 0.12
            cal_x = wx_outer - wx_s * 0.032
            make_box(
                f"{wid}_BremboCaliper",
                cal_x - 0.022, cal_y - 0.055, wz - 0.02,
                cal_x + 0.022, cal_y + 0.055, wz + 0.135,
                col, mats["car_caliper"], bevel=0.010, smooth=True
            )

            # Sculpted outer alloy rim lip, center hub cap & 10 radial twin-V diamond-cut spokes at outer face!
            face_x = wx_outer - wx_s * 0.006
            hub = make_cylinder(f"{wid}_Hub", face_x, wy_p, wz, 0.056, 0.024, col, mats["brushed_steel"], segs=18)
            hub.rotation_euler = (0.0, math.pi * 0.5, 0.0)
            hub.location = (face_x - 0.012, wy_p, wz)

            bm_sp = bmesh.new()
            ring_segs = 28
            r_out, r_in = 0.248, 0.222
            for k in range(ring_segs):
                a0 = 2.0 * math.pi * k / ring_segs
                a1 = 2.0 * math.pi * (k + 1) / ring_segs
                for x_off_b in (-0.010, 0.010):
                    v0 = bm_sp.verts.new((x_off_b, r_in * math.cos(a0), r_in * math.sin(a0)))
                    v1 = bm_sp.verts.new((x_off_b, r_out * math.cos(a0), r_out * math.sin(a0)))
                    v2 = bm_sp.verts.new((x_off_b, r_out * math.cos(a1), r_out * math.sin(a1)))
                    v3 = bm_sp.verts.new((x_off_b, r_in * math.cos(a1), r_in * math.sin(a1)))
                    bm_sp.faces.new((v0, v1, v2, v3))
            # 10 Twin-V spokes
            for sp_i in range(5):
                base_a = sp_i * (2.0 * math.pi / 5.0)
                for v_sign in (-1, 1):
                    a_inner = base_a + v_sign * 0.09
                    a_outer = base_a + v_sign * 0.26
                    w_sp = 0.015
                    p_in = Vector((0.0, 0.050 * math.cos(a_inner), 0.050 * math.sin(a_inner)))
                    p_out = Vector((0.0, 0.228 * math.cos(a_outer), 0.228 * math.sin(a_outer)))
                    perp = Vector((0.0, -(p_out.z - p_in.z), p_out.y - p_in.y)).normalized() * w_sp
                    v_f0 = bm_sp.verts.new(p_in - perp + Vector((0.012, 0, 0)))
                    v_f1 = bm_sp.verts.new(p_in + perp + Vector((0.012, 0, 0)))
                    v_f2 = bm_sp.verts.new(p_out + perp * 0.75 + Vector((0.012, 0, 0)))
                    v_f3 = bm_sp.verts.new(p_out - perp * 0.75 + Vector((0.012, 0, 0)))
                    v_b0 = bm_sp.verts.new(p_in - perp + Vector((-0.012, 0, 0)))
                    v_b1 = bm_sp.verts.new(p_in + perp + Vector((-0.012, 0, 0)))
                    v_b2 = bm_sp.verts.new(p_out + perp * 0.75 + Vector((-0.012, 0, 0)))
                    v_b3 = bm_sp.verts.new(p_out - perp * 0.75 + Vector((-0.012, 0, 0)))
                    bm_sp.faces.new((v_f0, v_f1, v_f2, v_f3))
                    bm_sp.faces.new((v_b3, v_b2, v_b1, v_b0))
                    bm_sp.faces.new((v_f0, v_f3, v_b3, v_b0))
                    bm_sp.faces.new((v_f1, v_b1, v_b2, v_f2))
            bmesh.ops.recalc_face_normals(bm_sp, faces=bm_sp.faces)
            apply_box_uv(bm_sp, scale=2.0)
            m_sp = bpy.data.meshes.new(f"{wid}_AlloySpokes")
            bm_sp.to_mesh(m_sp)
            bm_sp.free()
            for poly in m_sp.polygons:
                poly.use_smooth = True
            m_sp.materials.append(mats["brushed_steel"])
            o_sp = bpy.data.objects.new(f"{wid}_AlloySpokes", m_sp)
            o_sp.location = (face_x, wy_p, wz)
            link_obj(o_sp, col)


def build_detailed_decorations(tag, col, pal):
    """Populates every room and outdoor zone with bespoke, high-craft interior & exterior accessories."""
    z = FLOOR_Z

    # --- 1. LIVING ROOM (RM-09): True Parabolic Arched Floor Lamp, Side Drink Table, Lathed Vessels & Shelf ---
    # True 18-segment smoothly curved parabolic brass floor reading lamp arching over the sofa corner!
    make_cylinder(f"{tag}_Decor_Living_LampBase", 5.68, 8.46, z, 0.16, 0.24, col, pal["stone_top"], segs=24)
    arch_pts = []
    for k in range(17):
        t = k / 16.0
        # Rising smoothly vertically then gracefully curving over toward (6.08, 8.46, z + 1.94)
        ax = 5.68 + 0.42 * (t ** 2.15)
        az = z + 0.23 + 1.92 * math.sin(t * math.pi * 0.56)
        arch_pts.append((ax, 8.46, az))
    make_swept_tube(f"{tag}_Decor_Living_LampStem", arch_pts, 0.011, col, pal["metal"], segs=12)
    # Tapered sculptural linen drum shade suspended from the curved arc tip
    tip_x, tip_y, tip_z = arch_pts[-1]
    make_cylinder(f"{tag}_Decor_Living_LampCord", tip_x, tip_y, tip_z - 0.14, 0.005, 0.14, col, pal["metal"], segs=8)
    make_lathed_mesh(
        f"{tag}_Decor_Living_LampShade", tip_x, tip_y, tip_z - 0.34,
        [(0.175, 0.0), (0.162, 0.08), (0.142, 0.17), (0.125, 0.22), (0.118, 0.22), (0.136, 0.17), (0.168, 0.0)],
        col, mats["emit_lamp"], segs=24
    )

    # Round marble & metal side table beside sofa South-East chaise end (x=6.28, y=8.46) with lathed crystal carafe
    make_cylinder(f"{tag}_Decor_Living_SideTblBase", 6.28, 8.46, z, 0.16, 0.03, col, pal["metal"], segs=22)
    make_cylinder(f"{tag}_Decor_Living_SideTblStem", 6.28, 8.46, z + 0.03, 0.020, 0.46, col, pal["metal"], segs=14)
    make_cylinder(f"{tag}_Decor_Living_SideTblTop", 6.28, 8.46, z + 0.49, 0.23, 0.028, col, pal["stone_top"], segs=28)
    make_lathed_mesh(
        f"{tag}_Decor_Living_Carafe", 6.25, 8.44, z + 0.518,
        [(0.038, 0.0), (0.048, 0.045), (0.042, 0.095), (0.022, 0.145), (0.027, 0.175)],
        col, mats["glass_clear"], segs=18
    )
    make_cylinder(f"{tag}_Decor_Living_Glass", 6.35, 8.50, z + 0.518, 0.028, 0.082, col, mats["glass_clear"], segs=16)

    # Woven floor pouf cushion near terrace view
    make_plush_cushion(f"{tag}_Decor_Living_FloorPouf", 5.82, 10.68, z, 6.34, 11.20, z + 0.34, col, pal["accent_pillow"], puff=0.25)

    # Floating display shelf on East media wall with sculpted lathed ceramic amphoras & books
    make_box(f"{tag}_Decor_Living_Shelf", 8.68, 8.38, z + 1.38, 8.92, 9.08, z + 1.42, col, pal["wood"], bevel=0.005)
    make_lathed_mesh(
        f"{tag}_Decor_Living_ShelfPot1", 8.79, 8.54, z + 1.42,
        [(0.038, 0.0), (0.058, 0.05), (0.052, 0.11), (0.028, 0.15), (0.034, 0.175)],
        col, mats["planter_terracotta"], segs=18
    )
    make_lathed_mesh(
        f"{tag}_Decor_Living_ShelfPot2", 8.80, 8.74, z + 1.42,
        [(0.048, 0.0), (0.070, 0.045), (0.062, 0.095), (0.045, 0.115)],
        col, mats["planter_ceramic"], segs=18
    )
    make_box(f"{tag}_Decor_Living_ShelfBooks", 8.72, 8.86, z + 1.42, 8.88, 9.03, z + 1.56, col, mats["linen_oatmeal"], bevel=0.004)

    # --- 2. DINING AREA (RM-10): 6-Place Tableware Setting with True Lathed Tulip Wine Glasses, Bowls & Candlesticks ---
    dt_z = z + 0.755
    for i in range(3):
        yc = 6.20 + i * 0.60
        for s_idx, px_c in enumerate((5.90, 6.40)):
            pid = f"{tag}_Decor_Dining_Set_{i}_{s_idx}"
            make_rounded_slab(f"{pid}_Mat", px_c - 0.14, yc - 0.18, dt_z, px_c + 0.14, yc + 0.18, dt_z + 0.004, 0.028, col, mats["linen_oatmeal"], segs=5)
            make_lathed_mesh(
                f"{pid}_Plate", px_c, yc, dt_z + 0.004,
                [(0.088, 0.0), (0.122, 0.011), (0.116, 0.013), (0.082, 0.005)],
                col, mats["ceramic_white"], segs=22
            )
            make_lathed_mesh(
                f"{pid}_Bowl", px_c, yc, dt_z + 0.010,
                [(0.052, 0.0), (0.078, 0.016), (0.086, 0.032), (0.080, 0.032), (0.050, 0.006)],
                col, pal["pot"], segs=20
            )
            # True curved lathed tulip crystal wine glass!
            gx = px_c + (0.10 if s_idx == 0 else -0.10)
            gy = yc + 0.13
            make_lathed_mesh(
                f"{pid}_WineGlass", gx, gy, dt_z + 0.004,
                [(0.032, 0.0), (0.030, 0.004), (0.005, 0.012), (0.004, 0.090), (0.018, 0.102), (0.038, 0.128), (0.035, 0.165), (0.028, 0.186)],
                col, mats["glass_clear"], segs=18
            )
    # Tapered dinner candlesticks flanking centerpiece bowl (cx=6.15, cy=6.80)
    for cy_off, c_idx in [(-0.34, 1), (0.34, 2)]:
        make_lathed_mesh(
            f"{tag}_Decor_Dining_Holder{c_idx}", 6.15, 6.80 + cy_off, dt_z,
            [(0.042, 0.0), (0.038, 0.012), (0.014, 0.065), (0.012, 0.105), (0.020, 0.120)],
            col, pal["metal"], segs=16
        )
        make_cylinder(f"{tag}_Decor_Dining_Taper{c_idx}", 6.15, 6.80 + cy_off, dt_z + 0.12, 0.011, 0.16, col, mats["ceramic_white"], segs=12, radius_top=0.008)
        make_cylinder(f"{tag}_Decor_Dining_Flame{c_idx}", 6.15, 6.80 + cy_off, dt_z + 0.28, 0.007, 0.022, col, mats["emit_warm"], segs=10, radius_top=0.001)
    make_box(f"{tag}_Decor_Dining_PicLight", 4.864, 5.48, z + 2.26, 4.98, 5.89, z + 2.285, col, pal["metal"], bevel=0.004)
    make_box(f"{tag}_Decor_Dining_PicGlow", 4.91, 5.50, z + 2.252, 4.97, 5.87, z + 2.26, col, mats["emit_warm"])

    # --- 3. MODERN KITCHEN (RM-11): Recessed Glass Built-in Oven w/ Rack & Knobs, Range Hood, Sculpted Cookware ---
    kt_z = z + 0.90
    make_box(f"{tag}_Decor_Kitchen_OvenFrame", 8.316, 6.26, z + 0.18, 8.332, 6.88, z + 0.78, col, mats["black_metal"], bevel=0.004)
    make_box(f"{tag}_Decor_Kitchen_OvenPanel", 8.312, 6.27, z + 0.68, 8.320, 6.87, z + 0.77, col, mats["brushed_steel"], bevel=0.002)
    # 3 metallic rotary control knobs + digital clock readout on stainless control strip
    for k_y in (6.36, 6.44, 6.76):
        kn = make_cylinder(f"{tag}_Decor_Kitchen_OvenKnob_{k_y:.2f}", 8.312, k_y, z + 0.725, 0.015, 0.020, col, mats["black_metal"], segs=12)
        kn.rotation_euler = (0, -math.pi * 0.5, 0)
    make_box(f"{tag}_Decor_Kitchen_OvenClock", 8.310, 6.52, z + 0.71, 8.314, 6.64, z + 0.74, col, mats["tv_screen"])
    # Recessed dark baking cavity behind reflective clear oven door glass + internal chrome rack!
    make_box(f"{tag}_Decor_Kitchen_OvenCavity", 8.320, 6.32, z + 0.24, 8.345, 6.82, z + 0.65, col, mats["matte_charcoal"])
    for rack_z in (z + 0.36, z + 0.50):
        make_box(f"{tag}_Decor_Kitchen_OvenRack_{rack_z:.2f}", 8.318, 6.34, rack_z, 8.335, 6.80, rack_z + 0.006, col, mats["brushed_steel"])
    make_box(f"{tag}_Decor_Kitchen_OvenGlass", 8.310, 6.31, z + 0.23, 8.317, 6.83, z + 0.66, col, mats["car_glass"])
    ov_h = make_cylinder(f"{tag}_Decor_Kitchen_OvenHandle", 8.285, 6.34, z + 0.64, 0.010, 0.46, col, mats["brushed_steel"], segs=12)
    ov_h.rotation_euler = (-math.pi * 0.5, 0, 0)
    make_box(f"{tag}_Decor_Kitchen_Hood", 8.56, 6.22, z + 1.50, 8.92, 6.92, z + 1.54, col, mats["brushed_steel"], bevel=0.004)
    make_box(f"{tag}_Decor_Kitchen_HoodLight", 8.58, 6.28, z + 1.494, 8.64, 6.86, z + 1.501, col, mats["emit_warm"])
    # Brushed-steel stockpot with domed lid, curved arch handle & curved side loop handles!
    make_cylinder(f"{tag}_Decor_Kitchen_Pot", 8.58, 6.42, kt_z + 0.015, 0.102, 0.125, col, mats["brushed_steel"], segs=24)
    make_lathed_mesh(
        f"{tag}_Decor_Kitchen_PotLid", 8.58, 6.42, kt_z + 0.140,
        [(0.105, 0.0), (0.095, 0.012), (0.055, 0.022), (0.005, 0.026)],
        col, mats["brushed_steel"], segs=22
    )
    make_swept_tube(
        f"{tag}_Decor_Kitchen_PotLidArc",
        [(8.58, 6.39, kt_z + 0.160), (8.58, 6.40, kt_z + 0.184), (8.58, 6.44, kt_z + 0.184), (8.58, 6.45, kt_z + 0.160)],
        0.006, col, mats["black_metal"], segs=10
    )
    for hy_s in (-1, 1):
        make_swept_tube(
            f"{tag}_Decor_Kitchen_PotLoop_{hy_s}",
            [(8.58, 6.42 + hy_s * 0.100, kt_z + 0.095), (8.58, 6.42 + hy_s * 0.132, kt_z + 0.105), (8.58, 6.42 + hy_s * 0.132, kt_z + 0.122), (8.58, 6.42 + hy_s * 0.100, kt_z + 0.124)],
            0.005, col, mats["brushed_steel"], segs=8
        )
    make_cylinder(f"{tag}_Decor_Kitchen_Pan", 8.58, 6.73, kt_z + 0.015, 0.108, 0.042, col, mats["brushed_brass"], segs=24)
    make_cylinder(f"{tag}_Decor_Kitchen_PanInner", 8.58, 6.73, kt_z + 0.050, 0.100, 0.008, col, mats["matte_charcoal"], segs=22)
    make_swept_tube(
        f"{tag}_Decor_Kitchen_PanHandle",
        [(8.475, 6.73, kt_z + 0.040), (8.41, 6.73, kt_z + 0.050), (8.33, 6.73, kt_z + 0.068)],
        0.009, col, mats["black_metal"], segs=10
    )
    # Rounded end-grain walnut cutting board, knife block & lathed organic ceramic fruit bowl
    make_rounded_slab(f"{tag}_Decor_Kitchen_Board", 7.00, 5.34, kt_z, 7.26, 5.64, kt_z + 0.024, 0.025, col, mats["walnut"], segs=6)
    make_box(f"{tag}_Decor_Kitchen_KnifeBlock", 8.68, 7.12, kt_z, 8.83, 7.28, kt_z + 0.21, col, pal["wood"], bevel=0.006)
    make_lathed_mesh(
        f"{tag}_Decor_Kitchen_FruitBowl", 8.60, 5.54, kt_z,
        [(0.085, 0.0), (0.125, 0.020), (0.152, 0.055), (0.146, 0.068), (0.138, 0.068), (0.114, 0.024), (0.005, 0.012)],
        col, mats["planter_ceramic"], segs=24
    )
    for fx_o, fy_o, f_mat in [(-0.04, -0.03, "planter_terracotta"), (0.04, -0.02, "foliage_sun"), (0.0, 0.04, "book_ochre")]:
        make_lathed_mesh(
            f"{tag}_Decor_Kitchen_Fruit_{fx_o:.2f}", 8.60 + fx_o, 5.54 + fy_o, kt_z + 0.022,
            [(0.012, 0.0), (0.034, 0.018), (0.036, 0.036), (0.022, 0.056), (0.004, 0.062)],
            col, mats[f_mat], segs=14
        )

    # --- 4. FOYER (RM-07) & GALLERY HALL (RM-08): Arched Backlit Entry Mirror, Key Console & Hall Art ---
    make_arched_mirror(f"{tag}_Decor_Foyer_Mirror", 5.962, 2.71, z + 0.86, 0.72, 1.42, "-X", col, pal["metal"], mats["mirror"], mats["emit_warm"])
    make_rounded_slab(f"{tag}_Decor_Foyer_Ledge", 5.72, 3.12, z + 0.82, 5.96, 3.44, z + 0.86, 0.035, col, pal["wood"], segs=6)
    make_lathed_mesh(
        f"{tag}_Decor_Foyer_Diffuser", 5.84, 3.28, z + 0.86,
        [(0.035, 0.0), (0.044, 0.045), (0.038, 0.095), (0.018, 0.125), (0.022, 0.135)],
        col, mats["glass_frosted"], segs=16
    )
    make_box(f"{tag}_ArtHall_Frame", 3.38, 8.05, z + 1.32, 3.86, 8.08, z + 2.15, col, pal["metal"])
    make_plane_uv(f"{tag}_ArtHall_Canvas", 3.41, 8.044, z + 1.35, 3.83, 8.044, z + 2.12, col, pal["art"])

    # --- 5. MASTER BEDROOM SUITE (RM-01): Sculpted Pendant Globes, Arched Backlit Dressing Mirror & Pouf ---
    for ny_p, n_tag in [(9.05, "S"), (11.30, "N")]:
        make_cylinder(f"{tag}_Decor_Master_PendCord_{n_tag}", 0.41, ny_p, z + 1.18, 0.005, CEIL_H - 1.18, col, pal["metal"], segs=8)
        make_cylinder(f"{tag}_Decor_Master_PendCap_{n_tag}", 0.41, ny_p, z + 1.12, 0.038, 0.065, col, pal["metal"], segs=16)
        make_lathed_mesh(
            f"{tag}_Decor_Master_PendGlobe_{n_tag}", 0.41, ny_p, z + 0.94,
            [(0.035, 0.0), (0.072, 0.030), (0.088, 0.082), (0.076, 0.140), (0.038, 0.180)],
            col, mats["emit_lamp"], segs=20
        )
        make_box(f"{tag}_Decor_Master_NSBook_{n_tag}", 0.30, ny_p - 0.14, z + 0.505, 0.52, ny_p + 0.02, z + 0.532, col, mats["linen_oatmeal"], bevel=0.003)
    # Sculpted Arched Backlit Dressing Mirror above Master Media/Dressing Console!
    make_arched_mirror(f"{tag}_Decor_Master_Vanity", 3.798, 10.83, z + 0.88, 0.78, 1.18, "-X", col, pal["metal"], mats["mirror"], mats["emit_warm"])
    make_cylinder(f"{tag}_Decor_Master_PoufBase", 3.12, 10.83, z, 0.21, 0.05, col, pal["metal"], segs=22)
    make_plush_cushion(f"{tag}_Decor_Master_PoufSeat", 2.91, 10.62, z + 0.05, 3.33, 11.04, z + 0.44, col, pal["upholstery"], puff=0.22)
    make_rounded_slab(f"{tag}_Decor_Master_PerfumeTray", 3.48, 10.68, z + 0.535, 3.68, 10.98, z + 0.548, 0.04, col, pal["metal"], segs=6)
    make_cylinder(f"{tag}_Decor_Master_Bottle1", 3.56, 10.78, z + 0.548, 0.028, 0.11, col, mats["glass_clear"], segs=14)
    make_cylinder(f"{tag}_Decor_Master_Bottle2", 3.60, 10.88, z + 0.548, 0.024, 0.09, col, pal["metal"], segs=14)
    make_box(f"{tag}_Decor_Master_AC", 1.30, 8.205, z + 2.58, 2.35, 8.43, z + 2.84, col, mats["white_lacquer"], bevel=0.015, smooth=True)
    make_box(f"{tag}_Decor_Master_ACVane", 1.34, 8.425, z + 2.60, 2.31, 8.435, z + 2.62, col, mats["black_metal"])

    # --- 6. BEDROOM 2 (RM-03) & PROGRAMMER STUDIO (RM-04): Wall Art, Bookshelves & Kanban Glass Board ---
    # Framed Wall Art above Bed in Bed 2 (West wall x=0.20)
    make_box(f"{tag}_ArtBed2_Frame", 0.20, 6.22, z + 1.34, 0.238, 7.18, z + 2.22, col, pal["metal"])
    make_plane_uv(f"{tag}_ArtBed2_Canvas", 0.242, 6.26, z + 1.38, 0.242, 7.14, z + 2.18, col, pal["art"])

    # Floating Bookshelves on North solid wall in Bed 2 (y=7.84..8.075, x=1.05..2.15) — individual hardcover books!
    b2_book_mats = [mats["book_navy"], mats["book_olive"], mats["book_ochre"], mats["book_slate"], mats["book_burgundy"], mats["linen_oatmeal"]]
    for sh_i, sh_z in enumerate((z + 1.42, z + 1.82)):
        bx0, bx1, by0, by1 = 1.05, 2.15, 7.84, 8.075
        make_box(f"{tag}_Decor_Bed2_Shelf{sh_i}", bx0, by0, sh_z, bx1, by1, sh_z + 0.032, col, pal["wood"], bevel=0.004)
        cur_bx = bx0 + 0.08
        for bk_i in range(7):
            bw = 0.026 + (bk_i % 3) * 0.008
            bh = 0.17 + ((bk_i + sh_i) % 4) * 0.022
            bmat = b2_book_mats[(bk_i + sh_i * 2) % len(b2_book_mats)]
            make_box(f"{tag}_Decor_Bed2_Bk_{sh_i}_{bk_i}", cur_bx, by0 + 0.025, sh_z + 0.032, cur_bx + bw, by1 - 0.03, sh_z + 0.032 + bh, col, bmat, bevel=0.003)
            cur_bx += bw + 0.004
        make_cylinder(f"{tag}_Decor_Bed2_ShelfPot{sh_i}", bx1 - 0.20, (by0 + by1) * 0.5, sh_z + 0.032, 0.062, 0.14, col, pal["pot"], segs=14)
        make_cylinder(f"{tag}_Decor_Bed2_ShelfPlant{sh_i}", bx1 - 0.20, (by0 + by1) * 0.5, sh_z + 0.15, 0.085, 0.10, col, mats["foliage_mid"], segs=12, radius_top=0.04)

    # Programmer Studio (RM-04) West Wall: Frameless Glass System Architecture & Sprint Kanban Board (x=6.088, y=2.92..4.02)
    make_box(f"{tag}_Decor_Studio_KanbanGlass", 6.088, 2.92, z + 1.08, 6.108, 4.02, z + 2.04, col, mats["tv_screen"], bevel=0.004)
    make_box(f"{tag}_Decor_Studio_KanbanTray", 6.108, 3.15, z + 1.06, 6.145, 3.78, z + 1.08, col, pal["metal"], bevel=0.003)
    # Color-coded sprint sticky notes & architecture node cards on the glass board
    for sn_i, (sy_n, sz_n, sn_mat) in enumerate([
        (3.06, 1.76, "book_ochre"),
        (3.06, 1.56, "book_olive"),
        (3.26, 1.76, "book_navy"),
        (3.26, 1.56, "linen_oatmeal"),
        (3.48, 1.76, "fabric_terracotta"),
        (3.70, 1.66, "book_slate"),
    ]):
        make_box(f"{tag}_Decor_Studio_Sticky_{sn_i}", 6.107, sy_n, z + sz_n, 6.114, sy_n + 0.13, z + sz_n + 0.13, col, mats.get(sn_mat, pal["accent_pillow"]), bevel=0.002)
    # Window-side potted Monstera plant in South-East corner of Programmer Studio (x=8.72, y=2.55)
    build_potted_plant(f"{tag}_Decor_Studio_CornerPlant", 8.74, 2.55, z, 0.15, 1.05, col, pal["pot"])
    # Round coffee/laptop side table in front of Coding Break Daybed (x=8.16, y=4.04 — 100% clear of Door D4, daybed & shelf!)
    make_cylinder(f"{tag}_Decor_Studio_LoungeTblBase", 8.16, 4.04, z, 0.14, 0.026, col, pal["metal"], segs=18)
    make_cylinder(f"{tag}_Decor_Studio_LoungeTblStem", 8.16, 4.04, z + 0.026, 0.018, 0.44, col, pal["metal"], segs=12)
    make_cylinder(f"{tag}_Decor_Studio_LoungeTblTop", 8.16, 4.04, z + 0.466, 0.20, 0.024, col, pal["stone_top"], segs=20)
    make_cylinder(f"{tag}_Decor_Studio_LoungeCup", 8.16, 4.04, z + 0.490, 0.032, 0.072, col, mats["ceramic_white"], segs=14)

    # --- 7. MASTER ENSUITE (RM-02) & SHARED BATH (RM-05): Heated Towel Ladders, Shower Niche Bottles & Bath Mats ---
    # Master Ensuite heated towel rail + draped bath towels on West wall (x=3.925, y=10.30..10.85)
    for rail_z in (z + 0.95, z + 1.18, z + 1.42, z + 1.65):
        make_box(f"{tag}_Decor_Ensuite_Rail_{rail_z:.2f}", 3.92, 10.32, rail_z, 3.99, 10.82, rail_z + 0.018, col, pal["metal"], bevel=0.004)
    make_plush_cushion(f"{tag}_Decor_Ensuite_Towel1", 3.95, 10.38, z + 0.98, 4.02, 10.76, z + 1.43, col, mats["linen_oatmeal"], puff=0.14)
    # Shower niche shelf & 3 spa bottles inside Master Ensuite walk-in shower (North wall y=11.48)
    make_box(f"{tag}_Decor_Ensuite_ShowerShelf", 4.35, 11.38, z + 1.18, 4.95, 11.50, z + 1.21, col, pal["stone_top"], bevel=0.004)
    for bi, bx_p in enumerate((4.48, 4.65, 4.82)):
        make_cylinder(f"{tag}_Decor_Ensuite_SpaBottle{bi}", bx_p, 11.43, z + 1.21, 0.032, 0.16, col, mats["leather_cognac"], segs=12, radius_top=0.018)
    # Slatted teak bath mat outside shower glass
    make_box(f"{tag}_Decor_Ensuite_BathMat", 4.10, 10.18, z, 4.72, 10.56, z + 0.022, col, mats["floor_teak"], bevel=0.004)

    # Shared Bathroom heated towel rail + towel on East wall (x=4.74, y=5.55..6.02) & shower shelf
    for rail_z in (z + 1.00, z + 1.25, z + 1.50):
        make_box(f"{tag}_Decor_Shared_Rail_{rail_z:.2f}", 4.68, 5.56, rail_z, 4.744, 6.00, rail_z + 0.018, col, pal["metal"], bevel=0.004)
    make_plush_cushion(f"{tag}_Decor_Shared_Towel", 4.66, 5.60, z + 1.02, 4.72, 5.96, z + 1.51, col, mats["linen_oatmeal"], puff=0.14)
    make_box(f"{tag}_Decor_Shared_ShowerShelf", 3.45, 5.12, z + 1.18, 4.05, 5.24, z + 1.21, col, pal["stone_top"], bevel=0.004)
    for bi, bx_p in enumerate((3.58, 3.75, 3.92)):
        make_cylinder(f"{tag}_Decor_Shared_SpaBottle{bi}", bx_p, 5.18, z + 1.21, 0.030, 0.15, col, mats["leather_cognac"], segs=12, radius_top=0.016)
    make_box(f"{tag}_Decor_Shared_BathMat", 3.45, 5.94, z, 4.05, 6.32, z + 0.022, col, mats["floor_teak"], bevel=0.004)

    # --- 8. LAUNDRY & UTILITY (RM-06): Upper Storage Shelves on South Wall (100% clear of Window W4!), Folded Towels & Hamper ---
    make_box(f"{tag}_Decor_Laundry_Shelf1", 3.62, 3.65, z + 1.52, 4.70, 3.86, z + 1.555, col, pal["wood"], bevel=0.004)
    make_box(f"{tag}_Decor_Laundry_Shelf2", 3.62, 3.65, z + 1.92, 4.70, 3.86, z + 1.955, col, pal["wood"], bevel=0.004)
    make_plush_cushion(f"{tag}_Decor_Laundry_Towels1", 4.12, 3.67, z + 1.555, 4.62, 3.84, z + 1.74, col, mats["linen_oatmeal"], puff=0.12)
    make_cylinder(f"{tag}_Decor_Laundry_Detergent1", 3.74, 3.75, z + 1.555, 0.055, 0.22, col, mats["glass_frosted"], segs=14, radius_top=0.032)
    make_cylinder(f"{tag}_Decor_Laundry_Detergent2", 3.92, 3.75, z + 1.555, 0.050, 0.19, col, pal["pot"], segs=14)
    make_cylinder(f"{tag}_Decor_Laundry_Hamper", 4.44, 3.88, z, 0.18, 0.54, col, mats["linen_oatmeal"], segs=18, radius_top=0.21)

    # --- 9. REAR OUTDOOR TERRACE (EXT-04): Tailored Woven Terrace Rug (strictly inside EXT-04), Hurricane Lantern & Coffee Service ---
    tz = 0.11
    make_box(f"{tag}_Decor_Terrace_Rug", 5.95, 11.88, tz, 8.55, 13.34, tz + 0.012, col, pal["rug"], bevel=0.005, smooth=True)
    # Outdoor teak coffee table (F-TR-TBL: x=7.02..7.62, y=12.30..12.90, top=tz+0.42) hurricane lantern & cups
    tt_z = tz + 0.42
    make_box(f"{tag}_Decor_Terrace_Tray", 7.12, 12.40, tt_z, 7.52, 12.80, tt_z + 0.018, col, pal["metal"], bevel=0.004)
    make_cylinder(f"{tag}_Decor_Terrace_LanternGlass", 7.26, 12.56, tt_z + 0.018, 0.075, 0.22, col, mats["glass_clear"], segs=16)
    make_cylinder(f"{tag}_Decor_Terrace_LanternCandle", 7.26, 12.56, tt_z + 0.022, 0.036, 0.12, col, mats["emit_lamp"], segs=14)
    make_cylinder(f"{tag}_Decor_Terrace_Cup1", 7.42, 12.52, tt_z + 0.018, 0.034, 0.065, col, mats["ceramic_white"], segs=14)
    make_cylinder(f"{tag}_Decor_Terrace_Cup2", 7.40, 12.68, tt_z + 0.018, 0.034, 0.065, col, mats["ceramic_white"], segs=14)


def build_style_furniture(style_name, pal):
    col = pal["col"]
    tag = style_name

    for f in spec["furniture"]:
        x0, y0, x1, y1 = [c * M for c in f["rect"]]
        cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
        w, d = x1 - x0, y1 - y0
        kind = f["kind"]
        fid = f"{tag}_{f['id']}"
        z_base = 0.03 if f["room"] == "EXT-01" else (0.11 if f["room"] == "EXT-04" else FLOOR_Z)

        if kind == "rug":
            make_box(fid, x0, y0, z_base, x1, y1, z_base + 0.014, col, pal["rug"], bevel=0.006, smooth=True)

        elif kind in ("bed_king", "bed_queen"):
            # Sleek floating bed base + softly lofted mattress, draped duvet, plump pillows!
            make_box(f"{fid}_Frame", x0 + 0.02, y0 + 0.02, z_base + 0.10, x1 - 0.02, y1 - 0.02, z_base + 0.28, col, pal["wood"], bevel=0.014, smooth=True)
            for lx in (x0 + 0.14, x1 - 0.19):
                for ly in (y0 + 0.14, y1 - 0.19):
                    make_cylinder(f"{fid}_Leg_{lx:.2f}_{ly:.2f}", lx, ly, z_base, 0.024, 0.10, col, pal["metal"], segs=12)
            make_plush_cushion(f"{fid}_Mattress", x0 + 0.04, y0 + 0.04, z_base + 0.27, x1 - 0.04, y1 - 0.04, z_base + 0.52, col, mats["linen_oatmeal"], puff=0.08)

            if f["rotation_deg"] == 90:
                make_box(f"{fid}_Headboard", x0, y0 - 0.06, z_base + 0.10, x0 + 0.09, y1 + 0.06, z_base + 1.24, col, pal["wood_accent"], bevel=0.012)
                make_plush_cushion(f"{fid}_Duvet", x0 + 0.62, y0 + 0.01, z_base + 0.48, x1 + 0.02, y1 - 0.01, z_base + 0.59, col, pal["bed_linen"], puff=0.14)
                # Folded duvet throw runner across foot of bed
                make_plush_cushion(f"{fid}_ThrowRunner", x1 - 0.52, y0 - 0.02, z_base + 0.55, x1 + 0.02, y1 + 0.02, z_base + 0.62, col, pal["accent_pillow"], puff=0.10)
                pad = 0.12
                pw = (d - 3 * pad) * 0.5
                make_plush_cushion(f"{fid}_Pillow1", x0 + 0.14, y0 + pad, z_base + 0.51, x0 + 0.54, y0 + pad + pw, z_base + 0.70, col, mats["linen_oatmeal"], puff=0.28)
                make_plush_cushion(f"{fid}_Pillow2", x0 + 0.14, y0 + 2 * pad + pw, z_base + 0.51, x0 + 0.54, y1 - pad, z_base + 0.70, col, mats["linen_oatmeal"], puff=0.28)
                make_plush_cushion(f"{fid}_Lumbar", x0 + 0.50, cy - 0.30, z_base + 0.53, x0 + 0.72, cy + 0.30, z_base + 0.72, col, pal["accent_pillow"], puff=0.30)
            else:
                make_box(f"{fid}_Headboard", x1 - 0.09, y0 - 0.05, z_base + 0.10, x1, y1 + 0.05, z_base + 1.18, col, pal["wood_accent"], bevel=0.012)
                make_plush_cushion(f"{fid}_Duvet", x0 - 0.02, y0 + 0.01, z_base + 0.48, x1 - 0.62, y1 - 0.01, z_base + 0.59, col, pal["bed_linen"], puff=0.14)
                make_plush_cushion(f"{fid}_ThrowRunner", x0 - 0.02, y0 - 0.02, z_base + 0.55, x0 + 0.48, y1 + 0.02, z_base + 0.62, col, pal["accent_pillow"], puff=0.10)
                pad = 0.12
                pw = (d - 3 * pad) * 0.5
                make_plush_cushion(f"{fid}_Pillow1", x1 - 0.54, y0 + pad, z_base + 0.51, x1 - 0.14, y0 + pad + pw, z_base + 0.70, col, mats["linen_oatmeal"], puff=0.28)
                make_plush_cushion(f"{fid}_Pillow2", x1 - 0.54, y0 + 2 * pad + pw, z_base + 0.51, x1 - 0.14, y1 - pad, z_base + 0.70, col, mats["linen_oatmeal"], puff=0.28)

        elif kind == "nightstand":
            make_box(f"{fid}_Body", x0, y0, z_base + 0.16, x1, y1, z_base + 0.48, col, pal["wood"], bevel=0.008)
            make_box(f"{fid}_DrawerGap", x0 + 0.01, y0 + 0.01, z_base + 0.32, x1 + 0.004, y1 - 0.01, z_base + 0.328, col, mats["black_metal"])
            make_box(f"{fid}_Top", x0, y0, z_base + 0.48, x1, y1, z_base + 0.505, col, pal["stone_top"], bevel=0.004)
            # Sculptural alabaster / brass bedside table lamp
            make_cylinder(f"{fid}_LampBase", cx, cy, z_base + 0.505, 0.068, 0.16, col, pal["metal"], segs=18, radius_top=0.045)
            make_cylinder(f"{fid}_LampShade", cx, cy, z_base + 0.65, 0.135, 0.19, col, mats["emit_lamp"], segs=20, radius_top=0.115)

        elif kind == "wardrobe":
            wh = f["height_mm"] * M
            make_box(f"{fid}_Carcass", x0, y0, z_base, x1, y1, z_base + wh, col, pal["wood_accent"], bevel=0.005)
            # Crisp door panel shadow-gap dividers & elongated brass/black pulls facing into the room (never into wall!)
            if w > d:
                face_south = (f["rotation_deg"] == 180)
                gy0 = (y0 - 0.004) if face_south else (y1 - 0.002)
                gy1 = (y0 + 0.002) if face_south else (y1 + 0.004)
                py_pull = (y0 - 0.018) if face_south else (y1 + 0.018)
                for xi in (x0 + w * 0.25, x0 + w * 0.50, x0 + w * 0.75):
                    make_box(f"{fid}_Gap_{xi:.2f}", xi - 0.003, gy0, z_base + 0.02, xi + 0.003, gy1, z_base + wh - 0.02, col, mats["black_metal"])
                for xi in (x0 + w * 0.35, x0 + w * 0.65):
                    make_cylinder(f"{fid}_Pull_{xi:.2f}", xi, py_pull, z_base + 0.85, 0.008, 0.72, col, pal["metal"], segs=10)
            else:
                fx = x0 - 0.018 if f["rotation_deg"] == 270 else x1 + 0.018
                make_cylinder(f"{fid}_Pull", fx, cy, z_base + 0.85, 0.008, 0.72, col, pal["metal"], segs=10)

        elif kind == "sofa_l":
            # Low architectural walnut/oak plinth + softly lofted plush sofa cushions & angled throw pillows!
            make_box(f"{fid}_Plinth", x0 + 0.02, y0 + 0.02, z_base + 0.06, x1 - 0.02, y1 - 0.02, z_base + 0.21, col, pal["wood"], bevel=0.012, smooth=True)
            for lx in (x0 + 0.12, x1 - 0.12):
                for ly in (y0 + 0.12, y1 - 0.12):
                    make_cylinder(f"{fid}_Leg_{lx:.2f}_{ly:.2f}", lx, ly, z_base, 0.022, 0.06, col, pal["metal"], segs=10)
            make_plush_cushion(f"{fid}_BackFrame", x0, y0, z_base + 0.19, x0 + 0.22, y1, z_base + 0.76, col, pal["upholstery"], puff=0.10)
            make_plush_cushion(f"{fid}_ArmNorth", x0, y1 - 0.18, z_base + 0.19, x1 - 0.02, y1, z_base + 0.58, col, pal["upholstery"], puff=0.12)
            seg = (d - 0.18) / 3.0
            for i in range(3):
                sy0 = y0 + i * seg + 0.01
                sy1 = y0 + (i + 1) * seg - 0.01
                make_plush_cushion(f"{fid}_Seat{i}", x0 + 0.18, sy0, z_base + 0.21, x1, sy1, z_base + 0.44, col, pal["upholstery"], puff=0.16)
                make_plush_cushion(f"{fid}_BackCush{i}", x0 + 0.19, sy0 + 0.02, z_base + 0.42, x0 + 0.40, sy1 - 0.02, z_base + 0.80, col, pal["upholstery"], puff=0.22)
            # Organically tilted accent throw pillows
            make_plush_cushion(f"{fid}_Throw1", x0 + 0.36, y0 + 0.18, z_base + 0.43, x0 + 0.52, y0 + 0.56, z_base + 0.76, col, pal["accent_pillow"], puff=0.30, rot_z=0.24)
            make_plush_cushion(f"{fid}_Throw2", x0 + 0.36, y1 - 0.60, z_base + 0.43, x0 + 0.52, y1 - 0.22, z_base + 0.76, col, pal["accent_pillow"], puff=0.30, rot_z=-0.22)

        elif kind == "sofa_chaise":
            make_box(f"{fid}_Base", x0, y0 + 0.02, z_base + 0.06, x1 - 0.02, y1 - 0.02, z_base + 0.21, col, pal["wood"], bevel=0.012, smooth=True)
            make_plush_cushion(f"{fid}_Back", x0, y0, z_base + 0.19, x1, y0 + 0.20, z_base + 0.74, col, pal["upholstery"], puff=0.12)
            make_plush_cushion(f"{fid}_Seat", x0, y0 + 0.17, z_base + 0.21, x1, y1, z_base + 0.44, col, pal["upholstery"], puff=0.16)

        elif kind == "coffee_table":
            h_t = f["height_mm"] * M
            # Twin sculptural fluted drum plinth legs + stadium rounded-corner bullnose stone tabletop!
            make_cylinder(f"{fid}_Drum1", cx, y0 + d * 0.28, z_base, min(w, d) * 0.22, h_t - 0.045, col, pal["wood_accent"], segs=24)
            make_cylinder(f"{fid}_Drum2", cx, y1 - d * 0.28, z_base, min(w, d) * 0.22, h_t - 0.045, col, pal["wood_accent"], segs=24)
            make_rounded_slab(f"{fid}_Top", x0, y0, z_base + h_t - 0.045, x1, y1, z_base + h_t, 0.14, col, pal["stone_top"], segs=8)
            if f["room"] == "RM-09":
                make_box(f"{fid}_Book1", cx - 0.18, cy - 0.24, z_base + h_t, cx + 0.08, cy + 0.04, z_base + h_t + 0.032, col, mats["linen_oatmeal"], bevel=0.003)
                make_box(f"{fid}_Book2", cx - 0.15, cy - 0.20, z_base + h_t + 0.032, cx + 0.05, cy + 0.01, z_base + h_t + 0.056, col, pal["accent_pillow"], bevel=0.003)
                make_lathed_mesh(
                    f"{fid}_Vessel", cx + 0.12, cy + 0.22, z_base + h_t,
                    [(0.062, 0.0), (0.098, 0.048), (0.088, 0.102), (0.052, 0.136), (0.058, 0.150)],
                    col, mats["planter_ceramic"], segs=20
                )
                make_cylinder(f"{fid}_Candle", cx - 0.05, cy + 0.24, z_base + h_t, 0.035, 0.09, col, mats["emit_lamp"], segs=16)

        elif kind == "tv_console":
            make_box(f"{fid}_Credenza", x0, y0, z_base + 0.18, x1, y1, z_base + 0.50, col, pal["wood_accent"], bevel=0.008)
            make_rounded_slab(f"{fid}_Top", x0 - 0.01, y0 - 0.01, z_base + 0.50, x1, y1 + 0.01, z_base + 0.535, 0.03, col, pal["stone_top"], segs=6)
            make_box(f"{fid}_UnderGlow", x0 + 0.05, y0 + 0.08, z_base + 0.172, x1 - 0.06, y1 - 0.08, z_base + 0.18, col, mats["emit_warm"])
            if f["room"] == "RM-09":
                make_box(f"{fid}_FeaturePanel", x1 - 0.04, y0 + 0.06, z_base + 0.535, x1 + 0.01, y1 - 0.06, WALL_TOP_Z - 0.12, col, pal["wood_accent"])
                make_box(f"{fid}_OLED_Bezel", x1 - 0.088, cy - 0.78, z_base + 0.90, x1 - 0.048, cy + 0.78, z_base + 1.80, col, mats["black_metal"], bevel=0.006)
                make_box(f"{fid}_OLED_Screen", x1 - 0.094, cy - 0.76, z_base + 0.92, x1 - 0.086, cy + 0.76, z_base + 1.78, col, mats["tv_screen"])
                make_plane_uv(f"{fid}_OLED_ArtDisplay", x1 - 0.095, cy - 0.72, z_base + 0.96, x1 - 0.095, cy + 0.72, z_base + 1.74, col, pal["art"])
                make_box(f"{fid}_Soundbar", cx - 0.05, cy - 0.48, z_base + 0.535, cx + 0.05, cy + 0.48, z_base + 0.59, col, mats["black_metal"], bevel=0.008)
                make_lathed_mesh(
                    f"{fid}_DecorVase", cx, y0 + 0.24, z_base + 0.535,
                    [(0.048, 0.0), (0.082, 0.07), (0.072, 0.16), (0.034, 0.23), (0.044, 0.265)],
                    col, mats["planter_ceramic"], segs=20
                )
                make_box(f"{fid}_CredenzaBooks", cx - 0.11, y1 - 0.46, z_base + 0.535, cx + 0.11, y1 - 0.18, z_base + 0.585, col, mats["linen_oatmeal"], bevel=0.004)
                make_lathed_mesh(
                    f"{fid}_CredenzaSculpt", cx, y1 - 0.32, z_base + 0.585,
                    [(0.045, 0.0), (0.058, 0.035), (0.025, 0.075), (0.048, 0.115)],
                    col, pal["metal"], segs=18
                )

        elif kind == "dining_table_6":
            # Bullnose stadium rounded-corner walnut/oak dining table + sculpted pedestal legs + lathed centerpiece bowl
            make_rounded_slab(f"{fid}_Top", x0, y0, z_base + 0.715, x1, y1, z_base + 0.755, 0.12, col, pal["wood"], segs=8)
            make_cylinder(f"{fid}_Ped1", cx, y0 + 0.42, z_base, 0.16, 0.715, col, pal["wood_accent"], segs=24)
            make_cylinder(f"{fid}_Ped2", cx, y1 - 0.42, z_base, 0.16, 0.715, col, pal["wood_accent"], segs=24)
            make_lathed_mesh(
                f"{fid}_CenterBowl", cx, cy, z_base + 0.755,
                [(0.095, 0.0), (0.145, 0.025), (0.178, 0.072), (0.170, 0.090), (0.158, 0.090), (0.126, 0.032), (0.005, 0.015)],
                col, mats["planter_ceramic"], segs=24
            )
            # 6 Sculpted Curved-Back Upholstered Dining Chairs (rounded seat + curved wrap-around tub backrest!)
            for i in range(3):
                yc = y0 + 0.30 + i * 0.60
                for side_idx, (cx0, cx1, side_sign) in enumerate([
                    (x0 - 0.39, x0 - 0.01, -1.0),
                    (x1 + 0.01, x1 + 0.39, 1.0),
                ]):
                    cid = f"{fid}_Chair_{i}_{side_idx}"
                    scx = (cx0 + cx1) * 0.5
                    make_plush_cushion(f"{cid}_Seat", cx0, yc - 0.21, z_base + 0.42, cx1, yc + 0.21, z_base + 0.49, col, pal["upholstery"], puff=0.14)
                    # Curved horseshoe wrap-around upholstered backrest embracing the seat
                    arc_c = []
                    for ak in range(11):
                        ang = -math.pi * 0.46 + math.pi * 0.92 * (ak / 10.0)
                        rx = scx + side_sign * (0.175 * math.cos(ang))
                        ry = yc + 0.205 * math.sin(ang)
                        arc_c.append((rx, ry))
                    bm_ch = bmesh.new()
                    r_bot_in, r_bot_out, r_top_in, r_top_out = [], [], [], []
                    for rx, ry in arc_c:
                        dir_v = Vector((rx - scx, ry - yc, 0.0)).normalized()
                        p_in = Vector((rx, ry, 0.0)) - dir_v * 0.026
                        p_out = Vector((rx, ry, 0.0)) + dir_v * 0.026
                        r_bot_in.append(bm_ch.verts.new((p_in.x, p_in.y, z_base + 0.50)))
                        r_bot_out.append(bm_ch.verts.new((p_out.x, p_out.y, z_base + 0.50)))
                        r_top_in.append(bm_ch.verts.new((p_in.x, p_in.y, z_base + 0.81)))
                        r_top_out.append(bm_ch.verts.new((p_out.x, p_out.y, z_base + 0.81)))
                    for ak in range(len(arc_c) - 1):
                        bm_ch.faces.new((r_bot_out[ak], r_bot_out[ak + 1], r_top_out[ak + 1], r_top_out[ak]))
                        bm_ch.faces.new((r_bot_in[ak + 1], r_bot_in[ak], r_top_in[ak], r_top_in[ak + 1]))
                        bm_ch.faces.new((r_top_out[ak], r_top_out[ak + 1], r_top_in[ak + 1], r_top_in[ak]))
                        bm_ch.faces.new((r_bot_in[ak], r_bot_in[ak + 1], r_bot_out[ak + 1], r_bot_out[ak]))
                    bm_ch.faces.new((r_bot_in[0], r_bot_out[0], r_top_out[0], r_top_in[0]))
                    bm_ch.faces.new((r_bot_out[-1], r_bot_in[-1], r_top_in[-1], r_top_out[-1]))
                    bmesh.ops.bevel(bm_ch, geom=list(bm_ch.edges), offset=0.012, segments=2, affect="EDGES")
                    bmesh.ops.recalc_face_normals(bm_ch, faces=bm_ch.faces)
                    split_sharp_edges(bm_ch, 42.0)
                    apply_box_uv(bm_ch, scale=1.8)
                    m_ch = bpy.data.meshes.new(f"{cid}_Back")
                    bm_ch.to_mesh(m_ch)
                    bm_ch.free()
                    for poly in m_ch.polygons:
                        poly.use_smooth = True
                    m_ch.materials.append(pal["upholstery"])
                    link_obj(bpy.data.objects.new(f"{cid}_Back", m_ch), col)
                    for lx in (cx0 + 0.04, cx1 - 0.04):
                        for ly in (yc - 0.17, yc + 0.17):
                            make_cylinder(f"{cid}_L_{lx:.2f}_{ly:.2f}", lx, ly, z_base, 0.013, 0.43, col, pal["metal"], segs=10, radius_top=0.017)
            make_box(f"{fid}_PendantBar", cx - 0.028, cy - 0.68, z_base + 2.02, cx + 0.028, cy + 0.68, z_base + 2.09, col, pal["metal"], bevel=0.008)
            make_box(f"{fid}_PendantEmit", cx - 0.018, cy - 0.65, z_base + 2.008, cx + 0.018, cy + 0.65, z_base + 2.02, col, mats["emit_warm"])
            make_cylinder(f"{fid}_Rod1", cx, cy - 0.46, z_base + 2.09, 0.006, WALL_TOP_Z - (z_base + 2.09), col, pal["metal"], segs=8)
            make_cylinder(f"{fid}_Rod2", cx, cy + 0.46, z_base + 2.09, 0.006, WALL_TOP_Z - (z_base + 2.09), col, pal["metal"], segs=8)

        elif kind == "kitchen_counter":
            if f["id"] == "F-KT-E":
                make_box(f"{fid}_BaseCab", x0, y0, z_base + 0.08, x1, y1, z_base + 0.86, col, pal["cabinet"], bevel=0.004)
            else:
                # Keep sink cavity completely hollow above z_base + 0.715 while keeping full front cabinet apron!
                make_box(f"{fid}_BaseCab_Low", x0, y0, z_base + 0.08, x1, y1, z_base + 0.715, col, pal["cabinet"], bevel=0.004)
                make_box(f"{fid}_BaseCab_Apron", x0, y1 - 0.06, z_base + 0.715, x1, y1, z_base + 0.86, col, pal["cabinet"], bevel=0.003)
                make_box(f"{fid}_BaseCab_SideW", x0, y0, z_base + 0.715, 7.33, y1, z_base + 0.86, col, pal["cabinet"], bevel=0.003)
                make_box(f"{fid}_BaseCab_SideE", 8.05, y0, z_base + 0.715, x1, y1, z_base + 0.86, col, pal["cabinet"], bevel=0.003)
            make_box(f"{fid}_ToeKick", x0 + 0.04, y0 + 0.04, z_base, x1 - 0.01, y1 - 0.01, z_base + 0.08, col, mats["black_metal"])
            if f["id"] == "F-KT-E":
                make_box(f"{fid}_Counter", x0, y0, z_base + 0.86, x1, y1, z_base + 0.90, col, pal["stone_top"], bevel=0.004)
                for ry in (5.82, 6.38, 6.94):
                    make_box(f"{fid}_Reveal_{ry:.2f}", x0 - 0.003, ry - 0.002, z_base + 0.09, x0 + 0.003, ry + 0.002, z_base + 0.85, col, mats["black_metal"])
                make_box(f"{fid}_Backsplash", x1 - 0.022, y0 + 0.022, z_base + 0.90, x1, y1, z_base + 1.54, col, pal["stone_top"])
                make_box(f"{fid}_UpperCab", x1 - 0.36, y0 + 0.36, z_base + 1.54, x1, y1, z_base + 2.60, col, pal["cabinet"], bevel=0.004)
                make_box(f"{fid}_LEDStrip", x1 - 0.34, y0 + 0.42, z_base + 1.525, x1 - 0.31, y1 - 0.08, z_base + 1.54, col, mats["emit_warm"])
                # Refined Italian Espresso Machine (set flush so chrome grouphead, portafilter & curved mug sit cleanly on drip tray!)
                make_box(f"{fid}_EspressoBody", x1 - 0.31, 5.88, z_base + 0.90, x1 - 0.09, 6.12, z_base + 1.18, col, mats["black_metal"], bevel=0.012, smooth=True)
                make_box(f"{fid}_EspressoTop", x1 - 0.30, 5.89, z_base + 1.18, x1 - 0.10, 6.11, z_base + 1.195, col, mats["brushed_steel"], bevel=0.004)
                make_box(f"{fid}_EspressoTray", x1 - 0.41, 5.90, z_base + 0.90, x1 - 0.31, 6.10, z_base + 0.922, col, mats["brushed_steel"], bevel=0.003)
                make_cylinder(f"{fid}_EspressoGroup", x1 - 0.36, 6.00, z_base + 1.05, 0.030, 0.045, col, mats["brushed_steel"], segs=18)
                make_swept_tube(f"{fid}_EspressoPortafilter", [(x1 - 0.36, 6.00, z_base + 1.055), (x1 - 0.46, 6.00, z_base + 1.045)], 0.009, col, mats["walnut"], segs=10)
                make_curved_mug(f"{fid}_EspressoCup", x1 - 0.36, 6.00, z_base + 0.922, col, mats["ceramic_white"], handle_angle=1.2)
                make_lathed_mesh(
                    f"{fid}_Canister", x1 - 0.22, 7.28, z_base + 0.90,
                    [(0.048, 0.0), (0.054, 0.02), (0.054, 0.145), (0.046, 0.165), (0.046, 0.176)],
                    col, mats["planter_ceramic"], segs=18
                )
            else:
                # Split South Countertop around the real 3D recessed undermount sink cutout (X: 7.34..8.04, Y: 5.33..5.72)!
                make_box(f"{fid}_Counter_W", x0, y0, z_base + 0.86, 7.34, y1, z_base + 0.90, col, pal["stone_top"], bevel=0.003)
                make_box(f"{fid}_Counter_E", 8.04, y0, z_base + 0.86, x1, y1, z_base + 0.90, col, pal["stone_top"], bevel=0.003)
                make_box(f"{fid}_Counter_Back", 7.34, y0, z_base + 0.86, 8.04, 5.33, z_base + 0.90, col, pal["stone_top"], bevel=0.003)
                make_box(f"{fid}_Counter_Front", 7.34, 5.72, z_base + 0.86, 8.04, y1, z_base + 0.90, col, pal["stone_top"], bevel=0.003)
                for rx in (7.42, 7.88):
                    make_box(f"{fid}_Reveal_{rx:.2f}", rx - 0.002, y1 - 0.003, z_base + 0.09, rx + 0.002, y1 + 0.003, z_base + 0.85, col, mats["black_metal"])
                make_box(f"{fid}_Backsplash", x0, y0, z_base + 0.90, x1 + 0.62, y0 + 0.022, z_base + 1.54, col, pal["stone_top"])
                make_box(f"{fid}_UpperCab", x0, y0, z_base + 1.54, x1 + 0.62, y0 + 0.36, z_base + 2.60, col, pal["cabinet"], bevel=0.004)
                make_box(f"{fid}_LEDStrip", x0 + 0.08, y0 + 0.31, z_base + 1.525, x1 + 0.22, y0 + 0.34, z_base + 1.54, col, mats["emit_warm"])

        elif kind == "fridge":
            make_box(f"{fid}_Body", x0, y0, z_base, x1, y1, z_base + 2.28, col, pal["cabinet"], bevel=0.006)
            make_box(f"{fid}_DoorSplit", x0 - 0.003, cy - 0.003, z_base + 0.05, x0 + 0.004, cy + 0.003, z_base + 2.25, col, mats["black_metal"])
            make_cylinder(f"{fid}_Handle1", x0 - 0.02, cy - 0.04, z_base + 0.95, 0.009, 0.72, col, pal["metal"], segs=12)
            make_cylinder(f"{fid}_Handle2", x0 - 0.02, cy + 0.04, z_base + 0.95, 0.009, 0.72, col, pal["metal"], segs=12)

        elif kind == "cooktop":
            make_box(f"{fid}_Glass", x0, y0, z_base + 0.90, x1, y1, z_base + 0.910, col, mats["tv_screen"], bevel=0.002)
            for bx in (x0 + w * 0.30, x0 + w * 0.70):
                for by in (y0 + d * 0.28, y0 + d * 0.72):
                    make_cylinder(f"{fid}_Ring_{bx:.2f}_{by:.2f}", bx, by, z_base + 0.910, 0.074, 0.003, col, pal["metal"], segs=20)

        elif kind == "kitchen_sink":
            # TRUE 3D RECESSED UNDERMOUNT STAINLESS DOUBLE BASIN (19cm deep sunken bowls, zero flat stickers!) + curved gooseneck tap
            sx0, sy0, sx1, sy1 = 7.34, 5.33, 8.04, 5.72
            s_bot = z_base + 0.72
            s_top = z_base + 0.898
            # Brushed steel basin floor + 4 recessed perimeter walls + central divider
            make_box(f"{fid}_BasinFloor", sx0, sy0, s_bot, sx1, sy1, s_bot + 0.015, col, mats["brushed_steel"])
            make_box(f"{fid}_BasinWallW", sx0, sy0, s_bot, sx0 + 0.016, sy1, s_top, col, mats["brushed_steel"])
            make_box(f"{fid}_BasinWallE", sx1 - 0.016, sy0, s_bot, sx1, sy1, s_top, col, mats["brushed_steel"])
            make_box(f"{fid}_BasinWallS", sx0, sy0, s_bot, sx1, sy0 + 0.016, s_top, col, mats["brushed_steel"])
            make_box(f"{fid}_BasinWallN", sx0, sy1 - 0.016, s_bot, sx1, sy1, s_top, col, mats["brushed_steel"])
            make_box(f"{fid}_BasinDivider", cx - 0.014, sy0, s_bot, cx + 0.014, sy1, s_top - 0.012, col, mats["brushed_steel"], bevel=0.004)
            # Slim recessed brushed-steel rim lip flush with marble cutout
            make_box(f"{fid}_RimW", sx0 - 0.014, sy0 - 0.014, s_top - 0.004, sx0 + 0.004, sy1 + 0.014, s_top + 0.005, col, mats["brushed_steel"])
            make_box(f"{fid}_RimE", sx1 - 0.004, sy0 - 0.014, s_top - 0.004, sx1 + 0.014, sy1 + 0.014, s_top + 0.005, col, mats["brushed_steel"])
            make_box(f"{fid}_RimS", sx0, sy0 - 0.014, s_top - 0.004, sx1, sy0 + 0.004, s_top + 0.005, col, mats["brushed_steel"])
            make_box(f"{fid}_RimN", sx0, sy1 - 0.004, s_top - 0.004, sx1, sy1 + 0.014, s_top + 0.005, col, mats["brushed_steel"])
            # Deep strainer basket drains in each recessed bowl
            make_cylinder(f"{fid}_Drain1", (sx0 + cx) * 0.5, (sy0 + sy1) * 0.5, s_bot + 0.014, 0.032, 0.006, col, mats["black_metal"], segs=16)
            make_cylinder(f"{fid}_Drain2", (cx + sx1) * 0.5, (sy0 + sy1) * 0.5, s_bot + 0.014, 0.032, 0.006, col, mats["black_metal"], segs=16)
            fy_base = y0 + 0.018
            make_cylinder(f"{fid}_FaucetBase", cx, fy_base, z_base + 0.90, 0.022, 0.044, col, pal["metal"], segs=16)
            make_swept_tube(f"{fid}_FaucetLever", [(cx + 0.018, fy_base, z_base + 0.942), (cx + 0.068, fy_base + 0.012, z_base + 0.958)], 0.0055, col, pal["metal"], segs=10)
            # True smooth 180° curved tubular swan-neck kitchen faucet!
            goose_pts = [(cx, fy_base, z_base + 0.945), (cx, fy_base, z_base + 1.11)]
            for gk in range(13):
                ang = math.pi * (gk / 12.0)
                gy = fy_base + 0.095 * (1.0 - math.cos(ang))
                gz = z_base + 1.11 + 0.095 * math.sin(ang)
                goose_pts.append((cx, gy, gz))
            goose_pts.append((cx, fy_base + 0.190, z_base + 1.065))
            make_swept_tube(f"{fid}_FaucetGooseneck", goose_pts, 0.0105, col, pal["metal"], segs=14)
            make_cylinder(f"{fid}_FaucetAerator", cx, fy_base + 0.190, z_base + 1.054, 0.013, 0.014, col, pal["metal"], segs=16)
            make_lathed_mesh(
                f"{fid}_SoapPump", cx + 0.20, fy_base, z_base + 0.906,
                [(0.018, 0.0), (0.020, 0.052), (0.012, 0.068), (0.010, 0.082)],
                col, pal["metal"], segs=14
            )

        elif kind == "shower":
            make_box(f"{fid}_Tray", x0, y0, z_base, x1, y1, z_base + 0.02, col, mats["floor_travertine"])
            gy = y0 if f["room"] == "RM-02" else y1
            make_box(f"{fid}_GlassPanel", x0 + 0.02, gy - 0.006, z_base + 0.02, x1 - 0.52, gy + 0.006, z_base + 2.15, col, mats["glass_clear"])
            make_cylinder(f"{fid}_RainHead", cx, cy, z_base + 2.25, 0.15, 0.018, col, pal["metal"], segs=24)
            make_cylinder(f"{fid}_RainPipe", cx, cy, z_base + 2.27, 0.014, 0.53, col, pal["metal"], segs=12)

        elif kind == "vanity":
            make_box(f"{fid}_Cab", x0, y0, z_base + 0.42, x1, y1, z_base + 0.82, col, pal["wood"], bevel=0.008)
            make_rounded_slab(f"{fid}_Top", x0, y0, z_base + 0.82, x1, y1, z_base + 0.855, 0.022, col, pal["stone_top"], segs=6)
            # Sculpted hollow lathed ceramic vessel basin!
            rb = min(w, d) * 0.34
            make_lathed_mesh(
                f"{fid}_Basin", cx, cy, z_base + 0.855,
                [(rb * 0.72, 0.0), (rb, 0.045), (rb * 1.04, 0.115), (rb * 0.94, 0.115), (rb * 0.86, 0.045), (rb * 0.18, 0.012)],
                col, mats["ceramic_white"], segs=24
            )
            # Curved Swan-Neck Vanity Tap + Sculpted Arched Backlit Vanity Mirror!
            if f["rotation_deg"] == 270:
                tap_pts = [(x1 - 0.06, cy, z_base + 0.855), (x1 - 0.06, cy, z_base + 0.99)]
                for tk in range(11):
                    ang = math.pi * (tk / 10.0)
                    tap_pts.append((x1 - 0.06 - 0.075 * (1.0 - math.cos(ang)), cy, z_base + 0.99 + 0.065 * math.sin(ang)))
                make_swept_tube(f"{fid}_TapCurve", tap_pts, 0.009, col, pal["metal"], segs=12)
                make_cylinder(f"{fid}_Soap", x1 - 0.12, y0 + 0.14, z_base + 0.855, 0.028, 0.11, col, mats["planter_ceramic"], segs=14)
                make_arched_mirror(f"{fid}_Mirror", x1, cy, z_base + 1.04, (y1 - y0) * 0.84, 0.92, "-X", col, pal["metal"], mats["mirror"], mats["emit_warm"])
            else:
                tap_pts = [(cx, y1 - 0.06, z_base + 0.855), (cx, y1 - 0.06, z_base + 0.99)]
                for tk in range(11):
                    ang = math.pi * (tk / 10.0)
                    tap_pts.append((cx, y1 - 0.06 - 0.075 * (1.0 - math.cos(ang)), z_base + 0.99 + 0.065 * math.sin(ang)))
                make_swept_tube(f"{fid}_TapCurve", tap_pts, 0.009, col, pal["metal"], segs=12)
                make_cylinder(f"{fid}_Soap", x0 + 0.14, y1 - 0.12, z_base + 0.855, 0.028, 0.11, col, mats["planter_ceramic"], segs=14)
                make_arched_mirror(f"{fid}_Mirror", cx, y1, z_base + 1.04, (x1 - x0) * 0.84, 0.92, "-Y", col, pal["metal"], mats["mirror"], mats["emit_warm"])

        elif kind == "wc":
            if f["rotation_deg"] == 270:
                make_box(f"{fid}_Cistern", x1 - 0.15, y0 + 0.02, z_base + 0.42, x1, y1 - 0.02, z_base + 0.88, col, mats["ceramic_white"], bevel=0.016, smooth=True)
                make_plush_cushion(f"{fid}_Bowl", x0 + 0.02, y0 + 0.04, z_base + 0.15, x1 - 0.12, y1 - 0.04, z_base + 0.43, col, mats["ceramic_white"], puff=0.08)
            else:
                make_box(f"{fid}_Cistern", x0, y0 + 0.02, z_base + 0.42, x0 + 0.15, y1 - 0.02, z_base + 0.88, col, mats["ceramic_white"], bevel=0.016, smooth=True)
                make_plush_cushion(f"{fid}_Bowl", x0 + 0.12, y0 + 0.04, z_base + 0.15, x1 - 0.02, y1 - 0.04, z_base + 0.43, col, mats["ceramic_white"], puff=0.08)

        elif kind == "washer_dryer":
            # Under-counter front-load Washer & Dryer with stone folding top (z_top = z_base + 0.89 m, 100% below Window W4 sill!)
            make_box(f"{fid}_Washer", x0, y0, z_base, x1, y1, z_base + 0.85, col, mats["white_lacquer"], bevel=0.012)
            make_box(f"{fid}_CounterTop", x0 - 0.005, y0 - 0.01, z_base + 0.85, x1 + 0.005, y1 + 0.005, z_base + 0.89, col, pal["stone_top"], bevel=0.004)
            d1 = make_cylinder(f"{fid}_Drum1", cx, y0 - 0.008, z_base + 0.44, 0.21, 0.024, col, mats["black_metal"], segs=20)
            d1.rotation_euler = (math.pi * 0.5, 0, 0)

        elif kind == "utility_sink":
            make_box(f"{fid}_Cab", x0, y0, z_base, x1, y1, z_base + 0.86, col, pal["cabinet"])
            make_box(f"{fid}_Top", x0, y0, z_base + 0.86, x1, y1, z_base + 0.89, col, mats["brushed_steel"])

        elif kind == "desk":
            make_box(f"{fid}_Top", x0, y0, z_base + 0.72, x1, y1, z_base + 0.755, col, pal["wood"], bevel=0.008)
            make_box(f"{fid}_LegL", x0 + 0.04, y0 + 0.04, z_base, x0 + 0.08, y1 - 0.04, z_base + 0.72, col, pal["metal"])
            make_box(f"{fid}_LegR", x1 - 0.08, y0 + 0.04, z_base, x1 - 0.04, y1 - 0.04, z_base + 0.72, col, pal["metal"])
            # Tucked ergonomic study chair with 280mm clearance from Queen Bed F-B2-BED (y=6.22)
            make_plush_cushion(f"{fid}_ChairSeat", cx - 0.21, y1 - 0.06, z_base + 0.42, cx + 0.21, y1 + 0.28, z_base + 0.48, col, pal["upholstery"], puff=0.14)
            make_plush_cushion(f"{fid}_ChairBack", cx - 0.21, y1 + 0.22, z_base + 0.48, cx + 0.21, y1 + 0.28, z_base + 0.84, col, pal["upholstery"], puff=0.16)
            make_cylinder(f"{fid}_ChairStem", cx, y1 + 0.12, z_base, 0.020, 0.42, col, pal["metal"], segs=12)
            # Desktop Laptop, Leather Desk Mat & Mug (kept below window sill height!)
            dz = z_base + 0.755
            make_box(f"{fid}_DeskMat", cx - 0.26, cy - 0.12, dz, cx + 0.26, cy + 0.16, dz + 0.004, col, mats["matte_charcoal"], bevel=0.002)
            make_box(f"{fid}_LaptopBase", cx - 0.15, cy - 0.04, dz + 0.004, cx + 0.15, cy + 0.14, dz + 0.015, col, mats["brushed_steel"], bevel=0.003)
            make_box(f"{fid}_LaptopLid", cx - 0.15, cy - 0.055, dz + 0.015, cx + 0.15, cy - 0.040, dz + 0.195, col, mats["black_metal"], bevel=0.003)
            make_plane_uv(f"{fid}_LaptopScreen", cx - 0.138, cy - 0.038, dz + 0.024, cx + 0.138, cy - 0.038, dz + 0.186, col, mats["ide_screen"], flip_u=True)
            make_cylinder(f"{fid}_DeskMug", x0 + 0.16, cy + 0.04, dz, 0.036, 0.085, col, mats["ceramic_white"], segs=14)

        elif kind == "programmer_desk":
            # Custom 2.28m Ergonomic Rounded-Corner Motorized Standing Programmer Battlestation Desk!
            # Programmer sits at +Y looking South (-Y) toward Window W2 -> Viewer's LEFT is +X, RIGHT is -X
            dz = z_base + 0.74
            make_rounded_slab(f"{fid}_Tabletop", x0, y0, z_base + 0.70, x1, y1, dz, 0.042, col, pal["wood"], segs=6)
            make_box(f"{fid}_LED_BiasStrip", x0 + 0.08, y0 + 0.005, z_base + 0.71, x1 - 0.08, y0 + 0.022, z_base + 0.735, col, mats["emit_warm"])
            for lx_p, l_tag in [(x0 + 0.18, "L"), (x1 - 0.18, "R")]:
                make_rounded_slab(f"{fid}_Foot_{l_tag}", lx_p - 0.038, y0 + 0.06, z_base, lx_p + 0.038, y1 - 0.06, z_base + 0.030, 0.025, col, mats["black_metal"], segs=5)
                make_box(f"{fid}_Col_{l_tag}", lx_p - 0.030, cy - 0.030, z_base + 0.030, lx_p + 0.030, cy + 0.030, z_base + 0.70, col, mats["black_metal"], bevel=0.005)
            make_box(f"{fid}_CableTray", cx - 0.55, y0 + 0.12, z_base + 0.60, cx + 0.55, y0 + 0.24, z_base + 0.70, col, mats["black_metal"])

            # 1) TRUE 1800R CURVED 49" Super-Ultrawide Coding Monitor + Curved Articulated Arm + Curved BenQ ScreenBar!
            my = y0 + 0.34
            make_swept_tube(
                f"{fid}_ArmPost_Main",
                [(cx + 0.02, y0 + 0.06, dz), (cx + 0.02, y0 + 0.12, dz + 0.22), (cx + 0.02, my - 0.02, dz + 0.31)],
                0.020, col, mats["black_metal"], segs=12
            )
            # 14-segment 1800R curved bezel & UV-mapped IDE screen wrapping gracefully toward the programmer (+Y)!
            n_curv = 14
            mw_half = 0.535
            curve_depth = 0.085  # ergonomic concave wrap toward +Y
            mz0, mz1 = dz + 0.13, dz + 0.48
            bm_bz = bmesh.new()
            bm_sc = bmesh.new()
            bz_f_b, bz_f_t, bz_b_b, bz_b_t = [], [], [], []
            sc_b, sc_t = [], []
            for k in range(n_curv + 1):
                t = k / n_curv  # 0..1 from Viewer's LEFT (+X) to Viewer's RIGHT (-X)
                u_norm = 1.0 - 2.0 * t  # +1 (East/Left) to -1 (West/Right)
                px = cx + u_norm * mw_half
                py_c = my + curve_depth * (u_norm * u_norm)
                bz_f_b.append(bm_bz.verts.new((px, py_c + 0.010, mz0)))
                bz_f_t.append(bm_bz.verts.new((px, py_c + 0.010, mz1)))
                bz_b_b.append(bm_bz.verts.new((px, py_c - 0.014, mz0)))
                bz_b_t.append(bm_bz.verts.new((px, py_c - 0.014, mz1)))
                # Recessed inner screen panel
                sx = cx + u_norm * (mw_half - 0.012)
                sy = my + curve_depth * (u_norm * u_norm) + 0.012
                sc_b.append(bm_sc.verts.new((sx, sy, mz0 + 0.012)))
                sc_t.append(bm_sc.verts.new((sx, sy, mz1 - 0.012)))
            for k in range(n_curv):
                bm_bz.faces.new((bz_f_b[k], bz_f_b[k + 1], bz_f_t[k + 1], bz_f_t[k]))
                bm_bz.faces.new((bz_b_b[k + 1], bz_b_b[k], bz_b_t[k], bz_b_t[k + 1]))
                bm_bz.faces.new((bz_f_t[k], bz_f_t[k + 1], bz_b_t[k + 1], bz_b_t[k]))
                bm_bz.faces.new((bz_b_b[k], bz_b_b[k + 1], bz_f_b[k + 1], bz_f_b[k]))
                f_sc = bm_sc.faces.new((sc_b[k], sc_b[k + 1], sc_t[k + 1], sc_t[k]))
                uv_sc = bm_sc.loops.layers.uv.verify()
                u0, u1 = k / n_curv, (k + 1) / n_curv
                for lp, uvc in zip(f_sc.loops, [(u0, 0.0), (u1, 0.0), (u1, 1.0), (u0, 1.0)]):
                    lp[uv_sc].uv = uvc
            bm_bz.faces.new((bz_b_b[0], bz_f_b[0], bz_f_t[0], bz_b_t[0]))
            bm_bz.faces.new((bz_f_b[-1], bz_b_b[-1], bz_b_t[-1], bz_f_t[-1]))
            bmesh.ops.recalc_face_normals(bm_bz, faces=bm_bz.faces)
            split_sharp_edges(bm_bz, 38.0)
            apply_box_uv(bm_bz, scale=1.0)
            m_bz = bpy.data.meshes.new(f"{fid}_Ultrawide_Bezel")
            bm_bz.to_mesh(m_bz)
            bm_bz.free()
            for poly in m_bz.polygons:
                poly.use_smooth = True
            m_bz.materials.append(mats["black_metal"])
            link_obj(bpy.data.objects.new(f"{fid}_Ultrawide_Bezel", m_bz), col)

            bmesh.ops.recalc_face_normals(bm_sc, faces=bm_sc.faces)
            m_sc = bpy.data.meshes.new(f"{fid}_Ultrawide_Screen")
            bm_sc.to_mesh(m_sc)
            bm_sc.free()
            for poly in m_sc.polygons:
                poly.use_smooth = True
            m_sc.materials.append(mats["ide_screen"])
            link_obj(bpy.data.objects.new(f"{fid}_Ultrawide_Screen", m_sc), col)

            # Curved BenQ ScreenBar Halo Monitor Light Bar following top arc of curved 49" display!
            sb_pts = [(cx + (1.0 - 2.0 * (k / 8.0)) * 0.25, my + 0.025 + curve_depth * ((1.0 - 2.0 * (k / 8.0)) * 0.47) ** 2, mz1 + 0.015) for k in range(9)]
            make_swept_tube(f"{fid}_ScreenBar_Lamp", sb_pts, 0.011, col, mats["black_metal"], segs=12)
            sb_epts = [(p[0], p[1] + 0.002, p[2] - 0.010) for p in sb_pts]
            make_swept_tube(f"{fid}_ScreenBar_Emit", sb_epts, 0.006, col, mats["emit_warm"], segs=10)

            # 2) Secondary 27" Vertical Portrait Monitor on Viewer's LEFT (+X, subtly angled inward toward programmer)
            vx0, vx1 = cx + 0.59, cx + 0.93
            make_cylinder(f"{fid}_ArmPost_Vert", (vx0 + vx1) * 0.5, my + 0.04, dz, 0.016, 0.30, col, mats["black_metal"], segs=14)
            make_box(f"{fid}_VertMonitor_Bezel", vx0, my + 0.065, dz + 0.08, vx1, my + 0.095, dz + 0.56, col, mats["black_metal"], bevel=0.005)
            make_plane_uv(f"{fid}_VertMonitor_Screen", vx0 + 0.014, my + 0.097, dz + 0.094, vx1 - 0.014, my + 0.097, dz + 0.546, col, mats["ide_screen"], flip_u=True)

            # 3) Developer MacBook Pro on Sculpted Brushed-Aluminum Stand on Viewer's RIGHT (-X)
            lx0, lx1 = cx - 0.91, cx - 0.59
            make_box(f"{fid}_LaptopStand", lx0 + 0.04, my + 0.03, dz, lx1 - 0.04, my + 0.19, dz + 0.072, col, mats["brushed_steel"], bevel=0.005)
            make_box(f"{fid}_LaptopBody", lx0, my + 0.04, dz + 0.072, lx1, my + 0.24, dz + 0.084, col, mats["brushed_steel"], bevel=0.003)
            make_box(f"{fid}_LaptopLid", lx0, my + 0.025, dz + 0.084, lx1, my + 0.042, dz + 0.282, col, mats["black_metal"], bevel=0.003)
            make_plane_uv(f"{fid}_LaptopCode", lx0 + 0.012, my + 0.044, dz + 0.096, lx1 - 0.012, my + 0.044, dz + 0.270, col, mats["ide_screen"], flip_u=True)

            # 4) Custom 75% Mechanical Keyboard, Rounded Desk Mat, Sculpted Mouse, Rotary Audio DAC & True Curved Coffee Mug!
            make_rounded_slab(f"{fid}_WoolDeskMat", cx - 0.46, my + 0.09, dz, cx + 0.46, y1 - 0.04, dz + 0.003, 0.018, col, mats["matte_charcoal"], segs=5)
            make_box(f"{fid}_MechKeyboard_Case", cx - 0.16, my + 0.135, dz + 0.003, cx + 0.16, my + 0.255, dz + 0.021, col, mats["black_metal"], bevel=0.004)
            make_box(f"{fid}_MechKeyboard_Keys", cx - 0.148, my + 0.147, dz + 0.021, cx + 0.148, my + 0.243, dz + 0.028, col, mats["white_lacquer"], bevel=0.002)
            make_box(f"{fid}_MechKeyboard_Esc", cx + 0.122, my + 0.147, dz + 0.021, cx + 0.148, my + 0.169, dz + 0.030, col, mats["fabric_terracotta"], bevel=0.002)
            make_box(f"{fid}_MechKeyboard_Enter", cx - 0.148, my + 0.180, dz + 0.021, cx - 0.112, my + 0.210, dz + 0.030, col, mats["book_olive"], bevel=0.002)
            make_plush_cushion(f"{fid}_WirelessMouse", cx - 0.285, my + 0.150, dz + 0.003, cx - 0.222, my + 0.248, dz + 0.028, col, mats["matte_charcoal"], puff=0.22)
            make_box(f"{fid}_AudioDAC_Base", cx + 0.22, my + 0.145, dz + 0.003, cx + 0.30, my + 0.225, dz + 0.020, col, mats["black_metal"], bevel=0.004)
            make_cylinder(f"{fid}_AudioDAC_Knob", cx + 0.26, my + 0.185, dz + 0.020, 0.022, 0.014, col, mats["brushed_brass"], segs=18)
            make_curved_mug(f"{fid}_CoffeeMug", cx - 0.38, my + 0.215, dz + 0.003, col, mats["ceramic_white"], handle_angle=2.4)

            # 5) Rounded-Bevel Matte Studio Reference Monitor Speakers
            for sp_x, sp_tag in [(x0 + 0.12, "R"), (x1 - 0.12, "L")]:
                make_box(f"{fid}_Speaker_{sp_tag}", sp_x - 0.068, my + 0.01, dz, sp_x + 0.068, my + 0.15, dz + 0.20, col, mats["matte_charcoal"], bevel=0.014, smooth=True)
                wf = make_cylinder(f"{fid}_Woofer_{sp_tag}", sp_x, my + 0.151, dz + 0.08, 0.038, 0.005, col, mats["brushed_brass"], segs=18)
                wf.rotation_euler = (-math.pi * 0.5, 0, 0)
                tw = make_cylinder(f"{fid}_Tweeter_{sp_tag}", sp_x, my + 0.151, dz + 0.15, 0.018, 0.005, col, mats["black_metal"], segs=16)
                tw.rotation_euler = (-math.pi * 0.5, 0, 0)

            # 6) Sculpted Ergonomic Executive Mesh Coding Chair with TRUE Curved 5-Spoke Star Base & Curved S-Lumbar Spine!
            ch_y = y1 + 0.30
            make_cylinder(f"{fid}_ChairHub", cx, ch_y, z_base + 0.075, 0.028, 0.355, col, mats["black_metal"], segs=16)
            for arm_i in range(5):
                ang = arm_i * (2.0 * math.pi / 5.0) + 0.3
                ca_i, sa_i = math.cos(ang), math.sin(ang)
                leg_x = cx + 0.27 * ca_i
                leg_y = ch_y + 0.27 * sa_i
                # Curved arched spoke radiating cleanly from center cylinder directly to each caster!
                make_swept_tube(
                    f"{fid}_ChairSpoke_{arm_i}",
                    [(cx + 0.02 * ca_i, ch_y + 0.02 * sa_i, z_base + 0.105), (cx + 0.15 * ca_i, ch_y + 0.15 * sa_i, z_base + 0.082), (leg_x, leg_y, z_base + 0.056)],
                    0.015, col, mats["brushed_steel"], segs=10, radius_end=0.011
                )
                make_cylinder(f"{fid}_Caster_{arm_i}", leg_x, leg_y, z_base, 0.024, 0.054, col, mats["black_metal"], segs=12)
            make_plush_cushion(f"{fid}_ChairSeat", cx - 0.24, ch_y - 0.22, z_base + 0.43, cx + 0.24, ch_y + 0.22, z_base + 0.49, col, mats["fabric_charcoal"], puff=0.14)
            make_plush_cushion(f"{fid}_ChairBack", cx - 0.22, ch_y + 0.17, z_base + 0.49, cx + 0.22, ch_y + 0.24, z_base + 1.00, col, mats["fabric_charcoal"], puff=0.14)
            # Smooth S-curved ergonomic chair spine & curved neck support
            make_swept_tube(
                f"{fid}_ChairSpine",
                [(cx, ch_y + 0.02, z_base + 0.41), (cx, ch_y + 0.22, z_base + 0.44), (cx, ch_y + 0.265, z_base + 0.62), (cx, ch_y + 0.245, z_base + 0.84), (cx, ch_y + 0.255, z_base + 1.04)],
                0.018, col, mats["black_metal"], segs=12, radius_end=0.012
            )
            make_plush_cushion(f"{fid}_ChairHeadrest", cx - 0.11, ch_y + 0.17, z_base + 1.01, cx + 0.11, ch_y + 0.23, z_base + 1.11, col, mats["leather_cognac"], puff=0.16)
            for ar_s, ar_tag in [(-1, "L"), (1, "R")]:
                ax_c = cx + ar_s * 0.255
                make_swept_tube(
                    f"{fid}_ArmrestCurve_{ar_tag}",
                    [(cx + ar_s * 0.14, ch_y, z_base + 0.42), (ax_c, ch_y, z_base + 0.46), (ax_c, ch_y, z_base + 0.635)],
                    0.013, col, mats["black_metal"], segs=10
                )
                make_rounded_slab(f"{fid}_ArmrestPad_{ar_tag}", ax_c - 0.036, ch_y - 0.14, z_base + 0.632, ax_c + 0.036, ch_y + 0.09, z_base + 0.656, 0.020, col, mats["matte_charcoal"], segs=5)

        elif kind == "homelab_shelf":
            # Full-Height Acoustic Fluted Wood Feature Wall + 4-Tier LED-Lit Homelab & Tech Bookshelf on East Wall
            make_box(f"{fid}_AcousticSlatPanel", x1 - 0.035, y0 - 0.10, z_base, x1 + 0.015, y1 + 0.08, WALL_TOP_Z - 0.08, col, pal["wood_accent"])
            for py_post in (y0 + 0.04, cy, y1 - 0.04):
                make_box(f"{fid}_Post_{py_post:.2f}", x0 + 0.02, py_post - 0.016, z_base, x1 - 0.035, py_post + 0.016, z_base + 2.35, col, mats["black_metal"])
            for sh_idx, sh_h in enumerate((0.52, 1.04, 1.56, 2.08)):
                sz0 = z_base + sh_h
                make_box(f"{fid}_Tier_{sh_idx}", x0, y0, sz0, x1 - 0.03, y1, sz0 + 0.032, col, pal["wood"], bevel=0.005)
                make_box(f"{fid}_LED_{sh_idx}", x0 + 0.04, y0 + 0.06, sz0 - 0.008, x0 + 0.065, y1 - 0.06, sz0, col, mats["emit_warm"])
            # Tier 1: Custom Mini-ITX Tempered-Glass Homelab Workstation PC with visible internal motherboard, GPU & AIO cooler!
            pc_z = z_base + 0.552
            make_box(f"{fid}_HomelabPC_Chassis", x0 + 0.08, y0 + 0.14, pc_z, x1 - 0.06, y0 + 0.56, pc_z + 0.39, col, mats["matte_charcoal"], bevel=0.006)
            make_box(f"{fid}_HomelabPC_FrontMesh", x0 + 0.075, y0 + 0.135, pc_z + 0.02, x1 - 0.065, y0 + 0.145, pc_z + 0.37, col, mats["black_metal"], bevel=0.003)
            make_box(f"{fid}_HomelabPC_GPU", x0 + 0.095, y0 + 0.18, pc_z + 0.08, x0 + 0.18, y0 + 0.48, pc_z + 0.16, col, mats["black_metal"], bevel=0.004)
            make_box(f"{fid}_HomelabPC_GPU_LED", x0 + 0.082, y0 + 0.20, pc_z + 0.14, x0 + 0.096, y0 + 0.46, pc_z + 0.155, col, mats["emit_ev_green"])
            aio = make_cylinder(f"{fid}_HomelabPC_AIO_LED", x0 + 0.11, y0 + 0.36, pc_z + 0.25, 0.042, 0.025, col, mats["emit_warm"], segs=16)
            aio.rotation_euler = (0.0, math.pi * 0.5, 0.0)
            make_box(f"{fid}_HomelabPC_Glass", x0 + 0.072, y0 + 0.16, pc_z + 0.02, x0 + 0.079, y0 + 0.54, pc_z + 0.37, col, mats["glass_clear"])
            # 4-Bay NAS Storage Array with drive bay slots & status LEDs
            make_box(f"{fid}_NAS_Array", x0 + 0.09, y0 + 0.66, pc_z, x1 - 0.08, y0 + 0.94, pc_z + 0.21, col, mats["black_metal"], bevel=0.006)
            for bay_i in range(4):
                by_slot = y0 + 0.695 + bay_i * 0.056
                make_box(f"{fid}_NAS_Bay_{bay_i}", x0 + 0.085, by_slot, pc_z + 0.025, x0 + 0.095, by_slot + 0.042, pc_z + 0.185, col, mats["matte_charcoal"], bevel=0.002)
            # Tier 2 & 3: Row of individual Hardcover Technical Books (varied heights, widths & spine colors — zero orange blocks!)
            book_spine_mats = [mats["book_navy"], mats["book_olive"], mats["book_slate"], mats["book_ochre"], mats["book_burgundy"], mats["linen_oatmeal"], mats["matte_charcoal"]]
            for b_tier, tz_b in [(1, z_base + 1.072), (2, z_base + 1.592)]:
                cur_by = y0 + 0.14
                for bk_idx in range(11):
                    b_thick = 0.026 + (bk_idx % 3) * 0.009
                    b_height = 0.19 + ((bk_idx + b_tier * 2) % 4) * 0.024
                    b_depth = 0.19 + (bk_idx % 2) * 0.025
                    b_mat = book_spine_mats[(bk_idx + b_tier * 3) % len(book_spine_mats)]
                    make_box(
                        f"{fid}_Book_{b_tier}_{bk_idx}",
                        x0 + 0.09, cur_by, tz_b,
                        x0 + 0.09 + b_depth, cur_by + b_thick, tz_b + b_height,
                        col, b_mat, bevel=0.003
                    )
                    cur_by += b_thick + 0.004
                # Architectural brass bookend & sculptural ceramic vessel on each shelf
                make_box(f"{fid}_Bookend_{b_tier}", x0 + 0.10, cur_by, tz_b, x0 + 0.26, cur_by + 0.012, tz_b + 0.16, col, pal["metal"], bevel=0.002)
                make_cylinder(f"{fid}_Vessel_{b_tier}", (x0 + x1) * 0.5, y1 - 0.34, tz_b, 0.072, 0.21, col, pal["pot"], segs=16, radius_top=0.044)
                # Horizontal stacked art/architecture monographs beside vessel
                make_box(f"{fid}_HBook1_{b_tier}", x0 + 0.08, y1 - 0.78, tz_b, x1 - 0.08, y1 - 0.50, tz_b + 0.032, col, mats["book_slate"], bevel=0.003)
                make_box(f"{fid}_HBook2_{b_tier}", x0 + 0.10, y1 - 0.76, tz_b + 0.032, x1 - 0.10, y1 - 0.52, tz_b + 0.060, col, mats["linen_oatmeal"], bevel=0.003)

        elif kind == "studio_lounge":
            # Cozy Coding Break Daybed & Reading Lounge along North wall of Programmer Studio
            make_box(f"{fid}_Plinth", x0 + 0.02, y0 + 0.02, z_base + 0.06, x1 - 0.02, y1 - 0.02, z_base + 0.22, col, pal["wood"], bevel=0.012, smooth=True)
            make_plush_cushion(f"{fid}_Mattress", x0, y0, z_base + 0.21, x1, y1, z_base + 0.44, col, pal["upholstery"], puff=0.16)
            make_plush_cushion(f"{fid}_BackBolster", x0 + 0.02, y1 - 0.18, z_base + 0.42, x1 - 0.02, y1 - 0.01, z_base + 0.76, col, pal["upholstery"], puff=0.20)
            make_plush_cushion(f"{fid}_PillowL", x0 + 0.08, y1 - 0.32, z_base + 0.43, x0 + 0.46, y1 - 0.14, z_base + 0.74, col, pal["accent_pillow"], puff=0.28, rot_z=0.18)
            make_plush_cushion(f"{fid}_PillowR", x1 - 0.48, y1 - 0.32, z_base + 0.43, x1 - 0.10, y1 - 0.14, z_base + 0.74, col, mats["linen_oatmeal"], puff=0.28, rot_z=-0.16)

        elif kind == "bench":
            make_box(f"{fid}_Base", x0, y0, z_base, x1, y1, z_base + 0.39, col, pal["wood_accent"], bevel=0.008)
            make_plush_cushion(f"{fid}_Cushion", x0 + 0.01, y0 + 0.01, z_base + 0.39, x1 - 0.01, y1 - 0.01, z_base + 0.48, col, pal["upholstery"], puff=0.18)

        elif kind == "plant_pot":
            px_plant = 5.83 if f["id"] == "F-FY-PLANT" else cx
            r_plant = 0.11 if f["id"] == "F-FY-PLANT" else min(w, d) * 0.52
            build_potted_plant(fid, px_plant, cy, z_base, r_plant, f["height_mm"] * M, col, pal["pot"])

        elif kind in ("outdoor_lounge", "armchair"):
            make_box(f"{fid}_Frame", x0, y0, z_base + 0.08, x1, y1, z_base + 0.28, col, mats["walnut"], bevel=0.012)
            make_plush_cushion(f"{fid}_Cushion", x0 + 0.03, y0 + 0.03, z_base + 0.28, x1 - 0.03, y1 - 0.03, z_base + 0.47, col, pal["upholstery"], puff=0.18)
            make_plush_cushion(f"{fid}_Back", x0 + 0.03, y1 - 0.20, z_base + 0.44, x1 - 0.03, y1 - 0.01, z_base + 0.78, col, pal["upholstery"], puff=0.22)
            make_plush_cushion(f"{fid}_AccentPillow", cx - 0.18, y1 - 0.32, z_base + 0.45, cx + 0.18, y1 - 0.16, z_base + 0.68, col, pal["accent_pillow"], puff=0.26)

        elif kind == "car":
            build_luxury_car(fid, x0, y0, x1, y1, z_base, col, pal)

        else:
            # Keep laundry utility storage credenza counter-height & clear of Window W4 jamb (y < 3.88)
            cab_h = 0.89 if f["id"] == "F-LN-SHELF" else f["height_mm"] * M
            cab_y1 = min(y1, 3.88) if f["id"] == "F-LN-SHELF" else y1
            make_box(fid, x0, y0, z_base, x1, cab_y1, z_base + cab_h, col, pal["cabinet"], bevel=0.005)

    # REAL SINUSOIDAL S-FOLD PLEATED SHEER CURTAINS + ceiling recessed track!
    for cx0, cx1, cy_curt, cname in [
        (5.48, 5.96, 11.40, "Curtain_Living_W"),
        (8.42, 8.90, 11.40, "Curtain_Living_E"),
        (0.38, 0.92, 11.40, "Curtain_Master_W"),
        (3.04, 3.58, 11.40, "Curtain_Master_E"),
        (6.16, 6.66, 2.16, "Curtain_Studio_W"),
        (8.36, 8.86, 2.16, "Curtain_Studio_E"),
    ]:
        make_pleated_curtain(f"{tag}_{cname}", cx0, cx1, cy_curt, FLOOR_Z + 0.02, WALL_TOP_Z - 0.03, col, pal["curtain"], waves=5)

    # Framed Gallery Artwork (Living Room, Master Bedroom, Dining Gallery)
    make_box(f"{tag}_ArtLiving_Frame", 5.49, 9.40, FLOOR_Z + 1.28, 5.53, 10.65, FLOOR_Z + 2.38, col, pal["metal"])
    make_plane_uv(f"{tag}_ArtLiving_Canvas", 5.535, 9.44, FLOOR_Z + 1.32, 5.535, 10.61, FLOOR_Z + 2.34, col, pal["art"])

    make_box(f"{tag}_ArtMaster_Frame", 0.20, 9.65, FLOOR_Z + 1.35, 0.24, 10.75, FLOOR_Z + 2.30, col, pal["metal"])
    make_plane_uv(f"{tag}_ArtMaster_Canvas", 0.245, 9.69, FLOOR_Z + 1.39, 0.245, 10.71, FLOOR_Z + 2.26, col, pal["art"])

    make_box(f"{tag}_ArtDining_Frame", 4.864, 5.35, FLOOR_Z + 1.30, 4.90, 6.02, FLOOR_Z + 2.20, col, pal["metal"])
    make_plane_uv(f"{tag}_ArtDining_Canvas", 4.905, 5.38, FLOOR_Z + 1.33, 4.905, 5.99, FLOOR_Z + 2.17, col, pal["art"])

    # Keep South Kitchen BaseCab clear behind the 19cm recessed stainless sink basin!
    # (Handled smoothly because BaseCab sits below s_bot for F-KT-S)
    # Bespoke room-by-room accessories, tableware, lamps, books, spa details & outdoor decor
    build_detailed_decorations(tag, col, pal)
    # Complete Level 2 Furnishings: RM-12 Tempat Jemuran & Service Deck, RM-13 Sky Lounge & EXT-05 Front Balcony
    build_level2_furniture(tag, col, pal)


def make_draped_garment(name, x0, x1, y_bar, z_bar, drop_len, col_name, mat):
    """Creates a realistic softly pleated U-draped cloth towel / shirt with organic fabric folds & soft corners."""
    bm = bmesh.new()
    cols_n = 14
    r_bar = 0.018
    prof = [
        (y_bar - 0.034, z_bar - drop_len),
        (y_bar - 0.030, z_bar - drop_len * 0.68),
        (y_bar - 0.025, z_bar - drop_len * 0.35),
        (y_bar - r_bar, z_bar - 0.01),
        (y_bar - r_bar * 0.6, z_bar + r_bar),
        (y_bar + r_bar * 0.6, z_bar + r_bar),
        (y_bar + r_bar, z_bar - 0.01),
        (y_bar + 0.025, z_bar - drop_len * 0.35),
        (y_bar + 0.030, z_bar - drop_len * 0.68),
        (y_bar + 0.032, z_bar - drop_len * 0.94),
    ]
    grid = []
    for c in range(cols_n + 1):
        tx = c / float(cols_n)
        px = x0 + (x1 - x0) * tx
        # Subtle catenary cloth sag & curved edge drape
        edge_lift = 0.018 * (1.0 - math.sin(tx * math.pi) ** 0.45)
        row = []
        for pi, (py, pz) in enumerate(prof):
            hem_w = 1.0 if pi in (0, len(prof) - 1) else (0.65 if pi in (1, len(prof) - 2) else (0.30 if pi in (2, len(prof) - 3) else 0.0))
            wave = (math.sin(tx * math.pi * 4.0) * 0.014 + math.cos(tx * math.pi * 7.0) * 0.005) * hem_w
            row.append(bm.verts.new((px, py + wave, pz + edge_lift * hem_w)))
        grid.append(row)
    for c in range(cols_n):
        for p in range(len(prof) - 1):
            bm.faces.new((grid[c][p], grid[c + 1][p], grid[c + 1][p + 1], grid[c][p + 1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    apply_box_uv(bm, scale=2.2)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    mesh.materials.append(mat)
    return link_obj(bpy.data.objects.new(name, mesh), col_name)


def build_level2_furniture(tag, col, pal):
    """Builds complete Level 2 spaces: RM-12 Tempat Jemuran & Service Deck, RM-13 Sky Lounge, EXT-05 Front Balcony."""
    z2 = FLOOR2_Z

    # =========================================================================
    # 1. RM-12 TEMPAT JEMURAN & SKY SERVICE DECK (X: 0.20..4.864, Y: 6.80..11.50)
    # =========================================================================
    # A) Primary Brushed-Stainless Folding 3-Bar Drying Rack #1 (Jemuran Lipat Palang 3: X=0.88..2.52, Y=9.05..9.82)
    rx0, rx1, ry0, ry1 = 0.88, 2.52, 9.05, 9.82
    ryc = (ry0 + ry1) * 0.5
    for sx, stag in [(rx0, "W"), (rx1, "E")]:
        # Sculpted brushed-stainless A-frame tubular legs
        make_swept_tube(f"{tag}_L2_Jemuran_Rack1_LegF_{stag}", [(sx, ry0, z2), (sx, ryc - 0.14, z2 + 1.18), (sx, ryc, z2 + 1.36)], 0.014, col, mats["brushed_steel"], segs=10)
        make_swept_tube(f"{tag}_L2_Jemuran_Rack1_LegB_{stag}", [(sx, ry1, z2), (sx, ryc + 0.14, z2 + 1.18), (sx, ryc, z2 + 1.36)], 0.014, col, mats["brushed_steel"], segs=10)
        make_swept_tube(f"{tag}_L2_Jemuran_Rack1_Brace_{stag}", [(sx, ry0 + 0.06, z2 + 0.36), (sx, ry1 - 0.06, z2 + 0.36)], 0.010, col, mats["brushed_steel"], segs=8)
    # 3 Parallel Horizontal Drying Rails + Lower Shoe-Drying Bars
    for bar_i, (by_r, bz_r) in enumerate([(ryc - 0.14, z2 + 1.18), (ryc, z2 + 1.36), (ryc + 0.14, z2 + 1.18)]):
        make_swept_tube(f"{tag}_L2_Jemuran_Rack1_Bar_{bar_i}", [(rx0 - 0.04, by_r, bz_r), (rx1 + 0.04, by_r, bz_r)], 0.011, col, mats["brushed_steel"], segs=10)
    make_swept_tube(f"{tag}_L2_Jemuran_Rack1_LowBar1", [(rx0, ryc - 0.12, z2 + 0.36), (rx1, ryc - 0.12, z2 + 0.36)], 0.009, col, mats["brushed_steel"], segs=8)
    make_swept_tube(f"{tag}_L2_Jemuran_Rack1_LowBar2", [(rx0, ryc + 0.12, z2 + 0.36), (rx1, ryc + 0.12, z2 + 0.36)], 0.009, col, mats["brushed_steel"], segs=8)
    # Draped Fresh-Washed Towels, Linen Sheets & Clothes + Walnut Clothespins on Rack #1!
    garments_r1 = [
        ("WhiteTowel", 0.96, 1.48, ryc - 0.14, z2 + 1.18, 0.56, mats["linen_white"]),
        ("BeigeTowel", 1.56, 2.04, ryc - 0.14, z2 + 1.18, 0.52, mats["boucle_beige"]),
        ("WhiteSheet", 0.98, 1.82, ryc, z2 + 1.36, 0.72, mats["linen_white"]),
        ("SageTee", 1.94, 2.42, ryc, z2 + 1.36, 0.54, mats["linen_sage"]),
        ("NavyDenim", 1.12, 1.62, ryc + 0.14, z2 + 1.18, 0.64, mats["cotton_navy"]),
        ("OatmealLinen", 1.76, 2.38, ryc + 0.14, z2 + 1.18, 0.50, mats["linen_oatmeal"]),
    ]
    for gname, gx0, gx1, gy_b, gz_b, gdrop, gmat in garments_r1:
        make_draped_garment(f"{tag}_L2_Jemuran_Cloth_{gname}", gx0, gx1, gy_b, gz_b, gdrop, col, gmat)
        for pin_x in (gx0 + 0.06, gx1 - 0.06):
            make_box(f"{tag}_L2_Jemuran_Pin_{gname}_{pin_x:.2f}", pin_x - 0.008, gy_b - 0.012, gz_b + 0.012, pin_x + 0.008, gy_b + 0.012, gz_b + 0.056, col, mats["walnut"])

    # B) Secondary Folding Gull-Wing Drying Rack #2 (Jemuran Sayap: X=2.98..4.32, Y=9.75..10.48)
    r2x0, r2x1, r2y0, r2y1 = 2.98, 4.32, 9.75, 10.48
    r2yc = (r2y0 + r2y1) * 0.5
    for sx, stag in [(r2x0 + 0.24, "W"), (r2x1 - 0.24, "E")]:
        make_swept_tube(f"{tag}_L2_Jemuran_Rack2_LegA_{stag}", [(sx, r2y0, z2), (sx, r2y1, z2 + 0.96)], 0.012, col, mats["brushed_steel"], segs=8)
        make_swept_tube(f"{tag}_L2_Jemuran_Rack2_LegB_{stag}", [(sx, r2y1, z2), (sx, r2y0, z2 + 0.96)], 0.012, col, mats["brushed_steel"], segs=8)
    # Central horizontal frame + angled wing extensions + parallel drying wires
    for wy in (r2y0 + 0.04, r2yc, r2y1 - 0.04):
        make_swept_tube(f"{tag}_L2_Jemuran_Rack2_Rail_{wy:.2f}", [(r2x0, wy, z2 + 1.06), (r2x0 + 0.24, wy, z2 + 0.96), (r2x1 - 0.24, wy, z2 + 0.96), (r2x1, wy, z2 + 1.06)], 0.008, col, mats["brushed_steel"], segs=8)
    make_draped_garment(f"{tag}_L2_Jemuran_R2_Towel1", 3.30, 3.88, r2y0 + 0.04, z2 + 0.96, 0.44, col, mats["linen_white"])
    make_draped_garment(f"{tag}_L2_Jemuran_R2_Towel2", 3.38, 3.96, r2y1 - 0.04, z2 + 0.96, 0.42, col, mats["linen_sage"])

    # C) Wall-Mounted Overhead Stainless Clothesline + 5 Wooden Hangers with Shirts along East Wall (X=4.48..4.86, Y=7.25..8.12)
    make_box(f"{tag}_L2_Jemuran_WallBrk1", 4.46, 7.24, z2 + 1.88, 4.864, 7.28, z2 + 1.94, col, mats["black_metal"])
    make_box(f"{tag}_L2_Jemuran_WallBrk2", 4.46, 8.08, z2 + 1.88, 4.864, 8.12, z2 + 1.94, col, mats["black_metal"])
    make_swept_tube(f"{tag}_L2_Jemuran_HangBar", [(4.54, 7.24, z2 + 1.91), (4.54, 8.12, z2 + 1.91)], 0.011, col, mats["brushed_steel"], segs=10)
    hang_mats = [mats["linen_white"], mats["linen_oatmeal"], mats["cotton_navy"], mats["linen_white"], mats["linen_sage"]]
    for hi, hmat in enumerate(hang_mats):
        hy = 7.36 + hi * 0.165
        # Triangular wooden hanger + crisp hanging shirt silhouette
        make_swept_tube(f"{tag}_L2_Jemuran_Hanger_{hi}", [(4.54, hy, z2 + 1.91), (4.54, hy, z2 + 1.83), (4.38, hy, z2 + 1.75), (4.70, hy, z2 + 1.75), (4.54, hy, z2 + 1.83)], 0.006, col, mats["light_oak"], segs=6)
        make_rounded_slab(f"{tag}_L2_Jemuran_Shirt_{hi}", 4.37, hy - 0.020, z2 + 1.18, 4.71, hy + 0.020, z2 + 1.76, 0.018, col, hmat, segs=4)

    # D) L2 Laundry Prep & Folding Counter + True Recessed 3D Stainless Slop Sink & Gooseneck Tap (X=0.22..2.28, Y=7.02..7.60)
    make_box(f"{tag}_L2_Jemuran_CabLow", 0.22, 7.02, z2 + 0.06, 2.28, 7.60, z2 + 0.675, col, pal["cabinet"], bevel=0.004)
    make_box(f"{tag}_L2_Jemuran_CabApron", 0.22, 7.54, z2 + 0.675, 2.28, 7.60, z2 + 0.84, col, pal["cabinet"], bevel=0.003)
    make_box(f"{tag}_L2_Jemuran_CabSideE", 0.97, 7.02, z2 + 0.675, 2.28, 7.60, z2 + 0.84, col, pal["cabinet"], bevel=0.003)
    make_box(f"{tag}_L2_Jemuran_CabToe", 0.24, 7.04, z2, 2.26, 7.56, z2 + 0.06, col, mats["black_metal"])
    # Counter split cleanly around sunken slop sink (X=0.40..0.96, Y=7.12..7.52)
    make_box(f"{tag}_L2_Jemuran_TopW", 0.22, 7.02, z2 + 0.84, 0.40, 7.60, z2 + 0.88, col, pal["stone_top"], bevel=0.003)
    make_box(f"{tag}_L2_Jemuran_TopE", 0.96, 7.02, z2 + 0.84, 2.28, 7.60, z2 + 0.88, col, pal["stone_top"], bevel=0.003)
    make_box(f"{tag}_L2_Jemuran_TopS", 0.40, 7.02, z2 + 0.84, 0.96, 7.12, z2 + 0.88, col, pal["stone_top"], bevel=0.003)
    make_box(f"{tag}_L2_Jemuran_TopN", 0.40, 7.52, z2 + 0.84, 0.96, 7.60, z2 + 0.88, col, pal["stone_top"], bevel=0.003)
    # Recessed 3D stainless slop sink basin + 180° curved gooseneck tap
    make_box(f"{tag}_L2_Jemuran_SinkFloor", 0.40, 7.12, z2 + 0.68, 0.96, 7.52, z2 + 0.695, col, mats["brushed_steel"])
    make_box(f"{tag}_L2_Jemuran_SinkW", 0.40, 7.12, z2 + 0.68, 0.415, 7.52, z2 + 0.882, col, mats["brushed_steel"])
    make_box(f"{tag}_L2_Jemuran_SinkE", 0.945, 7.12, z2 + 0.68, 0.96, 7.52, z2 + 0.882, col, mats["brushed_steel"])
    make_box(f"{tag}_L2_Jemuran_SinkS", 0.40, 7.12, z2 + 0.68, 0.96, 7.135, z2 + 0.882, col, mats["brushed_steel"])
    make_box(f"{tag}_L2_Jemuran_SinkN", 0.40, 7.505, z2 + 0.68, 0.96, 7.52, z2 + 0.882, col, mats["brushed_steel"])
    make_cylinder(f"{tag}_L2_Jemuran_SinkDrain", 0.68, 7.32, z2 + 0.694, 0.030, 0.006, col, mats["black_metal"], segs=14)
    g2_pts = [(0.68, 7.06, z2 + 0.88), (0.68, 7.06, z2 + 1.08)]
    for gk in range(11):
        ang = math.pi * (gk / 10.0)
        g2_pts.append((0.68, 7.06 + 0.09 * (1.0 - math.cos(ang)), z2 + 1.08 + 0.09 * math.sin(ang)))
    g2_pts.append((0.68, 7.24, z2 + 1.04))
    make_swept_tube(f"{tag}_L2_Jemuran_Gooseneck", g2_pts, 0.010, col, mats["brushed_steel"], segs=10)
    # Folded Clean Towel Stacks + Detergent & Softener Bottles + Woven Rattan Laundry Hamper
    for ti, (tz_off, tmat) in enumerate([(0.0, mats["linen_white"]), (0.055, mats["boucle_beige"]), (0.110, mats["linen_sage"])]):
        make_plush_cushion(f"{tag}_L2_Jemuran_FoldTowel_{ti}", 1.18, 7.12, z2 + 0.88 + tz_off, 1.56, 7.48, z2 + 0.935 + tz_off, col, tmat, puff=0.14)
    make_cylinder(f"{tag}_L2_Jemuran_Detergent1", 1.76, 7.20, z2 + 0.88, 0.052, 0.24, col, mats["white_lacquer"], segs=14, radius_top=0.036)
    make_cylinder(f"{tag}_L2_Jemuran_DetergentCap1", 1.76, 7.20, z2 + 1.12, 0.024, 0.04, col, mats["cotton_navy"], segs=12)
    make_cylinder(f"{tag}_L2_Jemuran_Softener2", 1.92, 7.22, z2 + 0.88, 0.046, 0.21, col, mats["linen_sage"], segs=14, radius_top=0.030)
    make_lathed_mesh(f"{tag}_L2_Jemuran_PinBowl", 2.10, 7.28, z2 + 0.88, [(0.055, 0.0), (0.082, 0.025), (0.088, 0.068), (0.080, 0.068), (0.050, 0.012)], col, mats["planter_ceramic"], segs=16)
    # Woven Rattan Laundry Basket overflowing with soft folded linens at (2.62, 7.34)
    make_lathed_mesh(
        f"{tag}_L2_Jemuran_RattanBasket", 2.62, 7.34, z2,
        [(0.19, 0.0), (0.22, 0.14), (0.24, 0.48), (0.225, 0.50), (0.21, 0.48), (0.18, 0.04)],
        col, mats["rattan"], segs=16
    )
    make_plush_cushion(f"{tag}_L2_Jemuran_BasketLinen", 2.42, 7.15, z2 + 0.36, 2.82, 7.52, z2 + 0.55, col, mats["linen_white"], puff=0.22)

    # E) Folding Ironing Board & Ceramic Steam Iron (X=3.05..4.15, Y=7.14..7.52)
    make_rounded_slab(f"{tag}_L2_Jemuran_IronBoard", 3.05, 7.16, z2 + 0.80, 4.15, 7.50, z2 + 0.84, 0.14, col, mats["linen_oatmeal"], segs=5)
    make_swept_tube(f"{tag}_L2_Jemuran_IronLeg1", [(3.22, 7.20, z2), (3.92, 7.20, z2 + 0.80)], 0.012, col, mats["black_metal"], segs=8)
    make_swept_tube(f"{tag}_L2_Jemuran_IronLeg2", [(3.92, 7.46, z2), (3.22, 7.46, z2 + 0.80)], 0.012, col, mats["black_metal"], segs=8)
    make_rounded_slab(f"{tag}_L2_Jemuran_SteamIron", 3.84, 7.25, z2 + 0.84, 4.06, 7.40, z2 + 0.94, 0.04, col, mats["white_lacquer"], segs=4)

    # =========================================================================
    # 2. RM-13 L2 SKY LOUNGE & FAMILY PAVILION (X: 4.984..8.944, Y: 5.20..11.50)
    # =========================================================================
    make_rounded_slab(f"{tag}_L2_Lounge_Rug", 5.38, 5.60, z2, 8.20, 8.35, z2 + 0.014, 0.06, col, pal["rug"], segs=4)
    # Plush 3-Seater Family Sofa along West Wall (X=5.12..6.04, Y=5.65..7.90 — 100% clear of Door D9 at Y=8.20..9.10!)
    make_box(f"{tag}_L2_Lounge_SofaBase", 5.12, 5.65, z2 + 0.06, 6.02, 7.90, z2 + 0.26, col, pal["wood"], bevel=0.01)
    make_plush_cushion(f"{tag}_L2_Lounge_SofaSeat1", 5.16, 5.70, z2 + 0.25, 6.04, 6.78, z2 + 0.45, col, pal["upholstery"], puff=0.18)
    make_plush_cushion(f"{tag}_L2_Lounge_SofaSeat2", 5.16, 6.80, z2 + 0.25, 6.04, 7.86, z2 + 0.45, col, pal["upholstery"], puff=0.18)
    make_plush_cushion(f"{tag}_L2_Lounge_SofaBack", 5.12, 5.68, z2 + 0.42, 5.36, 7.88, z2 + 0.82, col, pal["upholstery"], puff=0.20)
    make_plush_cushion(f"{tag}_L2_Lounge_Pillow1", 5.36, 5.88, z2 + 0.44, 5.62, 6.32, z2 + 0.74, col, pal["accent_pillow"], puff=0.26, rot_z=0.20)
    make_plush_cushion(f"{tag}_L2_Lounge_Pillow2", 5.36, 7.22, z2 + 0.44, 5.62, 7.66, z2 + 0.74, col, mats["linen_oatmeal"], puff=0.26, rot_z=-0.18)
    # Sculptural Round Travertine Coffee Table + Tea Tray & Ceramic Mugs
    make_cylinder(f"{tag}_L2_Lounge_TblDrum", 6.85, 6.78, z2, 0.24, 0.34, col, pal["wood_accent"], segs=16)
    make_cylinder(f"{tag}_L2_Lounge_TblTop", 6.85, 6.78, z2 + 0.34, 0.52, 0.036, col, pal["stone_top"], segs=16)
    make_rounded_slab(f"{tag}_L2_Lounge_Tray", 6.66, 6.60, z2 + 0.376, 7.04, 6.96, z2 + 0.392, 0.04, col, pal["wood"], segs=4)
    make_curved_mug(f"{tag}_L2_Lounge_Cup1", 6.78, 6.72, z2 + 0.392, col, mats["ceramic_white"], handle_angle=0.5)
    make_curved_mug(f"{tag}_L2_Lounge_Cup2", 6.92, 6.84, z2 + 0.392, col, mats["ceramic_white"], handle_angle=-1.1)
    # East Wall Floating Fluted Media Console + 55" OLED Screen + Acoustic Slat Accent
    make_box(f"{tag}_L2_Lounge_MediaSlat", 8.91, 5.75, z2, 8.944, 8.15, WALL2_TOP_Z - 0.08, col, pal["wood_accent"])
    make_box(f"{tag}_L2_Lounge_MediaCons", 8.50, 5.82, z2 + 0.22, 8.92, 8.08, z2 + 0.54, col, pal["wood"], bevel=0.008)
    make_box(f"{tag}_L2_Lounge_TV", 8.85, 6.18, z2 + 0.88, 8.90, 7.72, z2 + 1.78, col, mats["tv_screen"], bevel=0.006)
    # North Reading Nook + Coffee Bar Credenza under Window W7 (Y=10.95..11.46)
    make_box(f"{tag}_L2_Lounge_Credenza", 6.55, 10.96, z2 + 0.08, 8.78, 11.46, z2 + 0.62, col, pal["cabinet"], bevel=0.006)
    make_box(f"{tag}_L2_Lounge_CredTop", 6.54, 10.95, z2 + 0.62, 8.79, 11.47, z2 + 0.648, col, pal["stone_top"], bevel=0.004)
    make_lathed_mesh(f"{tag}_L2_Lounge_Kettle", 7.15, 11.20, z2 + 0.648, [(0.068, 0.0), (0.072, 0.06), (0.056, 0.14), (0.044, 0.16)], col, mats["black_metal"], segs=14)
    make_plush_cushion(f"{tag}_L2_Lounge_ChairSeat", 5.38, 10.12, z2 + 0.26, 6.12, 10.86, z2 + 0.45, col, pal["upholstery"], puff=0.18)
    make_plush_cushion(f"{tag}_L2_Lounge_ChairBack", 5.38, 10.68, z2 + 0.42, 6.12, 10.90, z2 + 0.86, col, pal["upholstery"], puff=0.20)
    build_potted_plant(f"{tag}_L2_Lounge_Fig", 8.58, 10.55, z2, 0.18, 1.55, col, pal["pot"])
    # S-Fold Sheer Curtains flanking L2 Sliding Door D10 & Panoramic Window W7
    for cx0, cx1, cy_c, cn in [
        (5.12, 5.56, 5.30, "L2_Curtain_Balc_W"),
        (8.34, 8.80, 5.30, "L2_Curtain_Balc_E"),
        (5.22, 5.68, 11.38, "L2_Curtain_Rear_W"),
        (8.22, 8.68, 11.38, "L2_Curtain_Rear_E"),
    ]:
        make_pleated_curtain(f"{tag}_{cn}", cx0, cx1, cy_c, z2 + 0.02, WALL2_TOP_Z - 0.06, col, pal["curtain"], waves=4)

    # =========================================================================
    # 3. EXT-05 L2 FRONT SKY BALCONY (X: 3.164..8.944, Y: 2.04..5.00)
    # =========================================================================
    for bx_c, b_tag in [(3.98, "W"), (5.38, "E")]:
        make_box(f"{tag}_L2_Balc_ChairFrame_{b_tag}", bx_c - 0.36, 3.00, z2 + 0.06, bx_c + 0.36, 3.74, z2 + 0.26, col, mats["walnut"], bevel=0.01)
        make_plush_cushion(f"{tag}_L2_Balc_ChairSeat_{b_tag}", bx_c - 0.33, 3.03, z2 + 0.26, bx_c + 0.33, 3.71, z2 + 0.44, col, pal["upholstery"], puff=0.18)
        make_plush_cushion(f"{tag}_L2_Balc_ChairBack_{b_tag}", bx_c - 0.33, 3.52, z2 + 0.42, bx_c + 0.33, 3.73, z2 + 0.78, col, pal["upholstery"], puff=0.20)
    make_cylinder(f"{tag}_L2_Balc_BistroBase", 4.68, 3.36, z2, 0.16, 0.03, col, mats["black_metal"], segs=16)
    make_cylinder(f"{tag}_L2_Balc_BistroStem", 4.68, 3.36, z2 + 0.03, 0.022, 0.44, col, mats["black_metal"], segs=12)
    make_cylinder(f"{tag}_L2_Balc_BistroTop", 4.68, 3.36, z2 + 0.47, 0.28, 0.032, col, mats["travertine"], segs=16)
    make_curved_mug(f"{tag}_L2_Balc_Cup1", 4.62, 3.32, z2 + 0.502, col, mats["ceramic_white"], handle_angle=0.8)
    make_curved_mug(f"{tag}_L2_Balc_Cup2", 4.76, 3.42, z2 + 0.502, col, mats["ceramic_white"], handle_angle=-1.4)
    # Lush tropical planter shrubs along South-East Front Balcony trough!
    for pl_i, pl_x in enumerate((6.65, 7.55, 8.42)):
        sh_obj = make_tropical_shrub(f"{tag}_L2_Balc_PlanterShrub_{pl_i}", pl_x, 2.30, 0.34, col, seed=510 + pl_i * 13)
        sh_obj.location = (pl_x, 2.30, z2 + 0.38)


for sname, spal in STYLE_PALETTES.items():
    build_style_furniture(sname, spal)

# ---------------------------------------------------------------------------
# 10. LUSH TROPICAL LANDSCAPE, BAMBOO PRIVACY GROVE & CONTEXT
# ---------------------------------------------------------------------------
make_box("Land_Perimeter_North", -0.15, SITE_D, 0.0, SITE_W + 0.15, SITE_D + 0.15, 2.20, "Landscape", mats["ext_stucco"])
# Horizontal slatted teak architectural accent atop rear courtyard wall!
for sl_i, sl_z in enumerate([2.26, 2.38, 2.50, 2.62]):
    make_box(f"Land_RearTimberSlat_{sl_i}", 0.0, SITE_D + 0.02, sl_z, SITE_W, SITE_D + 0.10, sl_z + 0.065, "Landscape", mats["walnut"])

make_box("Land_Perimeter_West_Rear", -0.15, 11.70, 0.0, 0.0, SITE_D, 2.20, "Landscape", mats["ext_stucco"])
make_box("Land_Perimeter_East_Rear", SITE_W, 11.70, 0.0, SITE_W + 0.15, SITE_D, 2.20, "Landscape", mats["ext_stucco"])
make_box("Land_Perimeter_West_Carport", -0.15, 0.0, 0.0, 0.0, 5.00, 1.90, "Landscape", mats["ext_stucco"])
make_box("Land_Perimeter_East_Front", SITE_W, 0.0, 0.0, SITE_W + 0.15, 1.90, 1.60, "Landscape", mats["ext_stucco"])
make_box("Land_Front_LowWall", 5.55, 0.0, 0.0, SITE_W, 0.20, 0.68, "Landscape", mats["ext_stucco"], bevel=0.01)
make_box("Land_Front_LowWall_Cap", 5.53, -0.02, 0.68, SITE_W + 0.02, 0.22, 0.72, "Landscape", mats["roof_coping"])

# Resort-style tropical bamboo privacy screen along rear terrace wall (clear of West staircase!)
make_bamboo_screen("Land_RearBambooGrove", 5.85, 8.85, 13.30, "Landscape", count=9)

# Exterior ground context (excluded from architecture.glb so Three.js manages horizon cleanly)
make_box("Context_Sidewalk", -12.0, -1.60, -0.08, SITE_W + 12.0, 0.0, 0.0, "Landscape", mats["sidewalk"])
make_box("Context_Street_Asphalt", -14.0, -8.50, -0.16, SITE_W + 14.0, -1.60, -0.06, "Landscape", mats["street_asphalt"])
make_box("Context_Opposite_Sidewalk", -14.0, -9.80, -0.08, SITE_W + 14.0, -8.50, 0.0, "Landscape", mats["sidewalk"])
make_box("Context_Opposite_GardenWall", -10.0, -10.20, 0.0, SITE_W + 10.0, -9.85, 1.85, "Landscape", mats["ext_stucco"])
make_box("Context_Opposite_WallCap", -10.0, -10.24, 1.85, SITE_W + 10.0, -9.81, 1.92, "Landscape", mats["roof_coping"])
make_box("Context_Opposite_Villa", 1.5, -14.8, 0.0, 12.5, -10.6, 3.8, "Landscape", mats["ext_stucco"])
make_realistic_tree("Context_StreetTree_1", 5.8, -9.2, 1.15, 3.6, "Landscape", maple=False, seed=401)
make_realistic_tree("Context_StreetTree_2", 9.6, -9.2, 1.25, 3.9, "Landscape", maple=False, seed=402)
make_box("Context_Surrounding_Ground", -14.0, -15.0, -0.18, SITE_W + 14.0, SITE_D + 12.0, -0.02, "Landscape", mats["lawn"])
make_box("Context_Neighbor_West", -7.5, 2.5, -0.02, -0.35, 12.5, 3.6, "Landscape", mats["ext_stucco"])
make_box("Context_Neighbor_East", SITE_W + 0.35, 2.5, -0.02, SITE_W + 7.5, 12.5, 3.6, "Landscape", mats["ext_stucco"])

# Stepping Stones & TRUE Branching Trees / Tropical Frond Shrubs
for idx_l, item in enumerate(spec["landscaping"]):
    lid = item["id"]
    if item["kind"] == "stepping_stone":
        x0, y0, x1, y1 = [c * M for c in item["rect"]]
        make_box(f"Land_{lid}", x0, y0, 0.01, x1, y1, 0.055, "Landscape", mats["stepping_stone"], bevel=0.008)
    else:
        cx, cy = item["center"][0] * M, item["center"][1] * M
        r = item["radius_mm"] * M
        if item["kind"] == "tree":
            th = 3.1 if lid == "L-TREE-1" else 2.65
            is_maple = "Maple" in item.get("name", "")
            make_realistic_tree(f"Land_{lid}", cx, cy, r, th, "Landscape", maple=is_maple, seed=100 + idx_l * 17)
        else:
            make_tropical_shrub(f"Land_{lid}", cx, cy, r, "Landscape", seed=200 + idx_l * 19)

# ---------------------------------------------------------------------------
# 11. ARCHITECTURAL LIGHTING & PHYSICAL SKY
# ---------------------------------------------------------------------------
world = bpy.data.worlds.new("World_Tropical_Daylight")
scene.world = world
wnt = world.node_tree
wnt.nodes.clear()
w_out = wnt.nodes.new("ShaderNodeOutputWorld")
w_bg = wnt.nodes.new("ShaderNodeBackground")
w_sky = wnt.nodes.new("ShaderNodeTexSky")
w_sky.sky_type = "MULTIPLE_SCATTERING"
w_sky.sun_disc = True
w_sky.sun_elevation = math.radians(38.0)
w_sky.sun_rotation = math.radians(142.0)
w_sky.air_density = 1.15
if hasattr(w_sky, "aerosol_density"):
    w_sky.aerosol_density = 1.25
if hasattr(w_sky, "dust_density"):
    w_sky.dust_density = 1.25
w_bg.inputs["Strength"].default_value = 0.085
wnt.links.new(w_sky.outputs["Color"], w_bg.inputs["Color"])
wnt.links.new(w_bg.outputs["Background"], w_out.inputs["Surface"])


def add_light(name, ltype, loc, energy, color=(1.0, 0.90, 0.76), size=0.25, rot=(0, 0, 0)):
    ldata = bpy.data.lights.new(name=name, type=ltype)
    ldata.energy = energy
    ldata.color = color
    if ltype == "AREA":
        ldata.size = size
    elif ltype == "POINT":
        ldata.shadow_soft_size = size
    elif ltype == "SPOT":
        ldata.shadow_soft_size = size
        ldata.spot_size = math.radians(85)
        ldata.spot_blend = 0.55
    lobj = bpy.data.objects.new(name=name, object_data=ldata)
    lobj.location = loc
    lobj.rotation_euler = rot
    return link_obj(lobj, "Lighting")


downlight_coords = [
    ("DL_Living_1", 6.45, 9.50, WALL_TOP_Z),
    ("DL_Living_2", 7.95, 10.40, WALL_TOP_Z),
    ("DL_Dining", 6.15, 6.80, WALL_TOP_Z),
    ("DL_Kitchen", 7.80, 6.60, WALL_TOP_Z),
    ("DL_Foyer", 4.65, 2.85, WALL_TOP_Z),
    ("DL_Hall", 4.65, 8.55, WALL_TOP_Z),
    ("DL_Master_1", 1.95, 10.00, WALL_TOP_Z),
    ("DL_Master_2", 3.10, 9.60, WALL_TOP_Z),
    ("DL_Bed2", 1.65, 6.70, WALL_TOP_Z),
    ("DL_Bed3", 7.50, 3.60, WALL_TOP_Z),
    ("DL_Ensuite", 4.60, 10.20, FLOOR_Z + WET_CEIL_H),
    ("DL_SharedBath", 4.00, 6.10, FLOOR_Z + WET_CEIL_H),
    ("DL_Laundry", 4.00, 4.30, FLOOR_Z + WET_CEIL_H),
    # Level 2 Sky Lounge Recessed Ceiling Downlights
    ("L2_DL_Lounge_1", 6.20, 6.80, WALL2_TOP_Z - 0.04),
    ("L2_DL_Lounge_2", 7.75, 6.80, WALL2_TOP_Z - 0.04),
    ("L2_DL_Lounge_3", 6.95, 10.10, WALL2_TOP_Z - 0.04),
]

dl_trim_mesh = None
for dname, dx, dy, dz in downlight_coords:
    make_cylinder(f"Fixture_{dname}_Bezel", dx, dy, dz - 0.014, 0.074, 0.014, "Lighting", mats["black_metal"], segs=18)
    make_cylinder(f"Fixture_{dname}", dx, dy, dz - 0.017, 0.058, 0.016, "Lighting", mats["emit_warm"], segs=16)
    add_light(f"Light_{dname}", "AREA", (dx, dy, dz - 0.04), energy=40.0, color=(1.0, 0.89, 0.74), size=0.22)

# Level 2 Tempat Jemuran Waterproof Pergola LED Bars & Front Balcony Exterior Sconces
make_box("Fixture_L2_Jemuran_Bar1", 1.10, 8.40, WALL2_TOP_Z - 0.14, 3.60, 8.46, WALL2_TOP_Z - 0.11, "Lighting", mats["black_metal"])
make_box("Fixture_L2_Jemuran_Bar1_Glow", 1.14, 8.41, WALL2_TOP_Z - 0.148, 3.56, 8.45, WALL2_TOP_Z - 0.138, "Lighting", mats["emit_warm"])
make_box("Fixture_L2_Jemuran_Bar2", 1.10, 10.30, WALL2_TOP_Z - 0.14, 3.60, 10.36, WALL2_TOP_Z - 0.11, "Lighting", mats["black_metal"])
make_box("Fixture_L2_Jemuran_Bar2_Glow", 1.14, 10.31, WALL2_TOP_Z - 0.148, 3.56, 10.35, WALL2_TOP_Z - 0.138, "Lighting", mats["emit_warm"])
for sc2_n, sc2_x, sc2_y in [("Arch_Sconce_L2Balcony_1", 5.26, 4.94), ("Arch_Sconce_L2Balcony_2", 8.65, 4.94)]:
    make_cylinder(sc2_n, sc2_x, sc2_y, FLOOR2_Z + 1.95, 0.036, 0.28, "Lighting", mats["black_metal"], segs=12)
    make_cylinder(f"{sc2_n}_GlowT", sc2_x, sc2_y, FLOOR2_Z + 2.225, 0.032, 0.012, "Lighting", mats["emit_warm"], segs=10)
    make_cylinder(f"{sc2_n}_GlowB", sc2_x, sc2_y, FLOOR2_Z + 1.942, 0.032, 0.012, "Lighting", mats["emit_warm"], segs=10)

# Interactive Architectural Wall Light Switch Plates (mounted at +1.12m beside each room door!)
wall_switches = [
    ("SwitchPlate_Foyer", 5.84, 2.10, 5.93, 2.114, FLOOR_Z),
    ("SwitchPlate_Studio", 6.084, 4.02, 6.098, 4.11, FLOOR_Z),
    ("SwitchPlate_Living", 5.490, 9.20, 5.504, 9.29, FLOOR_Z),
    ("SwitchPlate_Dining", 4.864, 6.94, 4.878, 7.03, FLOOR_Z),
    ("SwitchPlate_Kitchen", 6.82, 5.20, 6.91, 5.214, FLOOR_Z),
    ("SwitchPlate_Master", 3.786, 9.18, 3.800, 9.27, FLOOR_Z),
    ("SwitchPlate_Ensuite", 3.920, 10.24, 3.934, 10.33, FLOOR_Z),
    ("SwitchPlate_Bed2", 3.110, 7.08, 3.124, 7.17, FLOOR_Z),
    ("SwitchPlate_SharedBath", 4.730, 6.90, 4.744, 6.99, FLOOR_Z),
    ("SwitchPlate_Laundry", 4.730, 3.84, 4.744, 3.93, FLOOR_Z),
    ("SwitchPlate_L2Jemuran", 4.850, 9.18, 4.864, 9.27, FLOOR2_Z),
    ("SwitchPlate_L2Lounge", 4.984, 9.18, 4.998, 9.27, FLOOR2_Z),
]
for sw_name, sx0, sy0, sx1, sy1, sw_z in wall_switches:
    make_box(sw_name, sx0, sy0, sw_z + 1.08, sx1, sy1, sw_z + 1.17, "Lighting", mats["black_metal"], bevel=0.003)
    make_box(f"{sw_name}_LED", (sx0 + sx1) * 0.5 - 0.008, (sy0 + sy1) * 0.5 - 0.008, sw_z + 1.12, (sx0 + sx1) * 0.5 + 0.008, (sy0 + sy1) * 0.5 + 0.008, sw_z + 1.132, "Lighting", mats["emit_warm"])

add_light("Light_Dining_Pendant", "AREA", (6.15, 6.80, FLOOR_Z + 1.95), energy=65.0, color=(1.0, 0.86, 0.66), size=0.55)
add_light("Light_Master_Bedside_S", "POINT", (0.41, 9.05, FLOOR_Z + 0.78), energy=18.0, color=(1.0, 0.83, 0.60), size=0.14)
add_light("Light_Master_Bedside_N", "POINT", (0.41, 11.30, FLOOR_Z + 0.78), energy=18.0, color=(1.0, 0.83, 0.60), size=0.14)
add_light("Light_Outdoor_FrontPorch", "AREA", (4.70, 1.60, WALL_TOP_Z + 0.04), energy=55.0, color=(1.0, 0.85, 0.64), size=0.35)
add_light("Light_Outdoor_Terrace_1", "AREA", (6.80, 12.25, WALL_TOP_Z + 0.04), energy=60.0, color=(1.0, 0.84, 0.62), size=0.40)
add_light("Light_Outdoor_Terrace_2", "AREA", (8.20, 12.25, WALL_TOP_Z + 0.04), energy=60.0, color=(1.0, 0.84, 0.62), size=0.40)
add_light("Light_Outdoor_Carport", "AREA", (1.55, 2.50, 2.74), energy=48.0, color=(1.0, 0.89, 0.74), size=0.60)
# Warm architectural sconce down-spots on front & rear facades
add_light("Light_Outdoor_SconceF1", "SPOT", (3.66, 1.80, 2.08), energy=45.0, color=(1.0, 0.82, 0.56), size=0.06)
add_light("Light_Outdoor_SconceF2", "SPOT", (6.18, 1.80, 2.08), energy=45.0, color=(1.0, 0.82, 0.56), size=0.06)

# ---------------------------------------------------------------------------
# 12. COLLISION MESHES (HEIGHT-ISOLATED LEVEL 1 & LEVEL 2 GUARDRAILS + WALLS)
# ---------------------------------------------------------------------------
make_box("Col_Site_South", 0.0, -0.15, 0.0, SITE_W, 0.0, 6.8, "Collision_Meshes")
make_box("Col_Site_North", 0.0, SITE_D, 0.0, SITE_W, SITE_D + 0.15, 6.8, "Collision_Meshes")
make_box("Col_Site_West", -0.15, 0.0, 0.0, 0.0, SITE_D, 6.8, "Collision_Meshes")
make_box("Col_Site_East", SITE_W, 0.0, 0.0, SITE_W + 0.15, SITE_D, 6.8, "Collision_Meshes")
make_box("Col_Floor_Ground", 0.0, 0.0, -0.10, SITE_W, SITE_D, FLOOR_Z, "Collision_Meshes")
make_box("Col_Kitchen_E", 8.324, 5.20, FLOOR_Z, 8.944, 8.20, FLOOR_Z + 0.95, "Collision_Meshes")
make_box("Col_Kitchen_S", 6.984, 5.20, FLOOR_Z, 8.324, 5.82, FLOOR_Z + 0.95, "Collision_Meshes")
# Level 2 Collision Walls & Safety Guardrails (Z = FLOOR2_Z..WALL2_TOP_Z so L1 walking is never obstructed!)
make_box("Col_L2_Jemuran_W", 0.0, 6.80, FLOOR2_Z, 0.20, 11.70, WALL2_TOP_Z, "Collision_Meshes")
make_box("Col_L2_Jemuran_S", 0.20, 6.80, FLOOR2_Z, 4.864, 7.00, WALL2_TOP_Z, "Collision_Meshes")
make_box("Col_L2_Jemuran_N_Rail", 1.85, 11.50, FLOOR2_Z, 4.864, 11.65, FLOOR2_Z + 1.50, "Collision_Meshes")
make_box("Col_L2_Landing_W", 0.0, 11.70, FLOOR2_Z, 0.24, 13.45, FLOOR2_Z + 1.50, "Collision_Meshes")
make_box("Col_L2_Landing_N", 0.20, 13.34, FLOOR2_Z, 1.95, 13.48, FLOOR2_Z + 1.50, "Collision_Meshes")
make_box("Col_L2_Lounge_E", 8.944, 2.00, FLOOR2_Z, SITE_W, 11.70, WALL2_TOP_Z, "Collision_Meshes")
make_box("Col_L2_Lounge_N", 4.864, 11.50, FLOOR2_Z, 8.944, 11.70, WALL2_TOP_Z, "Collision_Meshes")
make_box("Col_L2_Lounge_W_S", 4.864, 5.00, FLOOR2_Z, 4.984, 8.20, WALL2_TOP_Z, "Collision_Meshes")
make_box("Col_L2_Lounge_W_N", 4.864, 9.10, FLOOR2_Z, 4.984, 11.50, WALL2_TOP_Z, "Collision_Meshes")
make_box("Col_L2_Lounge_S_W", 4.984, 5.00, FLOOR2_Z, 5.55, 5.20, WALL2_TOP_Z, "Collision_Meshes")
make_box("Col_L2_Lounge_S_E", 8.35, 5.00, FLOOR2_Z, 8.944, 5.20, WALL2_TOP_Z, "Collision_Meshes")
make_box("Col_L2_Balcony_S", 3.164, 1.96, FLOOR2_Z, 8.96, 2.10, FLOOR2_Z + 1.50, "Collision_Meshes")
make_box("Col_L2_Balcony_W", 3.10, 2.00, FLOOR2_Z, 3.24, 6.80, FLOOR2_Z + 1.50, "Collision_Meshes")

for obj in cols["Collision_Meshes"].objects:
    obj.hide_render = True

# ---------------------------------------------------------------------------
# 13. TOUR WAYPOINTS & CAMERAS
# ---------------------------------------------------------------------------
waypoints_out = []
for wp in spec["walkthrough_waypoints"]:
    px, py = wp["position_mm"][0] * M, wp["position_mm"][1] * M
    tx, ty = wp["look_at_mm"][0] * M, wp["look_at_mm"][1] * M
    if wp.get("floor", 1) == 2:
        base_z = FLOOR2_Z
    else:
        base_z = 0.05 if wp["room"].startswith("EXT-") else FLOOR_Z
    pz, tz = base_z + 1.65, base_z + 1.40

    e_pos = bpy.data.objects.new(f"Waypoint_{wp['id']}", None)
    e_pos.empty_display_type = "PLAIN_AXES"
    e_pos.empty_display_size = 0.35
    e_pos.location = (px, py, pz)
    link_obj(e_pos, "Tour_Waypoints")

    e_tgt = bpy.data.objects.new(f"WaypointTarget_{wp['id']}", None)
    e_tgt.empty_display_type = "SPHERE"
    e_tgt.empty_display_size = 0.12
    e_tgt.location = (tx, ty, tz)
    link_obj(e_tgt, "Tour_Waypoints")

    waypoints_out.append({
        "id": wp["id"],
        "name": wp["name"],
        "room": wp["room"],
        "eye_height_m": 1.65,
        "blender_position": [round(px, 4), round(py, 4), round(pz, 4)],
        "blender_look_at": [round(tx, 4), round(ty, 4), round(tz, 4)],
        "threejs_position": [round(px, 4), round(pz, 4), round(-py, 4)],
        "threejs_look_at": [round(tx, 4), round(tz, 4), round(-ty, 4)],
    })


def add_camera(name, loc, target, lens=28.0, ortho=False, ortho_scale=16.5):
    cdata = bpy.data.cameras.new(name)
    cdata.lens = lens
    cdata.clip_start = 0.05
    cdata.clip_end = 250.0
    if ortho:
        cdata.type = "ORTHO"
        cdata.ortho_scale = ortho_scale
    cobj = bpy.data.objects.new(name, cdata)
    cobj.location = Vector(loc)
    direction = Vector(target) - Vector(loc)
    cobj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return link_obj(cobj, "Cameras")


cam_ext_hero = add_camera("Cam_Exterior_Hero", (10.2, -5.8, 2.25), (4.6, 3.8, 1.75), lens=26.0)
cam_ext_rear = add_camera("Cam_Exterior_Rear", (4.95, 13.15, 1.48), (7.65, 10.60, 1.32), lens=22.0)
cam_int_living = add_camera("Cam_Interior_Living", (5.75, 5.55, FLOOR_Z + 1.48), (7.45, 11.40, FLOOR_Z + 1.25), lens=21.0)
cam_int_master = add_camera("Cam_Interior_Master", (3.55, 8.65, FLOOR_Z + 1.44), (1.10, 10.60, FLOOR_Z + 1.12), lens=22.0)
cam_int_studio = add_camera("Cam_Interior_Studio", (6.75, 4.65, FLOOR_Z + 1.42), (7.65, 2.25, FLOOR_Z + 1.05), lens=20.0)
cam_int_dining = add_camera("Cam_Interior_KitchenDining", (5.55, 10.85, FLOOR_Z + 1.48), (7.65, 5.75, FLOOR_Z + 1.15), lens=22.0)
cam_dollhouse = add_camera("Cam_Dollhouse_Ortho", (16.5, -5.5, 18.5), (4.57, 6.75, 1.20), ortho=True, ortho_scale=16.2)
cam_fps = add_camera("Cam_FirstPerson", (4.70, 2.80, FLOOR_Z + 1.65), (6.00, 7.20, FLOOR_Z + 1.50), lens=26.0)
scene.camera = cam_ext_hero

# ---------------------------------------------------------------------------
# 14. VALIDATION, SAVE `house.blend`, EXPORT GLBs & JSON CONFIGS
# ---------------------------------------------------------------------------
def world_bounds_of_collection(col_name):
    mins = Vector((1e9, 1e9, 1e9))
    maxs = Vector((-1e9, -1e9, -1e9))
    for obj in cols[col_name].objects:
        if obj.type != "MESH":
            continue
        for corner in obj.bound_box:
            wc = obj.matrix_world @ Vector(corner)
            for k in range(3):
                mins[k] = min(mins[k], wc[k])
                maxs[k] = max(maxs[k], wc[k])
    return mins, maxs


bpy.context.view_layer.update()
fl_min, fl_max = world_bounds_of_collection("Floors")
wl_min, wl_max = world_bounds_of_collection("Walls")
assert abs((fl_max.x - fl_min.x) - SITE_W) < 0.002, f"Site X mismatch: {fl_max.x - fl_min.x}"
assert abs((fl_max.y - fl_min.y) - SITE_D) < 0.002, f"Site Y mismatch: {fl_max.y - fl_min.y}"
assert abs((wl_max.z - wl_min.z) - (WALL2_TOP_Z - FLOOR_Z)) < 0.02, f"2-story wall height mismatch: {wl_max.z - wl_min.z}"
print(f"3D 2-STORY VALIDATION PASSED: Site={fl_max.x - fl_min.x:.3f}m x {fl_max.y - fl_min.y:.3f}m | 2-Story Height={wl_max.z - wl_min.z:.3f}m")


def bake_cycles_architectural_ao():
    """
    Bakes true Cycles Metal GPU Ambient Occlusion into a shared 2048x2048 atlas on UVMap_AO (TEXCOORD_1)
    across all static architectural walls, floors, ceilings, stairs & pergola beams — giving Three.js
    real ray-traced corner & ceiling GI occlusion at ZERO runtime FPS cost!
    """
    print("Baking Cycles GPU Architectural Ambient Occlusion (2048x2048 UVMap_AO)...")
    # Temporarily hide furniture, doors, windows & landscape so AO strictly bakes clean permanent architecture
    temp_hidden = []
    for cname in ("Furniture_Modern", "Furniture_Scandinavian", "Furniture_WarmLuxury", "Doors", "Windows", "Landscape"):
        for o in cols[cname].objects:
            temp_hidden.append((o, o.hide_render, o.hide_viewport))
            o.hide_render = True
            o.hide_viewport = True

    bake_objs = []
    for cname in ("Walls", "Floors", "Ceilings", "Architecture"):
        for o in cols[cname].objects:
            if o.type != "MESH" or not o.data or len(o.data.polygons) == 0:
                continue
            if o.name.startswith("Context_"):
                continue
            mat0 = o.data.materials[0] if len(o.data.materials) > 0 else None
            if mat0 and any(k in mat0.name for k in ("Glass", "Light_", "Mirror")):
                continue
            bake_objs.append(o)

    if not bake_objs:
        return

    # Clone shared materials strictly for baked architectural shells so Furniture_* materials stay untouched
    ao_mat_map = {}
    for o in bake_objs:
        if len(o.data.materials) == 0:
            continue
        orig_m = o.data.materials[0]
        if orig_m.name not in ao_mat_map:
            cm = orig_m.copy()
            cm.name = f"{orig_m.name}_ArchAO"
            ao_mat_map[orig_m.name] = cm
        o.data.materials[0] = ao_mat_map[orig_m.name]

    # Create UVMap_AO (TEXCOORD_1) on every architectural mesh & pack cleanly in Multi-Object Edit Mode
    bpy.ops.object.select_all(action="DESELECT")
    for o in bake_objs:
        o.hide_viewport = False
        o.hide_render = False
        if "UVMap_AO" not in o.data.uv_layers:
            if len(o.data.uv_layers) == 0:
                o.data.uv_layers.new(name="UVMap")
            uv_ao = o.data.uv_layers.new(name="UVMap_AO")
        else:
            uv_ao = o.data.uv_layers["UVMap_AO"]
        o.data.uv_layers.active = uv_ao
        o.data.uv_layers[0].active_render = True
        o.select_set(True)
    bpy.context.view_layer.objects.active = bake_objs[0]

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.012, area_weight=0.25)
    bpy.ops.object.mode_set(mode="OBJECT")

    # Allocate 1024x1024 Non-Color AO atlas (crisp smooth GI/AO + ultra-light WebP!)
    ao_img = bpy.data.images.new("Arch_AO_Baked", width=1024, height=1024, alpha=False)
    ao_img.colorspace_settings.name = "Non-Color"

    gltf_ng = bpy.data.node_groups.get("glTF Material Output")
    if gltf_ng is None:
        gltf_ng = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
        gltf_ng.interface.new_socket(name="Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")

    for cm in ao_mat_map.values():
        nt = cm.node_tree
        uv_node = nt.nodes.new("ShaderNodeUVMap")
        uv_node.uv_map = "UVMap_AO"
        uv_node.location = (-520, -560)
        tex_node = nt.nodes.new("ShaderNodeTexImage")
        tex_node.image = ao_img
        tex_node.location = (-260, -560)
        nt.links.new(uv_node.outputs["UV"], tex_node.inputs["Vector"])
        g_out = nt.nodes.new("ShaderNodeGroup")
        g_out.node_tree = gltf_ng
        g_out.location = (260, -560)
        nt.links.new(tex_node.outputs["Color"], g_out.inputs["Occlusion"])

    # Join temporary duplicate copies into ONE single bake proxy mesh so Cycles Metal GPU bakes in ONE 3-second pass!
    # CRITICAL: Use a local short-range ShaderNodeAmbientOcclusion (distance=0.60m, clamped 0.44..1.00) emitted into
    # BAKE_TYPE='EMIT' instead of infinite-distance BAKE_TYPE='AO' — prevents closed rooms & ceilings from baking black!
    bake_mat = bpy.data.materials.new("Temp_AO_BakeMat")
    bake_mat.use_nodes = True
    b_nt = bake_mat.node_tree
    b_nt.nodes.clear()
    b_out = b_nt.nodes.new("ShaderNodeOutputMaterial")
    b_emit = b_nt.nodes.new("ShaderNodeEmission")
    b_ao = b_nt.nodes.new("ShaderNodeAmbientOcclusion")
    b_ao.samples = 16
    b_ao.inputs["Distance"].default_value = 0.60
    b_map = b_nt.nodes.new("ShaderNodeMapRange")
    b_map.clamp = True
    b_map.inputs["From Min"].default_value = 0.0
    b_map.inputs["From Max"].default_value = 1.0
    b_map.inputs["To Min"].default_value = 0.44
    b_map.inputs["To Max"].default_value = 1.00
    b_nt.links.new(b_ao.outputs["AO"], b_map.inputs["Value"])
    b_nt.links.new(b_map.outputs["Result"], b_emit.inputs["Color"])
    b_nt.links.new(b_emit.outputs["Emission"], b_out.inputs["Surface"])

    b_tex = b_nt.nodes.new("ShaderNodeTexImage")
    b_tex.image = ao_img
    b_tex.select = True
    b_nt.nodes.active = b_tex

    bpy.ops.object.select_all(action="DESELECT")
    proxy_objs = []
    for o in bake_objs:
        dup = o.copy()
        dup.data = o.data.copy()
        dup.data.materials.clear()
        dup.data.materials.append(bake_mat)
        scene.collection.objects.link(dup)
        dup.select_set(True)
        proxy_objs.append(dup)
        # Hide original during single-pass proxy bake so rays don't self-intersect duplicates!
        o.hide_render = True
        o.hide_viewport = True

    bpy.context.view_layer.objects.active = proxy_objs[0]
    bpy.ops.object.join()
    proxy_merged = bpy.context.view_layer.objects.active
    proxy_merged.data.uv_layers.active = proxy_merged.data.uv_layers["UVMap_AO"]

    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.bake.margin = 6
    scene.render.bake.use_clear = True
    bpy.ops.object.bake(type="EMIT")

    ao_path = TEX_DIR / "arch_ao_baked.png"
    ao_img.filepath_raw = str(ao_path)
    ao_img.file_format = "PNG"
    ao_img.save()
    ao_img.pack()
    print(f"Baked single-pass Cycles GPU Architectural AO atlas -> {ao_path} ({ao_path.stat().st_size / 1024:.1f} KB)")

    # Remove temporary proxy & restore all objects cleanly
    bpy.data.objects.remove(proxy_merged, do_unlink=True)
    bpy.data.materials.remove(bake_mat, do_unlink=True)
    for o in bake_objs:
        o.hide_render = False
        o.hide_viewport = False
    bpy.ops.object.select_all(action="DESELECT")
    for o, hr, hv in temp_hidden:
        o.hide_render = hr
        o.hide_viewport = hv


bake_cycles_architectural_ao()


def poly_stats(col_names):
    tris, objs = 0, 0
    for cn in col_names:
        for obj in cols[cn].objects:
            if obj.type == "MESH":
                objs += 1
                tris += sum(max(0, len(p.vertices) - 2) for p in obj.data.polygons)
    return {"objects": objs, "triangles": tris}


def set_style_visibility(active_style):
    for sname, spal in STYLE_PALETTES.items():
        show = (sname == active_style)
        c = cols[spal["col"]]
        c.hide_viewport = not show
        c.hide_render = not show
        for obj in c.objects:
            obj.hide_viewport = not show
            obj.hide_render = not show


set_style_visibility("WarmLuxury")
blend_path = OUT_DIR / "house.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
print(f"Saved Blender project: {blend_path}")


def export_collections_glb(col_names, filepath: Path, exclude_context=False):
    prev_state = []
    bpy.ops.object.select_all(action="DESELECT")
    for cn in col_names:
        c = cols[cn]
        prev_state.append((c, c.hide_viewport, c.hide_render))
        c.hide_viewport = False
        c.hide_render = False
        for obj in c.objects:
            if exclude_context and obj.name.startswith("Context_"):
                continue
            prev_state.append((obj, obj.hide_viewport, obj.hide_render))
            obj.hide_viewport = False
            obj.hide_render = False
            obj.select_set(True)

    bpy.ops.export_scene.gltf(
        filepath=str(filepath),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=True,
        export_texcoords=True,
        export_normals=True,
        export_materials="EXPORT",
        export_image_format="WEBP",
        export_image_quality=80,
        export_meshopt_compression_enable=True,
        export_lights=False,
        export_cameras=False,
    )
    bpy.ops.object.select_all(action="DESELECT")
    for item, hv, hr in prev_state:
        item.hide_viewport = hv
        item.hide_render = hr
    print(f"Exported {filepath.name}: {filepath.stat().st_size / 1024:.1f} KB | {poly_stats(col_names)}")


arch_cols = ["Architecture", "Walls", "Floors", "Ceilings", "Roof", "Doors", "Windows", "Lighting", "Landscape", "Tour_Waypoints"]
export_collections_glb(arch_cols, OUT_DIR / "architecture.glb", exclude_context=True)
export_collections_glb(["Furniture_Modern"], OUT_DIR / "furniture-modern.glb")
export_collections_glb(["Furniture_Scandinavian"], OUT_DIR / "furniture-scandinavian.glb")
export_collections_glb(["Furniture_WarmLuxury"], OUT_DIR / "furniture-warm-luxury.glb")
export_collections_glb(["Collision_Meshes"], OUT_DIR / "collision.glb")

scene_config = {
    "project": spec["meta"]["project_name"],
    "units": "meters (1 Three.js unit = 1 Blender unit = 1 m)",
    "coordinate_convention": "glTF 2.0 Right-Handed Y-Up (threeX = x, threeY = z, threeZ = -y)",
    "site_bounds_m": {
        "width_x": SITE_W,
        "depth_z": SITE_D,
        "total_land_area_m2": spec["area_summary"]["total_land_area_m2"],
        "building_footprint_m2": spec["area_summary"]["building_footprint_m2"],
        "usable_interior_m2": spec["area_summary"]["usable_interior_floor_area_m2"],
        "finished_floor_y": FLOOR_Z,
        "ceiling_height_m": CEIL_H,
    },
    "assets": {
        "blend_source": "house.blend",
        "architecture": {"file": "architecture.glb", **poly_stats(arch_cols)},
        "collision": {"file": "collision.glb", **poly_stats(["Collision_Meshes"])},
        "interior_styles": {
            "modern": {"label": "Modern Minimalist", "file": "furniture-modern.glb", "floor_override_material": "Mat_Floor_ModernStone", **poly_stats(["Furniture_Modern"])},
            "scandinavian": {"label": "Scandinavian Natural", "file": "furniture-scandinavian.glb", "floor_override_material": "Mat_Floor_WhiteOak", **poly_stats(["Furniture_Scandinavian"])},
            "warm_luxury": {"label": "Warm Luxury", "file": "furniture-warm-luxury.glb", "floor_override_material": "Mat_Floor_Limestone", **poly_stats(["Furniture_WarmLuxury"])},
        },
    },
    "dollhouse_toggle_objects": {
        "roof": [o.name for o in cols["Roof"].objects],
        "ceilings": [o.name for o in cols["Ceilings"].objects],
        "level2_objects": [
            o.name
            for cn in ("Architecture", "Walls", "Floors", "Ceilings", "Roof", "Doors", "Windows", "Lighting")
            for o in cols[cn].objects
            if "L2_" in o.name
        ],
    },
    "interactive_doors": door_interactive_meta,
    "lighting_presets": {
        "morning": {
            "label": "Morning Tropical Light (08:30)",
            "sun_elevation_deg": 28.0,
            "sun_azimuth_deg": 95.0,
            "sky_intensity": 0.085,
            "sun_color_hex": "#FFF0D6",
            "interior_lights_multiplier": 1.15,
            "outdoor_lights_multiplier": 0.0,
            "exposure": 0.25,
        },
        "afternoon": {
            "label": "Bright Afternoon (14:30)",
            "sun_elevation_deg": 42.0,
            "sun_azimuth_deg": 145.0,
            "sky_intensity": 0.085,
            "sun_color_hex": "#FFFFFF",
            "interior_lights_multiplier": 0.65,
            "outdoor_lights_multiplier": 0.30,
            "exposure": -0.15,
        },
        "sunset": {
            "label": "Golden Sunset (17:45)",
            "sun_elevation_deg": 7.5,
            "sun_azimuth_deg": 248.0,
            "sky_intensity": 0.068,
            "sun_color_hex": "#FFB570",
            "interior_lights_multiplier": 1.95,
            "outdoor_lights_multiplier": 2.10,
            "exposure": 0.38,
        },
        "night": {
            "label": "Architectural Night (20:30)",
            "sun_elevation_deg": -12.0,
            "sun_azimuth_deg": 265.0,
            "sky_intensity": 0.008,
            "sun_color_hex": "#3B527A",
            "interior_lights_multiplier": 2.50,
            "outdoor_lights_multiplier": 2.60,
            "exposure": 0.55,
        },
    },
    "cameras": {
        "exterior_hero": {"threejs_position": [10.2, 2.25, 5.8], "threejs_target": [4.6, 1.75, -3.8], "fov_deg": 46},
        "exterior_rear": {"threejs_position": [4.95, 1.48, -13.15], "threejs_target": [7.65, 1.32, -10.60], "fov_deg": 52},
        "interior_living": {"threejs_position": [5.75, 1.63, -5.55], "threejs_target": [7.45, 1.40, -11.40], "fov_deg": 55},
        "interior_master": {"threejs_position": [3.55, 1.59, -8.65], "threejs_target": [1.10, 1.27, -10.60], "fov_deg": 54},
        "dollhouse_ortho": {"type": "orthographic", "threejs_position": [16.5, 18.5, 5.5], "threejs_target": [4.57, 1.20, -6.75], "ortho_scale": 16.2},
        "first_person_start": {"eye_height_m": 1.65, "threejs_position": [4.70, 1.80, -2.80], "threejs_target": [6.00, 1.65, -7.20], "fov_deg": 60},
    },
}

(OUT_DIR / "scene-config.json").write_text(json.dumps(scene_config, indent=2), encoding="utf-8")
(OUT_DIR / "tour-waypoints.json").write_text(json.dumps({
    "project": spec["meta"]["project_name"],
    "default_eye_height_m": 1.65,
    "walk_speed_mps": 1.35,
    "waypoints": waypoints_out,
}, indent=2), encoding="utf-8")

print("Wrote scene-config.json and tour-waypoints.json successfully.")
