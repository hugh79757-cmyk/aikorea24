from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SlideType(str, Enum):
    """Instagram 슬라이드/씬 타입"""
    HOOK = "hook"
    CONFLICT = "conflict"
    TWIST = "twist"
    EXPANSION = "expansion"
    CTA = "cta"
    LINK = "link"
    BRANDING = "branding"
    COVER = "cover"


@dataclass(slots=True)
class InstagramSlide:
    """Instagram Carousel 슬라이드 데이터"""
    slide_type: SlideType
    title: str
    body: str
    highlight_number: Optional[str] = None
    emoji_prefix: str = ""
    style_hint: str = ""
    subtitle: Optional[str] = None


@dataclass(slots=True)
class InstagramReelScene:
    """Instagram Reels 씬"""
    scene_index: int
    text: str
    slide_ref: SlideType
    duration_seconds: float
    transition_type: Optional[str] = None
    animation_style: str = "fade"
    caption_lines: list[str] = None

    def __post_init__(self):
        if self.caption_lines is None:
            self.caption_lines = []


# Package exports
__all__ = [
    "SlideType",
    "InstagramSlide",
    "InstagramReelScene",
    "convert_format_d_to_carousel",
    "convert_format_d_to_reel_script",
]