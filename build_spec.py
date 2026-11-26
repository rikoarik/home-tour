#!/usr/bin/env python3
"""
Single-source-of-truth architectural geometry generator and validator
for the Modern Single-Story Luxury Residence (9,144 x 13,500 mm).

Generates `floorplan-spec.json` and runs strict dimensional, area,
containment, and collision validations before writing output.
"""

import json
import math
from pathlib import Path

OUT_DIR = Path("/Users/macbookm2/.gemini/antigravity/scratch/luxury-residence-floorplan")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. SITE & ENVELOPE CONSTANTS (millimeters)
# ---------------------------------------------------------------------------
SITE_W = 9144      # 9.144 m (exact 30 ft; yields 123.444 m² and 45.288 m perimeter)
SITE_D = 13500     # 13.500 m
EXT_T = 200        # exterior wall thickness (mm)
INT_T = 120        # interior wall thickness (mm)
CEIL_H = 3000      # ceiling height (mm)

# Key structural grid lines (mm)
CARPORT_W = 3044   # X: 0 .. 3044
CARPORT_D = 5000   # Y: 0 .. 5000
FRONT_GARDEN_D = 1900  # Y: 0 .. 1900 (X: 3044 .. 9144)
REAR_WALL_OUTER_Y = 11700  # Rear garden/terrace: Y: 11700 .. 13500 (1800 mm deep)

# Exact interior clear faces
X_WEST_IN = 200
X_EAST_IN = SITE_W - EXT_T          # 8944
X_STEP_IN = CARPORT_W + EXT_T       # 3244 (inner face of West wall of Front-East block)
Y_FRONT_IN = FRONT_GARDEN_D + EXT_T # 2100
Y_CARPORT_IN = CARPORT_D + EXT_T    # 5200
Y_REAR_IN = REAR_WALL_OUTER_Y - EXT_T  # 11500

# Interior partition faces (all 120 mm thick)
# Vertical partitions:
# - Bed2 East wall: X = 3124 .. 3244 (aligns flush with X_STEP_IN = 3244!)
# - Service core (Laundry + Shared Bath) East wall: X = 4744 .. 4864
# - Master Bed East wall: X = 3800 .. 3920
# - Master Ensuite East wall: X = 5370 .. 5490
# - Bedroom 3 West wall: X = 5964 .. 6084
# Horizontal partitions:
# - Foyer / Laundry wall: Y = 3520 .. 3640 (X: 3244 .. 4864)
# - Laundry / Shared Bath wall: Y = 5000 .. 5120 (X: 3244 .. 4864; aligns with Y_CARPORT_OUT=5000)
# - Shared Bath North wall: Y = 7040 .. 7160 (X: 3244 .. 4864)
# - Bed 2 / Master Bed wall: Y = 8080 .. 8200 (X: 200 .. 3920)
# - Hall / Master Ensuite wall: Y = 9200 .. 9320 (X: 3920 .. 5490)
# - Bed 3 North wall: Y = 5080 .. 5200 (X: 5964 .. 8944)


def rect_area_m2(x0, y0, x1, y1):
    return ((x1 - x0) * (y1 - y0)) / 1_000_000.0


def poly_area_m2(pts):
    s = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        s += x1 * y2 - x2 * y1
    return abs(s) * 0.5 / 1_000_000.0


def poly_perimeter_m(pts):
    p = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        p += math.hypot(x2 - x1, y2 - y1)
    return p / 1000.0


# ---------------------------------------------------------------------------
# 2. SITE, FOOTPRINT & OUTDOOR ZONES
# ---------------------------------------------------------------------------
site_boundary = [[0, 0], [SITE_W, 0], [SITE_W, SITE_D], [0, SITE_D]]

building_footprint_poly = [
    [CARPORT_W, FRONT_GARDEN_D],
    [SITE_W, FRONT_GARDEN_D],
    [SITE_W, REAR_WALL_OUTER_Y],
    [0, REAR_WALL_OUTER_Y],
    [0, CARPORT_D],
    [CARPORT_W, CARPORT_D],
]

outdoor_zones = [
    {
        "id": "EXT-01",
        "name": "Carport (1 Vehicle)",
        "type": "carport",
        "bounds": {"x0": 0, "y0": 0, "x1": CARPORT_W, "y1": CARPORT_D},
        "polygon": [[0, 0], [CARPORT_W, 0], [CARPORT_W, CARPORT_D], [0, CARPORT_D]],
        "width_mm": CARPORT_W,
        "depth_mm": CARPORT_D,
        "area_m2": round(rect_area_m2(0, 0, CARPORT_W, CARPORT_D), 2),
        "finish": "flamed_basalt_pavers",
        "covered": True,
        "canopy_note": "Cantilevered steel & timber-slat pergola canopy (open sides)",
    },
    {
        "id": "EXT-02",
        "name": "Front Garden & Entry Path",
        "type": "front_garden",
        "bounds": {"x0": CARPORT_W, "y0": 0, "x1": SITE_W, "y1": FRONT_GARDEN_D},
        "polygon": [[CARPORT_W, 0], [SITE_W, 0], [SITE_W, FRONT_GARDEN_D], [CARPORT_W, FRONT_GARDEN_D]],
        "width_mm": SITE_W - CARPORT_W,
        "depth_mm": FRONT_GARDEN_D,
        "area_m2": round(rect_area_m2(CARPORT_W, 0, SITE_W, FRONT_GARDEN_D), 2),
        "finish": "manicured_lawn_and_stepping_stones",
        "covered": False,
    },
    {
        "id": "EXT-03",
        "name": "Rear Landscaped Garden",
        "type": "rear_garden",
        "bounds": {"x0": 0, "y0": REAR_WALL_OUTER_Y, "x1": 5490, "y1": SITE_D},
        "polygon": [[0, REAR_WALL_OUTER_Y], [5490, REAR_WALL_OUTER_Y], [5490, SITE_D], [0, SITE_D]],
        "width_mm": 5490,
        "depth_mm": SITE_D - REAR_WALL_OUTER_Y,
        "area_m2": round(rect_area_m2(0, REAR_WALL_OUTER_Y, 5490, SITE_D), 2),
        "finish": "tropical_lawn_and_pebble_border",
        "covered": False,
    },
    {
        "id": "EXT-04",
        "name": "Rear Outdoor Terrace",
        "type": "terrace",
        "bounds": {"x0": 5490, "y0": REAR_WALL_OUTER_Y, "x1": SITE_W, "y1": SITE_D},
        "polygon": [[5490, REAR_WALL_OUTER_Y], [SITE_W, REAR_WALL_OUTER_Y], [SITE_W, SITE_D], [5490, SITE_D]],
        "width_mm": SITE_W - 5490,
        "depth_mm": SITE_D - REAR_WALL_OUTER_Y,
        "area_m2": round(rect_area_m2(5490, REAR_WALL_OUTER_Y, SITE_W, SITE_D), 2),
        "finish": "teak_timber_deck",
        "covered": True,
        "canopy_note": "1,200 mm architectural roof overhang",
    },
]

# ---------------------------------------------------------------------------
# 3. WALLS (Exterior 200 mm, Interior 120 mm) — non-overlapping solid rects
# ---------------------------------------------------------------------------
# Each wall segment is stored as an exact axis-aligned rectangle [x0, y0, x1, y1]
# representing the structural wall BEFORE openings are subtracted, plus explicit
# centerline start/end and thickness for Three.js extrusion.
walls = [
    # --- EXTERIOR WALLS (200 mm) ---
    {
        "id": "EW-S1",
        "category": "exterior",
        "label": "South Front Facade Wall",
        "thickness_mm": EXT_T,
        "height_mm": CEIL_H,
        "rect": [3044, 1900, 9144, 2100],
        "start": [3144, 2000],
        "end": [9044, 2000],
        "orientation": "H",
        "material": "exterior_stucco_charcoal_white",
    },
    {
        "id": "EW-E1",
        "category": "exterior",
        "label": "East Boundary Exterior Wall",
        "thickness_mm": EXT_T,
        "height_mm": CEIL_H,
        "rect": [8944, 2100, 9144, 11500],
        "start": [9044, 2000],
        "end": [9044, 11600],
        "orientation": "V",
        "material": "exterior_stucco_charcoal_white",
    },
    {
        "id": "EW-N1",
        "category": "exterior",
        "label": "North Rear Facade Wall",
        "thickness_mm": EXT_T,
        "height_mm": CEIL_H,
        "rect": [0, 11500, 9144, 11700],
        "start": [100, 11600],
        "end": [9044, 11600],
        "orientation": "H",
        "material": "exterior_stucco_charcoal_white",
    },
    {
        "id": "EW-W1",
        "category": "exterior",
        "label": "West Boundary Exterior Wall",
        "thickness_mm": EXT_T,
        "height_mm": CEIL_H,
        "rect": [0, 5000, 200, 11500],
        "start": [100, 5100],
        "end": [100, 11600],
        "orientation": "V",
        "material": "exterior_stucco_charcoal_white",
    },
    {
        "id": "EW-S2",
        "category": "exterior",
        "label": "Behind-Carport South Exterior Wall",
        "thickness_mm": EXT_T,
        "height_mm": CEIL_H,
        "rect": [200, 5000, 3244, 5200],
        "start": [100, 5100],
        "end": [3144, 5100],
        "orientation": "H",
        "material": "exterior_stucco_charcoal_white",
    },
    {
        "id": "EW-W2",
        "category": "exterior",
        "label": "Carport-Side Stepped Exterior Wall",
        "thickness_mm": EXT_T,
        "height_mm": CEIL_H,
        "rect": [3044, 2100, 3244, 5000],
        "start": [3144, 2000],
        "end": [3144, 5100],
        "orientation": "V",
        "material": "exterior_stucco_charcoal_white",
    },
    # --- INTERIOR PARTITIONS (120 mm) ---
    {
        "id": "IW-01",
        "category": "interior",
        "label": "Foyer / Laundry Partition",
        "thickness_mm": INT_T,
        "height_mm": CEIL_H,
        "rect": [3244, 3520, 4864, 3640],
        "start": [3244, 3580],
        "end": [4804, 3580],
        "orientation": "H",
        "material": "interior_gypsum_warm_white",
    },
    {
        "id": "IW-02",
        "category": "interior",
        "label": "Laundry / Shared Bath Partition",
        "thickness_mm": INT_T,
        "height_mm": CEIL_H,
        "rect": [3244, 5000, 4744, 5120],
        "start": [3244, 5060],
        "end": [4804, 5060],
        "orientation": "H",
        "material": "interior_gypsum_moisture_resistant",
    },
    {
        "id": "IW-03",
        "category": "interior",
        "label": "Shared Bath North Partition",
        "thickness_mm": INT_T,
        "height_mm": CEIL_H,
        "rect": [3244, 7040, 4864, 7160],
        "start": [3244, 7100],
        "end": [4804, 7100],
        "orientation": "H",
        "material": "interior_gypsum_moisture_resistant",
    },
    {
        "id": "IW-04",
        "category": "interior",
        "label": "Service Core East Partition (Laundry & Shared Bath)",
        "thickness_mm": INT_T,
        "height_mm": CEIL_H,
        "rect": [4744, 3640, 4864, 7040],
        "start": [4804, 3580],
        "end": [4804, 7100],
        "orientation": "V",
        "material": "interior_gypsum_warm_white",
    },
    {
        "id": "IW-05",
        "category": "interior",
        "label": "Bedroom 2 East Partition",
        "thickness_mm": INT_T,
        "height_mm": CEIL_H,
        "rect": [3124, 5200, 3244, 8080],
        "start": [3184, 5200],
        "end": [3184, 8140],
        "orientation": "V",
        "material": "interior_gypsum_warm_white",
    },
    {
        "id": "IW-06",
        "category": "interior",
        "label": "Bedroom 2 / Master Bedroom Partition",
        "thickness_mm": INT_T,
        "height_mm": CEIL_H,
        "rect": [200, 8080, 3920, 8200],
        "start": [200, 8140],
        "end": [3860, 8140],
        "orientation": "H",
        "material": "interior_gypsum_acoustic",
    },
    {
        "id": "IW-07",
        "category": "interior",
        "label": "Master Bedroom East Partition",
        "thickness_mm": INT_T,
        "height_mm": CEIL_H,
        "rect": [3800, 8200, 3920, 11500],
        "start": [3860, 8140],
        "end": [3860, 11500],
        "orientation": "V",
        "material": "interior_gypsum_moisture_resistant",
    },
    {
        "id": "IW-08",
        "category": "interior",
        "label": "Master Ensuite South Partition",
        "thickness_mm": INT_T,
        "height_mm": CEIL_H,
        "rect": [3920, 9200, 5490, 9320],
        "start": [3860, 9260],
        "end": [5430, 9260],
        "orientation": "H",
        "material": "interior_gypsum_moisture_resistant",
    },
    {
        "id": "IW-09",
        "category": "interior",
        "label": "Master Ensuite / Living Room Partition",
        "thickness_mm": INT_T,
        "height_mm": CEIL_H,
        "rect": [5370, 9320, 5490, 11500],
        "start": [5430, 9260],
        "end": [5430, 11500],
        "orientation": "V",
        "material": "interior_gypsum_acoustic",
    },
    {
        "id": "IW-10",
        "category": "interior",
        "label": "Bedroom 3 West Partition",
        "thickness_mm": INT_T,
        "height_mm": CEIL_H,
        "rect": [5964, 2100, 6084, 5200],
        "start": [6024, 2100],
        "end": [6024, 5140],
        "orientation": "V",
        "material": "interior_gypsum_warm_white",
    },
    {
        "id": "IW-11",
        "category": "interior",
        "label": "Bedroom 3 / Kitchen Partition",
        "thickness_mm": INT_T,
        "height_mm": CEIL_H,
        "rect": [6084, 5080, 8944, 5200],
        "start": [6024, 5140],
        "end": [8944, 5140],
        "orientation": "H",
        "material": "interior_gypsum_acoustic",
    },
]

# ---------------------------------------------------------------------------
# 4. ROOMS (Strictly disjoint interior polygons covering 100% of usable area)
# ---------------------------------------------------------------------------
rooms = [
    {
        "id": "RM-01",
        "name": "Master Bedroom",
        "short_name": "MASTER BEDROOM",
        "zone": "private",
        "ceiling_height_mm": CEIL_H,
        "floor_material": "engineered_white_oak",
        "polygon": [[200, 8200], [3800, 8200], [3800, 11500], [200, 11500]],
        "width_mm": 3600,
        "depth_mm": 3300,
        "label_pos": [1850, 9950],
        "notes": "Includes 2,400 x 600 mm built-in full-height sliding wardrobe along South wall",
    },
    {
        "id": "RM-02",
        "name": "Master Ensuite Bathroom",
        "short_name": "MASTER\nENSUITE",
        "zone": "wet",
        "ceiling_height_mm": 2800,
        "floor_material": "honed_travertine_tile",
        "polygon": [[3920, 9320], [5370, 9320], [5370, 11500], [3920, 11500]],
        "width_mm": 1450,
        "depth_mm": 2180,
        "label_pos": [4340, 10080],
        "notes": "2,800 mm moisture-resistant recessed ceiling; glass walk-in rain shower",
    },
    {
        "id": "RM-03",
        "name": "Bedroom 2",
        "short_name": "BEDROOM 2",
        "zone": "private",
        "ceiling_height_mm": CEIL_H,
        "floor_material": "engineered_white_oak",
        "polygon": [[200, 5200], [3124, 5200], [3124, 8080], [200, 8080]],
        "width_mm": 2924,
        "depth_mm": 2880,
        "label_pos": [1660, 6750],
        "notes": "South window overlooks open-sided carport",
    },
    {
        "id": "RM-04",
        "name": "Bedroom 3",
        "short_name": "BEDROOM 3",
        "zone": "private",
        "ceiling_height_mm": CEIL_H,
        "floor_material": "engineered_white_oak",
        "polygon": [[6084, 2100], [8944, 2100], [8944, 5080], [6084, 5080]],
        "width_mm": 2860,
        "depth_mm": 2980,
        "label_pos": [7514, 3650],
        "notes": "Front guest suite / flexible study bedroom overlooking front garden",
    },
    {
        "id": "RM-05",
        "name": "Shared Bathroom",
        "short_name": "SHARED\nBATH",
        "zone": "wet",
        "ceiling_height_mm": 2800,
        "floor_material": "honed_travertine_tile",
        "polygon": [[3244, 5120], [4744, 5120], [4744, 7040], [3244, 7040]],
        "width_mm": 1500,
        "depth_mm": 1920,
        "label_pos": [3994, 6220],
        "notes": "Centrally located for Bed 2, Bed 3 & guests; mechanical inline exhaust duct",
    },
    {
        "id": "RM-06",
        "name": "Laundry & Utility",
        "short_name": "LAUNDRY &\nUTILITY",
        "zone": "service",
        "ceiling_height_mm": 2800,
        "floor_material": "matte_porcelain_grey",
        "polygon": [[3244, 3640], [4744, 3640], [4744, 5000], [3244, 5000]],
        "width_mm": 1500,
        "depth_mm": 1360,
        "label_pos": [3994, 4320],
        "notes": "Stacked washer/dryer, utility sink & natural louver ventilation to carport",
    },
    {
        "id": "RM-07",
        "name": "Main Entrance & Foyer",
        "short_name": "FOYER",
        "zone": "circulation",
        "ceiling_height_mm": CEIL_H,
        "floor_material": "large_format_limestone",
        "polygon": [[3244, 2100], [5964, 2100], [5964, 3520], [3244, 3520]],
        "width_mm": 2720,
        "depth_mm": 1420,
        "label_pos": [4600, 2860],
        "notes": "1,000 mm architectural pivot door with full-height sidelight & entry bench",
    },
    {
        "id": "RM-08",
        "name": "Entry Gallery & Private Hall",
        "short_name": "GALLERY\nHALL",
        "zone": "circulation",
        "ceiling_height_mm": CEIL_H,
        "floor_material": "large_format_limestone",
        # Disjoint union of 2 zones represented as a single list of sub-rects + primary polygon:
        # Sub-A (Entry Gallery): [4864, 3520] to [5964, 5200] (1100 x 1680 = 1.848 m²)
        # Sub-B (Private Hall West-Lower): [3244, 7160] to [4864, 8080] (1620 x 920 = 1.4904 m²)
        # Sub-C (Private Hall Upper Vestibule): [3920, 8080] to [5490, 9200] (1570 x 1120 = 1.7584 m²)
        # Wait: connect Sub-B and Sub-C cleanly with [4864..5490, 8200..9200] already in Sub-C!
        # Let's check [4864..5490, 7160..8080] -> part of Dining Area! So Sub-B meets Dining seamlessly at x=4864.
        "sub_rects": [
            [4864, 3520, 5964, 5200],
            [3244, 7160, 4864, 8080],
            [3920, 8080, 5490, 9200],
        ],
        "polygon": [[3244, 7160], [4864, 7160], [4864, 8080], [5490, 8080], [5490, 9200], [3920, 9200], [3920, 8080], [3244, 8080]],
        "width_mm": 1100,
        "depth_mm": 5680,
        "label_pos": [4680, 8580],
        "notes": "1,100 mm clear circulation spine linking Foyer, Dining/Living, Bed 2, Bed 3 & Master Suite",
    },
    {
        "id": "RM-09",
        "name": "Open-Plan Living Room",
        "short_name": "LIVING ROOM",
        "zone": "public",
        "ceiling_height_mm": CEIL_H,
        "floor_material": "large_format_limestone",
        "polygon": [[5490, 8200], [8944, 8200], [8944, 11500], [5490, 11500]],
        "width_mm": 3454,
        "depth_mm": 3300,
        "label_pos": [7217, 9880],
        "notes": "Seamless indoor-outdoor connection via 2,800 mm 3-panel sliding glass doors to Rear Terrace",
    },
    {
        "id": "RM-10",
        "name": "Dining Area",
        "short_name": "DINING AREA",
        "zone": "public",
        "ceiling_height_mm": CEIL_H,
        "floor_material": "large_format_limestone",
        # Covers [4864..6944, 5200..8200] MINUS [4864..5490, 8080..8200] which is inside RM-08 Sub-C!
        # Let's make RM-08 Sub-C start at y=8200 -> [3920, 8200, 5490, 9200] AND add [3920, 8080, 4864, 8200] to RM-08!
        # That keeps RM-10 a super clean rectangle [4864, 5200, 6944, 8200]!
        "polygon": [[4864, 5200], [6944, 5200], [6944, 8200], [4864, 8200]],
        "width_mm": 2080,
        "depth_mm": 3000,
        "label_pos": [5904, 6700],
        "notes": "Open-plan 6-seat dining zone seamlessly adjacent to Kitchen and Living Room",
    },
    {
        "id": "RM-11",
        "name": "Modern Kitchen",
        "short_name": "MODERN\nKITCHEN",
        "zone": "public",
        "ceiling_height_mm": CEIL_H,
        "floor_material": "large_format_limestone",
        "polygon": [[6944, 5200], [8944, 5200], [8944, 8200], [6944, 8200]],
        "width_mm": 2000,
        "depth_mm": 3000,
        "label_pos": [7744, 6700],
        "notes": "L-shaped honed quartz countertop, 4-burner induction hob, double sink, integrated fridge & oven tower",
    },
]

# Fix RM-08 sub_rects so they are 100% disjoint from RM-10 [4864..6944, 5200..8200]:
rooms[7]["sub_rects"] = [
    [4864, 3520, 5964, 5200],   # Entry Gallery: 1100 x 1680 = 1.8480 m²
    [3244, 7160, 4864, 8080],   # Lower Private Hall: 1620 x 920 = 1.4904 m²
    [3920, 8080, 4864, 8200],   # Bridge strip: 944 x 120 = 0.1133 m²
    [3920, 8200, 5490, 9200],   # Upper Master Vestibule: 1570 x 1000 = 1.5700 m²
]
rooms[7]["polygon"] = [
    [3244, 7160], [4864, 7160], [4864, 8200], [5490, 8200],
    [5490, 9200], [3920, 9200], [3920, 8080], [3244, 8080],
]

for r in rooms:
    if "sub_rects" in r:
        a = sum(rect_area_m2(*sr) for sr in r["sub_rects"])
    else:
        a = poly_area_m2(r["polygon"])
    r["area_m2"] = round(a, 2)
    r["area_sqft"] = round(a * 10.7639104, 2)

# ---------------------------------------------------------------------------
# 5. DOORS (D1 - D8) with exact opening coordinates, hinge & swing arc
# ---------------------------------------------------------------------------
# Convention:
# - opening: [x0, y0, x1, y1] cutting cleanly through host wall
# - hinge: [hx, hy]
# - leaf_open_end: [ex, ey] (90° open tip)
# - swing_arc: {center, radius, start_deg, end_deg} (CCW in standard CAD math coords)
doors = [
    {
        "id": "D1",
        "type": "Architectural Timber Pivot Door",
        "host_wall": "EW-S1",
        "connects": ["EXT-02", "RM-07"],
        "width_mm": 1000,
        "height_mm": 2200,
        "opening": [4200, 1900, 5200, 2100],
        "hinge": [4200, 2100],
        "leaf_open_end": [4200, 3100],
        "swing_arc": {"center": [4200, 2100], "radius": 1000, "start_deg": 0, "end_deg": 90},
        "swing_direction": "Inward-Left (into Foyer)",
        "material": "solid_walnut_pivot",
    },
    {
        "id": "D2",
        "type": "Flush Timber Interior Door",
        "host_wall": "IW-07",
        "connects": ["RM-08", "RM-01"],
        "width_mm": 850,
        "height_mm": 2100,
        "opening": [3800, 8275, 3920, 9125],
        "hinge": [3800, 8275],
        "leaf_open_end": [2950, 8275],
        "swing_arc": {"center": [3800, 8275], "radius": 850, "start_deg": 90, "end_deg": 180},
        "swing_direction": "Inward-South (into Master Bedroom)",
        "material": "matte_oak_veneer",
    },
    {
        "id": "D3",
        "type": "Flush Timber Interior Door",
        "host_wall": "IW-05",
        "connects": ["RM-08", "RM-03"],
        "width_mm": 800,
        "height_mm": 2100,
        "opening": [3124, 7220, 3244, 8020],
        "hinge": [3124, 8020],
        "leaf_open_end": [2324, 8020],
        "swing_arc": {"center": [3124, 8020], "radius": 800, "start_deg": 180, "end_deg": 270},
        "swing_direction": "Inward-North (into Bedroom 2)",
        "material": "matte_oak_veneer",
    },
    {
        "id": "D4",
        "type": "Flush Timber Interior Door",
        "host_wall": "IW-10",
        "connects": ["RM-08", "RM-04"],
        "width_mm": 800,
        "height_mm": 2100,
        "opening": [5964, 4180, 6084, 4980],
        "hinge": [6084, 4980],
        "leaf_open_end": [6884, 4980],
        "swing_arc": {"center": [6084, 4980], "radius": 800, "start_deg": 270, "end_deg": 360},
        "swing_direction": "Inward-North (into Bedroom 3)",
        "material": "matte_oak_veneer",
    },
    {
        "id": "D5",
        "type": "Moisture-Resistant Bathroom Door",
        "host_wall": "IW-04",
        "connects": ["RM-10", "RM-05"],
        "width_mm": 700,
        "height_mm": 2100,
        "opening": [4744, 6160, 4864, 6860],
        "hinge": [4744, 6160],
        "leaf_open_end": [4044, 6160],
        "swing_arc": {"center": [4744, 6160], "radius": 700, "start_deg": 90, "end_deg": 180},
        "swing_direction": "Inward-South (into Shared Bathroom)",
        "material": "lacquered_moisture_resistant_timber",
    },
    {
        "id": "D6",
        "type": "Moisture-Resistant Ensuite Door",
        "host_wall": "IW-07",
        "connects": ["RM-01", "RM-02"],
        "width_mm": 750,
        "height_mm": 2100,
        "opening": [3800, 9450, 3920, 10200],
        "hinge": [3920, 9450],
        "leaf_open_end": [4670, 9450],
        "swing_arc": {"center": [3920, 9450], "radius": 750, "start_deg": 0, "end_deg": 90},
        "swing_direction": "Inward-South (into Master Ensuite)",
        "material": "lacquered_moisture_resistant_timber",
    },
    {
        "id": "D7",
        "type": "Cavity Pocket Door (Laundry)",
        "host_wall": "IW-04",
        "connects": ["RM-08", "RM-06"],
        "width_mm": 750,
        "height_mm": 2100,
        "opening": [4744, 3980, 4864, 4730],
        "hinge": None,
        "leaf_open_end": None,
        "swing_arc": None,
        "sliding_track": [[4804, 3980], [4804, 4730]],
        "swing_direction": "Pocket Slide South (zero swing clearance)",
        "material": "lacquered_timber_pocket",
    },
    {
        "id": "D8",
        "type": "3-Panel Aluminum Sliding Glass Door",
        "host_wall": "EW-N1",
        "connects": ["RM-09", "EXT-04"],
        "width_mm": 2800,
        "height_mm": 2400,
        "opening": [5817, 11500, 8617, 11700],
        "hinge": None,
        "leaf_open_end": None,
        "swing_arc": None,
        "sliding_panels": 3,
        "swing_direction": "Multi-track Slide East/West (to Rear Terrace)",
        "material": "black_anodized_aluminum_low_e_glass",
    },
]

# ---------------------------------------------------------------------------
# 6. WINDOWS (W1 - W6) with exact opening coordinates, width, height, sill
# ---------------------------------------------------------------------------
windows = [
    {
        "id": "W1",
        "type": "Full-Height Entry Sidelight",
        "host_wall": "EW-S1",
        "room": "RM-07",
        "width_mm": 500,
        "height_mm": 2200,
        "sill_height_mm": 0,
        "opening": [5260, 1900, 5760, 2100],
        "glazing": "laminated_frosted_low_e",
        "orientation": "South (Front Garden)",
    },
    {
        "id": "W2",
        "type": "Double Casement Picture Window",
        "host_wall": "EW-S1",
        "room": "RM-04",
        "width_mm": 1600,
        "height_mm": 1400,
        "sill_height_mm": 900,
        "opening": [6714, 1900, 8314, 2100],
        "glazing": "double_glazed_clear_low_e",
        "orientation": "South (Front Garden)",
    },
    {
        "id": "W3",
        "type": "Horizontal Sliding Privacy Window",
        "host_wall": "EW-S2",
        "room": "RM-03",
        "width_mm": 1500,
        "height_mm": 1100,
        "sill_height_mm": 1100,
        "opening": [880, 5000, 2380, 5200],
        "glazing": "double_glazed_tinted_low_e",
        "orientation": "South (Over Carport)",
    },
    {
        "id": "W4",
        "type": "Frosted Ventilation Louver Window",
        "host_wall": "EW-W2",
        "room": "RM-06",
        "width_mm": 800,
        "height_mm": 900,
        "sill_height_mm": 1300,
        "opening": [3044, 3920, 3244, 4720],
        "glazing": "frosted_louver_glass",
        "orientation": "West (Over Carport)",
    },
    {
        "id": "W5",
        "type": "Top-Hung Frosted Awning Window",
        "host_wall": "EW-N1",
        "room": "RM-02",
        "width_mm": 800,
        "height_mm": 700,
        "sill_height_mm": 1500,
        "opening": [4245, 11500, 5045, 11700],
        "glazing": "frosted_tempered_low_e",
        "orientation": "North (Rear Garden)",
    },
    {
        "id": "W6",
        "type": "Panoramic Casement & Fixed Window",
        "host_wall": "EW-N1",
        "room": "RM-01",
        "width_mm": 2200,
        "height_mm": 1800,
        "sill_height_mm": 600,
        "opening": [900, 11500, 3100, 11700],
        "glazing": "double_glazed_clear_low_e",
        "orientation": "North (Rear Garden)",
    },
]

# ---------------------------------------------------------------------------
# 7. COMPLETE FURNITURE, SANITARY FIXTURES, VEHICLE & LANDSCAPING
# ---------------------------------------------------------------------------
# Every item has exact bounding rect [x0, y0, x1, y1] in mm, room ID, kind,
# rotation_deg, elevation_height_mm, and material for consistent 2D & Three.js use.
furniture = [
    # --- RM-01: Master Bedroom [200..3800, 8200..11500] ---
    {"id": "F-MB-WARD", "room": "RM-01", "kind": "wardrobe", "name": "Master Built-in Sliding Wardrobe", "rect": [200, 8200, 2600, 8800], "height_mm": 2800, "rotation_deg": 0, "material": "fluted_walnut_millwork"},
    {"id": "F-MB-BED", "room": "RM-01", "kind": "bed_king", "name": "King Platform Bed (1800x2000)", "rect": [200, 9300, 2200, 11100], "height_mm": 550, "rotation_deg": 90, "material": "boucle_linen_oak"},
    {"id": "F-MB-NS1", "room": "RM-01", "kind": "nightstand", "name": "Master Nightstand South", "rect": [200, 8840, 620, 9260], "height_mm": 500, "rotation_deg": 0, "material": "smoked_oak"},
    {"id": "F-MB-NS2", "room": "RM-01", "kind": "nightstand", "name": "Master Nightstand North", "rect": [200, 11120, 620, 11480], "height_mm": 500, "rotation_deg": 0, "material": "smoked_oak"},
    {"id": "F-MB-CONS", "room": "RM-01", "kind": "tv_console", "name": "Master Dressing / Media Console", "rect": [3400, 10280, 3780, 11380], "height_mm": 650, "rotation_deg": 270, "material": "fluted_walnut_millwork"},

    # --- RM-02: Master Ensuite [3920..5370, 9320..11500] ---
    {"id": "F-ME-SHW", "room": "RM-02", "kind": "shower", "name": "Walk-in Glass Rain Shower", "rect": [3920, 10600, 5370, 11500], "height_mm": 2200, "rotation_deg": 0, "material": "frameless_glass_travertine"},
    {"id": "F-ME-VAN", "room": "RM-02", "kind": "vanity", "name": "Floating Stone Vanity & Basin", "rect": [4890, 9380, 5370, 10280], "height_mm": 850, "rotation_deg": 270, "material": "honed_calacatta_marble"},
    {"id": "F-ME-WC", "room": "RM-02", "kind": "wc", "name": "Wall-Hung WC", "rect": [4790, 10290, 5370, 10580], "height_mm": 420, "rotation_deg": 270, "material": "matte_white_ceramic"},

    # --- RM-03: Bedroom 2 [200..3124, 5200..8080] ---
    {"id": "F-B2-BED", "room": "RM-03", "kind": "bed_queen", "name": "Queen Bed (1500x2000)", "rect": [200, 6080, 2200, 7580], "height_mm": 520, "rotation_deg": 90, "material": "warm_grey_linen"},
    {"id": "F-B2-NS", "room": "RM-03", "kind": "nightstand", "name": "Bedroom 2 Nightstand", "rect": [200, 7620, 620, 8040], "height_mm": 500, "rotation_deg": 0, "material": "natural_oak"},
    {"id": "F-B2-WARD", "room": "RM-03", "kind": "wardrobe", "name": "Bedroom 2 Built-in Wardrobe", "rect": [2544, 5200, 3124, 6550], "height_mm": 2600, "rotation_deg": 270, "material": "natural_oak"},
    {"id": "F-B2-DESK", "room": "RM-03", "kind": "desk", "name": "Study Desk & Chair", "rect": [900, 5220, 1950, 5740], "height_mm": 750, "rotation_deg": 0, "material": "natural_oak"},

    # --- RM-04: Bedroom 3 [6084..8944, 2100..5080] ---
    {"id": "F-B3-BED", "room": "RM-04", "kind": "bed_queen", "name": "Queen Bed (1500x2000)", "rect": [6944, 2780, 8944, 4280], "height_mm": 520, "rotation_deg": 270, "material": "sand_linen"},
    {"id": "F-B3-NS", "room": "RM-04", "kind": "nightstand", "name": "Bedroom 3 Nightstand", "rect": [8524, 2320, 8944, 2740], "height_mm": 500, "rotation_deg": 0, "material": "natural_oak"},
    {"id": "F-B3-WARD", "room": "RM-04", "kind": "wardrobe", "name": "Bedroom 3 Built-in Wardrobe", "rect": [7344, 4480, 8944, 5080], "height_mm": 2600, "rotation_deg": 180, "material": "natural_oak"},
    {"id": "F-B3-DESK", "room": "RM-04", "kind": "desk", "name": "Study Desk & Chair", "rect": [6140, 2120, 7140, 2640], "height_mm": 750, "rotation_deg": 0, "material": "natural_oak"},

    # --- RM-05: Shared Bathroom [3244..4744, 5120..7040] ---
    {"id": "F-SB-SHW", "room": "RM-05", "kind": "shower", "name": "Shared Walk-in Shower", "rect": [3244, 5120, 4744, 5920], "height_mm": 2200, "rotation_deg": 0, "material": "frameless_glass_travertine"},
    {"id": "F-SB-VAN", "room": "RM-05", "kind": "vanity", "name": "Shared Floating Vanity", "rect": [3320, 6590, 4020, 7040], "height_mm": 850, "rotation_deg": 180, "material": "honed_calacatta_marble"},
    {"id": "F-SB-WC", "room": "RM-05", "kind": "wc", "name": "Wall-Hung WC", "rect": [3244, 6020, 3824, 6420], "height_mm": 420, "rotation_deg": 90, "material": "matte_white_ceramic"},

    # --- RM-06: Laundry & Utility [3244..4744, 3640..5000] ---
    {"id": "F-LN-WD", "room": "RM-06", "kind": "washer_dryer", "name": "Stacked Front-Load Washer & Dryer", "rect": [3264, 4340, 3914, 4980], "height_mm": 1750, "rotation_deg": 0, "material": "brushed_graphite_appliance"},
    {"id": "F-LN-SINK", "room": "RM-06", "kind": "utility_sink", "name": "Utility Sink & Linen Cabinet", "rect": [3934, 4440, 4684, 4980], "height_mm": 880, "rotation_deg": 0, "material": "quartz_and_stainless"},
    {"id": "F-LN-SHELF", "room": "RM-06", "kind": "cabinet", "name": "Utility Storage Rack", "rect": [3264, 3660, 4164, 3980], "height_mm": 2100, "rotation_deg": 0, "material": "matte_white_laminate"},

    # --- RM-07: Foyer [3244..5964, 2100..3520] ---
    {"id": "F-FY-BENCH", "room": "RM-07", "kind": "bench", "name": "Foyer Entry Bench & Shoe Millwork", "rect": [3264, 2220, 3724, 3440], "height_mm": 460, "rotation_deg": 90, "material": "fluted_walnut_millwork"},
    {"id": "F-FY-PLANT", "room": "RM-07", "kind": "plant_pot", "name": "Foyer Indoor Planter", "rect": [5560, 2200, 5910, 2550], "height_mm": 1200, "rotation_deg": 0, "material": "terracotta_and_ficus"},

    # --- RM-09: Open-Plan Living Room [5490..8944, 8200..11500] ---
    {"id": "F-LV-RUG", "room": "RM-09", "kind": "rug", "name": "Woven Wool Area Rug", "rect": [5720, 8550, 8220, 11100], "height_mm": 15, "rotation_deg": 0, "material": "handwoven_ivory_wool"},
    {"id": "F-LV-SOFA", "room": "RM-09", "kind": "sofa_l", "name": "Luxury 3-Seater Sectional Sofa", "rect": [5540, 8750, 6460, 11050], "height_mm": 780, "rotation_deg": 90, "material": "warm_taupe_boucle"},
    {"id": "F-LV-CHAISE", "room": "RM-09", "kind": "sofa_chaise", "name": "Sectional Chaise Extension", "rect": [6460, 8750, 7180, 9550], "height_mm": 430, "rotation_deg": 0, "material": "warm_taupe_boucle"},
    {"id": "F-LV-CTBL", "room": "RM-09", "kind": "coffee_table", "name": "Sculptural Travertine Coffee Table", "rect": [6860, 9760, 7660, 10860], "height_mm": 360, "rotation_deg": 0, "material": "honed_travertine"},
    {"id": "F-LV-TV", "room": "RM-09", "kind": "tv_console", "name": "Floating Media Wall & 65-in OLED", "rect": [8464, 8750, 8924, 11100], "height_mm": 520, "rotation_deg": 270, "material": "fluted_walnut_millwork"},
    {"id": "F-LV-PLANT", "room": "RM-09", "kind": "plant_pot", "name": "Living Corner Fiddle-Leaf Fig", "rect": [8464, 11120, 8884, 11480], "height_mm": 1800, "rotation_deg": 0, "material": "ceramic_planter_foliage"},

    # --- RM-10: Dining Area [4864..6944, 5200..8200] ---
    {"id": "F-DN-TBL", "room": "RM-10", "kind": "dining_table_6", "name": "6-Seat Walnut Dining Table (900x1800)", "rect": [5700, 5900, 6600, 7700], "height_mm": 750, "rotation_deg": 0, "material": "solid_walnut_and_brass"},

    # --- RM-11: Modern Kitchen [6944..8944, 5200..8200] ---
    {"id": "F-KT-E", "room": "RM-11", "kind": "kitchen_counter", "name": "East Kitchen Counter & Induction Hob", "rect": [8324, 5200, 8944, 8200], "height_mm": 900, "rotation_deg": 270, "material": "matte_charcoal_quartz"},
    {"id": "F-KT-S", "room": "RM-11", "kind": "kitchen_counter", "name": "South Kitchen Counter & Double Sink", "rect": [6984, 5200, 8324, 5820], "height_mm": 900, "rotation_deg": 0, "material": "matte_charcoal_quartz"},
    {"id": "F-KT-FRIDGE", "room": "RM-11", "kind": "fridge", "name": "Integrated French-Door Refrigerator", "rect": [8264, 7450, 8944, 8200], "height_mm": 2100, "rotation_deg": 270, "material": "panel_ready_walnut"},
    {"id": "F-KT-HOB", "room": "RM-11", "kind": "cooktop", "name": "4-Burner Induction Cooktop", "rect": [8414, 6220, 8874, 6920], "height_mm": 910, "rotation_deg": 270, "material": "black_ceramic_glass"},
    {"id": "F-KT-SINK", "room": "RM-11", "kind": "kitchen_sink", "name": "Undermount Double Sink", "rect": [7320, 5280, 8060, 5740], "height_mm": 900, "rotation_deg": 0, "material": "gunmetal_stainless"},

    # --- EXT-01: Carport Vehicle [0..3044, 0..5000] ---
    {"id": "F-CP-CAR", "room": "EXT-01", "kind": "car", "name": "Luxury Sedan / SUV (1850x4400)", "rect": [600, 320, 2450, 4720], "height_mm": 1520, "rotation_deg": 0, "material": "metallic_silver_vehicle"},

    # --- EXT-04: Rear Outdoor Terrace [5490..9144, 11700..13500] ---
    {"id": "F-TR-SOFA", "room": "EXT-04", "kind": "outdoor_lounge", "name": "Outdoor Teak Lounge Sofa", "rect": [6100, 12720, 7700, 13380], "height_mm": 720, "rotation_deg": 180, "material": "teak_and_weather_linen"},
    {"id": "F-TR-TBL", "room": "EXT-04", "kind": "coffee_table", "name": "Outdoor Stone Side Table", "rect": [6500, 12080, 7300, 12560], "height_mm": 400, "rotation_deg": 0, "material": "terrazzo_stone"},
    {"id": "F-TR-CHAIR", "room": "EXT-04", "kind": "armchair", "name": "Outdoor Lounge Armchair", "rect": [7980, 12450, 8680, 13150], "height_mm": 720, "rotation_deg": 225, "material": "teak_and_weather_linen"},
]

# Landscape elements (trees, stepping stones, planter beds)
landscaping = [
    {"id": "L-STEP-1", "zone": "EXT-02", "kind": "stepping_stone", "rect": [4250, 150, 5150, 550]},
    {"id": "L-STEP-2", "zone": "EXT-02", "kind": "stepping_stone", "rect": [4250, 750, 5150, 1150]},
    {"id": "L-STEP-3", "zone": "EXT-02", "kind": "stepping_stone", "rect": [4250, 1350, 5150, 1780]},
    {"id": "L-TREE-1", "zone": "EXT-02", "kind": "tree", "center": [8350, 1050], "radius_mm": 620, "name": "Olive / Frangipani Specimen Tree"},
    {"id": "L-TREE-2", "zone": "EXT-02", "kind": "shrub_cluster", "center": [6650, 620], "radius_mm": 420, "name": "Ornamental Agave & Grasses"},
    {"id": "L-TREE-3", "zone": "EXT-02", "kind": "shrub_cluster", "center": [3580, 750], "radius_mm": 360, "name": "Entry Architectural Shrub"},
    {"id": "L-TREE-4", "zone": "EXT-03", "kind": "tree", "center": [1050, 12650], "radius_mm": 650, "name": "Rear Courtyard Japanese Maple"},
    {"id": "L-TREE-5", "zone": "EXT-03", "kind": "tree", "center": [4550, 12720], "radius_mm": 540, "name": "Ornamental Bamboo / Palm"},
    {"id": "L-TREE-6", "zone": "EXT-03", "kind": "shrub_cluster", "center": [2850, 12950], "radius_mm": 400, "name": "Shade Fern & River Stone Bed"},
    {"id": "L-TREE-7", "zone": "EXT-04", "kind": "shrub_cluster", "center": [8820, 12050], "radius_mm": 280, "name": "Terrace Planter Box"},
]

# ---------------------------------------------------------------------------
# 8. MATERIALS (Three.js PBR + 2D Presentation)
# ---------------------------------------------------------------------------
materials = {
    "exterior_stucco_charcoal_white": {"name": "Architectural Smooth White Stucco", "color_hex": "#F1EFEA", "roughness": 0.82, "metalness": 0.0},
    "interior_gypsum_warm_white": {"name": "Warm Alabaster Gypsum Plaster", "color_hex": "#F6F4EF", "roughness": 0.88, "metalness": 0.0},
    "interior_gypsum_acoustic": {"name": "Acoustic Insulated Drywall", "color_hex": "#F3F1EC", "roughness": 0.88, "metalness": 0.0},
    "interior_gypsum_moisture_resistant": {"name": "Moisture-Resistant Plaster & Tile Backer", "color_hex": "#ECEAE4", "roughness": 0.75, "metalness": 0.0},
    "engineered_white_oak": {"name": "Wide-Plank Engineered White Oak", "color_hex": "#C9AD88", "roughness": 0.55, "metalness": 0.0, "plank_mm": [180, 1200]},
    "large_format_limestone": {"name": "Large-Format Honed Warm Limestone (900x900)", "color_hex": "#DDD6C8", "roughness": 0.45, "metalness": 0.0, "tile_mm": [900, 900]},
    "honed_travertine_tile": {"name": "Honed Travertine Wet-Area Tile (600x600)", "color_hex": "#CFC7B8", "roughness": 0.50, "metalness": 0.0, "tile_mm": [600, 600]},
    "matte_porcelain_grey": {"name": "Anti-Slip Matte Grey Porcelain (600x600)", "color_hex": "#B7B9B6", "roughness": 0.65, "metalness": 0.0, "tile_mm": [600, 600]},
    "flamed_basalt_pavers": {"name": "Flamed Dark Basalt Stone Pavers", "color_hex": "#5E636B", "roughness": 0.78, "metalness": 0.05},
    "teak_timber_deck": {"name": "Natural Oiled Teak Outdoor Decking", "color_hex": "#A87B51", "roughness": 0.62, "metalness": 0.0},
    "manicured_lawn_and_stepping_stones": {"name": "Zoysia Lawn & Honed Concrete Pavers", "color_hex": "#6E8F5B", "roughness": 0.92, "metalness": 0.0},
    "tropical_lawn_and_pebble_border": {"name": "Lush Courtyard Turf & River Pebbles", "color_hex": "#658852", "roughness": 0.92, "metalness": 0.0},
    "fluted_walnut_millwork": {"name": "Fluted American Walnut Veneer", "color_hex": "#6E4B32", "roughness": 0.48, "metalness": 0.0},
    "matte_charcoal_quartz": {"name": "Honed Charcoal Quartz & Matte Cabinetry", "color_hex": "#3B3F46", "roughness": 0.35, "metalness": 0.05},
    "black_anodized_aluminum_low_e_glass": {"name": "Black Anodized Aluminum Frame + Low-E Glass", "color_hex": "#1E242B", "roughness": 0.25, "metalness": 0.75},
}

# ---------------------------------------------------------------------------
# 9. WALKTHROUGH WAYPOINTS (For Future Three.js Reconstruction)
# ---------------------------------------------------------------------------
# Three.js mapping: three_x = x_mm / 1000, three_y = z_mm / 1000, three_z = -y_mm / 1000
waypoints = [
    {"id": "WP-01", "name": "Street Approach & Front Garden", "room": "EXT-02", "position_mm": [4700, 500, 1650], "look_at_mm": [4700, 2100, 1500]},
    {"id": "WP-02", "name": "Main Entrance Foyer", "room": "RM-07", "position_mm": [4700, 2800, 1650], "look_at_mm": [5400, 6200, 1450]},
    {"id": "WP-03", "name": "Entry Gallery & Dining Threshold", "room": "RM-08", "position_mm": [5400, 4600, 1650], "look_at_mm": [7000, 9500, 1400]},
    {"id": "WP-04", "name": "Open-Plan Dining & Kitchen", "room": "RM-10", "position_mm": [5900, 6600, 1650], "look_at_mm": [8100, 6200, 1300]},
    {"id": "WP-05", "name": "Living Room Facing Rear Terrace", "room": "RM-09", "position_mm": [6600, 9600, 1650], "look_at_mm": [7200, 12600, 1300]},
    {"id": "WP-06", "name": "Rear Outdoor Terrace & Garden", "room": "EXT-04", "position_mm": [7000, 12400, 1650], "look_at_mm": [2200, 12500, 1350]},
    {"id": "WP-07", "name": "Master Suite Threshold", "room": "RM-01", "position_mm": [3200, 8900, 1650], "look_at_mm": [1400, 10200, 1200]},
    {"id": "WP-08", "name": "Master Ensuite Bathroom", "room": "RM-02", "position_mm": [4450, 9900, 1650], "look_at_mm": [4750, 11100, 1400]},
    {"id": "WP-09", "name": "Bedroom 2", "room": "RM-03", "position_mm": [2600, 7400, 1650], "look_at_mm": [1200, 6200, 1200]},
    {"id": "WP-10", "name": "Bedroom 3", "room": "RM-04", "position_mm": [6450, 4450, 1650], "look_at_mm": [7800, 3100, 1200]},
]

# ---------------------------------------------------------------------------
# 10. MATHEMATICAL VALIDATION
# ---------------------------------------------------------------------------
site_area_exact = poly_area_m2(site_boundary)
site_perim_exact = poly_perimeter_m(site_boundary)
footprint_exact = poly_area_m2(building_footprint_poly)
outdoor_exact = sum(rect_area_m2(z["bounds"]["x0"], z["bounds"]["y0"], z["bounds"]["x1"], z["bounds"]["y1"]) for z in outdoor_zones)
wall_area_exact = sum(rect_area_m2(*w["rect"]) for w in walls)
usable_interior_exact = sum(
    sum(rect_area_m2(*sr) for sr in r["sub_rects"]) if "sub_rects" in r else poly_area_m2(r["polygon"])
    for r in rooms
)

# Verify exact partition of site area & building footprint!
assert abs((footprint_exact + outdoor_exact) - site_area_exact) < 1e-6, (
    f"Site area mismatch: footprint({footprint_exact}) + outdoor({outdoor_exact}) != site({site_area_exact})"
)
assert abs((usable_interior_exact + wall_area_exact) - footprint_exact) < 1e-6, (
    f"Footprint area mismatch: usable({usable_interior_exact:.6f}) + walls({wall_area_exact:.6f}) != footprint({footprint_exact:.6f})"
)

# Verify all wall rects are pairwise non-overlapping
for i in range(len(walls)):
    x0, y0, x1, y1 = walls[i]["rect"]
    assert x0 < x1 and y0 < y1, f"Degenerate wall {walls[i]['id']}"
    assert 0 <= x0 and x1 <= SITE_W and 0 <= y0 and y1 <= SITE_D, f"Wall {walls[i]['id']} outside site"
    for j in range(i + 1, len(walls)):
        ax0, ay0, ax1, ay1 = walls[j]["rect"]
        ox = min(x1, ax1) - max(x0, ax0)
        oy = min(y1, ay1) - max(y0, ay0)
        assert not (ox > 0 and oy > 0), f"Overlapping walls {walls[i]['id']} and {walls[j]['id']}"

# Verify every door & window opening lies strictly inside its host wall
wall_map = {w["id"]: w for w in walls}
for item in doors + windows:
    w = wall_map[item["host_wall"]]
    wx0, wy0, wx1, wy1 = w["rect"]
    ox0, oy0, ox1, oy1 = item["opening"]
    assert ox0 >= wx0 and ox1 <= wx1 and oy0 >= wy0 and oy1 <= wy1, (
        f"Opening {item['id']} ({item['opening']}) exceeds host wall {w['id']} ({w['rect']})"
    )

# Verify every furniture item stays inside its assigned room/zone bounds
room_bounds = {}
for r in rooms:
    xs = [p[0] for p in r["polygon"]]
    ys = [p[1] for p in r["polygon"]]
    room_bounds[r["id"]] = (min(xs), min(ys), max(xs), max(ys))
for z in outdoor_zones:
    b = z["bounds"]
    room_bounds[z["id"]] = (b["x0"], b["y0"], b["x1"], b["y1"])

for f in furniture:
    fx0, fy0, fx1, fy1 = f["rect"]
    rx0, ry0, rx1, ry1 = room_bounds[f["room"]]
    assert fx0 >= rx0 and fx1 <= rx1 and fy0 >= ry0 and fy1 <= ry1, (
        f"Furniture {f['id']} ({f['rect']}) exceeds room {f['room']} ({rx0, ry0, rx1, ry1})"
    )

# ---------------------------------------------------------------------------
# 11. ASSEMBLE & WRITE JSON SPECIFICATION
# ---------------------------------------------------------------------------
spec = {
    "meta": {
        "project_name": "Modern Single-Story Luxury Residence — Villa Aurelia 123",
        "drawing_title": "GROUND FLOOR ARCHITECTURAL PLAN",
        "sheet_number": "A-101",
        "scale": "1:50",
        "units": "mm",
        "ceiling_height_mm": CEIL_H,
        "exterior_wall_thickness_mm": EXT_T,
        "interior_wall_thickness_mm": INT_T,
        "coordinate_system": {
            "origin": "South-West (Front-Left) corner of site plot [0, 0]",
            "x_axis": "+East (0 to 9,144 mm)",
            "y_axis": "+North (0 to 13,500 mm, street at Y=0)",
            "north_arrow_deg": 90,
            "threejs_mapping": "threeX = x_mm / 1000, threeY = elevation_mm / 1000, threeZ = -y_mm / 1000",
        },
    },
    "site": {
        "width_mm": SITE_W,
        "depth_mm": SITE_D,
        "boundary_polygon": site_boundary,
        "total_land_area_m2": round(site_area_exact, 2),
        "total_land_area_exact_m2": round(site_area_exact, 4),
        "total_land_area_sqft": round(site_area_exact * 10.7639104, 2),
        "total_perimeter_m": round(site_perim_exact, 2),
        "total_perimeter_exact_m": round(site_perim_exact, 4),
        "street_frontage": "South edge (Y = 0)",
    },
    "area_summary": {
        "total_land_area_m2": round(site_area_exact, 2),
        "building_footprint_m2": round(footprint_exact, 2),
        "building_footprint_pct": round((footprint_exact / site_area_exact) * 100, 2),
        "usable_interior_floor_area_m2": round(usable_interior_exact, 2),
        "usable_interior_floor_area_sqft": round(usable_interior_exact * 10.7639104, 2),
        "structural_wall_area_m2": round(wall_area_exact, 2),
        "total_outdoor_area_m2": round(outdoor_exact, 2),
        "total_outdoor_area_pct": round((outdoor_exact / site_area_exact) * 100, 2),
        "carport_area_m2": outdoor_zones[0]["area_m2"],
        "front_garden_area_m2": outdoor_zones[1]["area_m2"],
        "rear_garden_area_m2": outdoor_zones[2]["area_m2"],
        "rear_terrace_area_m2": outdoor_zones[3]["area_m2"],
        "validation_residual_m2": round(abs((usable_interior_exact + wall_area_exact + outdoor_exact) - site_area_exact), 6),
    },
    "building_footprint_polygon": building_footprint_poly,
    "outdoor_zones": outdoor_zones,
    "rooms": rooms,
    "walls": walls,
    "doors": doors,
    "windows": windows,
    "furniture": furniture,
    "landscaping": landscaping,
    "materials": materials,
    "walkthrough_waypoints": waypoints,
    "assumptions_and_constraints": [
        "Exact Plot Reconciliation: Prompt specifies 123.44 m² (1,328.74 sq ft), 45.29 m perimeter, and ~9.14 x 13.50 m. Using 9,144 mm (30 ft) x 13,500 mm yields 123.444 m² (123.44 m² / 1,328.74 sq ft) and 45.288 m (45.29 m) perimeter — matching all four site metrics to 2 decimal places.",
        "Zero Side-Yard Setbacks: East and West exterior walls are sited on the side property lines (standard urban compact-lot typology) to maintain generous room widths, 1,100 mm clear circulation, a 3.04 x 5.00 m carport, front garden (1.90 m deep), and rear garden/terrace (1.80 m deep). Local zoning requiring side setbacks (e.g., 1.0–1.5 m) would require a 2-story scheme or reduced bedroom count.",
        "Orientation & Street Access: Main road assumed along the South boundary (Y = 0) with true North oriented straight up (+Y). Actual solar path / local street orientation must be verified against the land survey.",
        "Shared Bathroom Ventilation: Positioned in the central wet core to maximize perimeter daylight for all 3 bedrooms, living room, and laundry; therefore requires a dedicated roof-ducted inline exhaust fan (minimum 50 L/s) or tubular skylight.",
        "Structural & MEP Scope: Wall thicknesses follow 200 mm exterior masonry/insulated cavity and 120 mm interior partitions; structural column grid, foundation footings, roof drainage, and septic/municipal utility tie-ins require local structural/MEP engineering sign-off.",
        "Local Building Codes: Lot coverage is 64.95% (80.17 m² of 123.44 m²), with 35.05% open/semi-open outdoor area (43.27 m²). Confirm against municipal FAR/KDB, front setback (GSB), and fire-rated zero-lot-line wall requirements.",
    ],
}

spec_path = OUT_DIR / "floorplan-spec.json"
spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")

print("VALIDATION PASSED!")
print(json.dumps(spec["area_summary"], indent=2))
print(f"Rooms: {len(rooms)}, Walls: {len(walls)}, Doors: {len(doors)}, Windows: {len(windows)}, Furniture: {len(furniture)}")
