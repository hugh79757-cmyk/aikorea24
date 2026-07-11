"""Instagram Graph API 설정 — 환경변수 기반 로드."""
from __future__ import annotations

import os

# Instagram Graph API version (2026-07 기준 최신 안정)
API_VERSION = "v25.0"
GRAPH_API_BASE = "https://graph.facebook.com"

# Instagram Business Account ID (from env)
INSTAGRAM_ACCOUNT_ID: str = os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
ACCESS_TOKEN: str = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")

# Facebook Page ID (optional, for cross-posting)
FACEBOOK_PAGE_ID: str = os.environ.get("FACEBOOK_PAGE_ID", "")

# Publishing defaults
DEFAULT_HASHTAGS: list[str] = [
    "AI뉴스",
    "인공지능",
    "AI코리아24",
    "AI트렌드",
]

# Caption templates — {hook_text}, {cta_text}, {hashtags} placeholders
CAROUSEL_CAPTION_TEMPLATE: str = (
    "{hook_text}\n\n"
    "{cta_text}\n\n"
    "---\n"
    "이 이슈, 3분 안에 정리해서 매일 브리핑에서 봅니다\n"
    "팔로우해서 매일 AI 뉴스 받아보기 → @aikorea24\n\n"
    "{hashtags}"
)
REEL_CAPTION_TEMPLATE: str = "{hook_text}\n\n{hashtags}"

# Rate limiting
MAX_PUBLISH_PER_HOUR: int = 2
RETRY_DELAYS_SECONDS: list[int] = [60, 300, 900]  # 1min, 5min, 15min

# Media file limits
MAX_IMAGE_SIZE_MB: int = 10
MAX_VIDEO_SIZE_MB: int = 250

# Publish log file (rate limit tracking)
PUBLISH_LOG_FILE: str = "instagram_publish_log.json"

__all__ = [
    "API_VERSION",
    "GRAPH_API_BASE",
    "INSTAGRAM_ACCOUNT_ID",
    "ACCESS_TOKEN",
    "FACEBOOK_PAGE_ID",
    "DEFAULT_HASHTAGS",
    "CAROUSEL_CAPTION_TEMPLATE",
    "REEL_CAPTION_TEMPLATE",
    "MAX_PUBLISH_PER_HOUR",
    "RETRY_DELAYS_SECONDS",
    "MAX_IMAGE_SIZE_MB",
    "MAX_VIDEO_SIZE_MB",
    "PUBLISH_LOG_FILE",
]
