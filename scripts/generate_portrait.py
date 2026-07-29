#!/usr/bin/env python3
from __future__ import annotations
"""
generate_portrait.py — converts photo.jpg into ascii.svg with a self-typing animation.

Pipeline (per the guide):
  1. rembg   — cut out background → white
  2. bilateral filter — smooth skin, keep edges
  3. CLAHE (clip≈3.0) — local contrast enhancement
  4. darkening curve (v/255)^1.7 — prevents washed-out faces
  5. map to ramp ' .`:-=+*cs#%@'
  6. emit SVG with per-row SMIL clip animation + embedded JetBrains Mono

Requirements:
    pip install pillow numpy opencv-python-headless rembg onnxruntime

Usage:
    python3 scripts/generate_portrait.py [--photo path/to/photo.jpg]

Output:
    ascii.svg  (in repo root)
"""

import argparse
import base64
import math
import sys
from pathlib import Path

ROOT   = Path(__file__).parent.parent
FONTS  = ROOT / "fonts"

# ── ramp ──────────────────────────────────────────────────────────────────────
RAMP = ' .`:-=+*cs#%@'    # index 0 = white (background), index -1 = black
N    = len(RAMP)           # 13

# ── geometry ──────────────────────────────────────────────────────────────────
COLS      = 90             # character columns
CHAR_W    = 7.74           # px  (JetBrains Mono 0.600 em at font-size 12.9)
FONT_SIZE = 12.9           # px
ASPECT    = 0.48           # monospace char height/width ≈ 0.48 after accounting for 2:1 cell ratio
SVG_DISPLAY_W = 460        # px — the width= we put on the <img> in README

# ── animation ─────────────────────────────────────────────────────────────────
ROW_STAGGER  = 0.09        # seconds between rows starting to type
CURSOR_CHAR  = "█"
CURSOR_COLOR = "#57606a"
TEXT_FILL    = "#57606a"


def load_font_b64() -> str | None:
    p = FONTS / "ramp.woff2"
    if not p.exists():
        return None
    return base64.b64encode(p.read_bytes()).decode()


def process_image(photo: Path) -> list[str]:
    """Full pipeline → list of strings, one per row, each len == COLS."""
    try:
        import cv2
        import numpy as np
        from PIL import Image
        from rembg import remove
    except ImportError as e:
        sys.exit(f"Missing dependency: {e}\nRun: pip install pillow numpy opencv-python-headless rembg onnxruntime")

    # ── 1. background removal ──────────────────────────────────────────────────
    print("  removing background…")
    with open(photo, "rb") as f:
        raw = f.read()
    bg_removed = remove(raw)

    img_pil = Image.open(__import__("io").BytesIO(bg_removed)).convert("RGBA")

    # Composite onto white
    white = Image.new("RGBA", img_pil.size, (255, 255, 255, 255))
    white.paste(img_pil, mask=img_pil.split()[3])
    img_rgb = white.convert("RGB")

    # ── 2. resize to target columns ───────────────────────────────────────────
    rows = max(1, int(COLS * (img_rgb.height / img_rgb.width) * ASPECT))
    img_small = img_rgb.resize((COLS, rows), Image.LANCZOS)

    img_cv = cv2.cvtColor(np.array(img_small), cv2.COLOR_RGB2BGR)

    # ── 3. bilateral filter ───────────────────────────────────────────────────
    img_cv = cv2.bilateralFilter(img_cv, d=5, sigmaColor=50, sigmaSpace=50)

    # ── 4. grayscale + CLAHE ──────────────────────────────────────────────────
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # ── 5. darkening curve ────────────────────────────────────────────────────
    lut = np.array([int(255 * (i / 255) ** 1.7) for i in range(256)], dtype=np.uint8)
    gray = lut[gray]

    # ── 6. map to ramp ────────────────────────────────────────────────────────
    # Invert: 0 (black pixel) → bright ramp end; 255 (white/bg) → space
    indices = ((255 - gray.astype(np.float32)) / 255.0 * (N - 1)).astype(np.int32)
    indices = np.clip(indices, 0, N - 1)

    lines = []
    for row in indices:
        lines.append("".join(RAMP[i] for i in row))

    return lines


def escape_xml(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_svg(lines: list[str], font_b64: str | None) -> str:
    rows     = len(lines)
    svg_w    = COLS * CHAR_W
    svg_h    = rows * FONT_SIZE * 1.2   # 1.2 line-height

    # Font declaration
    if font_b64:
        font_face = (
            f"    @font-face {{\n"
            f"      font-family: 'JBM';\n"
            f"      src: url('data:font/woff2;base64,{font_b64}') format('woff2');\n"
            f"    }}\n"
        )
        font_family = "'JBM', monospace"
    else:
        font_face   = ""
        font_family = "monospace"

    line_h = FONT_SIZE * 1.2

    parts: list[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg"')
    parts.append(f'     width="{SVG_DISPLAY_W}" height="{SVG_DISPLAY_W * (svg_h / svg_w):.0f}"')
    parts.append(f'     viewBox="0 0 {svg_w:.2f} {svg_h:.2f}">')
    parts.append(f'  <defs>')
    parts.append(f'    <style>')
    parts.append(f'{font_face}')
    parts.append(f'      text {{')
    parts.append(f'        font-family: {font_family};')
    parts.append(f'        font-size: {FONT_SIZE}px;')
    parts.append(f'        fill: {TEXT_FILL};')
    parts.append(f'        white-space: pre;')
    parts.append(f'      }}')
    parts.append(f'    </style>')

    # One clipPath per row — rect animates width 0→full at the row's Y position
    for i in range(rows):
        rect_y = i * line_h
        parts.append(f'    <clipPath id="r{i}">')
        parts.append(f'      <rect x="0" y="{rect_y:.2f}" width="0" height="{line_h * 1.2:.2f}">')
        # Main wipe
        begin = f"{i * ROW_STAGGER:.3f}s"
        dur   = f"{(COLS * 0.018):.2f}s"   # ~1.62 s to type full row at 90 cols
        parts.append(
            f'        <animate attributeName="width" from="0" to="{svg_w:.2f}"'
            f' begin="{begin}" dur="{dur}" fill="freeze"/>'
        )
        parts.append(f'      </rect>')
        parts.append(f'    </clipPath>')

    parts.append(f'  </defs>')

    # Text rows
    for i, line in enumerate(lines):
        y       = (i + 1) * line_h
        begin   = f"{i * ROW_STAGGER:.3f}s"
        parts.append(f'  <text x="0" y="{y:.2f}" clip-path="url(#r{i})">{escape_xml(line)}</text>')

    parts.append(f'</svg>')
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ascii.svg from photo.jpg")
    parser.add_argument("--photo", default=str(ROOT / "photo.jpg"),
                        help="Path to input photo (default: photo.jpg in repo root)")
    args = parser.parse_args()

    photo = Path(args.photo)
    if not photo.exists():
        print(f"Photo not found: {photo}")
        print("Drop your headshot as photo.jpg in the repo root, then re-run.")
        print("\nTips for best results:")
        print("  · Side-lit (window at ~45°, other lights off)")
        print("  · Tight crop chin→above-hair, filling the frame")
        print("  · 1200px+ resolution")
        print("  · Plain background")
        print("  · Slight angle, not dead-on")
        sys.exit(1)

    print(f"Processing {photo}…")
    lines = process_image(photo)
    print(f"  → {len(lines)} rows × {COLS} cols")

    font_b64 = load_font_b64()
    if font_b64 is None:
        print("Warning: fonts/ramp.woff2 not found — font will fall back to system monospace.")
        print("Run scripts/subset_font.py first for consistent cross-platform rendering.")

    print("Building SVG…")
    svg = build_svg(lines, font_b64)

    out = ROOT / "ascii.svg"
    out.write_text(svg, encoding="utf-8")
    size_kb = out.stat().st_size / 1024
    print(f"Written: {out}  ({size_kb:.1f} KB)")
    print(f"Animation duration: ~{(len(lines) - 1) * ROW_STAGGER + COLS * 0.018:.1f}s")
    print("\nVerify in a browser — wait for the animation to finish (fill=freeze, no loop).")


if __name__ == "__main__":
    main()
