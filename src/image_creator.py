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
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from src.image_fetcher import fetch_story_image

# ── Canvas ─────────────────────────────────────────────────────────────────────
WIDTH   = 1080
HEIGHT  = 1350
PAD_X   = 44
PAD_TOP = 36
PAD_BOT = 40

# The photo is the flexible element: its height is whatever is left once the
# brief and the footer have taken theirs, so the canvas is always full. A fixed
# PHOTO_H left ~420 px of dead navy under a short brief.
PHOTO_H_MIN = 700          # never let a very long brief squash the photo
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

def _fit_contain(img: Image.Image, w: int, h: int) -> Image.Image:
    """Fit the complete source inside the photo area without crop or distortion."""
    if img.width <= 0 or img.height <= 0:
        return Image.new("RGB", (w, h), NAVY)

    scale = min(w / img.width, h / img.height)
    nw = max(1, round(img.width * scale))
    nh = max(1, round(img.height * scale))
    resized = img.convert("RGB").resize((nw, nh), Image.Resampling.LANCZOS)
    contained = Image.new("RGB", (w, h), NAVY)
    contained.paste(resized, ((w - nw) // 2, (h - nh) // 2))
    return contained


def _cover_blurred(img: Image.Image, w: int, h: int) -> Image.Image:
    """Create a blurred cover background; only this supporting layer may crop."""
    scale = max(w / img.width, h / img.height)
    nw = max(w, round(img.width * scale))
    nh = max(h, round(img.height * scale))
    resized = img.convert("RGB").resize((nw, nh), Image.Resampling.LANCZOS)
    left, top = (nw - w) // 2, (nh - h) // 2
    cropped = resized.crop((left, top, left + w, top + h))
    return cropped.filter(ImageFilter.GaussianBlur(radius=max(14, round(min(w, h) * 0.025))))


def _feathered_contain(img: Image.Image, w: int, h: int,
                       fade_top: bool = False) -> Image.Image:
    """Layer a complete sharp source over its blurred cover with soft edges."""
    scale = min(w / img.width, h / img.height)
    nw = max(1, round(img.width * scale))
    nh = max(1, round(img.height * scale))
    left = (w - nw) // 2
    top = (h - nh) // 2
    sharp = img.convert("RGB").resize((nw, nh), Image.Resampling.LANCZOS)
    background = _cover_blurred(img, w, h)

    mask = Image.new("L", (w, h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rectangle((left, top, left + nw - 1, top + nh - 1), fill=255)
    side_background = w - nw
    feather = min(round(nw * 0.12), max(18, round(side_background * 0.20)))
    if side_background:
        for x in range(left, min(w, left + feather)):
            mask_draw.line((x, top, x, top + nh - 1),
                           fill=round(255 * (x - left) / max(1, feather)))
        for x in range(max(0, left + nw - feather), left + nw):
            mask_draw.line((x, top, x, top + nh - 1),
                           fill=round(255 * (left + nw - x) / max(1, feather)))

    if fade_top:
        top_feather = max(24, round(nh * 0.22))
        for y in range(top, min(h, top + top_feather)):
            mask_draw.line((left, y, left + nw - 1, y),
                           fill=round(255 * (y - top) / max(1, top_feather)))

    foreground = Image.new("RGB", (w, h), NAVY)
    foreground.paste(sharp, (left, top))
    return Image.composite(foreground, background, mask)


def _scrim(img: Image.Image, fade_top: bool = False,
        content_top: int = 0, fade_sides: bool = False,
        content_left: int = 0, content_width: int | None = None) -> Image.Image:
    """Fade the lower edge and conditionally fade source-facing edges."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)
    h       = img.height
    content_width = content_width or img.width
    content_right = content_left + content_width - 1
    side_fade_width = max(1, round(content_width * 0.22))
    for y in range(h):
        t = y / (h - 1)
        top_fade_end = content_top + round((h - content_top * 2) * 0.22)
        if fade_top and content_top <= y <= top_fade_end:
            a = 0.85 * (1 - (y - content_top) / max(1, top_fade_end - content_top))
        elif t <= 0.45:
            a = 0.0
        elif t <= 0.88:
            a = 0.85 * (t - 0.45) / 0.43
        else:
            a = 0.85 + 0.15 * (t - 0.88) / 0.12
        for x in range(img.width):
            side_a = 0.0
            if fade_sides and content_left - side_fade_width <= x <= content_left:
                side_a = 0.85 * (x - content_left + side_fade_width) / side_fade_width
            elif fade_sides and content_right <= x <= content_right + side_fade_width:
                side_a = 0.85 * (content_right + side_fade_width - x) / side_fade_width
            draw.point((x, y), fill=NAVY + (int(max(a, side_a) * 255),))
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

    canvas = Image.new("RGB", (WIDTH, HEIGHT), NAVY)
    draw   = ImageDraw.Draw(canvas)

    # 1. Measure the brief first — the photo gets whatever height is left ───────
    d_font   = _body(26, "Medium")
    d_line_h = round(26 * 1.5)
    d_x      = PAD_X + 5 + 20
    d_lines  = _wrap(draw, brief_text, d_font, WIDTH - d_x - PAD_X)[:6]
    brief_h  = d_line_h * len(d_lines)
    photo_h  = max(PHOTO_H_MIN,
                   HEIGHT - FOOTER_H - BRIEF_GAP - brief_h - PAD_TOP)

    # 2. Photo + scrim ──────────────────────────────────────────────────────────
    bg_src = fetch_story_image(story, pexels_api_key)
    if bg_src is None:
        bg_src = Image.new("RGB", (WIDTH, photo_h), (20, 60, 20))
    contained_bg = _feathered_contain(bg_src, WIDTH, photo_h,
                                      fade_top=bg_src.width > bg_src.height)
    scale = min(WIDTH / bg_src.width, photo_h / bg_src.height)
    content_width = round(bg_src.width * scale)
    content_top = (photo_h - round(bg_src.height * scale)) // 2
    content_left = (WIDTH - content_width) // 2
    canvas.paste(_scrim(
        contained_bg,
        fade_top=False,
        content_top=content_top,
        fade_sides=False,
    ), (0, 0))

    # 3. Category pill — top-left, green on navy text ───────────────────────────
    cat_font = _body(20, "ExtraBold")
    cat_text = category.upper()
    cat_w    = draw.textlength(cat_text, font=cat_font)
    pill     = [PAD_X, 44, PAD_X + 18 + 10 + 10 + cat_w + 22, 44 + 11 + 20 + 11]
    draw.rounded_rectangle(pill, radius=(pill[3] - pill[1]) / 2, fill=GREEN)
    dot_cx, dot_cy = PAD_X + 18 + 5, (pill[1] + pill[3]) / 2
    draw.ellipse([dot_cx - 5, dot_cy - 5, dot_cx + 5, dot_cy + 5], fill=NAVY)
    _draw_lines(draw, int(PAD_X + 18 + 10 + 10), int(pill[1] + 11),
                [cat_text], cat_font, 20, NAVY)

    # 4. Headline — Caprasimo, sitting on the bottom of the photo ───────────────
    h_font   = _display(56)
    h_line_h = round(56 * 1.12)
    h_lines  = _wrap(draw, title, h_font, WIDTH - PAD_X * 2)[:4]
    _draw_lines(draw, PAD_X, photo_h - 36 - h_line_h * len(h_lines),
                h_lines, h_font, h_line_h, WHITE)

    # 5. Brief description — green rule + body copy (measured in step 1) ────────
    d_top = photo_h + PAD_TOP
    draw.rounded_rectangle(
        [PAD_X, d_top, PAD_X + 5, d_top + d_line_h * len(d_lines)],
        radius=3, fill=GREEN,
    )
    _draw_lines(draw, d_x, d_top, d_lines, d_font, d_line_h, BODY)

    # 6. Brand line — centred above the bottom padding ──────────────────────────
    b_font   = _display(26)
    b_line_h = 36
    b_top    = HEIGHT - PAD_BOT - b_line_h
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
    """Renders with no network image and checks the canvas has no dead band.

    The bug this guards: PHOTO_H was fixed, so a short brief left ~420 px of
    empty navy between the brief and the footer. The photo now flexes, so the
    band just above the footer rule must always be photo, never bare navy.
    """
    short = "Two lines of brief copy, the common case for a BBC summary line."
    long  = ("A far longer brief that wraps to five or six lines so the photo "
             "has to give up height to make room for it, which is the other end "
             "of the range and the case that used to overflow the footer rule "
             "instead of leaving a gap above it, both of which look broken.")

    for name, brief in (("short", short), ("long", long)):
        img = create_post_image(
            title      = "'Best host in the world': Mexico keep spirits up after England heartbreak",
            brief_text = brief,
            category   = "International",
            story      = {"title": "", "description": ""},
        )
        assert img.size == (WIDTH, HEIGHT), img.size
        assert img.getpixel((5, HEIGHT - 5)) == NAVY, "bottom band should be navy"

        # Walk up from the footer rule: the first non-navy row is the photo
        # bottom. A fixed PHOTO_H put it ~420 px up; it should now be snug.
        rule_y = HEIGHT - PAD_BOT - 36 - 32
        y = rule_y - 1
        while y > 0 and img.getpixel((WIDTH // 2, y)) == NAVY:
            y -= 1
        gap = rule_y - y
        assert gap < 320, f"{name}: {gap}px of dead space above the footer"
        print(f"  {name} brief → photo bottom {gap}px above the rule")

    save_image(img, "design_check.jpg")
    print("ok → design_check.jpg")


if __name__ == "__main__":
    _demo()
