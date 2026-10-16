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
