import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import subprocess

def load_env(filepath):
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                line = line.replace('export ', '')
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip().strip('"')

load_env('/Users/twinssn/Projects/aikorea24/api_test/.env.sh')

def fetch_naver_news(query, display=5):
    encoded = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/news.json?query={encoded}&display={display}&sort=date"
    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", os.environ['NAVER_CLIENT_ID'])
    req.add_header("X-Naver-Client-Secret", os.environ['NAVER_CLIENT_SECRET'])
    with urllib.request.urlopen(req) as res:
        data = json.loads(res.read().decode('utf-8'))
    results = []
    for item in data.get('items', []):
        title = item['title'].replace('<b>','').replace('</b>','').replace('&quot;','"').replace('&amp;','&')
        desc = item['description'].replace('<b>','').replace('</b>','').replace('&quot;','"').replace('&amp;','&')
        results.append({'title': title, 'link': item['originallink'], 'description': desc[:200], 'pub_date': item['pubDate'], 'source': 'naver'})
    return results

def fetch_rss(url, source_name, limit=5):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as res:
        xml_data = res.read().decode('utf-8')
    root = ET.fromstring(xml_data)
    results = []
    for item in root.findall('.//item')[:limit]:
        results.append({
            'title': item.findtext('title','').strip(),
            'link': item.findtext('link','').strip(),
            'description': item.findtext('description','').strip()[:200],
            'pub_date': item.findtext('pubDate',''),
            'source': source_name
        })
    return results

def insert_to_d1(news_list):
    count = 0
    for n in news_list:
        title = n['title'].replace("'", "''")
        link = n['link'].replace("'", "''")
        desc = n['description'].replace("'", "''")
        source = n['source']
        pub = n.get('pub_date', '')
        sql = f"INSERT OR IGNORE INTO news (title, link, description, source, category, pub_date) VALUES ('{title}', '{link}', '{desc}', '{source}', 'AI', '{pub}');"
        try:
            subprocess.run(
                ['npx', 'wrangler', 'd1', 'execute', 'aikorea24-db', '--remote', '--command', sql],
                capture_output=True, text=True, cwd='/Users/twinssn/Projects/aikorea24'
            )
            count += 1
            print(f"  ✅ {n['title'][:40]}...")
        except Exception as e:
            print(f"  ❌ {e}")
    return count

if __name__ == '__main__':
    all_news = []

    print("🔍 네이버: AI 지원사업")
    all_news += fetch_naver_news("AI 지원사업", 5)

    print("🔍 네이버: 인공지능 정책")
    all_news += fetch_naver_news("인공지능 정책", 5)

    print("📡 AI타임스 RSS")
    all_news += fetch_rss("https://www.aitimes.com/rss/allArticle.xml", "AI타임스", 5)

    print(f"\n총 {len(all_news)}건 수집. D1에 삽입 중...")
    inserted = insert_to_d1(all_news)
    print(f"\n✅ {inserted}건 D1 삽입 완료")
