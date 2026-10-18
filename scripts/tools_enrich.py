#!/usr/bin/env python3
"""도구 상세페이지 심화(enrich) — 기존 섹션은 그대로 두고 심층 섹션을 추가한다.

배경 (AIK24-TOOLSTHIN-02 실측)
  상세페이지 412개 중 397개가 동일한 8섹션 템플릿이고, 섹션당 내용은 평균 146자(1~3줄)다.
  사용법·요금 한도·한국어 출력 실측·주의사항·대안 비교는 생성 스키마에 아예 없어
  페이지가 '한 줄 쓰고 끝'으로 읽힌다. 이 스크립트는 그 빈 자리를 채우고,
  필요하면 표준 8섹션(--with-standard)까지 함께 생성해 얇은 본문을 살린다.

원칙
  - 기존 섹션 문장은 삭제하지 않는다(추가·병합만).
  - 가격·수치는 크롤링 텍스트에 근거가 있을 때만 쓰게 하고, 없으면 '확인 필요'로 명시한다.
  - 게이트(분량·금지어·프롬프트 릭·평서체 비율)를 통과하지 못하면 재생성 1회 후 실패 처리한다.

사용 예
  python3 scripts/tools_enrich.py --dry-run                        # 대상/현황만 (LLM 호출 없음)
  python3 scripts/tools_enrich.py --slug spriteframe --with-standard --apply
  python3 scripts/tools_enrich.py --min-body 600 --with-standard --apply --jobs 2
  python3 scripts/tools_enrich.py --list scripts/logs/tmp_sections/enrich30.txt --apply --jobs 3
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "threads" / "v3"))

TOOLS_DIR = ROOT / "src" / "content" / "tools"

try:
    from tools_collector import (  # noqa: E402
        SYSTEM_PROMPT as HOUSE_SYSTEM,
        USER_PROMPT_TEMPLATE,
        build_body,
        chat_completion,
        crawl_tool_page,
        humanize_md,
    )
except Exception as e:  # pragma: no cover
    print(f"[FATAL] tools_collector import 실패: {type(e).__name__}: {e}")
    sys.exit(2)

# ── 섹션 순서 (기존 8섹션 + 신규 심화 섹션) ─────────────────────────────────
ORDER = [
    "한줄 요약", "핵심 기능", "사용법",
    "가격 정책", "요금제 자세히",
    "한국어 지원", "한국어 품질 실측",
    "이런 분에게 추천합니다", "실제 활용 예시",
    "유사 툴과 비교", "대안 도구 비교",
    "장단점", "주의사항", "자주 묻는 질문",
]

DEEP_SYSTEM = HOUSE_SYSTEM + """

[심화 섹션 작성 규칙 — 위 규칙에 추가로 적용]
• 섹션끼리 같은 내용을 반복하지 않습니다. 같은 문장을 두 번 쓰지 않습니다.
• 가격·한도·크레딧 같은 수치는 [크롤링 텍스트]에 근거가 있을 때만 씁니다.
  근거가 없으면 "정확한 금액과 한도는 공식 요금 페이지에서 확인이 필요합니다"처럼 확인 필요를 밝힙니다.
• 한국어 결과 예시는 실제 화면을 본 것처럼 단정하지 말고, 이 도구가 낼 법한 형태의 예시로 씁니다.
• 확인되지 않은 기능을 만들어내지 않습니다. 모르면 "확인이 필요합니다"라고 씁니다.
• 모든 문장은 "~습니다/~합니다" 체입니다.
• 출력 전에 조사(은/는·이/가·을/를·으로/로)와 맞춤법을 스스로 점검합니다.
"""

DEEP_USER = """다음 AI 도구의 상세페이지에 넣을 심층 정보를 JSON 으로 작성하세요.

도구명: __NAME__
한줄 설명: __DESC__
분류: __CATEGORY__
가격 표기(수집값): __PRICE__
URL: __URL__
한국어 지원: __KOREAN__
난이도: __DIFF__
기존 수록 정보(요약): __EXISTING__

[크롤링 텍스트 — 사실 근거. 여기에 없는 수치는 쓰지 마세요]
__CRAWLED__

반환 형식 (이 JSON 구조만 출력. 빈 배열·빈 문자열 금지):
{
  "howto": [
    {"step": "1. 첫 단계 (동작 중심 20자 이내)", "detail": "무엇을 어떻게 하는지 2~3문장. 화면 위치·입력값을 구체적으로."}
  ],
  "pricing_detail": {
    "free_limits": "무료로 쓸 수 있는 범위 2~3문장 (메시지 수·크레딧·해상도·워터마크 등)",
    "paid_plans": [
      {"name": "플랜명", "price": "금액 (달러·원화 병기, 모르면 '공식 페이지 확인 필요')", "includes": "포함 내용 1~2문장"}
    ],
    "refund_note": "환불·해지·결제 관련 1~2문장"
  },
  "korean_test": {
    "cases": [
      {"task": "업무 상황 (12자 이내)", "prompt": "한국어로 실제 입력할 프롬프트 1~2문장",
       "expected_output": "이 도구가 낼 결과 예시 2~3문장", "note": "한국어 품질 관찰 1문장"}
    ],
    "overall": "한국어 품질 총평 2~3문장 (번역투·띄어쓰기·존댓말·전문용어 처리)"
  },
  "pros_cons": {
    "pros": ["구체적인 장점 4개 (각 1문장, 25자 이상)"],
    "cons": ["구체적인 단점 3개 (각 1문장, 25자 이상)"]
  },
  "cautions": [
    {"title": "개인정보", "detail": "1~2문장"}
  ],
  "alternatives": [
    {"name": "대안 도구명", "price": "가격대", "korean": "한국어 지원 수준", "best_for": "이 대안이 더 나은 경우", "weakness": "약점"}
  ],
  "faq_extra": [
    {"q": "실제로 검색할 법한 질문", "a": "2~3문장 (이유와 예외 포함)"}
  ]
}
개수 기준: howto 4개 · paid_plans 2~3개 · korean_test.cases 2개 · pros 4개/cons 3개 ·
cautions 4개(개인정보·저작권/상업적 이용·요금/한도·계정 관리) · alternatives 3개 · faq_extra 4개.
"""

MIN_LEN = {
    "사용법": 300, "요금제 자세히": 200, "한국어 품질 실측": 400,
    "장단점": 250, "주의사항": 200, "대안 도구 비교": 250,
}
MIN_FAQ_EXTRA = 300
MIN_TOTAL_NEW = 1800

BANNED = (
    "사실상", "실질적으로", "결론적으로", "혁신적인", "획기적인", "파격적인",
    "본질적으로", "지평을 열", "시대가 도래", "라고 할 수 있습니다",
)
LEAK = ("```", "tool_detail", "faq_extra", "korean_test", "pros_cons", "pricing_detail", '"howto"')


# ── md 파싱/조립 ─────────────────────────────────────────────────────────
def split_frontmatter(text: str) -> tuple[str, str, str]:
    if not text.startswith("---"):
        return "\x00", text, ""
    end = text.find("\n---", 3)
    if end == -1:
        return "\x00", text, ""
    return text[3:end], text[end + 4:], text[end:end + 4]


def fm_value(fm: str, key: str) -> str:
    m = re.search(rf'^{key}\s*:\s*"?(.*?)"?\s*$', fm, re.M)
    return m.group(1).strip() if m else ""


def parse_sections(body: str) -> tuple[str, list[tuple[str, str]]]:
    """(도입부, [(제목, 내용)]) — 첫 H2 앞 텍스트는 도입부로 보존."""
    parts = re.split(r"^## +(.+)$", body, flags=re.M)
    lead = parts[0]
    secs: list[tuple[str, str]] = []
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        content = (parts[i + 1] if i + 1 < len(parts) else "").strip()
        secs.append((title, content))
    return lead, secs


def compose(body_lead: str, secs: list[tuple[str, str]], new: dict[str, str]) -> str:
    have = dict(secs)
    out: list[str] = []
    used: set[str] = set()
    for title in ORDER:
        content = have.get(title, "").strip() or new.get(title, "").strip()
        if not content:
            continue
        if title == "자주 묻는 질문" and new.get("__faq_extra__"):
            content = content + "\n\n" + new["__faq_extra__"]
        out.append(f"## {title}\n\n{content}\n")
        used.add(title)
    for title, content in secs:  # ORDER 에 없는 기존 섹션은 원문 그대로 뒤에 보존
        if title in used or not content.strip():
            continue
        out.append(f"## {title}\n\n{content.strip()}\n")
    body = body_lead.rstrip("\n")
    sections = "\n".join(out)
    joined = (body + "\n\n" + sections) if body.strip() else sections
    return joined.rstrip("\n") + "\n"


# ── 렌더러 ───────────────────────────────────────────────────────────────
def render_howto(items: list) -> str:
    lines = []
    for i, it in enumerate(items, 1):
        if not isinstance(it, dict):
            continue
        step = re.sub(r"^\s*\d+[.)]?\s*", "", str(it.get("step", "")).strip())
        detail = str(it.get("detail", "")).strip()
        if not step and not detail:
            continue
        lines.append(f"**{i}. {step}**\n\n{detail}\n")
    return "\n".join(lines).strip()


def render_pricing(pd: dict) -> str:
    lines = []
    if pd.get("free_limits"):
        lines.append(f"- **무료로 쓸 수 있는 범위**: {pd['free_limits']}\n")
    for plan in pd.get("paid_plans", []) or []:
        if not isinstance(plan, dict):
            continue
        name = str(plan.get("name", "")).strip()
        price = str(plan.get("price", "")).strip()
        inc = str(plan.get("includes", "")).strip()
        lines.append(f"- **{name}** ({price}): {inc}\n")
    if pd.get("refund_note"):
        lines.append(f"**환불과 해지**: {pd['refund_note']}\n")
    return "\n".join(lines).strip()


def render_korean(kt: dict) -> str:
    lines = []
    for c in kt.get("cases", []) or []:
        if not isinstance(c, dict):
            continue
        lines.append(f"**{str(c.get('task', '')).strip()}**\n")
        if c.get("prompt"):
            lines.append(f"- 프롬프트: {c['prompt']}")
        if c.get("expected_output"):
            lines.append(f"- 결과 예시: {c['expected_output']}")
        if c.get("note"):
            lines.append(f"- 관찰: {c['note']}")
        lines.append("")
    if kt.get("overall"):
        lines.append(str(kt["overall"]).strip())
    return "\n".join(lines).strip()


def render_pros_cons(pc: dict) -> str:
    pros = [str(p).strip() for p in (pc.get("pros") or []) if str(p).strip()]
    cons = [str(c).strip() for c in (pc.get("cons") or []) if str(c).strip()]
    parts = []
    if pros:
        parts.append("**장점**\n\n" + "\n".join(f"- {p}" for p in pros))
    if cons:
        parts.append("**단점**\n\n" + "\n".join(f"- {c}" for c in cons))
    return "\n\n".join(parts).strip()


def render_cautions(items: list) -> str:
    lines = []
    for c in items or []:
        if not isinstance(c, dict):
            continue
        title = str(c.get("title", "")).strip()
        detail = str(c.get("detail", "")).strip()
        lines.append(f"- **{title}**: {detail}" if title else f"- {detail}")
    return "\n".join(lines).strip()


def render_alternatives(items: list) -> str:
    rows = [x for x in (items or []) if isinstance(x, dict)]
    if not rows:
        return ""
    lines = ["| 도구 | 가격 | 한국어 | 잘 맞는 경우 | 약점 |", "|---|---|---|---|---|"]
    for a in rows:
        cells = [str(a.get(k, "")).replace("|", "/").replace("\n", " ").strip()
                 for k in ("name", "price", "korean", "best_for", "weakness")]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines).strip()


def render_faq_extra(items: list) -> str:
    lines = []
    for f in items or []:
        if not isinstance(f, dict):
            continue
        lines.append(f"**{str(f.get('q', '')).strip()}**\n\n{str(f.get('a', '')).strip()}\n")
    return "\n".join(lines).strip()


# ── 게이트 ───────────────────────────────────────────────────────────────
def plain_style_ratio(text: str) -> float:
    """'~한다/~이다' 평서체 종결 비율. '~합니다/습니다' 는 제외."""
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sents:
        return 0.0
    plain = 0
    for s in sents:
        if re.search(r"(?<!니)(?<!요)다\.?$", s):
            plain += 1
    return plain / len(sents)


def gate(new: dict[str, str], faq_extra: str) -> list[str]:
    issues = []
    for title, minimum in MIN_LEN.items():
        got = len(new.get(title, ""))
        if got < minimum:
            issues.append(f"{title} {got}자 < {minimum}자")
    if len(faq_extra) < MIN_FAQ_EXTRA:
        issues.append(f"FAQ 추가분 {len(faq_extra)}자 < {MIN_FAQ_EXTRA}자")
    total = sum(len(v) for k, v in new.items() if not k.startswith("__")) + len(faq_extra)
    if total < MIN_TOTAL_NEW:
        issues.append(f"신규 총량 {total}자 < {MIN_TOTAL_NEW}자")
    blob = "\n".join(list(new.values()) + [faq_extra])
    for w in BANNED:
        if w in blob:
            issues.append(f"금지 표현 '{w}'")
    for w in LEAK:
        if w in blob:
            i = blob.find(w)
            issues.append(f"프롬프트 릭 '{w}' … {blob[max(0, i - 30):i + 30]!r}")
    ratio = plain_style_ratio(blob)
    if ratio > 0.20:
        issues.append(f"평서체 비율 {ratio:.0%} > 20%")
    return issues


def deep_prompt(name: str, meta: dict, crawled: str, existing: str) -> str:
    return (DEEP_USER
            .replace("__NAME__", name)
            .replace("__DESC__", meta["desc"])
            .replace("__CATEGORY__", meta["category"])
            .replace("__PRICE__", meta["price"])
            .replace("__URL__", meta["url"])
            .replace("__KOREAN__", meta["korean"])
            .replace("__DIFF__", meta["difficulty"])
            .replace("__EXISTING__", existing[:600])
            .replace("__CRAWLED__", crawled[:3500]))


def parse_json(raw: str) -> dict | None:
    if not raw:
        return None
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if m:
        raw = m.group(1)
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None


def generate_standard(name: str, meta: dict, crawled: str) -> str:
    """기존 파이프라인과 같은 프롬프트·렌더러로 표준 8섹션 본문을 만든다(빈 본문 페이지용)."""
    prompt = (USER_PROMPT_TEMPLATE
              .replace("__NAME__", name)
              .replace("__DESCRIPTION__", meta["desc"])
              .replace("__PRICE__", meta["price"])
              .replace("__URL__", meta["url"])
              .replace("__CRAWLED_PRICING__", crawled[:1200]))
    raw = chat_completion(messages=[{"role": "user", "content": prompt}],
                          system_prompt=HOUSE_SYSTEM, temperature=0.5, max_tokens=3000)
    data = parse_json(raw)
    if not data:
        return ""
    return build_body({"tool_detail": data.get("tool_detail") or {}}) if data.get("tool_detail") else ""


def enrich_one(slug: str, apply: bool, with_standard: bool, dump: str = "") -> dict:
    t0 = time.time()
    path = TOOLS_DIR / f"{slug}.md"
    if not path.exists():
        return {"slug": slug, "ok": False, "why": "md 없음"}
    text = path.read_text(encoding="utf-8")
    fm, body, _ = split_frontmatter(text)
    if fm == "\x00":
        return {"slug": slug, "ok": False, "why": "frontmatter 없음"}
    lead, secs = parse_sections(body)
    have = {t for t, _ in secs}

    name = fm_value(fm, "name")
    meta = {
        "desc": fm_value(fm, "description"),
        "category": fm_value(fm, "category"),
        "price": fm_value(fm, "price"),
        "url": fm_value(fm, "url").strip('"'),
        "korean": fm_value(fm, "koreanSupport"),
        "difficulty": fm_value(fm, "difficulty"),
    }
    existing = re.sub(r"\s+", " ", body)[:900]
    crawled = ""
    try:
        c = crawl_tool_page(meta["url"])
        crawled = " ".join(filter(None, [c.get("description", ""), c.get("pricing_text", "")]))
    except Exception:
        crawled = ""

    prompt = deep_prompt(name, meta, crawled, existing)
    issues: list[str] = []
    for attempt in (1, 2):
        raw = chat_completion(
            messages=[{"role": "user", "content": prompt + ("\n\n이전 시도가 다음을 못 맞췄습니다: "
                                                             + "; ".join(issues) + "\n더 구체적으로 다시 작성하세요." if issues else "")}],
            system_prompt=DEEP_SYSTEM,
            temperature=0.55,
            max_tokens=6000,
        )
        data = parse_json(raw)
        if not data:
            issues = ["JSON 파싱 실패"]
            continue
        howto = render_howto(data.get("howto") or [])
        pricing = render_pricing(data.get("pricing_detail") or {})
        korean = render_korean(data.get("korean_test") or {})
        proscons = render_pros_cons(data.get("pros_cons") or {})
        cautions = render_cautions(data.get("cautions") or [])
        alts = render_alternatives(data.get("alternatives") or [])
        faq_extra = render_faq_extra(data.get("faq_extra") or [])

        new = {
            "사용법": humanize_md(howto),
            "요금제 자세히": humanize_md(pricing),
            "한국어 품질 실측": humanize_md(korean),
            "장단점": humanize_md(proscons),
            "주의사항": humanize_md(cautions),
            "대안 도구 비교": alts,
        }
        if with_standard and len(secs) < 4:
            # 표준 섹션이 이미 있는 페이지는 건너뛴다(불필요한 호출·중복 생성 방지).
            std_body = generate_standard(name, meta, crawled)
            for t, c in parse_sections(std_body)[1]:
                if t not in have and t not in new and c.strip():
                    new[t] = c  # 기존 섹션은 건드리지 않고 빈 자리만 채운다
        issues = gate(new, faq_extra)
        if not issues:
            merged = compose(lead, secs, {**new, "__faq_extra__": faq_extra})
            # 앞 경계 개행 필수 — fm 은 닫는 '---' 앞 개행을 포함하지 않는다(split_frontmatter 계약).
            document = f"---{fm.rstrip()}\n---\n\n{merged}"
            if dump:
                d = Path(dump)
                d.mkdir(parents=True, exist_ok=True)
                (d / f"{slug}.md").write_text(document, encoding="utf-8")
            if apply:
                path.write_text(document, encoding="utf-8")
            return {
                "slug": slug, "ok": True, "written": apply, "secs": time.time() - t0,
                "new_chars": sum(len(v) for k, v in new.items() if not k.startswith("__")) + len(faq_extra),
                "before": len(body), "after": len(merged),
                "sections": [t for t in ORDER if t in new or t in have],
                "rounds": attempt,
            }
    return {"slug": slug, "ok": False, "why": "게이트 미통과: " + "; ".join(issues[:4])}


def targets(min_body: int, slugs: list[str], list_file: str | None) -> list[str]:
    if slugs:
        return slugs
    if list_file:
        return [l.strip() for l in Path(list_file).read_text(encoding="utf-8").split() if l.strip()]
    out = []
    for p in sorted(TOOLS_DIR.glob("*.md")):
        fm, body, _ = split_frontmatter(p.read_text(encoding="utf-8"))
        if fm == "\x00":
            continue
        if min_body and len(body.strip()) >= min_body:
            continue
        if not min_body and "## 사용법" in body:
            continue  # 이미 심화된 페이지는 건너뛴다
        out.append(p.stem)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="실제 md 갱신(없으면 미리보기만)")
    ap.add_argument("--slug", default="", help="쉼표 구분 슬러그")
    ap.add_argument("--list", default="", help="슬러그 목록 파일")
    ap.add_argument("--min-body", type=int, default=0, help="본문이 이 글자 수 미만인 페이지만")
    ap.add_argument("--with-standard", action="store_true", help="빈 본문이면 표준 섹션도 생성")
    ap.add_argument("--jobs", type=int, default=1, help="동시 실행 수")
    ap.add_argument("--dump", default="", help="결과 본문을 검토용으로 저장할 디렉터리")
    args = ap.parse_args()

    slugs = [s.strip() for s in args.slug.split(",") if s.strip()] if args.slug else []
    tg = targets(args.min_body, slugs, args.list or None)
    t0 = time.time()
    print(f"대상 {len(tg)}건 · apply={args.apply} · with_standard={args.with_standard} · jobs={args.jobs}")
    if not tg:
        return 0

    if args.jobs <= 1:
        results = [enrich_one(s, args.apply, args.with_standard, args.dump) for s in tg]
    else:
        results = []
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futs = {pool.submit(enrich_one, s, args.apply, args.with_standard, args.dump): s for s in tg}
            for f in as_completed(futs):
                try:
                    results.append(f.result())
                except Exception as e:
                    results.append({"slug": futs[f], "ok": False, "why": f"{type(e).__name__}: {e}"})

    ok = [r for r in results if r.get("ok")]
    ng = [r for r in results if not r.get("ok")]
    for r in ok:
        print(f"  ✅ {r['slug']:34s} +{r['new_chars']:,}자  ({r['before']:,} → {r['after']:,})  시도 {r['rounds']}")
    for r in ng:
        print(f"  ❌ {r['slug']:34s} {r.get('why', '')}")
    if ok:
        print(f"\n신규 분량 합계 {sum(r['new_chars'] for r in ok):,}자 · 평균 {sum(r['new_chars'] for r in ok)//len(ok):,}자/건")
    print(f"완료: 성공 {len(ok)} / 실패 {len(ng)} / 총 {len(results)} · 소요 {time.time() - t0:.0f}초 "
          f"(건당 {(time.time() - t0) / max(len(results), 1):.1f}초, jobs={args.jobs})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
