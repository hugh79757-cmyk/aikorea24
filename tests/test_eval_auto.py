"""AIK24-EVAL-AUTO (2026-11-08) 회귀 테스트.

고정하는 계약(정책)만 검사한다 — 실제 CLI 호출·네트워크·EmDash 쓰기는 하지 않는다.

1. 트리거 필터: 무료 접미사 규칙으로만 새 모델을 고른다(유료·이름변경·제거 제외).
2. CLI 목록 조회 실패는 "0건"과 구분된다(빈 자료를 성공으로 바꾸지 않는다).
3. 블로그 초안은 측정값만 쓰고, 게이트가 요구하는 형식(마무리 H2·표·3,000자)을 만족한다.
4. 0점 문항은 성격을 단정하지 않고 '검토 필요'로 표시된다.
"""
import json
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import free_model_eval_auto as fea  # noqa: E402
import model_eval as me  # noqa: E402


def _fake_result(score=9, max_score=12):
    details = []
    for i, spec in enumerate(me.TEST_QUESTIONS, 1):
        pts = 1 if i <= score else 0
        details.append({
            "idx": i, "axis": spec["axis"], "score": pts, "source": "cli",
            "answer": f"답변 {i} " + "가" * 40,
        })
    res = {
        "model_id": "iceman-free", "source": "cli", "provider": "zen",
        "cli_model": "opencode/iceman-free", "score": score, "max_score": max_score,
        "details": details, "failed": 0, "defect_n": 0, "no_response_n": 0,
        "graded_n": max_score, "score_display": f"{score}/{max_score}",
        "by_axis": {}, "token_usage": {"prompt": 0, "completion": 0},
    }
    for d in details:
        b = res["by_axis"].setdefault(d["axis"], {"score": 0, "max_score": 0, "failed": 0})
        b["max_score"] += 1
        b["score"] += d["score"]
    return res


# ── 1. 트리거 필터 ──────────────────────────────────────────────────────

def test_candidates_keep_only_free_suffix():
    alert = {
        "new_by_provider": {
            "openrouter": ["liquid/lfm-3-1.7b:free", "liquid/lfm-3-1.7b"],
            "kilo": ["liquid/lfm-3-1.7b:free"],
            "zen": ["iceman-free", "inkling-2-small-free", "some-paid-model"],
        },
        "removed_by_provider": {"zen": ["pulse-alpha-free"]},
    }
    got = [c["model_id"] for c in fea.candidates_from_alert(alert)]
    assert got == ["liquid/lfm-3-1.7b:free", "iceman-free", "inkling-2-small-free"]


def test_candidates_dedupe_and_skip_unknown_provider():
    alert = {"new_by_provider": {"somewhere": ["x-free"], "zen": ["iceman-free", "iceman-free"]}}
    got = [c["model_id"] for c in fea.candidates_from_alert(alert)]
    assert got == ["iceman-free"]


# ── 2. 실패를 0건으로 바꾸지 않는다 ────────────────────────────────────

def test_cli_catalog_returns_none_on_missing_cli(monkeypatch):
    class Boom(FileNotFoundError):
        pass

    def fake_run(*a, **k):
        raise Boom()

    monkeypatch.setattr(fea.subprocess, "run", fake_run)
    assert fea.cli_catalog() is None


def test_cli_catalog_returns_none_on_empty_output(monkeypatch):
    class P:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(fea.subprocess, "run", lambda *a, **k: P())
    assert fea.cli_catalog() is None


def test_cli_catalog_returns_set(monkeypatch):
    class P:
        returncode = 0
        stdout = "opencode/iceman-free\nopenrouter/x:free\nnot-a-model-line\n"
        stderr = ""

    monkeypatch.setattr(fea.subprocess, "run", lambda *a, **k: P())
    got = fea.cli_catalog()
    assert got == {"opencode/iceman-free", "openrouter/x:free"}


def test_resolve_cli_id_uses_provider_prefix():
    cat = {"opencode/iceman-free", "openrouter/liquid/lfm-3-1.7b:free", "kilo/liquid/lfm-3-1.7b:free"}
    assert fea.resolve_cli_id("iceman-free", "zen", cat) == "opencode/iceman-free"
    assert fea.resolve_cli_id("liquid/lfm-3-1.7b:free", "kilo", cat) == "kilo/liquid/lfm-3-1.7b:free"
    assert fea.resolve_cli_id("iceman-free", "kilo", cat) is None
    assert fea.resolve_cli_id("iceman-free", "nvidia-nim", cat) is None


# ── 3. 초안 = 측정값 + 시리즈 포맷 ─────────────────────────────────────

def test_build_draft_meets_series_format():
    res = _fake_result(score=9)
    title, body, excerpt = fea.build_draft(
        "iceman-free", res, "opencode/iceman-free", measured_context=262144, day="2026-11-08")

    # PIPE-10 모델 귀속
    assert "iceman-free" in title and "iceman-free" in body
    # 2026-11-08 재작성된 독자용 구조
    assert body.startswith("OpenCode 무료 목록에")          # 라벨 없이 독자 문장으로 시작
    assert "## iceman-free가 뭔가" in body
    assert "## 5분 안에 써보기" in body
    assert "## 어떤 작업에 강한가" in body
    assert "## 어디서 걸리는가" in body
    assert "## 다른 무료 모델과 비교" in body
    assert "## AIK24 실측 결과 (2026-11-08)" in body
    assert body.count("\n## 마무리") == 1
    # 측정값 그대로
    assert "9/12" in body
    assert "262,144 토큰" in body
    # 토큰 사용량은 미측정으로 명시
    assert "CLI 경유로 측정되지 않음 (미측정)" in body
    assert excerpt and "**" not in excerpt and "`" not in excerpt


def test_build_draft_passes_quality_gate():
    res = _fake_result(score=9)
    title, body, _ = fea.build_draft(
        "iceman-free", res, "opencode/iceman-free", measured_context=262144, day="2026-11-08")
    ok, issues, repaired = fea.gate_draft(title, body, "iceman-free", verify_links=False)
    assert ok, issues
    assert len(repaired) >= 3000


def test_build_draft_without_measured_context_says_unmeasured():
    res = _fake_result(score=4)
    title, body, _ = fea.build_draft("iceman-free", res, "opencode/iceman-free",
                                     measured_context=None, day="2026-11-08")
    assert "| 니들 컨텍스트 실측 하한 | 미측정 |" in body


def test_build_draft_has_no_internal_terms():
    res = _fake_result(score=6)
    _, body, _ = fea.build_draft("iceman-free", res, "opencode/iceman-free", day="2026-11-08")
    for term in ("launchd", "dev.vars", ".env.common", "firecrawl"):
        assert term not in body


def test_gate_draft_fails_when_model_not_attributed():
    res = _fake_result(score=9)
    _t, body, _ = fea.build_draft("iceman-free", res, "opencode/iceman-free", day="2026-11-08")
    ok, issues, _ = fea.gate_draft("무제", body, "iceman-free", verify_links=False)
    assert not ok
    assert any("PIPE-10" in i for i in issues)


# ── 3-b. 2026-11-08 강화된 '읽는 사람' 게이트 ────────────────────────────

def _body(score=9):
    return fea.build_draft("iceman-free", _fake_result(score), "opencode/iceman-free",
                           day="2026-11-08")[1]


def test_gate_rejects_report_label_lead():
    body = "한 줄 요약: 이 모델은 좋습니다.\n" + _body()
    ok, issues, _ = fea.gate_draft("iceman-free 실측", body, "iceman-free", verify_links=False)
    assert not ok
    assert any("한 줄 요약" in i for i in issues)


def test_gate_rejects_question_dump():
    body = _body() + "\n" + "\n".join(f"- Q{i} [축] 정답 — 답변: ..." for i in range(1, 13)) + "\n"
    ok, issues, _ = fea.gate_draft("iceman-free 실측", body, "iceman-free", verify_links=False)
    assert not ok
    assert any("문항 나열" in i for i in issues)


def test_gate_rejects_too_many_tables():
    body = _body() + "\n| a |\n| --- |\n| b |\n\n| c |\n| --- |\n| d |\n"
    ok, issues, _ = fea.gate_draft("iceman-free 실측", body, "iceman-free", verify_links=False)
    assert not ok
    assert any("표 " in i for i in issues)


def test_gate_rejects_repo_path_leak():
    body = _body() + "\n이 저장소에는 `tests/test_safe_div.py` 가 있습니다.\n"
    ok, issues, _ = fea.gate_draft("iceman-free 실측", body, "iceman-free", verify_links=False)
    assert not ok
    assert any("저장소 경로" in i for i in issues)


def test_gate_rejects_japanese_katakana():
    body = _body() + "\n타임아ウト이 발생했습니다.\n"
    ok, issues, _ = fea.gate_draft("iceman-free 실측", body, "iceman-free", verify_links=False)
    assert not ok
    assert any("가타카나" in i for i in issues)


def test_scrub_answer_removes_repo_paths():
    got = fea._scrub_answer("구현 `scripts/safe_div.py` 와 테스트 tests/test_x.py 를 참고했습니다")
    assert "scripts/" not in got and "tests/" not in got


# ── 4. 0점 문항 = 검토 필요 ───────────────────────────────────────────

def test_zero_score_notes_are_review_needed_not_judged():
    res = _fake_result(score=8)
    zeros = fea.zero_score_notes(res)
    assert len(zeros) == 4
    assert all(z["review_needed"] for z in zeros)
    assert all("성격" not in json.dumps(z, ensure_ascii=False) for z in zeros)
    assert [z["idx"] for z in zeros] == [9, 10, 11, 12]


def test_zero_score_notes_empty_when_all_correct():
    assert fea.zero_score_notes(_fake_result(score=12)) == []


# ── 5. 평가 호출은 저장소 밖(임시 디렉터리)에서 돈다 ────────────────────

def test_sandbox_cwd_moves_out_and_restores():
    import os
    before = os.getcwd()
    with fea._sandbox_cwd() as d:
        assert os.path.realpath(os.getcwd()) == os.path.realpath(d)
        assert os.path.realpath(d) != os.path.realpath(before)
    assert os.getcwd() == before


def test_evaluate_runs_cli_outside_repo(monkeypatch):
    """opencode run 이 저장소에서 돌면 모델이 저장소 파일을 덮어쓴다(2026-11-08 사고)."""
    import os
    seen = {}
    repo = os.getcwd()

    def fake_eval(model_id, cli_model=None):
        seen["cwd"] = os.getcwd()
        return _fake_result(score=9), None

    monkeypatch.setattr(fea.model_eval, "eval_model_cli", fake_eval)
    monkeypatch.setattr(fea.model_eval, "probe_context_length", lambda *a, **k: 8192)
    monkeypatch.setattr(fea.model_eval, "cache_put", lambda *a, **k: None)
    monkeypatch.setattr(fea.model_eval, "cache_load", lambda: {"iceman-free": {"details": [1]}})
    out = fea.evaluate("iceman-free", "opencode/iceman-free")
    assert out["ok"] is True
    assert os.path.realpath(seen["cwd"]) != os.path.realpath(repo)


# ── 6. 시퀀스 고정: 브리핑 발행 → 모델 테스트 → 블로그 글 ────────────────

def _row(source, mid, date="2026-11-08-1", order=1, news_id=1):
    return {"source": source, "original_title": mid, "date": date,
            "sort_order": order, "news_id": news_id}


def test_briefing_rows_map_only_free_model_sources():
    rows = [
        _row("OpenCode Zen", "iceman-free", order=1),
        _row("OpenRouter Free Models", "liquid/lfm-3-1.7b:free", order=2),
        _row("The Decoder", "사이버 보안 기사", order=3),      # 무료 모델 소스 아님
        _row("Kilo Free Models", "", order=4),                # 제목 없음
    ]
    got = fea._candidates_from_briefing_rows(rows)
    assert [c["model_id"] for c in got] == ["iceman-free", "liquid/lfm-3-1.7b:free"]
    assert got[0]["provider"] == "zen"
    assert got[0]["briefing_date"] == "2026-11-08-1" and got[0]["sort_order"] == 1


def test_briefing_rows_dedupe_same_model():
    rows = [_row("OpenCode Zen", "iceman-free", order=1),
            _row("OpenCode Zen", "iceman-free", order=2)]
    assert len(fea._candidates_from_briefing_rows(rows)) == 1


def test_alert_only_candidate_waits_for_briefing():
    """브리핑에 아직 안 실린 신규는 테스트하지 않고 대기 상태로만 기록한다."""
    q = {"models": {}}
    fea._merge_candidates(q, [{"provider": "zen", "model_id": "inkling-2-small-free"}],
                          "2026-11-08", briefed=False)
    e = q["models"]["inkling-2-small-free"]
    assert e["status"] == "awaiting_briefing"
    assert "브리핑" in e["reason"]


def test_briefed_candidate_promotes_from_awaiting():
    q = {"models": {}}
    fea._merge_candidates(q, [{"provider": "zen", "model_id": "iceman-free"}],
                          "2026-11-08", briefed=False)
    fea._merge_candidates(q, [{"provider": "zen", "model_id": "iceman-free",
                               "briefing_date": "2026-11-08-1", "sort_order": 1, "news_id": 5}],
                          "2026-11-08", briefed=True)
    e = q["models"]["iceman-free"]
    assert e["status"] == "pending"
    assert e["briefing"]["sort_order"] == 1


def test_make_post_publishes_and_links_when_gate_passes(monkeypatch, tmp_path):
    calls = {}
    monkeypatch.setattr(fea, "DRAFT_DIR", tmp_path)
    monkeypatch.setattr(fea, "AUTO_PUBLISH", True)

    import emdash_publish as ep
    monkeypatch.setattr(ep, "create_draft_post", lambda *a, **k: calls.setdefault("draft", "u"))
    monkeypatch.setattr(ep, "publish_by_slug", lambda u: "https://x/posts/published")
    monkeypatch.setattr(fea, "_link_briefing", lambda e, u: calls.setdefault("link", u))

    e = {"model_id": "iceman-free", "briefing": {"date": "2026-11-08-1", "sort_order": 1}}
    fea._make_post(e, "iceman-free", _fake_result(9), "opencode/iceman-free", 8192,
                   "2026-11-08", {"models": {}})
    assert calls.get("draft") == "u"
    assert e["published_url"] == "https://x/posts/published"
    assert e["briefing_linked"] is True


def test_make_post_never_publishes_when_gate_fails(monkeypatch, tmp_path):
    """게이트 미달이면 초안 보존까지만 — 발행 함수는 아예 호출되지 않아야 한다."""
    monkeypatch.setattr(fea, "DRAFT_DIR", tmp_path)
    monkeypatch.setattr(fea, "REJECTED_DIR", tmp_path)
    monkeypatch.setattr(fea, "AUTO_PUBLISH", True)
    # 마무리 H2 가 없는 얇은 본문 → 게이트 실패
    monkeypatch.setattr(fea, "build_draft", lambda *a, **k: ("iceman-free 실측", "짧은 본문", "짧은 본문"))
    published = {"n": 0}

    import emdash_publish as ep
    monkeypatch.setattr(ep, "create_draft_post", lambda *a, **k: published.update(n=100) or "x")
    monkeypatch.setattr(ep, "publish_by_slug", lambda u: published.update(n=1) or "x")

    e = {"model_id": "iceman-free"}
    fea._make_post(e, "iceman-free", _fake_result(9), "opencode/iceman-free", 8192,
                   "2026-11-08", {"models": {}})
    assert published["n"] == 0
    assert e["draft"]["ok"] is False and e["draft"]["issues"]


def test_publish_flag_is_explicit():
    """발행 자동화는 상수 하나로 끌 수 있어야 한다."""
    assert isinstance(fea.AUTO_PUBLISH, bool)


# ── 7. 신규 모델만 측정 (2026-11-12 대표님 지시) ────────────────────────

def test_already_measured_from_cache_even_if_ttl_expired(monkeypatch):
    """캐시가 만료돼도 이미 측정한 모델은 재측정하지 않는다."""
    old = {"score": 8, "max_score": 12, "details": [{"idx": 1}], "ts": 0}
    monkeypatch.setattr(fea.model_eval, "cache_load", lambda: {"m-free": old})
    why, hit = fea.already_measured("m-free")
    assert why == "캐시" and hit is old


def test_already_measured_from_leaderboard_without_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(fea.model_eval, "cache_load", lambda: {})
    lb = tmp_path / "lb.json"
    lb.write_text(json.dumps([{"model_id": "m-free", "qv": fea.model_eval.EVAL_QUESTIONS_VERSION, "score": 9}]),
                  encoding="utf-8")
    monkeypatch.setattr(fea.model_eval, "LEADERBOARD_PATH", str(lb))
    why, hit = fea.already_measured("m-free")
    assert why == "리더보드" and hit is None


def test_already_measured_false_for_new_model(monkeypatch, tmp_path):
    monkeypatch.setattr(fea.model_eval, "cache_load", lambda: {})
    lb = tmp_path / "lb.json"
    lb.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(fea.model_eval, "LEADERBOARD_PATH", str(lb))
    assert fea.already_measured("brand-new-free") == (None, None)
