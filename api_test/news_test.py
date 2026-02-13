import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

# .env 파일 직접 읽기
def load_env(filepath):
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                line = line.replace('export ', '')
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

load_env('/Users/twinssn/Projects/aikorea24/.env')

# ========================================
# 1. 네이버 뉴스 검색
# ========================================
def fetch_naver_news(query, display=5):
    client_id = os.environ.get('NAVER_CLIENT_ID')
    client_secret = os.environ.get('NAVER_CLIENT_SECRET')
    
    encoded_query = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/news.json?query={encoded_query}&display={display}&sort=date"
    
    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", client_id)
    req.add_header("X-Naver-Client-Secret", client_secret)
    
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
    
    results = []
    for item in data.get('items', []):
        title = item['title'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"')
        results.append({
            'title': title,
            'link': item['originallink'],
            'description': item['description'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"'),
            'pubDate': item['pubDate'],
            'source': 'naver'
        })
    return results

# ========================================
# 2. RSS 뉴스 수집
# ========================================
def fetch_rss(url, source_name, limit=5):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        xml_data = response.read().decode('utf-8')
    
    root = ET.fromstring(xml_data)
    results = []
    
    for item in root.findall('.//item')[:limit]:
        title = item.findtext('title', '')
        link = item.findtext('link', '')
        desc = item.findtext('description', '')
        pub_date = item.findtext('pubDate', '')
        
        results.append({
            'title': title.strip(),
            'link': link.strip(),
            'description': desc.strip()[:200],
            'pubDate': pub_date,
            'source': source_name
        })
    return results

# ========================================
# 실행
# ========================================
if __name__ == '__main__':
    print("=" * 60)
    print("🔍 네이버 뉴스: 'AI 지원사업'")
    print("=" * 60)
    for n in fetch_naver_news("AI 지원사업", 3):
        print(f"  📰 {n['title']}")
        print(f"     {n['link']}")
        print()

    print("=" * 60)
    print("🔍 네이버 뉴스: 'AI 바우처'")
    print("=" * 60)
    for n in fetch_naver_news("AI 바우처", 3):
        print(f"  📰 {n['title']}")
        print(f"     {n['link']}")
        print()

    print("=" * 60)
    print("📡 AI타임스 RSS")
    print("=" * 60)
    for n in fetch_rss("https://www.aitimes.com/rss/allArticle.xml", "AI타임스", 3):
        print(f"  📰 {n['title']}")
        print(f"     {n['link']}")
        print()

    print("✅ 수집 테스트 완료")
