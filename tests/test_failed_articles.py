"""Tests for scripts.threads.failed_articles — persistent failed article tracking."""
import pytest
import os
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from scripts.threads import failed_articles


class TestLoadFailedArticles:
    @pytest.fixture(autouse=True)
    def setup_paths(self, tmp_path, monkeypatch):
        """Isolate file paths per test."""
        self.test_articles_path = os.path.join(str(tmp_path), "failed_articles.json")
        self.test_crawls_path = os.path.join(str(tmp_path), "failed_crawls.json")
        failed_articles.FAILED_ARTICLES_FILE = self.test_articles_path
        failed_articles.FAILED_CRAWLS_FILE = self.test_crawls_path
        # Ensure no files exist initially
        if os.path.exists(self.test_articles_path):
            os.remove(self.test_articles_path)
        if os.path.exists(self.test_crawls_path):
            os.remove(self.test_crawls_path)
        # Reset in-memory state
        failed_articles._failed_article_ids.clear()
        failed_articles._failed_articles_meta.clear()

    def test_load_when_file_missing(self):
        """When failed_articles.json does not exist, returns empty set."""
        ids = failed_articles.load_failed_articles()
        assert isinstance(ids, set)
        assert len(ids) == 0
        # Should not create the file automatically
        assert not os.path.exists(self.test_articles_path)

    def test_load_from_valid_file(self):
        """Loads article IDs from existing file."""
        data = {
            "failed_ids": {
                "123": {"failed_at": datetime.now().isoformat(), "reason": "test"},
                "456": {"failed_at": datetime.now().isoformat(), "reason": "test2"}
            },
            "last_updated": datetime.now().isoformat()
        }
        os.makedirs(os.path.dirname(self.test_articles_path), exist_ok=True)
        with open(self.test_articles_path, 'w') as f:
            json.dump(data, f)
        ids = failed_articles.load_failed_articles()
        assert '123' in ids
        assert '456' in ids
        assert len(ids) == 2

    def test_merge_from_failed_crawls(self):
        """Loads article IDs from failed_crawls.json and merges."""
        crawls_data = {
            "failed": [
                {"url": "http://example.com", "status": "404", "failed_at": datetime.now().isoformat(), "article_id": "999"},
                {"url": "http://example2.com", "status": "500", "failed_at": datetime.now().isoformat(), "article_id": "888"}
            ],
            "updated_at": datetime.now().isoformat()
        }
        os.makedirs(os.path.dirname(self.test_crawls_path), exist_ok=True)
        with open(self.test_crawls_path, 'w') as f:
            json.dump(crawls_data, f)
        ids = failed_articles.load_failed_articles()
        assert '999' in ids
        assert '888' in ids

    def test_clear_old_entries_during_load(self):
        """Old entries (older than retention) are purged on load."""
        # Create a file with one old and one fresh entry
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        new_date = datetime.now().isoformat()
        data = {
            "failed_ids": {
                "old": {"failed_at": old_date, "reason": "old"},
                "fresh": {"failed_at": new_date, "reason": "fresh"}
            },
            "last_updated": datetime.now().isoformat()
        }
        os.makedirs(os.path.dirname(self.test_articles_path), exist_ok=True)
        with open(self.test_articles_path, 'w') as f:
            json.dump(data, f)
        ids = failed_articles.load_failed_articles()
        assert 'fresh' in ids
        assert 'old' not in ids


class TestSaveFailedArticle:
    @pytest.fixture(autouse=True)
    def setup_paths(self, tmp_path, monkeypatch):
        self.test_articles_path = os.path.join(str(tmp_path), "failed_articles.json")
        failed_articles.FAILED_ARTICLES_FILE = self.test_articles_path
        failed_articles._failed_article_ids.clear()
        failed_articles._failed_articles_meta.clear()
        # Preload to initialize file if needed
        if os.path.exists(self.test_articles_path):
            os.remove(self.test_articles_path)

    def test_save_creates_file_and_entry(self):
        failed_articles.save_failed_article('123', reason='write_validation_failed', title='Test', url='http://example.com')
        assert os.path.exists(self.test_articles_path)
        with open(self.test_articles_path, 'r') as f:
            data = json.load(f)
        assert '123' in data['failed_ids']
        assert data['failed_ids']['123']['reason'] == 'write_validation_failed'
        assert failed_articles.is_article_failed('123')

    def test_save_updates_metadata(self):
        failed_articles.save_failed_article('123', reason='first')
        failed_articles.save_failed_article('123', reason='updated')
        with open(self.test_articles_path, 'r') as f:
            data = json.load(f)
        assert data['failed_ids']['123']['reason'] == 'updated'

    def test_save_strips_hash_prefix(self):
        failed_articles.save_failed_article('#456', reason='test')
        assert failed_articles.is_article_failed('456')
        assert '456' in failed_articles._failed_article_ids


class TestIsArticleFailed:
    @pytest.fixture(autouse=True)
    def setup(self):
        failed_articles._failed_article_ids.clear()
        failed_articles._failed_articles_meta.clear()

    def test_positive(self):
        failed_articles._failed_article_ids.add('123')
        assert failed_articles.is_article_failed('123')

    def test_negative(self):
        assert not failed_articles.is_article_failed('999')

    def test_strips_hash(self):
        failed_articles._failed_article_ids.add('123')
        assert failed_articles.is_article_failed('#123')


class TestClearOldEntries:
    @pytest.fixture(autouse=True)
    def setup_paths(self, tmp_path, monkeypatch):
        self.test_articles_path = os.path.join(str(tmp_path), "failed_articles.json")
        failed_articles.FAILED_ARTICLES_FILE = self.test_articles_path
        os.makedirs(os.path.dirname(self.test_articles_path), exist_ok=True)
        failed_articles._failed_article_ids.clear()
        failed_articles._failed_articles_meta.clear()
        yield
        # cleanup not needed

    def test_purges_old_entries(self):
        now = datetime.now()
        old_date = (now - timedelta(days=10)).isoformat()
        new_date = now.isoformat()
        # Prepare in-memory state
        failed_articles._failed_articles_meta = {
            'old': {'failed_at': old_date, 'reason': 'old'},
            'fresh': {'failed_at': new_date, 'reason': 'fresh'}
        }
        failed_articles._failed_article_ids = {'old', 'fresh'}
        # Write a corresponding file
        data = {
            "failed_ids": {
                "old": {"failed_at": old_date, "reason": "old"},
                "fresh": {"failed_at": new_date, "reason": "fresh"}
            },
            "last_updated": now.isoformat()
        }
        with open(self.test_articles_path, 'w') as f:
            json.dump(data, f)
        # Run purge with 7 day retention
        purged = failed_articles.clear_old_entries(max_days=7)
        assert purged == 1
        assert 'old' not in failed_articles._failed_article_ids
        assert 'fresh' in failed_articles._failed_article_ids
        # Verify file updated
        with open(self.test_articles_path, 'r') as f:
            file_data = json.load(f)
        assert 'old' not in file_data['failed_ids']
        assert 'fresh' in file_data['failed_ids']

    def test_retention_from_env(self, monkeypatch):
        monkeypatch.setenv('FAILED_ARTICLE_RETENTION_DAYS', '30')
        now = datetime.now()
        old_date = (now - timedelta(days=40)).isoformat()
        recent_old_date = (now - timedelta(days=10)).isoformat()  # within 30
        failed_articles._failed_articles_meta = {
            'very_old': {'failed_at': old_date, 'reason': 'very_old'},
            'recent_old': {'failed_at': recent_old_date, 'reason': 'recent_old'},
            'fresh': {'failed_at': now.isoformat(), 'reason': 'fresh'}
        }
        failed_articles._failed_article_ids = {'very_old', 'recent_old', 'fresh'}
        # file
        data = {
            "failed_ids": {
                "very_old": {"failed_at": old_date, "reason": "very_old"},
                "recent_old": {"failed_at": recent_old_date, "reason": "recent_old"},
                "fresh": {"failed_at": now.isoformat(), "reason": "fresh"}
            },
            "last_updated": now.isoformat()
        }
        with open(self.test_articles_path, 'w') as f:
            json.dump(data, f)
        purged = failed_articles.clear_old_entries()  # uses env
        assert purged == 1
        assert 'very_old' not in failed_articles._failed_article_ids
        assert 'recent_old' in failed_articles._failed_article_ids
        assert 'fresh' in failed_articles._failed_article_ids

    def test_handles_invalid_timestamp(self):
        # Entry with malformed failed_at should be purged
        now = datetime.now()
        failed_articles._failed_articles_meta = {
            'bad': {'failed_at': 'not-a-date', 'reason': 'bad'},
            'good': {'failed_at': now.isoformat(), 'reason': 'good'}
        }
        failed_articles._failed_article_ids = {'bad', 'good'}
        data = {
            "failed_ids": {
                "bad": {"failed_at": "not-a-date", "reason": "bad"},
                "good": {"failed_at": now.isoformat(), "reason": "good"}
            },
            "last_updated": now.isoformat()
        }
        with open(self.test_articles_path, 'w') as f:
            json.dump(data, f)
        purged = failed_articles.clear_old_entries(max_days=7)
        assert purged == 1
        assert 'bad' not in failed_articles._failed_article_ids
        assert 'good' in failed_articles._failed_article_ids
