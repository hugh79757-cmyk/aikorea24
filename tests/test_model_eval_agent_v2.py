"""AIK24-EVAL-JUDGE-04 — 판관 폐지 · 문항 v2(에이전트 축) · 결정적 채점.

검증 대상은 [PRODUCTION CODE] scripts/model_eval.py / scripts/free_models_page.py.
이 파일은 [TEST CODE] 다.

핵심 계약: **판관이 없다.** 같은 답안은 언제나 같은 점수다(0 또는 1). 측정 결함도 없다.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import model_eval as me  # noqa: E402


# ═══ 1. 문항 구성: 2/4/2/4 + 결정적 채점 배선 ══════════════════════════

def test_axis_distribution_is_2_4_2_4():
    from collections import Counter
    c = Counter(q["axis"] for q in me.TEST_QUESTIONS)
    assert (c["지시이행"], c["코딩실무"], c["맥락유지"], c["에이전트"]) == (2, 4, 2, 4)
    assert sum(c.values()) == 12


def test_docstring_does_not_claim_4x3():
    head = Path(me.__file__).read_text(encoding="utf-8")[:6000]
    assert "4개 실무 축 × 3문항" not in head


def test_no_chat_writing_axis_remains():
    assert "역할판단" not in me.AXES


def test_every_question_has_a_grading_path():
    """모든 문항은 sandbox 또는 결정적 채점 함수 중 하나를 갖는다."""
    for i, spec in enumerate(me.TEST_QUESTIONS, 1):
        if spec.get("sandbox"):
            assert spec.get("sandbox_harness"), f"Q{i}: sandbox 하네스 없음"
            assert spec.get("sandbox_reference"), f"Q{i}: sandbox reference 없음"
        else:
            assert spec.get("grade") in me.GRADERS, f"Q{i}: 채점 경로 없음"


def test_no_judge_remains():
    """판관 모델 기능이 코드에서 사라졌어야 한다."""
    for gone in ("JUDGE_MODEL", "JUDGE_TIMEOUT_SEC", "JUDGE_TEMPERATURE",
                 "JUDGE_MAX_TOKENS", "_judge_opencode", "_judge_groq",
                 "judge_precheck", "score_response"):
        assert not hasattr(me, gone), f"{gone} 은 판관 잔재다"


def test_grade_answer_raises_when_question_has_no_grader():
    with pytest.raises(KeyError):
        me.grade_answer({"axis": "없음", "q": "x"}, "답")


# ═══ 2. CLI 단일 경로 정책 (2026-10-14 대표님 결정) ═══════════════════════

def test_resolve_cli_model_uses_explicit_map_with_variant():
    assert me.resolve_cli_model("ll-alpha-free") == "opencode/ll-alpha-free#max"


def test_resolve_cli_model_reads_free_models_cli_catalog():
    assert me.resolve_cli_model("cohere/north-mini-code:free") == "kilo/cohere/north-mini-code:free"


def test_resolve_cli_model_returns_none_for_unregistered():
    assert me.resolve_cli_model("totally-unknown/model-x") is None


def test_main_entry_exits_2_when_cli_unregistered(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["model_eval.py", "totally-unknown/model-x"])
    monkeypatch.setattr(me, "resolve_cli_model", lambda mid: None)
    g = dict(me.__dict__)
    g["__name__"] = "__main__"
    txt = Path(me.__file__).read_text(encoding="utf-8")
    src = txt[txt.index('if __name__ == "__main__":'):]
    with pytest.raises(SystemExit) as e:
        exec(compile(src, "main", "exec"), g)
    assert e.value.code == 2


# ═══ 3. 결정적 채점 — 문항별 통과/실패 (9문항 × 2) ════════════════════════

def test_q1_korean_sentinel_pass():
    a = "이 코드는 두 값을 더해 돌려주는 파이썬 함수입니다.\n\n---끝---"
    assert me.grade_q1_korean_sentinel(a) == 1


def test_q1_korean_sentinel_fail_english_only():
    a = "This function adds two numbers.\n---끝---"
    assert me.grade_q1_korean_sentinel(a) == 0


def test_q2_pure_json_pass():
    a = '{"이름": "김민수", "나이": 31, "취미": ["등산", "독서"]}'
    assert me.grade_q2_pure_json(a) == 1


def test_q2_pure_json_fail_code_fence():
    a = '```json\n{"이름": "김민수", "나이": 31, "취미": ["등산", "독서"]}\n```'
    assert me.grade_q2_pure_json(a) == 0


def test_q4_pytest_pass():
    a = ("```python\n"
         "def test_safe_div_zero():\n    assert safe_div(1, 0) is None\n\n"
         "def test_safe_div_normal():\n    assert safe_div(4, 2) == 2\n```")
    assert me.grade_q4_pytest_written(a) == 1


def test_q4_pytest_fail_prose_only():
    assert me.grade_q4_pytest_written("safe_div 은 0 이면 None 을 돌려줍니다.") == 0


def test_q7_marker_pass():
    assert me.grade_q7_marker_exact("normalize_ledger_entries") == 1


def test_q7_marker_fail_near_miss():
    assert me.grade_q7_marker_exact("normalize_ledger_entries 입니다.") == 0


def test_q8_three_tasks_pass():
    a = "1. 파이썬 설치 확인 2. 변수 이름 규칙 세 가지 3. 에러 메시지 끝까지 읽기"
    assert me.grade_q8_three_tasks(a) == 1


def test_q8_three_tasks_fail_missing_third():
    assert me.grade_q8_three_tasks("1. 파이썬 설치 확인 2. 변수 이름 규칙") == 0


def test_q9_json_array5_pass():
    a = '["race condition", "global state", "idempotency", "persistence fault", "side effect"]'
    assert me.grade_q9_json_array5(a) == 1


def test_q9_json_array5_fail_wrong_length():
    assert me.grade_q9_json_array5('["race condition", "idempotency"]') == 0


def test_q10_rootcause_diff_pass():
    a = ("Root cause: timeout 5초가 부족하고 예외 처리가 없다.\n"
         "--- a/app.py\n+++ b/app.py\n@@ -8,3 +8,6 @@\n+    try:\n+        ...\n")
    assert me.grade_q10_rootcause_diff(a) == 1


def test_q10_rootcause_diff_fail_no_diff():
    assert me.grade_q10_rootcause_diff("Root cause: 네트워크가 느리다.") == 0


def test_q11_four_step_plan_pass():
    a = ('[{"screen": "뼈대", "state_model": "epoch", "verify": "로딩"},'
         ' {"screen": "선택", "state_model": "card", "verify": "클릭"},'
         ' {"screen": "계통수", "state_model": "tree", "verify": "화면"},'
         ' {"screen": "엔딩", "state_model": "extinct", "verify": "문구"}]')
    assert me.grade_q11_four_step_plan(a) == 1


def test_q11_four_step_plan_fail_missing_keys():
    a = '[{"step": 1}, {"step": 2}, {"step": 3}, {"step": 4}]'
    assert me.grade_q11_four_step_plan(a) == 0


def test_q12_priority_split_pass():
    a = ("## 지금 처리\n- 고객 메일 발송 대기 건\n- 느린 쿼리 하나\n\n"
         "## 나중에\n- 내부 도구 버튼 문구 수정")
    assert me.grade_q12_priority_split(a) == 1


def test_q12_priority_split_fail_button_not_deferred():
    a = "## 지금 처리\n- 고객 메일 발송\n- 느린 쿼리\n- 버튼 문구도 지금 한다"
    assert me.grade_q12_priority_split(a) == 0


# ═══ 4. 샌드박스 — 실행 기반 채점 (3문항 × 2) ═══════════════════════════

def _specs():
    return {q.get("sandbox_kind"): q for q in me.TEST_QUESTIONS if q.get("sandbox")}


@pytest.mark.parametrize("kind", ["get_expired_tokens", "user_filter_refactor", "parse_log_line"])
def test_sandbox_reference_passes(kind):
    spec = _specs()[kind]
    pts, reason = me.sandbox_grade(spec, "```python\n" + spec["sandbox_reference"] + "```")
    assert pts == 1, f"{kind}: {reason}"


@pytest.mark.parametrize("kind,bad", [
    ("get_expired_tokens",
     "from datetime import datetime, timedelta\n\n"
     "def get_expired_tokens(tokens, now):\n"
     "    return [t for t in tokens\n"
     "            if datetime.fromisoformat(t['expires_at']) < now - timedelta(days=30)]\n"),
    ("user_filter_refactor",
     "def get_active_user(users):\n    return [u for u in users]\n\n"
     "def get_admin_user(users):\n    return [u for u in users]\n"),
    ("parse_log_line", "def parse_log_line(s):\n    return s\n"),
])
def test_sandbox_broken_answer_fails(kind, bad):
    spec = _specs()[kind]
    pts, _ = me.sandbox_grade(spec, bad)
    assert pts == 0


def test_extract_code_strips_fences():
    assert me.extract_code("설명.\n```python\nprint(1)\n```\n끝").strip() == "print(1)"


def test_sandbox_reference_failure_is_measurement_defect():
    """reference 정답이 통과 못 하면 그 문항은 측정 결함 — 0점으로 몰지 않는다."""
    spec = dict(_specs()["parse_log_line"])
    spec["sandbox_reference"] = "def parse_log_line(s):\n    return None\n"
    pts, reason = me.sandbox_grade(spec, "def parse_log_line(s):\n    return ('a','INFO','b')\n")
    assert pts is None and "측정 결함" in reason


# ═══ 5. 채점 분모 · 표기 ══════════════════════════════════════════════════

def test_graded_denominator_is_always_full(monkeypatch):
    """결정적 채점에는 측정 결함이 없다 — 분모는 언제나 12."""
    monkeypatch.setattr(me, "cli_call", lambda *a, **k: ("답", ""))
    monkeypatch.setattr(me.time, "sleep", lambda *_: None)
    res, blocked = me.eval_model_cli("cat-jam-free")
    assert blocked is None
    assert res["defect_n"] == 0
    assert res["graded_n"] == 12
    assert all(isinstance(d["score"], int) for d in res["details"])


def test_score_display_has_no_exclusion_suffix():
    assert me.score_display({"score": 10, "graded_n": 12, "max_score": 12}) == "10/12"


def test_same_answer_always_scores_same(monkeypatch):
    """결정성 — 같은 답안을 두 번 채점해도 결과가 같다."""
    monkeypatch.setattr(me, "cli_call", lambda *a, **k: (
        '{"이름": "김민수", "나이": 31, "취미": ["등산", "독서"]}', ""))
    monkeypatch.setattr(me.time, "sleep", lambda *_: None)
    a, _ = me.eval_model_cli("cat-jam-free")
    b, _ = me.eval_model_cli("cat-jam-free")
    assert a["score"] == b["score"]
    assert [d["score"] for d in a["details"]] == [d["score"] for d in b["details"]]


# ═══ 6. 러닝 로그 append (덮어쓰지 않는다) ═══════════════════════════════

def test_append_run_log_is_append_only(tmp_path, monkeypatch):
    p = tmp_path / "runs.jsonl"
    monkeypatch.setattr(me, "RUNS_LOG_PATH", str(p))
    me.append_run_log({"model_id": "m", "score": 1})
    me.append_run_log({"model_id": "m", "score": 1})
    assert len(p.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_runs_log_survives_cache_overwrite(tmp_path, monkeypatch):
    import json as _j
    monkeypatch.setattr(me, "CACHE_PATH", str(tmp_path / "cache.json"))
    monkeypatch.setattr(me, "RUNS_LOG_PATH", str(tmp_path / "runs.jsonl"))
    monkeypatch.setattr(me, "LEADERBOARD_PATH", str(tmp_path / "lb.json"))
    for score in (9, 10):
        me.cache_put("cat-jam-free", {"model_id": "cat-jam-free", "score": score,
                                      "max_score": 12, "graded_n": 12, "details": [{"idx": 1}]})
    lines = (tmp_path / "runs.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert [_j.loads(x)["score"] for x in lines] == [9, 10]
    assert _j.loads((tmp_path / "cache.json").read_text(encoding="utf-8"))["cat-jam-free"]["score"] == 10


# ═══ 7. 사용 가능 수준 라벨 ══════════════════════════════════════════════

def test_usage_levels_map_scores_to_labels():
    lv = me.usage_levels({"코딩실무": {"score": 3}, "에이전트": {"score": 1}}, 2)
    assert lv["코딩실무"] == "코딩 실무 가능"
    assert lv["에이전트"] == "에이전트 기초 수준"
    assert lv["한글"] == "한글 사용 가능"


def test_usage_levels_zero_means_unusable():
    lv = me.usage_levels({"코딩실무": {"score": 0}, "에이전트": {"score": 0}}, 0)
    assert lv["코딩실무"] == "코딩 사용 불가"
    assert lv["에이전트"] == "에이전트 사용 불가"
    assert lv["한글"] == "한글 사용 불가"
