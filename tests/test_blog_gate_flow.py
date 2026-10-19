"""AIK24-BLOG-02 — 발행 게이트 배선 통합 테스트 (LLM 호출 없음, D1/EmDash 부작용 없음).

`generate_draft`·`save_draft`·`publish_post`·`hold`·`verify_published` 를 스텁으로 바꾸고
**실제 제어흐름 코드**(`_gate_and_fix`, `_publish_generated_to_emdash`)를 그대로 실행한다.

검증:
- 1차 게이트: 통과 시 교정 0회 / 미달 시 표 수리 + 교정(초안수정) → 통과 / 교정 2회 미달 → 보류
- 미달 초안이 발행 대기(`_EMDASH_PENDING`)에 남지 않는다 (검사를 우회한 발행 방지)
- 2차 게이트: 표 구분선이 없으면 **수리본**이 발행 본문이 된다 / 미달이면 발행하지 않는다

실행(기본 pytest 는 integration 을 제외한다):
    set -a && . ./.env && set +a
    .venv/bin/python3 -m pytest tests/test_blog_gate_flow.py -q -m integration
"""
import importlib
import re

import pytest

pytestmark = pytest.mark.integration

g = importlib.import_module("blog_quality_gate")
try:
    gen = importlib.import_module("blog_draft_generator")
except Exception as e:  # .env 미로드 등 import 단계 실패는 skip (테스트 실패 아님)
    pytest.skip("blog_draft_generator import 실패: %s" % e, allow_module_level=True)

TODAY = "2026-10-19"
FILLER = "기사에 있는 사실을 풀어 쓴 문장이다. 추측을 넣지 않고 근거만 쓴다. " * 90

GOOD = ("TITLE: 테스트 제목\n---\n## 도입\n\n" + FILLER + "\n\n## 핵심 내용\n\n"
        "| 항목 | 값 |\n| --- | --- |\n| 무료 크레딧 | 200달러 |\n| 기간 | 30일 |\n\n"
        "## 마무리 — 지금 할 일\n\n1. 첫 단계\n2. 둘째 단계\n3. 셋째 단계\n\n"
        "참고: [원문](https://example.com/a) / [문서](https://example.org/b) / [가이드](https://example.net/c)\n")

BAD = ("TITLE: 테스트 제목\n---\n## 도입\n\n짧은 본문.\n\n"
       "| 항목 | 값 |\n| 무료 크레딧 | 200달러 |\n\n## 마무리 — 지금 할 일\n\n1. 하나\n")


def _md(body: str) -> str:
    return ('---\ntitle: 테스트 제목\ndescription: 요약\ndate: 2026-10-19T09:30:00+09:00\n---\n\n'
            + body)


class StubGen:
    """`generate_draft` 대체 — 큐에 넣은 응답을 차례로 돌려준다."""

    def __init__(self, queue=None):
        self.queue = list(queue or [])
        self.calls = []

    def __call__(self, keyword, articles, grade, fix_note=None, link_hint=True,
                 corrective=False, model_order=None):
        self.calls.append({"corrective": corrective, "model_order": model_order,
                           "fix_note": fix_note})
        return self.queue.pop(0) if self.queue else ""


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """네트워크·디스크·전역 상태 격리."""
    monkeypatch.setattr(g, "dead_links", lambda links, **kw: [])
    gen._EMDASH_PENDING.clear()
    yield
    gen._EMDASH_PENDING.clear()


@pytest.fixture
def stub_save(monkeypatch):
    """`save_draft` 대체 — 파싱 + frontmatter 결합 + pending 등록. 너무 짧으면 저장 거부."""
    def _save(gpt_output, keyword, file_num, today_str, articles=None):
        title, body = gen._parse_title_body(gpt_output or "")
        if not body or len(body) < 200:
            return "", ""
        fp = "/tmp/stub-%d.md" % file_num
        gen._EMDASH_PENDING[fp] = {"md": _md(body), "links": []}
        return fp, title
    monkeypatch.setattr(gen, "save_draft", _save)
    return _save


@pytest.fixture
def stub_gen(monkeypatch):
    def _install(queue):
        sg = StubGen(queue)
        monkeypatch.setattr(gen, "generate_draft", sg)
        return sg
    return _install


def _body_of(fp):
    return g.body_of((gen._EMDASH_PENDING.get(fp) or {}).get("md", ""))


def _seed(body, n=700):
    fp = "/tmp/seed-%d.md" % n
    gen._EMDASH_PENDING[fp] = {"md": _md(body)}
    return fp


class TestGateAndFix:
    def test_pass_without_correction(self, stub_gen, stub_save):
        sg = stub_gen([])
        fp1 = _seed(g.body_of(GOOD))
        fp, title, consumed, issues, best = gen._gate_and_fix("테스트 제목", {"title": "테스트 제목"}, fp1, "테스트 제목", 700, TODAY)
        assert fp == fp1 and issues is None and best is None
        assert consumed == 1
        assert sg.calls == [], "1차가 통과하면 교정을 호출하지 않는다"

    def test_missing_separator_is_repaired_then_corrected(self, stub_gen, stub_save):
        sg = stub_gen([GOOD])
        fp1 = _seed(g.body_of(BAD))
        fp, title, consumed, issues, best = gen._gate_and_fix("테스트 제목", {"title": "테스트 제목"}, fp1, "테스트 제목", 700, TODAY)
        assert fp and issues is None
        assert consumed == 2, "교정 1회 → 파일번호 2개 소비"
        assert [c["corrective"] for c in sg.calls] == [True], "교정은 초안수정 모드여야 한다"
        assert sg.calls[0]["fix_note"], "교정 지시문(초안 내용 포함)을 넘겨야 한다"
        assert len(re.findall(r"^\|\s*-{2,}", _body_of(fp), re.M)) >= 1
        assert len(_body_of(fp)) >= g.MIN_CHARS

    def test_hold_after_two_failed_corrections(self, stub_gen, stub_save):
        sg = stub_gen([BAD, BAD])
        fp1 = _seed(g.body_of(BAD))
        fp, title, consumed, issues, best = gen._gate_and_fix("테스트 제목", {"title": "테스트 제목"}, fp1, "테스트 제목", 700, TODAY)
        assert fp is None and issues and best
        assert len(sg.calls) == 2
        assert consumed == 3
        # 미달본이 발행 대기에 남으면 검사를 우회해 발행된다 — 반환된 1건만 남아야 한다
        assert set(gen._EMDASH_PENDING) == {best}
        gen._EMDASH_PENDING.pop(best, None)

    def test_empty_correction_response_holds(self, stub_gen, stub_save):
        stub_gen(["", ""])
        fp1 = _seed(g.body_of(BAD))
        fp, title, consumed, issues, best = gen._gate_and_fix("테스트 제목", {"title": "테스트 제목"}, fp1, "테스트 제목", 700, TODAY)
        assert fp is None and issues
        assert consumed == 1, "저장이 안 된 교정은 파일번호를 소비하지 않는다"


class TestPublishGate:
    @pytest.fixture
    def publish_spy(self, monkeypatch):
        calls = {"publish": [], "hold": [], "verify": []}
        monkeypatch.setattr("emdash_publish.publish_post",
                            lambda title, body, excerpt=None, featured_image=None, published_at=None:
                            calls["publish"].append((title, body)) or "https://emdash.aikorea24.kr/posts/fake")
        monkeypatch.setattr(g, "hold",
                            lambda md, title, issues, retry_md=None, retry_issues=None, reason="":
                            calls["hold"].append((title, reason, list(issues))) or "/tmp/fake-hold.md")
        monkeypatch.setattr(g, "verify_published",
                            lambda url, expected_body=None, title=None:
                            calls["verify"].append((url, expected_body)) or True)
        return calls

    def test_publishes_repaired_body(self, publish_spy):
        gen._EMDASH_PENDING["/tmp/p1.md"] = {
            "md": _md(g.body_of(GOOD).replace("| --- | --- |\n", "")), "links": [(1, False)]}
        gen._publish_generated_to_emdash([("/tmp/p1.md", "테스트 제목", 1, 1)])
        assert len(publish_spy["publish"]) == 1
        published = publish_spy["publish"][0][1]
        assert len(re.findall(r"^\|\s*-{2,}", published, re.M)) >= 1, "수리본이 발행 본문이어야 한다"
        assert publish_spy["verify"] and publish_spy["verify"][0][1] == published, "3차 검증은 발행 본문과 대조"
        assert not publish_spy["hold"]

    def test_holds_when_still_below_bar(self, publish_spy):
        gen._EMDASH_PENDING["/tmp/p2.md"] = {"md": _md("## 도입\n\n짧은 본문.\n"), "links": [(2, False)]}
        gen._publish_generated_to_emdash([("/tmp/p2.md", "테스트 제목 2", 2, 1)])
        assert not publish_spy["publish"], "미달 초안은 발행하면 안 된다"
        assert len(publish_spy["hold"]) == 1
        assert "2차 게이트" in publish_spy["hold"][0][1]
        assert publish_spy["hold"][0][2], "결함 목록을 보류 기록에 남긴다"

    def test_skips_unknown_draft(self, publish_spy):
        gen._publish_generated_to_emdash([("/tmp/none.md", "없는 초안", 3, 1)])
        assert not publish_spy["publish"] and not publish_spy["hold"]
