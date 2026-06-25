"""
Creates a 1080x1080 Facebook post image.

Layout:
  ┌──────────────────────────────┐
  │  Photo — gradient overlay    │  ~57 % height
  │  (lighter top, dark bottom)  │
  │                              │
  │  [// CATEGORY]  ← overlaid  │
  │  ████ HEADLINE LINE 1 ████   │  ← overlaid crimson banners
  │  ████ HEADLINE LINE 2 ████   │
  ├══════════════════════════════┤  crimson 6px separator
  │▌ Brief description text…     │  left accent strip
  │▌ More description text…      │
  │                              │
  │████████ [ PAGE NAME ] ███████│  full crimson brand bar
  └──────────────────────────────┘
"""

import os
from PIL import Image, ImageDraw, ImageFont

from src.image_fetcher import fetch_story_image

# ── Canvas constants ───────────────────────────────────────────────────────────
WIDTH        = 1080
HEIGHT       = 1080
PHOTO_H      = 620     # photo section (~57 %) — bigger than before
BRAND_BAR_H  = 68      # full-width crimson bar at very bottom
ACCENT_W     = 8       # left crimson accent strip in text section

CRIMSON      = (185,  12,  35)
DARK_CRIMSON = (115,   5,  20)
WHITE        = (255, 255, 255)
BLACK        = (18,  18,  18)
WARM_WHITE   = (244, 241, 241)   # warmer off-white for text section

FONT_BLACK   = "/usr/share/fonts/truetype/lato/Lato-Black.ttf"
FONT_BOLD    = "/usr/share/fonts/truetype/lato/Lato-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/lato/Lato-Regular.ttf"


# ── Font helper ────────────────────────────────────────────────────────────────

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


# ── Image crop helpers ─────────────────────────────────────────────────────────

def _crop_for_photo_section(img: Image.Image) -> Image.Image:
    w, h = WIDTH, PHOTO_H
    scale = max(w / img.width, h / img.height)
    new_w = int(img.width  * scale)
    new_h = int(img.height * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w) // 2
    is_portrait = img.height > img.width * 1.1
    top = 0 if is_portrait else (new_h - h) // 2
    return img.crop((left, top, left + w, top + h))


def _gradient_overlay(img: Image.Image) -> Image.Image:
    """
    Cinematic gradient: very light at the top, progressively darker toward
    the bottom so overlaid headline text is always readable.
    """
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)
    h       = img.height
    for y in range(h):
        t = y / h
        if t < 0.35:
            alpha = int(30 * (t / 0.35))          # 0 → 30  (top stays bright)
        else:
            alpha = int(30 + 200 * ((t - 0.35) / 0.65))  # 30 → 230 (bottom darkens)
        draw.line([(0, y), (img.width - 1, y)], fill=(0, 0, 0, alpha))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


# ── Drawing helpers ────────────────────────────────────────────────────────────

def _rounded_rect(draw: ImageDraw.ImageDraw, xy: list, radius: int, fill) -> None:
    try:
        draw.rounded_rectangle(xy, radius=radius, fill=fill)
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


# ── Public API ─────────────────────────────────────────────────────────────────

def create_post_image(
    title:          str,
    brief_text:     str,
    category:       str,
    story:          dict,
    pexels_api_key: str = "",
    page_name:      str = "FOOTBALL NEWS",
) -> Image.Image:

    # ── 1. Background photo ────────────────────────────────────────────────────
    bg_src = fetch_story_image(story, pexels_api_key)
    if bg_src is None:
        bg_src = Image.new("RGB", (WIDTH, PHOTO_H), (18, 90, 35))

    bg = _gradient_overlay(_crop_for_photo_section(bg_src))

    # ── 2. Canvas — warm off-white base ───────────────────────────────────────
    canvas = Image.new("RGB", (WIDTH, HEIGHT), WARM_WHITE)
    canvas.paste(bg, (0, 0))
    draw = ImageDraw.Draw(canvas)

    MARGIN = 56
    MAX_W  = WIDTH - MARGIN * 2

    # ── 3. Overlay: category pill on the photo ────────────────────────────────
    #    Work bottom-up: measure how much space the headlines need, then place
    #    the category pill above them, all sitting on the photo.

    h_font  = _font(50, black=True)
    H_PH, H_PV = 22, 14

    headline_lines = _wrap(draw, title, h_font, MAX_W - H_PH * 2)[:3]
    line_h         = h_font.size + H_PV * 2 + 6   # height of one banner row

    cat_font   = _font(28, bold=True)
    CAT_PH, CAT_PV = 20, 9
    cat_text   = f"// {category.upper()}"
    cat_w      = int(draw.textlength(cat_text, font=cat_font))
    cat_box_h  = cat_font.size + CAT_PV * 2

    gap_cat_headline = 14
    total_overlay_h  = cat_box_h + gap_cat_headline + line_h * len(headline_lines)

    # Anchor so the last headline ends 18px above the separator
    overlay_top = PHOTO_H - total_overlay_h - 18

    # Category pill
    cat_y = overlay_top
    _rounded_rect(
        draw,
        [MARGIN, cat_y, MARGIN + cat_w + CAT_PH * 2, cat_y + cat_box_h],
        radius=5,
        fill=CRIMSON,
    )
    draw.text((MARGIN + CAT_PH, cat_y + CAT_PV), cat_text, fill=WHITE, font=cat_font)

    # Headline banners (overlaid on photo)
    current_y = cat_y + cat_box_h + gap_cat_headline
    for i, line in enumerate(headline_lines):
        lw    = int(draw.textlength(line, font=h_font))
        lh    = h_font.size
        color = CRIMSON if i % 2 == 0 else DARK_CRIMSON
        _rounded_rect(
            draw,
            [MARGIN, current_y, MARGIN + lw + H_PH * 2, current_y + lh + H_PV * 2],
            radius=4,
            fill=color,
        )
        draw.text((MARGIN + H_PH, current_y + H_PV), line, fill=WHITE, font=h_font)
        current_y += lh + H_PV * 2 + 6

    # ── 4. Crimson separator + left accent strip ───────────────────────────────
    draw.rectangle([0, PHOTO_H, WIDTH, PHOTO_H + 6], fill=CRIMSON)
    # Left accent strip runs from separator to top of brand bar
    draw.rectangle(
        [0, PHOTO_H + 6, ACCENT_W, HEIGHT - BRAND_BAR_H],
        fill=CRIMSON,
    )

    # ── 5. Brief description ───────────────────────────────────────────────────
    d_font      = _font(34)
    d_line_h    = d_font.size + 11
    desc_x      = MARGIN + 4          # slightly indented from accent strip
    desc_y      = PHOTO_H + 38

    for line in _wrap(draw, brief_text, d_font, MAX_W - 4)[:4]:
        draw.text((desc_x, desc_y), line, fill=BLACK, font=d_font)
        desc_y += d_line_h

    # ── 6. Full-width crimson brand bar ───────────────────────────────────────
    bar_top = HEIGHT - BRAND_BAR_H
    draw.rectangle([0, bar_top, WIDTH, HEIGHT], fill=CRIMSON)

    brand_font = _font(34, bold=True)
    brand_text = page_name.upper()
    brand_w    = int(draw.textlength(brand_text, font=brand_font))
    brand_y    = bar_top + (BRAND_BAR_H - brand_font.size) // 2
    draw.text(((WIDTH - brand_w) // 2, brand_y), brand_text, fill=WHITE, font=brand_font)

    # Small decorative dots flanking the brand name
    dot_y  = bar_top + BRAND_BAR_H // 2
    dot_x1 = (WIDTH - brand_w) // 2 - 28
    dot_x2 = (WIDTH + brand_w) // 2 + 18
    for dx, size in [(dot_x1, 6), (dot_x1 - 14, 4), (dot_x2, 6), (dot_x2 + 14, 4)]:
        draw.ellipse([dx - size, dot_y - size, dx + size, dot_y + size], fill=WHITE)

    return canvas


def save_image(img: Image.Image, path: str) -> None:
    img.save(path, format="JPEG", quality=95, optimize=True)
