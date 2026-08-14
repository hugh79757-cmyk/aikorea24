#!/usr/bin/env python3
"""
 persisted failed article tracking to prevent infinite retry loops across restarts.

Functions:
- load_failed_articles(): Load failed article IDs from disk, merge from failed_crawls.json
- save_failed_article(article_id, reason="unknown"): Persist a single failed article
- is_article_failed(article_id): Check if an article ID is in the failed set
- clear_old_entries(max_days=None): Purge entries older than retention period
- get_failed_article_count(): Return current count (for logging)
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Set, Dict, Any

# Project root resolution
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from pipeline.infra import project_root
PROJECT_DIR = project_root()

THREADS_DIR = os.path.join(PROJECT_DIR, 'scripts', 'threads')
LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
FAILED_ARTICLES_FILE = os.path.join(LOGS_DIR, 'failed_articles.json')
FAILED_CRAWLS_FILE = os.path.join(LOGS_DIR, 'failed_crawls.json')

# In-memory cache of failed article IDs
_failed_article_ids: Set[str] = set()
# Metadata for each failed article (article_id -> metadata dict)
_failed_articles_meta: Dict[str, Dict[str, Any]] = {}


def _ensure_logs_dir():
    os.makedirs(LOGS_DIR, exist_ok=True)


def _get_retention_days() -> float:
    """Get retention period from env or default 2 hours (0.083 days).
    
    Changed from 24h to 2h: write_thread failures are often transient
    (model instability), and 24h TTL starves the article pool.
    """
    try:
        hours = float(os.environ.get('FAILED_ARTICLE_RETENTION_HOURS', '2'))
        return max(0.083, hours / 24)  # convert hours to days, minimum ~2h
    except (ValueError, TypeError):
        return 2 / 24  # 2 hours in days


FAILED_ARTICLES_RETENTION_SECONDS = 2 * 3600  # 2 hours for failed_crawls (was 24h)


def _is_crawl_expired(entry: dict) -> bool:
    expired_at = entry.get("expired_at")
    if not expired_at:
        failed_at = entry.get("failed_at", "")
        if failed_at:
            try:
                dt = datetime.fromisoformat(failed_at.replace("Z", "+00:00"))
                expired_at = (dt + timedelta(seconds=FAILED_ARTICLES_RETENTION_SECONDS)).isoformat()
            except (ValueError, TypeError):
                return True
        else:
            return True
    try:
        return datetime.fromisoformat(expired_at.replace("Z", "+00:00")) < datetime.now()
    except (ValueError, TypeError):
        return True


def load_failed_articles() -> Set[str]:
    """
    Load failed article IDs from failed_articles.json on disk.
    Also merges URLs from failed_crawls.json (with 24h TTL).
    Returns the set of failed article IDs.
    """
    global _failed_article_ids, _failed_articles_meta
    _failed_article_ids = set()
    _failed_articles_meta = {}

    _ensure_logs_dir()

    # 1. Load from failed_articles.json (primary store)
    if os.path.exists(FAILED_ARTICLES_FILE):
        try:
            with open(FAILED_ARTICLES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            failed_ids_dict = data.get('failed_ids', {})
            for aid, meta in failed_ids_dict.items():
                _failed_article_ids.add(str(aid))
                _failed_articles_meta[str(aid)] = meta
        except (json.JSONDecodeError, IOError) as e:
            print(f"[WARN] Failed to load {FAILED_ARTICLES_FILE}: {e}", file=sys.stderr)

    # 2. Merge from failed_crawls.json (with 24h TTL)
    if os.path.exists(FAILED_CRAWLS_FILE):
        try:
            with open(FAILED_CRAWLS_FILE, 'r', encoding='utf-8') as f:
                crawl_data = json.load(f)
            valid_entries = []
            purged_count = 0
            for entry in crawl_data.get('failed', []):
                if _is_crawl_expired(entry):
                    purged_count += 1
                    continue
                valid_entries.append(entry)
                aid = entry.get('article_id', '')
                if aid:
                    aid_str = str(aid)
                    _failed_article_ids.add(aid_str)
                    if aid_str not in _failed_articles_meta:
                        _failed_articles_meta[aid_str] = {
                            'failed_at': entry.get('failed_at', datetime.now().isoformat()),
                            'reason': entry.get('status', 'crawl_failed'),
                            'source': 'failed_crawls.json',
                        }
            if purged_count > 0:
                crawl_data['failed'] = valid_entries
                crawl_data['updated_at'] = datetime.now().isoformat()
                with open(FAILED_CRAWLS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(crawl_data, f, ensure_ascii=False, indent=2)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[WARN] Failed to load {FAILED_CRAWLS_FILE}: {e}", file=sys.stderr)

    # 3. Clear old entries (retention policy for failed_articles.json)
    clear_old_entries()

    return _failed_article_ids


def save_failed_article(article_id: str, reason: str = "unknown", title: str = "", url: str = "") -> None:
    """
    Save a failed article ID to disk (persistent store).
    Adds to in-memory set and updates the JSON file.
    """
    global _failed_article_ids, _failed_articles_meta

    aid_str = str(article_id).lstrip('#').strip()
    if not aid_str:
        return

    _failed_article_ids.add(aid_str)

    # Update metadata — TTL is 2 hours (was 24h)
    now = datetime.now()
    meta = {
        'failed_at': now.isoformat(),
        'expired_at': (now + timedelta(hours=2)).isoformat(),
        'reason': reason,
        'title': title,
        'url': url
    }
    _failed_articles_meta[aid_str] = meta

    # Persist to file
    _ensure_logs_dir()
    try:
        # Read existing to preserve structure
        data = {'failed_ids': {}, 'last_updated': datetime.now().isoformat()}
        if os.path.exists(FAILED_ARTICLES_FILE):
            with open(FAILED_ARTICLES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        # Update the specific article's metadata
        if 'failed_ids' not in data:
            data['failed_ids'] = {}
        data['failed_ids'][aid_str] = meta
        data['last_updated'] = datetime.now().isoformat()
        with open(FAILED_ARTICLES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[WARN] Failed to save {FAILED_ARTICLES_FILE}: {e}", file=sys.stderr)


def is_article_failed(article_id: str) -> bool:
    """Check if an article ID is in the failed set."""
    aid_str = str(article_id).lstrip('#').strip()
    return aid_str in _failed_article_ids


def clear_old_entries(max_days: int = None) -> int:
    """
    Remove entries older than max_days from both in-memory set and disk.
    Returns number of entries purged.
    """
    global _failed_article_ids, _failed_articles_meta

    if max_days is None:
        max_days = _get_retention_days()

    cutoff = datetime.now() - timedelta(days=max_days)
    purged = 0

    # Identify entries to purge based on failed_at timestamp
    to_remove = []
    for aid, meta in _failed_articles_meta.items():
        try:
            failed_at = datetime.fromisoformat(meta.get('failed_at', '').replace('Z', '+00:00'))
            if failed_at < cutoff:
                to_remove.append(aid)
        except (ValueError, KeyError, TypeError):
            # If timestamp is invalid, consider purging as unsafe
            to_remove.append(aid)

    # Update in-memory
    for aid in to_remove:
        _failed_article_ids.discard(aid)
        del _failed_articles_meta[aid]
        purged += 1

    # Persist the cleaned state to disk
    if purged > 0 and os.path.exists(FAILED_ARTICLES_FILE):
        try:
            with open(FAILED_ARTICLES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Remove purged entries from failed_ids
            if 'failed_ids' in data:
                for aid in to_remove:
                    data['failed_ids'].pop(aid, None)
            data['last_updated'] = datetime.now().isoformat()
            with open(FAILED_ARTICLES_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[WARN] Failed to update {FAILED_ARTICLES_FILE} after purge: {e}", file=sys.stderr)

    return purged


def get_failed_article_count() -> int:
    """Return the number of failed articles currently tracked."""
    return len(_failed_article_ids)


def get_failed_articles_meta() -> Dict[str, Dict[str, Any]]:
    """Return metadata dict for all failed articles (copy)."""
    return dict(_failed_articles_meta)


# Emergency manual function (plan: Manual escape hatch)
def fail_article(article_id: str, reason: str = "manual") -> None:
    """
    Emergency function to manually mark an article as failed.
    Usage: python3 -c "from scripts.threads.failed_articles import save_failed_article; save_failed_article('38290')"
    """
    save_failed_article(article_id, reason=reason)


# Self-test when run directly
if __name__ == '__main__':
    print("Loading failed articles...")
    ids = load_failed_articles()
    print(f"Loaded {len(ids)} failed article IDs")
    print(f"Sample: {list(ids)[:5]}")
