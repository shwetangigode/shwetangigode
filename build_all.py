#!/usr/bin/env python3
"""
build_all.py
--------------------------------
One command to build the full premium animated GitHub profile:

    python3 build_all.py --username shwetangigode

This will:
  1. Generate github-contribution-animation.svg
  2. Generate terminal-card.svg (ASCII avatar portrait)
  3. Generate info-card.svg (neofetch-style stats panel)
  4. Inject all three into README.md (side-by-side table + centered graph)

Designed to also be dropped into a scheduled GitHub Action so the
profile refreshes automatically (see README_SETUP.md for the workflow
snippet).
"""

from __future__ import annotations

import argparse
import os

import generate_contribution_graph as contrib
import generate_info_card as info
import generate_terminal_card as terminal
import inject_readme


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the full animated GitHub profile")
    ap.add_argument("--username", default="shwetangigode")
    ap.add_argument("--name", default=None, help="Display name for the terminal footer")
    ap.add_argument(
        "--local-image",
        default=None,
        help="Path to a local photo (e.g. a selfie) to use for the ASCII "
             "portrait instead of fetching the GitHub avatar.",
    )
    ap.add_argument("--vertical-bias", type=float, default=0.28,
                     help="Vertical anchor (0-1) for square-cropping --local-image")
    ap.add_argument("--zoom", type=float, default=1.0,
                     help="0-1: trim to the centered fraction of --local-image's square crop")
    ap.add_argument(
        "--static",
        action="store_true",
        help="Never fetch a real photo for the terminal card (not even the "
             "GitHub avatar). Renders a fixed, non-photographic avatar glyph.",
    )
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"),
                     help="GitHub token for real contribution/profile data (optional)")
    ap.add_argument("--stack", default="Python,JavaScript,TypeScript,React,Node.js,Docker,PostgreSQL,AWS")
    ap.add_argument("--role", default=None, help="Override the info-card 'role' field")
    ap.add_argument("--bio", default=None, help="Override the info-card bio line")
    ap.add_argument(
        "--highlights",
        default=None,
        help="Pipe-separated 'Label:Value' lines for the info-card Highlights section",
    )
    ap.add_argument("--readme", default="README.md")
    ap.add_argument("--outdir", default=".")
    ap.add_argument(
        "--anchor",
        default=None,
        help="If README.md has no PROFILE-SVG markers yet, insert the new "
             "section right before this literal heading instead of appending",
    )
    ap.add_argument("--heading", default="## 🖥️ Terminal Portrait & Live Stats")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    contrib_path = os.path.join(args.outdir, "github-contribution-animation.svg")
    terminal_path = os.path.join(args.outdir, "terminal-card.svg")
    info_path = os.path.join(args.outdir, "info-card.svg")

    # 1) contribution graph
    grid = None
    if args.token:
        grid = contrib.fetch_real_contributions(args.username, args.token)
    if grid is None:
        grid = contrib.generate_synthetic_contributions()
    with open(contrib_path, "w", encoding="utf-8") as fh:
        fh.write(contrib.build_svg(grid, args.username))
    print(f"[build] wrote {contrib_path}")

    # 2) terminal card (ASCII portrait)
    display_name = args.name or terminal.resolve_display_name(args.username, args.token)
    with open(terminal_path, "w", encoding="utf-8") as fh:
        fh.write(terminal.build_svg(args.username, display_name,
                                     local_image=args.local_image,
                                     vertical_bias=args.vertical_bias,
                                     zoom=args.zoom,
                                     static=args.static))
    print(f"[build] wrote {terminal_path}")

    # 3) neofetch info card
    stack = [s.strip() for s in args.stack.split(",") if s.strip()]
    stats = info.fetch_profile_stats(args.username, args.token)
    highlights = [h.strip() for h in args.highlights.split("|")] if args.highlights else None
    with open(info_path, "w", encoding="utf-8") as fh:
        fh.write(info.build_svg(args.username, stack, stats, role=args.role,
                                 bio_override=args.bio, highlights=highlights))
    print(f"[build] wrote {info_path}")

    # 4) README injection
    block = inject_readme.build_block(
        os.path.basename(terminal_path),
        os.path.basename(info_path),
        os.path.basename(contrib_path),
        heading=args.heading,
    )
    inject_readme.inject(args.readme, block, anchor=args.anchor)
    print(f"[build] updated {args.readme}")


if __name__ == "__main__":
    main()
