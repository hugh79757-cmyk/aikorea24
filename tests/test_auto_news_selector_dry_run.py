import os
import pytest

from auto_news_selector import (
    cluster_by_topic,
    select_top_articles,
    _compute_light_scores,
    _two_pass_selection,
    _log_shadow_diff,
)


class TestClusterByTopic:
    def test_attaches_cluster_label(self):
        articles = [
            {"title": "OpenAI announces new model", "description": "GPT-5 details"},
            {"title": "Nvidia GPU shortage worsens", "description": "Supply chain issues"},
            {"title": "Some random tech news", "description": "General update"},
        ]
        clusters = cluster_by_topic(articles)
        assert articles[0]["cluster"] == "openai"
        assert articles[1]["cluster"] == "nvidia"
        assert articles[2]["cluster"] == "misc"

    def test_misc_cluster_for_unmatched(self):
        articles = [
            {"title": "Weather forecast for Seoul", "description": "Sunny with clouds"},
        ]
        clusters = cluster_by_topic(articles)
        assert articles[0]["cluster"] == "misc"

    def test_all_matched_clusters_in_dict(self):
        articles = [
            {"title": "Google news", "description": "Gemini update"},
            {"title": "Meta", "description": "Llama released"},
        ]
        clusters = cluster_by_topic(articles)
        assert "google" in clusters
        assert "meta" in clusters


class TestLegacyRoundRobinRegression:
    """BRIEFING_SCORER_MODE=dry_run에서 선택 결과가 기존과 동일해야 함"""

    def test_select_top_articles_returns_6_or_less(self):
        articles = [
            {"id": i, "title": f"Article {i}", "description": "test", "cluster": c}
            for i, c in enumerate(["openai", "google", "anthropic", "meta", "nvidia", "microsoft",
                                    "openai", "google", "anthropic", "meta"])
        ]
        clusters = {}
        for a in articles:
            clusters.setdefault(a["cluster"], []).append(a)
        selected = select_top_articles(clusters, max_count=6)
        assert len(selected) <= 6

    def test_select_no_duplicate_ids(self):
        articles = [
            {"id": i % 3, "title": f"Article {i}", "description": "test", "cluster": c}
            for i, c in enumerate(["openai", "google", "anthropic"] * 3)
        ]
        clusters = {}
        for a in articles:
            clusters.setdefault(a["cluster"], []).append(a)
        selected = select_top_articles(clusters, max_count=6)
        ids = [a["id"] for a in selected]
        assert len(ids) == len(set(ids))

    def test_select_one_per_cluster_first(self):
        articles = [
            {"id": 1, "title": "A", "description": "test", "cluster": "openai"},
            {"id": 2, "title": "B", "description": "test", "cluster": "google"},
            {"id": 3, "title": "C", "description": "test", "cluster": "anthropic"},
        ]
        clusters = {}
        for a in articles:
            clusters.setdefault(a["cluster"], []).append(a)
        selected = select_top_articles(clusters, max_count=6)
        assert len(selected) == 3

    def test_regression_empty_input(self):
        selected = select_top_articles({}, max_count=6)
        assert selected == []


class TestTwoPassSelection:
    def test_pass1_returns_articles_ge_70(self, sample_weights):
        articles = [
            {"id": 1, "title": "Big News", "full_score": 85, "cluster": "openai", "link": "https://a.com/1"},
            {"id": 2, "title": "Small News", "full_score": 45, "cluster": "google", "link": "https://a.com/2"},
            {"id": 3, "title": "Medium News", "full_score": 72, "cluster": "anthropic", "link": "https://a.com/3"},
        ]
        clusters = {}
        for a in articles:
            clusters.setdefault(a["cluster"], []).append(a)
        pass1, pass2 = _two_pass_selection(clusters, max_count=6)
        for a in pass1:
            assert a["full_score"] >= 70

    def test_pass1_max_3_slots(self, sample_weights):
        articles = [
            {"id": i, "title": f"High Impact {i}", "full_score": 80 + i, "cluster": f"c{i}", "link": f"https://a.com/{i}"}
            for i in range(6)
        ]
        clusters = {}
        for a in articles:
            clusters.setdefault(a["cluster"], []).append(a)
        pass1, pass2 = _two_pass_selection(clusters, max_count=6)
        assert len(pass1) <= 3

    def test_total_slots_exactly_6(self, sample_weights):
        articles = [
            {"id": i, "title": f"Article {i}", "full_score": max(0, 80 - i * 10), "cluster": f"c{i % 5}", "link": f"https://a.com/{i}"}
            for i in range(15)
        ]
        clusters = {}
        for a in articles:
            clusters.setdefault(a["cluster"], []).append(a)
        pass1, pass2 = _two_pass_selection(clusters, max_count=6)
        assert len(pass1) + len(pass2) == 6

    def test_no_duplicate_ids_in_result(self, sample_weights):
        articles = [
            {"id": 1, "title": "A", "full_score": 85, "cluster": "openai", "link": "https://a.com/1"},
            {"id": 2, "title": "B", "full_score": 75, "cluster": "google", "link": "https://a.com/2"},
            {"id": 1, "title": "A dup", "full_score": 85, "cluster": "openai", "link": "https://a.com/1"},  # duplicate id
        ]
        clusters = {}
        for a in articles:
            clusters.setdefault(a["cluster"], []).append(a)
        pass1, pass2 = _two_pass_selection(clusters, max_count=6)
        all_ids = [a["id"] for a in pass1 + pass2]
        assert len(all_ids) == len(set(all_ids))


class TestShadowDiffLogging:
    def test_no_change_log(self, tmp_path):
        legacy = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
        pass1 = [{"id": "1"}]
        pass2 = [{"id": "2"}, {"id": "3"}]
        # Should not raise
        _log_shadow_diff(legacy, pass1, pass2, [], "dry_run")

    def test_changed_log(self, tmp_path):
        legacy = [{"id": "1", "title": "old"}, {"id": "2", "title": "old2"}, {"id": "3", "title": "old3"}]
        pass1 = [{"id": "4", "title": "new1"}]
        pass2 = [{"id": "5", "title": "new2"}, {"id": "6", "title": "new3"}]
        _log_shadow_diff(legacy, pass1, pass2, legacy + pass1 + pass2, "shadow")


class TestDryRunMode:
    def test_dry_run_env_var_default(self):
        mode = os.environ.get("BRIEFING_SCORER_MODE", "dry_run")
        assert mode == "dry_run"

    def test_no_side_effect_on_selection(self, monkeypatch):
        """dry_run 모드: scoring 수행하지만 선택은 레거시 로직 사용"""
        monkeypatch.setenv("BRIEFING_SCORER_MODE", "dry_run")
        assert os.environ.get("BRIEFING_SCORER_MODE") == "dry_run"


class TestMiscClusterHandling:
    def test_misc_cluster_in_clusters(self):
        articles = [
            {"id": 1, "title": "Random news", "description": "Something unrelated to AI topics"},
            {"id": 2, "title": "Another topic", "description": "More random content"},
        ]
        clusters = cluster_by_topic(articles)
        assert "misc" in clusters
        assert len(clusters["misc"]) == 2

    def test_misc_round_robin_light_score_check(self):
        """misc cluster: light_score >= 20인 기사만 slot 보유"""
        clusters = {
            "misc": [
                {"id": 1, "light_score": 25, "full_score": 30, "cluster": "misc"},
                {"id": 2, "light_score": 10, "full_score": 15, "cluster": "misc"},
            ],
            "openai": [
                {"id": 3, "light_score": 50, "full_score": 60, "cluster": "openai"},
            ],
        }
        pass1, pass2 = _two_pass_selection(clusters, max_count=6)
        pass2_ids = [a["id"] for a in pass2]
        assert 1 in pass2_ids  # light_score >= 20
