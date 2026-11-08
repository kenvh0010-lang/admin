"""Brand, video format, voice, and cross-platform font configuration."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = PROJECT_ROOT / "content"
ASSETS_DIR = PROJECT_ROOT / "assets"
OUTPUT_DIR = PROJECT_ROOT / "output"


@dataclass(frozen=True)
class BrandTheme:
    channel_name: str = "Mind & Margin"
    channel_handle: str = "@MindAndMargin"
    tagline: str = "Wealth Psychology • Mental Models • AI Leverage"
    bg_primary: Tuple[int, int, int] = (11, 16, 32)       # Deep Obsidian Navy (#0B1020)
    bg_card: Tuple[int, int, int] = (19, 28, 52)          # Elevated Slate Card (#131C34)
    accent_gold: Tuple[int, int, int] = (245, 185, 66)    # Compounding Gold (#F5B942)
    accent_cyan: Tuple[int, int, int] = (34, 211, 238)    # Leverage Cyan (#22D3EE)
    accent_crimson: Tuple[int, int, int] = (244, 63, 94)  # Hook / Warning Red (#F43F5E)
    text_primary: Tuple[int, int, int] = (248, 250, 252)  # Crisp White (#F8FAFC)
    text_muted: Tuple[int, int, int] = (148, 163, 184)    # Muted Slate (#94A3B8)
    grid_line: Tuple[int, int, int] = (28, 39, 68)        # Subtle Grid (#1C2744)


@dataclass(frozen=True)
class VideoFormat:
    name: str
    width: int
    height: int
    fps: int = 30
    is_vertical: bool = True


FORMATS = {
    "short": VideoFormat(name="short", width=1080, height=1920, fps=30, is_vertical=True),
    "long": VideoFormat(name="long", width=1920, height=1080, fps=30, is_vertical=False),
}

VOICE_PRESETS = {
    "en_authoritative": "en-US-ChristopherNeural",
    "en_storyteller": "en-US-AndrewMultilingualNeural",
    "en_warm_female": "en-US-AvaMultilingualNeural",
    "vi_male": "vi-VN-NamMinhNeural",
    "vi_female": "vi-VN-HoaiMyNeural",
}

BOLD_FONT_CANDIDATES = [
    str(ASSETS_DIR / "fonts" / "Inter-Bold.ttf"),
    "/usr/share/fonts/truetype/roboto/unhinted/RobotoCondensed-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

REGULAR_FONT_CANDIDATES = [
    str(ASSETS_DIR / "fonts" / "Inter-Regular.ttf"),
    "/usr/share/fonts/truetype/roboto/unhinted/RobotoCondensed-Medium.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def resolve_font_path(bold: bool = False) -> str:
    """Return the first existing TrueType font path across Linux, macOS, and Windows."""
    candidates = BOLD_FONT_CANDIDATES if bold else REGULAR_FONT_CANDIDATES
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    for candidate in REGULAR_FONT_CANDIDATES + BOLD_FONT_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    raise FileNotFoundError("No TrueType font found. Place a .ttf file in assets/fonts/.")


DEFAULT_THEME = BrandTheme()
