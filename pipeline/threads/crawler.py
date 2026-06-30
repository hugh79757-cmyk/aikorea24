"""pipeline/threads/crawler.py — 기사 크롤링 및 실패 기록"""
import os, json, time
from datetime import datetime
import requests
from bs4 import BeautifulSoup

from pipeline.infra import project_root
from pipeline.infra.logger import get_scrubbed_logger

logger = get_scrubbed_logger(__name__)

PROJECT_DIR = project_root()
LOGS_DIR = os.path.join(PROJECT_DIR, 'scripts', 'threads', 'logs')
FAILED_CRAWLS_FILE = os.path.join(LOGS_DIR, 'failed_crawls.json')
os.makedirs(LOGS_DIR, exist_ok=True)


def _log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')
    log_path = os.path.join(LOGS_DIR, datetime.now().strftime('%Y-%m-%d') + '.log')
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] [v3] {msg}\n')


def log_failed_crawl(url, source, title, status):
    """크롤링 실패한 URL을 failed_crawls.json에 기록"""
    data = {"failed": [], "updated_at": ""}
    if os.path.exists(FAILED_CRAWLS_FILE):
        try:
            with open(FAILED_CRAWLS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            pass
    now = datetime.now().isoformat()
    entry = {"url": url, "source": source, "title": title, "status": status, "failed_at": now}
    data['failed'] = [e for e in data['failed'] if e.get('url') != url]
    data['failed'].append(entry)
    data['updated_at'] = now
    with open(FAILED_CRAWLS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_article_body(url, source='', title=''):
    """원문 기사 본문을 크롤링해서 텍스트 반환. 실패 시 빈 문자열.
    2회 재시도. 실패 시 failed_crawls.json에 기록.
    """
    if not url:
        return ''

    max_attempts = 2
    for attempt in range(max_attempts):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'lxml')
            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'noscript', 'iframe']):
                tag.decompose()
            body = None
            for selector in ['article', 'main', '[role="main"]', '.article-body', '.post-content', '.entry-content', '.story-body']:
                candidate = soup.select_one(selector)
                if candidate:
                    body = candidate.get_text(separator='\n', strip=True)
                    break
            if not body:
                body = soup.get_text(separator='\n', strip=True)
            lines = [l.strip() for l in body.split('\n') if l.strip()]
            text = '\n'.join(lines)
            _log(f'  📰 크롤링: {url[:50]}... ({len(text)}자)')
            return text
        except Exception as e:
            err_msg = f'{type(e).__name__}'
            _log(f'  ⚠️ 크롤링 실패 ({attempt+1}/{max_attempts}): {url[:50]}... ({err_msg})')
            if attempt < max_attempts - 1:
                time.sleep(3)
            else:
                log_failed_crawl(url, source, title, err_msg)
                return ''
