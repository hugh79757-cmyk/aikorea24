"""tests/test_zen_pending_hygiene.py

2026-10-18 회귀 테스트 — zen_pending 원장 위생.

사고 실측: cat-jam-free 가 10-14 사유("OpenRouter 경로 없음 · 호출 경로 미확보")로
원장에 남았지만 실제 상태는 "Model unavailable → Zen 무료 목록에서 제외"였다.
원인 2가지:
  1. mark_zen_pending 이 `mid in d` 면 무조건 돌아가 첫 사유가 영구히 박혔다.
  2. 목록에서 사라진 모델의 항목을 걷어내는 경로가 없었다.

계약:
  · 같은 사유면 쓰지 않는다(불필요한 쓰기 방지).
  · 사유가 바뀌면 날짜와 함께 갱신한다.
  · 최신 카탈로그에 없는 모델은 잔재로 판정한다.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import free_models_page as fmp  # noqa: E402
import prune_zen_pending as pz  # noqa: E402


# ---------------------------------------------------------- mark_zen_pending

def _capture_write(monkeypatch, current):
    written = {}
    monkeypatch.setattr(fmp, "zen_pending", lambda: dict(current))
    monkeypatch.setattr(fmp.mc, "_write_json", lambda path, data: written.update(data))
    return written


def test_same_reason_is_not_rewritten(monkeypatch):
    written = _capture_write(monkeypatch, {"m-free": {"reason": "CLI 대상 미등록", "ts": "2026-10-14"}})
    fmp.mark_zen_pending("m-free", "CLI 대상 미등록")

    assert written == {}, written


def test_changed_reason_is_refreshed(monkeypatch):
    """10-14 사유가 실제 상태(Model unavailable)로 바뀌면 원장도 바뀌어야 한다."""
    written = _capture_write(monkeypatch, {"m-free": {"reason": "OpenRouter 경로 없음 · 호출 경로 미확보",
                                                     "ts": "2026-10-14"}})
    monkeypatch.setattr(fmp.mc.time, "strftime", lambda fmt: "2026-10-18")
    fmp.mark_zen_pending("m-free", "Model unavailable: opencode/m-free")

    assert written["m-free"]["reason"] == "Model unavailable: opencode/m-free"
    assert written["m-free"]["ts"] == "2026-10-18"


def test_new_entry_is_recorded(monkeypatch):
    written = _capture_write(monkeypatch, {})
    monkeypatch.setattr(fmp.mc.time, "strftime", lambda fmt: "2026-10-18")
    fmp.mark_zen_pending("new-free", "CLI 대상 미등록")

    assert written == {"new-free": {"reason": "CLI 대상 미등록", "ts": "2026-10-18"}}


# ---------------------------------------------------------- prune (잔재)

def test_stale_entries_picks_models_absent_from_catalog():
    pending = {"gone-free": {"reason": "x"}, "alive-free": {"reason": "y"}}
    assert pz.stale_entries(pending, {"alive-free"}) == ["gone-free"]


def test_stale_entries_without_catalog_is_empty():
    """판정 근거가 없으면 아무것도 지우지 않는다 (fail-safe)."""
    assert pz.stale_entries({"a": {}}, None) == []
    assert pz.stale_entries({"a": {}}, set()) == []


def test_stale_entries_tolerates_bad_shape():
    assert pz.stale_entries(None, {"a"}) == []
    assert pz.stale_entries(["a"], {"a"}) == []


def test_catalog_ids_reads_snapshot(tmp_path, monkeypatch):
    p = tmp_path / "snap.json"
    p.write_text('[{"model_id": "a-free"}, {"model_id": "b-free"}, {}]', encoding="utf-8")
    monkeypatch.setattr(pz.mc, "snapshot_path", lambda day: str(p))

    assert pz.catalog_ids("2026-10-18") == {"a-free", "b-free"}


def test_catalog_ids_missing_snapshot_is_none(tmp_path, monkeypatch):
    """스냅샷이 없으면 None — 호출자가 '판정 불가'로 읽는다(삭제 금지)."""
    monkeypatch.setattr(pz.mc, "snapshot_path", lambda day: str(tmp_path / "nope.json"))

    assert pz.catalog_ids("2026-10-18") is None
