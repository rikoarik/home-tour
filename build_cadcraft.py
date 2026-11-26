#!/usr/bin/env python3
"""
Builds the native CADCraft architectural floor plan (DXF, DWG, SVG, PNG)
directly from `floorplan-spec.json` using `cadcraft-cli`.
"""

import json
import math
import subprocess
from pathlib import Path

OUT_DIR = Path("/Users/macbookm2/.gemini/antigravity/scratch/luxury-residence-floorplan")
SPEC_PATH = OUT_DIR / "floorplan-spec.json"
CADCRAFT_CLI = "/Users/macbookm2/.awsm/native/cadcraft/bin/cadcraft-cli"

spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))

cmds = []


def add_cmd(cid, params=None):
    cmds.append((cid, params or {}))


def subtract_openings(wall_rect, openings, orientation):
    """Splits a wall rectangle [x0,y0,x1,y1] into solid wall segments excluding openings."""
    wx0, wy0, wx1, wy1 = wall_rect
    if orientation == "H":
        cuts = sorted([(o[0], o[2]) for o in openings], key=lambda c: c[0])
        segs = []
        cur = wx0
        for c0, c1 in cuts:
            if c0 > cur:
                segs.append([cur, wy0, c0, wy1])
            cur = max(cur, c1)
        if cur < wx1:
            segs.append([cur, wy0, wx1, wy1])
        return segs
    else:
        cuts = sorted([(o[1], o[3]) for o in openings], key=lambda c: c[0])
        segs = []
        cur = wy0
        for c0, c1 in cuts:
            if c0 > cur:
                segs.append([wx0, cur, wx1, c0])
            cur = max(cur, c1)
        if cur < wy1:
            segs.append([wx0, cur, wx1, wy1])
        return segs


def rect_pline(x0, y0, x1, y1, width=None):
    p = {"vertices": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], "closed": True}
    if width is not None:
        p["width"] = width
    add_cmd("pline", p)


def rect_solid(x0, y0, x1, y1):
    # AutoCAD SOLID uses bowtie corner order: bottom-left, bottom-right, top-left, top-right
    add_cmd("solid", {"points": [[x0, y0], [x1, y0], [x0, y1], [x1, y1]]})


def line(p1, p2):
    add_cmd("line", {"points": [p1, p2]})


def text_at(x, y, txt, height=160, justify="MC", rotation=0):
    p = {"at": [x, y], "text": txt, "height": height, "justify": justify}
    if rotation:
        p["rotation"] = rotation
    add_cmd("text", p)


# ---------------------------------------------------------------------------
# 1. UNITS, LAYERS & DIMENSION STYLE
# ---------------------------------------------------------------------------
add_cmd("units", {"lunits": 2, "luprec": 0, "insunits": 4})  # Decimal, 0 prec, Millimeters

layers = [
    ("A-SHEET-BORDER", "148,163,184", 0.35),
    ("A-SITE-BNDY", "250,204,21", 0.35),
    ("A-WALL-EXTR", "248,250,252", 0.50),
    ("A-WALL-EXTR-FILL", "71,85,105", 0.13),
    ("A-WALL-INTR", "203,213,225", 0.30),
    ("A-WALL-INTR-FILL", "51,65,85", 0.13),
    ("A-DOOR", "245,158,11", 0.25),
    ("A-DOOR-SWING", "148,163,184", 0.13),
    ("A-GLAZ", "56,189,248", 0.25),
    ("A-FURN", "186,200,218", 0.18),
    ("A-SANITARY", "125,211,252", 0.18),
    ("A-LAND", "74,222,128", 0.18),
    ("A-DIMS", "34,211,238", 0.18),
    ("A-ANNO-ROOM", "241,245,249", 0.20),
    ("A-ANNO-TAG", "34,211,238", 0.18),
    ("A-ANNO-SCHD", "226,232,240", 0.18),
    ("A-TITLE", "248,250,252", 0.30),
]

for name, rgb, lw in layers:
    add_cmd("layer.new", {"name": name, "color": rgb, "lineweight": lw})

# Configure clean architectural metric dimension style (scale 1:50 -> 150 mm text height = 3 mm on sheet)
add_cmd("dimstyle", {
    "name": "ARCH_1_50",
    "current": True,
    "DIMTXT": 150,
    "DIMASZ": 100,
    "DIMTSZ": 80,
    "DIMEXE": 120,
    "DIMEXO": 100,
    "DIMGAP": 60,
    "DIMDEC": 0,
    "DIMLUNIT": 2,
    "DIMTAD": 1,
})

# ---------------------------------------------------------------------------
# 2. SITE BOUNDARY & OUTDOOR ZONES
# ---------------------------------------------------------------------------
SITE_W = spec["site"]["width_mm"]
SITE_D = spec["site"]["depth_mm"]

add_cmd("layer.current", {"name": "A-SITE-BNDY"})
rect_pline(0, 0, SITE_W, SITE_D, width=35)

# Building footprint subtle outline reference & outdoor zones
add_cmd("layer.current", {"name": "A-LAND"})
# Carport boundary & pergola canopy dashed lines (drawn as thin structural grid lines)
for y_slat in range(600, 4800, 600):
    line([100, y_slat], [2944, y_slat])

# Rear terrace timber decking lines (X: 5490..9144, Y: 11700..13500)
rect_pline(5490, 11700, SITE_W, SITE_D)
for x_plank in range(5670, SITE_W, 180):
    line([x_plank, 11700], [x_plank, SITE_D])

# Landscaping: stepping stones, trees, shrubs
for item in spec["landscaping"]:
    if item["kind"] == "stepping_stone":
        rect_pline(*item["rect"])
    else:
        cx, cy = item["center"]
        r = item["radius_mm"]
        add_cmd("circle", {"center": [cx, cy], "radius": r})
        add_cmd("circle", {"center": [cx, cy], "radius": r * 0.62})
        add_cmd("circle", {"center": [cx, cy], "radius": r * 0.14})
        # Radial canopy ribs for architectural tree symbol
        for deg in range(0, 360, 45):
            rad = math.radians(deg)
            line([cx + r * 0.2 * math.cos(rad), cy + r * 0.2 * math.sin(rad)],
                 [cx + r * 0.92 * math.cos(rad), cy + r * 0.92 * math.sin(rad)])

# ---------------------------------------------------------------------------
# 3. WALLS (Exterior 200 mm & Interior 120 mm) WITH EXACT OPENING CUTOUTS
# ---------------------------------------------------------------------------
openings_by_wall = {}
for op in spec["doors"] + spec["windows"]:
    openings_by_wall.setdefault(op["host_wall"], []).append(op["opening"])

for w in spec["walls"]:
    segs = subtract_openings(w["rect"], openings_by_wall.get(w["id"], []), w["orientation"])
    fill_layer = "A-WALL-EXTR-FILL" if w["category"] == "exterior" else "A-WALL-INTR-FILL"
    edge_layer = "A-WALL-EXTR" if w["category"] == "exterior" else "A-WALL-INTR"
    add_cmd("layer.current", {"name": fill_layer})
    for seg in segs:
        rect_solid(*seg)
    add_cmd("layer.current", {"name": edge_layer})
    for seg in segs:
        rect_pline(*seg)

# ---------------------------------------------------------------------------
# 4. DOORS (Jambs, Leaves, Swing Arcs, Sliding Panels & Tags)
# ---------------------------------------------------------------------------
for d in spec["doors"]:
    ox0, oy0, ox1, oy1 = d["opening"]
    add_cmd("layer.current", {"name": "A-DOOR"})
    # Door jamb ticks
    if (ox1 - ox0) > (oy1 - oy0):  # Horizontal wall opening
        line([ox0, oy0], [ox0, oy1])
        line([ox1, oy0], [ox1, oy1])
    else:  # Vertical wall opening
        line([ox0, oy0], [ox1, oy0])
        line([ox0, oy1], [ox1, oy1])

    if d["swing_arc"]:
        hx, hy = d["hinge"]
        ex, ey = d["leaf_open_end"]
        # Draw 45 mm thick door leaf polygon
        dx, dy = ex - hx, ey - hy
        L = math.hypot(dx, dy)
        nx, ny = -dy / L * 45, dx / L * 45
        add_cmd("pline", {
            "vertices": [[hx, hy], [ex, ey], [ex + nx, ey + ny], [hx + nx, hy + ny]],
            "closed": True,
        })
        add_cmd("layer.current", {"name": "A-DOOR-SWING"})
        arc = d["swing_arc"]
        add_cmd("arc", {
            "center": arc["center"],
            "radius": arc["radius"],
            "start": arc["start_deg"],
            "end": arc["end_deg"],
        })
    elif d.get("sliding_panels"):
        # 3-panel sliding glass door tracks
        n = d["sliding_panels"]
        w_span = ox1 - ox0
        pw = w_span / n
        ym = (oy0 + oy1) / 2
        line([ox0, oy0 + 30], [ox1, oy0 + 30])
        line([ox0, oy1 - 30], [ox1, oy1 - 30])
        for i in range(n):
            px0 = ox0 + i * pw
            px1 = px0 + pw
            y_off = ym - 25 if i % 2 == 0 else ym + 25
            rect_pline(px0, y_off - 15, px1, y_off + 15)
    elif d.get("sliding_track"):
        p1, p2 = d["sliding_track"]
        line(p1, p2)
        rect_pline(p1[0] - 20, p1[1], p1[0] + 20, p1[1] + (p2[1] - p1[1]) * 0.65)

    # Door tag circle
    add_cmd("layer.current", {"name": "A-ANNO-TAG"})
    tx, ty = (ox0 + ox1) / 2, (oy0 + oy1) / 2
    if d["id"] == "D1":
        ty -= 280
    elif d["id"] == "D8":
        ty += 280
    elif d["id"] in ("D2", "D3", "D5", "D7"):
        tx += 260
    elif d["id"] in ("D4", "D6"):
        tx -= 260
    add_cmd("circle", {"center": [tx, ty], "radius": 140})
    text_at(tx, ty, d["id"], height=110)

# ---------------------------------------------------------------------------
# 5. WINDOWS (Frames, Glass Lines & Tags)
# ---------------------------------------------------------------------------
for win in spec["windows"]:
    ox0, oy0, ox1, oy1 = win["opening"]
    add_cmd("layer.current", {"name": "A-GLAZ"})
    rect_pline(ox0, oy0, ox1, oy1)
    if (ox1 - ox0) > (oy1 - oy0):
        ym = (oy0 + oy1) / 2
        line([ox0, ym - 25], [ox1, ym - 25])
        line([ox0, ym + 25], [ox1, ym + 25])
        # Mullion
        if win["width_mm"] >= 1400:
            xm = (ox0 + ox1) / 2
            line([xm, oy0], [xm, oy1])
    else:
        xm = (ox0 + ox1) / 2
        line([xm - 25, oy0], [xm - 25, oy1])
        line([xm + 25, oy0], [xm + 25, oy1])

    # Window tag hexagon/box outside wall
    add_cmd("layer.current", {"name": "A-ANNO-TAG"})
    tx, ty = (ox0 + ox1) / 2, (oy0 + oy1) / 2
    if win["host_wall"] == "EW-S1":
        ty = oy0 - 260
    elif win["host_wall"] == "EW-S2":
        ty = oy0 - 260
    elif win["host_wall"] == "EW-W2":
        tx = ox0 - 280
    elif win["host_wall"] == "EW-N1":
        ty = oy1 + 260
    rect_pline(tx - 150, ty - 110, tx + 150, ty + 110)
    text_at(tx, ty, win["id"], height=105)

# ---------------------------------------------------------------------------
# 6. FURNITURE & SANITARY FIXTURES (Detailed Architectural Blocks)
# ---------------------------------------------------------------------------
for f in spec["furniture"]:
    x0, y0, x1, y1 = f["rect"]
    w_box, h_box = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    kind = f["kind"]

    is_sanitary = kind in ("shower", "vanity", "wc", "kitchen_sink", "utility_sink", "washer_dryer")
    add_cmd("layer.current", {"name": "A-SANITARY" if is_sanitary else "A-FURN"})

    if kind in ("bed_king", "bed_queen"):
        rect_pline(x0, y0, x1, y1)
        # Headboard & pillows depending on rotation (90 = head West, 270 = head East)
        if f["rotation_deg"] == 90:
            rect_pline(x0, y0, x0 + 110, y1)  # headboard
            py_pad = 120
            pw = (h_box - 3 * py_pad) / 2
            rect_pline(x0 + 160, y0 + py_pad, x0 + 540, y0 + py_pad + pw)
            rect_pline(x0 + 160, y0 + 2 * py_pad + pw, x0 + 540, y1 - py_pad)
            line([x0 + 720, y0], [x0 + 720, y1])  # duvet fold
        else:
            rect_pline(x1 - 110, y0, x1, y1)  # headboard East
            py_pad = 120
            pw = (h_box - 3 * py_pad) / 2
            rect_pline(x1 - 540, y0 + py_pad, x1 - 160, y0 + py_pad + pw)
            rect_pline(x1 - 540, y0 + 2 * py_pad + pw, x1 - 160, y1 - py_pad)
            line([x1 - 720, y0], [x1 - 720, y1])

    elif kind == "wardrobe":
        rect_pline(x0, y0, x1, y1)
        # Diagonal cross + clothing rail line
        if w_box > h_box:
            line([x0, cy], [x1, cy])
            for xi in range(int(x0 + 600), int(x1), 600):
                line([xi, y0], [xi, y1])
        else:
            line([cx, y0], [cx, y1])
            for yi in range(int(y0 + 600), int(y1), 600):
                line([x0, yi], [x1, yi])

    elif kind == "sofa_l":
        rect_pline(x0, y0, x1, y1)
        # Backrest West + 3 seat cushions
        rect_pline(x0, y0, x0 + 220, y1)
        seg_h = h_box / 3
        for i in range(1, 3):
            line([x0 + 220, y0 + i * seg_h], [x1, y0 + i * seg_h])

    elif kind == "dining_table_6":
        rect_pline(x0, y0, x1, y1)
        # 6 chairs (3 West, 3 East)
        for i in range(3):
            cy_c = y0 + 300 + i * 600
            rect_pline(x0 - 380, cy_c - 210, x0 - 40, cy_c + 210)
            rect_pline(x1 + 40, cy_c - 210, x1 + 380, cy_c + 210)

    elif kind == "shower":
        rect_pline(x0, y0, x1, y1)
        # Floor slope X lines + circular drain
        line([x0, y0], [x1, y1])
        line([x0, y1], [x1, y0])
        add_cmd("circle", {"center": [cx, cy], "radius": 55})

    elif kind == "vanity":
        rect_pline(x0, y0, x1, y1)
        if w_box >= h_box:
            add_cmd("ellipse", {"center": [cx, cy], "major": [w_box * 0.34, 0], "ratio": max(0.1, min(1.0, h_box / w_box))})
        else:
            add_cmd("ellipse", {"center": [cx, cy], "major": [0, h_box * 0.34], "ratio": max(0.1, min(1.0, w_box / h_box))})

    elif kind == "wc":
        rect_pline(x0, y0, x1, y1)
        if f["rotation_deg"] == 270:  # Tank on East
            rect_pline(x1 - 170, y0, x1, y1)
            add_cmd("ellipse", {"center": [x0 + (w_box - 170) * 0.52, cy], "major": [(w_box - 170) * 0.45, 0], "ratio": 0.72})
        else:  # Tank on West
            rect_pline(x0, y0, x0 + 170, y1)
            add_cmd("ellipse", {"center": [x1 - (w_box - 170) * 0.52, cy], "major": [(w_box - 170) * 0.45, 0], "ratio": 0.72})

    elif kind == "cooktop":
        rect_pline(x0, y0, x1, y1)
        for bx in (x0 + w_box * 0.30, x0 + w_box * 0.70):
            for by in (y0 + h_box * 0.28, y0 + h_box * 0.72):
                add_cmd("circle", {"center": [bx, by], "radius": 78})

    elif kind == "kitchen_sink":
        rect_pline(x0, y0, x1, y1)
        rect_pline(x0 + 40, y0 + 50, cx - 25, y1 - 50)
        rect_pline(cx + 25, y0 + 50, x1 - 40, y1 - 50)
        add_cmd("circle", {"center": [(x0 + cx) / 2, cy], "radius": 28})
        add_cmd("circle", {"center": [(cx + x1) / 2, cy], "radius": 28})

    elif kind == "car":
        # Sleek architectural sedan outline in carport
        rect_pline(x0 + 120, y0, x1 - 120, y1)
        rect_pline(x0, y0 + 450, x1, y1 - 450)
        rect_pline(x0 + 220, y0 + 1150, x1 - 220, y1 - 1250)  # cabin roof
        line([x0 + 150, y0 + 820], [x1 - 150, y0 + 820])      # rear glass
        line([x0 + 150, y1 - 920], [x1 - 150, y1 - 920])      # windshield

    elif kind == "plant_pot":
        add_cmd("circle", {"center": [cx, cy], "radius": min(w_box, h_box) / 2})
        add_cmd("circle", {"center": [cx, cy], "radius": min(w_box, h_box) * 0.3})

    elif kind == "desk":
        rect_pline(x0, y0, x1, y1)
        # Office chair tucked North of desk
        add_cmd("circle", {"center": [cx, y1 + 260], "radius": 210})

    else:
        rect_pline(x0, y0, x1, y1)

# ---------------------------------------------------------------------------
# 7. ROOM LABELS & CALCULATED FLOOR AREAS
# ---------------------------------------------------------------------------
add_cmd("layer.current", {"name": "A-ANNO-ROOM"})
for r in spec["rooms"]:
    lx, ly = r["label_pos"]
    lines = r["short_name"].split("\n")
    if len(lines) == 1:
        text_at(lx, ly + 110, lines[0], height=145)
        text_at(lx, ly - 100, f"{r['area_m2']:.2f} m2", height=120)
    else:
        text_at(lx, ly + 170, lines[0], height=130)
        text_at(lx, ly + 10, lines[1], height=130)
        text_at(lx, ly - 160, f"{r['area_m2']:.2f} m2", height=115)

# Outdoor zone labels
outdoor_labels = [
    (1522, 2500, "CARPORT", f"{spec['outdoor_zones'][0]['area_m2']:.2f} m2"),
    (6094, 950, "FRONT GARDEN", f"{spec['outdoor_zones'][1]['area_m2']:.2f} m2"),
    (2745, 12550, "REAR GARDEN", f"{spec['outdoor_zones'][2]['area_m2']:.2f} m2"),
    (7317, 12600, "REAR TERRACE", f"{spec['outdoor_zones'][3]['area_m2']:.2f} m2"),
]
for ox, oy, nm, ar in outdoor_labels:
    text_at(ox, oy + 90, nm, height=135)
    text_at(ox, oy - 110, ar, height=110)

# ---------------------------------------------------------------------------
# 8. EXTERNAL & INTERNAL DIMENSION LINES (MILLIMETERS)
# ---------------------------------------------------------------------------
add_cmd("layer.current", {"name": "A-DIMS"})

# Overall External Dimensions
add_cmd("dimlinear", {"p1": [0, 0], "p2": [SITE_W, 0], "at": [SITE_W / 2, -1350]})
add_cmd("dimlinear", {"p1": [0, 0], "p2": [3044, 0], "at": [1522, -700]})
add_cmd("dimlinear", {"p1": [3044, 0], "p2": [SITE_W, 0], "at": [6094, -700]})

# North Top External Dimensions
add_cmd("dimlinear", {"p1": [0, SITE_D], "p2": [SITE_W, SITE_D], "at": [SITE_W / 2, SITE_D + 1350]})
add_cmd("dimlinear", {"p1": [0, 11700], "p2": [3860, 11700], "at": [1930, SITE_D + 700]})
add_cmd("dimlinear", {"p1": [3860, 11700], "p2": [5430, 11700], "at": [4645, SITE_D + 700]})
add_cmd("dimlinear", {"p1": [5430, 11700], "p2": [SITE_W, 11700], "at": [7287, SITE_D + 700]})

# West Left External Dimensions
add_cmd("dimlinear", {"p1": [0, 0], "p2": [0, SITE_D], "at": [-1450, SITE_D / 2]})
add_cmd("dimlinear", {"p1": [0, 0], "p2": [0, 5000], "at": [-750, 2500]})
add_cmd("dimlinear", {"p1": [0, 5000], "p2": [0, 8140], "at": [-750, 6570]})
add_cmd("dimlinear", {"p1": [0, 8140], "p2": [0, 11700], "at": [-750, 9920]})
add_cmd("dimlinear", {"p1": [0, 11700], "p2": [0, SITE_D], "at": [-750, 12600]})

# East Right External Dimensions
add_cmd("dimlinear", {"p1": [SITE_W, 0], "p2": [SITE_W, SITE_D], "at": [SITE_W + 1450, SITE_D / 2]})
add_cmd("dimlinear", {"p1": [SITE_W, 0], "p2": [SITE_W, 1900], "at": [SITE_W + 750, 950]})
add_cmd("dimlinear", {"p1": [SITE_W, 1900], "p2": [SITE_W, 5140], "at": [SITE_W + 750, 3520]})
add_cmd("dimlinear", {"p1": [SITE_W, 5140], "p2": [SITE_W, 8200], "at": [SITE_W + 750, 6670]})
add_cmd("dimlinear", {"p1": [SITE_W, 8200], "p2": [SITE_W, 11700], "at": [SITE_W + 750, 9950]})
add_cmd("dimlinear", {"p1": [SITE_W, 11700], "p2": [SITE_W, SITE_D], "at": [SITE_W + 750, 12600]})

# Key Internal Clear Room Dimensions
add_cmd("dimlinear", {"p1": [200, 11250], "p2": [3800, 11250], "at": [2000, 11250]})
add_cmd("dimlinear", {"p1": [5490, 11250], "p2": [8944, 11250], "at": [7217, 11250]})
add_cmd("dimlinear", {"p1": [200, 5450], "p2": [3124, 5450], "at": [1662, 5450]})
add_cmd("dimlinear", {"p1": [6084, 4800], "p2": [8944, 4800], "at": [7514, 4800]})
add_cmd("dimlinear", {"p1": [3244, 6800], "p2": [4744, 6800], "at": [3994, 6800]})

# ---------------------------------------------------------------------------
# 9. ARCHITECTURAL SHEET BORDER, SCHEDULES, NORTH ARROW, SCALE BAR & TITLE BLOCK
# ---------------------------------------------------------------------------
SHEET_X0, SHEET_Y0 = -2400, -2400
SHEET_X1, SHEET_Y1 = 19600, 15600

add_cmd("layer.current", {"name": "A-SHEET-BORDER"})
rect_pline(SHEET_X0, SHEET_Y0, SHEET_X1, SHEET_Y1, width=60)
rect_pline(SHEET_X0 + 180, SHEET_Y0 + 180, SHEET_X1 - 180, SHEET_Y1 - 180, width=25)

# Right-hand schedule & title block column: X = 11400 .. 19200
COL_X0, COL_X1 = 11400, 19200
add_cmd("layer.current", {"name": "A-ANNO-SCHD"})


def draw_cad_table(x0, y_top, col_widths, title, headers, rows, row_h=300):
    total_w = sum(col_widths)
    title_h = 380
    hdr_h = 330
    total_h = title_h + hdr_h + len(rows) * row_h
    y_bot = y_top - total_h
    # Outer frame & header bands
    rect_pline(x0, y_bot, x0 + total_w, y_top, width=25)
    line([x0, y_top - title_h], [x0 + total_w, y_top - title_h])
    line([x0, y_top - title_h - hdr_h], [x0 + total_w, y_top - title_h - hdr_h])
    text_at(x0 + 120, y_top - title_h / 2, title, height=145, justify="ML")
    # Column dividers & headers
    cx = x0
    for idx, (cw, h) in enumerate(zip(col_widths, headers)):
        if idx > 0:
            line([cx, y_bot], [cx, y_top - title_h])
        text_at(cx + 90, y_top - title_h - hdr_h / 2, h, height=115, justify="ML")
        cx += cw
    # Data rows
    for r_i, row in enumerate(rows):
        ry_top = y_top - title_h - hdr_h - r_i * row_h
        ry_mid = ry_top - row_h / 2
        if r_i > 0:
            line([x0, ry_top], [x0 + total_w, ry_top])
        cx = x0
        for cw, val in zip(col_widths, row):
            text_at(cx + 90, ry_mid, str(val), height=110, justify="ML")
            cx += cw
    return y_bot


# Room Schedule Table
room_rows = [[r["id"], r["name"], f"{r['width_mm']}x{r['depth_mm']}", f"{r['area_m2']:.2f} m2"] for r in spec["rooms"]]
y_next = draw_cad_table(
    COL_X0, 15100, [950, 3550, 1850, 1450],
    "ROOM SCHEDULE  (USABLE INTERIOR: 69.43 m2)",
    ["ID", "SPACE NAME", "CLEAR (mm)", "AREA"],
    room_rows, row_h=285
)

# Door Schedule Table (concise clean text without mid-word truncation)
door_short_type = {
    "D1": "Timber Pivot Entry",
    "D2": "Flush Timber Interior",
    "D3": "Flush Timber Interior",
    "D4": "Flush Timber Interior",
    "D5": "Moisture-Res. Bath",
    "D6": "Moisture-Res. Ensuite",
    "D7": "Cavity Pocket Door",
    "D8": "3-Panel Sliding Glass",
}
door_short_op = {
    "D1": "Inward-Left (Foyer)",
    "D2": "Inward-South (Master)",
    "D3": "Inward-North (Bed 2)",
    "D4": "Inward-North (Bed 3)",
    "D5": "Inward-South (Bath)",
    "D6": "Inward-South (Ensuite)",
    "D7": "Pocket Slide South",
    "D8": "Multi-Track Slide E/W",
}
door_rows = [[d["id"], f"{d['width_mm']}x{d['height_mm']}", door_short_type[d["id"]], door_short_op[d["id"]]] for d in spec["doors"]]
y_next = draw_cad_table(
    COL_X0, y_next - 320, [800, 1500, 2750, 2750],
    "DOOR SCHEDULE  (ALL DIMS IN MM)",
    ["TAG", "W x H", "SPECIFICATION", "OPERATION"],
    door_rows, row_h=275
)

# Window Schedule Table
win_rows = [[w["id"], f"{w['width_mm']}x{w['height_mm']}", f"Sill {w['sill_height_mm']}", w["orientation"]] for w in spec["windows"]]
y_next = draw_cad_table(
    COL_X0, y_next - 320, [800, 1550, 1550, 3900],
    "WINDOW SCHEDULE  (GLAZING & SILL HEIGHTS)",
    ["TAG", "W x H", "SILL (mm)", "ORIENTATION"],
    win_rows, row_h=275
)

# North Arrow (top-left of sheet)
add_cmd("layer.current", {"name": "A-TITLE"})
nx, ny = -1300, 14200
add_cmd("circle", {"center": [nx, ny], "radius": 450})
add_cmd("pline", {"vertices": [[nx, ny + 450], [nx - 180, ny - 220], [nx, ny - 80], [nx + 180, ny - 220]], "closed": True})
text_at(nx, ny + 680, "N", height=280)

# Graphic Scale Bar (1:50, 0 to 5 meters)
sx, sy = -1800, -1900
for i in range(5):
    x_seg = sx + i * 1000
    rect_pline(x_seg, sy, x_seg + 1000, sy + 140)
    if i % 2 == 0:
        rect_solid(x_seg, sy, x_seg + 1000, sy + 140)
    text_at(x_seg, sy - 160, f"{i}m", height=130)
text_at(sx + 5000, sy - 160, "5m", height=130)
text_at(sx + 2500, sy + 320, "GRAPHIC SCALE 1:50 (UNITS: MILLIMETERS)", height=150)

# Architectural Legend strip above Title Block
leg_top = y_next - 260
leg_bot = 1550
rect_pline(COL_X0, leg_bot, COL_X1, leg_top, width=20)
text_at(COL_X0 + 140, leg_top - 220, "ARCHITECTURAL LEGEND:  EXT WALL 200mm  |  INT WALL 120mm  |  CEIL 3,000mm", height=110, justify="ML")
text_at(COL_X0 + 140, leg_bot + 260, "SITE: 9,144 x 13,500mm (123.44 m2)  |  FOOTPRINT: 80.17 m2  |  OUTDOOR: 43.27 m2", height=105, justify="ML")

# Architectural Title Block (bottom-right)
rect_pline(COL_X0, -2100, COL_X1, 1300, width=40)
line([COL_X0, 520], [COL_X1, 520])
line([COL_X0, -250], [COL_X1, -250])
line([COL_X0, -1100], [COL_X1, -1100])
text_at((COL_X0 + COL_X1) / 2, 910, "VILLA AURELIA 123 - LUXURY SINGLE-STORY RESIDENCE", height=150)
text_at((COL_X0 + COL_X1) / 2, 135, "GROUND FLOOR ARCHITECTURAL PLAN  (SCALE 1:50)", height=135)
text_at((COL_X0 + COL_X1) / 2, -675, "LAND: 123.44 m2  |  FOOTPRINT: 80.17 m2 (64.95%)  |  USABLE: 69.43 m2", height=110)
text_at((COL_X0 + COL_X1) / 2, -1600, "SHEET A-101  |  CADCRAFT NATIVE DXF  |  UNITS: MILLIMETERS", height=120)

# ---------------------------------------------------------------------------
# 10. EXECUTE CADCRAFT CLI TO GENERATE DXF, DWG, SVG, AND PNG
# ---------------------------------------------------------------------------
dxf_path = OUT_DIR / "luxury-residence-floorplan.dxf"
dwg_path = OUT_DIR / "luxury-residence-floorplan.dwg"
cad_png_path = OUT_DIR / "luxury-residence-cadcraft-export.png"

cli_args = [CADCRAFT_CLI, "run", "--metric"]
for cid, params in cmds:
    cli_args.extend(["--cmd", f"{cid} {json.dumps(params, separators=(',', ':'))}"])
cli_args.extend([
    "--save", str(dxf_path),
    "--export", str(cad_png_path),
    "--window=-2600,-2600,19800,15800",
])

print(f"Running cadcraft-cli with {len(cmds)} native CAD commands...")
res = subprocess.run(cli_args, capture_output=True, text=True)
if res.returncode != 0:
    print("STDERR:", res.stderr[:2000])
    print("STDOUT:", res.stdout[:2000])
    raise SystemExit(res.returncode)

# Also convert DXF -> DWG for complete CAD handoff
res_dwg = subprocess.run([CADCRAFT_CLI, "convert", str(dxf_path), str(dwg_path)], capture_output=True, text=True)
if res_dwg.returncode != 0:
    print("DWG convert warning:", res_dwg.stderr)

# Inspect resulting DXF summary via cadcraft-cli info
res_info = subprocess.run([CADCRAFT_CLI, "info", str(dxf_path)], capture_output=True, text=True)
print("CADCRAFT DXF INFO:", res_info.stdout)
print("Saved:", dxf_path, dwg_path, cad_png_path)
