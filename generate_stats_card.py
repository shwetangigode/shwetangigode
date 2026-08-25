#!/usr/bin/env python3
"""
generate_stats_card.py
--------------------------------
Generates `stats-card.svg`: a self-contained GitHub stats + top-languages
panel, styled to match terminal-card.svg / info-card.svg.

Why this exists: third-party hosted stats badges (github-readme-stats
deployments, official or personal forks) are a single point of failure
outside your control -- when THEIR GitHub API token gets rate-limited,
your README shows a broken "Something went wrong" image, and there's
nothing you can do about it except wait or switch hosts (which just
moves the same risk elsewhere). This card fetches the same kind of data
directly, at generation time, in your own CI run, using your repo's own
GITHUB_TOKEN -- so it lives or dies with YOUR rate limit (5,000 req/hr
on GitHub Actions), not a stranger's shared deployment. It's also a
plain static SVG once generated, so there's no runtime dependency at
all when someone views your profile.

Data: public repo count, followers, following, total stars across
public repos, and a top-languages breakdown (by repo count -- avoids
the N extra API calls per-repo byte-accurate breakdown would need,
which matters on unauthenticated/rate-limited runs).

Falls back to safe placeholder numbers if the API is unreachable, so
the pipeline always finishes successfully, same as the other cards.
"""

from __future__ import annotations

import argparse
import os
from typing import List, Optional

import requests

WIDTH = 940
BG = "#0d1117"
WINDOW_BG = "#0b0f16"
WINDOW_STROKE = "#232a36"
CHROME_BG = "#161b22"
MUTED = "#586173"
WHITE = "#e6edf3"
CYAN = "#39e6ff"
ORANGE = "#ff8a3d"
GREEN = "#39ff88"
PURPLE = "#b06bff"
BLUE = "#4ea1ff"

LANG_COLORS = {
    "Java": ORANGE, "Python": CYAN, "JavaScript": "#f2e34c", "TypeScript": BLUE,
    "HTML": "#e34f26", "CSS": "#4ea1ff", "Shell": GREEN, "Go": "#00add8",
    "C++": PURPLE, "C": "#5c6bc0", "Ruby": "#cc342d", "PHP": "#8892be",
    "Kotlin": "#a97bff", "Rust": "#dea584", "C#": "#68217a",
}
FALLBACK_COLORS = [CYAN, GREEN, ORANGE, PURPLE, BLUE]


def fetch_stats(username: str, token: Optional[str]) -> dict:
    headers = {"Authorization": f"bearer {token}"} if token else {}
    defaults = {
        "public_repos": 11, "followers": 4, "following": 12,
        "stars": 3, "languages": [("Java", 6), ("Python", 3), ("JavaScript", 2)],
    }
    try:
        r = requests.get(f"https://api.github.com/users/{username}",
                          headers=headers, timeout=10)
        if not r.ok:
            return defaults
        profile = r.json()

        repos_resp = requests.get(
            f"https://api.github.com/users/{username}/repos?per_page=100&type=owner",
            headers=headers, timeout=10,
        )
        if not repos_resp.ok:
            # profile call succeeded but repos call didn't (e.g. rate limited
            # mid-flight) -- fall back for BOTH stars and languages together,
            # rather than silently computing stars=0 from an empty list.
            return {
                "public_repos": profile.get("public_repos", defaults["public_repos"]),
                "followers": profile.get("followers", defaults["followers"]),
                "following": profile.get("following", defaults["following"]),
                "stars": defaults["stars"],
                "languages": defaults["languages"],
            }
        repos = repos_resp.json()
        if not isinstance(repos, list):
            repos = []

        stars = sum(r.get("stargazers_count", 0) for r in repos if not r.get("fork"))
        lang_counts: dict = {}
        for r_ in repos:
            if r_.get("fork"):
                continue
            lang = r_.get("language")
            if lang:
                lang_counts[lang] = lang_counts.get(lang, 0) + 1
        languages = sorted(lang_counts.items(), key=lambda kv: -kv[1])[:5]
        if not languages:
            languages = defaults["languages"]

        return {
            "public_repos": profile.get("public_repos", defaults["public_repos"]),
            "followers": profile.get("followers", defaults["followers"]),
            "following": profile.get("following", defaults["following"]),
            "stars": stars,
            "languages": languages,
        }
    except Exception:  # noqa: BLE001
        return defaults


def xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def build_svg(username: str, stats: dict, streaks: dict = None) -> str:
    streaks = streaks or {"current_streak": 0, "longest_streak": 0}
    win_left, win_top = 12, 14
    win_w = WIDTH - win_left * 2

    metrics = [
        ("REPOS", stats["public_repos"], ORANGE),
        ("STARS", stats["stars"], CYAN),
        ("FOLLOWERS", stats["followers"], GREEN),
        ("FOLLOWING", stats["following"], PURPLE),
        ("STREAK", streaks["current_streak"], ORANGE),
        ("LONGEST", streaks["longest_streak"], CYAN),
    ]

    height = 260
    win_h = height - win_top - 14

    languages = stats["languages"]
    total = sum(c for _, c in languages) or 1
    max_count = max((c for _, c in languages), default=1)

    parts: List[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" '
        f'font-family="\'SF Mono\', \'Fira Code\', Consolas, monospace">'
    )

    parts.append("<defs>")
    parts.append(
        '<filter id="statGlow" x="-60%" y="-60%" width="220%" height="220%">'
        '<feGaussianBlur in="SourceGraphic" stdDeviation="2.4" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
        "</filter>"
    )
    parts.append(
        '<filter id="winShadow3" x="-30%" y="-30%" width="160%" height="180%">'
        '<feDropShadow dx="0" dy="10" stdDeviation="16" flood-color="#00e5ff" flood-opacity="0.10"/>'
        '<feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000000" flood-opacity="0.55"/>'
        "</filter>"
    )
    parts.append(
        f'<linearGradient id="chromeGrad3" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="#1c222d"/><stop offset="100%" stop-color="{CHROME_BG}"/>'
        f"</linearGradient>"
    )
    parts.append("</defs>")

    parts.append(f'<rect x="0" y="0" width="{WIDTH}" height="{height}" fill="{BG}"/>')
    parts.append(
        f'<g filter="url(#winShadow3)">'
        f'<rect x="{win_left}" y="{win_top}" width="{win_w}" height="{win_h}" rx="12" '
        f'fill="{WINDOW_BG}" stroke="{WINDOW_STROKE}" stroke-width="1.2"/>'
        f"</g>"
    )
    parts.append(
        f'<path d="M {win_left} {win_top + 28} L {win_left} {win_top + 12} '
        f'Q {win_left} {win_top} {win_left + 12} {win_top} '
        f'L {win_left + win_w - 12} {win_top} '
        f'Q {win_left + win_w} {win_top} {win_left + win_w} {win_top + 12} '
        f'L {win_left + win_w} {win_top + 28} Z" fill="url(#chromeGrad3)"/>'
    )
    parts.append(
        f'<line x1="{win_left}" y1="{win_top + 28}" x2="{win_left + win_w}" y2="{win_top + 28}" '
        f'stroke="{WINDOW_STROKE}" stroke-width="1"/>'
    )
    for i, color in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        cx = win_left + 20 + i * 18
        parts.append(f'<circle cx="{cx}" cy="{win_top + 14}" r="5.5" fill="{color}"/>')
    parts.append(
        f'<text x="{win_left + 62}" y="{win_top + 18}" font-size="10.5" fill="{MUTED}" '
        f'letter-spacing="0.3">{xml_escape(username)} — stats.live</text>'
    )

    # ---- metric counters row -------------------------------------------
    stagger = 0.08
    dur = 0.34
    mx = win_left + 36
    m_w = (win_w - 72) / len(metrics)
    for i, (label, value, color) in enumerate(metrics):
        cx = mx + i * m_w
        begin = round(i * stagger, 3)
        parts.append(
            f'<g opacity="0">'
            f'<animate attributeName="opacity" from="0" to="1" begin="{begin}s" '
            f'dur="{dur}s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" from="0 8" to="0 0" '
            f'begin="{begin}s" dur="{dur}s" fill="freeze" calcMode="spline" '
            f'keySplines="0.2 0.8 0.2 1"/>'
            f'<text x="{cx}" y="{win_top + 66}" font-size="26" font-weight="700" '
            f'fill="{color}" filter="url(#statGlow)">{value}</text>'
            f'<text x="{cx}" y="{win_top + 84}" font-size="10" fill="{MUTED}" '
            f'letter-spacing="0.5">{label}</text>'
            f"</g>"
        )

    parts.append(
        f'<line x1="{win_left + 24}" y1="{win_top + 104}" x2="{win_left + win_w - 24}" '
        f'y2="{win_top + 104}" stroke="{WINDOW_STROKE}" stroke-width="1"/>'
    )

    # ---- top languages bars ---------------------------------------------
    ly = win_top + 130
    parts.append(
        f'<text x="{win_left + 24}" y="{ly}" font-size="11" font-weight="700" fill="{BLUE}" '
        f'letter-spacing="0.5">TOP LANGUAGES</text>'
    )
    bar_x = win_left + 24
    bar_w_max = win_w - 260
    row_h = 22
    for i, (lang, count) in enumerate(languages):
        color = LANG_COLORS.get(lang, FALLBACK_COLORS[i % len(FALLBACK_COLORS)])
        y = ly + 20 + i * row_h
        pct = round(count / total * 100)
        bar_w = max(6, bar_w_max * (count / max_count))
        begin = round(0.3 + i * stagger, 3)
        parts.append(
            f'<g opacity="0">'
            f'<animate attributeName="opacity" from="0" to="1" begin="{begin}s" '
            f'dur="{dur}s" fill="freeze"/>'
            f'<text x="{bar_x}" y="{y}" font-size="11" fill="{WHITE}">{xml_escape(lang)}</text>'
            f'<rect x="{bar_x + 110}" y="{y - 10}" width="0" height="10" rx="3" fill="{color}">'
            f'<animate attributeName="width" from="0" to="{bar_w:.1f}" begin="{begin}s" '
            f'dur="0.5s" fill="freeze" calcMode="spline" keySplines="0.2 0.8 0.2 1"/>'
            f"</rect>"
            f'<text x="{bar_x + 110 + bar_w_max + 40}" y="{y}" font-size="10" fill="{MUTED}" '
            f'text-anchor="end">{pct}%</text>'
            f"</g>"
        )

    parts.append("</svg>")
    return "".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate stats-card.svg")
    ap.add_argument("--username", default="shwetangigode")
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    ap.add_argument("--out", default="stats-card.svg")
    args = ap.parse_args()

    stats = fetch_stats(args.username, args.token)

    # streaks come from the same contribution data used for the animated
    # calendar -- self-hosted, no third-party streak service involved.
    import generate_contribution_graph as contrib
    grid = None
    if args.token:
        grid = contrib.fetch_real_contributions(args.username, args.token)
    if grid is None:
        grid = contrib.generate_synthetic_contributions()
    streaks = contrib.compute_streaks(grid)

    svg = build_svg(args.username, stats, streaks)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"[stats] wrote {args.out} ({len(svg):,} bytes)")


if __name__ == "__main__":
    main()
