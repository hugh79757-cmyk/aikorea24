"""도구 디렉토리(/tools/) 두 섹션 폐지 + 카드 NEW 배지 계약 (AIK24-TOOLSYNC-06).

2026-10-18 대표님 결정:
  · '최신 등록' 섹션 삭제 — md `updated` 상위 6칸 회전 창이라, 수집기가 매일
    06:00 에 2~11개를 자동 등록하면 이틀이면 밀려난다. 게다가 D1 전용(제출 승인)
    툴은 updated=created_at 이라 승인해도 상단에 올라오지 못한다
    (실측: spriteframe created_at 2026-10-14 / aitraining-jobs 2026-10-13 →
    상위 6칸은 10-18·10-18·10-17·10-17·10-17·10-16 이라 7~8번째로 밀림).
  · '인기 도구' 섹션 삭제 — 인기도 데이터가 아니라 koreanSupport + order 정렬이라
    실측 노출이 order=-1 동률 6건 + ChatGPT·Claude 였다.
  · 두 섹션 모두 아래 전체 도구 그리드(필터·검색·정렬 보유)의 부분집합이라 중복.
  · '⭐ 리뷰 순' 정렬 삭제 — 모든 카드 data-review=0 고정이라 눌러도 아무 일도 없었다.
  · 신규 노출은 그리드 카드의 '최근 7일 NEW' 배지가 맡는다.

검증 두 갈래:
  1) 배지 규칙 — astro 안의 실제 헬퍼를 node 로 실행해 날짜 경계를 대조한다.
  2) 배선/잔재 — 섹션·죽은 정렬이 실제로 사라졌고, 그리드 조작부는 남았는지 파일 계약.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PAGE = REPO / "src" / "pages" / "tools" / "index.astro"

# 고정 시각: 2026-10-18 15:00 KST (= 06:00 UTC). 컷오프는 7일 전 = 2026-10-11.
FIXED_NOW_MS = 1792303200000  # 2026-10-18T06:00:00Z

# (updated 값, 기대 NEW 여부)
CASES = [
    ("2026-10-18", True),          # 오늘 등록(수집기 당일분)
    ("2026-10-18 06:16:33", True),  # D1 created_at 형태(시각 포함)
    ("2026-10-14", True),          # spriteframe — 승인했는데 상단에 안 뜨던 건
    ("2026-10-13", True),          # aitraining-jobs — 위와 같은 건
    ("2026-10-11", True),          # 컷오프 경계(포함)
    ("2026-10-10", False),         # 컷오프 하루 전
    ("2026-06-28", False),         # 기존 툴
    ("", False),                   # 값 없음
    (None, False),                 # 값 없음(null)
    ("2026-10-25", False),         # 미래 날짜 방어
]

needs_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="node 없음 — Astro 빌드 환경에서만 실행되는 계약"
)


def _extract_badge_rule() -> str:
    """astro 프런트매터에서 NEW 배지 헬퍼 정의를 그대로 떼어낸다."""
    text = PAGE.read_text(encoding="utf-8")
    m = re.search(r"(const KST_OFFSET_MS[\s\S]*?\n\};\n)", text)
    assert m, "index.astro 에서 NEW 배지 헬퍼(isNewTool) 정의를 찾지 못했다"
    rule = m.group(1)
    # node 는 TS 타입 표기를 못 읽는다 — 헬퍼 시그니처만 벗긴다.
    js = rule.replace("(t: any): boolean =>", "(t) =>")
    assert js != rule, "헬퍼 시그니처 형태가 바뀌었다 — 테스트의 타입 제거 규칙을 갱신하라"
    return js


@needs_node
def test_new_badge_rule_dates():
    """규칙 자체 — 7일 창(포함 경계)과 방어 케이스."""
    script = (
        f"Date.now = () => {FIXED_NOW_MS};\n"
        f"{_extract_badge_rule()}\n"
        f"const cases = {json.dumps([c[0] for c in CASES], ensure_ascii=False)};\n"
        "console.log(JSON.stringify(cases.map((u) => isNewTool({ data: { updated: u } }))));\n"
    )
    proc = subprocess.run(
        ["node", "-e", script],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        timeout=120,
    )
    assert proc.returncode == 0, f"node 실행 실패: {proc.stderr.strip()[:500]}"

    got = json.loads(proc.stdout.strip().splitlines()[-1])
    expected = [c[1] for c in CASES]
    assert got == expected, "\n".join(
        f"  updated={CASES[i][0]!r}\n  want={expected[i]}\n  got ={got[i]}"
        for i in range(len(CASES))
        if got[i] != expected[i]
    )


def test_both_sections_are_gone():
    """'최신 등록'·'인기 도구' 섹션이 실제로 사라졌다 (주석 언급은 허용)."""
    text = PAGE.read_text(encoding="utf-8")
    for heading in ("최신 등록", "인기 도구"):
        assert f">{heading}</h2>" not in text, f"'{heading}' 섹션이 아직 렌더된다"
    for ident in ("newTools", "popularTools"):
        assert ident not in text, f"삭제된 섹션의 계산({ident})이 남아 있다"


def test_new_badge_is_wired_into_grid_card():
    """배지가 그리드 카드 헤더에 실제로 박혀 있다 (계산만 하고 안 그리면 의미 없음)."""
    text = PAGE.read_text(encoding="utf-8")
    assert "{isNewTool(tool) && (" in text, "카드에서 isNewTool 을 호출하지 않는다"
    badge = re.search(r"\{isNewTool\(tool\) && \(\s*<span[^>]*>NEW</span>\s*\)\}", text)
    assert badge, "카드 NEW 배지 마크업을 찾지 못했다"
    # 배지는 이름·MAKER·KR 배지와 같은 헤더 묶음 안에 있어야 한다.
    header = text[badge.start(): badge.start() + 900]
    assert "koreanSupport" in header or "KR" in header, "배지가 카드 헤더 묶음 밖에 있다"


def test_grid_controls_survive():
    """전체 도구 그리드와 조작부(필터·검색·정렬)는 그대로 남아 있다."""
    text = PAGE.read_text(encoding="utf-8")
    for needle in (
        'id="tools-grid"',
        'id="tool-search"',
        'id="filter-free"',
        'id="filter-korean"',
        'id="sort-order"',
        'value="order"',      # 추천순
        'value="name"',       # 이름순
        'value="updated"',    # 최신순
        "{allTools.map((tool, i) => {",
    ):
        assert needle in text, f"그리드 요소가 사라졌다: {needle}"


def test_review_sort_removed():
    """죽은 '⭐ 리뷰 순' 정렬은 옵션·분기·속성 모두 제거됐다."""
    text = PAGE.read_text(encoding="utf-8")
    assert "리뷰 순" not in text, "정렬 셀렉트에 '⭐ 리뷰 순' 이 남아 있다"
    assert "data-review" not in text, "data-review 속성이 남아 있다"
    assert "sort === 'review'" not in text, "review 정렬 분기가 남아 있다"
