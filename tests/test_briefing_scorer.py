import json
import pytest

from briefing_scorer import (
    score_article,
    _parse_amounts,
    _match_entity_tiers,
    _score_financial_impact,
    _score_freshness,
    _score_source_authority,
    _score_topic_blast_radius,
    _score_conflict_drama,
    _penalty_low_tier_entity,
    _penalty_duplicate_theme,
    normalize_timestamp,
)
from datetime import datetime, timezone, timedelta


class TestAmountParsing:
    def test_usd_billion(self):
        text = "Nvidia announced a $10 billion deal"
        found, amounts = _parse_amounts(text)
        assert amounts["usd_max"] == 10_000_000_000
        assert any("$10 billion" in f["raw"] for f in found)

    def test_usd_bn(self):
        text = "Deal worth $5bn"
        found, amounts = _parse_amounts(text)
        assert amounts["usd_max"] == 5_000_000_000

    def test_usd_trillion(self):
        text = "reaching $1.2 trillion market cap"
        found, amounts = _parse_amounts(text)
        assert amounts["usd_max"] == 1_200_000_000_000

    def test_usd_million(self):
        text = "raised $50 million in Series B"
        found, amounts = _parse_amounts(text)
        assert amounts["usd_max"] == 50_000_000

    def test_gbp_billion(self):
        text = "funding of £800 million raised"
        found, amounts = _parse_amounts(text)
        assert amounts["usd_max"] == 800_000_000 * 1.27

    def test_gbp_bn(self):
        text = "invested £2bn in AI"
        found, amounts = _parse_amounts(text)
        assert amounts["usd_max"] == 2_000_000_000 * 1.27

    def test_eur_million(self):
        text = "€500 million investment announced"
        found, amounts = _parse_amounts(text)
        assert amounts["usd_max"] == 500_000_000 * 1.08

    def test_krw_jo(self):
        text = "1조 원 투자 결정"
        found, amounts = _parse_amounts(text)
        assert amounts["krw_max"] == 1_000_000_000_000

    def test_krw_eok(self):
        text = "5000억 규모 펀드 조성"
        found, amounts = _parse_amounts(text)
        assert amounts["krw_max"] == 5000 * 100_000_000

    def test_multiple_amounts_picks_max(self):
        text = "$1B investment grew to $10B valuation"
        found, amounts = _parse_amounts(text)
        assert amounts["usd_max"] == 10_000_000_000

    def test_no_amount(self):
        text = "New product launch announcement"
        found, amounts = _parse_amounts(text)
        assert amounts["usd_max"] == 0
        assert amounts["krw_max"] == 0

    def test_empty_text(self):
        found, amounts = _parse_amounts("")
        assert amounts["usd_max"] == 0


class TestFinancialImpact:
    def test_over_10b(self, sample_weights):
        score = _score_financial_impact({"usd_max": 50_000_000_000, "krw_max": 0}, sample_weights)
        assert score == 25

    def test_1b_to_10b(self, sample_weights):
        score = _score_financial_impact({"usd_max": 5_000_000_000, "krw_max": 0}, sample_weights)
        assert score == 15

    def test_100m_to_1b(self, sample_weights):
        score = _score_financial_impact({"usd_max": 500_000_000, "krw_max": 0}, sample_weights)
        assert score == 8

    def test_under_100m(self, sample_weights):
        score = _score_financial_impact({"usd_max": 50_000_000, "krw_max": 0}, sample_weights)
        assert score == 0

    def test_krw_1jo_plus(self, sample_weights):
        score = _score_financial_impact({"usd_max": 0, "krw_max": 5_000_000_000_000}, sample_weights)
        assert score == 25

    def test_krw_1000eok_to_1jo(self, sample_weights):
        score = _score_financial_impact({"usd_max": 0, "krw_max": 500_000_000_000}, sample_weights)
        assert score == 15

    def test_krw_100eok_to_1000eok(self, sample_weights):
        score = _score_financial_impact({"usd_max": 0, "krw_max": 50_000_000_000}, sample_weights)
        assert score == 8

    def test_usd_wins_if_higher(self, sample_weights):
        score = _score_financial_impact({"usd_max": 10_000_000_000, "krw_max": 100_000_000_000}, sample_weights)
        assert score == 25

    def test_krw_wins_if_higher(self, sample_weights):
        score = _score_financial_impact({"usd_max": 100_000_000, "krw_max": 5_000_000_000_000}, sample_weights)
        assert score == 25


class TestEntityTier:
    def test_tier1_matches(self, sample_tiers):
        text = "OpenAI announced a new model with Nvidia partnership"
        tier, entities = _match_entity_tiers(text, sample_tiers)
        assert tier == 1
        assert "OpenAI" in entities or "Nvidia" in entities

    def test_tier2_matches(self, sample_tiers):
        text = "Mistral AI released a new language model"
        tier, entities = _match_entity_tiers(text, sample_tiers)
        assert tier == 2

    def test_tier3_default(self, sample_tiers):
        text = "A small startup raised seed funding for AI tools"
        tier, entities = _match_entity_tiers(text, sample_tiers)
        assert tier == 3
        assert entities == []

    def test_tier1_plus_tier2(self, sample_tiers):
        text = "Google partnered with Hugging Face on new project"
        tier, entities = _match_entity_tiers(text, sample_tiers)
        assert tier == 1
        assert "Google" in entities

    def test_empty_text(self, sample_tiers):
        tier, entities = _match_entity_tiers("", sample_tiers)
        assert tier == 3


class TestFreshness:
    def test_under_1h(self, sample_weights):
        dt = datetime.now(timezone.utc) - timedelta(minutes=30)
        score, hours = _score_freshness(dt, sample_weights)
        assert score == 15

    def test_under_3h(self, sample_weights):
        dt = datetime.now(timezone.utc) - timedelta(hours=2)
        score, hours = _score_freshness(dt, sample_weights)
        assert score == 10

    def test_under_6h(self, sample_weights):
        dt = datetime.now(timezone.utc) - timedelta(hours=4)
        score, hours = _score_freshness(dt, sample_weights)
        assert score == 5

    def test_over_6h(self, sample_weights):
        dt = datetime.now(timezone.utc) - timedelta(hours=10)
        score, hours = _score_freshness(dt, sample_weights)
        assert score == 0

    def test_exact_1h_edge(self, sample_weights):
        dt = datetime.now(timezone.utc) - timedelta(minutes=59)
        score, hours = _score_freshness(dt, sample_weights)
        assert score == 15

    def test_exact_3h_edge(self, sample_weights):
        dt = datetime.now(timezone.utc) - timedelta(hours=1, minutes=1)
        score, hours = _score_freshness(dt, sample_weights)
        assert score == 10

    def test_none_date(self, sample_weights):
        score, hours = _score_freshness(None, sample_weights)
        assert score == 0
        assert hours == -1


class TestSourceAuthority:
    def test_tier1_source(self, sample_weights):
        score = _score_source_authority("TechCrunch", sample_weights)
        assert score == 10

    def test_tier2_source(self, sample_weights):
        score = _score_source_authority("City AM", sample_weights)
        assert score == 5

    def test_BBC_tier1(self, sample_weights):
        score = _score_source_authority("BBC", sample_weights)
        assert score == 10

    def test_unknown_source(self, sample_weights):
        score = _score_source_authority("Unknown", sample_weights)
        assert score == 5


class TestTopicBlastRadius:
    def test_high_cluster(self, sample_weights):
        score = _score_topic_blast_radius("ai-regulation", "some text", sample_weights)
        assert score == 15

    def test_mid_cluster(self, sample_weights):
        score = _score_topic_blast_radius("product-launch", "some text", sample_weights)
        assert score == 8

    def test_low_cluster(self, sample_weights):
        score = _score_topic_blast_radius("misc", "ordinary text", sample_weights)
        assert score == 3

    def test_keyword_override(self, sample_weights):
        score = _score_topic_blast_radius("misc", "lawsuit filed today", sample_weights)
        assert score == 15


class TestConflictDrama:
    def test_match_lawsuit(self, sample_weights):
        score = _score_conflict_drama("company faces lawsuit over AI", sample_weights)
        assert score == 10

    def test_match_scandal(self, sample_weights):
        score = _score_conflict_drama("scandal erupts at AI startup", sample_weights)
        assert score == 10

    def test_no_match(self, sample_weights):
        score = _score_conflict_drama("peaceful product launch event", sample_weights)
        assert score == 0


class TestPenaltyLowTierEntity:
    def test_tier3_solo_penalty(self, sample_weights, sample_tiers):
        score = _penalty_low_tier_entity(3, "A small startup launched a product", sample_weights, sample_tiers)
        assert score == -10

    def test_tier3_with_tier1_entities_exempt(self, sample_weights, sample_tiers):
        score = _penalty_low_tier_entity(3, "Nvidia technology powers this product", sample_weights, sample_tiers)
        assert score == 0

    def test_tier1_no_penalty(self, sample_weights, sample_tiers):
        score = _penalty_low_tier_entity(1, "Google announced new features", sample_weights, sample_tiers)
        assert score == 0

    def test_tier2_no_penalty(self, sample_weights, sample_tiers):
        score = _penalty_low_tier_entity(2, "Mistral announced new features", sample_weights, sample_tiers)
        assert score == 0


class TestPenaltyDuplicateTheme:
    def test_same_cluster_entity_overlap(self, sample_weights):
        briefings = [
            {"cluster": "nvidia", "entities": ["Nvidia"], "impact_amount": 100_000_000_000}
        ]
        score = _penalty_duplicate_theme("nvidia", "Nvidia news", briefings, sample_weights, 50_000_000_000, 0)
        assert score == -15

    def test_impact_double_exempt(self, sample_weights):
        briefings = [
            {"cluster": "nvidia", "entities": ["Nvidia"], "impact_amount": 100_000_000_000}
        ]
        score = _penalty_duplicate_theme("nvidia", "Nvidia news", briefings, sample_weights, 500_000_000_000, 0)
        assert score == 0

    def test_different_cluster(self, sample_weights):
        briefings = [
            {"cluster": "nvidia", "entities": ["Nvidia"], "impact_amount": 100_000_000_000}
        ]
        score = _penalty_duplicate_theme("google", "Google news", briefings, sample_weights, 0, 0)
        assert score == 0

    def test_empty_briefings(self, sample_weights):
        score = _penalty_duplicate_theme("nvidia", "Nvidia news", [], sample_weights, 50_000_000_000, 0)
        assert score == 0


class TestScoreArticleLightMode:
    def test_light_mode_breakdown_has_4_items(self, sample_weights, sample_tiers):
        article = {
            "title": "Nvidia Unveils $500B AI Chip Deal with OpenAI",
            "description": "Major chip deal announcement",
            "source": "TechCrunch",
            "pub_date": (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%a, %d %b %Y %H:%M:%S %z"),
            "cluster": "nvidia",
        }
        result = score_article(article, sample_weights, sample_tiers, mode="light")
        assert result["mode"] == "light"
        assert result["breakdown"]["topic_blast_radius"] == 0
        assert result["breakdown"]["conflict_drama"] == 0
        assert result["breakdown"]["penalty_duplicate_theme"] == 0
        assert result["breakdown"]["financial_impact"] > 0
        assert result["breakdown"]["entity_tier"] > 0

    def test_total_cap_at_95(self, sample_weights, sample_tiers):
        article = {
            "title": "Nvidia Unveils $500B AI Chip Deal with OpenAI",
            "description": "Major chip deal announcement with huge impact",
            "source": "TechCrunch",
            "pub_date": (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime("%a, %d %b %Y %H:%M:%S %z"),
            "cluster": "nvidia",
        }
        result = score_article(article, sample_weights, sample_tiers, mode="light")
        assert result["total"] <= 95

    def test_light_mode_all_fields_present(self, sample_weights, sample_tiers):
        article = {
            "title": "Small announcement",
            "description": "Minor update",
            "source": "City AM",
            "pub_date": "2026-06-29",
            "cluster": "misc",
        }
        result = score_article(article, sample_weights, sample_tiers, mode="light")
        assert "total" in result
        assert "breakdown" in result
        assert "evidence" in result
        assert "tier_reasoning" in result
        assert "mode" in result


class TestScoreArticleFullMode:
    def test_full_mode_includes_all_7_items(self, sample_weights, sample_tiers):
        article = {
            "title": "Nvidia Unveils $500B AI Chip Deal with OpenAI",
            "description": "Major chip deal announcement",
            "body": "Nvidia announced a massive deal. lawsuit concerns raised. This is a major merger-acquisition event with huge impact.",
            "source": "TechCrunch",
            "pub_date": (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%a, %d %b %Y %H:%M:%S %z"),
            "cluster": "nvidia",
            "link": "https://example.com/1",
        }
        result = score_article(article, sample_weights, sample_tiers, recent_briefings=[], mode="full")
        assert result["mode"] == "full"
        assert result["breakdown"]["topic_blast_radius"] >= 0
        assert result["breakdown"]["conflict_drama"] >= 0
        assert result["breakdown"]["penalty_low_tier_entity"] <= 0
        assert result["breakdown"]["penalty_duplicate_theme"] <= 0

    def test_empty_body_is_crawl_failed(self, sample_weights, sample_tiers):
        article = {
            "title": "Test",
            "description": "Test desc",
            "body": "",
            "source": "City AM",
            "pub_date": "2026-06-29",
            "cluster": "misc",
        }
        result = score_article(article, sample_weights, sample_tiers, mode="full")
        assert result["evidence"]["crawl_failed"] is True

    def test_meta_only_article_no_error(self, sample_weights, sample_tiers):
        article = {
            "id": 99,
            "title": "Minimal Article",
            "source": "City AM",
        }
        result = score_article(article, sample_weights, sample_tiers, mode="light")
        assert result["total"] >= 0
        assert result["evidence"]["hours_since_publish"] == -1


class TestNormalizeTimestamp:
    def test_rfc822_format(self):
        dt = normalize_timestamp("Mon, 29 Jun 2026 15:16:00 +0000")
        assert dt is not None
        assert dt.hour == 15

    def test_iso_format(self):
        dt = normalize_timestamp("2026-06-29T15:16:00Z")
        assert dt is not None
        assert dt.year == 2026

    def test_simple_date(self):
        dt = normalize_timestamp("2026-06-29")
        assert dt is not None

    def test_invalid_string(self):
        dt = normalize_timestamp("not a date")
        assert dt is None

    def test_none(self):
        dt = normalize_timestamp(None)
        assert dt is None


class TestTierReasoning:
    def test_impact_pass_reasoning(self, sample_weights, sample_tiers):
        article = {
            "title": "Nvidia Unveils $500B AI Chip Deal with OpenAI",
            "description": "Major deal",
            "source": "TechCrunch",
            "pub_date": (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%a, %d %b %Y %H:%M:%S %z"),
            "cluster": "nvidia",
        }
        result = score_article(article, sample_weights, sample_tiers, mode="light")
        assert "tier-1" in result["tier_reasoning"]
