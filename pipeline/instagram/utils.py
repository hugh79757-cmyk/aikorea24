"""Instagram Carousel/Reels 유틸리티 함수."""
from __future__ import annotations

import re
import shutil
import subprocess
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# KST = UTC+9
KST = timezone(timedelta(hours=9))

# Project root (auto-detected from this file's location)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def ensure_dir(path: str | Path) -> Path:
    """mkdir -p equivalent. Returns the Path object."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def slugify(text: str, max_length: int = 60) -> str:
    """Create a safe filename slug from Korean/English text.

    Strips special characters, replaces spaces with hyphens,
    and truncates to max_length.
    """
    # Remove non-alphanumeric characters except Korean and hyphens
    slug = re.sub(r'[^\w\s가-힣ㄱ-ㅎㅏ-ㅣ-]', '', text)
    # Replace whitespace with hyphens
    slug = re.sub(r'\s+', '-', slug.strip())
    # Collapse multiple hyphens
    slug = re.sub(r'-{2,}', '-', slug)
    # Truncate
    return slug[:max_length].rstrip('-') or 'untitled'


def timestamp_kst() -> str:
    """Current KST timestamp string: YYYYMMDD_HHMMSS."""
    now = datetime.now(KST)
    return now.strftime("%Y%m%d_%H%M%S")


def date_str_kst() -> str:
    """Current KST date string: YYYYMMDD."""
    now = datetime.now(KST)
    return now.strftime("%Y%m%d")


def get_playwright_path() -> str | None:
    """Find the playwright CLI binary path.

    Returns the path string if found, None otherwise.
    """
    # Try shutil.which first (respects PATH)
    path = shutil.which("playwright")
    if path:
        return path

    # Fallback: common macOS homebrew path
    homebrew_path = Path("/opt/homebrew/bin/playwright")
    if homebrew_path.exists():
        return str(homebrew_path)

    return None


def create_run_directory(base_name: str = "instagram-carousel-output") -> Path:
    """Create a dated output directory: project_root/<base_name>/YYYYMMDD/.

    If directory already exists, it is reused (overwrite mode — one run per day).
    """
    date_part = date_str_kst()
    output_dir = PROJECT_ROOT / base_name / date_part
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def cleanup_old_html(output_dir: Path) -> int:
    """Remove temporary HTML files from output directory after PNG capture.

    Returns the number of files removed.
    """
    removed = 0
    for html_file in output_dir.glob("*.html"):
        try:
            html_file.unlink()
            removed += 1
        except OSError as e:
            logger.warning("Failed to remove %s: %s", html_file, e)
    return removed


def ensure_output_dir(date_str: str | None = None, kind: str = "carousel") -> Path:
    """Create output directory for carousel or reel PNGs.

    Args:
        date_str: Optional date string (YYYYMMDD). Defaults to today KST.
        kind: "carousel" or "reel"
    """
    if date_str is None:
        date_str = date_str_kst()
    base = "instagram-carousel-output" if kind == "carousel" else "instagram-reel-output"
    output_dir = PROJECT_ROOT / base / date_str
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


__all__ = [
    "ensure_dir",
    "slugify",
    "timestamp_kst",
    "date_str_kst",
    "get_playwright_path",
    "create_run_directory",
    "cleanup_old_html",
    "ensure_output_dir",
    "PROJECT_ROOT",
]
