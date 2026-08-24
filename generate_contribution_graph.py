#!/usr/bin/env python3
"""
generate_contribution_graph.py
--------------------------------
Generates `github-contribution-animation.svg`: a 53x7 GitHub-style
contribution calendar rendered as a self-contained, SMIL-animated SVG.

Visual language: deep dark-mode / glassmorphism / cyberpunk neon.

Animation: a diagonal "slant reveal" sweeping from bottom-left to
top-right. Each cell pops in with a bright white/green specular
"glint" that flashes and fades, settling into its final contribution
color. Level 3+ cells get an outer neon glow filter.

No external CSS or JS -- everything is native SVG + SMIL (<animate>),
so it animates correctly even when GitHub renders it as a plain <img>.

Usage:
    python3 generate_contribution_graph.py --username shwetangigode
    python3 generate_contribution_graph.py --username shwetangigode --token <GH_TOKEN>

If a GitHub token is supplied (or found in the GITHUB_TOKEN env var),
real contribution data is pulled via the GraphQL API. Otherwise a
tasteful synthetic dataset (weekday-weighted, with streaks) is used
so the script always produces a finished result offline.
"""

from __future__ import annotations

import argparse
import datetime
import os
import random
import sys
from typing import List, Optional

import requests

# --------------------------------------------------------------------------
# Layout constants
# --------------------------------------------------------------------------
WEEKS = 53
DAYS = 7
CELL = 11            # square size (px)
GAP = 3               # gap between squares (px)
STEP = CELL + GAP
GRID_LEFT = 46        # left margin inside panel (room for day labels)
GRID_TOP = 46          # top margin inside panel (room for title + months)
PANEL_PAD = 22

WIDTH = GRID_LEFT + WEEKS * STEP - GAP + PANEL_PAD
HEIGHT = GRID_TOP + DAYS * STEP - GAP + PANEL_PAD + 18

# --------------------------------------------------------------------------
# Palette -- deep dark / neon cyberpunk
# --------------------------------------------------------------------------
BG_TOP = "#0d1117"
BG_BOTTOM = "#090c10"
PANEL_STROKE = "#1f2530"
TITLE_A = "#00f5ff"   # cyan
TITLE_B = "#7c5cff"   # purple
MUTED_TEXT = "#6b7280"

# Contribution-level palette (0..4). Base neon teal/green ramp.
LEVEL_COLORS = {
    0: "#161b22",   # empty slot
    1: "#0b3d3a",   # dim teal
    2: "#0f6e63",   # mid teal-green
    3: "#12d6a0",   # bright neon green
    4: "#39ffb0",   # brightest neon green
}
# Rare neon accent swaps for level 4 cells, for that cyberpunk "sparkle"
ACCENT_COLORS = ["#39ffb0", "#00e5ff", "#ff8a3d", "#b06bff"]

GLINT_COLOR = "#f2fff7"  # near-white with a hint of green

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAY_LABELS = {1: "Mon", 3: "Wed", 5: "Fri"}


# --------------------------------------------------------------------------
# Data: real (GraphQL) or synthetic
# --------------------------------------------------------------------------
def fetch_real_contributions(username: str, token: str) -> Optional[List[List[int]]]:
    """Pull the last ~53 weeks of contribution counts from GitHub's
    GraphQL API and bucket them into 5 levels (0-4). Returns a
    week-major grid: grid[week][day] -> level, or None on failure.
    """
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            weeks {
              contributionDays {
                weekday
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    try:
        resp = requests.post(
            "https://api.github.com/graphql",
            json={"query": query, "variables": {"login": username}},
            headers={"Authorization": f"bearer {token}"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        weeks_raw = data["data"]["user"]["contributionsCollection"][
            "contributionCalendar"]["weeks"]
    except Exception as exc:  # noqa: BLE001 - best effort, always degrade gracefully
        print(f"[contrib] GraphQL fetch failed, using synthetic data ({exc})",
              file=sys.stderr)
        return None

    counts: List[List[int]] = []
    for wk in weeks_raw:
        col = [0] * DAYS
        for d in wk["contributionDays"]:
            col[d["weekday"]] = d["contributionCount"]
        counts.append(col)

    # keep only the most recent WEEKS columns
    counts = counts[-WEEKS:]
    while len(counts) < WEEKS:
        counts.insert(0, [0] * DAYS)

    flat = [c for col in counts for c in col if c > 0]
    if not flat:
        return [[0] * DAYS for _ in range(WEEKS)]

    flat.sort()

    def q(p: float) -> float:
        idx = min(len(flat) - 1, int(p * (len(flat) - 1)))
        return flat[idx]

    t1, t2, t3 = q(0.25), q(0.5), q(0.85)

    def level(c: int) -> int:
        if c <= 0:
            return 0
        if c <= t1:
            return 1
        if c <= t2:
            return 2
        if c <= t3:
            return 3
        return 4

    return [[level(c) for c in col] for col in counts]


def generate_synthetic_contributions(seed: Optional[int] = None) -> List[List[int]]:
    """Weekday-weighted synthetic activity with a few realistic streaks
    and quiet weekends, so the demo output looks organic even offline.
    """
    rng = random.Random(seed)
    grid = [[0] * DAYS for _ in range(WEEKS)]

    streak_chance = 0.10
    week = 0
    while week < WEEKS:
        if rng.random() < streak_chance:
            streak_len = rng.randint(3, 9)
            intensity = rng.choice([2, 3, 3, 4])
            for i in range(streak_len):
                w = week + i // DAYS
                d = i % DAYS
                if w >= WEEKS:
                    break
                # weekends a bit quieter even during streaks
                bump = -1 if d in (0, 6) and rng.random() < 0.5 else 0
                grid[w][d] = max(0, min(4, intensity + rng.choice([-1, 0, 0, 1]) + bump))
            week += max(1, streak_len // DAYS)
        else:
            for d in range(DAYS):
                base = 0.12 if d in (0, 6) else 0.38
                if rng.random() < base:
                    grid[week][d] = rng.choice([1, 1, 2, 2, 3])
            week += 1
    return grid


# --------------------------------------------------------------------------
# SVG building
# --------------------------------------------------------------------------
def diagonal_index(week: int, day: int) -> int:
    """Bottom-left -> top-right sweep: front-line = week - day.
    Bottom-left cell (week=0, day=DAYS-1) is the most negative,
    top-right cell (week=WEEKS-1, day=0) is the most positive.
    """
    return week - day


def month_marker_weeks(start_date: datetime.date) -> List[tuple]:
    """Return (week_index, label) for the first week of each month
    that appears in the grid."""
    markers = []
    last_month = None
    for w in range(WEEKS):
        d = start_date + datetime.timedelta(weeks=w)
        if d.month != last_month:
            markers.append((w, MONTH_LABELS[d.month - 1]))
            last_month = d.month
    return markers


def build_svg(grid: List[List[int]], username: str) -> str:
    min_diag = min(diagonal_index(w, d) for w in range(WEEKS) for d in range(DAYS))
    max_diag = max(diagonal_index(w, d) for w in range(WEEKS) for d in range(DAYS))
    diag_span = max_diag - min_diag

    step_delay = 0.028          # seconds between successive diagonals
    pop_dur = 0.28
    glint_dur = 0.42
    total_reveal = diag_span * step_delay + pop_dur + 0.4

    today = datetime.date.today()
    # align to the most recent Sunday so columns look like real GitHub weeks
    grid_start = today - datetime.timedelta(weeks=WEEKS - 1)
    grid_start = grid_start - datetime.timedelta(days=(grid_start.weekday() + 1) % 7)

    parts: List[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'font-family="\'Segoe UI\', \'SF Mono\', Consolas, monospace">'
    )

    # ---------------------------------------------------------------- defs
    parts.append("<defs>")
    parts.append(
        f'<linearGradient id="bgGrad" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{BG_TOP}"/>'
        f'<stop offset="100%" stop-color="{BG_BOTTOM}"/>'
        f"</linearGradient>"
    )
    parts.append(
        f'<linearGradient id="titleGrad" x1="0%" y1="0%" x2="100%" y2="0%">'
        f'<stop offset="0%" stop-color="{TITLE_A}"/>'
        f'<stop offset="50%" stop-color="{TITLE_B}"/>'
        f'<stop offset="100%" stop-color="{TITLE_A}"/>'
        f'<animate attributeName="x1" values="-40%;100%;-40%" dur="6s" repeatCount="indefinite"/>'
        f'<animate attributeName="x2" values="60%;200%;60%" dur="6s" repeatCount="indefinite"/>'
        f"</linearGradient>"
    )
    # glow filter for high-intensity cells
    parts.append(
        '<filter id="cellGlow" x="-150%" y="-150%" width="400%" height="400%">'
        '<feGaussianBlur in="SourceGraphic" stdDeviation="2.6" result="blur"/>'
        '<feMerge>'
        '<feMergeNode in="blur"/>'
        '<feMergeNode in="blur"/>'
        '<feMergeNode in="SourceGraphic"/>'
        "</feMerge>"
        "</filter>"
    )
    parts.append(
        '<filter id="panelGlow" x="-20%" y="-20%" width="140%" height="140%">'
        '<feGaussianBlur in="SourceGraphic" stdDeviation="6" result="b"/>'
        '<feColorMatrix in="b" type="matrix" values="'
        '0 0 0 0 0.20  0 0 0 0 0.85  0 0 0 0 1  0 0 0 0.35 0" result="tint"/>'
        '<feMerge><feMergeNode in="tint"/><feMergeNode in="SourceGraphic"/></feMerge>'
        "</filter>"
    )
    parts.append("</defs>")

    # ---------------------------------------------------------------- bg
    parts.append(f'<rect x="0" y="0" width="{WIDTH}" height="{HEIGHT}" fill="url(#bgGrad)"/>')

    panel_x, panel_y = 6, 6
    panel_w, panel_h = WIDTH - 12, HEIGHT - 12
    parts.append(
        f'<rect x="{panel_x}" y="{panel_y}" width="{panel_w}" height="{panel_h}" rx="16" '
        f'fill="#11161f" fill-opacity="0.72" stroke="{PANEL_STROKE}" stroke-width="1" '
        f'filter="url(#panelGlow)"/>'
    )

    # ---------------------------------------------------------------- title
    parts.append(
        f'<text x="{panel_x + 18}" y="26" font-size="13" font-weight="700" '
        f'letter-spacing="0.5" fill="url(#titleGrad)">CONTRIBUTION ACTIVITY</text>'
    )
    parts.append(
        f'<circle cx="{panel_x + panel_w - 16}" cy="21" r="4" fill="{ACCENT_COLORS[0]}">'
        f'<animate attributeName="opacity" values="1;0.25;1" dur="1.6s" repeatCount="indefinite"/>'
        f"</circle>"
    )

    # ---------------------------------------------------------------- month labels
    for w, label in month_marker_weeks(grid_start):
        x = GRID_LEFT + w * STEP
        parts.append(
            f'<text x="{x}" y="{GRID_TOP - 8}" font-size="9" fill="{MUTED_TEXT}">{label}</text>'
        )

    # ---------------------------------------------------------------- day labels
    for d, label in DAY_LABELS.items():
        y = GRID_TOP + d * STEP + CELL - 2
        parts.append(
            f'<text x="{GRID_LEFT - 8}" y="{y}" font-size="9" fill="{MUTED_TEXT}" '
            f'text-anchor="end">{label}</text>'
        )

    # ---------------------------------------------------------------- cells
    rng = random.Random(1337)
    for w in range(WEEKS):
        for d in range(DAYS):
            level = grid[w][d]
            x = GRID_LEFT + w * STEP
            y = GRID_TOP + d * STEP
            diag = diagonal_index(w, d)
            begin = round((diag - min_diag) * step_delay, 3)

            base_color = LEVEL_COLORS[level]
            if level == 4 and rng.random() < 0.16:
                base_color = rng.choice(ACCENT_COLORS)

            glow_attr = ' filter="url(#cellGlow)"' if level >= 3 else ""

            # base cell: starts on the "empty" tone, pops to real opacity
            parts.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.5" '
                f'fill="{base_color}" opacity="0"{glow_attr}>'
                f'<animate attributeName="opacity" from="0" to="1" '
                f'begin="{begin}s" dur="{pop_dur}s" fill="freeze" calcMode="spline" '
                f'keySplines="0.2 0.8 0.2 1"/>'
                f"</rect>"
            )

            if level > 0:
                # specular glint flash overlay, fades to fully transparent
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.5" '
                    f'fill="{GLINT_COLOR}" opacity="0" pointer-events="none">'
                    f'<animate attributeName="opacity" '
                    f'values="0;0.95;0" keyTimes="0;0.18;1" '
                    f'begin="{begin}s" dur="{glint_dur}s" fill="freeze"/>'
                    f"</rect>"
                )
            else:
                # empty cells still get a subtle border fade-in for cohesion
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.5" '
                    f'fill="none" stroke="#232a35" stroke-width="1" opacity="0">'
                    f'<animate attributeName="opacity" from="0" to="1" '
                    f'begin="{begin}s" dur="{pop_dur}s" fill="freeze"/>'
                    f"</rect>"
                )

    # ---------------------------------------------------------------- legend
    legend_y = GRID_TOP + DAYS * STEP + 14
    parts.append(
        f'<text x="{GRID_LEFT}" y="{legend_y + 8}" font-size="9" fill="{MUTED_TEXT}">Less</text>'
    )
    lx = GRID_LEFT + 32
    for lvl in range(5):
        parts.append(
            f'<rect x="{lx}" y="{legend_y}" width="{CELL}" height="{CELL}" rx="2.5" '
            f'fill="{LEVEL_COLORS[lvl]}" opacity="0">'
            f'<animate attributeName="opacity" from="0" to="1" begin="{total_reveal}s" '
            f'dur="0.4s" fill="freeze"/>'
            f"</rect>"
        )
        lx += STEP
    parts.append(
        f'<text x="{lx + 4}" y="{legend_y + 8}" font-size="9" fill="{MUTED_TEXT}">More</text>'
    )
    parts.append(
        f'<text x="{panel_x + panel_w - 18}" y="{legend_y + 8}" font-size="9" '
        f'fill="{MUTED_TEXT}" text-anchor="end">@{username}</text>'
    )

    parts.append("</svg>")
    return "".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate github-contribution-animation.svg")
    ap.add_argument("--username", default="shwetangigode", help="GitHub username")
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"),
                     help="GitHub token (or set GITHUB_TOKEN env var) for real contribution data")
    ap.add_argument("--out", default="github-contribution-animation.svg")
    ap.add_argument("--seed", type=int, default=None, help="Seed for synthetic data (offline mode)")
    args = ap.parse_args()

    grid: Optional[List[List[int]]] = None
    if args.token:
        grid = fetch_real_contributions(args.username, args.token)
    if grid is None:
        grid = generate_synthetic_contributions(seed=args.seed)

    svg = build_svg(grid, args.username)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"[contrib] wrote {args.out} ({len(svg):,} bytes)")


if __name__ == "__main__":
    main()
