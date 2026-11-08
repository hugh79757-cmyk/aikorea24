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
    # 시리즈 포맷
    assert "## 2. OpenCode에서 사용하는 방법" in body
    assert "## 4. 이런 분께 추천합니다" in body
    assert "## 5. 솔직한 한계" in body
    assert "## AIK24 실측 결과 (2026-11-08)" in body
    assert body.count("\n## 마무리") == 1
    # 측정값 그대로
    assert "9/12" in body
    assert "262,144 토큰" in body
    # 토큰 사용량은 미측정으로 명시
    assert "CLI 경유로 측정되지 않음 (미측정)" in body
    assert excerpt and "**" not in excerpt


def test_build_draft_passes_quality_gate():
    res = _fake_result(score=9)
    title, body, _ = fea.build_draft(
        "iceman-free", res, "opencode/iceman-free", measured_context=262144, day="2026-11-08")
    ok, issues, repaired = fea.gate_draft(title, body, "iceman-free")
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
    ok, issues, _ = fea.gate_draft("무제", body, "iceman-free")
    assert not ok
    assert any("PIPE-10" in i for i in issues)


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
