"""Tests for compass rotation — weighted_pick and independent rotation axes."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "threads"))

from pipeline.threads.compass import (
    INTRO_STYLES,
    INTRO_STYLE_EXAMPLES,
    INTRO_STYLE_PREFIXES,
    weighted_pick,
    _load_intro_rotation,
    _load_h2_rotation,
    _save_intro_rotation,
    _save_h2_rotation,
)

pytestmark = pytest.mark.unit


class TestWeightedPick:
    """weighted_pick must exclude recent items and distribute equally."""

    def test_excludes_recent_two(self):
        items = ["a", "b", "c", "d", "e"]
        recent = ["a", "b"]
        # Run many times — never picks a or b
        for _ in range(100):
            picked = weighted_pick(items, recent, exclude_count=2)
            assert picked not in recent, f"recent item {picked} was picked"

    def test_excludes_exact_two_from_end(self):
        items = ["a", "b", "c", "d", "e"]
        recent = ["d", "e"]
        for _ in range(100):
            picked = weighted_pick(items, recent, exclude_count=2)
            assert picked not in recent, f"recent item {picked} was picked"

    def test_all_items_pickable_when_no_recent(self):
        items = ["a", "b", "c"]
        seen = set()
        for _ in range(300):
            seen.add(weighted_pick(items, [], exclude_count=2))
        assert seen == {"a", "b", "c"}, f"not all items pickable: {seen}"

    def test_falls_back_when_all_recent(self):
        items = ["a", "b"]
        recent = ["a", "b"]
        # With 2 items and exclude_count=2, falls back to random from all
        seen = set()
        for _ in range(100):
            seen.add(weighted_pick(items, recent, exclude_count=2))
        assert len(seen) >= 1

    def test_single_item_list(self):
        result = weighted_pick(["only"], [], exclude_count=2)
        assert result == "only"

    def test_empty_items_raises(self):
        with pytest.raises(ValueError):
            weighted_pick([], [], exclude_count=2)


class TestRotationIndependence:
    """intro_style and h2_flow use independent counters."""

    def test_intro_styles_count(self):
        assert len(INTRO_STYLES) >= 8, (
            f"8개 이상 intro_style 패턴 필요, got {len(INTRO_STYLES)}"
        )

    def test_all_styles_have_examples(self):
        from pipeline.threads.compass import INTRO_STYLE_EXAMPLES, INTRO_STYLE_PREFIXES
        for style in INTRO_STYLES:
            assert style in INTRO_STYLE_EXAMPLES, f"예시 누락: {style}"
            assert INTRO_STYLE_EXAMPLES[style], f"빈 예시: {style}"
            assert style in INTRO_STYLE_PREFIXES, f"프리픽스 누락: {style}"
            assert INTRO_STYLE_PREFIXES[style], f"빈 프리픽스: {style}"

    def test_no_consecutive_intro_style_repeat(self):
        """weighted_pick with exclude_count=2 prevents immediate repeats."""
        items = list(range(5))
        recent = []
        last = None
        repeats = 0
        for i in range(100):
            picked = weighted_pick(items, recent[-2:], exclude_count=2)
            if picked == last:
                repeats += 1
            recent.append(picked)
            last = picked
        assert repeats == 0, f"연속 반복 {repeats}회 발생"


class TestRotationPersistence:
    """Rotation counters persist in posted.json."""

    def test_save_and_load_intro_rotation(self, monkeypatch, tmp_path):
        import os
        import pipeline.threads.compass as compass_mod

        test_json = tmp_path / "posted.json"
        test_json.write_text("{}")
        monkeypatch.setattr(compass_mod, "_POSTED_JSON_PATH", str(test_json))

        _save_intro_rotation(3)
        result = _load_intro_rotation()
        assert result == 3

    def test_save_and_load_h2_rotation(self, monkeypatch, tmp_path):
        import pipeline.threads.compass as compass_mod

        test_json = tmp_path / "posted.json"
        test_json.write_text("{}")
        monkeypatch.setattr(compass_mod, "_POSTED_JSON_PATH", str(test_json))

        _save_h2_rotation(7)
        result = _load_h2_rotation()
        assert result == 7

    def test_default_rotation_zero(self, monkeypatch, tmp_path):
        import pipeline.threads.compass as compass_mod

        test_json = tmp_path / "posted.json"
        test_json.write_text("{}")
        monkeypatch.setattr(compass_mod, "_POSTED_JSON_PATH", str(test_json))

        assert _load_intro_rotation() == 0
        assert _load_h2_rotation() == 0


class TestIntroStylePatterns:
    """All intro_style patterns produce valid rotation."""

    def test_all_patterns_in_rotation_list(self):
        """Every pattern in INTRO_STYLE_EXAMPLES must be in INTRO_STYLES."""
        for style in INTRO_STYLE_EXAMPLES:
            assert style in INTRO_STYLES, f"INTRO_STYLE_EXAMPLES에 있는 패턴이 INTRO_STYLES에 없음: {style}"
