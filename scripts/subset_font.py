#!/usr/bin/env python3
from __future__ import annotations
"""
subset_font.py — run once locally to produce the woff2 subsets used by the SVG generators.

Requirements:
    pip install fonttools brotli

Usage:
    python3 scripts/subset_font.py

Output (in fonts/):
    ramp.woff2       ~1.3 KB  — the 13 ASCII ramp characters
    headings.woff2   ~1.4 KB  — letters used in the three section headings
    body-regular.woff2  ~4.5 KB  — basic latin, regular
    body-bold.woff2     ~4.5 KB  — basic latin, bold (for stats numbers)
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
FONTS_DIR = ROOT / "fonts"
FONTS_DIR.mkdir(exist_ok=True)

REGULAR = FONTS_DIR / "JetBrainsMono-Regular.ttf"
BOLD    = FONTS_DIR / "JetBrainsMono-Bold.ttf"

SUBSETS = [
    # (output_name, source_ttf, text_or_unicodes, description)
    (
        "ramp.woff2",
        REGULAR,
        " .`:-=+*cs#%@",
        "13 ASCII ramp characters for the portrait",
    ),
    (
        "headings.woff2",
        REGULAR,
        "aboutstckprjec",   # unique letters in "about" "stack" "projects"
        "Section heading labels",
    ),
    (
        "body-regular.woff2",
        REGULAR,
        None,               # None → basic latin unicode range
        "Body text, regular weight",
    ),
    (
        "body-bold.woff2",
        BOLD,
        None,
        "Body text, bold weight (stats numbers)",
    ),
]

LATIN_RANGE = ",".join(str(i) for i in range(0x20, 0x7F))  # U+0020–U+007E


def subset(output_name: str, source: Path, text: str | None, desc: str) -> None:
    if not source.exists():
        print(f"  SKIP  {output_name} — source not found: {source}")
        return

    out = FONTS_DIR / output_name
    cmd = [
        sys.executable, "-m", "fonttools", "subset",
        str(source),
        "--flavor=woff2",
        "--layout-features=",
        "--no-hinting",
        f"--output-file={out}",
    ]

    if text is not None:
        # escape for shell safety — pass via file instead
        txt_file = FONTS_DIR / "_tmp_text.txt"
        txt_file.write_text(text, encoding="utf-8")
        cmd.append(f"--text-file={txt_file}")
    else:
        cmd.append(f"--unicodes={LATIN_RANGE}")

    print(f"  subsetting → {output_name}  ({desc})")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)

    if text is not None:
        (FONTS_DIR / "_tmp_text.txt").unlink(missing_ok=True)

    size_kb = out.stat().st_size / 1024
    print(f"           ✓ {out.name}  {size_kb:.1f} KB")


def main() -> None:
    print("JetBrains Mono subset generator")
    print("=" * 40)

    for name, src, text, desc in SUBSETS:
        subset(name, src, text, desc)

    print()
    print("Done. Commit the fonts/ directory.")
    print("Do NOT commit the source .ttf files — they're large and the")
    print("woff2 subsets are what the SVG generators embed.")


if __name__ == "__main__":
    main()
