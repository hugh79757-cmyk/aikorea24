"""EVAL-CLI-01: CLI 경유 평가 회귀 테스트.

범위를 좁게 유지한다 — 정책(어떤 점수를 남기고 어떤 점수를 남기지 않는가)만 고정.
"""
import sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import model_eval as me


def test_cli_model_map_excludes_unregistered():
    # jev-1.13-free 는 CLI 미등록 — 넣으면 파이프라인이 존재하지 않는 모델을 부른다.
    assert "jev-1.13-free" not in me.CLI_MODEL_MAP
    assert me.CLI_MODEL_MAP["cat-jam-free"] == "opencode/cat-jam-free"


def test_cli_prompt_includes_seed_turns():
    plain = me.cli_prompt({"q": "몇 개?"})
    assert plain == "몇 개?"

    multi = me.cli_prompt({
        "q": "그다음은?",
        "seed": [{"role": "user", "content": "1부터 세"}, {"role": "assistant", "content": "하나 둘 셋"}],
    })
    assert "1부터 세" in multi and "하나 둘 셋" in multi
    assert multi.rstrip().endswith("그다음은?")  # 실제 질문이 마지막에 와야 한다


def test_cli_call_parses_ndjson_text(monkeypatch):
    class R:
        stdout = ('{"type":"step_start","part":{}}\n'
                  '{"type":"text","part":{"text":"정답은 "}}\n'
                  '{"type":"text","part":{"text":"7392 입니다."}}\n')
    monkeypatch.setattr(me.subprocess, "run", lambda *a, **k: R())
    assert me.cli_call("opencode/x", "hi") == ("정답은 7392 입니다.", "")


def test_cli_call_returns_reason_on_error(monkeypatch):
    class R:
        stdout = '{"type":"error","error":{"message":"Model unavailable"}}'
    monkeypatch.setattr(me.subprocess, "run", lambda *a, **k: R())
    assert me.cli_call("opencode/x", "hi") == ("", "Model unavailable")


def test_cli_call_handles_timeout(monkeypatch):
    def boom(*a, **k):
        raise me.subprocess.TimeoutExpired(cmd="opencode", timeout=60)
    monkeypatch.setattr(me.subprocess, "run", boom)
    text, err = me.cli_call("opencode/x", "hi")
    assert text == "" and "타임아웃" in err


def test_eval_model_cli_unregistered_model_is_blocked_not_zero():
    result, blocked = me.eval_model_cli("jev-1.13-free")
    assert blocked  # 점수 0을 남기지 말고 대기 사유를 돌려준다
    assert result["score"] == 0 and result["details"] == []


def test_eval_model_cli_blocked_on_unreachable_model(monkeypatch):
    """첫 문항에서 CLI 가 죽으면 즉시 중단 — 나머지 11문항을 0으로 채우지 않는다."""
    monkeypatch.setattr(me, "cli_call", lambda *a, **k: ("", "Model unavailable"))
    result, blocked = me.eval_model_cli("cat-jam-free")
    assert blocked == "Model unavailable"
    assert result["score"] == 0 and result["details"] == []


def test_eval_model_cli_result_shape(monkeypatch):
    monkeypatch.setattr(me, "score_response", lambda q, e, a: 1)
    monkeypatch.setattr(me, "cli_call", lambda *a, **k: ("42", ""))
    monkeypatch.setattr(me.time, "sleep", lambda *_: None)
    result, blocked = me.eval_model_cli("cat-jam-free")
    assert blocked is None
    assert result["source"] == "cli" and result["provider"] == "zen"
    assert result["token_usage"] == {"prompt": 0, "completion": 0}
    assert result["max_score"] == len(me.TEST_QUESTIONS)
    assert all(d["source"] == "cli" for d in result["details"])


def test_eval_model_cli_retries_timeout_once(monkeypatch):
    """EVAL-LLALPHA-01: 60초 타임아웃은 모델 부재가 아니다 — 180초로 1회 재시도한 뒤 결과를 쓴다."""
    seen = []

    def fake(cli_model, prompt, timeout=me.QUESTION_TIMEOUT):
        seen.append(timeout)
        return ("", "CLI 타임아웃 60초") if len(seen) == 1 else ("정답", "")

    monkeypatch.setattr(me, "cli_call", fake)
    monkeypatch.setattr(me, "score_response", lambda q, e, a: 1)
    # AGENT-EVAL-01: 문항 3개가 샌드박스 채점으로 바뀌었으므로, 이 테스트의 목적(타임아웃 재시도)
    # 을 흐리지 않도록 샌드박스만 통과로 스텁한다. 본 테스트는 채점 방식이 아니라 재시도 계약이다.
    monkeypatch.setattr(me, "sandbox_grade", lambda spec, ans: (1, "stub"))
    monkeypatch.setattr(me.time, "sleep", lambda *_: None)
    result, blocked = me.eval_model_cli("cat-jam-free")
    assert blocked is None                       # 재시도가 성공했으므로 차단하지 않는다
    assert seen[0] == me.QUESTION_TIMEOUT
    assert seen[1] == me.CLI_RETRY_TIMEOUT       # 1번 문항만 재시도 — 나머지는 1회 호출
    assert len(seen) == len(me.TEST_QUESTIONS) + 1
    assert result["score"] == len(me.TEST_QUESTIONS)


def test_probe_doc_puts_secret_first():
    doc = me._probe_doc(4096)
    assert me.PROBE_SECRET in doc[:200]
    assert len(doc) >= 4096


def test_probe_context_length_respects_cache(monkeypatch):
    """모델당 1회 규칙 — 캐시에 있으면 프로브를 아예 돌리지 않는다."""
    calls = []
    monkeypatch.setattr(me, "_probe_hit", lambda *a, **k: calls.append(a) or ("", ""))
    cache = {"m": {"measured_context": 12345}}
    assert me.probe_context_length("m", cache=cache) == 12345
    assert calls == []


def test_probe_context_length_stops_at_first_failure(monkeypatch):
    hits = {"n": 0}

    def fake(model_id, cli_model, target):
        hits["n"] += 1
        return ("7392", "") if target <= 16384 else ("잘못됨", "")

    monkeypatch.setattr(me, "_probe_hit", fake)
    monkeypatch.setattr(me.time, "sleep", lambda *_: None)
    monkeypatch.setattr(me, "PROBE_STEPS", (8192, 16384, 32768))
    got = me.probe_context_length("m", cache={})
    assert 8192 <= got <= 16384
    assert hits["n"] >= 2  # 상한을 넘어서 실패 지점까지는 반드시 시도한다
