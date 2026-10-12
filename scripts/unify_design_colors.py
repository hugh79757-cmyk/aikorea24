#!/usr/bin/env python3
"""AIK24-RENEWAL-02 (B-2) 초록/핑크/파랑/보라/노랑 → 흑백+빨강(#E63B2E) 마이그레이션.

정답 기준: /news/ 페이지 (흰 배경 + text-[#111111] + border-left 4px #E63B2E + bg-[#111111] 버튼)

적용 방식: Tailwind 클래스 토큰을 정규식으로 매핑. 클래스명 토큰은 문자열 전체에서
유일하게 식별되므로 class=""/템플릿리터럴/cn() 구분 없이 텍스트 치환으로 안전하다.

제외: src/auto_poster/** (SNS OG 카드 이미지 생성기 — 사이트 화면 아님, 이 지시서 범위 밖)

사용법:
    python3 scripts/unify_design_colors.py          # dry-run (변경만 보고)
    python3 scripts/unify_design_colors.py --apply  # 실제 적용
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COL = r"(?:blue|indigo|sky|cyan|teal|emerald|green|lime|purple|violet|fuchsia|pink|rose|amber|yellow|orange)"
V = r"(?:[a-z-]+:)?"  # hover:/focus:/dark: 등 변형 접두사
TOK = rf"\b{V}(?:bg|text|border|from|via|to|ring|ring-offset|fill|stroke|shadow|outline|decoration|placeholder|caret|accent)-{COL}-[0-9]{{2,3}}\b"

# 1) 그라디언트 런 통째로 단색 검정으로. hover: 접두사가 섞여도 처리.
GRAD_RUN = re.compile(
    rf"{V}bg-gradient-to-(?:r|l|t|b|tr|tl|br|bl)"
    rf"(?:\s+{V}(?:from|via|to)-{COL}-[0-9]{{2,3}})*"
)

# 2) 잔여 from-/via-/to- 단일 토큰 → 제거
STOP = re.compile(rf"\s*{V}(?:from|via|to)-{COL}-[0-9]{{2,3}}")

# 3) 남는 컬러 토큰 매핑 (변형 접두사 유지)
RULES = [
    (re.compile(rf"\b{V}bg-{COL}-(600|700|800|900)\b"),
     lambda m: _sub_variant(m, "bg-[#111111]")),
    (re.compile(rf"\b{V}bg-{COL}-(400|500)\b"),
     lambda m: _sub_variant(m, "bg-[#333333]")),
    (re.compile(rf"\b{V}bg-{COL}-300\b"),
     lambda m: _sub_variant(m, "bg-[#e5e5e5]")),
    (re.compile(rf"\b{V}bg-{COL}-(50|100|200)\b"),
     lambda m: _sub_variant(m, "bg-gray-100")),
    (re.compile(rf"\b{V}text-{COL}-(600|700|800|900)\b"),
     lambda m: _sub_variant(m, "text-[#111111]")),
    (re.compile(rf"\b{V}text-{COL}-(400|500)\b"),
     lambda m: _sub_variant(m, "text-[#555555]")),
    (re.compile(rf"\b{V}text-{COL}-(200|300)\b"),
     lambda m: _sub_variant(m, "text-gray-500")),
    (re.compile(rf"\b{V}border-{COL}-(50|100|200)\b"),
     lambda m: _sub_variant(m, "border-[#e5e5e5]")),
    (re.compile(rf"\b{V}border-{COL}-(300|400|500|600|700)\b"),
     lambda m: _sub_variant(m, "border-[#e5e5e5]")),
    (re.compile(rf"\b{V}focus:border-{COL}-[0-9]{{2,3}}\b"),
     lambda m: _sub_variant(m, "focus:border-[#111111]")),
    (re.compile(rf"\b{V}(?:ring|ring-offset)-{COL}-[0-9]{{2,3}}\b"),
     lambda m: _sub_variant(m, "ring-[#111111]")),
    (re.compile(rf"\b{V}placeholder-{COL}-[0-9]{{2,3}}\b"),
     lambda m: _sub_variant(m, "placeholder-gray-500")),
    (re.compile(rf"\b{V}caret-{COL}-[0-9]{{2,3}}\b"),
     lambda m: _sub_variant(m, "caret-[#111111]")),
    (re.compile(rf"\b{V}decoration-{COL}-[0-9]{{2,3}}\b"),
     lambda m: _sub_variant(m, "decoration-[#111111]")),
    (re.compile(rf"\b{V}fill-{COL}-[0-9]{{2,3}}\b"),
     lambda m: _sub_variant(m, "fill-[#111111]")),
    (re.compile(rf"\b{V}stroke-{COL}-[0-9]{{2,3}}\b"),
     lambda m: _sub_variant(m, "stroke-[#111111]")),
    (re.compile(rf"\b{V}shadow-{COL}-[0-9]{{2,3}}\b"),
     lambda m: _sub_variant(m, "shadow-[#e5e5e5]")),
    (re.compile(rf"\b{V}accent-{COL}-[0-9]{{2,3}}\b"),
     lambda m: _sub_variant(m, "accent-[#111111]")),
    (re.compile(rf"\b{V}outline-{COL}-[0-9]{{2,3}}\b"),
     lambda m: _sub_variant(m, "outline-[#e5e5e5]")),
]

VAR_RE = re.compile(r"^(?:[a-z-]+:)?(?:.*$)")


def _catchall(m):
    """남는 임의 셰이드/불투명도(/NN) 변형을 마지막에 흑백으로 정리한다."""
    shade = int(re.search(r"-(\d{2,3})(?:/\d+)?$", m.group(0)).group(1))
    prop = m.group(1)
    if prop == "bg":
        return _sub_variant(m, "bg-[#111111]" if shade >= 400 else "bg-gray-100")
    if prop == "text":
        return _sub_variant(m, "text-[#111111]" if shade >= 500 else "text-[#555555]")
    if prop in ("border", "ring", "ring-offset", "outline"):
        return _sub_variant(m, "border-[#e5e5e5]")
    return _sub_variant(m, "text-[#111111]")


CATCHALL = re.compile(
    rf"\b{V}(bg|text|border|from|via|to|ring|ring-offset|fill|stroke|shadow|outline|decoration|placeholder|caret|accent)-{COL}-[0-9]{{2,3}}(?:/\d+)?\b"
)


def _sub_variant(m, repl):
    """매치 문자열에서 hover:/dark: 등 변형 접두사를 떼어 repl 앞에 다시 붙인다."""
    s = m.group(0)
    # 토큰 시작 부분의 변형 접두사(hover:, dark:, focus: 등) 추출
    prefix = ""
    i = 0
    while i < len(s) and s[i].islower():
        j = s.find(":", i)
        if j == -1:
            break
        seg = s[i:j]
        if seg in ("bg", "text", "border", "from", "via", "to", "ring",
                   "ring-offset", "fill", "stroke", "shadow", "outline",
                   "decoration", "placeholder", "caret", "accent"):
            break
        prefix += s[i:j + 1]
        i = j + 1
    body = s[i:]
    return prefix + repl if prefix else repl


def migrate(text: str, stats: dict) -> str:
    # 1) 그라디언트 런 → 단색 검정
    def grad_sub(m):
        s = m.group(0)
        pfx = ""
        # 런 전체를 덮는 공통 변형 접두사(hover:)가 있으면 유지
        first = s.split()[0]
        if first.startswith("hover:"):
            pfx = "hover:"
        stats["gradient"] += 1
        return (pfx + "bg-[#111111]") if pfx else "bg-[#111111]"

    text = GRAD_RUN.sub(grad_sub, text)
    # 2) 남은 from-/via-/to- 제거
    text, n = STOP.subn("", text)
    stats["gradient_stop_removed"] += n
    # 3) 개별 토큰 매핑
    for rx, fn in RULES:
        text, n = rx.subn(fn, text)
        stats["token"] += n
    # 4) 끝판 규칙: 남는 셰이드/불투명도 변형
    text, n = CATCHALL.subn(_catchall, text)
    stats["token"] += n
    # 5) 그라디언트 치환으로 생긴 깨진 이중 불투명도 방어
    text = re.sub(r"bg-\[#111111\]/(\d+)/\1\b", r"bg-[#111111]/\1", text)
    text = re.sub(r"bg-\[#333333\]/(\d+)/\1\b", r"bg-[#333333]/\1", text)
    return text


def discover():
    out = []
    for p in (ROOT / "src").rglob("*"):
        if not p.is_file() or p.suffix not in (".astro", ".ts", ".tsx", ".css", ".js"):
            continue
        if "auto_poster" in p.parts:
            continue
        out.append(p)
    return sorted(out)


def main():
    apply_mode = "--apply" in sys.argv
    files = discover()
    changed = []
    total_grad = total_tok = 0
    for p in files:
        orig = p.read_text(encoding="utf-8")
        stats = {"gradient": 0, "gradient_stop_removed": 0, "token": 0}
        new = migrate(orig, stats)
        if new != orig:
            changed.append((p.relative_to(ROOT), stats, len(orig) != len(new)))
            total_grad += stats["gradient"]
            total_tok += stats["token"] + stats["gradient_stop_removed"]
            if apply_mode:
                p.write_text(new, encoding="utf-8")

    for rel, st, _ in changed:
        print(f"  {rel}  (그라디언트 {st['gradient']} / 토큰 {st['token'] + st['gradient_stop_removed']})")
    print(f"\n  변경 파일 {len(changed)}개 | 그라디언트 {total_grad}건 | 토큰 치환 {total_tok}건")
    print("  모드:", "적용 완료" if apply_mode else "DRY-RUN (미적용)")


if __name__ == "__main__":
    main()
