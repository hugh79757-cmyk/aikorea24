"""pipeline.threads.contrast — contrast writing pivot (extractor → background → curator)."""
from typing import TypedDict

class ContrastBundle(TypedDict, total=False):
    seed_article: dict
    af: dict
    background: dict | None
    cross_articles: list[dict]
    cards: list[str] | None

__all__ = ["ContrastBundle", "CONTRAST_CARD_MAP", "run_contrast_thread"]

try:
    from pipeline.threads.contrast.prompts import CONTRAST_CARD_MAP  # noqa: F401
except Exception:
    CONTRAST_CARD_MAP = {}  # type: ignore

try:
    from pipeline.threads.contrast.orchestrator import run_contrast_thread  # noqa: F401
except Exception:
    run_contrast_thread = None  # type: ignore
