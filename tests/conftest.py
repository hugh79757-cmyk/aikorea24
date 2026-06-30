import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_weights():
    return {
        "financial_impact": {
            "usd": {"10B_plus": 25, "1B_10B": 15, "100M_1B": 8, "lt_100M": 0},
            "krw": {"1조_plus": 25, "1000억_1조": 15, "100억_1000억": 8, "lt_100억": 0},
        },
        "entity_tier": {"weight": 20, "tier1": 20, "tier2": 10, "tier3": 0},
        "freshness": {"weight": 15, "lt_1h": 15, "lt_3h": 10, "lt_6h": 5, "gt_6h": 0},
        "source_authority": {
            "weight": 10,
            "tier1_sources": ["BBC", "Reuters", "Bloomberg", "TechCrunch"],
            "tier1_score": 10,
            "tier2_score": 5,
        },
        "topic_blast_radius": {
            "weight": 15,
            "high": ["ai-regulation", "safety-incident", "merger-acquisition", "lawsuit"],
            "high_score": 15,
            "mid": ["product-launch", "funding-round"],
            "mid_score": 8,
            "low_score": 3,
        },
        "conflict_drama": {
            "weight": 10,
            "keywords": ["lawsuit", "resign", "fired", "scandal", "fraud", "probe"],
            "score": 10,
        },
        "penalties": {
            "low_tier_entity_solo": -10,
            "duplicate_theme_7d": -15,
        },
        "thresholds": {
            "light_score_min_misc_slot": 20,
            "impact_pass_min": 70,
            "impact_pass_max_slots": 3,
            "top_n_crawl": 20,
            "total_max": 95,
        },
        "crawl_concurrency": 1,
        "fx_gbp_to_usd": 1.27,
        "fx_eur_to_usd": 1.08,
    }


@pytest.fixture
def sample_tiers():
    return {
        "tier1": ["OpenAI", "Google", "Anthropic", "Nvidia", "Meta", "Microsoft", "Apple", "Amazon", "DeepMind", "xAI"],
        "tier2": ["Mistral", "Cohere", "Stability AI", "Hugging Face", "Adobe", "Samsung", "Tesla", "Oracle", "IBM"],
        "tier3_marker": "default",
    }


@pytest.fixture
def mock_articles_20():
    path = FIXTURES_DIR / "articles_20.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return _default_articles_20()


@pytest.fixture
def mock_recent_briefings():
    path = FIXTURES_DIR / "recent_briefings_7d.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


def _default_articles_20():
    """Fallback: 20 default articles if fixture file doesn't exist"""
    now = "2026-06-30 12:00:00"
    articles = []
    templates = [
        {"id": 1, "title": "Nvidia Unveils $500B AI Chip Deal with OpenAI", "source": "TechCrunch", "cluster": "nvidia", "amount": 500_000_000_000},
        {"id": 2, "title": "Google DeepMind Announces Gemini 3 Breakthrough", "source": "BBC", "cluster": "google", "amount": 0},
        {"id": 3, "title": "Anthropic Raises $10B for Claude Development", "source": "Bloomberg", "cluster": "anthropic", "amount": 10_000_000_000},
        {"id": 4, "title": "Microsoft Layoffs 15,000 Employees in Reorganization", "source": "Reuters", "cluster": "microsoft", "amount": 0},
        {"id": 5, "title": "EU Proposes New AI Regulation Framework", "source": "BBC", "cluster": "ai-regulation", "amount": 0},
        {"id": 6, "title": "Meta Releases Open Source LLM Benchmark", "source": "TechCrunch", "cluster": "meta", "amount": 0},
        {"id": 7, "title": "Startup Raises £800M for AI Drug Discovery", "source": "City AM", "cluster": "investment", "amount": 800_000_000},
        {"id": 8, "title": "Tesla Autopilot Lawsuit: $50M Settlement Reached", "source": "Reuters", "cluster": "lawsuit", "amount": 50_000_000},
        {"id": 9, "title": "Samsung Developing AI Memory Chips with HBM4E", "source": "City AM", "cluster": "nvidia", "amount": 0},
        {"id": 10, "title": "Hugging Face Launches New Dataset Platform", "source": "TechCrunch", "cluster": "opensource", "amount": 0},
        {"id": 11, "title": "SEC Probes AI Fraud Startup Claims", "source": "Bloomberg", "cluster": "ai-regulation", "amount": 0},
        {"id": 12, "title": "Oracle Reports $5B AI Cloud Revenue Growth", "source": "City AM", "cluster": "investment", "amount": 5_000_000_000},
        {"id": 13, "title": "Apple Acquires AI Vision Startup for $200M", "source": "Bloomberg", "cluster": "merger-acquisition", "amount": 200_000_000},
        {"id": 14, "title": "Adobe Integrates Firefly into Creative Suite", "source": "TechCrunch", "cluster": "product-launch", "amount": 0},
        {"id": 15, "title": "Mistral AI Releases New Language Model", "source": "BBC", "cluster": "opensource", "amount": 0},
        {"id": 16, "title": "India's UPI Crosses 10B Monthly Transactions with AI", "source": "Reuters", "cluster": "misc", "amount": 0},
        {"id": 17, "title": "California Sues Gas Stations for AI Price Fixing", "source": "BBC", "cluster": "ai-regulation", "amount": 0},
        {"id": 18, "title": "SpaceX Valuation Tops Amazon at $1.2T", "source": "Bloomberg", "cluster": "investment", "amount": 1_200_000_000_000},
        {"id": 19, "title": "Harvard Study: AI Coding Assistants Reduce Bugs by 40%", "source": "City AM", "cluster": "misc", "amount": 0},
        {"id": 20, "title": "SoftBank CEO Masayoshi Son Predicts AGI by 2030", "source": "TechCrunch", "cluster": "investment", "amount": 0},
    ]
    for t in templates:
        desc = f"AI industry news about {t['title']}"
        articles.append({
            "id": t["id"],
            "title": t["title"],
            "link": f"https://example.com/{t['id']}",
            "description": desc,
            "source": t["source"],
            "pub_date": now,
            "cluster": t["cluster"],
            "body": f"Article body. Major announcement with significant impact. {t['title']}. This is the full article text for scoring purposes.",
        })
    return articles


@pytest.fixture
def monkeypatch_d1(monkeypatch):
    """Mock d1_query to return empty results (prevents real D1 calls)"""
    def mock_d1(sql, retries=2):
        return []
    monkeypatch.setattr("auto_news_selector.d1_query", mock_d1)
    monkeypatch.setattr("pipeline.infra.d1_client.d1_query", mock_d1)
    return mock_d1


@pytest.fixture
def monkeypatch_openai(monkeypatch):
    """OpenAI Chat Completions 를 Mock 처리합니다.

    OpenAI API 호출을 가로채서 제어된 응답을 반환합니다.
    실제 API 키와 요금이 필요 없는 테스트에 사용하세요.

    사용법:
        def test_something(monkeypatch_openai):
            result = my_function()  # OpenAI 호출이 모의됨
    """
    class MockResponse:
        def __init__(self, content="Mocked response"):
            self.choices = [type('obj', (object,), {
                'message': type('obj', (object,), {'content': content})
            })()]

    def mock_create(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(
        "openai.resources.chat.completions.Completions.create",
        mock_create,
    )
    return mock_create


@pytest.fixture
def monkeypatch_deepseek(monkeypatch):
    """DeepSeek API (openai 패키지, custom base_url)를 Mock 처리합니다.

    코드베이스는 `from openai import OpenAI` 방식으로 DeepSeek에 접속합니다
    (base_url=https://api.deepseek.com/v1).
    이 fixture는 OpenAI 클래스 자체를 Mock으로 대체합니다.

    사용법:
        def test_deepseek(monkeypatch_deepseek):
            result = my_function()  # DeepSeek 호출이 모의됨
    """
    from unittest.mock import MagicMock

    mock = MagicMock()
    mock.chat.completions.create.return_value.choices[0].message.content = (
        "Mocked DeepSeek response"
    )

    def mock_openai_init(*args, **kwargs):
        return mock

    monkeypatch.setattr("openai.OpenAI", mock_openai_init)
    return mock


@pytest.fixture
def monkeypatch_http(monkeypatch):
    """HTTP 요청 (requests.get, urllib.request.urlopen)을 Mock 처리합니다.

    RSS 피드 수집, 웹 크롤링 등 외부 HTTP 호출이 필요한 테스트에서
    실제 네트워크 요청 없이 제어된 응답을 반환합니다.

    사용법:
        def test_feed_parsing(monkeypatch_http):
            articles = fetch_rss()  # HTTP 호출이 모의됨
    """
    import io

    class MockResponse:
        def __init__(self, text="", status_code=200):
            self.text = text
            self.status_code = status_code

        def read(self):
            return self.text.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def mock_get(*args, **kwargs):
        return MockResponse(
            text=(
                "<rss><channel><item>"
                "<title>Test Article</title>"
                "<link>https://example.com/test</link>"
                "<description>Test description</description>"
                "</item></channel></rss>"
            )
        )

    def mock_urlopen(url, *args, **kwargs):
        return MockResponse(
            text=(
                "<rss><channel><item>"
                "<title>Test Article</title>"
                "<link>https://example.com/test</link>"
                "<description>Test description</description>"
                "</item></channel></rss>"
            )
        )

    monkeypatch.setattr("requests.get", mock_get)
    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
    return mock_get
