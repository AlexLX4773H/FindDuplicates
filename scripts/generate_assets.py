"""
Asset generator for CasaOS Docker App Store and Docker Compose.
Generates:
- assets/icon.png (512x512)
- assets/icon-256.png (256x256)
- assets/icon-128.png (128x128)
- assets/icon-64.png (64x64)
- assets/banner.png (1024x500)
Uses Pillow with 2x supersampling and Lanczos filter for smooth antialiasing.
"""

import math
import os
from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

def create_gradient_canvas(width, height, c_top_left, c_bottom_right):
    base = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(base)
    for y in range(height):
        t = y / (height - 1)
        # Interpolate between top-left and bottom-right
        r = int(c_top_left[0] * (1 - t) + c_bottom_right[0] * t)
        g = int(c_top_left[1] * (1 - t) + c_bottom_right[1] * t)
        b = int(c_top_left[2] * (1 - t) + c_bottom_right[2] * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))
    return base

def draw_rounded_rect_gradient(draw, xy, radius, fill_color, outline_color=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill_color, outline=outline_color, width=width)

def render_icon(target_size=512):
    # Render at 2x for supersampled sharpness
    scale = 2
    size = target_size * scale
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = 32 * scale
    squircle_box = [margin, margin, size - margin, size - margin]
    squircle_rad = 110 * scale

    # Dark background squircle
    draw.rounded_rectangle(
        squircle_box,
        radius=squircle_rad,
        fill=(20, 24, 45, 255),
        outline=(99, 102, 241, 180),
        width=4 * scale,
    )

    # Inner subtle glow edge
    inner_box = [margin + 6 * scale, margin + 6 * scale, size - margin - 6 * scale, size - margin - 6 * scale]
    draw.rounded_rectangle(
        inner_box,
        radius=squircle_rad - 6 * scale,
        outline=(244, 63, 94, 90),
        width=2 * scale,
    )

    # Screentone manga dots pattern in background
    for dot_x in range(margin + 40 * scale, size - margin - 40 * scale, 35 * scale):
        for dot_y in range(margin + 40 * scale, size - margin - 40 * scale, 35 * scale):
            draw.ellipse(
                [dot_x - 3 * scale, dot_y - 3 * scale, dot_x + 3 * scale, dot_y + 3 * scale],
                fill=(255, 255, 255, 12),
            )

    # Overlapping Manga Pages (Duplicate Metaphor)
    # 1. Back Page (slanted copy)
    p2_w, p2_h = 175 * scale, 240 * scale
    p2_x, p2_y = 195 * scale, 95 * scale
    # Draw back page
    draw.rounded_rectangle(
        [p2_x, p2_y, p2_x + p2_w, p2_y + p2_h],
        radius=14 * scale,
        fill=(148, 163, 184, 255),
        outline=(203, 213, 225, 255),
        width=3 * scale,
    )
    # Page lines
    draw.rectangle([p2_x + 18 * scale, p2_y + 25 * scale, p2_x + 90 * scale, p2_y + 37 * scale], fill=(100, 116, 139, 255))
    draw.rectangle([p2_x + 18 * scale, p2_y + 55 * scale, p2_x + 155 * scale, p2_y + 120 * scale], fill=(226, 232, 240, 255))
    draw.rectangle([p2_x + 18 * scale, p2_y + 135 * scale, p2_x + 80 * scale, p2_y + 215 * scale], fill=(226, 232, 240, 255))
    draw.rectangle([p2_x + 92 * scale, p2_y + 135 * scale, p2_x + 155 * scale, p2_y + 215 * scale], fill=(226, 232, 240, 255))

    # 2. Front Page (sharp, crisp white copy)
    p1_w, p1_h = 190 * scale, 265 * scale
    p1_x, p1_y = 110 * scale, 125 * scale
    draw.rounded_rectangle(
        [p1_x, p1_y, p1_x + p1_w, p1_y + p1_h],
        radius=16 * scale,
        fill=(255, 255, 255, 255),
        outline=(241, 245, 249, 255),
        width=3 * scale,
    )
    # Front page Manga Header & Panels
    draw.rectangle([p1_x + 20 * scale, p1_y + 24 * scale, p1_x + 95 * scale, p1_y + 38 * scale], fill=(15, 23, 42, 255))
    # Chapter 01 badge on page
    draw.rounded_rectangle(
        [p1_x + 115 * scale, p1_y + 18 * scale, p1_x + 172 * scale, p1_y + 42 * scale],
        radius=12 * scale,
        fill=(244, 63, 94, 255),
    )
    # Panel 1 (Top Hero Comic Panel - Dark Ink Style)
    draw.rounded_rectangle(
        [p1_x + 20 * scale, p1_y + 52 * scale, p1_x + 170 * scale, p1_y + 140 * scale],
        radius=8 * scale,
        fill=(30, 41, 59, 255),
    )
    # Stylized rising sun / speed focus in panel
    draw.ellipse(
        [p1_x + 75 * scale, p1_y + 75 * scale, p1_x + 115 * scale, p1_y + 115 * scale],
        fill=(239, 68, 68, 255),
    )
    draw.line([p1_x + 25 * scale, p1_y + 58 * scale, p1_x + 75 * scale, p1_y + 85 * scale], fill=(56, 189, 248, 160), width=2 * scale)
    draw.line([p1_x + 165 * scale, p1_y + 58 * scale, p1_x + 115 * scale, p1_y + 85 * scale], fill=(56, 189, 248, 160), width=2 * scale)

    # Panels 2 & 3 (Bottom Split Panels)
    draw.rounded_rectangle(
        [p1_x + 20 * scale, p1_y + 152 * scale, p1_x + 90 * scale, p1_y + 242 * scale],
        radius=8 * scale,
        fill=(248, 250, 252, 255),
        outline=(203, 213, 225, 255),
        width=2 * scale,
    )
    draw.rounded_rectangle(
        [p1_x + 100 * scale, p1_y + 152 * scale, p1_x + 170 * scale, p1_y + 242 * scale],
        radius=8 * scale,
        fill=(248, 250, 252, 255),
        outline=(203, 213, 225, 255),
        width=2 * scale,
    )

    # Scanner / Duplicate Detection Lens (Bottom-right badge)
    lens_cx, lens_cy = 345 * scale, 345 * scale
    lens_r = 74 * scale

    # Outer neon ring
    draw.ellipse(
        [lens_cx - lens_r, lens_cy - lens_r, lens_cx + lens_r, lens_cy + lens_r],
        fill=(15, 23, 42, 250),
        outline=(56, 189, 248, 255),
        width=6 * scale,
    )
    # Inner lens surface
    draw.ellipse(
        [lens_cx - (lens_r - 10 * scale), lens_cy - (lens_r - 10 * scale), lens_cx + (lens_r - 10 * scale), lens_cy + (lens_r - 10 * scale)],
        fill=(24, 30, 56, 255),
        outline=(168, 85, 247, 200),
        width=3 * scale,
    )

    # Twin Duplicate Icon inside lens
    # Left Doc
    d_x, d_y = lens_cx - 30 * scale, lens_cy - 28 * scale
    draw.rounded_rectangle(
        [d_x, d_y, d_x + 32 * scale, d_y + 44 * scale],
        radius=5 * scale,
        fill=(30, 41, 59, 200),
        outline=(56, 189, 248, 255),
        width=3 * scale,
    )
    # Right Overlapping Doc (The Duplicate)
    d2_x, d2_y = lens_cx - 12 * scale, lens_cy - 16 * scale
    draw.rounded_rectangle(
        [d2_x, d2_y, d2_x + 32 * scale, d2_y + 44 * scale],
        radius=5 * scale,
        fill=(40, 25, 50, 240),
        outline=(244, 63, 94, 255),
        width=3 * scale,
    )
    # Equality green checkmark / equal badge
    eq_x, eq_y = lens_cx + 18 * scale, lens_cy - 24 * scale
    eq_r = 14 * scale
    draw.ellipse(
        [eq_x - eq_r, eq_y - eq_r, eq_x + eq_r, eq_y + eq_r],
        fill=(16, 185, 129, 255),
        outline=(255, 255, 255, 255),
        width=2 * scale,
    )
    draw.line([eq_x - 6 * scale, eq_y - 2 * scale, eq_x + 6 * scale, eq_y - 2 * scale], fill=(255, 255, 255, 255), width=3 * scale)
    draw.line([eq_x - 6 * scale, eq_y + 3 * scale, eq_x + 6 * scale, eq_y + 3 * scale], fill=(255, 255, 255, 255), width=3 * scale)

    # Scanner handle
    draw.line(
        [lens_cx + 52 * scale, lens_cy + 52 * scale, lens_cx + 90 * scale, lens_cy + 90 * scale],
        fill=(14, 165, 233, 255),
        width=12 * scale,
    )

    # Antialiased downscaling
    final_img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)
    return final_img

def render_banner(width=1024, height=500):
    scale = 2
    sw, sh = width * scale, height * scale
    img = Image.new("RGBA", (sw, sh), (10, 13, 26, 255))
    draw = ImageDraw.Draw(img)

    # Subtle background gradient layers
    for y in range(sh):
        factor = y / sh
        r = int(12 * (1 - factor) + 20 * factor)
        g = int(15 * (1 - factor) + 26 * factor)
        b = int(32 * (1 - factor) + 48 * factor)
        draw.line([(0, y), (sw, y)], fill=(r, g, b, 255))

    # Glow bursts
    # Left burst (Violet)
    for rad in range(350 * scale, 50 * scale, -10 * scale):
        alpha = int(35 * (1 - rad / (350 * scale)))
        draw.ellipse([80 * scale - rad, 160 * scale - rad, 80 * scale + rad, 160 * scale + rad], fill=(139, 92, 246, alpha))

    # Right burst (Rose / Cyan)
    for rad in range(400 * scale, 50 * scale, -10 * scale):
        alpha = int(45 * (1 - rad / (400 * scale)))
        draw.ellipse([800 * scale - rad, 220 * scale - rad, 800 * scale + rad, 220 * scale + rad], fill=(244, 63, 94, alpha))

    # Right Side: Comparison Card 1 (Complete)
    c1_x, c1_y = 550 * scale, 90 * scale
    c1_w, c1_h = 390 * scale, 150 * scale
    draw.rounded_rectangle([c1_x, c1_y, c1_x + c1_w, c1_y + c1_h], radius=16 * scale, fill=(24, 30, 52, 240), outline=(51, 65, 85, 255), width=2 * scale)
    # Circle badge #1
    draw.ellipse([c1_x + 20 * scale, c1_y + 20 * scale, c1_x + 50 * scale, c1_y + 50 * scale], fill=(59, 130, 246, 50), outline=(59, 130, 246, 255), width=2 * scale)
    # Metrics
    draw.rounded_rectangle([c1_x + 20 * scale, c1_y + 75 * scale, c1_x + 125 * scale, c1_y + 125 * scale], radius=8 * scale, fill=(15, 23, 42, 255))
    draw.rounded_rectangle([c1_x + 140 * scale, c1_y + 75 * scale, c1_x + 245 * scale, c1_y + 125 * scale], radius=8 * scale, fill=(15, 23, 42, 255))
    draw.rounded_rectangle([c1_x + 260 * scale, c1_y + 75 * scale, c1_x + 370 * scale, c1_y + 125 * scale], radius=8 * scale, fill=(15, 23, 42, 255))

    # Right Side: Comparison Card 2 (Duplicate Flagged)
    c2_x, c2_y = 580 * scale, 240 * scale
    c2_w, c2_h = 390 * scale, 175 * scale
    draw.rounded_rectangle([c2_x, c2_y, c2_x + c2_w, c2_y + c2_h], radius=16 * scale, fill=(28, 32, 58, 255), outline=(244, 63, 94, 255), width=3 * scale)
    # Duplicate detected pill
    draw.rounded_rectangle([c2_x + 240 * scale, c2_y + 16 * scale, c2_x + 370 * scale, c2_y + 42 * scale], radius=13 * scale, fill=(244, 63, 94, 50), outline=(244, 63, 94, 255), width=2 * scale)
    # Circle badge #2
    draw.ellipse([c2_x + 20 * scale, c2_y + 20 * scale, c2_x + 50 * scale, c2_y + 50 * scale], fill=(239, 68, 68, 50), outline=(239, 68, 68, 255), width=2 * scale)
    # Metrics
    draw.rounded_rectangle([c2_x + 20 * scale, c2_y + 80 * scale, c2_x + 125 * scale, c2_y + 130 * scale], radius=8 * scale, fill=(15, 23, 42, 255))
    draw.rounded_rectangle([c2_x + 140 * scale, c2_y + 80 * scale, c2_x + 245 * scale, c2_y + 130 * scale], radius=8 * scale, fill=(15, 23, 42, 255))
    draw.rounded_rectangle([c2_x + 260 * scale, c2_y + 80 * scale, c2_x + 370 * scale, c2_y + 130 * scale], radius=8 * scale, fill=(15, 23, 42, 255))

    # Downscale smoothly
    final_img = img.resize((width, height), Image.Resampling.LANCZOS)
    return final_img

if __name__ == "__main__":
    print("Generating CasaOS icons and sprites...")
    icon_512 = render_icon(512)
    icon_512.save(os.path.join(ASSETS_DIR, "icon.png"), "PNG")
    print("Created assets/icon.png (512x512)")

    for sz in [256, 128, 64]:
        resized = icon_512.resize((sz, sz), Image.Resampling.LANCZOS)
        resized.save(os.path.join(ASSETS_DIR, f"icon-{sz}.png"), "PNG")
        print(f"Created assets/icon-{sz}.png ({sz}x{sz})")

    banner_img = render_banner(1024, 500)
    banner_img.save(os.path.join(ASSETS_DIR, "banner.png"), "PNG")
    print("Created assets/banner.png (1024x500)")
