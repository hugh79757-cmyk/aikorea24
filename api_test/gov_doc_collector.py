#!/usr/bin/env python3
"""정부 공문서 AI 학습데이터 수집기 - aikorea24 연동"""

import os
import sys
import json
import requests
import subprocess
import hashlib
from datetime import datetime

# 프로젝트 루트
PROJECT_ROOT = '/Users/twinssn/Projects/aikorea24'

# .env에서 키 로드
env_path = os.path.join(PROJECT_ROOT, '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                os.environ[k.strip()] = v.strip()

API_KEY = os.environ.get('DATA_GO_KR_KEY', '')
if not API_KEY:
    print('ERROR: DATA_GO_KR_KEY not found in .env')
    sys.exit(1)

BASE_URL = 'http://apis.data.go.kr/1741000/publicDoc'

# AI 관련 검색 키워드
SEARCH_KEYWORDS = [
    'AI', '인공지능', '디지털', '데이터', '클라우드',
    '소프트웨어', '사이버', '스마트', '자율주행', '로봇',
    '반도체', 'GPT', '딥러닝', '빅데이터', '메타버스'
]

# 엔드포인트별 문서 유형
ENDPOINTS = {
    'getDocPress': '보도자료',
    'getDocReport': '정책보고서',
    'getDocSpeech': '연설문',
}

# AI 관련 필터
STRONG_AI_WORDS = ['AI', '인공지능', 'GPT', '딥러닝', '머신러닝', 'LLM', '생성형', '챗봇', 'ChatGPT', '클로드', '앤트로픽', 'OpenAI']
WEAK_AI_WORDS = ['디지털', '데이터', '클라우드', '스마트', '자율주행', '로봇', '반도체', '소프트웨어', '사이버', '빅데이터', '메타버스', '플랫폼']
EXCLUDE_WORDS = ['귀농', '귀촌', '귀어', '교복', '부동산', '아파트', '축구', '야구', '결혼', '이혼', '장례']

def is_ai_related(title, text_preview=''):
    combined = (title + ' ' + text_preview[:200]).upper()
    for w in EXCLUDE_WORDS:
        if w in combined:
            return False
    for w in STRONG_AI_WORDS:
        if w.upper() in combined:
            return True
    weak_count = sum(1 for w in WEAK_AI_WORDS if w.upper() in combined)
    return weak_count >= 2

def fetch_docs(endpoint, keyword, num=10, page=1):
    url = f'{BASE_URL}/{endpoint}'
    params = {
        'serviceKey': API_KEY,
        'format': 'json',
        'numOfRows': num,
        'pageNo': page,
        'title': keyword
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        body = data.get('response', {}).get('body', {})
        total = body.get('totalCount', 0)
        results = body.get('resultList', [])
        if isinstance(results, dict):
            results = [results]
        return results, total
    except Exception as e:
        print(f'  Error fetching {endpoint}/{keyword}: {e}')
        return [], 0

def safe_sql(text, maxlen=500):
    if not text:
        return ''
    t = text.replace("'", "''").replace('\\', '').replace('\n', ' ').replace('\r', '')
    return t[:maxlen]

def title_hash(title):
    return hashlib.md5(title.strip().lower().encode()).hexdigest()

def get_existing_hashes():
    cmd = f'npx wrangler d1 execute aikorea24-db --remote --command "SELECT title FROM news;"'
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=30)
        hashes = set()
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line and not line.startswith(('⛅', '─', '🌀', '✘', 'Resource', '┌', '│', '├', '└', 'Getting')):
                hashes.add(title_hash(line))
        return hashes
    except:
        return set()

def insert_to_d1(item):
    title = safe_sql(item['title'], 200)
    link = safe_sql(item.get('link', ''), 500)
    desc = safe_sql(item.get('description', ''), 1000)
    source = safe_sql(item.get('source', ''), 50)
    category = safe_sql(item.get('category', 'policy'), 20)
    pub_date = safe_sql(item.get('pub_date', ''), 30)

    sql = f"INSERT INTO news (title, link, description, source, category, pub_date) VALUES ('{title}', '{link}', '{desc}', '{source}', '{category}', '{pub_date}');"
    cmd = f'npx wrangler d1 execute aikorea24-db --remote --command "{sql}"'
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=15)
        return result.returncode == 0 and 'ERROR' not in result.stderr
    except:
        return False

def main():
    print('=' * 60)
    print(f'정부 공문서 AI 학습데이터 수집기')
    print(f'실행 시각: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 60)

    # 기존 뉴스 해시
    print('\n기존 뉴스 해시 로딩...')
    existing = get_existing_hashes()
    print(f'기존 뉴스: {len(existing)}건')

    collected = []
    for endpoint, doc_type in ENDPOINTS.items():
        print(f'\n--- {doc_type} ({endpoint}) ---')
        ep_count = 0
        for kw in SEARCH_KEYWORDS:
            results, total = fetch_docs(endpoint, kw, num=10, page=1)
            if not results:
                continue
            for item in results:
                if isinstance(item, dict) and 'meta' in item:
                    meta = item['meta']
                    text_data = item.get('data', {}).get('text', '')
                else:
                    meta = item
                    text_data = ''

                title = meta.get('title', '')
                if not title:
                    continue
                if not is_ai_related(title, text_data):
                    continue
                if title_hash(title) in existing:
                    continue

                # 미리보기 텍스트 (앞 300자)
                preview = text_data[:300].replace("'", "''") if text_data else ''

                collected.append({
                    'title': title,
                    'link': f'https://www.data.go.kr/data/15125451/openapi.do',
                    'description': preview if preview else f'{doc_type} - {meta.get("ministry", "")} ({meta.get("date", "")})',
                    'source': f'정부공문서({doc_type})',
                    'category': 'policy',
                    'pub_date': meta.get('date', '')
                })
                existing.add(title_hash(title))
                ep_count += 1
        print(f'  {doc_type} AI 관련: {ep_count}건')

    print(f'\n총 신규 수집: {len(collected)}건')

    if not collected:
        print('신규 데이터 없음. 종료.')
        return

    # D1 저장
    print('\nD1 저장 중...')
    saved = 0
    failed = 0
    for i, item in enumerate(collected):
        if insert_to_d1(item):
            saved += 1
            print(f'  [{i+1}/{len(collected)}] 저장: {item["title"][:40]}...')
        else:
            failed += 1
            print(f'  [{i+1}/{len(collected)}] 실패: {item["title"][:40]}...')

    print(f'\n완료: 저장 {saved}건, 실패 {failed}건')

if __name__ == '__main__':
    main()
