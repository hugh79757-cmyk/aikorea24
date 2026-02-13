#!/usr/bin/env python3
"""aikorea24 뉴스 수집기 v2 - 5개 소스, D1 저장"""

import os, json, subprocess, urllib.request, urllib.parse
from datetime import datetime
from xml.etree import ElementTree as ET
from html import unescape
import re

# === 환경변수 로드 ===
def load_env(path):
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith('#') or '=' not in line:
                continue
            line = line.replace('export ', '')
            key, val = line.split('=', 1)
            os.environ[key.strip()] = val.strip().strip('"').strip("'")

load_env('/Users/twinssn/Projects/aikorea24/api_test/.env.sh')

PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'
NAVER_ID = os.environ.get('NAVER_CLIENT_ID', '')
NAVER_SECRET = os.environ.get('NAVER_CLIENT_SECRET', '')
DATA_KEY = os.environ.get('DATA_GO_KR_KEY', '')

def clean(text):
    text = unescape(text or '')
    return re.sub(r'<[^>]+>', '', text).strip()

# === 1. 과기부 사업공고 (AI 키워드 필터) ===
def fetch_msit_announcements(limit=20):
    url = f"http://apis.data.go.kr/1721000/msitannouncementinfo/businessAnnouncMentList?ServiceKey={DATA_KEY}&pageNo=1&numOfRows={limit}&returnType=json"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        items = data['response'][1]['body']['items']
        results = []
        keywords = ['AI', '인공지능', '디지털', '데이터', '클라우드', '소프트웨어', '바우처']
        for entry in items:
            item = entry['item']
            title = clean(item.get('subject', ''))
            if any(k in title for k in keywords):
                results.append({
                    'title': title,
                    'link': item.get('viewUrl', ''),
                    'description': f"담당: {item.get('deptName','')} | {item.get('managerName','')} {item.get('managerTel','')}",
                    'source': '과기부 사업공고',
                    'category': 'grant',
                    'pub_date': item.get('pressDt', '')
                })
        print(f"  과기부 사업공고: {len(results)}건 (AI 관련)")
        return results
    except Exception as e:
        print(f"  과기부 사업공고 실패: {e}")
        return []

# === 2. 과기부 보도자료 ===
def fetch_msit_press(limit=10):
    url = f"http://apis.data.go.kr/1721000/msitpressreleaseinfo/pressReleaseList?ServiceKey={DATA_KEY}&pageNo=1&numOfRows={limit}&returnType=json"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        items = data['response'][1]['body']['items']
        results = []
        for entry in items:
            item = entry['item']
            results.append({
                'title': clean(item.get('subject', '')),
                'link': item.get('viewUrl', ''),
                'description': f"담당: {item.get('deptName','')}",
                'source': '과기부 보도자료',
                'category': 'policy',
                'pub_date': item.get('pressDt', '')
            })
        print(f"  과기부 보도자료: {len(results)}건")
        return results
    except Exception as e:
        print(f"  과기부 보도자료 실패: {e}")
        return []

# === 3. 행정안전부 공공서비스(혜택) ===
def fetch_gov_benefits(limit=10):
    url = f"https://api.odcloud.kr/api/gov24/v3/serviceList?page=1&perPage={limit}&serviceKey={DATA_KEY}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        results = []
        keywords = ['AI', '인공지능', '디지털', '창업', '소상공인', '중소기업', '기술', '혁신']
        for item in data.get('data', []):
            name = item.get('서비스명', '')
            if any(k in name or k in item.get('서비스목적요약', '') for k in keywords):
                results.append({
                    'title': name,
                    'link': f"https://www.gov.kr/portal/rcvfvrSvc/dtlEx/{item.get('서비스ID','')}",
                    'description': item.get('서비스목적요약', '')[:200],
                    'source': '정부24 혜택',
                    'category': 'benefit',
                    'pub_date': datetime.now().strftime('%Y-%m-%d')
                })
        print(f"  정부24 혜택: {len(results)}건 (관련 키워드)")
        return results
    except Exception as e:
        print(f"  정부24 혜택 실패: {e}")
        return []

# === 4. 네이버 뉴스 검색 ===
def fetch_naver_news(query, display=5):
    encoded = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/news.json?query={encoded}&display={display}&sort=date"
    req = urllib.request.Request(url, headers={
        'X-Naver-Client-Id': NAVER_ID,
        'X-Naver-Client-Secret': NAVER_SECRET
    })
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        results = []
        for item in data.get('items', []):
            results.append({
                'title': clean(item['title']),
                'link': item['link'],
                'description': clean(item['description'])[:200],
                'source': '네이버뉴스',
                'category': 'news',
                'pub_date': datetime.now().strftime('%Y-%m-%d')
            })
        return results
    except Exception as e:
        print(f"  네이버 '{query}' 실패: {e}")
        return []

# === 5. RSS 수집 ===
def fetch_rss(url, source_name, limit=5):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        xml = urllib.request.urlopen(req, timeout=10).read()
        tree = ET.fromstring(xml)
        results = []
        for item in tree.findall('.//item')[:limit]:
            results.append({
                'title': clean(item.findtext('title', '')),
                'link': item.findtext('link', ''),
                'description': clean(item.findtext('description', ''))[:200],
                'source': source_name,
                'category': 'news',
                'pub_date': datetime.now().strftime('%Y-%m-%d')
            })
        return results
    except Exception as e:
        print(f"  RSS {source_name} 실패: {e}")
        return []

# === D1 저장 ===
def insert_to_d1(news_list):
    success = 0
    for item in news_list:
        title = item['title'].replace("'", "''")
        desc = item['description'].replace("'", "''")
        link = item['link'].replace("'", "''")
        sql = f"INSERT OR IGNORE INTO news (title, link, description, source, category, pub_date) VALUES ('{title}', '{link}', '{desc}', '{item['source']}', '{item['category']}', '{item['pub_date']}')"
        try:
            subprocess.run(
                ['npx', 'wrangler', 'd1', 'execute', 'aikorea24-db', '--remote', '--command', sql],
                capture_output=True, text=True, cwd=PROJECT_DIR, timeout=30
            )
            success += 1
        except:
            pass
    return success

# === 메인 실행 ===
if __name__ == '__main__':
    print(f"\n{'='*50}")
    print(f"aikorea24 뉴스 수집 시작: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}\n")

    all_news = []

    # 1. 과기부 사업공고 (AI 관련만)
    print("[1/5] 과기부 사업공고...")
    all_news.extend(fetch_msit_announcements(50))

    # 2. 과기부 보도자료
    print("[2/5] 과기부 보도자료...")
    all_news.extend(fetch_msit_press(10))

    # 3. 정부24 혜택
    print("[3/5] 정부24 혜택...")
    all_news.extend(fetch_gov_benefits(50))

    # 4. 네이버 뉴스
    print("[4/5] 네이버 뉴스...")
    for q in ['AI 지원사업', '인공지능 정책', 'AI 바우처 2026']:
        results = fetch_naver_news(q, 5)
        all_news.extend(results)
        print(f"  네이버 '{q}': {len(results)}건")

    # 5. RSS
    print("[5/5] RSS 피드...")
    rss_sources = [
        ('https://www.aitimes.com/rss/allArticle.xml', 'AI타임스'),
    ]
    for url, name in rss_sources:
        results = fetch_rss(url, name, 5)
        all_news.extend(results)
        print(f"  {name}: {len(results)}건")

    print(f"\n총 수집: {len(all_news)}건")

    # D1 저장
    print("\nD1 저장 중...")
    inserted = insert_to_d1(all_news)
    print(f"D1 저장 완료: {inserted}건")

    print(f"\n{'='*50}")
    print("수집 완료!")
    print(f"{'='*50}\n")
