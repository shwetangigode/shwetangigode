#!/usr/bin/env python3
"""
generate_about_visual.py
--------------------------------
Generates `about-visual.svg`: a looping, animated distributed-systems /
event-streaming diagram for the About Me section -- pulsing service
nodes connected by traveling "packet" dots along Kafka-style event
lines, in the same dark cyberpunk palette as the other cards.

Why an SVG instead of a GIF: everything else in this profile was moved
away from third-party/external assets specifically because they're a
reliability risk (see stats-card.svg). A hand-authored animated GIF
would need to be uploaded, hosted, and kept in sync by hand; this is
generated the same way as everything else -- self-contained, versioned
alongside the code, and free to restyle by editing this file.

Pure SMIL only -- no CSS animations, no JS.
"""

from __future__ import annotations

import argparse
import math
from typing import List, Tuple

WIDTH, HEIGHT = 560, 320
BG = "#0d1117"
PANEL_BG = "#0b0f16"
PANEL_STROKE = "#232a36"
CYAN = "#39e6ff"
GREEN = "#39ff88"
ORANGE = "#ff8a3d"
PURPLE = "#b06bff"
MUTED = "#586173"
WHITE = "#e6edf3"

# (x, y, label, color)
NODES: List[Tuple[float, float, str, str]] = [
    (110, 90, "API", CYAN),
    (300, 60, "Kafka", ORANGE),
    (470, 100, "DB", GREEN),
    (110, 230, "Batch", PURPLE),
    (300, 250, "Cache", CYAN),
    (470, 210, "Monitor", GREEN),
]

# indices into NODES: (from, to)
EDGES: List[Tuple[int, int]] = [
    (0, 1), (1, 2), (0, 3), (3, 4), (4, 1), (1, 5), (2, 5),
]


def build_svg() -> str:
    parts: List[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" font-family="\'SF Mono\', Consolas, monospace">'
    )

    parts.append("<defs>")
    parts.append(
        '<filter id="nodeGlow" x="-150%" y="-150%" width="400%" height="400%">'
        '<feGaussianBlur in="SourceGraphic" stdDeviation="3.2" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
        "</filter>"
    )
    parts.append(
        f'<linearGradient id="aboutBg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{PANEL_BG}"/>'
        f'<stop offset="100%" stop-color="#090c10"/>'
        f"</linearGradient>"
    )
    parts.append("</defs>")

    parts.append(f'<rect x="0" y="0" width="{WIDTH}" height="{HEIGHT}" fill="{BG}"/>')
    parts.append(
        f'<rect x="4" y="4" width="{WIDTH - 8}" height="{HEIGHT - 8}" rx="14" '
        f'fill="url(#aboutBg)" stroke="{PANEL_STROKE}" stroke-width="1.2"/>'
    )

    # ---- edges (static lines) -------------------------------------------
    for a, b in EDGES:
        x1, y1, _, _ = NODES[a]
        x2, y2, _, _ = NODES[b]
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{PANEL_STROKE}" stroke-width="1.4"/>'
        )

    # ---- traveling packets along each edge --------------------------------
    packet_colors = [CYAN, GREEN, ORANGE, PURPLE]
    for i, (a, b) in enumerate(EDGES):
        x1, y1, _, _ = NODES[a]
        x2, y2, _, _ = NODES[b]
        color = packet_colors[i % len(packet_colors)]
        dur = 2.6 + (i % 3) * 0.5
        begin = round(i * 0.35, 2)
        parts.append(
            f'<circle r="3.2" fill="{color}" filter="url(#nodeGlow)">'
            f'<animateMotion path="M {x1} {y1} L {x2} {y2}" '
            f'begin="{begin}s" dur="{dur}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.1;0.85;1" '
            f'begin="{begin}s" dur="{dur}s" repeatCount="indefinite"/>'
            f"</circle>"
        )

    # ---- nodes -------------------------------------------------------------
    for i, (x, y, label, color) in enumerate(NODES):
        pulse_begin = round(i * 0.22, 2)
        parts.append(
            f'<circle cx="{x}" cy="{y}" r="16" fill="none" stroke="{color}" '
            f'stroke-width="1.2" opacity="0.5">'
            f'<animate attributeName="r" values="14;22;14" begin="{pulse_begin}s" '
            f'dur="2.4s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0.55;0;0.55" begin="{pulse_begin}s" '
            f'dur="2.4s" repeatCount="indefinite"/>'
            f"</circle>"
        )
        parts.append(
            f'<circle cx="{x}" cy="{y}" r="10" fill="{PANEL_BG}" stroke="{color}" '
            f'stroke-width="2" filter="url(#nodeGlow)"/>'
        )
        parts.append(
            f'<text x="{x}" y="{y + 28}" font-size="10.5" fill="{WHITE}" '
            f'text-anchor="middle">{label}</text>'
        )

    # ---- caption / typewriter line -----------------------------------------
    caption = "designing for scale, one event at a time"
    cy = HEIGHT - 26
    parts.append(
        f'<clipPath id="captionClip">'
        f'<rect x="{WIDTH/2 - 170}" y="{cy - 12}" width="0" height="18">'
        f'<animate attributeName="width" from="0" to="340" begin="0.6s" dur="2.6s" '
        f'fill="freeze" calcMode="spline" keySplines="0.3 0.9 0.2 1"/>'
        f"</rect>"
        f"</clipPath>"
    )
    parts.append(
        f'<text x="{WIDTH/2}" y="{cy}" font-size="12" fill="{MUTED}" '
        f'text-anchor="middle" clip-path="url(#captionClip)" font-style="italic">'
        f'{caption}</text>'
    )

    parts.append("</svg>")
    return "".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate about-visual.svg")
    ap.add_argument("--out", default="about-visual.svg")
    args = ap.parse_args()
    svg = build_svg()
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"[about] wrote {args.out} ({len(svg):,} bytes)")


if __name__ == "__main__":
    main()
