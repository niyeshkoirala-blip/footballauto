"""
Creates a 1080x1080 Facebook post image.

Theme: Pitch Side News — deep navy (#0A1634) + bright green (#48B937)

Layout:
  ┌──────────────────────────────┐
  │  Photo — navy gradient       │  ~58 % height
  │                              │
  │  ╭─ CATEGORY PILL ─╮        │  ← green pill
  │  ╭── HEADLINE LINE 1 ──╮    │  ← navy rounded banners
  │  ╭── HEADLINE LINE 2 ──╮    │
  ├══════════════════════════════╡  green separator
  │  Brief description text…     │  ← white text on dark navy
  │  More description text…      │
  │                              │
  │▐▌ PITCH SIDE • NEWS ▐▌      │  ← green + white brand bar
  └──────────────────────────────┘
"""

import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from src.image_fetcher import fetch_story_image

# ── Canvas ─────────────────────────────────────────────────────────────────────
WIDTH       = 1080
HEIGHT      = 1080
PHOTO_H     = 780
BRAND_BAR_H = 80
ACCENT_W    = 7

# ── Brand colours (Pitch Side News) ────────────────────────────────────────────
NAVY        = (10,  22,  52)
NAVY_MID    = (16,  34,  78)
NAVY_LIGHT  = (22,  48, 105)
GREEN       = (72, 185,  55)
GREEN_DARK  = (42, 130,  32)
WHITE       = (255, 255, 255)
OFF_WHITE   = (210, 220, 235)   # blue-tinted white for secondary text
BLACK       = (0,   0,   0)

# ── Fonts ───────────────────────────────────────────────────────────────────────
FONT_BLACK   = "/usr/share/fonts/truetype/lato/Lato-Black.ttf"
FONT_BOLD    = "/usr/share/fonts/truetype/lato/Lato-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/lato/Lato-Regular.ttf"


def _font(size: int, bold: bool = False, black: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        [FONT_BLACK, FONT_BOLD, "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
        if black else
        [FONT_BOLD,  "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
        if bold else
        [FONT_REGULAR, "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]
    )
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ── Image helpers ───────────────────────────────────────────────────────────────

def _crop_center(img: Image.Image, w: int, h: int) -> Image.Image:
    scale = max(w / img.width, h / img.height)
    nw, nh = int(img.width * scale), int(img.height * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - w) // 2
    top  = 0 if img.height > img.width * 1.1 else (nh - h) // 2
    return img.crop((left, top, left + w, top + h))


def _navy_gradient_overlay(img: Image.Image) -> Image.Image:
    """Dark at bottom with a navy tint, stays bright at the top."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)
    h       = img.height
    for y in range(h):
        t = y / h
        if t < 0.30:
            alpha = int(20 * (t / 0.30))
        else:
            alpha = int(20 + 215 * ((t - 0.30) / 0.70))
        # Tint toward navy rather than pure black
        r = int(10  * (alpha / 255))
        g = int(22  * (alpha / 255))
        b = int(52  * (alpha / 255))
        draw.line([(0, y), (img.width - 1, y)],
                  fill=(max(0, r), max(0, g), max(0, b), alpha))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def _pill(draw: ImageDraw.ImageDraw, xy: list, fill, radius: int = 999) -> None:
    x0, y0, x1, y1 = xy
    r = min(radius, (y1 - y0) // 2, (x1 - x0) // 2)
    try:
        draw.rounded_rectangle(xy, radius=r, fill=fill)
    except AttributeError:
        draw.rectangle(xy, fill=fill)


def _wrap(draw: ImageDraw.ImageDraw, text: str,
          font: ImageFont.FreeTypeFont, max_px: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur:   list[str] = []
    for word in words:
        test = " ".join(cur + [word])
        if draw.textlength(test, font=font) <= max_px:
            cur.append(word)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [word]
    if cur:
        lines.append(" ".join(cur))
    return lines


# ── Decorative helpers ──────────────────────────────────────────────────────────

def _draw_pitch_lines(draw: ImageDraw.ImageDraw, x: int, y: int,
                      size: int, color, alpha_img: Image.Image) -> None:
    """Draw a tiny football pitch icon."""
    # outer circle
    draw.ellipse([x - size, y - size, x + size, y + size],
                 outline=color, width=2)
    # centre dot
    draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=color)
    # horizontal midline
    draw.line([(x - size, y), (x + size, y)], fill=color, width=2)


def _draw_brand_bar(draw: ImageDraw.ImageDraw, canvas: Image.Image,
                    bar_top: int, page_name: str) -> None:
    """
    Two-tone brand bar:
      left half → dark navy
      separator → bright green vertical stripe
      full bar  → navy
    Text: 'PITCH SIDE' in white + 'NEWS' in green, centred.
    """
    # Background
    draw.rectangle([0, bar_top, WIDTH, HEIGHT], fill=NAVY)

    # Green top border line
    draw.rectangle([0, bar_top, WIDTH, bar_top + 4], fill=GREEN)

    # Split page_name into parts to colour "NEWS" green
    name_upper = page_name.upper()
    font_brand = _font(38, bold=True)

    # Render whole name white first, then overwrite "NEWS" in green
    parts = name_upper.split()
    coloured = []
    for part in parts:
        if part in ("NEWS", "FC", "SIDE"):
            coloured.append((part, GREEN))
        else:
            coloured.append((part, WHITE))

    # Measure total width
    space_w = int(draw.textlength(" ", font=font_brand))
    total_w = sum(int(draw.textlength(p, font=font_brand)) for p, _ in coloured) \
              + space_w * (len(coloured) - 1)

    text_y = bar_top + (BRAND_BAR_H - font_brand.size) // 2

    # Draw green accent chevrons
    cx = (WIDTH - total_w) // 2 - 36
    for offset in (0, 10):
        for yi in range(4):
            draw.line([
                (cx - 8 + offset, text_y + yi * 9),
                (cx      + offset, text_y + yi * 9 + 4),
                (cx - 8 + offset, text_y + yi * 9 + 8),
            ], fill=GREEN, width=2)

    cx2 = (WIDTH + total_w) // 2 + 18
    for offset in (0, 10):
        for yi in range(4):
            draw.line([
                (cx2 + 8 - offset, text_y + yi * 9),
                (cx2     - offset, text_y + yi * 9 + 4),
                (cx2 + 8 - offset, text_y + yi * 9 + 8),
            ], fill=GREEN, width=2)

    # Draw each word
    cur_x = (WIDTH - total_w) // 2
    for i, (part, color) in enumerate(coloured):
        draw.text((cur_x, text_y), part, fill=color, font=font_brand)
        cur_x += int(draw.textlength(part, font=font_brand))
        if i < len(coloured) - 1:
            cur_x += space_w


# ── Public API ──────────────────────────────────────────────────────────────────

def create_post_image(
    title:          str,
    brief_text:     str,
    category:       str,
    story:          dict,
    pexels_api_key: str = "",
    page_name:      str = "PITCH SIDE News",
) -> Image.Image:

    # 1. Background photo ────────────────────────────────────────────────────────
    bg_src = fetch_story_image(story, pexels_api_key)
    if bg_src is None:
        bg_src = Image.new("RGB", (WIDTH, PHOTO_H), (20, 60, 20))

    bg = _navy_gradient_overlay(_crop_center(bg_src, WIDTH, PHOTO_H))

    # 2. Canvas — dark navy base ─────────────────────────────────────────────────
    canvas = Image.new("RGB", (WIDTH, HEIGHT), NAVY)
    canvas.paste(bg, (0, 0))
    draw = ImageDraw.Draw(canvas)

    MARGIN = 54
    MAX_W  = WIDTH - MARGIN * 2

    # 3. Headline banners (overlaid on photo) ────────────────────────────────────
    h_font  = _font(52, black=True)
    H_PH, H_PV = 24, 13

    headline_lines = _wrap(draw, title, h_font, MAX_W - H_PH * 2)[:3]
    line_h         = h_font.size + H_PV * 2 + 8

    cat_font  = _font(26, bold=True)
    CAT_PH, CAT_PV = 22, 10
    cat_text  = f"● {category.upper()}"
    cat_w     = int(draw.textlength(cat_text, font=cat_font))
    cat_box_h = cat_font.size + CAT_PV * 2

    gap = 16
    total_h = cat_box_h + gap + line_h * len(headline_lines)

    overlay_top = PHOTO_H - total_h - 22

    # Category pill — bright green, fully rounded
    cat_y = overlay_top
    _pill(draw,
          [MARGIN, cat_y, MARGIN + cat_w + CAT_PH * 2, cat_y + cat_box_h],
          fill=GREEN)
    draw.text((MARGIN + CAT_PH, cat_y + CAT_PV), cat_text, fill=WHITE, font=cat_font)

    # Headline banners — deep navy, heavily rounded
    current_y = cat_y + cat_box_h + gap
    for i, line in enumerate(headline_lines):
        lw    = int(draw.textlength(line, font=h_font))
        lh    = h_font.size
        color = NAVY if i % 2 == 0 else NAVY_MID
        _pill(draw,
              [MARGIN, current_y, MARGIN + lw + H_PH * 2, current_y + lh + H_PV * 2],
              fill=color, radius=28)
        # Subtle green left edge accent on banner
        draw.rectangle(
            [MARGIN, current_y + 6, MARGIN + 5, current_y + lh + H_PV * 2 - 6],
            fill=GREEN,
        )
        draw.text((MARGIN + H_PH, current_y + H_PV), line, fill=WHITE, font=h_font)
        current_y += lh + H_PV * 2 + 8

    # 4. Green separator ─────────────────────────────────────────────────────────
    draw.rectangle([0, PHOTO_H, WIDTH, PHOTO_H + 5], fill=GREEN)

    # Left green accent strip
    draw.rectangle([0, PHOTO_H + 5, ACCENT_W, HEIGHT - BRAND_BAR_H], fill=GREEN)

    # 5. Brief description ───────────────────────────────────────────────────────
    d_font   = _font(33)
    d_line_h = d_font.size + 12
    desc_x   = MARGIN + 4
    desc_y   = PHOTO_H + 36

    for line in _wrap(draw, brief_text, d_font, MAX_W - 4)[:4]:
        draw.text((desc_x, desc_y), line, fill=OFF_WHITE, font=d_font)
        desc_y += d_line_h

    # 6. Brand bar ───────────────────────────────────────────────────────────────
    bar_top = HEIGHT - BRAND_BAR_H
    _draw_brand_bar(draw, canvas, bar_top, page_name)

    return canvas


def save_image(img: Image.Image, path: str) -> None:
    img.save(path, format="JPEG", quality=95, optimize=True)
