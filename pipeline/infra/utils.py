"""공유 유틸리티 함수 — Instagram/Tools 등 여러 파이프라인에서 공통 사용.

이 모듈은 Instagram 의존성을 가지지 않으며, edge_tts 등 선택적 의존성도
불러오지 않는다. 필요한 함수만 이곳에서 제공하여 순환/연쇄 Import 문제를
방지한다.
"""
from __future__ import annotations

import re
from pathlib import Path

# Project root (auto-detected from this file's location)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


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


def ensure_dir(path: str | Path) -> Path:
    """mkdir -p equivalent. Returns the Path object."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


__all__ = [
    "PROJECT_ROOT",
    "slugify",
    "ensure_dir",
]
