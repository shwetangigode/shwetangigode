#!/usr/bin/env python3
"""
generate_info_card.py
--------------------------------
Generates `info-card.svg`: a compact neofetch-style panel meant to sit
next to `terminal-card.svg`. Sections: About / Stack / Highlights.

Animation: every line slides up + fades in, staggered 0.06s apart, to
simulate a terminal printing neofetch output line-by-line. Pure SMIL.

Live data (best-effort, always degrades gracefully):
  - public repo count, followers, following via api.github.com
  - falls back to sensible placeholder numbers if the API is
    unreachable or rate-limited.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from typing import List, Optional

import requests

WIDTH = 460
BG = "#0d1117"
WINDOW_BG = "#0b0f16"
WINDOW_STROKE = "#232a36"
CHROME_BG = "#161b22"
MUTED = "#586173"
WHITE = "#e6edf3"
CYAN = "#39e6ff"
ORANGE = "#ff8a3d"
BLUE = "#4ea1ff"
GREEN = "#39ff88"
PURPLE = "#b06bff"

LINE_H = 20
PAD_X = 24
TOP_CHROME = 44
BOTTOM_PAD = 22


@dataclass
class Line:
    kind: str  # "header" | "field" | "spacer" | "bar"
    label: str = ""
    value: str = ""
    color: str = WHITE
    icon: str = ""


def fetch_profile_stats(username: str, token: Optional[str]) -> dict:
    headers = {"Authorization": f"bearer {token}"} if token else {}
    defaults = {
        "public_repos": 42,
        "followers": 128,
        "following": 37,
        "bio": "Building things that ship. Open source enthusiast.",
    }
    try:
        r = requests.get(f"https://api.github.com/users/{username}",
                          headers=headers, timeout=10)
        if not r.ok:
            return defaults
        data = r.json()
        return {
            "public_repos": data.get("public_repos", defaults["public_repos"]),
            "followers": data.get("followers", defaults["followers"]),
            "following": data.get("following", defaults["following"]),
            "bio": data.get("bio") or defaults["bio"],
        }
    except Exception:  # noqa: BLE001
        return defaults


def build_lines(
    username: str,
    stack: List[str],
    stats: dict,
    role: Optional[str] = None,
    bio_override: Optional[str] = None,
    highlights: Optional[List[str]] = None,
) -> List[Line]:
    bio = bio_override or stats["bio"]
    if len(bio) > 46:
        bio = bio[:43].rstrip() + "..."

    lines: List[Line] = []
    lines.append(Line("header", label=f"{username}", value="@ github", color=CYAN))
    lines.append(Line("bar"))

    lines.append(Line("section", label="About", color=ORANGE))
    lines.append(Line("field", label="bio", value=bio, color=WHITE, icon="›"))
    lines.append(Line("field", label="role", value=role or "Software Developer", color=WHITE, icon="›"))
    lines.append(Line("spacer"))

    lines.append(Line("section", label="Stack", color=BLUE))
    # wrap stack chips into rows of ~3
    chunk = 3
    for i in range(0, len(stack), chunk):
        row = stack[i:i + chunk]
        lines.append(Line("field", label="", value="  •  ".join(row), color=CYAN, icon="›"))
    lines.append(Line("spacer"))

    lines.append(Line("section", label="Highlights", color=GREEN))
    if highlights:
        # custom "Label:Value" achievement lines take priority over raw API counters
        for item in highlights:
            if ":" in item:
                label, value = item.split(":", 1)
            else:
                label, value = "", item
            lines.append(Line("field", label=label.strip(), value=value.strip(), color=WHITE, icon="›"))
    else:
        lines.append(Line("field", label="repos", value=str(stats["public_repos"]), color=WHITE, icon="›"))
        lines.append(Line("field", label="followers", value=str(stats["followers"]), color=WHITE, icon="›"))
        lines.append(Line("field", label="following", value=str(stats["following"]), color=WHITE, icon="›"))
    lines.append(Line("spacer"))
    lines.append(Line("swatches"))

    return lines


def xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_svg(
    username: str,
    stack: List[str],
    stats: dict,
    role: Optional[str] = None,
    bio_override: Optional[str] = None,
    highlights: Optional[List[str]] = None,
) -> str:
    lines = build_lines(username, stack, stats, role=role, bio_override=bio_override, highlights=highlights)

    y = TOP_CHROME + 20
    row_ys: List[int] = []
    for ln in lines:
        row_ys.append(y)
        if ln.kind == "spacer":
            y += LINE_H * 0.55
        elif ln.kind == "bar":
            y += LINE_H * 0.9
        elif ln.kind == "swatches":
            y += LINE_H * 1.1
        else:
            y += LINE_H

    height = int(y + BOTTOM_PAD)
    win_left, win_top = 12, 14
    win_w = WIDTH - win_left * 2
    win_h = height - win_top - 14

    stagger = 0.06
    dur = 0.34

    parts: List[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" '
        f'font-family="\'SF Mono\', \'Fira Code\', Consolas, monospace">'
    )

    # ---- defs ---------------------------------------------------------
    parts.append("<defs>")
    parts.append(
        '<filter id="softGlow" x="-60%" y="-60%" width="220%" height="220%">'
        '<feGaussianBlur in="SourceGraphic" stdDeviation="2.4" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
        "</filter>"
    )
    parts.append(
        '<filter id="winShadow2" x="-30%" y="-30%" width="160%" height="180%">'
        '<feDropShadow dx="0" dy="10" stdDeviation="16" flood-color="#b06bff" flood-opacity="0.10"/>'
        '<feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000000" flood-opacity="0.55"/>'
        "</filter>"
    )
    parts.append(
        f'<linearGradient id="chromeGrad2" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="#1c222d"/>'
        f'<stop offset="100%" stop-color="{CHROME_BG}"/>'
        f"</linearGradient>"
    )
    parts.append(
        '<linearGradient id="logoGrad" x1="0%" y1="0%" x2="100%" y2="100%">'
        f'<stop offset="0%" stop-color="{CYAN}"/>'
        f'<stop offset="100%" stop-color="{PURPLE}"/>'
        "</linearGradient>"
    )
    parts.append("</defs>")

    # ---- background + window ------------------------------------------
    parts.append(f'<rect x="0" y="0" width="{WIDTH}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<g filter="url(#winShadow2)">'
        f'<rect x="{win_left}" y="{win_top}" width="{win_w}" height="{win_h}" rx="12" '
        f'fill="{WINDOW_BG}" stroke="{WINDOW_STROKE}" stroke-width="1.2"/>'
        f"</g>"
    )
    parts.append(
        f'<path d="M {win_left} {win_top + 28} L {win_left} {win_top + 12} '
        f'Q {win_left} {win_top} {win_left + 12} {win_top} '
        f'L {win_left + win_w - 12} {win_top} '
        f'Q {win_left + win_w} {win_top} {win_left + win_w} {win_top + 12} '
        f'L {win_left + win_w} {win_top + 28} Z" fill="url(#chromeGrad2)"/>'
    )
    parts.append(
        f'<line x1="{win_left}" y1="{win_top + 28}" x2="{win_left + win_w}" y2="{win_top + 28}" '
        f'stroke="{WINDOW_STROKE}" stroke-width="1"/>'
    )
    for i, color in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        cx = win_left + 20 + i * 18
        parts.append(f'<circle cx="{cx}" cy="{win_top + 14}" r="5.5" fill="{color}"/>')
    parts.append(
        f'<text x="{win_left + 62}" y="{win_top + 18}" font-size="10.5" '
        f'fill="{MUTED}" letter-spacing="0.3">neofetch --style=cyberpunk</text>'
    )

    # ---- rotating hex logo, top-right of the panel ----------------------
    lx, ly = win_left + win_w - 34, win_top + 18
    parts.append(
        f'<g transform="translate({lx},{ly})" opacity="0.9">'
        f'<g>'
        f'<polygon points="0,-12 10.4,-6 10.4,6 0,12 -10.4,6 -10.4,-6" '
        f'fill="none" stroke="url(#logoGrad)" stroke-width="1.6" filter="url(#softGlow)"/>'
        f'<polygon points="0,-6 5.2,-3 5.2,3 0,6 -5.2,3 -5.2,-3" '
        f'fill="url(#logoGrad)" opacity="0.55"/>'
        f'<animateTransform attributeName="transform" type="rotate" '
        f'from="0 0 0" to="360 0 0" dur="14s" repeatCount="indefinite"/>'
        f"</g>"
        f"</g>"
    )

    # ---- animated lines --------------------------------------------------
    for i, (ln, y0) in enumerate(zip(lines, row_ys)):
        begin = round(i * stagger, 3)
        if ln.kind == "spacer":
            continue

        if ln.kind == "bar":
            parts.append(
                f'<g opacity="0">'
                f'<animate attributeName="opacity" from="0" to="1" begin="{begin}s" '
                f'dur="{dur}s" fill="freeze"/>'
                f'<line x1="{win_left + PAD_X}" y1="{y0 - 5}" x2="{win_left + win_w - PAD_X}" '
                f'y2="{y0 - 5}" stroke="{WINDOW_STROKE}" stroke-width="1.4"/>'
                f"</g>"
            )
            continue

        if ln.kind == "swatches":
            sw_x = win_left + PAD_X
            colors = [ORANGE, BLUE, GREEN, CYAN, WHITE]
            g = [f'<g opacity="0">'
                 f'<animate attributeName="opacity" from="0" to="1" begin="{begin}s" '
                 f'dur="{dur}s" fill="freeze"/>']
            for j, c in enumerate(colors):
                g.append(
                    f'<rect x="{sw_x + j * 22}" y="{y0 - 10}" width="14" height="14" rx="3" '
                    f'fill="{c}"/>'
                )
            g.append("</g>")
            parts.append("".join(g))
            continue

        # header / section / field: slide up (dy 8 -> 0) + fade in
        parts.append(
            f'<g opacity="0">'
            f'<animate attributeName="opacity" from="0" to="1" begin="{begin}s" '
            f'dur="{dur}s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" '
            f'from="0 8" to="0 0" begin="{begin}s" dur="{dur}s" fill="freeze" '
            f'calcMode="spline" keySplines="0.2 0.8 0.2 1"/>'
        )

        x = win_left + PAD_X
        if ln.kind == "header":
            parts.append(
                f'<text x="{x}" y="{y0}" font-size="15" font-weight="700" '
                f'fill="{ln.color}" filter="url(#softGlow)">{xml_escape(ln.label)}</text>'
            )
            parts.append(
                f'<text x="{x + len(ln.label) * 9.2 + 8}" y="{y0}" font-size="12" '
                f'fill="{MUTED}">{xml_escape(ln.value)}</text>'
            )
        elif ln.kind == "section":
            parts.append(
                f'<text x="{x}" y="{y0}" font-size="12.5" font-weight="700" '
                f'fill="{ln.color}">{xml_escape(ln.label.upper())}</text>'
            )
        else:  # field
            cursor_x = x
            if ln.icon:
                parts.append(
                    f'<text x="{cursor_x}" y="{y0}" font-size="11.5" fill="{MUTED}">{ln.icon}</text>'
                )
                cursor_x += 14
            if ln.label:
                parts.append(
                    f'<text x="{cursor_x}" y="{y0}" font-size="11.5" fill="{MUTED}">'
                    f'{xml_escape(ln.label)}:</text>'
                )
                cursor_x += (len(ln.label) + 1) * 6.4 + 8
            parts.append(
                f'<text x="{cursor_x}" y="{y0}" font-size="11.5" fill="{ln.color}">'
                f'{xml_escape(ln.value)}</text>'
            )

        parts.append("</g>")

    parts.append("</svg>")
    return "".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate info-card.svg")
    ap.add_argument("--username", default="shwetangigode")
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    ap.add_argument(
        "--stack",
        default="Python,JavaScript,TypeScript,React,Node.js,Docker,PostgreSQL,AWS",
        help="Comma-separated tech stack list",
    )
    ap.add_argument("--role", default=None, help="Override the 'role' field (e.g. job title)")
    ap.add_argument("--bio", default=None, help="Override the bio line instead of pulling from the API")
    ap.add_argument(
        "--highlights",
        default=None,
        help="Pipe-separated 'Label:Value' achievement lines, e.g. "
             "'Award:Engineer of the Year|Perf:+80% throughput'. "
             "Overrides the default repos/followers/following counters.",
    )
    ap.add_argument("--out", default="info-card.svg")
    args = ap.parse_args()

    stack = [s.strip() for s in args.stack.split(",") if s.strip()]
    stats = fetch_profile_stats(args.username, args.token)
    highlights = [h.strip() for h in args.highlights.split("|")] if args.highlights else None
    svg = build_svg(args.username, stack, stats, role=args.role, bio_override=args.bio, highlights=highlights)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"[info] wrote {args.out} ({len(svg):,} bytes)")


if __name__ == "__main__":
    main()
