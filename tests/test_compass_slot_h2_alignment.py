"""Tests for pipeline.threads.compass — H2 heading order vs slot order (REQ-39-06)."""
import json
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "threads"))

from pipeline.threads.compass import (
    _build_blog_pass2_user_prompt,
    _build_pass2_user_prompt,
)

pytestmark = pytest.mark.unit


COMPASS = {
    "category": "business",
    "slot1_fact": "GS그룹이 AI 데이터센터 프로젝트를 발표했다",
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


def _section_h2_map(body: str) -> dict:
    """Map each ## H2 heading to the body text following it (until next heading)."""
    import re
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


def _norm(s: str) -> str:
    """Strip punctuation for content comparison."""
    return s.replace(".", "").replace(",", "").strip()


def _contains(needle: str, hay: str) -> bool:
    """Ordered-subsequence containment.

    The LLM may paraphrase a slot sentence (drop a token like "국내") while
    still proving the section carries the right slot's substance in the
    right order. A strict substring match would be too brittle.
    """
    ntok = _norm(needle).split()
    htok = _norm(hay).split()
    if not ntok:
        return False
    i = 0
    for t in ntok:
        while i < len(htok) and htok[i] != t:
            i += 1
        if i >= len(htok):
            return False
        i += 1
    return True


class TestH2OrderPositive:
    """H2 headings must follow h2_flow order and each section must carry
    the matching slot's content."""

    def test_blog_prompt_contains_slot_order_rule(self):
        p = _build_blog_pass2_user_prompt(
            COMPASS, "본문",
            h2_flow="현황과 주요 수치", intro_style="what_if", summary_format="bullet",
        )
        assert all(x in p for x in ["slot1_fact", "slot2_compare", "slot3_context", "slot4_outlook"]), "slot 필드 누락"
        assert "코드가 결정한 값" in p, "코드 결정 섹션 누락"

    def test_thread_prompt_contains_slot_order_rule(self):
        p = _build_pass2_user_prompt(COMPASS, "본문")
        assert "h2_flow[0]은 slot1_fact" in p
        assert "절대 순서를 바꾸지 마세요" in p

    def test_h2_sections_follow_slot_order(self):
        body = (
            "## 팩트: 핵심 사건과 수치\n"
            "GS그룹이 AI 데이터센터 프로젝트를 발표했다.\n\n"
            "## 비교: 경쟁사 대비 차별점\n"
            "SK는 이미 운영 중이며 GS는 에너지 수직계열화로 차별화된다.\n\n"
            "## 맥락: 시장 트렌드와 배경\n"
            "글로벌 AI 인프라 전력 수요가 급증하는 시장 배경이다.\n\n"
            "## 전망: 향후 변수와 전망\n"
            "2028년 준공 후 국내 DC 시장 판도가 변할 가능성이 있다.\n\n"
            "## 요약: 핵심 포인트 정리\n"
            "GS의 데이터센터 프로젝트가 주목받는 이유이다."
        )
        sections = _section_h2_map(body)
        headings = list(sections.keys())
        assert headings == COMPASS["h2_flow"], (
            f"H2 순서 불일치: {headings} != {COMPASS['h2_flow']}"
        )
        # Each section must contain its slot's content.
        # Token-level containment (see _contains) tolerates a paraphrase
        # such as dropping "국내" while still proving the section carries
        # the right slot's substance in the right order.
        assert _contains(COMPASS["slot1_fact"], sections[COMPASS["h2_flow"][0]])
        assert _contains(COMPASS["slot2_compare"], sections[COMPASS["h2_flow"][1]])
        assert _contains(COMPASS["slot3_context"], sections[COMPASS["h2_flow"][2]])
        assert _contains(COMPASS["slot4_outlook"], sections[COMPASS["h2_flow"][3]])


class TestH2OrderNegative:
    """H2 in wrong order must be detectable — the slot content is in the
    wrong section."""

    def test_h2_in_wrong_order_is_detectable(self):
        body = (
            "## 전망: 향후 변수와 전망\n"
            "GS그룹이 AI 데이터센터 프로젝트를 발표했다.\n\n"
            "## 팩트: 핵심 사건과 수치\n"
            "2028년 준공 후 국내 DC 시장 판도가 변할 가능성이 있다.\n\n"
            "## 비교: 경쟁사 대비 차별점\n"
            "SK는 이미 운영 중이며 GS는 에너지 수직계열화로 차별화된다.\n\n"
            "## 맥락: 시장 트렌드와 배경\n"
            "글로벌 AI 인프라 전력 수요가 급증하는 시장 배경이다.\n\n"
            "## 요약: 핵심 포인트 정리\n"
            "GS의 데이터센터 프로젝트가 주목받는 이유이다."
        )
        sections = _section_h2_map(body)
        headings = list(sections.keys())
        assert headings != COMPASS["h2_flow"], (
            "의도된 역순서가 감지되지 않음"
        )
        # In a reversed-order draft the fact content lands in the wrong
        # section: slot4_outlook content appears in the fact section, and
        # slot1_fact content appears in the outlook section.
        assert _contains(COMPASS["slot4_outlook"], sections[COMPASS["h2_flow"][0]]), (
            "전망 내용이 팩트 섹션에 있음 (순서 뒤짐)"
        )
        assert _contains(COMPASS["slot1_fact"], sections[COMPASS["h2_flow"][3]]), (
            "팩트 내용이 전망 섹션에 있음 (순서 뒤짐)"
        )