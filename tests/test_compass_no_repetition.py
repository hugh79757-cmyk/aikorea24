"""Tests for pipeline.threads.compass — no factual repetition across H2 sections (REQ-39-07)."""
import json
import pytest
import re
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "threads"))

from pipeline.threads.compass import _build_blog_pass2_user_prompt

pytestmark = pytest.mark.unit


COMPASS = {
    "category": "business",
    "slot1_fact": "GS그룹이 2.4GW 규모의 AI 데이터센터 프로젝트를 발표했다",
    "slot2_compare": "SK는 이미 운영 중이며 GS는 에너지 수직계열화로 차별화된다",
    "slot3_context": "글로벌 AI 인프라 전력 수요가 급증하는 시장 배경이다",
    "slot4_outlook": "2028년 준공 후 국내 DC 시장 판도가 변할 가능성이 있다",
    "intro_style": "number_shock",
    "h2_flow": [
        "팩트: 핵심 사건과 수치",
        "비교: 경쟁사 대비 차별점",
        "맥락: 시장 트렌드와 배경",
        "전망: 향후 변수와 전망",
        "요약: 핵심 포인트 정리",
    ],
    "tone": "analytical",
    "table_plan": None,
}

# Numeric tokens that must not repeat across sections.
# 2-char+ numbers and 4-char+ Korean tokens (e.g. 2.4GW, 2028년, 데이터센터).
_NUMERIC_RE = re.compile(r"\d[\d.]*\w*")
_KOR_TOKEN_RE = re.compile(r"[가-힣]{4,}")


def _section_h2_map(body: str) -> dict:
    blocks = {}
    current = None
    for line in body.split("\n"):
        m = re.match(r"^#{1,3}\s+(.+)$", line.strip())
        if m:
            current = m.group(1).strip()
            blocks[current] = []
        elif current is not None:
            blocks[current].append(line)
    return {k: "\n".join(v).strip() for k, v in blocks.items()}


def detect_repetition(body: str) -> dict:
    """Return {token: [headings where token appears]} for any numeric token
    or 4+ character Korean noun that appears in more than one H2 section.
    Equivalent logic to the anti-repetition rule enforced by the Pass 2
    prompt (REQ-39-07)."""
    sections = _section_h2_map(body)
    seen = {}
    for heading, text in sections.items():
        for tok in set(_NUMERIC_RE.findall(text)) | set(_KOR_TOKEN_RE.findall(text)):
            seen.setdefault(tok, []).append(heading)
    return {tok: hs for tok, hs in seen.items() if len(hs) > 1}


class TestNoRepetitionPositive:
    """Sections with unique content must pass."""

    def test_blog_prompt_contains_anti_repetition_rule(self):
        p = _build_blog_pass2_user_prompt(
            COMPASS, "본문",
            h2_flow="현황과 주요 수치", intro_style="what_if", summary_format="bullet",
        )
        assert "slot1_fact" in p, "Compass JSON 누락"
        assert "코드가 결정한 값" in p, "코드 결정 섹션 누락"

    def test_unique_sections_pass(self):
        body = (
            "## 팩트: 핵심 사건과 수치\n"
            "GS그룹이 새로운 인프라 프로젝트를 발표했다.\n\n"
            "## 비교: 경쟁사 대비 차별점\n"
            "SK는 이미 운영 중이며 GS는 에너지 수직계열화로 차별화된다.\n\n"
            "## 맥락: 시장 트렌드와 배경\n"
            "글로벌 AI 인프라 전력 수요가 급증하는 시장 배경이다.\n\n"
            "## 전망: 향후 변수와 전망\n"
            "2028년 준공 후 시장 판도가 변할 가능성이 있다.\n\n"
            "## 요약: 핵심 포인트 정리\n"
            "GS의 새로운 프로젝트가 주목받는 이유이다."
        )
        dups = detect_repetition(body)
        assert dups == {}, f"예상치 못한 중복: {dups}"


class TestNoRepetitionNegative:
    """A number repeated across sections must be caught."""

    def test_repeated_number_is_caught(self):
        body = (
            "## 팩트: 핵심 사건과 수치\n"
            "GS그룹이 2.4GW 규모의 AI 데이터센터 프로젝트를 발표했다.\n\n"
            "## 비교: 경쟁사 대비 차별점\n"
            "SK는 이미 운영 중이며 GS는 에너지 수직계열화로 차별화된다.\n\n"
            "## 맥락: 시장 트렌드와 배경\n"
            "2.4GW 프로젝트는 글로벌 AI 인프라 전력 수요 급증 속이다.\n\n"
            "## 전망: 향후 변수와 전망\n"
            "2028년 준공 후 시장 판도가 변할 가능성이 있다.\n\n"
            "## 요약: 핵심 포인트 정리\n"
            "GS의 데이터센터 프로젝트가 주목받는 이유이다."
        )
        dups = detect_repetition(body)
        assert dups, "중복 numeric token이 감지되지 않음"
        assert any("2.4GW" in tok for tok in dups), (
            f"2.4GW 중복 미감지: {dups}"
        )

    def test_repeated_korean_token_is_caught(self):
        body = (
            "## 팩트: 핵심 사건과 수치\n"
            "GS그룹이 AI 데이터센터 프로젝트를 발표했다.\n\n"
            "## 비교: 경쟁사 대비 차별점\n"
            "SK는 이미 운영 중이며 GS는 에너지 수직계열화로 차별화된다.\n\n"
            "## 맥락: 시장 트렌드와 배경\n"
            "데이터센터 투자 급증 속에서 GS가 주목받는 이유이다.\n\n"
            "## 전망: 향후 변수와 전망\n"
            "2028년 준공 후 데이터센터 시장 판도가 변할 가능성이 있다.\n\n"
            "## 요약: 핵심 포인트 정리\n"
            "GS의 데이터센터 프로젝트가 주목받는 이유이다."
        )
        dups = detect_repetition(body)
        assert any("데이터센터" in tok for tok in dups), (
            f"데이터센터 중복 미감지: {dups}"
        )