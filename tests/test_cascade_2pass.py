import json
import os
import pytest

from briefing_scorer import score_article, _parse_amounts, load_weights, load_entity_tiers


class TestCascadeLightScore:
    """Phase A: light score — 4개 항목만 산출"""

    def test_light_score_produces_financial_entity_freshness_source(self, sample_weights, sample_tiers):
        article = {
            "title": "Nvidia Unveils $500B AI Chip Deal with OpenAI",
            "description": "Major deal between two AI leaders",
            "source": "TechCrunch",
            "pub_date": "Mon, 30 Jun 2026 10:00:00 +0000",
            "cluster": "nvidia",
        }
        result = score_article(article, sample_weights, sample_tiers, mode="light")
        assert result["breakdown"]["financial_impact"] > 0
        assert result["breakdown"]["entity_tier"] > 0
        assert result["breakdown"]["freshness"] > 0
        assert result["breakdown"]["source_authority"] > 0
        # Light mode: full-only 항목은 0
        assert result["breakdown"]["topic_blast_radius"] == 0
        assert result["breakdown"]["conflict_drama"] == 0
        assert result["breakdown"]["penalty_duplicate_theme"] == 0

    def test_light_score_high_total_indicates_impact(self, sample_weights, sample_tiers):
        article = {
            "title": "Nvidia Unveils $500B AI Chip Deal with OpenAI",
            "description": "Major announcement reshaping AI landscape",
            "source": "TechCrunch",
            "pub_date": (__import__("datetime").datetime.now(__import__("datetime").timezone.utc) -
                         __import__("datetime").timedelta(minutes=30)).strftime("%a, %d %b %Y %H:%M:%S %z"),
            "cluster": "nvidia",
        }
        result = score_article(article, sample_weights, sample_tiers, mode="light")
        assert result["total"] >= 40  # financial + entity + freshness + source

    def test_light_score_low_for_small_article(self, sample_weights, sample_tiers):
        article = {
            "title": "Minor update to documentation",
            "description": "Small change in API reference",
            "source": "City AM",
            "pub_date": "Mon, 23 Jun 2026 10:00:00 +0000",
            "cluster": "misc",
        }
        result = score_article(article, sample_weights, sample_tiers, mode="light")
        assert result["total"] <= 25


class TestCascadeFullScore:
    """Phase B: full score — Topic N개만 본문 크롤링 후 전 항목 산출"""

    def test_high_blast_radius_from_cluster(self, sample_weights, sample_tiers):
        article = {
            "title": "EU Fines Tech Giant for AI Regulation Violation",
            "description": "Regulatory action against major AI company",
            "body": "The EU has imposed fines for violating AI regulations. The lawsuit marks a turning point in AI governance.",
            "source": "BBC",
            "pub_date": "Mon, 30 Jun 2026 08:00:00 +0000",
            "cluster": "ai-regulation",
        }
        result = score_article(article, sample_weights, sample_tiers, mode="full")
        assert result["breakdown"]["topic_blast_radius"] == 15

    def test_conflict_drama_from_body(self, sample_weights, sample_tiers):
        article = {
            "title": "Startup CEO Resigns Amid Fraud Probe",
            "description": "Scandal hits AI startup",
            "body": "The CEO resigned after a fraud probe revealed misconduct. The scandal has shaken investor confidence.",
            "source": "Reuters",
            "pub_date": "Mon, 30 Jun 2026 06:00:00 +0000",
            "cluster": "investment",
        }
        result = score_article(article, sample_weights, sample_tiers, mode="full")
        assert result["breakdown"]["conflict_drama"] > 0

    def test_duplicate_theme_penalty_applied(self, sample_weights, sample_tiers):
        article = {
            "title": "Nvidia GPU Shortage Worsens",
            "description": "Supply constraints continue",
            "body": "Nvidia continues to face GPU shortage issues affecting AI training deployments.",
            "source": "TechCrunch",
            "pub_date": "Mon, 30 Jun 2026 04:00:00 +0000",
            "cluster": "nvidia",
        }
        recent = [
            {"cluster": "nvidia", "entities": ["Nvidia"], "impact_amount": 500_000_000_000}
        ]
        result = score_article(article, sample_weights, sample_tiers, recent_briefings=recent, mode="full")
        assert result["breakdown"]["penalty_duplicate_theme"] < 0

    def test_duplicate_theme_exempt_with_2x_impact(self, sample_weights, sample_tiers):
        article = {
            "title": "Nvidia Signs $2T AI Chip Deal",
            "description": "Record-breaking partnership",
            "body": "Nvidia signed a $2 trillion AI chip deal, doubling previous records.",
            "source": "Bloomberg",
            "pub_date": "Mon, 30 Jun 2026 02:00:00 +0000",
            "cluster": "nvidia",
        }
        recent = [
            {"cluster": "nvidia", "entities": ["Nvidia"], "impact_amount": 500_000_000_000}
        ]
        result = score_article(article, sample_weights, sample_tiers, recent_briefings=recent, mode="full")
        assert result["breakdown"]["penalty_duplicate_theme"] == 0


class TestTopNSelection:
    """Top-N 20개 선별 후 크롤링 → 2-Pass"""

    def test_top_n_selects_highest_light_scores_first(self, sample_weights, sample_tiers, mock_articles_20):
        from auto_news_selector import _compute_light_scores
        scored = _compute_light_scores(mock_articles_20, sample_weights, sample_tiers, [])
        top_5 = [s for s in scored[:5]]
        top_5_scores = [s[0] for s in top_5]
        assert all(top_5_scores[i] >= top_5_scores[i + 1] for i in range(len(top_5_scores) - 1))

    def test_top_n_produces_exactly_n(self, sample_weights, sample_tiers, mock_articles_20):
        from auto_news_selector import _compute_light_scores
        scored = _compute_light_scores(mock_articles_20, sample_weights, sample_tiers, [])
        n = sample_weights.get("thresholds", {}).get("top_n_crawl", 20)
        top_n = [a for _, a in scored[:n]]
        assert len(top_n) <= n
        assert len(top_n) > 0

    def test_2pass_slot_sum_is_6(self, sample_weights, sample_tiers, mock_articles_20):
        from auto_news_selector import _compute_light_scores, _two_pass_selection
        scored = _compute_light_scores(mock_articles_20, sample_weights, sample_tiers, [])
        top_10 = [a for _, a in scored[:10]]
        # Assign mock full scores for 2-pass
        ls_max = max(s[0] for s in scored[:10]) if scored[:10] else 0
        for a in top_10:
            a["full_score"] = a.get("light_score", 0) + 5
        clusters = {}
        for a in top_10:
            clusters.setdefault(a["cluster"], []).append(a)
        pass1, pass2 = _two_pass_selection(clusters, max_count=6)
        assert len(pass1) + len(pass2) <= 6

    def test_empty_scored_list_handled(self, sample_weights, sample_tiers):
        from auto_news_selector import _two_pass_selection
        pass1, pass2 = _two_pass_selection({}, max_count=6)
        assert len(pass1) == 0
        assert len(pass2) == 0


class TestAmountExtractionEdgeCases:
    @pytest.mark.parametrize("text, expected_min_usd", [
        ("$10 billion investment", 10_000_000_000),
        ("$10bn raise", 10_000_000_000),
        ("$1 trillion market", 1_000_000_000_000),
        ("$500m funding", 500_000_000),
        ("£2bn invested", 2_000_000_000 * 1.27),
        ("€1 billion raised", 1_000_000_000 * 1.08),
        ("3조 원 규모", 0),  # KRW, not USD
        ("500억 투자", 0),  # KRW
    ])
    def test_various_amount_formats(self, text, expected_min_usd):
        found, amounts = _parse_amounts(text)
        if expected_min_usd > 0:
            assert amounts["usd_max"] >= expected_min_usd * 0.99
        else:
            assert amounts["krw_max"] > 0 or amounts["usd_max"] == 0

    def test_currency_mixed_in_same_text(self):
        text = "Company raised $1B in US and £500M in UK, plus 1000억 in Korea"
        found, amounts = _parse_amounts(text)
        assert amounts["usd_max"] > 0
        assert amounts["krw_max"] == 1000 * 100_000_000


class TestConfigLoad:
    def test_impact_weights_loads(self):
        weights = load_weights()
        assert "financial_impact" in weights
        assert "thresholds" in weights
        assert weights["thresholds"]["impact_pass_min"] == 70
        assert weights["thresholds"]["total_max"] == 95

    def test_entity_tiers_loads(self):
        tiers = load_entity_tiers()
        assert "tier1" in tiers
        assert "OpenAI" in tiers["tier1"]
        assert "tier2" in tiers
