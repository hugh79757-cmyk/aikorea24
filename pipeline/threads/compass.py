"""pipeline/threads/compass.py — Compass 2-pass writing system for Threads pipeline."""
import json
import random
import re
import sys
import os
from datetime import datetime

from pipeline.infra.config import project_root
from pipeline.infra.logger import get_scrubbed_logger

logger = get_scrubbed_logger(__name__)

_root = str(project_root())
if _root not in sys.path:
    sys.path.insert(0, _root)
_threads_path = str(project_root() / "scripts" / "threads")
if _threads_path not in sys.path:
    sys.path.insert(0, _threads_path)

INTRO_STYLES = [
    "self_identity_call",
    "number_shock",
    "reversal",
    "contrast",
    "conflicting_fact",
    "quote_lead",
    "reverse_chronology",
    "what_if",
]

# One-line Korean examples per intro_style pattern (REQ-39-10).
INTRO_STYLE_EXAMPLES = {
    "self_identity_call": "이 기술의 핵심은 데이터 처리 속도입니다",
    "number_shock": "2.4GS.수가 GS그룹이 짓는 데이터센터의 규모입니다",
    "reversal": "전력 회사가 데이터센터를 짓습니다. 놀라운 일이 아닙니다",
    "contrast": "SK는 이미 데이터센터를 운영 중입니다. GS는 이제 시작합니다",
    "conflicting_fact": "GS그룹은 전력 회사입니다. 하지만 데이터센터의 핵심은 전력이 아닙니다",
    "quote_lead": '"AI가 인간을 이해한다"는 주장, 실제는 통계적 패턴 매칭입니다',
    "reverse_chronology": "2028년 상용화 목표 — 그 뒤, 2026년 지금의 기술 수준을 본다",
    "what_if": "만약 AI가 인간의 감정을 진짜로 느낄 수 있다면 어떨까",
}

INTRO_STYLE_PREFIXES = {
    "self_identity_call": "~의 핵심은 ~입니다",
    "number_shock": "숫자로 시작",
    "reversal": "예상과 반전되는 사실로 시작",
    "contrast": "A와 B를 대비하며 시작",
    "conflicting_fact": "서로 모순되는 사실로 시작",
    "quote_lead": "인용문으로 시작",
    "reverse_chronology": "시간 역순으로 시작",
    "what_if": "가정법 질문으로 시작",
}

H2_FLOW_PRESETS = {
    "tech": [
        "기술적 배경과 핵심 원리",
        "현황과 주요 수치",
        "적용 분야와 기대 효과",
        "한계와 과제",
        "향후 전망",
    ],
    "business": [
        "팩트: 핵심 사건과 수치",
        "비교: 경쟁사 대비 차별점",
        "맥락: 시장 트렌드와 배경",
        "전망: 향후 변수와 전망",
        "요약: 핵심 포인트 정리",
    ],
    "society": [
        "사건 배경",
        "주요 반응과 파장",
        "사회적 맥락과 원인",
        "영향과 변화",
        "미해결 쟁점",
    ],
    "culture": [
        "문화적 배경",
        "핵심 사건과 쟁점",
        "대중 반응과 논쟁",
        "사회적 함의",
        "향후 전개",
    ],
    "science": [
        "연구 배경과 목적",
        "연구 방법과 데이터",
        "주요 발견과 수치",
        "한계와 검증",
        "향후 연구 방향",
    ],
}

# H2 required/optional split (Task 2-2): first 3 required, last 2 optional per category.
H2_FLOW_REQUIRED = {cat: presets[:3] for cat, presets in H2_FLOW_PRESETS.items()}
H2_FLOW_OPTIONAL = {cat: presets[3:] for cat, presets in H2_FLOW_PRESETS.items()}

COMPASS_FIELD_LABELS = [
    "slot1_fact",
    "slot2_compare",
    "slot3_context",
    "slot4_outlook",
    "intro_style",
    "h2_flow",
]

_NAVER_TAG_WHITELIST = (
    "p, h2, h3, strong, b, blockquote, hr, ul, ol, li, table, img, a"
)

_NAVER_TAG_STRIP_RE = re.compile(
    r"<(/?)(div|span|style|class|font|center|section|article|aside|nav|header|footer|main|details|summary|dialog|figure|figcaption|time|mark|small|del|ins|sub|sup|abbr|address|cite|code|pre|var|samp|kbd|output)[^>]*>",
    re.IGNORECASE,
)

_POSTED_JSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "posted.json"
)

_compass_cache: dict[tuple, tuple] = {}

# Recent style history for weighted_pick (module-level, persisted via posted.json).
_recent_intro_styles: list[str] = []
_recent_h2_flows: list[list[str]] = []
_recent_summary_formats: list[str] = []


def _log(msg):
    from datetime import datetime
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] [compass] {msg}')


# ── Rotation: independent axes (Task 1-1) ──────────────────────────────────

def _load_intro_rotation() -> int:
    """Load compass_intro_rotation counter from posted.json."""
    try:
        if os.path.exists(_POSTED_JSON_PATH):
            with open(_POSTED_JSON_PATH) as f:
                data = json.load(f)
            return data.get("compass_intro_rotation", 0)
    except Exception:
        pass
    return 0


def _save_intro_rotation(counter: int) -> None:
    """Save compass_intro_rotation counter to posted.json."""
    try:
        data = {}
        if os.path.exists(_POSTED_JSON_PATH):
            with open(_POSTED_JSON_PATH) as f:
                data = json.load(f)
        data["compass_intro_rotation"] = counter
        with open(_POSTED_JSON_PATH, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_h2_rotation() -> int:
    """Load compass_h2_rotation counter from posted.json."""
    try:
        if os.path.exists(_POSTED_JSON_PATH):
            with open(_POSTED_JSON_PATH) as f:
                data = json.load(f)
            return data.get("compass_h2_rotation", 0)
    except Exception:
        pass
    return 0


def _save_h2_rotation(counter: int) -> None:
    """Save compass_h2_rotation counter to posted.json."""
    try:
        data = {}
        if os.path.exists(_POSTED_JSON_PATH):
            with open(_POSTED_JSON_PATH) as f:
                data = json.load(f)
        data["compass_h2_rotation"] = counter
        with open(_POSTED_JSON_PATH, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# Backward compat — delegates to intro rotation (Task 1-1).
def _load_compass_rotation() -> int:
    """Legacy: load compass_intro_rotation. Use _load_intro_rotation() instead."""
    return _load_intro_rotation()


def _save_compass_rotation(counter: int) -> None:
    """Legacy: save compass_intro_rotation. Use _save_intro_rotation() instead."""
    _save_intro_rotation(counter)


# ── Weighted random selection (Task 1-2) ─────────────────────────────────────

def weighted_pick(items: list, recent_items: list, exclude_count: int = 2) -> any:
    """Pick one item from items, excluding the most recent `exclude_count` items.

    Recent items get weight 0; remaining items get equal weight.
    If all items are in recent_items, falls back to random pick from all items.
    """
    if not items:
        raise ValueError("items cannot be empty")
    if len(items) <= exclude_count:
        return random.choice(items)

    excluded = set(recent_items[-exclude_count:])
    candidates = [item for item in items if item not in excluded]

    if not candidates:
        return random.choice(items)

    return random.choice(candidates)


def _wrap_naver_html(cards: list[str]) -> list[str]:
    """Wrap card text in Naver tag-whitelist HTML, strip disallowed tags."""
    wrapped = []
    for card in cards:
        clean = _NAVER_TAG_STRIP_RE.sub("", card)
        clean = re.sub(
            r"^#{1,3}\s+(.+)$", r"<h2>\1</h2>", clean, flags=re.MULTILINE
        )
        lines = []
        for line in clean.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if re.match(r"^<[^>]+>", stripped):
                lines.append(stripped)
            else:
                lines.append(f"<p>{stripped}</p>")
        wrapped.append("\n".join(lines))
    return wrapped


def build_system_prompt_compass() -> str:
    """System prompt for compass Pass 1 (JSON) and Pass 2 (body draft)."""
    return (
        "당신은 한국어 AI 뉴스 쓰레드 라이터입니다.\n"
        "톤: 공식적이고 신중한 어조 (~습니다, ~합니다 종결).\n"
        f"허용 HTML 태그: {_NAVER_TAG_WHITELIST}\n"
        "출력 언어는 한국어만. 영어 원문 인용 그대로 노출 금지.\n"
        "한자·일본어·히라가나·가타카나 절대 금지.\n"
        "각 카드는 짧은 절 단위로 줄바꿈 (10~25자), 절 사이 빈 줄 (\\n\\n).\n"
        "문장 하나가 60자를 넘지 않게 절단.\n"
        "종결어미 ~습니다/~합니다 중심.\n"
        "각 카드 350-450자.\n"
        "마지막 카드는 반드시 답글을 유도하는 열린 형태로 끝날 것 (질문, 의견 요청, 또는 독자 참여 유도).\n"
        "닫힌 종결 (~했다, ~이다 등)로 끝내지 말 것."
    )


def _build_pass1_user_prompt(pitch: dict, all_articles: list) -> str:
    """Build user prompt for Pass 1 compass JSON generation."""
    hook = pitch.get("hook", "")
    narrative = pitch.get("narrative", "")
    twist = pitch.get("twist", "")
    crawled_body = pitch.get("crawled_body", "")
    crawled_url = pitch.get("crawled_url", "")

    articles_text = ""
    for a in (all_articles or [])[:3]:
        articles_text += (
            f"- {a.get('title', '')} (출처: {a.get('source', '')}, "
            f"날짜: {a.get('pub_date', '')})\n"
        )

    return (
        f"=== 피치 ===\n"
        f"훅: {hook}\n"
        f"내러티브: {narrative}\n"
        f"반전: {twist}\n"
        f"출처 URL: {crawled_url}\n"
        f"크롤링 본문 (앞 3000자):\n{crawled_body[:3000]}\n\n"
        f"=== 관련 기사 ===\n{articles_text}\n\n"
        "위 피치와 기사를 바탕으로 compass JSON을 생성하세요.\n"
        "반드시 다음 9개 필드를 포함한 JSON만 출력하세요:\n"
        "- category: tech/business/society/culture/science\n"
        "- slot1_fact: 핵심 사실 (한 줄)\n"
        "- slot2_compare: 원문 본문에 비교 대상(경쟁사, 유사 제품, 대체 기술 등)이 **명시적으로** 언급된 경우에만 기록한다. 원문에 비교 대상이 없으면 값을 \"없음\"으로 둔다. 원문 밖의 기업·제품·서비스를 임의로 추가하지 않는다.\n"
        "- slot3_context: 배경 맥락 (2~3문장, 출처 기반)\n"
        "- slot4_outlook: 향후 전망 (한 줄)\n"
        "- intro_style: 다음 패턴 중 택1. 반드시 예시와 같은 형태로 시작하세요.\n"
        + "\n".join(
            f"  * {style}: {INTRO_STYLE_PREFIXES[style]} "
            f"(예: \"{INTRO_STYLE_EXAMPLES[style]}\")"
            for style in INTRO_STYLES
        )
        + "\n"
        "- h2_flow: category에 맞는 H2 흐름 리스트 (필수 3개 + 선택 2개, 총 3~6개)\n"
        "- tone: neutral_careful/fan_friendly/analytical 중 택1\n"
        "- table_plan: 본문에서 사용할 표 정보 (없으면 null)\n"
    )


def _build_pass2_user_prompt(compass: dict, crawled_body: str) -> str:
    """Build user prompt for Pass 2 body draft generation (thread mode)."""
    compass_header = json.dumps(compass, ensure_ascii=False, indent=2)
    return (
        f"[컴퍼스]\n{compass_header}\n\n"
        f"[출처 본문 (앞 4000자)]\n{crawled_body[:4000]}\n\n"
        "위 컴퍼스를 참고하여 쓰레드 카드 본문을 작성하세요.\n"
        "컴퍼스의 h2_flow 순서를 따르세요.\n"
        "각 H2 섹션은 compass의 슬롯 순서를 반드시 따르세요. "
        "h2_flow[0]은 slot1_fact 내용, h2_flow[1]은 slot2_compare 내용, "
        "h2_flow[2]은 slot3_context 내용, h2_flow[3]은 slot4_outlook 내용을 다루세요. "
        "절대 순서를 바꾸지 마세요.\n"
        "섹션별 중복 금지: 각 H2 섹션은 compass의 해당 슬롯 정보만 포함하세요. "
        "다른 섹션에서 이미 언급한 수치·사실·키워드를 반복하면 안 됩니다. "
        "예: '2.4GW'가 한 섹션에 나왔으면 다른 섹션에서 다시 언급하지 마세요.\n"
        "각 카드는 짧은 절 단위로 줄바꿈, 절 사이 빈 줄.\n"
        "출력은 JSON만: {\"cards\": [\"card1\", \"card2\", ...]}\n"
        "카드 수는 5개."
    )


def _build_blog_pass2_user_prompt(compass_json: dict, crawled_body: str,
                                    h2_flow: str, intro_style: str,
                                    summary_format: str) -> str:
    """Pass 2 유저 프롬프트 — 데이터 전달 전용"""

    return f"""아래 Compass JSON과 원문을 바탕으로 블로그 글을 작성하세요.

[Compass JSON]
{json.dumps(compass_json, ensure_ascii=False, indent=2)}

[원문 본문]
{crawled_body[:3000]}

[코드가 결정한 값 — 그대로 따를 것]
- intro_style: {intro_style}
- h2_flow: {h2_flow}
- summary_format: {summary_format}
  (요약 블록은 시스템이 처리하므로 본문에 넣지 마세요)

위 시스템 프롬프트의 규칙을 지키며 본문만 작성하세요."""


import pathlib

_EXAMPLES_PATH = pathlib.Path(__file__).parent / "style_examples_compass.md"

def _load_tone_example(tone: str) -> str:
    """style_examples_compass.md에서 톤별 예시 블록 추출"""
    text = _EXAMPLES_PATH.read_text(encoding="utf-8")
    marker = f"[{tone} 예시]"
    start = text.find(marker)
    if start == -1:
        return ""
    end = text.find("\n## ", start + 1)
    block = text[start + len(marker):end] if end != -1 else text[start + len(marker):]
    return block.strip()


def build_blog_system_prompt(tone: str) -> str:
    """Compass Pass 2 시스템 프롬프트 — 축소 버전 v2"""

    # ── 공통 규칙 (모든 톤 공유) ──
    common = """당신은 한국어 테크 뉴스 에디터입니다. 아래 규칙만 지킵니다.

[글자수]
- 본문 1,200자 이상 2,500자 이하 (공백 포함).

[문장 리듬]
- 한 절(clause)은 10~25자. 25자를 넘기면 마침표나 쉼표로 끊는다.
- 문단 사이에 빈 줄 하나를 둔다.
- 같은 주어-서술어 패턴을 연속 2회 사용하지 않는다.

[H2 제목]
- 15자 이내의 짧은 명사구 또는 의문구로 쓴다.
- H2는 3~5개 사용한다. 본문을 의미 단위로 나누는 데 쓴다.
- Compass JSON의 필드값을 그대로 제목에 쓰지 않는다.

[금지]
- 한자(漢字) 직접 사용 금지. 한글로만 쓴다.
- "획기적", "혁신적", "놀라운" 등 과장 수식어 금지.
- 원문에 없는 수치·인용·사실을 추가하지 않는다.
- 본문은 결론 문단으로 자연스럽게 끝납니다.
- 절대 금지: 📌, ✅, ❌, 🔍 등 이모지 마커, "핵심 질문", "요약", "정리하면", "한 줄 요약" — 본문 어디에도 사용하지 않습니다. 이 규칙을 어기면 글 전체가 폐기됩니다.
- slot2_compare가 "없음"이면 비교 문단을 만들지 않는다.

[참고: 요약 블록은 시스템이 본문 뒤에 자동 첨부합니다. 본문에서는 결론 문단으로 끝내세요.]
"""

    # ── 톤별 블록 ──
    tone_blocks = {
        "neutral_careful": """[톤: neutral_careful]
종결어미: ~습니다 / ~했습니다 / ~됩니다
1인칭·감탄사 사용하지 않는다.""",

        "fan_friendly": """[톤: fan_friendly]
종결어미: ~요 / ~해요 / ~었어요 / ~거예요
독자에게 말을 거는 듯한 친근한 어조를 쓴다.""",

        "analytical": """[톤: analytical]
종결어미: ~이다 / ~했다 / ~된다 / ~있다
분석 보고서처럼 건조한 평서체를 쓴다."""
    }

    tone_example = _load_tone_example(tone)
    result = common + "\n" + tone_blocks.get(tone, tone_blocks["neutral_careful"])
    if tone_example:
        result += f"\n\n<완성 글 예시 — 이 분량과 구조를 모방하세요>\n{tone_example}\n</완성 글 예시>"
    result += "\n[최종 확인] 작성 완료 후 글자수를 세어 1,200자 이상인지 반드시 확인한다."
    return result


def _rearrange_h2(compass: dict, h2_flow: list[str]) -> list[str]:
    """Conditionally rearrange H2 order based on slot content (Task 2-1).

    Rules:
    - If slot2_compare contains competitor names, move comparison section earlier.
    - If slot4_outlook contains uncertainty markers, move outlook section later.
    - Otherwise preserve original order.
    """
    import copy
    h2 = copy.deepcopy(h2_flow)
    slot2 = compass.get("slot2_compare", "")
    slot4 = compass.get("slot4_outlook", "")

    _uncertainty_kw = ["가능성", "예상", "불확실", "변동", "미정", "不确定", "전망이"]

    # Rule 1: If slot2_compare has specific competitor names, pull compare forward
    _competitors = ["KT", "SK", "네이버", "카카오", "삼성", "현대", "LG", "하나"]
    has_competitor = any(c in slot2 for c in _competitors)

    # Rule 2: If slot4_outlook has uncertainty, move outlook to position 3
    has_uncertainty = any(u in slot4 for u in _uncertainty_kw)

    if has_competitor and "비교" in h2[1] and len(h2) > 2:
        # Move compare (index 1) to index 0 if it has competitors
        compare_item = h2.pop(1)
        h2.insert(0, compare_item)

    if has_uncertainty and "전망" in h2[-1] and len(h2) > 3:
        # Move outlook (last) to position 3 (4th)
        outlook_item = h2.pop()
        h2.insert(3, outlook_item)

    return h2


def _build_summary_block(summary: str, format: str = "bullet", slot4_outlook: str = "") -> str:
    """Build summary block in specified format (Task 3-2).

    Formats: bullet (default), narrative, key_question, natural_close.
    """
    if format == "key_question" and slot4_outlook:
        return f"{slot4_outlook.rstrip('.')}에서 가장 큰 변수는 무엇일까요?"
    elif format == "natural_close" and slot4_outlook:
        return slot4_outlook
    elif format == "narrative" and summary:
        return summary
    elif format == "bullet" and summary:
        return f"핵심 요약\n{summary}"
    else:
        return ""


def write_compass_article(pitch: dict, all_articles: list, format_choice=None, output_target="naver", skip_g4=False, mode="thread", tone: str = "neutral_careful"):
    """Compass 2-pass writing pipeline.

    Pass 1: LLM generates compass JSON (9 fields).
    G4: fact_gate.check_slot3 on slot3_context vs crawled_body.
    Pass 2: LLM drafts body from compass.

    mode="thread": Returns (compass_dict, {"cards": [...], "link": "..."})
    mode="blog":   Returns (compass_dict, {"body": "markdown...", "link": "..."})
    Returns None on failure.
    """
    try:
        from v3.model_router import chat_completion
    except ImportError:
        try:
            from scripts.threads.v3.model_router import chat_completion
        except ImportError as e:
            _log(f"chat_completion 임포트 실패: {e}")
            return None

    from pipeline.threads.fact_gate import check_slot3
    from pipeline.threads.pitch import detect_prompt_leak
    from pipeline.threads.validator import (
        validate_cards,
        validate_card_structure,
        validate_final_output,
        FORMAT_CARD_COUNT_TOLERANCE,
    )

    crawled_body = pitch.get("crawled_body", "")
    crawled_url = pitch.get("crawled_url", "")

    # ── Compass cache key ──
    article_ids = pitch.get("article_ids", [])
    aid = article_ids[0] if article_ids else ""
    today = datetime.now().strftime("%Y-%m-%d")
    cache_key = (str(aid), today, tone)
    if cache_key in _compass_cache:
        _log(f" compass 캐시 히트: {cache_key}")
        return _compass_cache[cache_key]

    # ── Load independent rotation counters (Task 1-1) ──
    intro_rotation = _load_intro_rotation()
    h2_rotation = _load_h2_rotation()
    _log(f" intro_rotation={intro_rotation} h2_rotation={h2_rotation}")

    # ── Pass 1: compass JSON ──
    _log("Pass 1: compass JSON 생성")
    system_prompt = build_system_prompt_compass()
    user_prompt = _build_pass1_user_prompt(pitch, all_articles)

    compass_raw = chat_completion(
        messages=[{"role": "user", "content": user_prompt}],
        system_prompt=system_prompt,
        temperature=0.4,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )
    if not compass_raw:
        _log("Pass 1 실패: 빈 응답")
        return None

    compass = _parse_compass_json(compass_raw)
    if compass is None:
        _log("Pass 1 실패: JSON 파싱 오류")
        return None

    # Validate 9 required fields
    required = [
        "category", "slot1_fact", "slot2_compare", "slot3_context",
        "slot4_outlook", "intro_style", "h2_flow", "tone", "table_plan",
    ]
    missing = [f for f in required if f not in compass]
    if missing:
        _log(f"Pass 1 실패: 필수 필드 누락 — {missing}")
        return None

    # ── Override intro_style and h2_flow from rotation ──
    compass["tone"] = tone
    # intro_style via weighted_pick (Task 1-2): exclude recent 2
    recent_intros = _recent_intro_styles[-2:] if _recent_intro_styles else []
    compass["intro_style"] = weighted_pick(
        INTRO_STYLES, recent_intros, exclude_count=2
    )

    # h2_flow from category preset via weighted_pick (Task 1-2)
    cat = compass.get("category", "tech")
    presets = H2_FLOW_PRESETS.get(cat, H2_FLOW_PRESETS["tech"])
    recent_h2 = [tuple(_recent_h2_flows[-1])] if _recent_h2_flows else []
    compass["h2_flow"] = weighted_pick(
        presets, recent_h2, exclude_count=2
    )

    # Conditional rearrange (Task 2-1)
    compass["h2_flow"] = _rearrange_h2(compass, compass["h2_flow"])

    _log(f"  category={compass['category']} intro_style={compass['intro_style']}")
    _log(f"  slot3_context={compass.get('slot3_context', '')[:100]}...")

    # Track recent styles for weighted_pick (Task 1-2)
    _recent_intro_styles.append(compass["intro_style"])
    _recent_h2_flows.append(compass["h2_flow"])

    # ── G4 fact-gate on slot3_context ──
    if skip_g4:
        _log("G4 fact-gate: SKIPPED (skip_g4=True)")
    else:
        _log("G4 fact-gate: slot3_context 검증")
        g4_ok, g4_reason = check_slot3(compass["slot3_context"], crawled_body)
        if not g4_ok:
            _log(f"  G4 차단: {g4_reason}")
            return None
        _log(f"  G4 통과: {g4_reason}")

    # ── Pass 2: body draft ──
    if mode == "blog":
        _log("Pass 2: 블로그 본문 초안 생성 (blog mode)")
        blog_sys = build_blog_system_prompt(tone=tone)
        summary_format = weighted_pick(
            ["bullet", "narrative", "key_question", "natural_close"],
            _recent_summary_formats[-2:],
            exclude_count=2,
        )
        assert summary_format in ["bullet", "narrative", "key_question", "natural_close"], f"summary_format 비정상: {summary_format}"
        _log(f"[compass] summary_format={summary_format}")
        _recent_summary_formats.append(summary_format)
        user_prompt2 = _build_blog_pass2_user_prompt(
            compass, crawled_body, compass["h2_flow"], compass["intro_style"], summary_format,
        )

        draft_raw = chat_completion(
            messages=[{"role": "user", "content": user_prompt2}],
            system_prompt=blog_sys,
            temperature=0.5,
            max_tokens=4000,
        )
        if not draft_raw:
            _log("Pass 2 실패: 빈 응답")
            return None

        body = draft_raw.strip()
        if len(body) < 500:
            _log(f"Pass 2 실패: 본문 너무 짧음 ({len(body)}자)")
            return None

        # Leak detection on full body
        leaked, reason = detect_prompt_leak(body)
        if leaked:
            _log(f"  블로그 본문 프롬프트 누출: {reason}")
            return None
        for label in COMPASS_FIELD_LABELS:
            if re.search(rf'{label}\s*[:：]', body):
                _log(f"  블로그 본문 compass 레이블 누출: {label}")
                return None

        # LLM 본문에서 📌 블록이 있으면 제거 (잔여 방지)
        body_clean = re.sub(r'^.*📌.*$', '', body, flags=re.MULTILINE)
        body_clean = re.sub(r'\n{3,}', '\n\n', body_clean).strip()

        # 1,200자 미달 시 확장 재생성 (최대 2회)
        revision = 0
        while len(body_clean) < 1200 and revision < 2:
            revision += 1
            _log(f"[글자수] {len(body_clean)}자 미달 — 확장 재생성 ({revision}/2)")
            rev_prompt = (
                user_prompt2
                + f"\n\n[길이 강제] 현재 본문은 {len(body_clean)}자입니다. 반드시 1,200자 이상으로 확장하세요."
                " 구체적 사실·세부사항·배경을 추가하고, 문장을 길게 쓰며 절 분할을 최소화하세요."
            )
            draft_raw = chat_completion(
                messages=[{"role": "user", "content": rev_prompt}],
                system_prompt=blog_sys,
                temperature=0.5,
                max_tokens=4000,
            )
            if not draft_raw:
                break
            body = draft_raw.strip()
            body_clean = re.sub(r'^.*📌.*$', '', body, flags=re.MULTILINE)
            body_clean = re.sub(r'\n{3,}', '\n\n', body_clean).strip()
            _log(f"[글자수] 확장 결과: {len(body_clean)}자")

        # compass JSON의 slot1_fact + slot4_outlook로 요약 텍스트 생성
        slot4_outlook = compass.get("slot4_outlook", "")
        summary_text_parts = []
        if compass.get("slot1_fact"):
            summary_text_parts.append(compass["slot1_fact"])
        if slot4_outlook:
            summary_text_parts.append(slot4_outlook)
        summary_text = " ".join(summary_text_parts) if summary_text_parts else ""

        if summary_text:
            summary_block = _build_summary_block(summary_text, summary_format, slot4_outlook=slot4_outlook)
            body = body_clean + "\n\n" + summary_block
        else:
            body = body_clean

        # Increment rotation on success
        _save_intro_rotation(intro_rotation + 1)
        _save_h2_rotation(h2_rotation + 1)

        primary_url = crawled_url or ""
        _log(f"✅ Compass 블로그: {len(body)}자")
        result = (compass, {"body": body, "link": primary_url})
        _compass_cache[cache_key] = result
        return result

    else:
        _log("Pass 2: 쓰레드 카드 초안 생성 (thread mode)")
        user_prompt2 = _build_pass2_user_prompt(compass, crawled_body)

        draft_raw = chat_completion(
            messages=[{"role": "user", "content": user_prompt2}],
            system_prompt=system_prompt,
            temperature=0.5,
            max_tokens=3000,
            response_format={"type": "json_object"},
        )
        if not draft_raw:
            _log("Pass 2 실패: 빈 응답")
            return None

        cards = _parse_cards_json(draft_raw)
        if not cards:
            _log("Pass 2 실패: 카드 파싱 오류")
            return None

        # Trim to expected count
        lo, hi = FORMAT_CARD_COUNT_TOLERANCE.get("compass", (3, 8))
        if len(cards) > 5:
            cards = cards[:5]

        # ── Leak detection on each card ──
        for i, card in enumerate(cards, 1):
            leaked, reason = detect_prompt_leak(card)
            if leaked:
                _log(f"  Card {i} 프롬프트 누출: {reason}")
                return None
            for label in COMPASS_FIELD_LABELS:
                if re.search(rf'{label}\s*[:：]', card):
                    _log(f"  Card {i} compass 레이블 누출: {label}")
                    return None

        # ── Validator chain ──
        vc_ok, vc_reason = validate_cards(cards, pitch, "D")
        if not vc_ok:
            _log(f"  validate_cards 실패: {vc_reason}")
            return None

        vs_ok, vs_reason = validate_card_structure(cards)
        if not vs_ok:
            _log(f"  validate_card_structure 실패: {vs_reason}")
            return None

        vf_ok, vf_reason = validate_final_output(cards, crawled_body)
        if not vf_ok:
            _log(f"  validate_final_output 실패: {vf_reason}")
            return None

        # ── Increment rotation on success ──
        _save_intro_rotation(intro_rotation + 1)
        _save_h2_rotation(h2_rotation + 1)

        # ── Naver HTML wrapping ──
        if output_target == "naver":
            cards = _wrap_naver_html(cards)

        primary_url = crawled_url or ""
        _log(f"✅ Compass 쓰레드: {len(cards)}개 카드")
        result = (compass, {"cards": cards, "link": primary_url})
        _compass_cache[cache_key] = result
        return result


def _parse_compass_json(text: str) -> dict | None:
    """Parse compass JSON from LLM response."""
    text = text.strip()
    if text.startswith("```"):
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            text = m.group(1)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    # Brace extraction
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return None


def _parse_cards_json(text: str) -> list[str]:
    """Parse cards list from LLM response JSON."""
    text = text.strip()
    if text.startswith("```"):
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            text = m.group(1)
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "cards" in data:
            cards = data["cards"]
            if isinstance(cards, list):
                return [str(c).strip() for c in cards if c]
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, dict) and "cards" in data:
                cards = data["cards"]
                if isinstance(cards, list):
                    return [str(c).strip() for c in cards if c]
        except json.JSONDecodeError:
            pass
    return []