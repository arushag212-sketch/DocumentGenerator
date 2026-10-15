"""Update the SVNIT college logo with the high-resolution emblem and white underlay."""

from __future__ import annotations

import shutil
from pathlib import Path
from PIL import Image
import numpy as np

SOURCE_LOGO = Path("C:/Users/OMEN/.gemini/antigravity/brain/3ebb8e3b-8186-493b-b7be-618987052f30/.user_uploaded/media_1791993531017_fdd6cac2.png")

def process_and_save_logo():
    if not SOURCE_LOGO.exists():
        raise FileNotFoundError(f"Source logo not found at {SOURCE_LOGO}")

    print(f"Loading source logo from {SOURCE_LOGO}...")
    src = Image.open(SOURCE_LOGO).convert("RGBA")
    
    # Process image: ensure any transparent/semi-transparent background blends over white
    # so that transparent pixels have RGB=(255, 255, 255) instead of black (0, 0, 0)
    arr = np.array(src, dtype=np.float32)
    alpha = arr[:, :, 3:] / 255.0
    arr[:, :, :3] = arr[:, :, :3] * alpha + 255.0 * (1.0 - alpha)
    
    clean_rgba = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    targets = [
        Path("assets/svnit_crest.png"),
        Path("assets/permission_page1_img1.png"),
        Path("web/dist/assets/svnit_crest.png"),
        Path("web/dist/assets/permission_page1_img1.png"),
        Path("storage/assets/permission_page1_img1.png"),
        Path("storage/assets/svnit_crest.png"),
    ]

    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        clean_rgba.save(target, format="PNG")
        print(f"  [OK] Saved clean logo to: {target} ({clean_rgba.size[0]}x{clean_rgba.size[1]})")

if __name__ == "__main__":
    process_and_save_logo()
