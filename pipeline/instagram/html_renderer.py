"""Instagram Carousel/Reels HTML 렌더러.

HTML 템플릿 + string.Template → Playwright PNG 캡처 파이프라인.
Playwright 로컬 설치 기반 ($0 비용).
"""
from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from string import Template

from pipeline.instagram.models import InstagramSlide, SlideType
from pipeline.instagram.utils import (
    ensure_dir,
    get_playwright_path,
    cleanup_old_html,
)

logger = logging.getLogger(__name__)

# Template directory (sibling to this file)
TEMPLATE_DIR = Path(__file__).parent / "templates"

# Style hint → CSS class mapping
STYLE_TO_BG_CLASS = {
    "gradient-purple": "bg-hook",
    "gradient-red": "bg-conflict",
    "gradient-blue": "bg-twist",
    "dark-card": "bg-expansion",
    "gradient-green": "bg-cta",
    "minimal-dark": "bg-link",
    "brand-footer": "bg-brand",
}

# Dimensions
CAROUSEL_WIDTH = 1080
CAROUSEL_HEIGHT = 1350
REEL_WIDTH = 1080
REEL_HEIGHT = 1920

# Playwright capture timeout (seconds)
CAPTURE_TIMEOUT = 30


def _resolve_bg_class(style_hint: str) -> str:
    """Map a style_hint string to a CSS background class name."""
    return STYLE_TO_BG_CLASS.get(style_hint, "bg-link")


def _load_template(name: str) -> Template:
    """Load an HTML template by filename from the templates directory."""
    template_path = TEMPLATE_DIR / name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    return Template(template_path.read_text(encoding="utf-8"))


def _render_slide_to_html(
    slide: InstagramSlide,
    template: Template,
    output_path: Path,
) -> Path:
    """Render a single InstagramSlide into an HTML file using string.Template.

    Returns the path to the written HTML file.
    """
    bg_class = _resolve_bg_class(slide.style_hint)
    highlight = slide.highlight_number or ""
    subtitle = slide.subtitle or ""

    result = template.safe_substitute(
        emoji_prefix=slide.emoji_prefix,
        highlight_number=highlight,
        title=slide.title,
        body=slide.body,
        bg_class=bg_class,
        subtitle=subtitle,
    )

    output_path.write_text(result, encoding="utf-8")
    return output_path


def capture_html_to_png(
    html_path: str | Path,
    output_path: str | Path,
    width: int,
    height: int,
) -> bool:
    """Capture an HTML file to PNG using Playwright CLI.

    Uses: playwright screenshot --device-scale-factor=2 --viewport-size WxH

    Returns True on success, False on failure.
    """
    pw_path = get_playwright_path()
    if not pw_path:
        logger.error(
            "Playwright not found. Install: pip install playwright && "
            "python3 -m playwright install chromium"
        )
        return False

    html_path = Path(html_path).resolve()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        pw_path,
        "screenshot",
        "--device-scale-factor=2",
        "--viewport-size", f"{width}x{height}",
        f"file://{html_path}",
        str(output_path),
    ]

    for attempt in range(2):  # retry once on failure
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=CAPTURE_TIMEOUT,
                check=True,
            )
            if output_path.exists() and output_path.stat().st_size > 0:
                logger.info("Captured: %s (%d bytes)", output_path.name, output_path.stat().st_size)
                return True
            logger.warning("Capture produced empty file: %s", output_path)
        except subprocess.TimeoutExpired:
            logger.warning("Capture timeout (attempt %d/2): %s", attempt + 1, html_path.name)
        except subprocess.CalledProcessError as e:
            logger.warning(
                "Capture failed (attempt %d/2): %s — stderr: %s",
                attempt + 1, html_path.name, e.stderr[:200] if e.stderr else "",
            )
        except FileNotFoundError:
            logger.error(
                "Playwright binary not found at %s. Install: pip install playwright && "
                "python3 -m playwright install chromium",
                pw_path,
            )
            return False

    logger.error("Capture failed after 2 attempts: %s", html_path.name)
    return False


def render_carousel_slides(
    slides: list[InstagramSlide],
    output_dir: str | Path,
) -> list[Path]:
    """Render a list of InstagramSlide objects to PNG files.

    Each slide is rendered to HTML, captured as PNG, then the HTML is cleaned up.
    Returns a list of successfully generated PNG paths (partial success possible).
    """
    output_dir = Path(output_dir)
    ensure_dir(output_dir)
    template = _load_template("carousel_slide.html")

    png_paths: list[Path] = []
    for idx, slide in enumerate(slides, 1):
        slug = slide.slide_type.value
        html_path = output_dir / f"slide_{idx:02d}_{slug}.html"
        png_path = output_dir / f"slide_{idx:02d}_{slug}.png"

        try:
            _render_slide_to_html(slide, template, html_path)
            success = capture_html_to_png(
                html_path, png_path, CAROUSEL_WIDTH, CAROUSEL_HEIGHT,
            )
            if success:
                png_paths.append(png_path)
            else:
                logger.warning("Skipping slide %d (%s): capture failed", idx, slug)
        except Exception:
            logger.exception("Error rendering slide %d (%s)", idx, slug)

    # Cleanup temp HTML files
    cleanup_old_html(output_dir)

    return png_paths


def render_reel_cover(
    slide: InstagramSlide,
    output_dir: str | Path,
) -> Path | None:
    """Render a single InstagramSlide as a Reels cover (1080x1920).

    Returns the PNG path on success, None on failure.
    """
    output_dir = Path(output_dir)
    ensure_dir(output_dir)
    template = _load_template("reel_cover.html")

    slug = slide.slide_type.value
    html_path = output_dir / f"reel_cover_{slug}.html"
    png_path = output_dir / f"reel_cover_{slug}.png"

    try:
        _render_slide_to_html(slide, template, html_path)
        success = capture_html_to_png(
            html_path, png_path, REEL_WIDTH, REEL_HEIGHT,
        )
        if success:
            return png_path
    except Exception:
        logger.exception("Error rendering reel cover (%s)", slug)
    finally:
        # Cleanup temp HTML
        if html_path.exists():
            html_path.unlink(missing_ok=True)

    return None


def render_reel_thumbnail(slides: list[InstagramSlide]) -> Path | None:
    """Render a Reels thumbnail from the first slide (HOOK).

    Uses reel_cover.html template at 1080x1920.
    Returns the PNG path on success, None on failure.
    """
    if not slides:
        logger.warning("No slides provided for reel thumbnail")
        return None

    from pipeline.instagram.utils import create_run_directory
    output_dir = create_run_directory("instagram-reel-output")

    return render_reel_cover(slides[0], output_dir)


__all__ = [
    "render_carousel_slides",
    "render_reel_cover",
    "render_reel_thumbnail",
    "capture_html_to_png",
    "STYLE_TO_BG_CLASS",
]
