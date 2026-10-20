"""Club letterhead banner for letter-style system templates.

System templates carry a placeholder banner image (``club_banner_placeholder.png``) in their
header. At render time it is replaced with the club's own banner: an uploaded banner when the
club has one, otherwise a banner composed here in the institute's house style
(institute crest left, club name and institute line centred, club logo right).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

PLACEHOLDER_NAME = "club_banner_placeholder.png"
BANNER_SIZE = (2550, 348)
TITLE_COLOR = (79, 129, 189)

_ROOT = Path(__file__).resolve().parent.parent
_ASSETS = _ROOT / "assets"
_FONT_REGULAR = _ASSETS / "fonts" / "Tinos-Regular.ttf"
_FONT_BOLD = _ASSETS / "fonts" / "Tinos-Bold.ttf"
DEFAULT_CREST = _ASSETS / "svnit_crest.png"


def _font(path: Path, size: int):
    from PIL import ImageFont

    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default()


def _fit_font(draw, text: str, path: Path, start: int, max_width: int, min_size: int = 34):
    size = start
    while size > min_size:
        font = _font(path, size)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 4
    return _font(path, min_size)


def _paste_logo(canvas, logo_path: Optional[Path], box: tuple[int, int, int, int]) -> None:
    from PIL import Image

    if not logo_path or not Path(logo_path).exists():
        return
    try:
        logo = Image.open(logo_path).convert("RGBA")
    except OSError:
        return
    x0, y0, x1, y1 = box
    logo.thumbnail((x1 - x0, y1 - y0))
    x = x0 + (x1 - x0 - logo.width) // 2
    y = y0 + (y1 - y0 - logo.height) // 2
    canvas.paste(logo, (x, y), logo)


def _rgb(color: Optional[str]) -> tuple[int, int, int]:
    value = (color or "").strip().lstrip("#")
    if len(value) == 6:
        try:
            return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
        except ValueError:
            pass
    return TITLE_COLOR


def compose_banner(
    out_path: Path,
    title: str,
    subtitle: str,
    crest_path: Optional[Path] = DEFAULT_CREST,
    logo_path: Optional[Path] = None,
    color: Optional[str] = None,
) -> Path:
    """Draw a banner PNG and return its path."""
    from PIL import Image, ImageDraw

    width, height = BANNER_SIZE
    canvas = Image.new("RGBA", BANNER_SIZE, (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    side = 220  # logo slots at both ends
    _paste_logo(canvas, crest_path, (110, 40, 110 + side, height - 40))
    _paste_logo(canvas, logo_path, (width - 110 - side, 40, width - 110, height - 40))

    text_width = width - 2 * (110 + side + 60)
    title_font = _fit_font(draw, title, _FONT_REGULAR, 82, text_width)
    sub_font = _fit_font(draw, subtitle, _FONT_BOLD, 40, text_width, min_size=24)
    fill = _rgb(color)
    draw.text((width / 2, 140), title, font=title_font, fill=fill, anchor="mm")
    draw.text((width / 2, 235), subtitle, font=sub_font, fill=fill, anchor="mm")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, "PNG")
    return out_path


def club_banner_path(
    cache_dir: Path,
    club_name: str,
    institute_name: str,
    uploaded_banner: Optional[str] = None,
    logo_path: Optional[str] = None,
    color: Optional[str] = None,
) -> Path:
    """The banner to use for a club: its uploaded banner, else a cached composed one."""
    if uploaded_banner and Path(uploaded_banner).exists():
        return Path(uploaded_banner)
    title = (club_name or "Club").upper()
    subtitle = (institute_name or "").split("(")[0].strip().upper()
    logo = Path(logo_path) if logo_path else None
    logo_sig = ""
    if logo and logo.exists():
        logo_sig = hashlib.sha256(logo.read_bytes()).hexdigest()[:16]
    key = hashlib.sha256(f"v2|{title}|{subtitle}|{logo_sig}|{color}".encode()).hexdigest()[:24]
    target = cache_dir / f"banner_{key}.png"
    if not target.exists():
        compose_banner(target, title, subtitle, DEFAULT_CREST, logo, color)
    return target
