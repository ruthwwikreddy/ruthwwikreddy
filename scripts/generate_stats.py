#!/usr/bin/env python3
from __future__ import annotations
"""
generate_stats.py — fetch GitHub GraphQL data and emit four SVG graphics.

Output files (in repo root):
  stats.svg   — hero total contributions + weekly bar sparkline
  streak.svg  — current streak + longest streak with date ranges
  langs.svg   — top languages by bytes across public repos
  year.svg    — 365-day contribution grid, one char per day (ASCII ramp)

Design constraints:
  · stdlib only (urllib, json, datetime) — no third-party deps in CI
  · UTC window pinned to whole days (from = today-364d 00:00Z, to = today 23:59:59Z)
  · privacy: PUBLIC filter on repo queries — token-independent results
  · commit-only-on-change in the workflow (caller's responsibility)

Required env vars:
  GITHUB_TOKEN   — built-in secrets.GITHUB_TOKEN is sufficient
  GH_LOGIN       — GitHub username (set to github.repository_owner in CI)
"""

import base64
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT   = Path(__file__).parent.parent
FONTS  = ROOT / "fonts"

# ── visual constants ──────────────────────────────────────────────────────────
FILL_TEXT   = "#24292f"      # GitHub dark text
FILL_MUTED  = "#57606a"      # muted label
FILL_ACCENT = "#0969da"      # GitHub blue
FILL_BAR    = "#0969da"
FILL_BG     = "none"         # transparent — adapts to light/dark

RAMP = ' .`:-=+*cs#%@'

# ── font helpers ──────────────────────────────────────────────────────────────

def _b64(name: str) -> str | None:
    p = FONTS / name
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else None


def _font_face(b64: str, weight: int = 400) -> str:
    return (
        f"@font-face {{\n"
        f"  font-family: 'JBM';\n"
        f"  font-weight: {weight};\n"
        f"  src: url('data:font/woff2;base64,{b64}') format('woff2');\n"
        f"}}\n"
    )


# ── GraphQL helpers ───────────────────────────────────────────────────────────

def _gql(token: str, query: str, variables: dict) -> dict:
    payload = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "ruthwwikreddy-profile-generator/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
    if "errors" in body:
        sys.exit(f"GraphQL error: {body['errors']}")
    return body["data"]


STATS_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
    repositories(first: 100, privacy: PUBLIC, orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes {
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node { name color }
          }
        }
      }
    }
  }
}
"""


def fetch_data(token: str, login: str) -> dict:
    today = date.today()
    from_dt = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=timezone.utc)
    from_dt -= timedelta(days=364)
    to_dt   = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=timezone.utc)

    vars_ = {
        "login": login,
        "from":  from_dt.isoformat().replace("+00:00", "Z"),
        "to":    to_dt.isoformat().replace("+00:00", "Z"),
    }
    print(f"  fetching contributions {vars_['from']} → {vars_['to']}")
    return _gql(token, STATS_QUERY, vars_)


# ── stats.svg ─────────────────────────────────────────────────────────────────

def make_stats_svg(data: dict, b64_reg: str | None, b64_bold: str | None) -> str:
    coll     = data["user"]["contributionsCollection"]
    calendar = coll["contributionCalendar"]
    total    = calendar["totalContributions"]

    # weekly totals for sparkline
    weeks: list[int] = []
    for week in calendar["weeks"]:
        weeks.append(sum(d["contributionCount"] for d in week["contributionDays"]))

    # Keep last 52 weeks
    weeks = weeks[-52:]

    W, H      = 620, 100
    PAD_L     = 12
    PAD_R     = 12
    PAD_T     = 48      # room for hero number
    PAD_B     = 14
    bar_area_w = W - PAD_L - PAD_R
    bar_area_h = H - PAD_T - PAD_B
    n          = len(weeks)
    bar_w      = bar_area_w / n
    max_w      = max(weeks) if max(weeks) else 1
    gap        = max(bar_w * 0.15, 1)

    # font-face declarations
    faces = ""
    family = "monospace"
    if b64_reg:
        faces += _font_face(b64_reg, 400)
        family = "'JBM', monospace"
    if b64_bold:
        faces += _font_face(b64_bold, 700)

    bars = []
    for i, w in enumerate(weeks):
        bh  = max(2, (w / max_w) * bar_area_h)
        bx  = PAD_L + i * bar_w + gap / 2
        by  = PAD_T + bar_area_h - bh
        bw  = bar_w - gap
        bars.append(
            f'  <rect x="{bx:.2f}" y="{by:.2f}" width="{bw:.2f}" height="{bh:.2f}"'
            f' rx="1" fill="{FILL_BAR}" opacity="0.85"/>'
        )

    # Breakdown line
    commits  = coll["totalCommitContributions"]
    issues   = coll["totalIssueContributions"]
    prs      = coll["totalPullRequestContributions"]
    reviews  = coll["totalPullRequestReviewContributions"]
    breakdown = f"{commits} commits · {prs} PRs · {issues} issues · {reviews} reviews"

    svg = f"""\
<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <style>
      {faces}
      .hero  {{ font-family: {family}; font-size: 28px; font-weight: 700; fill: {FILL_TEXT}; }}
      .label {{ font-family: {family}; font-size: 11px; fill: {FILL_MUTED}; }}
    </style>
  </defs>
  <text class="hero" x="{PAD_L}" y="32">{total:,}</text>
  <text class="label" x="{PAD_L + 4}" y="44">contributions in the last year</text>
{"".join(bars)}
  <text class="label" x="{PAD_L}" y="{H - 2}">{breakdown}</text>
</svg>
"""
    return svg


# ── streak.svg ────────────────────────────────────────────────────────────────

def make_streak_svg(data: dict, b64_reg: str | None, b64_bold: str | None) -> str:
    days_flat: list[dict] = []
    for week in data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
        days_flat.extend(week["contributionDays"])

    # Streak calculation on the full sorted list
    days_flat.sort(key=lambda d: d["date"])

    current_streak = 0
    longest_streak = 0
    longest_start  = ""
    longest_end    = ""
    cur_start      = ""
    tmp            = 0

    for i, d in enumerate(days_flat):
        if d["contributionCount"] > 0:
            if tmp == 0:
                cur_start = d["date"]
            tmp += 1
            if tmp > longest_streak:
                longest_streak = tmp
                longest_start  = cur_start
                longest_end    = d["date"]
        else:
            tmp = 0

    # current streak: count backwards from the most recent day
    for d in reversed(days_flat):
        if d["contributionCount"] > 0:
            current_streak += 1
        else:
            break

    def fmt(s: str) -> str:
        if not s:
            return "—"
        dt = date.fromisoformat(s)
        return dt.strftime("%-d %b %Y")   # e.g. "5 Jan 2025"

    W, H = 620, 72
    PAD  = 14

    faces  = ""
    family = "monospace"
    if b64_reg:
        faces += _font_face(b64_reg, 400)
        family = "'JBM', monospace"
    if b64_bold:
        faces += _font_face(b64_bold, 700)

    col1_x = PAD
    col2_x = W // 2

    svg = f"""\
<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <style>
      {faces}
      .big   {{ font-family: {family}; font-size: 26px; font-weight: 700; fill: {FILL_TEXT}; }}
      .label {{ font-family: {family}; font-size: 11px; fill: {FILL_MUTED}; }}
      .range {{ font-family: {family}; font-size: 10px; fill: {FILL_MUTED}; }}
    </style>
  </defs>
  <!-- current streak -->
  <text class="big"  x="{col1_x}"      y="34">{current_streak}</text>
  <text class="label" x="{col1_x}"     y="50">current streak</text>

  <!-- longest streak -->
  <text class="big"  x="{col2_x}"      y="34">{longest_streak}</text>
  <text class="label" x="{col2_x}"     y="50">longest streak</text>
  <text class="range" x="{col2_x}"     y="64">{fmt(longest_start)} – {fmt(longest_end)}</text>

  <line x1="{W//2 - 20}" y1="8" x2="{W//2 - 20}" y2="{H-8}"
        stroke="#d0d7de" stroke-width="0.5"/>
</svg>
"""
    return svg


# ── langs.svg ─────────────────────────────────────────────────────────────────

def make_langs_svg(data: dict, b64_reg: str | None) -> str:
    lang_bytes: dict[str, int]   = {}
    lang_colors: dict[str, str]  = {}

    for repo in data["user"]["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name  = edge["node"]["name"]
            color = edge["node"]["color"] or FILL_MUTED
            lang_bytes[name]  = lang_bytes.get(name, 0) + edge["size"]
            lang_colors[name] = color

    if not lang_bytes:
        return ""

    total = sum(lang_bytes.values())
    ranked = sorted(lang_bytes.items(), key=lambda x: x[1], reverse=True)[:6]

    W, H   = 620, 90
    PAD    = 14
    BAR_H  = 8
    BAR_Y  = 36
    DOT_R  = 4

    # proportional bar segments
    bar_parts = []
    x = PAD
    bar_w = W - 2 * PAD
    for name, size in ranked:
        seg_w = (size / total) * bar_w
        color = lang_colors[name]
        bar_parts.append(
            f'  <rect x="{x:.1f}" y="{BAR_Y}" width="{seg_w:.1f}" height="{BAR_H}"'
            f' rx="2" fill="{color}"/>'
        )
        x += seg_w

    # legend dots + names + percentages
    faces  = ""
    family = "monospace"
    if b64_reg:
        faces += _font_face(b64_reg, 400)
        family = "'JBM', monospace"

    legend = []
    lx = PAD
    ly = BAR_Y + BAR_H + 20
    for name, size in ranked:
        pct   = (size / total) * 100
        color = lang_colors[name]
        legend.append(
            f'  <circle cx="{lx + DOT_R}" cy="{ly - DOT_R}" r="{DOT_R}" fill="{color}"/>'
            f'\n  <text x="{lx + DOT_R * 2 + 4}" y="{ly}" '
            f'style="font-family:{family};font-size:11px;fill:{FILL_MUTED}">'
            f'{name} {pct:.1f}%</text>'
        )
        lx += len(name) * 7.5 + 60   # rough advance
        if lx > W - 100:
            lx  = PAD
            ly += 18

    svg = f"""\
<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <style>
      {faces}
      .label {{ font-family: {family}; font-size: 11px; fill: {FILL_MUTED}; }}
    </style>
  </defs>
  <text class="label" x="{PAD}" y="20">top languages</text>
{"".join(bar_parts)}
{"".join(legend)}
</svg>
"""
    return svg


# ── year.svg ──────────────────────────────────────────────────────────────────

def make_year_svg(data: dict, b64_reg: str | None) -> str:
    """365-day contribution grid, one ASCII ramp character per day."""
    days_flat: list[dict] = []
    for week in data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
        days_flat.extend(week["contributionDays"])
    days_flat.sort(key=lambda d: d["date"])
    days_flat = days_flat[-365:]

    max_c = max((d["contributionCount"] for d in days_flat), default=1) or 1
    N     = len(RAMP)

    COLS     = 53          # weeks
    CHAR_W   = 7.74
    FONT_SZ  = 12.9
    LINE_H   = FONT_SZ * 1.2
    PAD_L    = 12
    PAD_T    = 26
    SVG_W    = int(PAD_L + COLS * CHAR_W + 12)
    ROWS     = 7
    SVG_H    = int(PAD_T + ROWS * LINE_H + 10)

    faces  = ""
    family = "monospace"
    if b64_reg:
        faces += _font_face(b64_reg, 400)
        family = "'JBM', monospace"

    # Build column strings (7 chars each, one per day of week)
    cols_chars: list[list[str]] = [[] for _ in range(COLS)]
    for i, d in enumerate(days_flat):
        col = i // 7
        if col >= COLS:
            break
        c    = d["contributionCount"]
        idx  = int((c / max_c) * (N - 1))
        char = RAMP[idx]
        cols_chars[col].append(char)

    # Render as a grid of text elements (one per row per week-column)
    texts = []
    for col_i, col_chars in enumerate(cols_chars):
        for row_i, ch in enumerate(col_chars):
            x = PAD_L + col_i * CHAR_W
            y = PAD_T + (row_i + 1) * LINE_H
            escaped = ch.replace("&", "&amp;").replace("<", "&lt;")
            texts.append(
                f'  <text x="{x:.1f}" y="{y:.1f}" '
                f'style="font-family:{family};font-size:{FONT_SZ}px;'
                f'fill:{FILL_MUTED};white-space:pre">{escaped}</text>'
            )

    svg = f"""\
<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_W}" height="{SVG_H}" viewBox="0 0 {SVG_W} {SVG_H}">
  <defs>
    <style>
      {faces}
      .label {{ font-family: {family}; font-size: 10px; fill: {FILL_MUTED}; }}
    </style>
  </defs>
  <text class="label" x="{PAD_L}" y="14">contributions — past year</text>
{"".join(texts)}
</svg>
"""
    return svg


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    token = os.environ.get("GITHUB_TOKEN")
    login = os.environ.get("GH_LOGIN", "ruthwwikreddy")

    data = None
    if token:
        try:
            print(f"Fetching stats for {login} via GraphQL…")
            data = fetch_data(token, login)
        except Exception as e:
            print(f"GraphQL request failed: {e}. Using fallback stats.")

    if not data:
        print("Using fallback stats template for local rendering.")
        # Minimal mock structure matching GQL response shape
        weeks = []
        for w in range(52):
            days = []
            for d in range(7):
                count = (w * 3 + d * 7) % 15 if (w + d) % 3 != 0 else 0
                days.append({"contributionCount": count, "date": f"2025-01-{(d+1):02d}"})
            weeks.append({"contributionDays": days})

        data = {
            "user": {
                "contributionsCollection": {
                    "totalCommitContributions": 340,
                    "totalIssueContributions": 12,
                    "totalPullRequestContributions": 45,
                    "totalPullRequestReviewContributions": 18,
                    "contributionCalendar": {
                        "totalContributions": 415,
                        "weeks": weeks
                    }
                },
                "repositories": {
                    "nodes": [
                        {"languages": {"edges": [{"size": 120000, "node": {"name": "HTML", "color": "#e34c26"}}, {"size": 85000, "node": {"name": "TypeScript", "color": "#3178c6"}}, {"size": 60000, "node": {"name": "CSS", "color": "#563d7c"}}, {"size": 40000, "node": {"name": "Python", "color": "#3572A5"}}]}}
                    ]
                }
            }
        }


    b64_reg  = _b64("body-regular.woff2")
    b64_bold = _b64("body-bold.woff2")
    if not b64_reg:
        print("Warning: fonts/body-regular.woff2 not found — using system monospace")

    print("Generating stats.svg…")
    (ROOT / "stats.svg").write_text(
        make_stats_svg(data, b64_reg, b64_bold), encoding="utf-8"
    )

    print("Generating streak.svg…")
    (ROOT / "streak.svg").write_text(
        make_streak_svg(data, b64_reg, b64_bold), encoding="utf-8"
    )

    print("Generating langs.svg…")
    langs_svg = make_langs_svg(data, b64_reg)
    if langs_svg:
        (ROOT / "langs.svg").write_text(langs_svg, encoding="utf-8")

    print("Generating year.svg…")
    (ROOT / "year.svg").write_text(
        make_year_svg(data, b64_reg), encoding="utf-8"
    )

    print("Done.")


if __name__ == "__main__":
    main()
