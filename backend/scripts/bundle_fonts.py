"""Bundle and install curated OFL/Apache open-licence fonts for ClubDocs Studio.

Downloads:
- Formal serif: Tinos, Merriweather, Playfair Display
- Modern sans: Roboto, Open Sans, Montserrat
- Mono: Roboto Mono
- Indic: Noto Sans Devanagari, Noto Sans Gujarati

Places fonts in:
1. assets/fonts/
2. frontend/public/fonts/
3. Windows user fonts directory (C:\\Users\\<user>\\AppData\\Local\\Microsoft\\Windows\\Fonts)
"""

from __future__ import annotations

import os
import pathlib
import shutil
import urllib.request

FONTS = {
    # Formal serif
    "Tinos-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/tinos/Tinos-Regular.ttf",
    "Tinos-Bold.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/tinos/Tinos-Bold.ttf",
    "Merriweather-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/merriweather/Merriweather%5Bopsz%2Cwdth%2Cwght%5D.ttf",
    "PlayfairDisplay-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
    # Modern sans
    "Roboto-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/roboto/Roboto%5Bwdth%2Cwght%5D.ttf",
    "OpenSans-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/opensans/OpenSans%5Bwdth%2Cwght%5D.ttf",
    "Montserrat-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf",
    # Monospace
    "RobotoMono-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/robotomono/RobotoMono%5Bwght%5D.ttf",
    # Indic languages
    "NotoSansDevanagari-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansdevanagari/NotoSansDevanagari%5Bwdth%2Cwght%5D.ttf",
    "NotoSansGujarati-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansgujarati/NotoSansGujarati%5Bwdth%2Cwght%5D.ttf",
}

LICENSES_TEXT = """# Open Font Licenses (OFL / Apache 2.0)

All fonts bundled in SVNIT ClubDocs Studio are distributed under permissive open licenses:

- **Tinos**: SIL Open Font License (OFL), Version 1.1
- **Merriweather**: SIL Open Font License (OFL), Version 1.1
- **Playfair Display**: SIL Open Font License (OFL), Version 1.1
- **Roboto**: SIL Open Font License (OFL), Version 1.1 / Apache License 2.0
- **Open Sans**: SIL Open Font License (OFL), Version 1.1
- **Montserrat**: SIL Open Font License (OFL), Version 1.1
- **Roboto Mono**: SIL Open Font License (OFL), Version 1.1
- **Noto Sans Devanagari**: SIL Open Font License (OFL), Version 1.1
- **Noto Sans Gujarati**: SIL Open Font License (OFL), Version 1.1

All fonts are self-hosted within the repository and application packages. No external CDN requests are made at runtime.
"""


def bundle_fonts():
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    assets_dir = repo_root / "assets" / "fonts"
    assets_dir.mkdir(parents=True, exist_ok=True)

    web_fonts_dir = repo_root.parent / "frontend" / "public" / "fonts"
    web_fonts_dir.mkdir(parents=True, exist_ok=True)

    user_fonts_dir = None
    if "USERPROFILE" in os.environ:
        user_fonts_dir = (
            pathlib.Path(os.environ["USERPROFILE"])
            / "AppData"
            / "Local"
            / "Microsoft"
            / "Windows"
            / "Fonts"
        )
        user_fonts_dir.mkdir(parents=True, exist_ok=True)

    # Write license file
    (assets_dir / "FONTS_LICENSES.md").write_text(LICENSES_TEXT, encoding="utf-8")

    print(f"Downloading {len(FONTS)} curated open-licence fonts...")
    for filename, url in FONTS.items():
        dest = assets_dir / filename
        if not dest.exists() or dest.stat().st_size == 0:
            print(f"  Fetching {filename}...")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                dest.write_bytes(data)
        else:
            print(f"  Cached {filename} ({dest.stat().st_size} bytes)")

        # Copy to frontend/public/fonts/
        shutil.copy2(dest, web_fonts_dir / filename)

        # Copy to Windows user fonts dir if on Windows
        if user_fonts_dir and user_fonts_dir.exists():
            try:
                shutil.copy2(dest, user_fonts_dir / filename)
            except Exception as e:
                print(f"  Note: Could not copy {filename} to user fonts: {e}")

    print("All fonts bundled successfully!")


if __name__ == "__main__":
    bundle_fonts()
