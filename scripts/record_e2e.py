"""Screen Recording & Artifact Generator for E2E Document Generation Journey.
Stitches captured screenshots into an animated GIF with comfortable reading pacing.
"""

from __future__ import annotations

import os
from pathlib import Path
from PIL import Image

SCREENSHOTS_DIR = Path("docs/screenshots/w3_slice")
OUTPUT_GIF = SCREENSHOTS_DIR / "e2e_walkthrough.gif"


def compile_gif():
    images = []
    screenshot_files = sorted(list(SCREENSHOTS_DIR.glob("*.png")))
    if not screenshot_files:
        print("[!] No screenshots found in docs/screenshots/w3_slice/")
        return

    print("=" * 60)
    print("SVNIT CLUBSDOCS - E2E SCREENSHOT ARTIFACTS")
    print("=" * 60)

    for f in screenshot_files:
        img = Image.open(f)
        images.append(img.convert("RGB"))
        size_kb = f.stat().st_size / 1024
        print(f"  {f.name:<45} {img.width}x{img.height} ({size_kb:.1f} KB)")

    # Save animated GIF: 2500ms per slide, loop forever
    if images:
        images[0].save(
            str(OUTPUT_GIF),
            save_all=True,
            append_images=images[1:],
            duration=2500,
            loop=0,
            optimize=True,
        )
        gif_size_kb = OUTPUT_GIF.stat().st_size / 1024
        print("-" * 60)
        print(f"Created walkthrough GIF: {OUTPUT_GIF} ({gif_size_kb:.1f} KB)")
        print("=" * 60)


if __name__ == "__main__":
    compile_gif()
