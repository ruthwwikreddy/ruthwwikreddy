#!/usr/bin/env python3
from __future__ import annotations
"""
generate_portrait_from_png.py — ultra-crisp 16:9 video aspect ratio ASCII portrait generator.

Generates a sharp, 16:9 widescreen animated ASCII SVG (110 cols x 31 rows)
from pre-rendered ASCII images using contrast enhancement and top-k intensity pooling.
"""

import argparse
import base64
import sys
from pathlib import Path

ROOT  = Path(__file__).parent.parent
FONTS = ROOT / "fonts"

# ── ramp ─────────────────────────────────────────────────────────────────────
RAMP = ' .:`-+*?s#%@$'
N    = len(RAMP)

# ── geometry ─────────────────────────────────────────────────────────────────
COLS          = 110
CHAR_W        = 7.74      # JetBrains Mono 0.600 em at font-size 12.9
FONT_SIZE     = 12.9
LINE_H_RATIO  = 1.2
# 31 rows gives an EXACT 16:9 widescreen video ratio for 110 columns!
TARGET_ROWS   = 31
SVG_DISPLAY_W = 460       # README display width (height will scale to ~259px for 16:9)

# ── animation ────────────────────────────────────────────────────────────────
ROW_STAGGER  = 0.04        # seconds between rows
TYPE_SPEED   = 0.010       # seconds per character
TEXT_FILL    = "#57606a"


def load_font_b64() -> str | None:
    p = FONTS / "ramp.woff2"
    if not p.exists():
        return None
    return base64.b64encode(p.read_bytes()).decode()


def image_to_lines(photo: Path) -> list[str]:
    try:
        from PIL import Image, ImageEnhance
    except ImportError:
        sys.exit("Missing dependency: pillow\nRun: pip install pillow")

    img_raw = Image.open(photo).convert("L")

    # Enhance contrast for crisp features
    enhancer = ImageEnhance.Contrast(img_raw)
    img = enhancer.enhance(1.6)

    rows = TARGET_ROWS

    block_w = img.width / COLS
    block_h = img.height / rows

    lines = []
    for r in range(rows):
        row_chars = []
        y1 = int(r * block_h)
        y2 = int((r + 1) * block_h)
        for c in range(COLS):
            x1 = int(c * block_w)
            x2 = int((c + 1) * block_w)
            box = img.crop((x1, y1, x2, y2))
            
            box_bytes = box.tobytes()
            sorted_pixels = sorted(box_bytes, reverse=True)
            top_k = max(1, len(sorted_pixels) // 3)
            val = sum(sorted_pixels[:top_k]) / top_k

            idx = int((val / 255.0) * (N - 1))
            idx = max(0, min(N - 1, idx))
            row_chars.append(RAMP[idx])
        lines.append("".join(row_chars))

    return lines


def escape_xml(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_svg(lines: list[str], font_b64: str | None) -> str:
    rows   = len(lines)
    svg_w  = COLS * CHAR_W
    svg_h  = rows * FONT_SIZE * LINE_H_RATIO
    line_h = FONT_SIZE * LINE_H_RATIO

    if font_b64:
        face = (
            f"    @font-face {{\n"
            f"      font-family: 'JBM';\n"
            f"      src: url('data:font/woff2;base64,{font_b64}') format('woff2');\n"
            f"    }}\n"
        )
        family = "'JBM', monospace"
    else:
        face   = ""
        family = "monospace"

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg"'
        f' width="{SVG_DISPLAY_W}"'
        f' height="{SVG_DISPLAY_W * (9 / 16):.0f}"'
        f' viewBox="0 0 {svg_w:.2f} {svg_h:.2f}">'
    )
    parts.append("  <defs>")
    parts.append("    <style>")
    parts.append(face)
    parts.append(f"      text {{ font-family: {family}; font-size: {FONT_SIZE}px;"
                 f" fill: {TEXT_FILL}; white-space: pre; }}")
    parts.append("    </style>")

    # Per-row clip paths — rect width wipes from 0 → full at the row's Y position
    for i in range(rows):
        begin = f"{i * ROW_STAGGER:.3f}s"
        dur   = f"{COLS * TYPE_SPEED:.2f}s"
        rect_y = i * line_h
        parts.append(f'    <clipPath id="r{i}">')
        parts.append(f'      <rect x="0" y="{rect_y:.2f}" width="0" height="{line_h * 1.2:.2f}">')
        parts.append(
            f'        <animate attributeName="width"'
            f' from="0" to="{svg_w:.2f}"'
            f' begin="{begin}" dur="{dur}" fill="freeze"/>'
        )
        parts.append("      </rect>")
        parts.append("    </clipPath>")

    parts.append("  </defs>")

    for i, line in enumerate(lines):
        y = (i + 1) * line_h
        parts.append(
            f'  <text x="0" y="{y:.2f}" clip-path="url(#r{i})">'
            f'{escape_xml(line)}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--photo",
        default=str(ROOT / "images" / "ascii-elite-1785349479576.png"),
        help="Path to input ASCII-art PNG",
    )
    args = parser.parse_args()

    photo = Path(args.photo)
    if not photo.exists():
        sys.exit(f"File not found: {photo}")

    print(f"Processing {photo.name} …")
    lines = image_to_lines(photo)
    print(f"  → {len(lines)} rows × {COLS} cols (16:9 ratio)")

    font_b64 = load_font_b64()

    print("Building 16:9 SVG …")
    svg = build_svg(lines, font_b64)

    out = ROOT / "ascii.svg"
    out.write_text(svg, encoding="utf-8")
    print(f"  ✓ {out} ({out.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
