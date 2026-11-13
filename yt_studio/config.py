"""Brand, video format, voice, and cross-platform font configuration."""

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = PROJECT_ROOT / "content"
ASSETS_DIR = PROJECT_ROOT / "assets"
OUTPUT_DIR = PROJECT_ROOT / "output"

RENDERER_VERSION = "2.4"


def natural_sort_key(path_or_str: Any) -> List[Any]:
    """Natural numeric sort key so short_2 < short_10 < short_100."""
    name = path_or_str.name if isinstance(path_or_str, Path) else str(path_or_str)
    return [int(tok) if tok.isdigit() else tok.lower() for tok in re.split(r"(\d+)", name)]


def discover_storyboards(root: Path = CONTENT_DIR) -> List[Path]:
    """Recursively discover all storyboard .json files under root in natural sort order."""
    if root.is_file():
        return [root]
    if not root.is_dir():
        return []
    return sorted(
        (
            p
            for p in root.rglob("*.json")
            if p.is_file()
            and p.name != "published_ledger.json"
            and not any(part.startswith(".") for part in p.relative_to(root).parts)
            # content/drafts/ holds unreviewed AI drafts; a human moves them out before they may be published
            and "drafts" not in p.relative_to(root).parts[:-1]
        ),
        key=natural_sort_key,
    )


@dataclass(frozen=True)
class BrandTheme:
    channel_name: str = "Mind & Margin"
    channel_handle: str = "@MindMargin-t4k"
    tagline: str = "Federal Filings • Financial Forensics • Regulatory Breakdowns"
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
    str(ASSETS_DIR / "fonts" / "RobotoCondensed-Bold.ttf"),
    "/usr/share/fonts/truetype/roboto/unhinted/RobotoCondensed-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

REGULAR_FONT_CANDIDATES = [
    str(ASSETS_DIR / "fonts" / "Inter-Regular.ttf"),
    str(ASSETS_DIR / "fonts" / "RobotoCondensed-Medium.ttf"),
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
