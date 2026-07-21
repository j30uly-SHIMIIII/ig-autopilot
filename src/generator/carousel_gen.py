"""Carousel image generator: solid-background slides + Japanese headline text.

Phase 1 uses a placeholder template (single background color, no imagery).
Each slide is rendered at 1080x1350 (IG portrait ratio) with the headline
centered and wrapped character-by-character (CJK text has no word spaces).
If the text doesn't fit the safe area at the largest font size, the font
size is stepped down until it fits or the minimum size is reached.
"""
from __future__ import annotations

from datetime import date as date_cls
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = REPO_ROOT / "config" / "templates" / "fonts"
FONT_REGULAR = FONT_DIR / "NotoSansJP-Regular.otf"
FONT_BOLD = FONT_DIR / "NotoSansJP-Bold.otf"
DATA_DIR = REPO_ROOT / "data"

SLIDE_WIDTH = 1080
SLIDE_HEIGHT = 1350
MAX_SLIDES = 10

DEFAULT_BACKGROUND_COLOR = (17, 24, 39)   # dark navy
DEFAULT_TEXT_COLOR = (255, 255, 255)

_MAX_FONT_SIZE = 96
_MIN_FONT_SIZE = 28
_FONT_STEP = 4
_LINE_SPACING = 1.35


def default_output_dir(for_date: date_cls | None = None) -> Path:
    for_date = for_date or date_cls.today()
    return DATA_DIR / "generated" / for_date.isoformat()


def _wrap_by_char(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for ch in text:
        if ch == "\n":
            lines.append(current)
            current = ""
            continue
        trial = current + ch
        width = draw.textbbox((0, 0), trial, font=font)[2]
        if width > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = trial
    lines.append(current)
    return lines


def _line_height(font: ImageFont.FreeTypeFont) -> int:
    ascent, descent = font.getmetrics()
    return int((ascent + descent) * _LINE_SPACING)


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: Path,
    max_width: int,
    max_height: int,
) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """Find the largest font size (within bounds) whose wrapped text fits the box."""
    last_font, last_lines = None, None
    for size in range(_MAX_FONT_SIZE, _MIN_FONT_SIZE - 1, -_FONT_STEP):
        font = ImageFont.truetype(str(font_path), size)
        lines = _wrap_by_char(draw, text, font, max_width)
        if _line_height(font) * len(lines) <= max_height:
            return font, lines
        last_font, last_lines = font, lines
    # Nothing fit within max_height even at the minimum size; return the
    # smallest rendering rather than raising, so a pipeline run can proceed.
    return last_font, last_lines


def render_slide(
    text: str,
    *,
    width: int = SLIDE_WIDTH,
    height: int = SLIDE_HEIGHT,
    background_color: tuple[int, int, int] = DEFAULT_BACKGROUND_COLOR,
    text_color: tuple[int, int, int] = DEFAULT_TEXT_COLOR,
    font_path: Path = FONT_REGULAR,
) -> Image.Image:
    if not font_path.exists():
        raise FileNotFoundError(f"Font not found: {font_path}")

    image = Image.new("RGB", (width, height), background_color)
    draw = ImageDraw.Draw(image)

    padding_x = int(width * 0.12)
    padding_y = int(height * 0.12)
    max_width = width - padding_x * 2
    max_height = height - padding_y * 2

    font, lines = _fit_text(draw, text, font_path, max_width, max_height)
    line_height = _line_height(font)
    total_height = line_height * len(lines)
    y = (height - total_height) // 2

    for line in lines:
        line_width = draw.textbbox((0, 0), line, font=font)[2]
        x = (width - line_width) // 2
        draw.text((x, y), line, font=font, fill=text_color)
        y += line_height

    return image


def generate_carousel(
    headlines: Sequence[str],
    output_dir: Path | str | None = None,
    *,
    background_color: tuple[int, int, int] = DEFAULT_BACKGROUND_COLOR,
    text_color: tuple[int, int, int] = DEFAULT_TEXT_COLOR,
    font_path: Path = FONT_REGULAR,
    filename_prefix: str = "slide",
) -> list[Path]:
    """Render one PNG per headline (up to MAX_SLIDES) into output_dir."""
    if not headlines:
        raise ValueError("headlines must contain at least one entry")
    if len(headlines) > MAX_SLIDES:
        raise ValueError(f"headlines exceeds carousel limit of {MAX_SLIDES}")

    output_dir = Path(output_dir) if output_dir else default_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for idx, headline in enumerate(headlines, start=1):
        image = render_slide(
            headline,
            background_color=background_color,
            text_color=text_color,
            font_path=font_path,
        )
        path = output_dir / f"{filename_prefix}_{idx:02d}.png"
        image.save(path, "PNG")
        paths.append(path)

    return paths
