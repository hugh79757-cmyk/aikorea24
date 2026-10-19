"""AIK24-BLOG-02 — 발행 게이트 단위 테스트 (외부 서비스 불필요).

검증 대상:
- `blog_quality_gate.repair_markdown()` / `repair_pending()` — 결정적 수리 (표 구분선·앞머리 H1)
- `blog_quality_gate.screen_extended()` — 네트워크 검사는 스텁으로 분리
- `emdash_precheck.check()` — PT JSON 차단, frontmatter 가 본문 길이에 섞이지 않게
- `blog_quality_gate.hold()` — 보류 기록 파일/메타
- `republish_held` — 정규화 제목 중복 판정

실행: `.venv/bin/python3 -m pytest tests/test_blog_quality_gate.py -q`
"""
import datetime
import json
import re

import pytest

import blog_quality_gate as g
import republish_held as rh
from emdash_precheck import check, looks_like_pt_json, strip_frontmatter

pytestmark = pytest.mark.unit

NO_SEP_TABLE = "## 핵심 내용\n\n| 항목 | 값 |\n| 무료 크레딧 | 200달러 |\n| 기간 | 30일 |\n"
VALID_TABLE = "## 핵심 내용\n\n| 항목 | 값 |\n| --- | --- |\n| 무료 크레딧 | 200달러 |\n"
FENCED = "## 예시\n\n```\n| a | b |\n| c | d |\n```\n"


class TestRepairMarkdown:
    def test_inserts_separator_row(self):
        fixed, fixes = g.repair_markdown(NO_SEP_TABLE)
        assert fixes, "구분선 없는 표를 수리했다고 보고해야 한다"
        assert len(re.findall(r"^\|\s*-{2,}", fixed, re.M)) >= 1
        assert "무료 크레딧 | 200달러" in fixed, "표 내용은 보존되어야 한다"

    def test_idempotent(self):
        once, f1 = g.repair_markdown(NO_SEP_TABLE)
        twice, f2 = g.repair_markdown(once)
        assert f1 and not f2
        assert once == twice

    def test_valid_table_untouched(self):
        fixed, fixes = g.repair_markdown(VALID_TABLE)
        assert not fixes
        assert fixed == VALID_TABLE

    def test_fenced_code_untouched(self):
        fixed, fixes = g.repair_markdown(FENCED)
        assert not fixes, "코드펜스 안의 파이프는 표가 아니다"
        assert fixed == FENCED

    def test_strips_leading_h1(self):
        fixed, fixes = g.repair_markdown("# 제목\n\n## 도입\n\n본문\n")
        assert "앞머리 H1 제거" in fixes
        assert not re.search(r"^#\s", fixed, re.M)
        assert "## 도입" in fixed, "본문 중간 소제목은 남아야 한다"

    def test_repair_pending_handles_frontmatter(self):
        md = "---\ntitle: \"t\"\ndate: 2026-10-19T09:30:00+09:00\n---\n\n" + NO_SEP_TABLE
        fixed, fixes = g.repair_pending(md)
        assert fixes
        assert fixed.startswith("---"), "frontmatter 는 보존되어야 한다"


class TestScreen:
    def test_short_body_without_links_is_flagged(self, monkeypatch):
        monkeypatch.setattr(g, "dead_links", lambda links, **kw: [])
        issues = g.screen_extended("## 도입\n\n짧은 본문이다.\n")
        assert any("본문" in i for i in issues)
        assert any("링크" in i for i in issues)

    def test_complete_body_passes(self, monkeypatch):
        monkeypatch.setattr(g, "dead_links", lambda links, **kw: [])
        body = (
            "## 도입\n\n" + ("사실을 풀어 쓴 문장이다. " * 400) + "\n\n"
            + VALID_TABLE + "\n## 마무리 — 지금 할 일\n\n1. 하나\n2. 둘\n3. 셋\n\n"
            "참고: [원문](https://example.com/a) [문서](https://example.org/b) [가이드](https://example.net/c)\n"
        )
        assert g.screen_extended(body) == []

    def test_dead_link_is_flagged(self, monkeypatch):
        monkeypatch.setattr(g, "dead_links", lambda links, **kw: ["https://dead.example/x"])
        body = (
            "## 도입\n\n" + ("사실을 풀어 쓴 문장이다. " * 400) + "\n\n"
            + VALID_TABLE + "\n## 마무리 — 지금 할 일\n\n1. 하나\n\n"
            "참고: [원문](https://example.com/a) [문서](https://example.org/b) [죽음](https://dead.example/x)\n"
        )
        assert any("끊긴 링크" in i for i in g.screen_extended(body))


class TestPrecheck:
    def test_pt_json_is_blocked(self):
        payload = json.dumps([{"_type": "block", "_key": "a1", "children": [{"_type": "span", "text": "가" * 5000}]}])
        assert looks_like_pt_json(payload)
        issues = check(payload)
        assert issues and "PT JSON" in issues[0], "PT JSON 은 문자수로 통과시키면 안 된다"

    def test_frontmatter_not_counted_in_body_length(self):
        md = ("---\ntitle: \"t\"\ndescription: \"" + ("설명" * 700) + "\"\n"
              "date: 2026-10-19T09:30:00+09:00\n---\n\n## 도입\n\n짧은 본문.\n")
        assert "description" not in strip_frontmatter(md)
        issues = check(strip_frontmatter(md))
        assert any("본문" in i for i in issues), "frontmatter 를 뺀 본문 길이로 판정해야 한다"


class TestHold:
    def test_writes_draft_and_meta(self, tmp_path, monkeypatch):
        monkeypatch.setattr(g, "REJECTED_DIR", str(tmp_path))
        monkeypatch.setattr(g, "HOLD_COUNT", 0)
        path = g.hold("## 도입\n\n초안 본문\n", "테스트 제목", ["표 0개 (최소 1)"],
                      reason="1차 게이트 미달(교정 2회 후에도 미달)")
        assert path and str(tmp_path) in path
        jp = path[:-3] + ".json"
        meta = json.loads(open(jp, encoding="utf-8").read())
        assert meta["title"] == "테스트 제목"
        assert meta["reason"].startswith("1차 게이트")
        assert meta["issues"] == ["표 0개 (최소 1)"]
        assert "초안 본문" in open(path, encoding="utf-8").read()

    def test_summary_line_counts_holds(self, tmp_path, monkeypatch):
        monkeypatch.setattr(g, "REJECTED_DIR", str(tmp_path))
        monkeypatch.setattr(g, "HOLD_COUNT", 0)
        monkeypatch.setattr(g, "HOLDED_TITLES", [])
        assert g.summary_line() == ""
        g.hold("x", "제목", ["표 0개 (최소 1)"])
        assert "게이트 보류 1건" in g.summary_line()


class TestRecoverDateFilter:
    """보류 파일명 스탬프(머신 로컬) → KST 정규화 판정.

    배경(2026-10-19 실측): `hold()` 는 머신 로컬 시각으로 파일명을 찍고 파이프라인의
    `today_str` 은 KST 기준이다. 이 머신은 +07 이라 두 값이 2시간 창에서 어긋난다.
    정규화하지 않으면 오프스케줄 실행에서 보류 글이 조용히 복구되지 않는다.
    """

    @staticmethod
    def _record(root, instant_utc, title):
        stamp = instant_utc.astimezone().strftime("%Y%m%d-%H%M%S")   # 머신 로컬 스탬프
        body = ("## 도입\n\n" + ("기사 사실을 풀어 쓴 문장이다. " * 250) + "\n\n"
                "| 항목 | 값 |\n| --- | --- |\n| 무료 크레딧 | 200달러 |\n\n"
                "## 마무리 — 지금 할 일\n\n1. 하나\n2. 둘\n3. 셋\n\n"
                "참고: [원문](https://example.com/a) [문서](https://example.org/b) [가이드](https://example.net/c)\n")
        md = ('---\ntitle: "%s"\ndescription: "요약"\ndate: 2026-10-19T09:30:00+09:00\n---\n\n%s' % (title, body))
        (root / (stamp + "-" + title + ".json")).write_text(
            json.dumps({"title": title, "reason": "1차 게이트 미달"}, ensure_ascii=False), encoding="utf-8")
        (root / (stamp + "-" + title + ".md")).write_text(md, encoding="utf-8")
        return stamp

    def test_kst_date_of_uses_kst_not_machine_local(self):
        inst = datetime.datetime(2026, 10, 18, 18, 0, tzinfo=datetime.timezone.utc)  # KST 10-19 03:00
        stamp_local = inst.astimezone().strftime("%Y%m%d-%H%M%S")
        assert rh._kst_date_of(stamp_local + "-글.json") == "2026-10-19"

    def test_kst_date_of_unparseable_returns_empty(self):
        assert rh._kst_date_of("깨진파일.json") == ""
        assert rh._kst_date_of("") == ""

    def test_scope_uses_kst_date(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(rh, "REJECTED_DIR", str(tmp_path))
        monkeypatch.setattr(rh, "_live_titles", lambda: set())
        monkeypatch.setattr(g, "dead_links", lambda links, **kw: [])
        utc = datetime.timezone.utc
        # 머신 로컬로는 전날일 수 있지만 KST 로는 10-19 → since=10-19 에 포함
        self._record(tmp_path, datetime.datetime(2026, 10, 18, 18, 0, tzinfo=utc), "경계시각글")
        # KST 10-18 → 제외
        self._record(tmp_path, datetime.datetime(2026, 10, 18, 3, 0, tzinfo=utc), "이전날글")
        rh.recover_since("2026-10-19", do_publish=False, limit=10)
        out = capsys.readouterr().out
        assert "경계시각글" in out, "KST 기준 10-19 인 보류건이 대상에서 빠졌다: %s" % out[:300]
        assert "이전날글" not in out, "KST 기준 10-18 인 보류건이 대상에 들어왔다"


class TestDuplicateGuard:
    def test_norm_title_ignores_punctuation(self):
        assert rh.norm_title("WorkBuddy에서 DeepSeek V4.1-Flash 무료로 쓰는 방법") == \
               rh.norm_title("WorkBuddy에서 DeepSeek V4.1 Flash 무료로 쓰는방법!")

    def test_is_duplicate_exact_and_extended(self):
        live = {"WorkBuddy에서 DeepSeek V4.1-Flash 무료로 쓰는 방법: 글로벌 버전 10월 31일까지 크레딧 0"}
        # 제목 뒤에 수식이 붙어도 중복으로 본다 (2026-10-19 실측: 이 형태로 중복 위험이 있었다)
        assert rh._is_duplicate("WorkBuddy에서 DeepSeek V4.1 Flash 무료로 쓰는 방법", live)
        assert not rh._is_duplicate("전혀 다른 주제의 새 글 제목입니다", live)

    def test_is_duplicate_respects_empty_live(self):
        assert rh._is_duplicate("아무 제목", set()) == ""
