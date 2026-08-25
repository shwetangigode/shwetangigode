#!/usr/bin/env python3
"""
generate_terminal_card.py
--------------------------------
Generates `terminal-card.svg`: a macOS-style terminal window containing
dense ASCII art, revealed row-by-row with a sweeping cursor, followed by
a `$ whoami` typewriter footer.

Three image sources, in order of precedence:
  1. --static           Never touches the network or any photo. Always
                         renders the same deterministic, non-photographic
                         cyberpunk avatar glyph. Safest option -- nothing
                         personally identifying is derived or published.
  2. --local-image PATH Use a local photo (auto-cropped + contrast-boosted).
  3. (default)           Fetch the user's public GitHub avatar.

Pipeline (for either photo source):
  1. Convert to a grayscale luminance grid with Pillow.
  2. Map luminance -> ASCII character density ramp (dark -> dense glyph).
  3. Emit each row as SVG <text>, clipped by an animated <clipPath>
     rect whose width grows left-to-right (the "typing" reveal), with
     a bright cursor block riding the same edge via synced SMIL.
  4. Footer: `$ whoami` types out, then the resolved display name
     appears, then a blinking cursor.

Pure SMIL only -- no CSS animations, no JS. Self-contained SVG.
"""

from __future__ import annotations

import argparse
import io
import os
import random
from typing import List, Optional

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageOps

# --------------------------------------------------------------------------
# ASCII conversion settings
# --------------------------------------------------------------------------
# Dense -> sparse luminance ramp (dark pixel -> dense glyph).
RAMP = "@%#*+=-:. "
COLS = 46
# Terminal monospace cells are taller than wide; correct the sample grid
# so the art doesn't look squashed.
CHAR_ASPECT = 0.52


def crop_to_square(img: Image.Image, vertical_bias: float = 0.28) -> Image.Image:
    """Center-crop a portrait/landscape photo to a square.

    `vertical_bias` controls where the crop window sits vertically for
    portrait photos: 0.0 = anchored to the top of the image, 1.0 =
    anchored to the bottom, 0.5 = dead center. A small bias (~0.25-0.3)
    keeps headroom above the face while still including the shoulders,
    which reads better once turned into a square ASCII avatar than a
    pure center crop.
    """
    w, h = img.size
    side = min(w, h)
    if w >= h:
        x0 = int((w - side) * 0.5)
        y0 = int((h - side) * 0.5)
    else:
        x0 = int((w - side) * 0.5)
        y0 = int((h - side) * vertical_bias)
    return img.crop((x0, y0, x0 + side, y0 + side))


def load_local_image(path: str, size: int = 400, vertical_bias: float = 0.28,
                      zoom: float = 1.0) -> Image.Image:
    """Load a local photo, square-crop it, boost contrast, and convert
    to grayscale for the ASCII pipeline.

    `zoom` (0 < zoom <= 1) keeps only the centered `zoom` fraction of the
    square crop, e.g. 0.8 trims 20% off each edge -- handy for cropping
    out a busy background (like an office ceiling) that would otherwise
    turn into distracting ASCII noise.
    """
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)  # respect phone camera orientation
    img = img.convert("L")
    img = crop_to_square(img, vertical_bias=vertical_bias)
    if zoom < 1.0:
        w, h = img.size
        new_side = int(w * zoom)
        x0 = (w - new_side) // 2
        y0 = (h - new_side) // 2
        img = img.crop((x0, y0, x0 + new_side, y0 + new_side))
    img = img.resize((size, size), Image.LANCZOS)
    img = ImageOps.autocontrast(img, cutoff=1)
    return img


def fetch_avatar(username: str, size: int = 200) -> Image.Image:
    """Fetch the user's GitHub avatar. Falls back to a generated
    placeholder portrait if the network is unavailable."""
    url = f"https://github.com/{username}.png?size={size}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("L")
        img = ImageOps.autocontrast(img, cutoff=1)
        return img
    except Exception as exc:  # noqa: BLE001
        print(f"[terminal] avatar fetch failed ({exc}); using static avatar")
        return static_avatar(username, size)


def static_avatar(seed_text: str, size: int) -> Image.Image:
    """A deterministic, non-photographic cyberpunk avatar glyph -- no
    real photo, no network call, nothing personally identifying. Same
    output every time for a given seed, so it reads as an intentional
    design choice rather than a broken fallback.

    Tones are chosen for the "dark pixel -> dense glyph" ASCII mapping:
    a bright background (255) fades to blank space, while the darker
    silhouette + visor renders as visible glyphs.
    """
    rng = random.Random(sum(ord(c) for c in seed_text) or 1)
    img = Image.new("L", (size, size), color=255)
    draw = ImageDraw.Draw(img)

    cx, cy = size / 2, size / 2 - size * 0.05
    head_r = size * 0.30

    # head + shoulders silhouette
    draw.ellipse([cx - head_r, cy - head_r * 1.15, cx + head_r, cy + head_r * 1.15], fill=60)
    draw.ellipse([cx - size * 0.42, cy + head_r * 0.55, cx + size * 0.42, cy + size * 0.85],
                 fill=110)

    # a horizontal "visor" band across the eye-line -- reads as a
    # deliberate cyberpunk design element (glasses/HUD), not a face
    visor_h = head_r * 0.32
    draw.rectangle(
        [cx - head_r * 0.92, cy - visor_h * 0.5, cx + head_r * 0.92, cy + visor_h * 0.5],
        fill=15,
    )
    # a couple of thin "scan line" accents below the visor
    for i in range(2):
        yy = cy + visor_h * 1.3 + i * visor_h * 0.9
        draw.rectangle([cx - head_r * 0.55, yy, cx + head_r * 0.55, yy + visor_h * 0.18], fill=40)

    # deterministic procedural texture (same seed -> same output, always)
    for _ in range(40):
        x = rng.uniform(cx - head_r, cx + head_r)
        y = rng.uniform(cy - head_r, cy + head_r)
        r = rng.uniform(2, 10)
        v = rng.randint(0, 190)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=v)

    img = img.filter(ImageFilter.GaussianBlur(2))
    return img


def image_to_ascii_rows(img: Image.Image, cols: int = COLS) -> List[str]:
    w, h = img.size
    rows_count = max(1, int(cols * (h / w) * CHAR_ASPECT))
    small = img.resize((cols, rows_count))
    pixels = small.load()

    ramp_len = len(RAMP) - 1
    lines: List[str] = []
    for y in range(rows_count):
        row_chars = []
        for x in range(cols):
            lum = pixels[x, y]  # 0 (black) .. 255 (white)
            # Dark pixels -> dense glyphs, bright pixels -> sparse/blank.
            # This is the conventional ASCII-art mapping and matters a lot
            # for real photos: a bright background (e.g. an office ceiling)
            # should fade toward blank, not dominate the frame with dense
            # characters just because it's well-lit.
            idx = int(lum / 255 * ramp_len)
            row_chars.append(RAMP[idx])
        lines.append("".join(row_chars))
    return lines


def luminance_rows(img: Image.Image, cols: int = COLS) -> List[List[int]]:
    """Average luminance per character cell, used to tint glyph color."""
    w, h = img.size
    rows_count = max(1, int(cols * (h / w) * CHAR_ASPECT))
    small = img.resize((cols, rows_count))
    pixels = small.load()
    grid = []
    for y in range(rows_count):
        grid.append([pixels[x, y] for x in range(cols)])
    return grid


def xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# --------------------------------------------------------------------------
# Layout / palette
# --------------------------------------------------------------------------
CHAR_W = 6.1
CHAR_H = 11
PAD_X = 20
PAD_TOP_CHROME = 44
PAD_BOTTOM = 66

BG = "#0d1117"
WINDOW_BG = "#0b0f16"
WINDOW_STROKE = "#232a36"
CHROME_BG = "#161b22"
NEON_GREEN = "#39ff88"
NEON_CYAN = "#39e6ff"
MUTED = "#586173"
PROMPT_GREEN = "#39ff88"
CURSOR_COLOR = "#f4fffb"


def glyph_color(lum: int) -> str:
    """Map luminance (0..255) to a neon green/cyan glow tone -- brighter
    pixels in the source photo render as brighter neon glyphs."""
    t = lum / 255.0
    # interpolate dim teal -> neon green -> near-white
    if t < 0.5:
        u = t / 0.5
        r = int(6 + u * (20 - 6))
        g = int(46 + u * (200 - 46))
        b = int(48 + u * (140 - 48))
    else:
        u = (t - 0.5) / 0.5
        r = int(20 + u * (220 - 20))
        g = int(200 + u * (255 - 200))
        b = int(140 + u * (230 - 140))
    return f"#{r:02x}{g:02x}{b:02x}"


def build_svg(username: str, display_name: str, cols: int = COLS,
              local_image: Optional[str] = None, vertical_bias: float = 0.28,
              zoom: float = 1.0, static: bool = False) -> str:
    if static:
        # Never touches the network or any photo -- purely a deterministic,
        # non-photographic design. Use this when a real/avatar photo is
        # not something you want derived into a public ASCII asset.
        img = static_avatar(username, 200)
    elif local_image:
        img = load_local_image(local_image, vertical_bias=vertical_bias, zoom=zoom)
    else:
        img = fetch_avatar(username)
    ascii_rows = image_to_ascii_rows(img, cols)
    lum_rows = luminance_rows(img, cols)
    n_rows = len(ascii_rows)

    art_w = cols * CHAR_W
    art_h = n_rows * CHAR_H

    width = int(art_w + PAD_X * 2 + 24)
    win_top = 14
    win_left = 12
    win_w = width - win_left * 2
    art_left = win_left + 16
    art_top = win_top + PAD_TOP_CHROME
    win_h = PAD_TOP_CHROME + art_h + PAD_BOTTOM
    height = win_top + win_h + 14

    row_delay = 0.085
    row_dur = 0.16
    total_art_time = n_rows * row_delay + row_dur

    parts: List[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="\'SF Mono\', \'Fira Code\', Consolas, monospace">'
    )

    # ---- defs -------------------------------------------------------
    parts.append("<defs>")
    parts.append(
        '<filter id="termGlow" x="-40%" y="-40%" width="180%" height="180%">'
        '<feGaussianBlur in="SourceGraphic" stdDeviation="3.2" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
        "</filter>"
    )
    parts.append(
        '<filter id="winShadow" x="-30%" y="-30%" width="160%" height="180%">'
        '<feDropShadow dx="0" dy="10" stdDeviation="16" flood-color="#00e5ff" flood-opacity="0.12"/>'
        '<feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000000" flood-opacity="0.55"/>'
        "</filter>"
    )
    parts.append(
        f'<linearGradient id="chromeGrad" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="#1c222d"/>'
        f'<stop offset="100%" stop-color="{CHROME_BG}"/>'
        f"</linearGradient>"
    )
    for i in range(n_rows):
        y = art_top + i * CHAR_H
        parts.append(
            f'<clipPath id="rowClip{i}">'
            f'<rect x="{art_left}" y="{y - CHAR_H + 3}" width="{art_w}" height="{CHAR_H}"/>'
            f"</clipPath>"
        )
    parts.append("</defs>")

    # ---- background ---------------------------------------------------
    parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{BG}"/>')

    # ---- terminal window ------------------------------------------------
    parts.append(
        f'<g filter="url(#winShadow)">'
        f'<rect x="{win_left}" y="{win_top}" width="{win_w}" height="{win_h}" rx="12" '
        f'fill="{WINDOW_BG}" stroke="{WINDOW_STROKE}" stroke-width="1.2"/>'
        f'</g>'
    )
    # chrome bar
    parts.append(
        f'<path d="M {win_left} {win_top + 28} L {win_left} {win_top + 12} '
        f'Q {win_left} {win_top} {win_left + 12} {win_top} '
        f'L {win_left + win_w - 12} {win_top} '
        f'Q {win_left + win_w} {win_top} {win_left + win_w} {win_top + 12} '
        f'L {win_left + win_w} {win_top + 28} Z" fill="url(#chromeGrad)"/>'
    )
    parts.append(
        f'<line x1="{win_left}" y1="{win_top + 28}" x2="{win_left + win_w}" y2="{win_top + 28}" '
        f'stroke="{WINDOW_STROKE}" stroke-width="1"/>'
    )
    # traffic lights
    for i, color in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        cx = win_left + 20 + i * 18
        parts.append(f'<circle cx="{cx}" cy="{win_top + 14}" r="5.5" fill="{color}"/>')
    # title (left-aligned, starting clear of the traffic-light dots)
    parts.append(
        f'<text x="{win_left + 62}" y="{win_top + 18}" font-size="10.5" '
        f'fill="{MUTED}" letter-spacing="0.3">{xml_escape(username)}</text>'
    )

    # ---- ASCII art rows -----------------------------------------------
    for i, row in enumerate(ascii_rows):
        y = art_top + i * CHAR_H
        # build per-character tspans colored by luminance so the portrait
        # keeps its neon "glow map" instead of being flat-colored
        row_lums = lum_rows[i]
        spans = []
        run_char = None
        run_color = None
        run_start = 0
        row_len = len(row)
        for x in range(row_len + 1):
            ch = row[x] if x < row_len else None
            color = glyph_color(row_lums[x]) if x < row_len else None
            if ch is None or color != run_color:
                if run_color is not None:
                    seg = row[run_start:x]
                    spans.append(
                        f'<tspan fill="{run_color}">{xml_escape(seg)}</tspan>'
                    )
                run_color = color
                run_start = x
        row_markup = "".join(spans)

        # Reveal via plain opacity fade on a <g> wrapper -- the same
        # technique already proven to animate correctly for info-card.svg
        # and github-contribution-animation.svg. (An earlier version used
        # an <animate> on a <clipPath>'s rect width to fake a left-to-right
        # "typing" wipe; animating geometry *inside* a referenced clipPath
        # is inconsistently supported across renderers, so it's avoided
        # here in favor of a mechanism with a track record of working.)
        begin = round(0.35 + i * row_delay, 3)
        parts.append(
            f'<g opacity="0">'
            f'<animate attributeName="opacity" from="0" to="1" begin="{begin}s" '
            f'dur="{row_dur}s" fill="freeze"/>'
            f'<text x="{art_left}" y="{y}" font-size="9" '
            f'xml:space="preserve">{row_markup}</text>'
            f"</g>"
        )
        # brief cursor flash at the start of this row -- a plain rect
        # opacity/x animation (not nested inside a clipPath), same
        # reliable category as the fade above.
        parts.append(
            f'<rect x="{art_left}" y="{y - CHAR_H + 3}" width="6" height="{CHAR_H}" '
            f'fill="{CURSOR_COLOR}" opacity="0" filter="url(#termGlow)">'
            f'<animate attributeName="opacity" values="0;0.92;0" keyTimes="0;0.4;1" '
            f'begin="{begin}s" dur="{row_dur + 0.1}s" fill="freeze"/>'
            f'<animate attributeName="x" from="{art_left}" to="{art_left + art_w}" '
            f'begin="{begin}s" dur="{row_dur + 0.1}s" fill="freeze"/>'
            f"</rect>"
        )

    # ---- footer: $ whoami typewriter -----------------------------------
    footer_y = art_top + n_rows * CHAR_H + 26
    prompt = "$ whoami"
    answer = display_name

    prompt_delay = total_art_time + 0.5
    char_dur = 0.045
    prompt_time = len(prompt) * char_dur

    # Monospace footer glyphs render wider than the dense-ASCII art font;
    # measured advance widths at font-size 12.5 for the fonts in the
    # font-family stack (SF Mono / Fira Code / Consolas / generic mono).
    PROMPT_CHAR_W = 7.7   # font-weight 600
    ANSWER_CHAR_W = 8.0   # font-weight 700 (slightly wider)
    GAP = 16

    prompt_px = len(prompt) * PROMPT_CHAR_W + 3
    parts.append(
        f'<clipPath id="promptClip">'
        f'<rect x="{art_left}" y="{footer_y - 12}" width="0" height="16">'
        f'<animate attributeName="width" from="0" to="{prompt_px}" '
        f'begin="{round(prompt_delay, 3)}s" dur="{prompt_time}s" fill="freeze" '
        f'calcMode="linear"/>'
        f"</rect>"
        f"</clipPath>"
    )
    parts.append(
        f'<text x="{art_left}" y="{footer_y}" font-size="12.5" font-weight="600" '
        f'fill="{PROMPT_GREEN}" clip-path="url(#promptClip)" xml:space="preserve">{xml_escape(prompt)}</text>'
    )

    answer_delay = prompt_delay + prompt_time + 0.15
    answer_char_dur = 0.05
    answer_time = max(0.01, len(answer) * answer_char_dur)
    ax = art_left + prompt_px + GAP
    answer_px = len(answer) * ANSWER_CHAR_W + 4
    parts.append(
        f'<clipPath id="answerClip">'
        f'<rect x="{ax}" y="{footer_y - 12}" width="0" height="16">'
        f'<animate attributeName="width" from="0" to="{answer_px}" '
        f'begin="{round(answer_delay, 3)}s" dur="{answer_time}s" fill="freeze" '
        f'calcMode="linear"/>'
        f"</rect>"
        f"</clipPath>"
    )
    parts.append(
        f'<text x="{ax}" y="{footer_y}" font-size="12.5" font-weight="700" '
        f'fill="{NEON_CYAN}" filter="url(#termGlow)" clip-path="url(#answerClip)" '
        f'xml:space="preserve">{xml_escape(answer)}</text>'
    )

    # blinking cursor after the answer finishes typing
    cursor_x = ax + answer_px + 2
    cursor_start = answer_delay + answer_time
    parts.append(
        f'<rect x="{cursor_x}" y="{footer_y - 11}" width="7" height="14" fill="{CURSOR_COLOR}" '
        f'opacity="0">'
        f'<animate attributeName="opacity" from="0" to="1" begin="{round(cursor_start, 3)}s" '
        f'dur="0.01s" fill="freeze"/>'
        f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.51;1" '
        f'begin="{round(cursor_start, 3)}s" dur="1s" repeatCount="indefinite"/>'
        f"</rect>"
    )

    parts.append("</svg>")
    return "".join(parts)


def resolve_display_name(username: str, token: Optional[str]) -> str:
    if token:
        try:
            r = requests.get(
                f"https://api.github.com/users/{username}",
                headers={"Authorization": f"bearer {token}"},
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            return data.get("name") or username
        except Exception:  # noqa: BLE001
            pass
    try:
        r = requests.get(f"https://api.github.com/users/{username}", timeout=10)
        if r.ok:
            data = r.json()
            return data.get("name") or username
    except Exception:  # noqa: BLE001
        pass
    return username


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate terminal-card.svg")
    ap.add_argument("--username", default="shwetangigode")
    ap.add_argument("--name", default=None, help="Display name (skips API lookup if given)")
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    ap.add_argument("--cols", type=int, default=COLS)
    ap.add_argument("--out", default="terminal-card.svg")
    ap.add_argument(
        "--local-image",
        default=None,
        help="Path to a local photo to use instead of fetching the GitHub "
             "avatar (e.g. a selfie). Auto-cropped to a square and "
             "contrast-boosted before ASCII conversion.",
    )
    ap.add_argument(
        "--vertical-bias",
        type=float,
        default=0.28,
        help="0.0-1.0: where the square crop sits vertically on a portrait "
             "photo (0=top-anchored/more headroom below, 1=bottom-anchored). "
             "Only applies with --local-image.",
    )
    ap.add_argument(
        "--zoom",
        type=float,
        default=1.0,
        help="0-1: keep only the centered fraction of the square crop, to "
             "trim a busy background. Only applies with --local-image.",
    )
    ap.add_argument(
        "--static",
        action="store_true",
        help="Never fetch a real photo (not even the GitHub avatar) or read "
             "--local-image. Always renders the same deterministic, "
             "non-photographic cyberpunk avatar glyph for this username.",
    )
    args = ap.parse_args()

    display_name = args.name or resolve_display_name(args.username, args.token)
    svg = build_svg(args.username, display_name, cols=args.cols,
                     local_image=args.local_image, vertical_bias=args.vertical_bias,
                     zoom=args.zoom, static=args.static)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"[terminal] wrote {args.out} ({len(svg):,} bytes)")


if __name__ == "__main__":
    main()
