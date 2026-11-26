#!/usr/bin/env python3
"""
High-Craft Photorealistic Satin-Matte PBR Texture Synthesizer (512-1024 px) for Villa Aurelia 123.
Produces tactile Albedo (with micro-cavity AO darkening), physically-calibrated Roughness,
and crisp tangent-space Normal maps with high-frequency mineral/fiber/weave micro-detail.
"""

from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

TEX_DIR = Path("/Users/macbookm2/.gemini/antigravity/scratch/luxury-residence-floorplan/blender/textures")
TEX_DIR.mkdir(parents=True, exist_ok=True)


def value_noise_2d(size: int, grid_x: int, grid_y: int, seed: int) -> np.ndarray:
    """Fast, strictly tileable smooth quintic value noise on a toroidal grid."""
    rng = np.random.default_rng(seed)
    grid = rng.random((grid_y, grid_x), dtype=np.float32)

    y = np.linspace(0, grid_y, size, endpoint=False, dtype=np.float32)
    x = np.linspace(0, grid_x, size, endpoint=False, dtype=np.float32)
    x0 = np.floor(x).astype(np.int32) % grid_x
    y0 = np.floor(y).astype(np.int32) % grid_y
    x1 = (x0 + 1) % grid_x
    y1 = (y0 + 1) % grid_y

    tx = x - np.floor(x)
    ty = y - np.floor(y)
    sx = tx * tx * tx * (tx * (tx * 6.0 - 15.0) + 10.0)
    sy = ty * ty * ty * (ty * (ty * 6.0 - 15.0) + 10.0)

    c00 = grid[y0[:, None], x0[None, :]]
    c10 = grid[y0[:, None], x1[None, :]]
    c01 = grid[y1[:, None], x0[None, :]]
    c11 = grid[y1[:, None], x1[None, :]]

    nx0 = c00 * (1.0 - sx[None, :]) + c10 * sx[None, :]
    nx1 = c01 * (1.0 - sx[None, :]) + c11 * sx[None, :]
    return nx0 * (1.0 - sy[:, None]) + nx1 * sy[:, None]


def fbm(size: int, octaves, seed: int = 42) -> np.ndarray:
    """Tileable multi-octave fBm; octaves is list of (gx, gy, weight)."""
    acc = np.zeros((size, size), dtype=np.float32)
    wsum = 0.0
    for i, (gx, gy, w) in enumerate(octaves):
        acc += w * value_noise_2d(size, gx, gy, seed + i * 37)
        wsum += w
    acc /= max(wsum, 1e-6)
    return np.clip(acc, 0.0, 1.0)


def height_to_normal(height: np.ndarray, strength: float = 2.0) -> Image.Image:
    # Multi-scale Sobel gradient for cleaner, sharper micro-surface relief
    hx = (
        (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * 0.65
        + (np.roll(height, -2, axis=1) - np.roll(height, 2, axis=1)) * 0.35
    ) * strength
    hy = (
        (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * 0.65
        + (np.roll(height, -2, axis=0) - np.roll(height, 2, axis=0)) * 0.35
    ) * strength
    nx = -hx
    ny = hy
    nz = np.ones_like(height)
    norm = np.sqrt(nx * nx + ny * ny + nz * nz) + 1e-6
    r = np.clip((nx / norm * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8)
    g = np.clip((ny / norm * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8)
    b = np.clip((nz / norm * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8)
    return Image.fromarray(np.stack([r, g, b], axis=-1), mode="RGB")


def save_pbr(name: str, albedo_rgb: np.ndarray, rough_01: np.ndarray, height_01: np.ndarray, normal_strength=2.0):
    Image.fromarray(np.clip(albedo_rgb, 0, 255).astype(np.uint8), mode="RGB").save(
        TEX_DIR / f"{name}_albedo.png", optimize=True
    )
    r_img = Image.fromarray(np.clip(rough_01 * 255, 0, 255).astype(np.uint8), mode="L")
    n_img = height_to_normal(height_01, strength=normal_strength)
    # 512px Roughness & Normal maps (256px for high-frequency tiled micro-weave fabrics) preserve full tactile relief while slashing VRAM & GLB size
    is_micro_fabric = any(k in name for k in ("fabric_", "linen_", "boucle_", "rug_"))
    max_aux = 256 if is_micro_fabric else 512
    if r_img.width > max_aux:
        r_img = r_img.resize((max_aux, max_aux), Image.Resampling.LANCZOS)
        n_img = n_img.resize((max_aux, max_aux), Image.Resampling.LANCZOS)
    r_img.save(TEX_DIR / f"{name}_roughness.png", optimize=True)
    n_img.save(TEX_DIR / f"{name}_normal.png", optimize=True)


def make_wood_veneer(name: str, size: int, light_rgb, mid_rgb, dark_rgb, seed=10, rough_base=0.66):
    """
    Wire-brushed architectural straight-grain wood veneer (American Walnut / White Oak).
    High-frequency longitudinal wood vessels, subtle medullary rays, and fine dark pore cavities.
    """
    fibers_fine = fbm(size, [(128, 8, 0.42), (256, 14, 0.36), (512, 24, 0.22)], seed=seed)
    fibers_med = fbm(size, [(36, 3, 0.55), (72, 6, 0.45)], seed=seed + 29)
    pores = fbm(size, [(320, 28, 0.65), (512, 48, 0.35)], seed=seed + 55)
    rays = fbm(size, [(18, 96, 0.6), (36, 192, 0.4)], seed=seed + 73)
    broad_tone = fbm(size, [(6, 2, 0.6), (14, 4, 0.4)], seed=seed + 99)

    t = np.clip(0.46 * fibers_fine + 0.34 * fibers_med + 0.20 * broad_tone, 0.0, 1.0)
    c0, c1, c2 = [np.array(c, dtype=np.float32) for c in (light_rgb, mid_rgb, dark_rgb)]
    albedo = np.where(
        t[..., None] < 0.5,
        c0 * (1 - 2 * t[..., None]) + c1 * (2 * t[..., None]),
        c1 * (2 - 2 * t[..., None]) + c2 * (2 * t[..., None] - 1),
    )
    # Crisp dark open-pore grain micro-grooves + subtle warm medullary fleck
    pore_groove = np.clip((pores - 0.62) * 0.72, 0.0, 0.24)
    ray_sheen = np.clip((rays - 0.68) * 0.20, 0.0, 0.06)
    albedo = albedo * (1.0 - pore_groove[..., None] + ray_sheen[..., None])

    height = np.clip(0.75 - 0.30 * pore_groove - 0.16 * (1.0 - fibers_fine), 0, 1)
    rough = np.clip(rough_base + 0.14 * pore_groove + 0.08 * (0.5 - fibers_fine), 0.56, 0.86)
    save_pbr(name, albedo, rough, height, normal_strength=1.85)


def make_wood_planks(name: str, size: int, light_rgb, mid_rgb, dark_rgb, planks=7, seed=11, rough_base=0.64, gap_px=2):
    """Authentic wide-plank engineered wood flooring / oiled teak decking with chamfered V-bevel AO."""
    fibers = fbm(size, [(96, 8, 0.45), (192, 14, 0.35), (384, 26, 0.20)], seed=seed)
    grain_band = fbm(size, [(28, 3, 0.58), (56, 6, 0.42)], seed=seed + 23)
    pores = fbm(size, [(320, 28, 0.65), (160, 16, 0.35)], seed=seed + 41)
    y, x = np.mgrid[0:size, 0:size]
    u = x / size
    v = y / size

    plank_w = size / planks
    p_idx = np.floor(x / plank_w).astype(np.int32) % planks
    rng = np.random.default_rng(seed + 77)
    p_tone = rng.uniform(-0.08, 0.08, size=planks)[p_idx]
    p_voff = rng.uniform(0.0, 1.0, size=planks)[p_idx]

    t = np.clip(0.48 * fibers + 0.36 * grain_band + 0.16 * pores + p_tone, 0.0, 1.0)

    # Smooth micro-beveled V-groove edge profile with natural edge AO shadow
    px_in_plank = x % plank_w
    dist_v = np.minimum(px_in_plank, plank_w - px_in_plank)
    bevel_v = np.clip(dist_v / (gap_px * 2.2), 0.0, 1.0)
    seam_v = dist_v < gap_px

    vy_in_board = ((v + p_voff) * 2.0) % 1.0
    dist_h = np.minimum(vy_in_board, 1.0 - vy_in_board) * size * 0.5
    bevel_h = np.clip(dist_h / (gap_px * 1.8), 0.0, 1.0)
    seam_h = dist_h < (gap_px * 0.75)

    bevel_ao = np.minimum(bevel_v, bevel_h)
    seam = seam_v | seam_h

    c0, c1, c2 = [np.array(c, dtype=np.float32) for c in (light_rgb, mid_rgb, dark_rgb)]
    albedo = np.where(
        t[..., None] < 0.5,
        c0 * (1 - 2 * t[..., None]) + c1 * (2 * t[..., None]),
        c1 * (2 - 2 * t[..., None]) + c2 * (2 * t[..., None] - 1),
    )
    pore_dark = np.clip((pores - 0.65) * 0.55, 0.0, 0.18)[..., None]
    albedo = albedo * (1.0 - pore_dark) * (0.68 + 0.32 * bevel_ao[..., None])
    albedo = np.where(seam[..., None], c2 * 0.44, albedo)

    height = np.where(seam, 0.08, 0.30 + 0.50 * bevel_ao - 0.14 * (1.0 - fibers))
    rough = np.clip(rough_base + 0.10 * fibers + (1.0 - bevel_ao) * 0.22, 0.55, 0.94)
    save_pbr(name, albedo, rough, height, normal_strength=2.3)


def make_fluted_wood(name: str, size: int, light_rgb, dark_rgb, flutes=28, seed=13):
    """Deep architectural fluted timber slats with soft cosine roundness & realistic valley AO."""
    fibers = fbm(size, [(128, 8, 0.55), (256, 16, 0.45)], seed=seed)
    y, x = np.mgrid[0:size, 0:size]
    u = x / size
    phase = (u * flutes) % 1.0
    slat_h = np.where(phase < 0.20, 0.04, 0.34 + 0.66 * np.sin(((phase - 0.20) / 0.80) * np.pi))
    ao = np.clip(0.32 + 0.68 * slat_h, 0.28, 1.0)
    c0, c1 = np.array(light_rgb, dtype=np.float32), np.array(dark_rgb, dtype=np.float32)
    base = c0 * (1.0 - fibers[..., None] * 0.55) + c1 * (fibers[..., None] * 0.55)
    albedo = base * ao[..., None]
    rough = np.clip(0.64 + 0.24 * (1.0 - slat_h), 0.58, 0.90)
    save_pbr(name, albedo, rough, slat_h, normal_strength=3.6)


def make_stone(name: str, size: int, base_rgb, vein_rgb, dark_vein_rgb, grout_rgb, tiles=2, seed=20, rough_base=0.66, linear_travertine=False):
    """
    Honed geological stone / marble / limestone / basalt tile texture with fine mineral grain,
    ridged branching capillaries, and recessed chamfered grout shadow joints.
    """
    cloud = fbm(size, [(4, 4, 0.45), (8, 8, 0.35), (16, 16, 0.20)], seed=seed)
    micro = fbm(size, [(48, 48, 0.42), (96, 96, 0.35), (256, 256, 0.23)], seed=seed + 41)
    mineral = fbm(size, [(256, 256, 0.55), (512, 512, 0.45)], seed=seed + 131)
    ridge_src = fbm(size, [(3, 3, 0.50), (6, 6, 0.32), (12, 12, 0.18)], seed=seed + 67)
    ridge_src2 = fbm(size, [(5, 5, 0.55), (10, 10, 0.45)], seed=seed + 89)

    y, x = np.mgrid[0:size, 0:size]
    u = x / size
    v = y / size

    if linear_travertine:
        bands = fbm(size, [(4, 32, 0.48), (8, 64, 0.32), (16, 128, 0.20)], seed=seed + 71)
        vein = np.clip(0.60 * bands + 0.40 * micro, 0, 1)
        fine_vein = np.power(np.clip(1.0 - np.abs(bands - 0.52) * 5.2, 0, 1), 3.0) * 0.48
    else:
        vein = np.clip(0.55 * cloud + 0.45 * micro, 0, 1)
        r1 = np.power(np.clip(1.0 - np.abs(ridge_src - 0.50) * 7.8, 0.0, 1.0), 3.5)
        r2 = np.power(np.clip(1.0 - np.abs(ridge_src2 - 0.48) * 9.5, 0.0, 1.0), 4.0) * 0.55
        fine_vein = np.clip(r1 * (0.45 + 0.55 * micro) + r2, 0.0, 1.0) * 0.56

    c_base = np.array(base_rgb, dtype=np.float32)
    c_vein = np.array(vein_rgb, dtype=np.float32)
    c_dark = np.array(dark_vein_rgb, dtype=np.float32)
    c_grout = np.array(grout_rgb, dtype=np.float32)

    albedo = c_base * (1.0 - vein[..., None] * 0.44) + c_vein * (vein[..., None] * 0.44)
    albedo = albedo * (1.0 - fine_vein[..., None]) + c_dark * fine_vein[..., None]
    # Crisp mineral sparkle/speckle micro-grain
    albedo *= (0.955 + 0.09 * mineral[..., None])

    grout = np.zeros((size, size), dtype=bool)
    chamfer = np.ones((size, size), dtype=np.float32)
    if tiles > 0:
        tx = np.floor(u * tiles).astype(np.int32) % tiles
        ty = np.floor(v * tiles).astype(np.int32) % tiles
        rng = np.random.default_rng(seed + 111)
        tile_var = rng.uniform(0.968, 1.032, size=(tiles, tiles))[ty, tx]
        albedo *= tile_var[..., None]

        ug = (u * tiles) % 1.0
        vg = (v * tiles) % 1.0
        d_edge = np.minimum(np.minimum(ug, 1.0 - ug), np.minimum(vg, 1.0 - vg))
        gw = 0.0045
        grout = d_edge < gw
        chamfer = np.clip((d_edge - gw) / 0.010, 0.0, 1.0)
        albedo = albedo * (0.84 + 0.16 * chamfer[..., None])
        albedo = np.where(grout[..., None], c_grout, albedo)

    height = np.where(grout, 0.12, 0.35 + 0.48 * chamfer - 0.14 * micro - 0.08 * mineral)
    rough = np.clip(rough_base + 0.12 * micro + 0.06 * (1.0 - mineral) + np.where(grout, 0.28, 0.0), 0.48, 0.96)
    save_pbr(name, albedo, rough, height, normal_strength=2.1)


def make_limewash_plaster(name: str, size: int, base_rgb, seed=30, rough_base=0.91):
    """Tactile hand-troweled Venetian limewash / mineral architectural plaster."""
    trowel = fbm(size, [(4, 4, 0.42), (9, 9, 0.35), (20, 20, 0.23)], seed=seed)
    sand = fbm(size, [(96, 96, 0.45), (192, 192, 0.35), (384, 384, 0.20)], seed=seed + 31)
    c = np.array(base_rgb, dtype=np.float32)
    albedo = c * (0.93 + 0.11 * trowel[..., None] + 0.045 * (sand[..., None] - 0.5))
    rough = np.clip(rough_base + 0.07 * (trowel - 0.5) + 0.05 * (sand - 0.5), 0.84, 0.98)
    height = 0.52 * trowel + 0.48 * sand
    save_pbr(name, albedo, rough, height, normal_strength=1.35)


def make_woven_fabric(name: str, size: int, base_rgb, seed=40, rough_base=0.94):
    """Heavy tactile bouclé / Belgian linen upholstery weave with yarn-knot micro-shadows."""
    y, x = np.mgrid[0:size, 0:size]
    warp = 0.5 + 0.5 * np.sin(2.0 * np.pi * x / 4.5)
    weft = 0.5 + 0.5 * np.sin(2.0 * np.pi * y / 4.5)
    checker = ((x // 4 + y // 4) % 2).astype(np.float32)
    slub = fbm(size, [(24, 6, 0.38), (6, 24, 0.38), (96, 96, 0.24)], seed=seed)
    knots = fbm(size, [(160, 160, 0.6), (320, 320, 0.4)], seed=seed + 53)
    weave = 0.34 * (warp * checker + weft * (1.0 - checker)) + 0.38 * slub + 0.28 * knots
    c = np.array(base_rgb, dtype=np.float32)
    albedo = c * (0.85 + 0.24 * weave[..., None])
    rough = np.clip(rough_base + 0.05 * (1.0 - weave), 0.88, 0.99)
    save_pbr(name, albedo, rough, weave, normal_strength=2.3)


def make_lush_grass(name: str, size: int, seed=50):
    """High-frequency natural tropical Zoysia turf with rich blade & soil depth."""
    patches = fbm(size, [(6, 6, 0.45), (14, 14, 0.35), (32, 32, 0.20)], seed=seed)
    blades = fbm(size, [(128, 128, 0.35), (256, 256, 0.38), (512, 512, 0.27)], seed=seed + 17)
    c_soil = np.array([46, 58, 32], dtype=np.float32)
    c_mid = np.array([72, 95, 46], dtype=np.float32)
    c_sun = np.array([108, 128, 64], dtype=np.float32)
    t = np.clip(0.45 * patches + 0.55 * blades, 0.0, 1.0)[..., None]
    albedo = np.where(t < 0.5, c_soil * (1 - 2 * t) + c_mid * (2 * t), c_mid * (2 - 2 * t) + c_sun * (2 * t - 1))
    rough = np.clip(0.90 + 0.08 * (1.0 - blades), 0.86, 0.99)
    save_pbr(name, albedo, rough, blades, normal_strength=3.4)


def make_artwork(filename: str, palette, seed=70):
    """Painterly gallery-grade textured minimalist canvas artwork."""
    w, h = 512, 640
    img = Image.new("RGB", (w, h), palette[0])
    draw = ImageDraw.Draw(img)
    draw.rectangle([48, 58, 336, 468], fill=palette[1])
    draw.ellipse([130, 165, 465, 500], fill=palette[2])
    draw.polygon([(70, 560), (260, 290), (455, 560)], fill=palette[3])
    draw.arc([90, 95, 430, 435], start=205, end=25, fill=palette[4], width=7)
    draw.line([(56, 470), (w - 56, 470)], fill=palette[4], width=3)
    img = img.filter(ImageFilter.GaussianBlur(radius=1.0))

    arr = np.array(img, dtype=np.float32)
    n = fbm(512, [(32, 32, 0.4), (96, 96, 0.4), (192, 192, 0.2)], seed=seed)
    n_crop = np.vstack([n, n[: h - 512, :]])
    arr = np.clip(arr * (0.93 + 0.13 * n_crop[..., None]), 0, 255).astype(np.uint8)
    Image.fromarray(arr).save(TEX_DIR / filename, optimize=True)


print("Synthesizing high-craft tactile PBR texture maps with micro-AO and crisp normals...")
make_wood_planks("white_oak", 1024, [206, 178, 142], [180, 150, 114], [142, 112, 80], planks=7, seed=11, rough_base=0.64, gap_px=2)
make_wood_planks("teak_deck", 1024, [156, 112, 72], [128, 88, 54], [84, 54, 30], planks=11, seed=14, rough_base=0.68, gap_px=3)

make_wood_veneer("walnut_wood", 1024, [118, 78, 50], [88, 56, 35], [58, 35, 21], seed=12, rough_base=0.65)
make_wood_veneer("light_oak_veneer", 1024, [214, 188, 154], [188, 160, 126], [154, 126, 94], seed=15, rough_base=0.66)
make_fluted_wood("fluted_walnut", 512, [116, 78, 50], [56, 34, 20], flutes=28, seed=13)
make_fluted_wood("fluted_oak", 512, [210, 184, 150], [152, 122, 88], flutes=28, seed=16)

make_stone("limestone_tile", 1024, [224, 215, 201], [204, 194, 179], [180, 170, 155], [166, 158, 146], tiles=2, seed=21, rough_base=0.66)
make_stone("travertine_tile", 1024, [214, 200, 181], [186, 171, 150], [156, 140, 120], [158, 148, 134], tiles=3, seed=22, rough_base=0.68, linear_travertine=True)
make_stone("modern_stone", 1024, [180, 178, 173], [156, 155, 150], [132, 132, 128], [118, 118, 115], tiles=2, seed=23, rough_base=0.64)
make_stone("basalt_paver", 1024, [82, 86, 91], [64, 68, 73], [48, 51, 56], [36, 39, 43], tiles=4, seed=24, rough_base=0.80)
make_stone("calacatta_marble", 1024, [241, 237, 230], [218, 211, 200], [162, 152, 139], [208, 203, 194], tiles=0, seed=25, rough_base=0.52)
make_stone("charcoal_quartz", 512, [52, 55, 60], [42, 45, 50], [32, 35, 39], [32, 35, 39], tiles=0, seed=26, rough_base=0.56)
make_stone("porcelain_grey", 512, [186, 188, 184], [170, 173, 169], [152, 155, 152], [140, 143, 140], tiles=3, seed=27, rough_base=0.68)

make_limewash_plaster("stucco_warm_white", 512, [237, 232, 222], seed=31, rough_base=0.91)
make_limewash_plaster("stucco_pure_white", 512, [244, 241, 236], seed=32, rough_base=0.90)
make_limewash_plaster("stucco_exterior", 512, [233, 228, 218], seed=33, rough_base=0.92)

make_woven_fabric("boucle_beige", 512, [218, 204, 186], seed=41, rough_base=0.94)
make_woven_fabric("linen_oatmeal", 512, [228, 220, 208], seed=42, rough_base=0.95)
make_woven_fabric("fabric_charcoal", 512, [70, 74, 80], seed=43, rough_base=0.93)
make_woven_fabric("rug_ivory", 512, [232, 224, 212], seed=44, rough_base=0.97)
make_woven_fabric("linen_sage", 512, [154, 166, 150], seed=45, rough_base=0.94)
make_woven_fabric("fabric_terracotta", 512, [142, 80, 52], seed=46, rough_base=0.93)

make_lush_grass("tropical_lawn", 1024, seed=51)
make_artwork("art_warm_luxury.png", [(236, 228, 216), (190, 170, 144), (104, 74, 52), (214, 200, 180), (168, 132, 76)], seed=71)
make_artwork("art_scandinavian.png", [(242, 238, 232), (210, 204, 194), (150, 164, 148), (224, 218, 208), (78, 86, 78)], seed=72)
make_artwork("art_modern.png", [(234, 234, 230), (180, 182, 186), (44, 48, 56), (206, 208, 212), (24, 26, 30)], seed=73)


def make_ide_screen(filename):
    """Synthesizes a crisp dark-mode VS Code / Neovim IDE + terminal & telemetry screen."""
    w, h = 1024, 512
    img = Image.new("RGB", (w, h), (15, 18, 26))
    drw = ImageDraw.Draw(img)
    drw.rectangle([0, 0, w, 28], fill=(11, 13, 19))
    drw.ellipse([14, 9, 24, 19], fill=(240, 92, 82))
    drw.ellipse([30, 9, 40, 19], fill=(245, 188, 66))
    drw.ellipse([46, 9, 56, 19], fill=(82, 204, 112))
    drw.rectangle([0, 28, 155, h - 22], fill=(18, 22, 31))
    drw.line([155, 28, 155, h - 22], fill=(38, 46, 62), width=2)
    drw.line([595, 28, 595, 365], fill=(38, 46, 62), width=2)
    drw.rectangle([156, 365, w, h - 22], fill=(12, 15, 22))
    drw.line([156, 365, w, 365], fill=(44, 54, 72), width=2)
    drw.rectangle([0, h - 22, w, h], fill=(24, 118, 182))

    rng = np.random.default_rng(99)
    for r_i in range(18):
        y = 44 + r_i * 18
        indent = 16 + (r_i % 3) * 12
        length = int(rng.integers(45, 105))
        col = (140, 155, 178) if r_i % 4 != 0 else (212, 175, 118)
        drw.rounded_rectangle([indent, y, min(144, indent + length), y + 7], radius=2, fill=col)

    palette = [
        (86, 182, 242),
        (212, 175, 118),
        (152, 195, 121),
        (198, 120, 221),
        (224, 108, 117),
        (171, 178, 191),
    ]
    for pane_x0, pane_x1 in [(175, 575), (615, 1000)]:
        for line_i in range(21):
            y = 44 + line_i * 14
            if rng.random() < 0.14:
                continue
            indent = (line_i % 4) * 16
            cx = pane_x0 + indent
            n_tokens = int(rng.integers(2, 6))
            for _ in range(n_tokens):
                tw = int(rng.integers(22, 84))
                if cx + tw > pane_x1:
                    break
                c = palette[int(rng.integers(0, len(palette)))]
                drw.rounded_rectangle([cx, y, cx + tw, y + 7], radius=3, fill=c)
                cx += tw + int(rng.integers(8, 16))

    for t_i in range(6):
        y = 380 + t_i * 16
        drw.rounded_rectangle([172, y, 222, y + 6], radius=2, fill=(82, 204, 112))
        drw.rounded_rectangle([232, y, 232 + int(rng.integers(120, 360)), y + 6], radius=2, fill=(148, 162, 184))
    pts = [(640 + k * 14, int(445 - 35 * float(np.sin(k * 0.45)) - int(rng.integers(-12, 12)))) for k in range(25)]
    drw.line(pts, fill=(56, 189, 248), width=3)
    img.save(TEX_DIR / filename, optimize=True)


make_ide_screen("code_ide_screen.png")

files = list(TEX_DIR.glob("*.png"))
print(f"Generated {len(files)} high-craft tactile PBR texture maps in {TEX_DIR}")
