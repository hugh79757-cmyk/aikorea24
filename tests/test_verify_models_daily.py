"""AIK24-EVAL-07 후속 — 일일 호출 검증의 FAIL 분류 테스트 (2026-10-16).

배경(실측 사고): 16:17 검증에서 nemotron 4종이 60초 타임아웃으로 FAIL 처리되어
free_models_cli.json 에서 **영구 삭제**됐다. 재수집 경로가 없어 다음 날까지
목록에서 빠져 있었다. 반대로 step-5-preview-free 처럼 실제로 제공이 중단된
모델은 목록에서 빠져야 한다(점검 중 표기).

규칙:
  - 제공 중단 사유(Model unavailable·404·401·403 등) → 캐시에서 제거
  - 일시 실패(타임아웃·빈 응답) → free_models_pending.json 에 남겨 다음 실행에서 재검증
  - 분류 불가 → 일시 실패로 취급(지우지 않는다)
"""
import json
import os
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, "scripts"))
sys.path.insert(0, PROJECT_DIR)

import verify_models_daily as vmd  # noqa: E402

DEAD_REASON = "Model unavailable: opencode/step-5-preview-free"
TIMEOUT_REASON = "CLI 타임아웃 60초"


def _entry(cli_id):
    return {"model_id": cli_id.split("/")[-1], "provider": cli_id.split("/")[0], "cli_id": cli_id}


def test_classify_fail_dead_markers():
    assert vmd.classify_fail(DEAD_REASON) == "dead"
    assert vmd.classify_fail("HTTP 404 Not Found") == "dead"
    assert vmd.classify_fail("model_not_found") == "dead"


def test_classify_fail_transient_and_unknown_keeps_model():
    assert vmd.classify_fail(TIMEOUT_REASON) == "transient"
    assert vmd.classify_fail("429 Too Many Requests") == "transient"
    assert vmd.classify_fail("") == "transient"  # 모르면 살려 둔다


def test_merge_candidates_adds_pending_and_dedups():
    cache = [_entry("kilo/a:free"), _entry("kilo/b:free")]
    pending = [_entry("kilo/b:free"), _entry("kilo/c:free")]
    merged = vmd.merge_candidates(cache, pending)
    assert [e["cli_id"] for e in merged] == ["kilo/a:free", "kilo/b:free", "kilo/c:free"]
    # 캐시 우선(중복 제거) — pending 쪽 사본이 캐시 항목을 덮지 않는다
    assert merged[1] is cache[1]


def test_merge_candidates_ignores_garbage():
    assert vmd.merge_candidates([{"cli_id": "kilo/a:free"}, "x", {}], None) == [{"cli_id": "kilo/a:free"}]


def test_split_results_three_way():
    a, b, c = _entry("kilo/a:free"), _entry("kilo/b:free"), _entry("opencode/dead-free")
    passed, dead, pending = vmd.split_results(
        [(a, True, "PONG"), (b, False, TIMEOUT_REASON), (c, False, DEAD_REASON)]
    )
    assert [e["cli_id"] for e in passed] == ["kilo/a:free"]
    assert [e["cli_id"] for e, _ in dead] == ["opencode/dead-free"]
    assert [e["cli_id"] for e, _ in pending] == ["kilo/b:free"]
    assert dead[0][1] == DEAD_REASON


def test_main_keeps_transient_fail_in_pending_and_drops_dead(tmp_path, monkeypatch):
    """main() 통합: PASS만 캐시, 일시 실패는 대기 목록, 제공 중단은 사라진다."""
    cli_json = tmp_path / "free_models_cli.json"
    pending_json = tmp_path / "free_models_pending.json"
    verify_json = tmp_path / "free_models_verify.json"
    cli_json.write_text(json.dumps([_entry("kilo/a:free"), _entry("kilo/dead:free")]), encoding="utf-8")
    # 지난 실행에서 타임아웃으로 빠져 있던 모델 — 이번에 복구되면 캐시로 돌아온다
    pending_json.write_text(json.dumps([_entry("kilo/revived:free")]), encoding="utf-8")

    def fake_verify(entry, timeout):
        cli_id = entry["cli_id"]
        if cli_id == "kilo/a:free":
            return entry, True, "PONG"
        if cli_id == "kilo/revived:free":
            return entry, True, "PONG"           # 복구됨 → 캐시 복귀
        return entry, False, DEAD_REASON         # 제공 중단 → 캐시에서 제거

    monkeypatch.setattr(vmd, "verify_one", fake_verify)
    monkeypatch.setattr(vmd, "PENDING_PATH", pending_json)
    monkeypatch.setattr(vmd, "VERIFY_PATH", verify_json)
    monkeypatch.setattr(sys, "argv", [
        "verify_models_daily.py", "--cli-json", str(cli_json), "--out", str(cli_json),
        "--pending", str(pending_json), "--verify-out", str(verify_json),
    ])

    rc = vmd.main()
    assert rc == 0
    assert sorted(e["cli_id"] for e in json.loads(cli_json.read_text(encoding="utf-8"))) == [
        "kilo/a:free", "kilo/revived:free"]
    assert json.loads(pending_json.read_text(encoding="utf-8")) == []
    verify = json.loads(verify_json.read_text(encoding="utf-8"))
    assert verify["pass"] == ["kilo/a:free", "kilo/revived:free"]
    assert verify["fail"][0]["kind"] == "dead"


def test_main_moves_timeout_fail_to_pending(tmp_path, monkeypatch):
    cli_json = tmp_path / "free_models_cli.json"
    pending_json = tmp_path / "free_models_pending.json"
    verify_json = tmp_path / "free_models_verify.json"
    cli_json.write_text(json.dumps([_entry("kilo/slow:free")]), encoding="utf-8")

    monkeypatch.setattr(vmd, "verify_one", lambda e, t: (e, False, TIMEOUT_REASON))
    monkeypatch.setattr(vmd, "PENDING_PATH", pending_json)
    monkeypatch.setattr(vmd, "VERIFY_PATH", verify_json)
    monkeypatch.setattr(sys, "argv", [
        "verify_models_daily.py", "--cli-json", str(cli_json), "--out", str(cli_json),
        "--pending", str(pending_json), "--verify-out", str(verify_json),
    ])

    assert vmd.main() == 0
    assert json.loads(cli_json.read_text(encoding="utf-8")) == []
    pending = json.loads(pending_json.read_text(encoding="utf-8"))
    assert [e["cli_id"] for e in pending] == ["kilo/slow:free"]
    assert json.loads(verify_json.read_text(encoding="utf-8"))["fail"][0]["kind"] == "transient"
