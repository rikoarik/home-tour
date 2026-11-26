#!/usr/bin/env python3
"""
Generates BOTH studio-grade orthographic 2D architectural floor plans directly
from the single-source-of-truth `floorplan-spec.json`:
  1. `floorplan-blueprint-v1.svg` / `.png` (Dark charcoal navy AutoCAD blueprint)
  2. `floorplan-presentation-v2.svg` / `.png` (Realistic materials, vegetation, soft shadows)

Both sheets use identical geometric coordinates from `floorplan-spec.json` and
render at 3840 x 2640 px orthographic top-down via headless Google Chrome.
"""

import json
import math
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

OUT_DIR = Path("/Users/macbookm2/.gemini/antigravity/scratch/luxury-residence-floorplan")
SPEC_PATH = OUT_DIR / "floorplan-spec.json"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))

SITE_W = spec["site"]["width_mm"]
SITE_D = spec["site"]["depth_mm"]

# Sheet canvas dimensions in px (3840 x 2640 -> ultra-crisp 4K architectural A1 landscape)
CANVAS_W = 3840
CANVAS_H = 2640

# Plan viewport mapping: exact orthographic scale (1 mm = SCALE px)
# Site is 9,144 mm wide x 13,500 mm tall; generous margin for header & 2 external dim tiers
SCALE = 0.143  # 9,144 mm -> 1,307.6 px wide; 13,500 mm -> 1,930.5 px tall
ORIGIN_X = 445.0
ORIGIN_Y = 2325.0  # South (y=0) at bottom; North (+Y) goes upward (SVG -Y)


def sx(x_mm):
    return ORIGIN_X + x_mm * SCALE


def sy(y_mm):
    return ORIGIN_Y - y_mm * SCALE


def sw(d_mm):
    return d_mm * SCALE


def subtract_openings(wall_rect, openings, orientation):
    wx0, wy0, wx1, wy1 = wall_rect
    if orientation == "H":
        cuts = sorted([(o[0], o[2]) for o in openings], key=lambda c: c[0])
        segs, cur = [], wx0
        for c0, c1 in cuts:
            if c0 > cur:
                segs.append([cur, wy0, c0, wy1])
            cur = max(cur, c1)
        if cur < wx1:
            segs.append([cur, wy0, wx1, wy1])
        return segs
    else:
        cuts = sorted([(o[1], o[3]) for o in openings], key=lambda c: c[0])
        segs, cur = [], wy0
        for c0, c1 in cuts:
            if c0 > cur:
                segs.append([wx0, cur, wx1, c0])
            cur = max(cur, c1)
        if cur < wy1:
            segs.append([wx0, cur, wx1, wy1])
        return segs


openings_by_wall = {}
for op in spec["doors"] + spec["windows"]:
    openings_by_wall.setdefault(op["host_wall"], []).append(op["opening"])


def svg_rect_mm(x0, y0, x1, y1, attrs=""):
    rx = sx(x0)
    ry = sy(y1)
    rw = sw(x1 - x0)
    rh = sw(y1 - y0)
    return f'<rect x="{rx:.2f}" y="{ry:.2f}" width="{rw:.2f}" height="{rh:.2f}" {attrs}/>'


def svg_poly_mm(pts, attrs=""):
    s = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in pts)
    return f'<polygon points="{s}" {attrs}/>'


def svg_line_mm(x1, y1, x2, y2, attrs=""):
    return f'<line x1="{sx(x1):.2f}" y1="{sy(y1):.2f}" x2="{sx(x2):.2f}" y2="{sy(y2):.2f}" {attrs}/>'


def svg_arc_mm(cx, cy, r_mm, start_deg, end_deg, attrs=""):
    # CAD CCW degrees -> SVG coordinates (Y flipped)
    a1 = math.radians(start_deg)
    a2 = math.radians(end_deg)
    x1, y1 = sx(cx + r_mm * math.cos(a1)), sy(cy + r_mm * math.sin(a1))
    x2, y2 = sx(cx + r_mm * math.cos(a2)), sy(cy + r_mm * math.sin(a2))
    r = sw(r_mm)
    # In SVG (y-down), CCW in CAD is sweep-flag=0
    large = 1 if abs(end_deg - start_deg) > 180 else 0
    return f'<path d="M {x1:.2f} {y1:.2f} A {r:.2f} {r:.2f} 0 {large} 0 {x2:.2f} {y2:.2f}" {attrs}/>'


def dim_h(x1, x2, y_ref, y_line, label=None, color="#22D3EE", text_color="#67E8F9", font_size=18):
    """Horizontal architectural dimension line with 45-degree ticks."""
    val = int(round(abs(x2 - x1)))
    txt = label if label is not None else f"{val:,}"
    out = []
    # Extension lines
    ext_dir = 1 if y_line >= y_ref else -1
    out.append(svg_line_mm(x1, y_ref + ext_dir * 80, x1, y_line + ext_dir * 120,
                           f'stroke="{color}" stroke-width="1.2" opacity="0.7"'))
    out.append(svg_line_mm(x2, y_ref + ext_dir * 80, x2, y_line + ext_dir * 120,
                           f'stroke="{color}" stroke-width="1.2" opacity="0.7"'))
    # Main dim line
    out.append(svg_line_mm(x1 - 80, y_line, x2 + 80, y_line,
                           f'stroke="{color}" stroke-width="1.6"'))
    # 45-deg architectural slash ticks
    tk = 75
    for xm in (x1, x2):
        out.append(svg_line_mm(xm - tk, y_line - tk, xm + tk, y_line + tk,
                               f'stroke="{color}" stroke-width="2.4"'))
    # Label above dim line
    mx, my = sx((x1 + x2) / 2), sy(y_line) - 8
    out.append(f'<text x="{mx:.2f}" y="{my:.2f}" text-anchor="middle" fill="{text_color}" '
               f'font-family="SF Mono, Menlo, Consolas, monospace" font-size="{font_size}" font-weight="600">{escape(txt)}</text>')
    return "\n".join(out)


def dim_v(y1, y2, x_ref, x_line, label=None, color="#22D3EE", text_color="#67E8F9", font_size=18):
    """Vertical architectural dimension line with 45-degree ticks."""
    val = int(round(abs(y2 - y1)))
    txt = label if label is not None else f"{val:,}"
    out = []
    ext_dir = 1 if x_line >= x_ref else -1
    out.append(svg_line_mm(x_ref + ext_dir * 80, y1, x_line + ext_dir * 120, y1,
                           f'stroke="{color}" stroke-width="1.2" opacity="0.7"'))
    out.append(svg_line_mm(x_ref + ext_dir * 80, y2, x_line + ext_dir * 120, y2,
                           f'stroke="{color}" stroke-width="1.2" opacity="0.7"'))
    out.append(svg_line_mm(x_line, y1 - 80, x_line, y2 + 80,
                           f'stroke="{color}" stroke-width="1.6"'))
    tk = 75
    for ym in (y1, y2):
        out.append(svg_line_mm(x_line - tk, ym - tk, x_line + tk, ym + tk,
                               f'stroke="{color}" stroke-width="2.4"'))
    mx, my = sx(x_line) - 10, sy((y1 + y2) / 2)
    out.append(f'<text x="{mx:.2f}" y="{my:.2f}" text-anchor="middle" fill="{text_color}" '
               f'font-family="SF Mono, Menlo, Consolas, monospace" font-size="{font_size}" font-weight="600" '
               f'transform="rotate(-90 {mx:.2f} {my:.2f})">{escape(txt)}</text>')
    return "\n".join(out)


def render_furniture_item(f, mode="blueprint"):
    """Draws detailed architectural furniture & fixtures for blueprint OR presentation mode."""
    x0, y0, x1, y1 = f["rect"]
    w_box, h_box = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    kind = f["kind"]
    bp = (mode == "blueprint")
    out = []

    stroke = "#94B8D7" if bp else "#4A433B"
    san_stroke = "#7DD3FC" if bp else "#5A6570"
    thin = "1.2" if bp else "1.1"
    shadow_attr = '' if bp else ' filter="url(#softShadow)"'

    if kind == "rug":
        if bp:
            out.append(svg_rect_mm(x0, y0, x1, y1, f'fill="none" stroke="#476682" stroke-width="1" stroke-dasharray="6 5"'))
        else:
            out.append(svg_rect_mm(x0, y0, x1, y1, 'fill="#EDE6DA" stroke="#D1C7B7" stroke-width="1.5" rx="4"'))
            out.append(svg_rect_mm(x0 + 90, y0 + 90, x1 - 90, y1 - 90, 'fill="none" stroke="#DFD6C7" stroke-width="1"'))
        return "\n".join(out)

    if kind in ("bed_king", "bed_queen"):
        bed_fill = "#132238" if bp else "#F5F1EA"
        duvet_fill = "#172B45" if bp else ("#D7CFC2" if kind == "bed_king" else "#CBD2D9")
        head_fill = "#334155" if bp else "#6E4E37"
        pillow_fill = "#1E3A5F" if bp else "#FFFFFF"
        out.append(f'<g{shadow_attr}>')
        out.append(svg_rect_mm(x0, y0, x1, y1, f'fill="{bed_fill}" stroke="{stroke}" stroke-width="1.6" rx="4"'))
        if f["rotation_deg"] == 90:
            # Headboard on West
            out.append(svg_rect_mm(x0, y0, x0 + 110, y1, f'fill="{head_fill}" stroke="{stroke}" stroke-width="1.4"'))
            out.append(svg_rect_mm(x0 + 700, y0 + 25, x1 - 25, y1 - 25, f'fill="{duvet_fill}" stroke="{stroke}" stroke-width="1.1" rx="3"'))
            out.append(svg_line_mm(x0 + 820, y0 + 25, x0 + 820, y1 - 25, f'stroke="{stroke}" stroke-width="1" opacity="0.6"'))
            pad = 120
            pw = (h_box - 3 * pad) / 2
            out.append(svg_rect_mm(x0 + 160, y0 + pad, x0 + 560, y0 + pad + pw, f'fill="{pillow_fill}" stroke="{stroke}" stroke-width="1.2" rx="6"'))
            out.append(svg_rect_mm(x0 + 160, y0 + 2 * pad + pw, x0 + 560, y1 - pad, f'fill="{pillow_fill}" stroke="{stroke}" stroke-width="1.2" rx="6"'))
        else:
            # Headboard on East
            out.append(svg_rect_mm(x1 - 110, y0, x1, y1, f'fill="{head_fill}" stroke="{stroke}" stroke-width="1.4"'))
            out.append(svg_rect_mm(x0 + 25, y0 + 25, x1 - 700, y1 - 25, f'fill="{duvet_fill}" stroke="{stroke}" stroke-width="1.1" rx="3"'))
            out.append(svg_line_mm(x1 - 820, y0 + 25, x1 - 820, y1 - 25, f'stroke="{stroke}" stroke-width="1" opacity="0.6"'))
            pad = 120
            pw = (h_box - 3 * pad) / 2
            out.append(svg_rect_mm(x1 - 560, y0 + pad, x1 - 160, y0 + pad + pw, f'fill="{pillow_fill}" stroke="{stroke}" stroke-width="1.2" rx="6"'))
            out.append(svg_rect_mm(x1 - 560, y0 + 2 * pad + pw, x1 - 160, y1 - pad, f'fill="{pillow_fill}" stroke="{stroke}" stroke-width="1.2" rx="6"'))
        out.append('</g>')

    elif kind == "wardrobe":
        w_fill = "#122136" if bp else "#7D5A3C"
        out.append(svg_rect_mm(x0, y0, x1, y1, f'fill="{w_fill}" stroke="{stroke}" stroke-width="1.5"'))
        if w_box > h_box:
            out.append(svg_line_mm(x0, cy, x1, cy, f'stroke="{stroke}" stroke-width="0.9" stroke-dasharray="5 4" opacity="0.7"'))
            for xi in range(int(x0 + 600), int(x1), 600):
                out.append(svg_line_mm(xi, y0, xi, y1, f'stroke="{stroke}" stroke-width="1.1"'))
        else:
            out.append(svg_line_mm(cx, y0, cx, y1, f'stroke="{stroke}" stroke-width="0.9" stroke-dasharray="5 4" opacity="0.7"'))
            for yi in range(int(y0 + 600), int(y1), 600):
                out.append(svg_line_mm(x0, yi, x1, yi, f'stroke="{stroke}" stroke-width="1.1"'))

    elif kind == "sofa_l":
        sf = "#162A44" if bp else "#C7B8A5"
        sb = "#1E3654" if bp else "#B09F8A"
        out.append(f'<g{shadow_attr}>')
        out.append(svg_rect_mm(x0, y0, x1, y1, f'fill="{sf}" stroke="{stroke}" stroke-width="1.5" rx="5"'))
        out.append(svg_rect_mm(x0, y0, x0 + 220, y1, f'fill="{sb}" stroke="{stroke}" stroke-width="1.2" rx="4"'))
        seg_h = h_box / 3
        for i in range(1, 3):
            out.append(svg_line_mm(x0 + 220, y0 + i * seg_h, x1, y0 + i * seg_h, f'stroke="{stroke}" stroke-width="1.1"'))
        # Throw cushions
        if not bp:
            for cy_p in (y0 + 380, y0 + h_box - 380):
                out.append(svg_rect_mm(x0 + 230, cy_p - 160, x0 + 420, cy_p + 160, 'fill="#8C6D51" stroke="#6E543D" stroke-width="0.9" rx="5"'))
        out.append('</g>')

    elif kind == "sofa_chaise":
        sf = "#162A44" if bp else "#C7B8A5"
        sb = "#1E3654" if bp else "#B09F8A"
        out.append(f'<g{shadow_attr}>')
        out.append(svg_rect_mm(x0, y0, x1, y1, f'fill="{sf}" stroke="{stroke}" stroke-width="1.5" rx="5"'))
        out.append(svg_rect_mm(x0, y0, x1, y0 + 210, f'fill="{sb}" stroke="{stroke}" stroke-width="1.2" rx="4"'))
        out.append('</g>')

    elif kind == "dining_table_6":
        tf = "#162A44" if bp else "#785337"
        cf = "#112035" if bp else "#B9AA98"
        out.append(f'<g{shadow_attr}>')
        for i in range(3):
            cy_c = y0 + 300 + i * 600
            out.append(svg_rect_mm(x0 - 360, cy_c - 200, x0 - 40, cy_c + 200, f'fill="{cf}" stroke="{stroke}" stroke-width="1.1" rx="4"'))
            out.append(svg_rect_mm(x1 + 40, cy_c - 200, x1 + 360, cy_c + 200, f'fill="{cf}" stroke="{stroke}" stroke-width="1.1" rx="4"'))
        out.append(svg_rect_mm(x0, y0, x1, y1, f'fill="{tf}" stroke="{stroke}" stroke-width="1.6" rx="5"'))
        out.append('</g>')

    elif kind == "shower":
        sh_fill = "#0D2036" if bp else "#D8D2C6"
        out.append(svg_rect_mm(x0, y0, x1, y1, f'fill="{sh_fill}" stroke="{san_stroke}" stroke-width="1.5"'))
        out.append(svg_line_mm(x0, y0, x1, y1, f'stroke="{san_stroke}" stroke-width="0.9" opacity="0.55"'))
        out.append(svg_line_mm(x0, y1, x1, y0, f'stroke="{san_stroke}" stroke-width="0.9" opacity="0.55"'))
        out.append(f'<circle cx="{sx(cx):.2f}" cy="{sy(cy):.2f}" r="{sw(55):.2f}" fill="none" stroke="{san_stroke}" stroke-width="1.4"/>')
        # Glass partition accent
        glass_y = y0 if f["room"] == "RM-02" else y1
        out.append(svg_line_mm(x0, glass_y, x1, glass_y, 'stroke="#38BDF8" stroke-width="3.2" opacity="0.85"'))

    elif kind == "vanity":
        vf = "#12263D" if bp else "#ECE7DF"
        bf = "#0B192C" if bp else "#FFFFFF"
        out.append(svg_rect_mm(x0, y0, x1, y1, f'fill="{vf}" stroke="{san_stroke}" stroke-width="1.4"'))
        out.append(f'<ellipse cx="{sx(cx):.2f}" cy="{sy(cy):.2f}" rx="{sw(w_box * 0.34):.2f}" ry="{sw(h_box * 0.34):.2f}" fill="{bf}" stroke="{san_stroke}" stroke-width="1.3"/>')

    elif kind == "wc":
        wf = "#12263D" if bp else "#FFFFFF"
        out.append(svg_rect_mm(x0, y0, x1, y1, f'fill="none" stroke="{san_stroke}" stroke-width="0.6" opacity="0.25"'))
        if f["rotation_deg"] == 270:
            out.append(svg_rect_mm(x1 - 170, y0 + 15, x1, y1 - 15, f'fill="{wf}" stroke="{san_stroke}" stroke-width="1.4" rx="2"'))
            out.append(f'<ellipse cx="{sx(x0 + (w_box - 170) * 0.52):.2f}" cy="{sy(cy):.2f}" rx="{sw((w_box - 170) * 0.48):.2f}" ry="{sw(h_box * 0.42):.2f}" fill="{wf}" stroke="{san_stroke}" stroke-width="1.4"/>')
        else:
            out.append(svg_rect_mm(x0, y0 + 15, x0 + 170, y1 - 15, f'fill="{wf}" stroke="{san_stroke}" stroke-width="1.4" rx="2"'))
            out.append(f'<ellipse cx="{sx(x1 - (w_box - 170) * 0.52):.2f}" cy="{sy(cy):.2f}" rx="{sw((w_box - 170) * 0.48):.2f}" ry="{sw(h_box * 0.42):.2f}" fill="{wf}" stroke="{san_stroke}" stroke-width="1.4"/>')

    elif kind == "kitchen_counter":
        kf = "#14273E" if bp else "#44484F"
        out.append(svg_rect_mm(x0, y0, x1, y1, f'fill="{kf}" stroke="{stroke}" stroke-width="1.5"'))

    elif kind == "fridge":
        ff = "#1A324E" if bp else "#684B34"
        out.append(svg_rect_mm(x0, y0, x1, y1, f'fill="{ff}" stroke="{stroke}" stroke-width="1.6"'))
        out.append(f'<text x="{sx(cx):.2f}" y="{sy(cy) + 4:.2f}" text-anchor="middle" fill="{"#94B8D7" if bp else "#E5DDD3"}" font-family="Inter, Helvetica, Arial" font-size="11" font-weight="700">REF</text>')

    elif kind == "cooktop":
        out.append(svg_rect_mm(x0, y0, x1, y1, f'fill="{"#0B1626" if bp else "#1E2229"}" stroke="{stroke}" stroke-width="1.3" rx="3"'))
        for bx in (x0 + w_box * 0.30, x0 + w_box * 0.70):
            for by in (y0 + h_box * 0.28, y0 + h_box * 0.72):
                out.append(f'<circle cx="{sx(bx):.2f}" cy="{sy(by):.2f}" r="{sw(75):.2f}" fill="none" stroke="{"#38BDF8" if bp else "#94A3B8"}" stroke-width="1.3"/>')

    elif kind == "kitchen_sink":
        out.append(svg_rect_mm(x0, y0, x1, y1, f'fill="{"#0E1E33" if bp else "#CBD5E1"}" stroke="{san_stroke}" stroke-width="1.4" rx="3"'))
        out.append(svg_rect_mm(x0 + 40, y0 + 45, cx - 20, y1 - 45, f'fill="{"#0B1626" if bp else "#94A3B8"}" stroke="{san_stroke}" stroke-width="1.1" rx="2"'))
        out.append(svg_rect_mm(cx + 20, y0 + 45, x1 - 40, y1 - 45, f'fill="{"#0B1626" if bp else "#94A3B8"}" stroke="{san_stroke}" stroke-width="1.1" rx="2"'))

    elif kind == "washer_dryer":
        out.append(svg_rect_mm(x0, y0, x1, y1, f'fill="{"#12253B" if bp else "#646B73"}" stroke="{san_stroke}" stroke-width="1.5" rx="3"'))
        out.append(f'<text x="{sx(cx):.2f}" y="{sy(cy) + 4:.2f}" text-anchor="middle" fill="{"#7DD3FC" if bp else "#F1F5F9"}" font-family="Inter, Helvetica, Arial" font-size="11" font-weight="700">W/D</text>')

    elif kind == "utility_sink":
        out.append(svg_rect_mm(x0, y0, x1, y1, f'fill="{"#12253B" if bp else "#D1D5DB"}" stroke="{san_stroke}" stroke-width="1.4"'))
        out.append(svg_rect_mm(x0 + 80, y0 + 80, x1 - 80, y1 - 80, f'fill="{"#0B1626" if bp else "#9CA3AF"}" stroke="{san_stroke}" stroke-width="1.1" rx="3"'))

    elif kind == "desk":
        df = "#162A44" if bp else "#A7825A"
        out.append(f'<g{shadow_attr}>')
        out.append(svg_rect_mm(x0, y0, x1, y1, f'fill="{df}" stroke="{stroke}" stroke-width="1.3" rx="3"'))
        out.append(f'<circle cx="{sx(cx):.2f}" cy="{sy(y1 + 260):.2f}" r="{sw(200):.2f}" fill="{"#112035" if bp else "#6D655E"}" stroke="{stroke}" stroke-width="1.1"/>')
        out.append('</g>')

    elif kind == "car":
        body_fill = "#13263E" if bp else "#CBD5E1"
        glass_fill = "#0D1C30" if bp else "#334155"
        roof_fill = "#18304D" if bp else "#E2E8F0"
        out.append(f'<g{shadow_attr}>')
        # Main luxury sedan body
        out.append(svg_rect_mm(x0 + 40, y0 + 60, x1 - 40, y1 - 60, f'fill="{body_fill}" stroke="{stroke}" stroke-width="1.8" rx="34"'))
        # Side mirrors
        out.append(svg_rect_mm(x0 - 50, y0 + 2650, x0 + 50, y0 + 2860, f'fill="{body_fill}" stroke="{stroke}" stroke-width="1.2" rx="4"'))
        out.append(svg_rect_mm(x1 - 50, y0 + 2650, x1 + 50, y0 + 2860, f'fill="{body_fill}" stroke="{stroke}" stroke-width="1.2" rx="4"'))
        # Windshield & rear glass
        out.append(svg_rect_mm(x0 + 210, y0 + 880, x1 - 210, y1 - 920, f'fill="{glass_fill}" stroke="{stroke}" stroke-width="1.2" rx="16"'))
        # Roof panel
        out.append(svg_rect_mm(x0 + 270, y0 + 1320, x1 - 270, y1 - 1480, f'fill="{roof_fill}" stroke="{stroke}" stroke-width="1.2" rx="12"'))
        # Headlights
        out.append(svg_rect_mm(x0 + 220, y1 - 180, x0 + 540, y1 - 80, f'fill="{"#38BDF8" if bp else "#FEF08A"}" opacity="0.85" rx="3"'))
        out.append(svg_rect_mm(x1 - 540, y1 - 180, x1 - 220, y1 - 80, f'fill="{"#38BDF8" if bp else "#FEF08A"}" opacity="0.85" rx="3"'))
        out.append('</g>')

    elif kind == "plant_pot":
        r = min(w_box, h_box) / 2
        if bp:
            out.append(f'<circle cx="{sx(cx):.2f}" cy="{sy(cy):.2f}" r="{sw(r):.2f}" fill="#112922" stroke="#4ADE80" stroke-width="1.3"/>')
            out.append(f'<circle cx="{sx(cx):.2f}" cy="{sy(cy):.2f}" r="{sw(r * 0.45):.2f}" fill="none" stroke="#4ADE80" stroke-width="1"/>')
        else:
            out.append(f'<g{shadow_attr}>')
            out.append(f'<circle cx="{sx(cx):.2f}" cy="{sy(cy):.2f}" r="{sw(r):.2f}" fill="#3D7043" stroke="#294D2E" stroke-width="1.1"/>')
            for deg in range(0, 360, 60):
                rad = math.radians(deg)
                lx = cx + r * 0.42 * math.cos(rad)
                ly = cy + r * 0.42 * math.sin(rad)
                out.append(f'<circle cx="{sx(lx):.2f}" cy="{sy(ly):.2f}" r="{sw(r * 0.42):.2f}" fill="#538B57" opacity="0.85"/>')
            out.append('</g>')

    elif kind in ("outdoor_lounge", "armchair"):
        lf = "#14273E" if bp else "#D6CBB9"
        frame = "#1E3654" if bp else "#8A623F"
        out.append(f'<g{shadow_attr}>')
        out.append(svg_rect_mm(x0, y0, x1, y1, f'fill="{frame}" stroke="{stroke}" stroke-width="1.3" rx="4"'))
        out.append(svg_rect_mm(x0 + 70, y0 + 70, x1 - 70, y1 - 70, f'fill="{lf}" stroke="{stroke}" stroke-width="1.1" rx="3"'))
        out.append('</g>')

    elif kind == "coffee_table":
        cf = "#14273E" if bp else "#DDD5C7"
        out.append(f'<g{shadow_attr}>')
        out.append(svg_rect_mm(x0, y0, x1, y1, f'fill="{cf}" stroke="{stroke}" stroke-width="1.4" rx="10"'))
        out.append('</g>')

    else:
        # Nightstands, TV consoles, benches, utility racks
        ff = "#14273E" if bp else "#7D5A3C"
        out.append(f'<g{shadow_attr}>')
        out.append(svg_rect_mm(x0, y0, x1, y1, f'fill="{ff}" stroke="{stroke}" stroke-width="1.3" rx="2"'))
        out.append('</g>')

    return "\n".join(out)


def render_tree(item, mode="blueprint"):
    cx, cy = item["center"]
    r = item["radius_mm"]
    if mode == "blueprint":
        out = [
            f'<circle cx="{sx(cx):.2f}" cy="{sy(cy):.2f}" r="{sw(r):.2f}" fill="#0E2528" fill-opacity="0.55" stroke="#4ADE80" stroke-width="1.5"/>',
            f'<circle cx="{sx(cx):.2f}" cy="{sy(cy):.2f}" r="{sw(r * 0.60):.2f}" fill="none" stroke="#4ADE80" stroke-width="1" stroke-dasharray="4 4"/>',
            f'<circle cx="{sx(cx):.2f}" cy="{sy(cy):.2f}" r="{sw(r * 0.12):.2f}" fill="#4ADE80"/>',
        ]
        for deg in range(0, 360, 45):
            rad = math.radians(deg)
            out.append(svg_line_mm(cx + r * 0.18 * math.cos(rad), cy + r * 0.18 * math.sin(rad),
                                   cx + r * 0.90 * math.cos(rad), cy + r * 0.90 * math.sin(rad),
                                   'stroke="#4ADE80" stroke-width="0.9" opacity="0.6"'))
        return "\n".join(out)
    else:
        # Realistic layered architectural tree canopy with soft shadow
        out = [f'<g filter="url(#treeShadow)">']
        base_col = "#3C6E42" if item["kind"] == "tree" else "#4C7F4D"
        hi_col = "#629A5D" if item["kind"] == "tree" else "#74AC6A"
        out.append(f'<circle cx="{sx(cx):.2f}" cy="{sy(cy):.2f}" r="{sw(r):.2f}" fill="{base_col}" stroke="#2A4F2E" stroke-width="1.2"/>')
        for i in range(6):
            ang = math.radians(i * 60 + 18)
            lx = cx + r * 0.42 * math.cos(ang)
            ly = cy + r * 0.42 * math.sin(ang)
            out.append(f'<circle cx="{sx(lx):.2f}" cy="{sy(ly):.2f}" r="{sw(r * 0.48):.2f}" fill="{hi_col}" opacity="0.72"/>')
        out.append(f'<circle cx="{sx(cx - r * 0.16):.2f}" cy="{sy(cy + r * 0.16):.2f}" r="{sw(r * 0.40):.2f}" fill="#85BC78" opacity="0.55"/>')
        out.append(f'<circle cx="{sx(cx):.2f}" cy="{sy(cy):.2f}" r="{sw(r * 0.08):.2f}" fill="#3D2B1F"/>')
        out.append('</g>')
        return "\n".join(out)


def render_table(x, y, col_widths, title, headers, rows, mode="blueprint"):
    bp = (mode == "blueprint")
    total_w = sum(col_widths)
    row_h = 33
    hdr_h = 38
    title_h = 40
    total_h = title_h + hdr_h + len(rows) * row_h

    bg = "#0E1A2C" if bp else "#FAF8F4"
    title_bg = "#132640" if bp else "#242B35"
    hdr_bg = "#102036" if bp else "#ECE7DF"
    border = "#284669" if bp else "#D5CEC3"
    title_fg = "#38BDF8" if bp else "#F8FAFC"
    hdr_fg = "#94B8D7" if bp else "#334155"
    cell_fg = "#E2E8F0" if bp else "#1E293B"
    stripe = "#0B1626" if bp else "#F3EFE8"

    out = [f'<g transform="translate({x},{y})">']
    out.append(f'<rect x="0" y="0" width="{total_w}" height="{total_h}" fill="{bg}" stroke="{border}" stroke-width="1.5" rx="4"/>')
    out.append(f'<rect x="0" y="0" width="{total_w}" height="{title_h}" fill="{title_bg}" rx="4"/>')
    out.append(f'<text x="16" y="26" fill="{title_fg}" font-family="Inter, Helvetica Neue, Arial" font-size="16" font-weight="700" letter-spacing="1.2">{escape(title)}</text>')
    out.append(f'<rect x="0" y="{title_h}" width="{total_w}" height="{hdr_h}" fill="{hdr_bg}"/>')

    cx = 0
    for cw, h in zip(col_widths, headers):
        out.append(f'<text x="{cx + 12}" y="{title_h + 25}" fill="{hdr_fg}" font-family="SF Mono, Menlo, monospace" font-size="13" font-weight="700">{escape(h)}</text>')
        cx += cw

    for r_idx, row in enumerate(rows):
        ry = title_h + hdr_h + r_idx * row_h
        if r_idx % 2 == 1:
            out.append(f'<rect x="1" y="{ry}" width="{total_w - 2}" height="{row_h}" fill="{stripe}"/>')
        out.append(f'<line x1="0" y1="{ry}" x2="{total_w}" y2="{ry}" stroke="{border}" stroke-width="0.7" opacity="0.6"/>')
        cx = 0
        for cw, val in zip(col_widths, row):
            out.append(f'<text x="{cx + 12}" y="{ry + 22}" fill="{cell_fg}" font-family="Inter, Helvetica Neue, Arial" font-size="14">{escape(str(val))}</text>')
            cx += cw

    out.append('</g>')
    return "\n".join(out), total_h


def build_sheet(mode="blueprint"):
    bp = (mode == "blueprint")
    p = []

    # SVG Header & Defs
    bg_color = "#0A1220" if bp else "#F4F1EA"
    frame_stroke = "#38BDF8" if bp else "#2B313B"
    inner_frame = "#1E3A5F" if bp else "#C9C1B4"

    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" height="{CANVAS_H}" viewBox="0 0 {CANVAS_W} {CANVAS_H}">')
    p.append('<defs>')
    # Blueprint technical grid
    if bp:
        p.append('''
        <pattern id="bpGrid" width="74" height="74" patternUnits="userSpaceOnUse">
          <path d="M 74 0 L 0 0 0 74" fill="none" stroke="#162842" stroke-width="0.9"/>
        </pattern>
        <pattern id="wallHatchExt" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="8" height="8" fill="#1E293B"/>
          <line x1="0" y1="0" x2="0" y2="8" stroke="#64748B" stroke-width="2.2"/>
        </pattern>
        <pattern id="wallHatchInt" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
          <rect width="8" height="8" fill="#172233"/>
          <line x1="0" y1="0" x2="0" y2="8" stroke="#475569" stroke-width="1.6"/>
        </pattern>
        ''')
    else:
        p.append('''
        <filter id="softShadow" x="-15%" y="-15%" width="140%" height="140%">
          <feDropShadow dx="4" dy="5" stdDeviation="4" flood-color="#1E1914" flood-opacity="0.20"/>
        </filter>
        <filter id="wallShadow" x="-10%" y="-10%" width="130%" height="130%">
          <feDropShadow dx="7" dy="8" stdDeviation="6" flood-color="#1C1917" flood-opacity="0.28"/>
        </filter>
        <filter id="treeShadow" x="-25%" y="-25%" width="160%" height="160%">
          <feDropShadow dx="8" dy="10" stdDeviation="7" flood-color="#1A261B" flood-opacity="0.30"/>
        </filter>
        <pattern id="oakFloor" width="26" height="90" patternUnits="userSpaceOnUse">
          <rect width="26" height="90" fill="#CEB38E"/>
          <rect x="0" y="0" width="13" height="90" fill="#C7AA82"/>
          <line x1="0" y1="0" x2="0" y2="90" stroke="#B6966E" stroke-width="0.8"/>
          <line x1="13" y1="0" x2="13" y2="90" stroke="#B6966E" stroke-width="0.8"/>
          <line x1="0" y1="45" x2="13" y2="45" stroke="#B6966E" stroke-width="0.6"/>
        </pattern>
        <pattern id="limestoneTile" width="88" height="88" patternUnits="userSpaceOnUse">
          <rect width="88" height="88" fill="#E3DDD2"/>
          <path d="M 88 0 L 0 0 0 88" fill="none" stroke="#CEC6B8" stroke-width="1"/>
        </pattern>
        <pattern id="travertineTile" width="52" height="52" patternUnits="userSpaceOnUse">
          <rect width="52" height="52" fill="#D5CEC1"/>
          <path d="M 52 0 L 0 0 0 52" fill="none" stroke="#BFB7A8" stroke-width="0.9"/>
        </pattern>
        <pattern id="porcelainTile" width="44" height="44" patternUnits="userSpaceOnUse">
          <rect width="44" height="44" fill="#C4C7C4"/>
          <path d="M 44 0 L 0 0 0 44" fill="none" stroke="#ADB1AE" stroke-width="0.9"/>
        </pattern>
        <pattern id="basaltPaver" width="46" height="46" patternUnits="userSpaceOnUse">
          <rect width="46" height="46" fill="#636972"/>
          <path d="M 46 0 L 0 0 0 46" fill="none" stroke="#50565E" stroke-width="1.2"/>
        </pattern>
        <pattern id="teakDeck" width="22" height="60" patternUnits="userSpaceOnUse">
          <rect width="22" height="60" fill="#B18356"/>
          <rect x="0" y="0" width="11" height="60" fill="#A6784C"/>
          <line x1="0" y1="0" x2="0" y2="60" stroke="#7E5936" stroke-width="1"/>
          <line x1="11" y1="0" x2="11" y2="60" stroke="#7E5936" stroke-width="1"/>
        </pattern>
        <pattern id="lawnTex" width="32" height="32" patternUnits="userSpaceOnUse">
          <rect width="32" height="32" fill="#769A61"/>
          <circle cx="8" cy="10" r="1.4" fill="#688C54" opacity="0.6"/>
          <circle cx="22" cy="24" r="1.6" fill="#84A86E" opacity="0.5"/>
          <circle cx="26" cy="8" r="1.1" fill="#61824E" opacity="0.5"/>
        </pattern>
        ''')
    p.append('</defs>')

    # Sheet Background & Architectural Border
    p.append(f'<rect x="0" y="0" width="{CANVAS_W}" height="{CANVAS_H}" fill="{bg_color}"/>')
    if bp:
        p.append(f'<rect x="44" y="44" width="{CANVAS_W - 88}" height="{CANVAS_H - 88}" fill="url(#bpGrid)"/>')
    p.append(f'<rect x="36" y="36" width="{CANVAS_W - 72}" height="{CANVAS_H - 72}" fill="none" stroke="{frame_stroke}" stroke-width="3"/>')
    p.append(f'<rect x="48" y="48" width="{CANVAS_W - 96}" height="{CANVAS_H - 96}" fill="none" stroke="{inner_frame}" stroke-width="1.2"/>')

    # Sheet Header Banner (top-left above plan)
    hdr_title_col = "#F8FAFC" if bp else "#1E242B"
    hdr_sub_col = "#38BDF8" if bp else "#786C5E"
    p.append(f'<text x="95" y="102" fill="{hdr_title_col}" font-family="Inter, Helvetica Neue, Arial" font-size="28" font-weight="800" letter-spacing="2">VILLA AURELIA 123 — GROUND FLOOR ARCHITECTURAL PLAN</text>')
    sub = "AUTOCAD TECHNICAL BLUEPRINT  •  SCALE 1:50  •  ALL DIMENSIONS IN MILLIMETERS" if bp else "ARCHITECTURAL PRESENTATION PLAN  •  REALISTIC FINISHES & LANDSCAPING  •  SCALE 1:50"
    p.append(f'<text x="95" y="134" fill="{hdr_sub_col}" font-family="SF Mono, Menlo, monospace" font-size="15" font-weight="600" letter-spacing="1.4">{sub}</text>')

    # -----------------------------------------------------------------------
    # FLOOR FILLS & OUTDOOR SURFACES
    # -----------------------------------------------------------------------
    if bp:
        # Subtle site & building footprint fill
        p.append(svg_rect_mm(0, 0, SITE_W, SITE_D, 'fill="#0C1729" stroke="#FACC15" stroke-width="2.2" stroke-dasharray="14 6 3 6"'))
        # Carport pergola overhead dashed projection
        for ys in range(600, 4800, 550):
            p.append(svg_line_mm(120, ys, 2924, ys, 'stroke="#334E6E" stroke-width="1" stroke-dasharray="8 6"'))
        # Rear terrace timber plank lines
        p.append(svg_rect_mm(5490, 11700, SITE_W, SITE_D, 'fill="#0F1F35" stroke="#476682" stroke-width="1.2"'))
        for xp in range(5670, SITE_W, 180):
            p.append(svg_line_mm(xp, 11700, xp, SITE_D, 'stroke="#233B57" stroke-width="0.8"'))
        # Building interior subtle floor tint
        p.append(svg_poly_mm(spec["building_footprint_polygon"], 'fill="#0E1C31" stroke="none"'))
        # Subtle wet-area grid in bathrooms
        for rm_id in ("RM-02", "RM-05"):
            rm = next(r for r in spec["rooms"] if r["id"] == rm_id)
            xs = [pt[0] for pt in rm["polygon"]]
            ys = [pt[1] for pt in rm["polygon"]]
            for gx in range(min(xs) + 300, max(xs), 300):
                p.append(svg_line_mm(gx, min(ys), gx, max(ys), 'stroke="#1B324E" stroke-width="0.7"'))
            for gy in range(min(ys) + 300, max(ys), 300):
                p.append(svg_line_mm(min(xs), gy, max(xs), gy, 'stroke="#1B324E" stroke-width="0.7"'))
    else:
        # Presentation realistic ground & floor materials
        p.append(svg_rect_mm(0, 0, 3044, 5000, 'fill="url(#basaltPaver)"'))
        p.append(svg_rect_mm(3044, 0, SITE_W, 1900, 'fill="url(#lawnTex)"'))
        p.append(svg_rect_mm(0, 11700, 5490, SITE_D, 'fill="url(#lawnTex)"'))
        # Rear garden pebble border strip along north boundary
        p.append(svg_rect_mm(0, 13050, 5490, SITE_D, 'fill="#CFC8BC" opacity="0.65"'))
        p.append(svg_rect_mm(5490, 11700, SITE_W, SITE_D, 'fill="url(#teakDeck)"'))
        # Subtle roof overhang shadow on terrace & front entry
        p.append(svg_rect_mm(5490, 11700, SITE_W, 12350, 'fill="#1E1914" opacity="0.10"'))
        p.append(svg_rect_mm(3044, 1500, SITE_W, 1900, 'fill="#1E1914" opacity="0.09"'))

        mat_to_pat = {
            "engineered_white_oak": "url(#oakFloor)",
            "large_format_limestone": "url(#limestoneTile)",
            "honed_travertine_tile": "url(#travertineTile)",
            "matte_porcelain_grey": "url(#porcelainTile)",
        }
        for rm in spec["rooms"]:
            fill_pat = mat_to_pat.get(rm["floor_material"], "#E3DDD2")
            if "sub_rects" in rm:
                for sr in rm["sub_rects"]:
                    p.append(svg_rect_mm(*sr, f'fill="{fill_pat}"'))
            else:
                p.append(svg_poly_mm(rm["polygon"], f'fill="{fill_pat}"'))

        # Crisp property line border
        p.append(svg_rect_mm(0, 0, SITE_W, SITE_D, 'fill="none" stroke="#8C6D46" stroke-width="2.2" stroke-dasharray="14 6 3 6"'))

    # Stepping stones (under landscaping & furniture)
    for item in spec["landscaping"]:
        if item["kind"] == "stepping_stone":
            if bp:
                p.append(svg_rect_mm(*item["rect"], 'fill="#15263D" stroke="#94B8D7" stroke-width="1.3"'))
            else:
                p.append(svg_rect_mm(*item["rect"], 'fill="#E5E0D7" stroke="#BDB6A9" stroke-width="1.3" rx="3" filter="url(#softShadow)"'))

    # -----------------------------------------------------------------------
    # FURNITURE & SANITARY FIXTURES
    # -----------------------------------------------------------------------
    # Render rugs first so sofas sit above them
    for f in spec["furniture"]:
        if f["kind"] == "rug":
            p.append(render_furniture_item(f, mode))
    for f in spec["furniture"]:
        if f["kind"] != "rug":
            p.append(render_furniture_item(f, mode))

    # -----------------------------------------------------------------------
    # WALLS (Exterior 200 mm & Interior 120 mm) WITH OPENING CUTOUTS
    # -----------------------------------------------------------------------
    p.append('<g>' if bp else '<g filter="url(#wallShadow)">')
    for w in spec["walls"]:
        segs = subtract_openings(w["rect"], openings_by_wall.get(w["id"], []), w["orientation"])
        if bp:
            w_fill = "url(#wallHatchExt)" if w["category"] == "exterior" else "url(#wallHatchInt)"
            w_stroke = "#F8FAFC" if w["category"] == "exterior" else "#CBD5E1"
            w_sw = "2.6" if w["category"] == "exterior" else "1.8"
        else:
            w_fill = "#242A33" if w["category"] == "exterior" else "#3F4752"
            w_stroke = "#14181E" if w["category"] == "exterior" else "#2A3038"
            w_sw = "1.8" if w["category"] == "exterior" else "1.2"
        for seg in segs:
            p.append(svg_rect_mm(*seg, f'fill="{w_fill}" stroke="{w_stroke}" stroke-width="{w_sw}"'))
    p.append('</g>')

    # -----------------------------------------------------------------------
    # DOORS & SWING ARCS
    # -----------------------------------------------------------------------
    for d in spec["doors"]:
        ox0, oy0, ox1, oy1 = d["opening"]
        door_col = "#F59E0B" if bp else "#6E4B32"
        arc_col = "#6495B8" if bp else "#8C7D6B"

        # Threshold line
        if (ox1 - ox0) > (oy1 - oy0):
            p.append(svg_line_mm(ox0, oy0, ox0, oy1, f'stroke="{door_col}" stroke-width="2"'))
            p.append(svg_line_mm(ox1, oy0, ox1, oy1, f'stroke="{door_col}" stroke-width="2"'))
        else:
            p.append(svg_line_mm(ox0, oy0, ox1, oy0, f'stroke="{door_col}" stroke-width="2"'))
            p.append(svg_line_mm(ox0, oy1, ox1, oy1, f'stroke="{door_col}" stroke-width="2"'))

        if d["swing_arc"]:
            hx, hy = d["hinge"]
            ex, ey = d["leaf_open_end"]
            dx, dy = ex - hx, ey - hy
            L = math.hypot(dx, dy)
            nx, ny = -dy / L * 45, dx / L * 45
            p.append(svg_poly_mm([[hx, hy], [ex, ey], [ex + nx, ey + ny], [hx + nx, hy + ny]],
                                 f'fill="{door_col}" stroke="{door_col}" stroke-width="1"'))
            arc = d["swing_arc"]
            p.append(svg_arc_mm(arc["center"][0], arc["center"][1], arc["radius"],
                                arc["start_deg"], arc["end_deg"],
                                f'fill="none" stroke="{arc_col}" stroke-width="1.3" stroke-dasharray="6 4"'))
        elif d.get("sliding_panels"):
            n = d["sliding_panels"]
            pw = (ox1 - ox0) / n
            ym = (oy0 + oy1) / 2
            p.append(svg_rect_mm(ox0, oy0, ox1, oy1, f'fill="{"#0D2238" if bp else "#CBD5E1"}" fill-opacity="0.45" stroke="#38BDF8" stroke-width="1.3"'))
            for i in range(n):
                px0 = ox0 + i * pw
                px1 = px0 + pw
                y_off = ym - 28 if i % 2 == 0 else ym + 28
                p.append(svg_rect_mm(px0, y_off - 16, px1, y_off + 16, 'fill="#38BDF8" stroke="#0284C7" stroke-width="1"'))
        elif d.get("sliding_track"):
            p1, p2 = d["sliding_track"]
            p.append(svg_line_mm(p1[0], p1[1], p2[0], p2[1], f'stroke="{arc_col}" stroke-width="1.2" stroke-dasharray="5 3"'))
            p.append(svg_rect_mm(p1[0] - 22, p1[1], p1[0] + 22, p1[1] + (p2[1] - p1[1]) * 0.65, f'fill="{door_col}"'))

        # Door tag callout (blueprint mode prominently, subtle in presentation)
        if bp:
            tx, ty = (ox0 + ox1) / 2, (oy0 + oy1) / 2
            if d["id"] == "D1":
                ty -= 280
            elif d["id"] == "D8":
                ty += 280
            elif d["id"] in ("D2", "D3", "D5", "D7"):
                tx += 270
            elif d["id"] in ("D4", "D6"):
                tx -= 270
            p.append(f'<circle cx="{sx(tx):.2f}" cy="{sy(ty):.2f}" r="16" fill="#0B1626" stroke="#F59E0B" stroke-width="1.5"/>')
            p.append(f'<text x="{sx(tx):.2f}" y="{sy(ty) + 4.5:.2f}" text-anchor="middle" fill="#FCD34D" font-family="SF Mono, Menlo, monospace" font-size="12" font-weight="700">{d["id"]}</text>')

    # -----------------------------------------------------------------------
    # WINDOWS
    # -----------------------------------------------------------------------
    for win in spec["windows"]:
        ox0, oy0, ox1, oy1 = win["opening"]
        g_fill = "#0D2D4A" if bp else "#B8DDF2"
        g_stroke = "#38BDF8" if bp else "#1E293B"
        p.append(svg_rect_mm(ox0, oy0, ox1, oy1, f'fill="{g_fill}" stroke="{g_stroke}" stroke-width="1.6"'))
        if (ox1 - ox0) > (oy1 - oy0):
            ym = (oy0 + oy1) / 2
            p.append(svg_line_mm(ox0, ym - 24, ox1, ym - 24, f'stroke="{g_stroke}" stroke-width="1.2"'))
            p.append(svg_line_mm(ox0, ym + 24, ox1, ym + 24, f'stroke="{g_stroke}" stroke-width="1.2"'))
            if win["width_mm"] >= 1400:
                xm = (ox0 + ox1) / 2
                p.append(svg_line_mm(xm, oy0, xm, oy1, f'stroke="{g_stroke}" stroke-width="2"'))
        else:
            xm = (ox0 + ox1) / 2
            p.append(svg_line_mm(xm - 24, oy0, xm - 24, oy1, f'stroke="{g_stroke}" stroke-width="1.2"'))
            p.append(svg_line_mm(xm + 24, oy0, xm + 24, oy1, f'stroke="{g_stroke}" stroke-width="1.2"'))

        if bp:
            tx, ty = (ox0 + ox1) / 2, (oy0 + oy1) / 2
            if win["host_wall"] in ("EW-S1", "EW-S2"):
                ty = oy0 - 270
            elif win["host_wall"] == "EW-W2":
                tx = ox0 - 290
            elif win["host_wall"] == "EW-N1":
                ty = oy1 + 270
            p.append(f'<rect x="{sx(tx) - 18:.2f}" y="{sy(ty) - 12:.2f}" width="36" height="24" rx="3" fill="#0B1626" stroke="#38BDF8" stroke-width="1.5"/>')
            p.append(f'<text x="{sx(tx):.2f}" y="{sy(ty) + 4.5:.2f}" text-anchor="middle" fill="#7DD3FC" font-family="SF Mono, Menlo, monospace" font-size="12" font-weight="700">{win["id"]}</text>')

    # -----------------------------------------------------------------------
    # BOTANICAL TREES & SHRUBS (On top of ground/walls edge)
    # -----------------------------------------------------------------------
    for item in spec["landscaping"]:
        if item["kind"] != "stepping_stone":
            p.append(render_tree(item, mode))

    # -----------------------------------------------------------------------
    # ROOM LABELS & CALCULATED FLOOR AREAS
    # -----------------------------------------------------------------------
    for r in spec["rooms"]:
        lx, ly = r["label_pos"]
        lines = r["short_name"].split("\n")
        box_w = 136 if r["id"] not in ("RM-02", "RM-05", "RM-06") else 108
        box_h = 46 if len(lines) == 1 else 60
        pill_bg = "#0A1424" if bp else "#FFFFFF"
        pill_op = "0.86" if bp else "0.86"
        pill_bd = "#25466B" if bp else "#D5CEC3"
        nm_col = "#F8FAFC" if bp else "#1E242B"
        ar_col = "#22D3EE" if bp else "#785D42"

        px, py = sx(lx), sy(ly)
        p.append(f'<rect x="{px - box_w / 2:.2f}" y="{py - box_h / 2:.2f}" width="{box_w}" height="{box_h}" rx="4" fill="{pill_bg}" fill-opacity="{pill_op}" stroke="{pill_bd}" stroke-width="1"/>')
        if len(lines) == 1:
            p.append(f'<text x="{px:.2f}" y="{py - 4:.2f}" text-anchor="middle" fill="{nm_col}" font-family="Inter, Helvetica Neue, Arial" font-size="13" font-weight="800" letter-spacing="0.6">{escape(lines[0])}</text>')
            p.append(f'<text x="{px:.2f}" y="{py + 14:.2f}" text-anchor="middle" fill="{ar_col}" font-family="SF Mono, Menlo, monospace" font-size="12.5" font-weight="700">{r["area_m2"]:.2f} m²</text>')
        else:
            p.append(f'<text x="{px:.2f}" y="{py - 12:.2f}" text-anchor="middle" fill="{nm_col}" font-family="Inter, Helvetica Neue, Arial" font-size="12" font-weight="800" letter-spacing="0.5">{escape(lines[0])}</text>')
            p.append(f'<text x="{px:.2f}" y="{py + 3:.2f}" text-anchor="middle" fill="{nm_col}" font-family="Inter, Helvetica Neue, Arial" font-size="12" font-weight="800" letter-spacing="0.5">{escape(lines[1])}</text>')
            p.append(f'<text x="{px:.2f}" y="{py + 20:.2f}" text-anchor="middle" fill="{ar_col}" font-family="SF Mono, Menlo, monospace" font-size="12" font-weight="700">{r["area_m2"]:.2f} m²</text>')

    # Outdoor Zone Callout Pills
    ext_labels = [
        (1522, 2520, "CARPORT", f"{spec['outdoor_zones'][0]['area_m2']:.2f} m²"),
        (6100, 950, "FRONT GARDEN", f"{spec['outdoor_zones'][1]['area_m2']:.2f} m²"),
        (2745, 12450, "REAR GARDEN", f"{spec['outdoor_zones'][2]['area_m2']:.2f} m²"),
        (7280, 12000, "OUTDOOR TERRACE", f"{spec['outdoor_zones'][3]['area_m2']:.2f} m²"),
    ]
    for ox, oy, nm, ar in ext_labels:
        px, py = sx(ox), sy(oy)
        bw = 138
        p.append(f'<rect x="{px - bw / 2:.2f}" y="{py - 21:.2f}" width="{bw}" height="42" rx="4" fill="{"#0A1424" if bp else "#1E242B"}" fill-opacity="0.82" stroke="{"#38BDF8" if bp else "#D6CBB9"}" stroke-width="1"/>')
        p.append(f'<text x="{px:.2f}" y="{py - 3:.2f}" text-anchor="middle" fill="#F8FAFC" font-family="Inter, Helvetica Neue, Arial" font-size="12" font-weight="800" letter-spacing="0.6">{nm}</text>')
        p.append(f'<text x="{px:.2f}" y="{py + 13:.2f}" text-anchor="middle" fill="{"#4ADE80" if bp else "#E2C49A"}" font-family="SF Mono, Menlo, monospace" font-size="11.5" font-weight="700">{ar}</text>')

    # Street Frontage Label at bottom
    p.append(f'<text x="{sx(SITE_W / 2):.2f}" y="{sy(-1680):.2f}" text-anchor="middle" fill="{"#64748B" if bp else "#64748B"}" font-family="Inter, Helvetica Neue, Arial" font-size="15" font-weight="700" letter-spacing="5">STREET FRONTAGE  (SOUTH ACCESS)</text>')

    # -----------------------------------------------------------------------
    # EXTERNAL & INTERNAL DIMENSION LINES (MILLIMETERS)
    # -----------------------------------------------------------------------
    dc = "#22D3EE" if bp else "#475569"
    dt = "#67E8F9" if bp else "#1E293B"
    # South external dimensions
    p.append(dim_h(0, SITE_W, 0, -1120, color=dc, text_color=dt))
    p.append(dim_h(0, 3044, 0, -560, color=dc, text_color=dt))
    p.append(dim_h(3044, SITE_W, 0, -560, color=dc, text_color=dt))
    # North external dimensions
    p.append(dim_h(0, SITE_W, SITE_D, SITE_D + 1120, color=dc, text_color=dt))
    p.append(dim_h(0, 3860, SITE_D, SITE_D + 560, color=dc, text_color=dt))
    p.append(dim_h(3860, 5430, SITE_D, SITE_D + 560, color=dc, text_color=dt))
    p.append(dim_h(5430, SITE_W, SITE_D, SITE_D + 560, color=dc, text_color=dt))
    # West external dimensions
    p.append(dim_v(0, SITE_D, 0, -1180, color=dc, text_color=dt))
    p.append(dim_v(0, 5000, 0, -580, color=dc, text_color=dt))
    p.append(dim_v(5000, 8140, 0, -580, color=dc, text_color=dt))
    p.append(dim_v(8140, 11700, 0, -580, color=dc, text_color=dt))
    p.append(dim_v(11700, SITE_D, 0, -580, color=dc, text_color=dt))
    # East external dimensions
    p.append(dim_v(0, SITE_D, SITE_W, SITE_W + 1180, color=dc, text_color=dt))
    p.append(dim_v(0, 1900, SITE_W, SITE_W + 580, color=dc, text_color=dt))
    p.append(dim_v(1900, 5140, SITE_W, SITE_W + 580, color=dc, text_color=dt))
    p.append(dim_v(5140, 8200, SITE_W, SITE_W + 580, color=dc, text_color=dt))
    p.append(dim_v(8200, 11700, SITE_W, SITE_W + 580, color=dc, text_color=dt))
    p.append(dim_v(11700, SITE_D, SITE_W, SITE_W + 580, color=dc, text_color=dt))

    # Internal clear dimensions (full set on blueprint; concise key dims on presentation)
    if bp:
        p.append(dim_h(200, 3800, 11350, 11320, color="#06B6D4", text_color="#A5F3FC", font_size=14))
        p.append(dim_h(3920, 5370, 11350, 11320, color="#06B6D4", text_color="#A5F3FC", font_size=13))
        p.append(dim_h(5490, 8944, 11350, 11320, color="#06B6D4", text_color="#A5F3FC", font_size=14))
        p.append(dim_h(200, 3124, 5400, 5400, color="#06B6D4", text_color="#A5F3FC", font_size=14))
        p.append(dim_h(6084, 8944, 4880, 4880, color="#06B6D4", text_color="#A5F3FC", font_size=14))
        p.append(dim_h(3244, 4744, 6900, 6900, color="#06B6D4", text_color="#A5F3FC", font_size=13))
        p.append(dim_h(4864, 6944, 8040, 8040, color="#06B6D4", text_color="#A5F3FC", font_size=13))
        p.append(dim_h(6944, 8944, 8040, 8040, color="#06B6D4", text_color="#A5F3FC", font_size=13))

    # -----------------------------------------------------------------------
    # RIGHT-HAND ARCHITECTURAL SIDEBAR (X = 2070 .. 3745)
    # -----------------------------------------------------------------------
    SB_X = 2070
    SB_W = 1675
    cur_y = 95

    # 1. AREA & SITE SUMMARY BAR (3 KPI cards)
    a = spec["area_summary"]
    cards = [
        ("TOTAL LAND AREA", f"{a['total_land_area_m2']:.2f} m²", f"1,328.74 sq ft  •  9.144 × 13.50 m  •  Perim 45.29 m"),
        ("BUILDING FOOTPRINT", f"{a['building_footprint_m2']:.2f} m²", f"{a['building_footprint_pct']:.2f}% Coverage  •  Outdoor {a['total_outdoor_area_m2']:.2f} m² ({a['total_outdoor_area_pct']:.1f}%)"),
        ("USABLE INTERIOR AREA", f"{a['usable_interior_floor_area_m2']:.2f} m²", f"{a['usable_interior_floor_area_sqft']:.1f} sq ft  •  Walls {a['structural_wall_area_m2']:.2f} m²  •  Ceil 3,000 mm"),
    ]
    cw = (SB_W - 28) / 3
    for i, (k, v, sub_txt) in enumerate(cards):
        cx = SB_X + i * (cw + 14)
        c_bg = "#0E1C31" if bp else "#FFFFFF"
        c_bd = "#25466B" if bp else "#D5CEC3"
        p.append(f'<rect x="{cx:.1f}" y="{cur_y}" width="{cw:.1f}" height="104" rx="5" fill="{c_bg}" stroke="{c_bd}" stroke-width="1.5"/>')
        p.append(f'<text x="{cx + 18:.1f}" y="{cur_y + 28}" fill="{"#94B8D7" if bp else "#64748B"}" font-family="SF Mono, Menlo, monospace" font-size="13" font-weight="700" letter-spacing="1">{k}</text>')
        p.append(f'<text x="{cx + 18:.1f}" y="{cur_y + 66}" fill="{"#22D3EE" if bp else "#1E242B"}" font-family="Inter, Helvetica Neue, Arial" font-size="30" font-weight="800">{v}</text>')
        p.append(f'<text x="{cx + 18:.1f}" y="{cur_y + 90}" fill="{"#94A3B8" if bp else "#6B6359"}" font-family="Inter, Helvetica Neue, Arial" font-size="12">{escape(sub_txt)}</text>')
    cur_y += 126

    # 2. ROOM SCHEDULE TABLE
    room_rows = [
        [r["id"], r["name"], f"{r['width_mm']:,} × {r['depth_mm']:,}", f"{r['area_m2']:.2f} m²", f"{r['ceiling_height_mm']:,} mm", r["floor_material"].replace("_", " ").title()[:24]]
        for r in spec["rooms"]
    ]
    tbl_svg, tbl_h = render_table(
        SB_X, cur_y, [105, 360, 235, 145, 165, 665],
        "ROOM SCHEDULE — USABLE INTERIOR FLOOR AREA (69.43 m² / 747.31 sq ft)",
        ["ID", "SPACE", "CLEAR DIM (mm)", "AREA", "CEILING", "FLOOR FINISH"],
        room_rows, mode
    )
    p.append(tbl_svg)
    cur_y += tbl_h + 22

    # 3. DOOR SCHEDULE & WINDOW SCHEDULE SIDE-BY-SIDE OR STACKED
    door_rows = [
        [d["id"], f"{d['width_mm']:,} × {d['height_mm']:,}", d["type"], d["swing_direction"]]
        for d in spec["doors"]
    ]
    tbl_svg, tbl_h = render_table(
        SB_X, cur_y, [90, 210, 560, 815],
        "DOOR SCHEDULE (ALL DIMENSIONS IN MILLIMETERS)",
        ["TAG", "W × H (mm)", "SPECIFICATION", "OPERATION / SWING DIRECTION"],
        door_rows, mode
    )
    p.append(tbl_svg)
    cur_y += tbl_h + 22

    win_rows = [
        [w["id"], f"{w['width_mm']:,} × {w['height_mm']:,}", f"{w['sill_height_mm']:,} mm", w["type"], w["orientation"]]
        for w in spec["windows"]
    ]
    tbl_svg, tbl_h = render_table(
        SB_X, cur_y, [90, 210, 155, 560, 660],
        "WINDOW SCHEDULE (GLAZING & SILL HEIGHTS)",
        ["TAG", "W × H (mm)", "SILL", "WINDOW TYPE", "ORIENTATION"],
        win_rows, mode
    )
    p.append(tbl_svg)
    cur_y += tbl_h + 22

    # 4. ARCHITECTURAL LEGEND + NORTH ARROW + 1:50 SCALE BAR
    leg_h = 250
    c_bg = "#0E1A2C" if bp else "#FAF8F4"
    c_bd = "#284669" if bp else "#D5CEC3"
    p.append(f'<rect x="{SB_X}" y="{cur_y}" width="{SB_W}" height="{leg_h}" rx="5" fill="{c_bg}" stroke="{c_bd}" stroke-width="1.5"/>')
    p.append(f'<text x="{SB_X + 20}" y="{cur_y + 32}" fill="{"#38BDF8" if bp else "#1E242B"}" font-family="Inter, Helvetica Neue, Arial" font-size="16" font-weight="800" letter-spacing="1.2">{"ARCHITECTURAL LEGEND & GRAPHIC SYMBOLS" if bp else "MATERIAL PALETTE, LEGEND & ORIENTATION"}</text>')

    # Legend swatches (left half of legend box)
    if bp:
        swatches = [
            ("Exterior Wall (200 mm)", "url(#wallHatchExt)", "#F8FAFC"),
            ("Interior Partition (120 mm)", "url(#wallHatchInt)", "#CBD5E1"),
            ("Glazing / Window Assembly", "#0D2D4A", "#38BDF8"),
            ("Door Leaf & Swing Arc", "#F59E0B", "#F59E0B"),
            ("Site Boundary (9,144 × 13,500)", "none", "#FACC15"),
            ("Dimension Lines (mm)", "none", "#22D3EE"),
        ]
    else:
        swatches = [
            ("Engineered White Oak (Bedrooms)", "url(#oakFloor)", "#B6966E"),
            ("Honed Limestone 900×900 (Living)", "url(#limestoneTile)", "#CEC6B8"),
            ("Honed Travertine (Bathrooms)", "url(#travertineTile)", "#BFB7A8"),
            ("Oiled Teak Decking (Rear Terrace)", "url(#teakDeck)", "#7E5936"),
            ("Flamed Basalt Pavers (Carport)", "url(#basaltPaver)", "#50565E"),
            ("Exterior 200mm / Interior 120mm Wall", "#242A33", "#14181E"),
        ]
    for i, (lbl, fl, st) in enumerate(swatches):
        col = i // 3
        row = i % 3
        lx = SB_X + 24 + col * 430
        ly = cur_y + 62 + row * 56
        p.append(f'<rect x="{lx}" y="{ly}" width="44" height="24" fill="{fl}" stroke="{st}" stroke-width="2" rx="2"/>')
        p.append(f'<text x="{lx + 58}" y="{ly + 17}" fill="{"#E2E8F0" if bp else "#1E293B"}" font-family="Inter, Helvetica Neue, Arial" font-size="15">{lbl}</text>')

    # Graphic Scale Bar (1:50) in right-center of legend box
    sbx = SB_X + 915
    sby = cur_y + 110
    p.append(f'<text x="{sbx}" y="{sby - 18}" fill="{"#94B8D7" if bp else "#334155"}" font-family="SF Mono, Menlo, monospace" font-size="14" font-weight="700">GRAPHIC SCALE 1:50 (METERS)</text>')
    seg_px = 1000 * SCALE  # exact 1 meter at plan scale (148 px)
    for i in range(4):
        fill_s = ("#22D3EE" if bp else "#1E242B") if i % 2 == 0 else ("#0B1626" if bp else "#FFFFFF")
        p.append(f'<rect x="{sbx + i * seg_px:.1f}" y="{sby}" width="{seg_px:.1f}" height="18" fill="{fill_s}" stroke="{"#38BDF8" if bp else "#1E242B"}" stroke-width="1.5"/>')
        p.append(f'<text x="{sbx + i * seg_px:.1f}" y="{sby + 38}" text-anchor="middle" fill="{"#CBD5E1" if bp else "#334155"}" font-family="SF Mono, Menlo, monospace" font-size="13">{i}m</text>')
    p.append(f'<text x="{sbx + 4 * seg_px:.1f}" y="{sby + 38}" text-anchor="middle" fill="{"#CBD5E1" if bp else "#334155"}" font-family="SF Mono, Menlo, monospace" font-size="13">4m</text>')
    p.append(f'<text x="{sbx}" y="{sby + 74}" fill="{"#94A3B8" if bp else "#64748B"}" font-family="Inter, Helvetica Neue, Arial" font-size="13">Ceiling: 3,000 mm (Wet areas 2,800 mm)  •  Zero Perspective Distortion</text>')

    # North Arrow (far right of legend box)
    nax = SB_X + SB_W - 95
    nay = cur_y + 135
    na_col = "#22D3EE" if bp else "#1E242B"
    p.append(f'<circle cx="{nax}" cy="{nay}" r="54" fill="none" stroke="{na_col}" stroke-width="2"/>')
    p.append(f'<polygon points="{nax},{nay - 46} {nax - 20},{nay + 24} {nax},{nay + 8} {nax + 20},{nay + 24}" fill="{na_col}"/>')
    p.append(f'<text x="{nax}" y="{nay - 62}" text-anchor="middle" fill="{na_col}" font-family="Inter, Helvetica Neue, Arial" font-size="22" font-weight="800">N</text>')
    cur_y += leg_h + 22

    # 5. ARCHITECTURAL TITLE BLOCK (Bottom-Right)
    tb_h = (CANVAS_H - 68) - cur_y
    tb_bg = "#0C182B" if bp else "#1E242B"
    p.append(f'<rect x="{SB_X}" y="{cur_y}" width="{SB_W}" height="{tb_h}" rx="5" fill="{tb_bg}" stroke="{"#38BDF8" if bp else "#1E242B"}" stroke-width="2"/>')
    p.append(f'<line x1="{SB_X + 1150}" y1="{cur_y}" x2="{SB_X + 1150}" y2="{cur_y + tb_h}" stroke="#334E6E" stroke-width="1.5"/>')
    p.append(f'<text x="{SB_X + 26}" y="{cur_y + 42}" fill="#38BDF8" font-family="SF Mono, Menlo, monospace" font-size="14" font-weight="700" letter-spacing="2">ARCHITECTURAL DESIGN &amp; VISUALIZATION STUDIO</text>')
    p.append(f'<text x="{SB_X + 26}" y="{cur_y + 84}" fill="#FFFFFF" font-family="Inter, Helvetica Neue, Arial" font-size="30" font-weight="800">VILLA AURELIA 123 — SINGLE-STORY LUXURY RESIDENCE</text>')
    p.append(f'<text x="{SB_X + 26}" y="{cur_y + 118}" fill="#CBD5E1" font-family="Inter, Helvetica Neue, Arial" font-size="16">Plot: 9,144 × 13,500 mm (123.44 m² / 1,328.74 sq ft)  |  Footprint: 80.17 m²  |  Usable Interior: 69.43 m²</text>')
    p.append(f'<text x="{SB_X + 26}" y="{cur_y + 148}" fill="#94A3B8" font-family="SF Mono, Menlo, monospace" font-size="13">Geometry Source: floorplan-spec.json (CADCraft DXF &amp; Three.js Ready)  |  Verified 0.00 m² Residual</text>')

    # Sheet Number Box
    p.append(f'<text x="{SB_X + 1180}" y="{cur_y + 38}" fill="#94B8D7" font-family="SF Mono, Menlo, monospace" font-size="13" font-weight="700">SHEET NO.</text>')
    sheet_no = "A-101" if bp else "A-102"
    p.append(f'<text x="{SB_X + 1180}" y="{cur_y + 92}" fill="#22D3EE" font-family="Inter, Helvetica Neue, Arial" font-size="44" font-weight="800">{sheet_no}</text>')
    p.append(f'<text x="{SB_X + 1370}" y="{cur_y + 52}" fill="#94B8D7" font-family="SF Mono, Menlo, monospace" font-size="13">SCALE: 1:50</text>')
    p.append(f'<text x="{SB_X + 1370}" y="{cur_y + 78}" fill="#94B8D7" font-family="SF Mono, Menlo, monospace" font-size="13">UNITS: MM</text>')
    p.append(f'<text x="{SB_X + 1370}" y="{cur_y + 104}" fill="#94B8D7" font-family="SF Mono, Menlo, monospace" font-size="13">DATE: 2026-11-25</text>')
    p.append(f'<text x="{SB_X + 1180}" y="{cur_y + 144}" fill="#CBD5E1" font-family="SF Mono, Menlo, monospace" font-size="12">{"TECHNICAL BLUEPRINT" if bp else "PRESENTATION EDITION"}</text>')

    p.append('</svg>')
    return "\n".join(p)


def svg_to_png(svg_path: Path, png_path: Path, svg_text: str):
    html_path = svg_path.with_suffix(".html")
    html_path.write_text(
        f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
        f'html,body{{margin:0;padding:0;width:{CANVAS_W}px;height:{CANVAS_H}px;overflow:hidden;}}'
        f'svg{{display:block;width:{CANVAS_W}px;height:{CANVAS_H}px;}}'
        f'</style></head><body>{svg_text}</body></html>',
        encoding="utf-8",
    )
    cmd = [
        CHROME,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--force-device-scale-factor=1",
        f"--window-size={CANVAS_W},{CANVAS_H}",
        f"--screenshot={png_path}",
        f"file://{html_path}",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    html_path.unlink(missing_ok=True)
    if res.returncode != 0:
        raise RuntimeError(f"Chrome render failed: {res.stderr}")


for mode, stem in [("blueprint", "floorplan-blueprint-v1"), ("presentation", "floorplan-presentation-v2")]:
    svg_path = OUT_DIR / f"{stem}.svg"
    png_path = OUT_DIR / f"{stem}.png"
    svg_text = build_sheet(mode)
    svg_path.write_text(svg_text, encoding="utf-8")
    svg_to_png(svg_path, png_path, svg_text)
    print(f"Rendered {svg_path.name} -> {png_path.name} ({png_path.stat().st_size:,} bytes)")
