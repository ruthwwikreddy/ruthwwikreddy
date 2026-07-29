#!/usr/bin/env python3
from __future__ import annotations
"""
generate_headers.py — emit hd-about.svg, hd-stack.svg, hd-projects.svg.

Produces: lowercase mono label + hairline rule extending to right edge,
in the same visual language as the portrait (JetBrains Mono, dark fill).
Run locally after subset_font.py, and again in CI (no heavy dependencies).
"""

import base64
from pathlib import Path

ROOT = Path(__file__).parent.parent
FONTS_DIR = ROOT / "fonts"

# Display dimensions (must match README img width=)
SVG_W = 620
SVG_H = 28

FONT_SIZE = 13        # px
LABEL_X   = 0
LABEL_Y   = 18        # baseline
RULE_Y    = 14        # middle of the rule line
RULE_GAP  = 10        # gap between label end and rule start

# Match portrait fill colour (neutral dark, works light & dark mode via GitHub's inversion)
FILL = "#57606a"      # GitHub's muted text colour — legible on both themes
RULE_COLOR = "#d0d7de"


def load_font_b64(name: str) -> str | None:
    path = FONTS_DIR / name
    if not path.exists():
        return None
    return base64.b64encode(path.read_bytes()).decode()


def make_svg(label: str, font_b64: str | None) -> str:
    if font_b64:
        font_face = (
            f"  @font-face {{\n"
            f"    font-family: 'JetBrainsMono';\n"
            f"    font-weight: 400;\n"
            f"    src: url('data:font/woff2;base64,{font_b64}') format('woff2');\n"
            f"  }}\n"
        )
        font_family = "JetBrainsMono, monospace"
    else:
        font_family = "monospace"
        font_face = ""

    # Estimate label width: JetBrains Mono 600/1000 advance → 0.6 * font_size * len
    char_w = FONT_SIZE * 0.600
    label_w = len(label) * char_w
    rule_start = LABEL_X + label_w + RULE_GAP

    svg = f"""\
<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_W}" height="{SVG_H}" viewBox="0 0 {SVG_W} {SVG_H}">
  <defs>
    <style>
{font_face}\
      text {{
        font-family: {font_family};
        font-size: {FONT_SIZE}px;
        fill: {FILL};
        font-weight: 400;
      }}
    </style>
  </defs>
  <text x="{LABEL_X}" y="{LABEL_Y}">{label}</text>
  <line x1="{rule_start:.1f}" y1="{RULE_Y}" x2="{SVG_W}" y2="{RULE_Y}"
        stroke="{RULE_COLOR}" stroke-width="0.5"/>
</svg>
"""
    return svg


HEADINGS = {
    "hd-about.svg":    "about",
    "hd-stack.svg":    "stack",
    "hd-projects.svg": "projects",
}


def main() -> None:
    font_b64 = load_font_b64("headings.woff2")
    if font_b64 is None:
        print("Warning: fonts/headings.woff2 not found — falling back to system monospace.")
        print("Run scripts/subset_font.py first for pixel-perfect rendering.")

    for filename, label in HEADINGS.items():
        svg = make_svg(label, font_b64)
        out = ROOT / filename
        out.write_text(svg, encoding="utf-8")
        print(f"wrote {filename}")

    print("Done.")


if __name__ == "__main__":
    main()
