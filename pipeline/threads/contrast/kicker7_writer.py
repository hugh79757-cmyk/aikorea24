"""kicker7 v3 글쓰기 — orchestrator 컬렉션(다각도+배경) 재사용.

orchestrator.run_contrast_thread(writer_fn=write_kicker7_thread) 형태로 호출.
수집된 seed/배경/교차 기사 본문을 SYSTEM_KICKER7_V3에 주입하고,
생성된 카드 말미에 정보소스 원문 URL을 `🔗 url` 형태로 후처리 삽입한다
(참고: scripts/threads/ARCHITECTURE.md:292 assemble_final / publisher.py:210 🔗 루트 답글 패턴).
"""
import sys, json, pathlib, re

_root = pathlib.Path(__file__).resolve().parents[3]
_threads_path = _root / "scripts" / "threads"
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
if str(_threads_path) not in sys.path:
    sys.path.insert(0, str(_threads_path))

from pipeline.infra.logger import get_scrubbed_logger  # noqa
logger = get_scrubbed_logger(__name__)

from pipeline.threads.contrast.prompts import SYSTEM_KICKER7_V3  # noqa
from pipeline.threads.person_gate import person_gate  # noqa


def _body_of(art: dict, limit: int = 3000) -> str:
    b = art.get("crawled_body") or art.get("body") or ""
    return b.strip()[:limit]


_DATE_RE = re.compile(
    r"\d{4}년\s*\d{1,2}월\s*\d{1,2}일|\d{1,2}월\s*\d{1,2}일|\d{4}년\s*\d{1,2}월|\d{4}년"
)


_MATERIAL_REPORT_RE = re.compile(r"^\s*\[재료 신고[^\]]*\]\s*$", re.MULTILINE)

_REDUNDANT_ORIGIN_RE = re.compile(r"\(\s*원문:\s*([^)]*)\)")


def _strip_redundant_original(cards: list[str]) -> list[str]:
    """결정적 후처리: 인라인 (원문: ...) 병기는 전부 제거 (2026-09-05 사용자 요청).
    카드6의 '원문: URL' 형태(괄호 없음)는 본 RE가 매칭 안 함 — 영향 없음."""
    out = [_REDUNDANT_ORIGIN_RE.sub("", c).strip() for c in cards]
    return out


def _strip_material_reports(cards: list[str]) -> tuple[list[str], list[str]]:
    """규칙14 신호는 파이프라인 내부용. 발행 카드 본문에서는 제거(프롬프트 릭 방지),
    제거된 신호는 로그용으로 반환."""
    import re
    cleaned = []
    reports = []
    for c in cards:
        found = _MATERIAL_REPORT_RE.findall(c)
        if found:
            reports.extend(found)
        c2 = _MATERIAL_REPORT_RE.sub("", c).strip("\n ").strip()
        if c2:
            cleaned.append(c2)
    return cleaned, reports


def _strip_date_from_first_sentence(card1: str) -> str:
    """규칙8 강제: 카드1 첫 문장에 날짜(연/월/일) 단어 배제. 첫 문장만 처리."""
    import re
    # 첫 문장 분리 (종결어미/줄바꿈 기준)
    m = re.split(r"(?<=[.!?])\s+|\n", card1, maxsplit=1)
    first = m[0]
    rest = m[1] if len(m) > 1 else ""
    cleaned = _DATE_RE.sub("", first).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    if not cleaned:
        return card1
    return (cleaned + ("\n\n" + rest if rest else "")) if rest else cleaned


def _parse_kicker7_cards(text: str) -> list[str]:
    """'--- 카드 N ---' / '--- 판단 ---' / plain '---' 구분자로 카드 분리.

    ponytail: 모델이 헤더 없는 plain '---'만 쓰는 경우가 많아 둘 다 경계로 인정.
    '--- 카드 6 ---'(텍스트 포함)은 HDR 매칭, plain '---'(3+ dash only)은 PLAIN 매칭.
    """
    import re
    lines = text.splitlines()
    cards: list[str] = []
    buf: list[str] = []
    hdr = re.compile(r"^---\s*(카드\s*\d+|판단)\s*---$", re.IGNORECASE)
    plain = re.compile(r"^-{3,}\s*$")
    for ln in lines:
        s = ln.strip()
        if hdr.match(s) or plain.match(s):
            if buf:
                body = "\n".join(buf).strip()
                if body:
                    cards.append(body)
            buf = []
            continue
        buf.append(ln)
    if buf:
        body = "\n".join(buf).strip()
        if body:
            cards.append(body)
    # fallback: 구분자 없으면 그대로 1카드
    if not cards and text.strip():
        return [text.strip()]
    return cards


def write_kicker7_thread(bundle: dict, all_articles=None, gate_signal=None) -> dict | None:
    af = bundle.get("af") or {}
    seed = bundle.get("seed_article") or {}
    backgrounds = bundle.get("backgrounds") or []
    cross = bundle.get("cross_articles") or []

    parts = []
    seed_body = _body_of(seed, 3000)
    if seed_body:
        parts.append(f"[시드 기사]\n제목: {seed.get('title','')}\n본문:\n{seed_body}")
    for b in backgrounds[:3]:
        bb = _body_of(b, 2000)
        if bb:
            parts.append(f"[배경 기사]\n제목: {b.get('title','')}\n본문:\n{bb}")
    for c in cross[:5]:
        cb = _body_of(c, 1500)
        if cb:
            parts.append(f"[교차 기사]\n제목: {c.get('title','')}\n본문:\n{cb}")
    related = "\n\n".join(parts)

    af_dump = json.dumps({k: af.get(k) for k in ["A", "B", "C", "D", "E", "F"]},
                         ensure_ascii=False, indent=2)

    # person_gate: 통과 여부와 무관하게 항상 생성. 신호만 카드 구성 분기용.
    # gate_signal 주입 시 중복 호출 방지(운영: route_person_stories가 1회 호출 후 전달).
    if gate_signal is not None:
        gate = gate_signal
    else:
        gate = person_gate(seed.get("title", ""), seed_body) if seed_body else {"pass": False}
    if gate.get("pass"):
        signal = ("[신호] 인물·직접 인용·구체적 대가 확인됨 — 카드4 현장 목소리와 "
                  "카드5 책임지도/인적 대가를 추출 사실 기반으로 강화하라.")
    else:
        signal = ("[신호] 인물·인용·대가 미확인 — 카드4/카드5는 JSON의 행위자·수치·사실 위주로만 "
                  "작성하고, 추정·과장·일반론을 금지한다.")

    user = (
        f"[기사 메타]\n- 제목: {seed.get('title','')}\n"
        f"- 발행일: {seed.get('pub_date','')}\n- 매체: {seed.get('source','')}\n\n"
        f"[추출 사실 A~F]\n{af_dump}\n\n"
        f"[관련 기사/배경 — 다각도 취재]\n{related}\n\n"
        f"{signal}\n\n"
        "이제 카드 1부터 작성하라.\n"
    )
    try:
        from scripts.threads.v3.model_router import chat_completion
    except Exception:
        from v3.model_router import chat_completion

    txt = chat_completion(
        messages=[{"role": "user", "content": user}],
        system_prompt=SYSTEM_KICKER7_V3,
        temperature=0.35,
        max_tokens=8000,
        extra_body={"thinking": {"type": "disabled"}},
    )
    if not txt:
        logger.info("kicker7 writer: empty response")
        return None

    cards = _parse_kicker7_cards(txt)
    if not cards:
        logger.info("kicker7 writer: parse failed")
        return None

    # 규칙8 결정적 강제: 카드1 첫 문장 날짜 배제 (모델 준수 실패 방지)
    if len(cards) >= 1:
        fixed = _strip_date_from_first_sentence(cards[0])
        if fixed != cards[0]:
            logger.info("kicker7 writer: 카드1 첫 문장 날짜 제거 적용")
            cards[0] = fixed

    # 규칙14 신호는 내부용 — 발행 카드에서 제거(프롬프트 릭 방지), 로그에 보관
    cards, reports = _strip_material_reports(cards)
    if reports:
        logger.info("kicker7 writer: 재료 신고 제거(발행 제외) %s", reports)

    # 결정적 후처리: 순수 한국어 (원문:) 중복 제거 (모델 미준수 대비)
    before = sum(1 for c in cards if _REDUNDANT_ORIGIN_RE.search(c))
    cards = _strip_redundant_original(cards)
    after = sum(1 for c in cards if _REDUNDANT_ORIGIN_RE.search(c))
    if before != after:
        logger.info("kicker7 writer: 중복 (원문:) 제거 %d→%d", before, after)

    # 카드6 출처 — 시스템이 결정적으로 부착 (LLM이 URL 출력 금지 규칙 준수 보장)
    primary_url = seed.get("link") or seed.get("url") or ""
    b_n = len(af.get("B") or [])
    c_n = len(af.get("C") or [])
    source_name = seed.get("source") or ""
    pub_date = seed.get("pub_date") or ""
    if not any(c.startswith("출처:") or c.startswith("--- 카드 6") for c in cards):
        cards.append(
            f"--- 카드 6 ---\n출처: {source_name}\n발행일: {pub_date}\n"
            f"원문: {primary_url}\n추출 사실: B {b_n}건 / C {c_n}건"
        )

    search_meta = bundle.get("search_meta") or {}
    logger.info("kicker7 writer: %d cards (cross=%s bg=%s gate=%s)", len(cards),
                search_meta.get("cross_n"), search_meta.get("bg_n"), gate.get("pass"))
    return {"cards": cards, "link": primary_url}
