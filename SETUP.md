# Animated GitHub Profile — Setup

Self-contained SVGs, animated with pure SMIL (`<animate>` / `<animateTransform>`,
no CSS keyframes, no JS). They animate correctly on GitHub because a
repo-relative `<img src="...svg">` in a README is served as raw SVG, and
Chrome/Firefox/Safari all run SMIL inside `<img>` elements.

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

## 2. Generate everything + wire up README.md

```bash
python3 build_all.py --username YOUR_GITHUB_USERNAME
```

This writes, into the current directory:

- `github-contribution-animation.svg` — 53×7 contribution calendar, diagonal
  bottom-left → top-right reveal, per-cell white/green glint, neon glow on
  level 3+ cells.
- `terminal-card.svg` — your GitHub avatar rendered as dense ASCII art
  inside a macOS-style terminal, revealed row-by-row with a sweeping
  cursor, plus a `$ whoami` typewriter footer.
- `info-card.svg` — a neofetch-style stats panel (About / Stack /
  Highlights) with staggered slide-up + fade-in lines.
- `stats-card.svg` — a self-hosted GitHub stats + top-languages panel
  (repos, stars, followers, following, top 5 languages by repo count).
  Generated directly from the GitHub API at build time using your own
  `GITHUB_TOKEN`, so it never depends on a third-party service's uptime
  or rate limit the way hosted badge services (github-readme-stats,
  streak-stats, etc.) do.

...and it injects a table (`terminal-card.svg` + `info-card.svg` side by
side, `github-contribution-animation.svg` centered below) into
`README.md`, between `<!-- PROFILE-SVG:START -->` / `<!-- PROFILE-SVG:END -->`
markers. Re-running `build_all.py` updates the block in place — safe to
call repeatedly, including from CI. `stats-card.svg` is generated but
not auto-injected by this block — reference it in your README wherever
you want it, e.g. `<img src="stats-card.svg" width="100%" />`.

### Optional flags

```bash
python3 build_all.py \
  --username shwetangigode \
  --name "Shwetang Igode" \
  --token "$GITHUB_TOKEN" \
  --stack "Python,JavaScript,TypeScript,React,Node.js,Docker,PostgreSQL,AWS" \
  --readme README.md
```

- `--token` (or env var `GITHUB_TOKEN`) unlocks **real** contribution-graph
  data (GraphQL `contributionsCollection`) and real profile stats
  (repos / followers / following). Without it, the scripts fall back to a
  realistic synthetic contribution pattern and safe default stats — the
  pipeline always finishes successfully, even fully offline.
- `--name` skips the GitHub API name lookup for the terminal footer.
- `--stack` controls the tech-stack chips on the info card.
- `--role`, `--bio`, `--highlights` override the info-card's About/Highlights
  content instead of pulling from the GitHub API (`--highlights` takes
  pipe-separated `Label:Value` pairs, e.g.
  `"Award:Engineer of the Year|Perf:+80% throughput"`).
- `--anchor` — if `README.md` doesn't have the `PROFILE-SVG` markers yet,
  insert the new section immediately before this literal heading (e.g.
  `"## About Me"`) instead of appending it to the end of the file.
- `--local-image PATH` — use a local photo (e.g. a selfie) for the ASCII
  portrait instead of fetching the GitHub avatar. Combine with:
  - `--vertical-bias 0.0-1.0` — where the square crop sits on a portrait
    photo (0 = top-anchored, keeps more headroom below the face; 1 =
    bottom-anchored). Default `0.28`.
  - `--zoom 0.0-1.0` — keeps only the centered fraction of the crop, to
    trim a busy background (an office ceiling, etc.) that would otherwise
    turn into distracting ASCII noise. Default `1.0` (no trim).

  ```bash
  python3 build_all.py --username shwetangigode --name "Shwetangi Gode" \
    --local-image avatar.jpg --vertical-bias 0.15 --zoom 0.72
  ```

  The photo is auto-rotated per its EXIF orientation, center-cropped to a
  square, contrast-boosted, then run through the same ASCII pipeline as a
  fetched avatar. It is **not** embedded in the SVG as an image — only the
  derived ASCII text is, so the SVG stays self-contained.

- `--static` — the safest option. Never touches the network or any photo,
  not even your public GitHub avatar. Always renders the same
  deterministic, non-photographic cyberpunk avatar glyph for your
  username, so nothing personally identifying is ever derived or
  published. This is what the included GitHub Action uses by default.

  ```bash
  python3 build_all.py --username shwetangigode --name "Shwetangi Gode" --static
  ```

  `--static` takes precedence over `--local-image` and the default
  avatar fetch if more than one is somehow specified.

## 3. Run each generator independently (optional)

Every script also works standalone:

```bash
python3 generate_contribution_graph.py --username shwetangigode
python3 generate_terminal_card.py --username shwetangigode --name "Shwetang Igode"
python3 generate_info_card.py --username shwetangigode
python3 inject_readme.py
```

## 4. Keep it fresh automatically (optional)

Drop `.github/workflows/update-profile.yml` (included) into your profile
repo (`YOUR_USERNAME/YOUR_USERNAME`) to regenerate and commit the SVGs on
a schedule, using the repo's built-in `GITHUB_TOKEN`.

## Notes on the avatar fetch

`generate_terminal_card.py` downloads `https://github.com/<username>.png`.
If that host is unreachable (e.g. a locked-down network/CI sandbox with an
egress allowlist), it automatically falls back to a procedurally generated
portrait-shaped placeholder so the build never fails — just re-run it with
normal internet access to get the real avatar.
