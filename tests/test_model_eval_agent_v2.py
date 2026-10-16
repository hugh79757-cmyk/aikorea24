"""AGENT-EVAL-01: 문항 v2 (에이전트·코딩 축) + 샌드박스 채점 + CLI 단일 경로.

검증 대상은 [PRODUCTION CODE] scripts/model_eval.py / scripts/free_models_page.py.
이 테스트 파일은 [TEST CODE] 다 — 둘을 동시에 고치지 않는다.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import model_eval as me  # noqa: E402


# ── 1. 문항 구성: 2/4/2/4 + 독스트링 정합성 ────────────────────────────

def test_axis_distribution_is_2_4_2_4():
    from collections import Counter
    c = Counter(q["axis"] for q in me.TEST_QUESTIONS)
    assert c["지시이행"] == 2
    assert c["코딩실무"] == 4
    assert c["맥락유지"] == 2
    assert c["에이전트"] == 4
    assert sum(c.values()) == 12


def test_docstring_does_not_claim_4x3():
    """均衡 배분 주장("4개 실무 축 × 3문항")이 코드에 남아 있으면 문서-코드 불일치다."""
    head = Path(me.__file__).read_text(encoding="utf-8")[:6000]
    assert "4개 실무 축 × 3문항" not in head


def test_no_chat_writing_axis_remains():
    assert "역할판단" not in me.AXES


# ── 2. CLI 단일 경로 정책 ──────────────────────────────────────────────

def test_resolve_cli_model_uses_explicit_map_with_variant():
    assert me.resolve_cli_model("ll-alpha-free") == "opencode/ll-alpha-free#max"


def test_resolve_cli_model_reads_free_models_cli_catalog():
    hit = me.resolve_cli_model("cohere/north-mini-code:free")
    assert hit == "kilo/cohere/north-mini-code:free"


def test_resolve_cli_model_returns_none_for_unregistered():
    assert me.resolve_cli_model("totally-unknown/model-x") is None


def test_main_entry_exits_2_when_cli_unregistered(monkeypatch):
    """정책: CLI 대상 미등록 → API 폴백 금지, 점수 없이 제외."""
    monkeypatch.setattr(sys, "argv", ["model_eval.py", "totally-unknown/model-x"])
    monkeypatch.setattr(me, "resolve_cli_model", lambda mid: None)
    g = dict(me.__dict__)
    g["__name__"] = "__main__"
    with pytest.raises(SystemExit) as e:
        exec(compile(_main_src(), "model_eval_main", "exec"), g)
    assert e.value.code == 2


def _main_src():
    txt = Path(me.__file__).read_text(encoding="utf-8")
    i = txt.index('if __name__ == "__main__":')
    return txt[i:]


# ── 3. 샌드박스: reference 통과 / 오답 실패 / 코드추출 ──────────────────

def _specs():
    return {q.get("sandbox_kind"): q for q in me.TEST_QUESTIONS if q.get("sandbox")}


def test_three_questions_are_sandboxed():
    assert set(_specs()) == {"get_expired_tokens", "user_filter_refactor", "parse_log_line"}


@pytest.mark.parametrize("kind", ["get_expired_tokens", "user_filter_refactor", "parse_log_line"])
def test_reference_solution_passes_its_own_harness(kind):
    spec = _specs()[kind]
    pts, reason = me.sandbox_grade(spec, "```python\n" + spec["sandbox_reference"] + "```")
    assert pts == 1, f"{kind}: {reason}"


def test_extract_code_strips_fences():
    got = me.extract_code("설명입니다.\n```python\nprint(1)\n```\n끝")
    assert got.strip() == "print(1)"
    assert "```" not in got


def test_extract_code_falls_back_to_raw_text():
    assert me.extract_code("def f():\n    return 1") != ""


def test_empty_answer_scores_zero_not_crash():
    spec = _specs()["parse_log_line"]
    pts, reason = me.sandbox_grade(spec, "")
    assert pts == 0


def test_broken_answer_fails_with_zero():
    """원래 버그(30일 뒤)를 그대로 돌려주는 답 = 실행 검증에서 0점."""
    spec = _specs()["get_expired_tokens"]
    broken = (
        "from datetime import datetime, timedelta\n\n"
        "def get_expired_tokens(tokens, now):\n"
        "    return [t for t in tokens\n"
        "            if datetime.fromisoformat(t['expires_at']) < now - timedelta(days=30)]\n"
    )
    pts, reason = me.sandbox_grade(spec, broken)
    assert pts == 0, reason


def test_reference_failure_is_measurement_defect_not_zero():
    """우리 정답이 통과 못 하면 그 문항은 측정 결함 — 모델을 0점으로 punish 하지 않는다."""
    spec = dict(_specs()["parse_log_line"])
    spec["sandbox_reference"] = "def parse_log_line(s):\n    return None\n"
    spec["sandbox_harness"] = "assert parse_log_line('2026-10-16T03:04:05Z INFO x') is not None\nprint('SANDBOX_OK')\n"
    pts, reason = me.sandbox_grade(spec, "def parse_log_line(s):\n    return ('a','INFO','b')\n")
    assert pts is None
    assert "측정 결함" in reason


def test_wrong_exception_type_fails_not_defect():
    spec = _specs()["parse_log_line"]
    bad = (
        "def parse_log_line(s):\n"
        "    parts = s.split()\n"
        "    if len(parts) < 3:\n"
        "        raise RuntimeError('x')\n"
        "    return parts[0], parts[1], ' '.join(parts[2:])\n"
    )
    pts, reason = me.sandbox_grade(spec, bad)
    assert pts == 0, reason


def test_sandbox_points_are_int_not_bool(monkeypatch):
    """샌드박스는 bool 을 반환한다 — details[].score 에 true 가 박히면 안 된다."""
    calls = {"n": 0}

    def fake(cli_model, prompt, timeout=60):
        calls["n"] += 1
        return ("정답", "")

    monkeypatch.setattr(me, "cli_call", fake)
    monkeypatch.setattr(me, "sandbox_grade", lambda spec, ans: (True, "stub"))
    monkeypatch.setattr(me, "score_response", lambda q, e, a: 1)
    monkeypatch.setattr(me.time, "sleep", lambda *_: None)
    res, _ = me.eval_model_cli("cat-jam-free")
    sb = [d for d in res["details"] if d.get("sandbox")]
    assert sb, "샌드박스 문항이 하나도 없어 테스트가 무의미"
    for d in sb:
        assert type(d["score"]) is int, f'Q{d["idx"]} score={d["score"]!r} ({type(d["score"]).__name__})'
    assert type(res["sandbox_pass"]) is int


# ── 4. 신뢰도 4단계 (AGENT-EVAL-01 후속) ────────────────────────────────

def test_judge_temperature_is_zero():
    """판관 온도 고정 — 0.1 로는 같은 답안에 0/1 이 흔들렸다."""
    assert me.JUDGE_TEMPERATURE == 0.0


def _fake_run(monkeypatch, answers, sandbox=None):
    seq = iter(answers)
    monkeypatch.setattr(me, "cli_call", lambda *a, **k: (next(seq), ""))
    if sandbox is not None:
        monkeypatch.setattr(me, "sandbox_grade", lambda spec, ans: sandbox)
    monkeypatch.setattr(me, "score_response", lambda q, e, a: 1)
    monkeypatch.setattr(me.time, "sleep", lambda *_: None)
    return me.eval_model_cli("cat-jam-free")


def test_judged_denominator_excludes_defects_and_no_response(monkeypatch):
    """측정 결함·미응답을 뺀 **실제 채점 분모**가 결과에 남는다.

    판관이 전부 결함을 낸다 해도 샌드박스 3문항은 기계 판정이라 분모에 남는다 —
    즉 분모는 12 가 아니라 9 로 줄고, 결함은 9 로 기록된다.
    """
    monkeypatch.setattr(me, "cli_call", lambda *a, **k: ("답", ""))
    monkeypatch.setattr(me, "score_response", lambda q, e, a: None)   # 판관 전부 결함
    monkeypatch.setattr(me.time, "sleep", lambda *_: None)
    res, _ = me.eval_model_cli("cat-jam-free")
    sandbox_n = sum(1 for q in me.TEST_QUESTIONS if q.get("sandbox"))
    assert sandbox_n == 3
    assert res["defect_n"] == 12 - sandbox_n
    assert res["judged_n"] == res["max_score"] - res["failed"] - res["defect_n"]
    assert res["judged_n"] == sandbox_n
    assert res["no_response_n"] == 0


def test_score_display_uses_judged_not_max(monkeypatch):
    monkeypatch.setattr(me, "cli_call", lambda *a, **k: ("답", ""))
    monkeypatch.setattr(me, "score_response", lambda q, e, a: 1)
    monkeypatch.setattr(me, "sandbox_grade", lambda spec, ans: (None, "결함"))
    monkeypatch.setattr(me.time, "sleep", lambda *_: None)
    res, _ = me.eval_model_cli("cat-jam-free")
    assert res["judged_n"] == 12
    assert res["score_display"] == "12/12"


def test_score_display_reports_exclusions():
    d = me.score_display({"score": 10, "judged_n": 11, "defect_n": 1, "max_score": 12})
    assert d == "10/11 (측정 결함 1 제외)"
    d2 = me.score_display({"score": 7, "judged_n": 10, "defect_n": 1,
                           "no_response_n": 1, "max_score": 12})
    assert "측정 결함 1" in d2 and "미응답 1" in d2 and d2.startswith("7/10")


def test_append_run_log_is_append_only(tmp_path, monkeypatch):
    """캐시는 덮어써도 되지만 러닝 로그는append 되야 변동 재현이 가능하다."""
    p = tmp_path / "runs.jsonl"
    monkeypatch.setattr(me, "RUNS_LOG_PATH", str(p))
    entry = {"model_id": "m", "score": 1}
    assert me.append_run_log(entry) is True
    assert me.append_run_log(entry) is True
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2, "두 번째 기록이 덮어써졌다"


def test_runs_log_survives_cache_overwrite(tmp_path, monkeypatch):
    """같은 모델을 두 번 돌려도 러닝 로그에는 두 줄이 남아야 한다."""
    cache = tmp_path / "cache.json"
    monkeypatch.setattr(me, "CACHE_PATH", str(cache))
    monkeypatch.setattr(me, "RUNS_LOG_PATH", str(tmp_path / "runs.jsonl"))
    monkeypatch.setattr(me, "LEADERBOARD_PATH", str(tmp_path / "lb.json"))
    for score in (9, 10):
        me.cache_put("cat-jam-free", {"model_id": "cat-jam-free", "score": score,
                                      "max_score": 12, "judged_n": 12, "details": [{"idx": 1}]})
    lines = (tmp_path / "runs.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    import json as _j
    assert [_j.loads(l)["score"] for l in lines] == [9, 10]
    assert _j.loads(cache.read_text(encoding="utf-8"))["cat-jam-free"]["score"] == 10


# ── AIK24-EVAL-JUDGE-01: 판관 Groq 고정 + JUDGE_MAX_TOKENS 상향 ────────

def test_judge_max_tokens_raised():
    """판관이 산문으로 시작해도 잘리지 않아야 한다 (10 → 100)."""
    assert me.JUDGE_MAX_TOKENS == 100


def test_judge_model_and_base_url_are_pinned():
    """판정 주체가 매번 바뀌면 점수 비교가 동전이다 — Groq 단일 모델로 고정."""
    assert me.JUDGE_PROVIDER == "groq"
    assert me.JUDGE_MODEL == "qwen/qwen3.8-27b"
    assert me.JUDGE_BASE_URL == "https://api.groq.com/openai/v1"
    assert me.JUDGE_KEY_NAMES == ("GROQ_API_KEY", "GROQ_API_KEY_2",
                                  "GROQ_API_KEY_3", "GROQ_API_KEY_4")


def test_score_response_returns_none_when_no_groq_key(monkeypatch):
    """Groq 키가 하나도 없으면 폴백 없이 None (측정 결함)."""
    for name in me.JUDGE_KEY_NAMES:
        monkeypatch.delenv(name, raising=False)

    class Boom:
        def __init__(self, *a, **k):
            raise AssertionError("키가 없는데 클라이언트가 만들어졌다")

    monkeypatch.setitem(__import__("sys").modules, "openai",
                        type("m", (), {"OpenAI": Boom}))
    assert me.score_response("문제", "정답", "답안") is None


def test_score_response_rotates_to_next_key_on_exception(monkeypatch):
    """첫 키가 예외를 던지면 다음 키로 넘어간다 (재시도·백오프 없음)."""
    for name in me.JUDGE_KEY_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "k1")
    monkeypatch.setenv("GROQ_API_KEY_2", "k2")

    used = []

    class FakeCompletions:
        def create(self, **kw):
            used.append(kw)
            msg = type("M", (), {"content": "1"})()
            return type("R", (), {"choices": [type("C", (), {"message": msg})()]})()

    class FakeOpenAI:
        def __init__(self, api_key=None, base_url=None):
            if api_key == "k1":
                raise RuntimeError("429 rate limited")
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setitem(__import__("sys").modules, "openai",
                        type("m", (), {"OpenAI": FakeOpenAI}))
    assert me.score_response("문제", "정답", "답안") == 1
    assert len(used) == 1, "첫 키 실패 후 다음 키로 넘어가 한 번만 성공해야 한다"
    assert used[0]["model"] == me.JUDGE_MODEL
    assert used[0]["temperature"] == 0.0
    assert used[0]["max_tokens"] == 100


def test_all_groq_keys_failing_returns_none(monkeypatch):
    """전멸 시 None — 폴백 체인으로 되돌아가지 않는다."""
    for name in me.JUDGE_KEY_NAMES:
        monkeypatch.setenv(name, "k")

    class AllFail:
        def __init__(self, api_key=None, base_url=None):
            raise RuntimeError("down")

    monkeypatch.setitem(__import__("sys").modules, "openai",
                        type("m", (), {"OpenAI": AllFail}))
    assert me.score_response("문제", "정답", "답안") is None


def test_judge_never_falls_back_to_fallback_chain(monkeypatch):
    """model_router.chat_completion 을 판관이 쓰지 않는다 (grep 0건의 회귀 방지)."""
    import model_router
    calls = []
    monkeypatch.setattr(model_router, "chat_completion",
                        lambda *a, **k: calls.append(1) or "1")
    monkeypatch.setattr(me, "_judge_groq", lambda p: "1")
    me.score_response("q", "e", "a")
    assert calls == [], "폴백 체인 경로가 남아 있다"
