"""브리핑 카드 제목의 수집기 내부 표식 노출 방지 계약 (AIK24-PIPE-05 §제목 표시 교정).

2026-10-18 브리핑(/briefing/2026-10-18-1/) 카드 1·2번 제목이 수집기 내부 표식
그대로 노출됐다:

    [제외] cat-jam-free — OpenCode Zen 무료 목록에서 제외

브리핑 카드 제목은 문장이어야 한다. 표식은 선정기 배제 필터
(auto_news_selector.EXCLUDED_TITLE_PREFIXES)와 수집 로그가 계속 쓰므로 DB 의
news.title 은 그대로 두고, 표시 단계에서만 문장으로 바꾼다
(src/lib/briefing-comment.ts → cleanBriefingTitle).

검증은 두 갈래다.
  1) 규칙 자체 — 실제 TS 함수를 node 로 실행해 입력/출력을 대조한다 (순수 함수).
  2) 배선 — 제목을 표시하는 6개 화면이 그 함수를 실제로 통과시키는지 파일 계약으로 확인한다.
     (한 곳만 빠져도 그 화면에만 표식이 남는다. PIPE-04 §작업2 와 같은 이유로 전 화면 동시 적용.)
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO / "src" / "lib" / "briefing-comment.ts"

# (입력 news.title, 독자 화면에 보여야 하는 문장)
CASES = [
    (
        "[제외] cat-jam-free — OpenCode Zen 무료 목록에서 제외",
        "OpenCode Zen 무료 목록에서 cat-jam-free 모델이 제외되었습니다",
    ),
    (
        "[제외] muse-spark-1.3-contributor-free — OpenCode Zen 무료 목록에서 제외",
        "OpenCode Zen 무료 목록에서 muse-spark-1.3-contributor-free 모델이 제외되었습니다",
    ),
    (
        "[제외] stepfun/step-5-preview-free — Kilo Free Models 무료 목록에서 제외",
        "Kilo Free Models 무료 목록에서 stepfun/step-5-preview-free 모델이 제외되었습니다",
    ),
    (
        "[신규 무료] reflection/beam-free — Kilo Free Models 무료 목록에 추가",
        "Kilo Free Models 무료 목록에 reflection/beam-free 모델이 추가되었습니다",
    ),
    (
        "[무료 LLM] beam-free — OpenCode Zen 무료 티어",
        "OpenCode Zen 무료 티어에 beam-free 모델이 포함되어 있습니다",
    ),
    (
        "[무료 LLM] xingchen-agi/xing4.0-29b-a4b:free — OpenRouter 무료 티어",
        "OpenRouter 무료 티어에 xingchen-agi/xing4.0-29b-a4b:free 모델이 포함되어 있습니다",
    ),
    # 언론사가 붙인 대괄호 접두어는 제목의 일부다 — 손대면 안 된다.
    ("[게시판] KT, AI 인재 양성 나선다", "[게시판] KT, AI 인재 양성 나선다"),
    ("[속보] 오픈AI 신모델 공개", "[속보] 오픈AI 신모델 공개"),
    # 표식 없는 일반 제목도 그대로다.
    ("Azure 무료 계정 $200 크레딧 (30일)", "Azure 무료 계정 $200 크레딧 (30일)"),
    # 위 3종 문장형으로 잡히지 않는 내부 표식은 떼어낸다.
    ("[제외] 알 수 없는 형식의 행", "알 수 없는 형식의 행"),
    # 빈 값 방어
    ("", ""),
]


needs_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="node 없음 — Astro 빌드 환경에서만 실행되는 계약"
)


@needs_node
def test_clean_briefing_title_rule():
    """규칙 자체 — 실제 TS 함수를 node 로 실행해 대조한다."""
    script = (
        f"import {{ cleanBriefingTitle }} from {json.dumps(MODULE.as_uri())};\n"
        f"const cases = {json.dumps([c[0] for c in CASES], ensure_ascii=False)};\n"
        "console.log(JSON.stringify(cases.map((c) => cleanBriefingTitle(c))));\n"
    )
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        timeout=120,
    )
    assert proc.returncode == 0, f"node 실행 실패: {proc.stderr.strip()[:500]}"

    got = json.loads(proc.stdout.strip().splitlines()[-1])
    expected = [c[1] for c in CASES]
    assert got == expected, "\n".join(
        f"  in={CASES[i][0]!r}\n  want={expected[i]!r}\n  got ={got[i]!r}"
        for i in range(len(CASES))
        if got[i] != expected[i]
    )


@needs_node
def test_internal_tag_never_survives_marker_formats():
    """표식 3종은 어떤 경우에도 결과 문자열 앞에 남지 않는다."""
    titles = [c[0] for c in CASES if c[0]]
    script = (
        f"import {{ cleanBriefingTitle }} from {json.dumps(MODULE.as_uri())};\n"
        f"const cases = {json.dumps(titles, ensure_ascii=False)};\n"
        "console.log(JSON.stringify(cases.map((c) => cleanBriefingTitle(c))));\n"
    )
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        timeout=120,
    )
    assert proc.returncode == 0, f"node 실행 실패: {proc.stderr.strip()[:500]}"
    for original, out in zip(titles, json.loads(proc.stdout.strip().splitlines()[-1])):
        if original.startswith(("[제외]", "[신규 무료]", "[무료 LLM]")):
            assert not out.startswith("["), f"내부 표식이 남았다: {out!r}"


# 제목을 표시하는 화면과, 그 화면이 함수를 통과시켜야 하는 지점.
WIRING = [
    ("src/lib/briefing-comment.ts", "export function cleanBriefingTitle"),
    ("src/pages/briefing/[date].astro", "cleanBriefingTitle(it.title)"),  # 카드 제목
    ("src/pages/briefing/[date].astro", "cleanBriefingTitle(n.title)"),  # 오늘의 다른 AI 뉴스
    ("src/components/home/BriefingSection.astro", "cleanBriefingTitle(it.title)"),  # 홈 카드
    ("src/pages/news.astro", "cleanBriefingTitle(it.title)"),  # /news/ 브리핑 카드
    ("src/pages/news.astro", "cleanBriefingTitle(n.title)"),  # /news/ 전체 소식
    ("src/pages/briefing/index.astro", "cleanBriefingTitle(n.title)"),  # 뉴스 목록
    ("src/pages/api/briefing/send-email.ts", "cleanBriefingTitle(it.news_title)"),  # 이메일
    ("src/pages/api/briefing/latest.ts", "cleanBriefingTitle(it.title)"),  # 브리핑 API 응답
]


@pytest.mark.parametrize("path,needle", WIRING)
def test_title_cleaning_is_wired_into_display_paths(path, needle):
    """배선 — 표시 화면이 정리 함수를 실제로 호출하는지 확인한다."""
    text = (REPO / path).read_text(encoding="utf-8")
    assert needle in text, f"{path} 에 {needle!r} 가 없다 — 이 화면에만 표식이 남는다"
