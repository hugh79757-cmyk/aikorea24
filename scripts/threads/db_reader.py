#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
aikorea24 D1 DB → 기사 풀 로드 (3단계 우선순위)
- 1순위: 오늘 briefing_items 포함 news
- 2순위: 최근 7일 news
- 3순위: 그 이전 news (최대 30일)
- posted.json 중복 제외
"""
import os, sys, json, re, subprocess
import urllib.request
from datetime import datetime, timedelta

PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'
THREADS_DIR = os.path.join(PROJECT_DIR, 'scripts', 'threads')
POSTED_FILE = os.path.join(THREADS_DIR, 'posted.json')
LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

# ============================================
# URL 유효성 검사 + Fallback (소스 공용)
# ============================================
_VALIDATE_SOURCES = {'TechCrunch', 'TechCrunch AI', 'CNBC Tech', 'BBC Technology', 'BBC', 'Business Insider AI'}

def validate_link(url, timeout=8):
    """GET 요청으로 URL이 유효한지 확인 (2xx/3xx면 True)
    HEAD 대신 GET 사용 (한국 뉴스 사이트가 HEAD를 차단하는 경우 대응)
    """
    if not url or not url.startswith('http'):
        return False
    try:
        req = urllib.request.Request(url, method='GET',
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 400
    except Exception:
        return False

def find_fallback_url(title, max_title_chars=80):
    """Google News RSS로 동일 기사 검색 → 첫 번째 결과 URL 반환"""
    import urllib.parse
    query = urllib.parse.quote(title[:max_title_chars])
    url = f'https://news.google.com/rss/search?q={query}&hl=en&gl=US&ceid=US:en'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'aikorea24-bot/4.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
        for item in root.iter('item'):
            link_el = item.find('link')
            if link_el is not None and link_el.text:
                found = link_el.text.strip()
                if found.startswith('http'):
                    return found
    except Exception:
        pass
    return None

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(os.path.join(LOGS_DIR, datetime.now().strftime('%Y-%m-%d') + '.log'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] {msg}\n')

def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"posted_links": [], "posted_ids": [], "history": [], "last_reset": ""}

def save_posted(data):
    with open(POSTED_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def d1_query(sql):
    cmd = ['npx', 'wrangler', 'd1', 'execute', 'aikorea24-db', '--remote', '--command', sql]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=PROJECT_DIR)
        if r.returncode != 0:
            return []
        m = re.search(r'"results"\s*:\s*(\[[\s\S]*?\])\s*,\s*"success"', r.stdout)
        if m:
            return json.loads(m.group(1))
        return []
    except Exception as e:
        log(f'  ⚠️ D1 오류: {e}')
        return []

def get_articles():
    """3단계 우선순위 기사 풀 반환"""
    posted = load_posted()
    posted_links = set(posted.get('posted_links', []))
    posted_ids = set(posted.get('posted_ids', []))
    today = datetime.now().strftime('%Y-%m-%d')

    articles = []

    # 1순위: 오늘 브리핑
    sql1 = f"""SELECT n.id, n.title, n.link, n.description, n.source, n.pub_date,
                      COALESCE(bi.comment, '') as comment
               FROM news n
               JOIN briefing_items bi ON bi.news_id = n.id
               JOIN briefings b ON b.id = bi.briefing_id
               WHERE b.date = '{today}' AND b.status = 'published'
               GROUP BY n.id ORDER BY bi.sort_order ASC"""
    rows = d1_query(sql1)
    for r in rows:
        if r['id'] not in posted_ids:
            r['priority'] = 1
            articles.append(r)
    log(f'  1순위 브리핑: {len(rows)}개 → 신규 {len([a for a in articles if a["priority"]==1])}개')

    # 2순위: 최근 7일 news (브리핑 제외)
    existing_ids = set(a['id'] for a in articles)
    sql2 = f"""SELECT id, title, link, description, source, pub_date, '' as comment
               FROM news
               WHERE pub_date >= date('now', '-7 days')
               ORDER BY pub_date DESC LIMIT 400"""
    rows2 = d1_query(sql2)
    for r in rows2:
        if r['id'] not in existing_ids and r['id'] not in posted_ids and r['link'] not in posted_links:
            r['priority'] = 2
            articles.append(r)
            existing_ids.add(r['id'])
    log(f'  2순위 최근7일: {len(rows2)}개 중 신규 {len([a for a in articles if a["priority"]==2])}개')

    # 3순위: 이전 기사
    if len(articles) < 50:
        remaining = 50 - len(articles)
        existing_ids = set(a['id'] for a in articles)
        sql3 = f"""SELECT id, title, link, description, source, pub_date, '' as comment
                   FROM news
                   WHERE pub_date < date('now', '-7 days')
                   ORDER BY pub_date DESC LIMIT {remaining + 20}"""
        rows3 = d1_query(sql3)
        for r in rows3:
            if r['id'] not in existing_ids and r['id'] not in posted_ids and r['link'] not in posted_links:
                r['priority'] = 3
                articles.append(r)
                existing_ids.add(r['id'])
        log(f'  3순위 이전: 신규 {len([a for a in articles if a["priority"]==3])}개')

    log(f'  총 기사 풀: {len(articles)}개')
    return articles


if __name__ == '__main__':
    articles = get_articles()
    p1 = sum(1 for a in articles if a['priority'] == 1)
    p2 = sum(1 for a in articles if a['priority'] == 2)
    p3 = sum(1 for a in articles if a['priority'] == 3)
    print(f'\n기사 풀 현황: 브리핑 {p1}개 + 최근7일 {p2}개 + 이전 {p3}개 = 총 {len(articles)}개')
    for a in articles[:5]:
        print(f'  [P{a["priority"]}] [{a["id"]}] {a["title"][:55]}')
    if len(articles) > 5:
        print(f'  ... 외 {len(articles)-5}개')
