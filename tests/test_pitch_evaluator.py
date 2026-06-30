"""Tests for pipeline.threads.pitch_evaluator."""
import pytest
import sys
from pathlib import Path

_scripts = str(Path(__file__).resolve().parent.parent / "scripts")
_threads = str(Path(__file__).resolve().parent.parent / "scripts" / "threads")
if _threads not in sys.path:
    sys.path.insert(0, _threads)
if _scripts not in sys.path:
    sys.path.insert(0, _scripts)

from pipeline.threads.pitch_evaluator import evaluate_pitch, filter_pitches


class TestEvaluatePitch:
    @pytest.mark.unit
    def test_passes_quality_gate(self, monkeypatch):
        from v3 import model_router
        def mock_chat(*args, **kwargs):
            return '{"score": 4, "passed": true, "direction_ok": true, "reason": "좋은 충돌"}'
        monkeypatch.setattr(model_router, "chat_completion", mock_chat)
        pitch = {"hook": "Nvidia가 OpenAI에 500억달러 AI 칩 계약", "narrative": "Test narrative", "article_ids": [1]}
        passed, score, reason = evaluate_pitch(pitch)
        assert passed is True
        assert score >= 3

    @pytest.mark.unit
    def test_fails_direction_mismatch(self, monkeypatch):
        from v3 import model_router
        def mock_chat(*args, **kwargs):
            return '{"score": 4, "passed": true, "direction_ok": false, "reason": "방향 불일치"}'
        monkeypatch.setattr(model_router, "chat_completion", mock_chat)
        pitch = {"hook": "Test hook", "narrative": "Test", "article_ids": [1]}
        passed, score, reason = evaluate_pitch(pitch)
        assert passed is False
        assert "방향" in reason

    @pytest.mark.unit
    def test_fallback_short_hook(self):
        pitch = {"hook": "AB", "narrative": "Test", "article_ids": [1]}
        passed, score, reason = evaluate_pitch(pitch)
        assert passed is False


class TestFilterPitches:
    @pytest.mark.unit
    def test_returns_first_valid(self, monkeypatch):
        from pipeline.threads import pitch_evaluator
        original = pitch_evaluator.evaluate_pitch
        call_count = [0]
        def mock_eval(pitch):
            call_count[0] += 1
            if call_count[0] == 2:
                return True, 4, "good"
            return False, 2, "bad"
        monkeypatch.setattr(pitch_evaluator, "evaluate_pitch", mock_eval)
        pitches = [
            {"hook": "Bad one", "article_ids": [1]},
            {"hook": "Good one", "article_ids": [2]},
            {"hook": "Also good", "article_ids": [3]},
        ]
        result = filter_pitches(pitches)
        assert result is not None
        assert result["hook"] == "Good one"

    @pytest.mark.unit
    def test_returns_none_when_all_fail(self, monkeypatch):
        from pipeline.threads import pitch_evaluator
        def mock_eval(pitch):
            return False, 0, "bad"
        monkeypatch.setattr(pitch_evaluator, "evaluate_pitch", mock_eval)
        pitches = [
            {"hook": "Bad one", "article_ids": [1]},
            {"hook": "Also bad", "article_ids": [2]},
        ]
        result = filter_pitches(pitches)
        assert result is None
