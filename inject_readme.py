#!/usr/bin/env python3
"""
inject_readme.py
--------------------------------
Injects the generated SVGs into README.md:
  - terminal-card.svg + info-card.svg side-by-side in an HTML <table>
  - github-contribution-animation.svg centered underneath

Idempotent: re-running updates the block in place (delimited by HTML
comments) instead of duplicating it, so this is safe to call from CI
on every push.
"""

from __future__ import annotations

import argparse
import os

START_MARKER = "<!-- PROFILE-SVG:START -->"
END_MARKER = "<!-- PROFILE-SVG:END -->"

DEFAULT_README_HEADER = """# Hi there 👋

"""


def build_block(terminal_svg: str, info_svg: str, contrib_svg: str, heading: str = None) -> str:
    heading_md = f"{heading}\n\n" if heading else ""
    return (
        f"{START_MARKER}\n"
        f"{heading_md}"
        f"<table>\n"
        f"<tr>\n"
        f'<td valign="top"><img src="{terminal_svg}" alt="ASCII Portrait Terminal" /></td>\n'
        f'<td valign="top"><img src="{info_svg}" alt="Neofetch Info Card" /></td>\n'
        f"</tr>\n"
        f"</table>\n"
        f"\n"
        f'<p align="center">\n'
        f'  <img src="{contrib_svg}" alt="Contribution Graph" width="100%" />\n'
        f"</p>\n"
        f"{END_MARKER}"
    )


def inject(readme_path: str, block: str, anchor: str = None) -> None:
    """Insert/replace `block` in the README.

    - If the START/END markers already exist, the content between them is
      replaced in place (idempotent re-runs, e.g. from CI).
    - Otherwise, if `anchor` (a literal substring, typically a heading
      like "## About Me") is found, the block is inserted immediately
      before it -- handy for dropping the section into a specific spot
      in an existing, hand-crafted README instead of tacking it onto
      the end.
    - Otherwise, the block is appended to the end of the file.
    """
    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as fh:
            content = fh.read()
    else:
        content = DEFAULT_README_HEADER

    if START_MARKER in content and END_MARKER in content:
        pre = content.split(START_MARKER)[0]
        post = content.split(END_MARKER)[1]
        new_content = pre + block + post
    elif anchor and anchor in content:
        pre, post = content.split(anchor, 1)
        pre = pre.rstrip("\n")
        new_content = f"{pre}\n\n{block}\n\n---\n\n{anchor}{post}"
    else:
        sep = "\n\n" if content and not content.endswith("\n\n") else ""
        new_content = content + sep + block + "\n"

    with open(readme_path, "w", encoding="utf-8") as fh:
        fh.write(new_content)


def main() -> None:
    ap = argparse.ArgumentParser(description="Inject SVG cards into README.md")
    ap.add_argument("--readme", default="README.md")
    ap.add_argument("--terminal-svg", default="terminal-card.svg")
    ap.add_argument("--info-svg", default="info-card.svg")
    ap.add_argument("--contrib-svg", default="github-contribution-animation.svg")
    ap.add_argument(
        "--anchor",
        default=None,
        help="If markers aren't found yet, insert the block right before this "
             "literal heading/text instead of appending to the end of the file.",
    )
    ap.add_argument("--heading", default="## 🖥️ Terminal Portrait & Live Stats",
                     help="Heading placed above the injected block")
    args = ap.parse_args()

    block = build_block(args.terminal_svg, args.info_svg, args.contrib_svg, heading=args.heading)
    inject(args.readme, block, anchor=args.anchor)
    print(f"[readme] updated {args.readme}")


if __name__ == "__main__":
    main()
