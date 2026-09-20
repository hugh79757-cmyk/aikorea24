"""pipeline/threads/compass.py — Compass 2-pass writing system for Threads pipeline."""
import json
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
]

H2_FLOW_PRESETS = {
    "tech": [
        "기술적 배경과 핵심 원리",
        "현황과 주요 수치",
        "적용 분야와 기대 효과",
        "한계와 과제",
        "향후 전망",
    ],
    "business": [
        "시장 배경과 규모",
        "핵심 비즈니스 모델",
        "경쟁 구도와 주요 플레이어",
        "실적과 수치",
        "향후 전략과 전망",
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

# Compass JSON field labels for leak detection
COMPASS_FIELD_LABELS = [
    "slot1_fact",
    "slot2_compare",
    "slot3_context",
    "slot4_outlook",
    "intro_style",
    "h2_flow",
]

# Naver HTML tag whitelist for formal article output
_NAVER_TAG_WHITELIST = (
    "p, h2, h3, strong, b, blockquote, hr, ul, ol, li, table, img, a"
)

# Disallowed tags for Naver output
_NAVER_TAG_STRIP_RE = re.compile(
    r"<(/?)(div|span|style|class|font|center|section|article|aside|nav|header|footer|main|details|summary|dialog|figure|figcaption|time|mark|small|del|ins|sub|sup|abbr|address|cite|code|pre|var|samp|kbd|output)[^>]*>",
    re.IGNORECASE,
)

_POSTED_JSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "posted.json"
)

# Module-level cache: (article_id, date_str) -> (compass, output)
_compass_cache: dict[tuple, tuple] = {}


def _log(msg):
    from datetime import datetime
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] [compass] {msg}')


def _load_compass_rotation() -> int:
    """Load compass_intro_rotation counter from posted.json."""
    try:
        if os.path.exists(_POSTED_JSON_PATH):
            with open(_POSTED_JSON_PATH) as f:
                data = json.load(f)
            return data.get("compass_intro_rotation", 0)
    except Exception:
        pass
    return 0


def _save_compass_rotation(counter: int) -> None:
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


def _wrap_naver_html(cards: list[str]) -> list[str]:
    """Wrap card text in Naver tag-whitelist HTML, strip disallowed tags."""
    wrapped = []
    for card in cards:
        # Strip disallowed tags
        clean = _NAVER_TAG_STRIP_RE.sub("", card)
        # Convert markdown-style headings to <h2>
        clean = re.sub(
            r"^#{1,3}\s+(.+)$", r"<h2>\1</h2>", clean, flags=re.MULTILINE
        )
        # Wrap non-tag lines in <p>
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
        "마지막 카드는 반드시 답글을 유도하는 열린 형태로 끝낼 것 (질문, 의견 요청, 또는 독자 참여 유도).\n"
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
        "- slot2_compare: 비교/대비 포인트 (한 줄)\n"
        "- slot3_context: 배경 맥락 (2~3문장, 출처 기반)\n"
        "- slot4_outlook: 향후 전망 (한 줄)\n"
        "- intro_style: self_identity_call/number_shock/reversal/contrast/conflicting_fact 중 택1\n"
        "- h2_flow: category에 맞는 H2 흐름 리스트 (5개)\n"
        "- tone: neutral_careful/fan_friendly/analytical 중 택1\n"
        "- table_plan: 본문에서 사용할 표 정보 (없으면 null)\n"
    )


def _build_pass2_user_prompt(compass: dict, crawled_body: str) -> str:
    """Build user prompt for Pass 2 body draft generation."""
    compass_header = json.dumps(compass, ensure_ascii=False, indent=2)
    return (
        f"[컴퍼스]\n{compass_header}\n\n"
        f"[출처 본문 (앞 4000자)]\n{crawled_body[:4000]}\n\n"
        "위 컴퍼스를 참고하여 쓰레드 카드 본문을 작성하세요.\n"
        "컴퍼스의 h2_flow 순서를 따르세요.\n"
        "각 카드는 짧은 절 단위로 줄바꿈, 절 사이 빈 줄.\n"
        "출력은 JSON만: {\"cards\": [\"card1\", \"card2\", ...]}\n"
        "카드 수는 5개."
    )


def write_compass_article(pitch: dict, all_articles: list, format_choice=None, output_target="naver", skip_g4=False):
    """Compass 2-pass writing pipeline.

    Pass 1: LLM generates compass JSON (9 fields).
    G4: fact_gate.check_slot3 on slot3_context vs crawled_body.
    Pass 2: LLM drafts body from compass.
    Returns (compass_dict, {"cards": [...], "link": "..."}) or None on failure.
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
    cache_key = (str(aid), today)
    if cache_key in _compass_cache:
        _log(f" compass 캐시 히트: {cache_key}")
        return _compass_cache[cache_key]

    # ── Load rotation counter ──
    rotation = _load_compass_rotation()
    _log(f" rotation counter: {rotation}")

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
    compass["intro_style"] = INTRO_STYLES[rotation % len(INTRO_STYLES)]
    cat = compass.get("category", "tech")
    presets = H2_FLOW_PRESETS.get(cat, H2_FLOW_PRESETS["tech"])
    # Rotate the h2_flow list so different runs start with different headings
    offset = rotation % len(presets)
    compass["h2_flow"] = presets[offset:] + presets[:offset]

    _log(f"  category={compass['category']} intro_style={compass['intro_style']}")
    _log(f"  slot3_context={compass.get('slot3_context', '')[:100]}...")

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
    _log("Pass 2: 본문 초안 생성")
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
        # Also check compass field label leakage
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
    _save_compass_rotation(rotation + 1)

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
