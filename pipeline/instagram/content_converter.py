from __future__ import annotations
import re
import random
from typing import Optional
from pipeline.instagram.models import SlideType, InstagramSlide, InstagramReelScene


# ──────────────────────────────────────────────
# 유틸리티 함수
# ──────────────────────────────────────────────

def extract_highlight(text: str) -> Optional[str]:
    """텍스트에서 숫자/단위 하이라이트 추출 (예: '87%', '3x', '#1', '$100M')"""
    match = re.search(r'(\d+[%$,#x]*\d*|#\d+)', text)
    return match.group(1) if match else None


def split_text_for_slide(text: str, max_chars: int = 80) -> tuple[str, str]:
    """텍스트를 title(첫 줄/첫 문장)과 body(나머지)로 분할"""
    text = text.strip()
    first_break = text.find('\n')
    period_pos = text.find('.')

    if first_break != -1 and (period_pos == -1 or first_break < period_pos):
        split_pos = first_break + 1
    elif period_pos != -1:
        split_pos = period_pos + 1
    else:
        split_pos = min(len(text), max_chars)

    title = text[:split_pos].strip()
    body = text[split_pos:].strip()

    if len(title) > 80:
        period_pos = title.find('.')
        if period_pos != -1:
            title = title[:period_pos + 1].strip()

    return title, body


def _split_korean_caption(text: str, max_width: int = 18) -> list[str]:
    """한국어 캡션을 단어 단위로 분할 (한 줄 최대 max_width 문자)"""
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    current_len = 0

    for word in words:
        word_len = len(word)
        if current_len + word_len + (1 if current_len > 0 else 0) > max_width:
            if current:
                lines.append(' '.join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += word_len + (1 if current_len > 0 else 0)

    if current:
        lines.append(' '.join(current))

    return lines


def _estimate_tts_duration(text: str) -> float:
    """한국어 TTS 예상 길이 추정 (초)"""
    if not text:
        return 2.0
    # 한국어: 초당 ~4.5음절, 영어: 단어당 ~3음절
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    korean_syllables = sum(1 for c in text if '\uac00' <= c <= '\ud7a3')
    total_syllables = korean_syllables + english_words * 3
    duration = max(1.5, min(6.0, total_syllables / 4.5))
    return round(duration, 1)


# ──────────────────────────────────────────────
# Format D → Carousel 슬라이드 변환
# ──────────────────────────────────────────────

STYLE_HINTS = {
    SlideType.HOOK: "gradient-purple",
    SlideType.CONFLICT: "gradient-red",
    SlideType.TWIST: "gradient-blue",
    SlideType.EXPANSION: "dark-card",
    SlideType.CTA: "gradient-green",
    SlideType.LINK: "minimal-dark",
    SlideType.BRANDING: "brand-footer",
}

EMOJI_PREFIX = {
    SlideType.HOOK: "🔥",
    SlideType.CONFLICT: "⚠️",
    SlideType.TWIST: "⚡",
    SlideType.EXPANSION: "📊",
    SlideType.CTA: "💡",
    SlideType.LINK: "🔗",
    SlideType.BRANDING: "🇰🇷",
}


def convert_format_d_to_carousel(cards: list[str]) -> list[InstagramSlide]:
    """
    Format D 6카드 → Instagram Carousel 슬라이드 리스트 (5~7개)

    Args:
        cards: Format D 6개 카드 문자열 리스트

    Returns:
        InstagramSlide 리스트 (5~7개)
    """
    if not cards or len(cards) < 6:
        return []

    slides: list[InstagramSlide] = []
    card_types = [SlideType.HOOK, SlideType.CONFLICT, SlideType.TWIST,
                  SlideType.EXPANSION, SlideType.CTA, SlideType.LINK]

    for card_text, slide_type in zip(cards, card_types):
        card_text = card_text.strip()
        if len(card_text) < 5:
            continue

        title, body = split_text_for_slide(card_text)
        highlight = extract_highlight(card_text)
        emoji = EMOJI_PREFIX.get(slide_type, "")
        style = STYLE_HINTS.get(slide_type, "minimal-dark")

        slide = InstagramSlide(
            slide_type=slide_type,
            title=title,
            body=body,
            highlight_number=highlight,
            emoji_prefix=emoji,
            style_hint=style,
        )
        slides.append(slide)

    # 브랜딩 슬라이드 추가
    branding_slide = InstagramSlide(
        slide_type=SlideType.BRANDING,
        title="AI코리아24",
        body="당신의 AI 여정을 응원합니다",
        style_hint="brand-footer",
        emoji_prefix="🇰🇷",
    )
    slides.append(branding_slide)

    return slides


# ──────────────────────────────────────────────
# Format D → Reels 대본 변환
# ──────────────────────────────────────────────

REEL_TRANSITIONS = ["wipeleft", "circlecrop", "dissolve", "smoothleft"]
REEL_ANIMATIONS = ["slide-up", "bounce", "bounce", "fade", "bounce", "fade"]


def convert_format_d_to_reel_script(cards: list[str]) -> list[InstagramReelScene]:
    """
    Format D 6카드 → Reels 6개 씬 대본

    Args:
        cards: Format D 6개 카드 문자열 리스트

    Returns:
        InstagramReelScene 리스트 (6개)
    """
    if not cards or len(cards) < 6:
        return []

    scenes: list[InstagramReelScene] = []
    card_type_names = ["hook", "conflict", "twist", "expansion", "cta", "link"]

    for idx, (card_text, card_type_name) in enumerate(zip(cards, card_type_names)):
        card_text = card_text.strip()
        if not card_text:
            continue

        # 씬 텍스트: 80자 내외
        scene_text = card_text[:80].strip()

        # 길이 추정
        duration = _estimate_tts_duration(card_text)
        duration = max(2.0, min(5.0, duration))

        # 캡션 분할
        caption_lines = _split_korean_caption(card_text[:40], 18)

        # 트랜지션 (첫 씬 제외)
        transition = None if idx == 0 else random.choice(REEL_TRANSITIONS)
        animation = REEL_ANIMATIONS[idx]

        scene = InstagramReelScene(
            scene_index=idx,
            text=scene_text,
            slide_ref=list(SlideType)[idx % len(SlideType)],
            duration_seconds=duration,
            transition_type=transition,
            animation_style=animation,
            caption_lines=caption_lines,
        )
        scenes.append(scene)

    return scenes


# ──────────────────────────────────────────────
# 편의 함수
# ──────────────────────────────────────────────

def convert_format_d(cards: list[str], target: str = "both") -> dict:
    """
    Format D 카드를 Carousel과/또는 Reels용으로 변환

    Args:
        cards: Format D 6카드 리스트
        target: "carousel" | "reels" | "both"

    Returns:
        변환 결과 딕셔너리
    """
    result: dict = {}
    if target in ("carousel", "both"):
        result["carousel"] = convert_format_d_to_carousel(cards)
    if target in ("reels", "both"):
        result["reels"] = convert_format_d_to_reel_script(cards)
    return result


__all__ = [
    "SlideType",
    "InstagramSlide",
    "InstagramReelScene",
    "convert_format_d_to_carousel",
    "convert_format_d_to_reel_script",
    "convert_format_d",
]
