#!/usr/bin/env python3
"""AIK24-PIPE-06 Phase A — 썸네일 게이트 결함 재현 테스트 (LLM·D1·EmDash 호출 0회).

배경
----
`blog_draft_generator.py` 5b 가 "생성된 글 전체의 썸네일이 실패"면 `return` 해서
**5c(EmDash 발행) 이전에** 함수가 끝났다. 초안은 메모리(_EMDASH_PENDING) 상주라
그대로 유실됐다 — 2026-10-20 09:30 실행의 minimax 초안이 정확히 그 경로였다.

검증 대상
--------
1) 썸네일 전부 실패 → 초안이 hold 로 보존되고 발행 대상에서 빠진다 (유실 없음)
2) 썸네일 통과 글은 발행 대상에 남는다
3) placeholder 사본도 '실패' 로 분류되어 hold 된다 (이미지 없는 공개 방지)
4) 5b 에서 함수를 끝내는 전면 return 이 남아있지 않다 (원본 결함 재발 방지)

사용: pytest tests/test_blog_thumbnail_gate.py -q
"""
import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

g = importlib.import_module("blog_quality_gate")
try:
    gen = importlib.import_module("blog_draft_generator")
except Exception as e:  # .env 미로드 등 import 단계 실패는 skip
    pytest.skip("blog_draft_generator import 실패: %s" % e, allow_module_level=True)


BODY = "## 도입\n\n" + ("사실만 쓴 문장이다. 근거를 붙인다. " * 120)


def _pending(fp, body=BODY):
    md = ('---\ntitle: "테스트"\ndescription: "요약"\ndate: 2026-10-20T09:30:00+09:00\n---\n\n' + body)
    gen._EMDASH_PENDING[fp] = {"md": md, "links": []}
    return fp


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    gen._EMDASH_PENDING.clear()
    yield
    gen._EMDASH_PENDING.clear()


@pytest.fixture
def no_thumbnails(monkeypatch):
    """썸네일 파일이 하나도 없도록 만든다 (판정 로직만 건드린다)."""
    monkeypatch.setattr(gen, "PROJECT_DIR", "/tmp/aik24-no-such-dir")
    monkeypatch.setattr(gen, "validate_thumbnail_quality", lambda p: (True, "ok"))
    monkeypatch.setattr(gen, "is_placeholder_copy", lambda p: False)
    return True


@pytest.fixture
def hold_spy(monkeypatch):
    calls = []
    monkeypatch.setattr(
        g, "hold",
        lambda md, title, issues, retry_md=None, retry_issues=None, reason="":
        calls.append({"title": title, "issues": list(issues), "reason": reason,
                      "md_len": len(md or "")}) or "/tmp/fake-hold.md")
    return calls


# ----------------------------------------------------------------------
class TestClassifyThumbnails:
    def test_missing_thumbnail_is_failure(self, no_thumbnails):
        fp = _pending("/tmp/t1.md")
        passed, issues, failed = gen.classify_thumbnails([(fp, "제목 1", 1, 1)])
        assert passed == 0
        assert len(issues) == 1 and len(failed) == 1
        assert failed[0][0] == fp
        assert "없음" in failed[0][4]

    def test_placeholder_copy_is_failure(self, monkeypatch):
        """placeholder 사본은 품질 OK지만 image 필드가 빠진다 → 발행하면 이미지 없는 글이 된다."""
        monkeypatch.setattr(gen, "PROJECT_DIR", "/tmp/aik24-thumb-fake")
        monkeypatch.setattr(gen, "validate_thumbnail_quality", lambda p: (True, "ok"))
        monkeypatch.setattr(gen.os.path, "exists", lambda p: str(p).endswith("thumbnail.webp"))
        monkeypatch.setattr(gen.os.path, "getsize", lambda p: 1000)
        monkeypatch.setattr(gen, "is_placeholder_copy", lambda p: True)
        fp = _pending("/tmp/t2.md")
        passed, issues, failed = gen.classify_thumbnails([(fp, "제목 2", 1, 1)])
        assert passed == 0
        assert "placeholder" in failed[0][4]

    def test_valid_thumbnail_passes(self, monkeypatch):
        import os as _os
        monkeypatch.setattr(gen, "validate_thumbnail_quality", lambda p: (True, "ok"))
        monkeypatch.setattr(gen, "is_placeholder_copy", lambda p: False)
        monkeypatch.setattr(gen.os.path, "exists", lambda p: True)
        monkeypatch.setattr(gen.os.path, "getsize", lambda p: 94066)
        fp = _pending("/tmp/t3.md")
        passed, issues, failed = gen.classify_thumbnails([(fp, "제목 3", 1, 1)])
        assert passed == 1 and not issues and not failed


# ----------------------------------------------------------------------
class TestNoDraftLoss:
    def test_all_thumbnails_fail_preserves_draft(self, no_thumbnails, hold_spy):
        """전부 실패해도 초안은 hold 로 보존된다 (유실 없음)."""
        fp = _pending("/tmp/t4.md")
        generated = [(fp, "제목 4", 1, 1)]
        passed, issues, failed = gen.classify_thumbnails(generated)
        held = gen.hold_thumbnail_failures(failed, "2026-10-20")

        assert passed == 0 and failed
        assert len(held) == 1
        # 보류 호출에 초안 본문이 들어갔는지 — 이것이 "유실 없음"의 증거
        assert len(hold_spy) == 1
        assert hold_spy[0]["md_len"] > 200, "초안 본문이 보류 기록으로 넘어가야 한다"
        assert "썸네일" in hold_spy[0]["reason"]
        assert hold_spy[0]["issues"], "보류 사유가 이슈 목록에 남아야 한다"

    def test_failed_posts_removed_from_publish_list(self, no_thumbnails, hold_spy):
        """실패 글은 발행 대상에서 빠지고, 통과 글은 남는다."""
        ok_fp = _pending("/tmp/ok.md")
        bad_fp = _pending("/tmp/bad.md")
        # 통과 글만 썸네일 OK 로 강제하기 위해 경로 존재 분기
        real_exists = os.path.exists

        def fake_exists(p):
            return "ok" in p

        monkey = pytest.MonkeyPatch()
        monkey.setattr(gen.os.path, "exists", fake_exists)
        monkey.setattr(gen, "validate_thumbnail_quality", lambda p: (True, "ok"))
        monkey.setattr(gen, "is_placeholder_copy", lambda p: False)
        monkey.setattr(gen.os.path, "getsize", lambda p: 1000)
        try:
            generated = [(ok_fp, "통과", 1, 1), (bad_fp, "실패", 2, 1)]
            passed, issues, failed = gen.classify_thumbnails(generated)
            assert passed == 1
            assert [f[0] for f in failed] == [bad_fp]
            held = gen.hold_thumbnail_failures(failed, "2026-10-20")
            bad_fps = {h[0] for h in held}
            remaining = [x for x in generated if x[0] not in bad_fps]
            assert [x[0] for x in remaining] == [ok_fp], "통과 글만 발행 대상에 남는다"
        finally:
            monkey.undo()


# ----------------------------------------------------------------------
class TestNoBlanketReturn:
    def test_source_has_no_blocking_return(self):
        """원본 결함(전면 return)이 남아있지 않아야 한다."""
        src = open(gen.__file__, encoding="utf-8").read()
        assert "모든 썸네일 품질 검증 실패 — 배포 차단" not in src, \
            "5b 의 전면 return 이 되살아나면 초안 유실이 재발한다"

    def test_main_5b_block_does_not_return_before_publish(self):
        """5b 와 5c 사이에 main() 을 끝내는 return 이 없어야 한다."""
        import inspect
        import re
        src = inspect.getsource(gen.main)
        idx_b = src.find("[5b] 발행 전 썸네일 품질 체크리스트")
        idx_c = src.find("[5c] EmDash 발행 중")
        assert idx_b != -1 and idx_c != -1 and idx_b < idx_c
        between = src[idx_b:idx_c]
        # main() 본문 레벨(4스페이스 들여쓰기)의 return 이 있으면 5c 에 도달하지 못한다
        bare_returns = [ln for ln in between.splitlines() if re.match(r"^ {4}return\b", ln)]
        assert not bare_returns, "5b 와 5c 사이에 함수 종료 return 이 있다: %r" % bare_returns
        assert "모든 썸네일" not in between
