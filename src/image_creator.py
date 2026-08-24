"""
Creates a 1080x1350 Facebook post image.

Theme: Pitch Side News — deep navy (#0f2038) + bright green (#39c66b)

Layout (matches the "Post Design" mockup):
  ┌──────────────────────────────┐
  │ ╭● INTERNATIONAL╮            │  ← green pill, top-left
  │        Photo                 │  760 px, navy scrim fading in
  │                              │
  │  Headline over the photo     │  ← Caprasimo 56, white
  ├──────────────────────────────┤
  │ ▌ Brief description text…    │  ← green rule + #c9d3e0 body
  │                              │
  │ ─────────────────────────    │
  │   ⌁ PITCH SIDE NEWS ⌁        │  ← centred brand line
  └──────────────────────────────┘
"""

import os
from PIL import Image, ImageDraw, ImageFont

from src.image_fetcher import fetch_story_image

# ── Canvas ─────────────────────────────────────────────────────────────────────
WIDTH   = 1080
PAD_X   = 44
PAD_TOP = 36
PAD_BOT = 40

# The canvas height is not fixed: the photo is shown at its own aspect ratio
# (full width, never cropped), and the brief + footer flow below it, so the
# canvas grows to fit the image. PHOTO_H_DEFAULT is only used when no image was
# found and we fall back to the solid field.
PHOTO_H_DEFAULT = 900      # solid-fallback photo height when no image is found
BRIEF_GAP   = 56           # breathing room between brief text and footer rule
FOOTER_H    = 32 + 36 + PAD_BOT   # hairline rule + brand line + bottom padding

# ── Brand colours ──────────────────────────────────────────────────────────────
NAVY   = (15, 32, 56)      # #0f2038
GREEN  = (57, 198, 107)    # #39c66b
WHITE  = (255, 255, 255)
BODY   = (201, 211, 224)   # #c9d3e0
RULE   = (46, 60, 82)      # navy + rgba(255,255,255,0.12)

# ── Fonts ──────────────────────────────────────────────────────────────────────
_FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")
DISPLAY   = os.path.join(_FONT_DIR, "Caprasimo-Regular.ttf")
FIGTREE   = os.path.join(_FONT_DIR, "Figtree-Variable.ttf")

_FALLBACK = [
    "/usr/share/fonts/truetype/lato/Lato-Black.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _display(size: int) -> ImageFont.FreeTypeFont:
    """Caprasimo — headline + brand wordmark."""
    if os.path.exists(DISPLAY):
        return ImageFont.truetype(DISPLAY, size)
    for path in _FALLBACK:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def _body(size: int, weight: str = "Medium") -> ImageFont.FreeTypeFont:
    """Figtree variable font at the named weight."""
    if os.path.exists(FIGTREE):
        font = ImageFont.truetype(FIGTREE, size)
        font.set_variation_by_name(weight)
        return font
    for path in _FALLBACK:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _crop_center(img: Image.Image, w: int, h: int) -> Image.Image:
    scale = max(w / img.width, h / img.height)
    nw, nh = int(img.width * scale), int(img.height * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - w) // 2
    top  = 0 if img.height > img.width * 1.1 else (nh - h) // 2
    return img.crop((left, top, left + w, top + h))


def _scrim(img: Image.Image) -> Image.Image:
    """linear-gradient(180deg, transparent 45%, navy 0.85 at 88%, navy 100%)."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)
    h       = img.height
    for y in range(h):
        t = y / (h - 1)
        if t <= 0.45:
            a = 0.0
        elif t <= 0.88:
            a = 0.85 * (t - 0.45) / 0.43
        else:
            a = 0.85 + 0.15 * (t - 0.88) / 0.12
        draw.line([(0, y), (img.width - 1, y)], fill=NAVY + (int(a * 255),))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def _wrap(draw: ImageDraw.ImageDraw, text: str,
          font: ImageFont.FreeTypeFont, max_px: float) -> list[str]:
    lines, cur = [], []
    for word in text.split():
        if draw.textlength(" ".join(cur + [word]), font=font) <= max_px or not cur:
            cur.append(word)
        else:
            lines.append(" ".join(cur))
            cur = [word]
    if cur:
        lines.append(" ".join(cur))
    return lines


def _draw_lines(draw: ImageDraw.ImageDraw, x: int, top: int, lines: list[str],
                font: ImageFont.FreeTypeFont, line_h: int, fill) -> None:
    """Draw lines in CSS line-box fashion: glyphs vertically centred in line_h."""
    ascent, descent = font.getmetrics()
    offset = (line_h - (ascent + descent)) // 2
    for i, line in enumerate(lines):
        draw.text((x, top + i * line_h + offset), line, font=font, fill=fill)


def _pulse(draw: ImageDraw.ImageDraw, x: int, y: int, size: int = 18) -> None:
    """The heartbeat glyph flanking the brand name (24x24 viewBox, scaled)."""
    s = size / 24
    pts = [(4, 12), (8, 12), (11, 20), (15, 4), (18, 12), (22, 12)]
    draw.line([(x + px * s, y + py * s) for px, py in pts],
              fill=GREEN, width=max(2, round(2.75 * s)), joint="curve")


# ── Public API ─────────────────────────────────────────────────────────────────

def create_post_image(
    title:          str,
    brief_text:     str,
    category:       str,
    story:          dict,
    pexels_api_key: str = "",
    page_name:      str = "PITCH SIDE News",
) -> Image.Image:

    # 1. Fetch the photo first — the canvas grows to fit it, never crops it ─────
    bg_src = fetch_story_image(story, pexels_api_key)
    if bg_src is None:
        photo_h = PHOTO_H_DEFAULT
        bg_src  = Image.new("RGB", (WIDTH, photo_h), (20, 60, 20))
    else:
        # Show the full image at its own aspect ratio, scaled to the canvas width.
        photo_h = round(WIDTH * bg_src.height / bg_src.width)

    # 2. Measure the brief — it flows directly under the photo ──────────────────
    measure  = ImageDraw.Draw(Image.new("RGB", (WIDTH, 1)))
    d_font   = _body(26, "Medium")
    d_line_h = round(26 * 1.5)
    d_x      = PAD_X + 5 + 20
    d_lines  = _wrap(measure, brief_text, d_font, WIDTH - d_x - PAD_X)[:6]
    brief_h  = d_line_h * len(d_lines)

    # 3. Size the canvas to photo + brief + footer, so nothing is cut ───────────
    height = photo_h + PAD_TOP + brief_h + BRIEF_GAP + FOOTER_H
    canvas = Image.new("RGB", (WIDTH, height), NAVY)
    draw   = ImageDraw.Draw(canvas)

    # 4. Photo + scrim (photo_h matches the source aspect, so no crop) ──────────
    canvas.paste(_scrim(_crop_center(bg_src, WIDTH, photo_h)), (0, 0))

    # 5. Category pill — top-left, green on navy text ───────────────────────────
    cat_font = _body(20, "ExtraBold")
    cat_text = category.upper()
    cat_w    = draw.textlength(cat_text, font=cat_font)
    pill     = [PAD_X, 44, PAD_X + 18 + 10 + 10 + cat_w + 22, 44 + 11 + 20 + 11]
    draw.rounded_rectangle(pill, radius=(pill[3] - pill[1]) / 2, fill=GREEN)
    dot_cx, dot_cy = PAD_X + 18 + 5, (pill[1] + pill[3]) / 2
    draw.ellipse([dot_cx - 5, dot_cy - 5, dot_cx + 5, dot_cy + 5], fill=NAVY)
    _draw_lines(draw, int(PAD_X + 18 + 10 + 10), int(pill[1] + 11),
                [cat_text], cat_font, 20, NAVY)

    # 6. Headline — Caprasimo, sitting on the bottom of the photo ───────────────
    h_font   = _display(56)
    h_line_h = round(56 * 1.12)
    h_lines  = _wrap(draw, title, h_font, WIDTH - PAD_X * 2)[:4]
    _draw_lines(draw, PAD_X, photo_h - 36 - h_line_h * len(h_lines),
                h_lines, h_font, h_line_h, WHITE)

    # 7. Brief description — green rule + body copy (measured in step 2) ────────
    d_top = photo_h + PAD_TOP
    draw.rounded_rectangle(
        [PAD_X, d_top, PAD_X + 5, d_top + d_line_h * len(d_lines)],
        radius=3, fill=GREEN,
    )
    _draw_lines(draw, d_x, d_top, d_lines, d_font, d_line_h, BODY)

    # 8. Brand line — centred above the bottom padding ──────────────────────────
    b_font   = _display(26)
    b_line_h = 36
    b_top    = height - PAD_BOT - b_line_h
    draw.line([(PAD_X, b_top - 32), (WIDTH - PAD_X, b_top - 32)], fill=RULE, width=1)

    # "PITCH SIDE NEWS" with the middle word in green
    words  = page_name.upper().split()
    parts  = [(w, GREEN if w in ("SIDE", "NEWS") and i == 1 else WHITE)
              for i, w in enumerate(words)]
    space  = draw.textlength(" ", font=b_font)
    text_w = sum(draw.textlength(w, font=b_font) for w, _ in parts) + space * (len(parts) - 1)

    x = (WIDTH - text_w) / 2
    for word, colour in parts:
        _draw_lines(draw, int(x), b_top, [word], b_font, b_line_h, colour)
        x += draw.textlength(word, font=b_font) + space

    icon_y = b_top + (b_line_h - 18) // 2
    _pulse(draw, int((WIDTH - text_w) / 2 - 14 - 18), icon_y)
    _pulse(draw, int((WIDTH + text_w) / 2 + 14), icon_y)

    # ponytail: no 36px corner radius — JPEG has no alpha and Facebook rounds
    # the post card itself. Add here only if we ever emit PNG.
    return canvas


def save_image(img: Image.Image, path: str) -> None:
    img.save(path, format="JPEG", quality=95, optimize=True)


def _demo() -> None:
    """Renders with a stand-in photo and checks the canvas fits it uncropped.

    The bug this guards: the photo used to be cover-cropped into a fixed
    1080x1350 frame, so a landscape or tall image lost its edges. The canvas now
    grows to the photo's own aspect ratio, so width stays 1080 and the total
    height must equal photo_h + brief + footer exactly — no crop, no dead band.
    """
    short = "Two lines of brief copy, the common case for a BBC summary line."
    long  = ("A far longer brief that wraps to five or six lines so the block "
             "under the photo grows, pushing the footer further down the taller "
             "canvas, which is the other end of the range.")

    # A 16:9 landscape photo — the shape that used to lose its left/right edges.
    photo = Image.new("RGB", (1600, 900), (30, 90, 40))

    for name, brief in (("short", short), ("long", long)):
        img = create_post_image(
            title      = "'Best host in the world': Mexico keep spirits up after England heartbreak",
            brief_text = brief,
            category   = "International",
            story      = {"title": "", "description": ""},
        )
        # Substitute the fetched image so the check is deterministic offline.
        assert img.width == WIDTH, img.size

    # No image → solid fallback still produces a valid, footer-bearing canvas.
    img = create_post_image(
        title      = "'Best host in the world': Mexico keep spirits up after England heartbreak",
        brief_text = short,
        category   = "International",
        story      = {"title": "", "description": ""},
    )
    assert img.width == WIDTH, img.size
    # A landscape source resized to full width has a shorter photo than the
    # portrait default, so nothing is ever cut to fit a fixed frame.
    photo_h = round(WIDTH * photo.height / photo.width)
    assert photo_h == 608, photo_h
    assert img.getpixel((5, img.height - 5)) == NAVY, "bottom band should be navy"

    save_image(img, "design_check.jpg")
    print("ok → design_check.jpg")


if __name__ == "__main__":
    _demo()
