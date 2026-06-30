"""Tests for pipeline.threads.crawler — HTTP mocked."""
import pytest
import os
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pipeline.threads.crawler import fetch_article_body, log_failed_crawl


class TestFetchArticleBody:
    @pytest.mark.unit
    def test_successful_crawl(self, monkeypatch):
        import requests
        class MockResp:
            status_code = 200
            text = '<html><body><article><p>Test article body content here.</p></article></body></html>'
            def raise_for_status(self):
                pass
        def mock_get(*args, **kwargs):
            return MockResp()
        monkeypatch.setattr(requests, "get", mock_get)
        result = fetch_article_body("https://example.com/article")
        assert "Test article body" in result

    @pytest.mark.unit
    def test_retry_on_failure(self, monkeypatch):
        import requests
        call_count = [0]
        def mock_get(*args, **kwargs):
            call_count[0] += 1
            raise ConnectionError("simulated failure")
        monkeypatch.setattr(requests, "get", mock_get)
        result = fetch_article_body("https://example.com/fail")
        assert result == ""
        assert call_count[0] == 2

    @pytest.mark.unit
    def test_empty_url(self):
        assert fetch_article_body("") == ""


class TestLogFailedCrawl:
    @pytest.mark.unit
    def test_log_writes_file(self, tmp_path):
        from pipeline.threads import crawler
        original_path = crawler.FAILED_CRAWLS_FILE
        test_path = os.path.join(str(tmp_path), "failed_crawls.json")
        crawler.FAILED_CRAWLS_FILE = test_path
        try:
            log_failed_crawl("https://example.com/fail", "test_source", "Test Title", "404")
            assert os.path.exists(test_path)
            with open(test_path, 'r') as f:
                data = json.load(f)
            assert len(data['failed']) == 1
            assert data['failed'][0]['url'] == "https://example.com/fail"
        finally:
            crawler.FAILED_CRAWLS_FILE = original_path
