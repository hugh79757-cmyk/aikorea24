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

def normalize_url(url):
    """URL 정규화: 쿼리 파라미터 제거, 트래일링 슬래시 제거, 소문자"""
    if not url:
        return ''
    url = url.split('?')[0].split('#')[0]
    url = url.rstrip('/')
    return url.lower()

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
    """GET 요청으로 URL이 유효한지 확인 (2xx만 True)
    3xx redirect는 존재하지 않는 URL이 홈페이지로 리디렉션되는 경우가 많으므로 False
    """
    if not url or not url.startswith('http'):
        return False
    try:
        req = urllib.request.Request(url, method='GET',
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            # 2xx만 유효. 3xx redirect는 거부 (URL 오류 가능성)
            return 200 <= resp.status < 300
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
            data = json.load(f)
        # posted_ids를 모두 str로 통일 (int/str 혼재 해결)
        data['posted_ids'] = [str(x) for x in data.get('posted_ids', [])]
        # 기존 posted_urls → posted_links로 병합 후 제거
        if 'posted_urls' in data:
            links = set(data.get('posted_links', []))
            links.update(data.get('posted_urls', []))
            data['posted_links'] = list(links)
            del data['posted_urls']
        # 새 필드 기본값
        data.setdefault('posted_titles', [])
        data.setdefault('posted_original_titles', [])
        # 하위 호환: posted_links를 normalize하여 중복 정리
        normalized_links = set()
        for link in data.get('posted_links', []):
            normalized_links.add(normalize_url(link) if link else '')
        data['posted_links'] = list(normalized_links - {''})
        return data
    return {"posted_links": [], "posted_ids": [], "posted_titles": [], "posted_original_titles": [], "history": [], "last_reset": ""}

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

def is_already_posted(article, posted):
    """4조건 중 하나라도 매칭되면 발행된 기사로 판정 (link, title, original_title, id)"""
    aid = str(article.get('id', ''))
    link = normalize_url(article.get('link', ''))
    title = (article.get('title', '') or '')[:30]
    original_title = (article.get('original_title', '') or '')[:30]

    # 1. id 매칭
    if aid and aid in posted.get('posted_ids', []):
        return True
    # 2. link 매칭 (정규화)
    if link and link in set(normalize_url(l) for l in posted.get('posted_links', [])):
        return True
    # 3. title[:30] 매칭
    if title and title in set(t[:30] for t in posted.get('posted_titles', [])):
        return True
    # 4. original_title[:30] 매칭 (비어있으면 스킵)
    if original_title and original_title in set(ot[:30] for ot in posted.get('posted_original_titles', [])):
        return True
    return False

def get_exclusion_reasons(article, posted):
    """기사가 어떤 필드로 제외되는지 reasons set 반환 (여러 필드 동시에 매칭 가능)"""
    reasons = set()
    aid = str(article.get('id', ''))
    link = normalize_url(article.get('link', ''))
    title = (article.get('title', '') or '')[:30]
    original_title = (article.get('original_title', '') or '')[:30]

    posted_ids = posted.get('posted_ids', [])
    posted_links_norm = set(normalize_url(l) for l in posted.get('posted_links', []))
    posted_titles_set = set(t[:30] for t in posted.get('posted_titles', []))
    posted_orig_titles_set = set(ot[:30] for ot in posted.get('posted_original_titles', []))

    if aid and aid in posted_ids:
        reasons.add('posted_ids')
    if link and link in posted_links_norm:
        reasons.add('posted_links')
    if title and title in posted_titles_set:
        reasons.add('posted_titles')
    if original_title and original_title in posted_orig_titles_set:
        reasons.add('posted_original_titles')
    return reasons

def get_articles():
    """3단계 우선순위 기사 풀 반환"""
    posted = load_posted()
    today = datetime.now().strftime('%Y-%m-%d')

    articles = []
    total_queried = 0
    total_excluded = 0
    field_excludes = {'posted_ids': 0, 'posted_links': 0, 'posted_titles': 0, 'posted_original_titles': 0}

    # 1순위: 오늘 브리핑
    sql1 = f"""SELECT n.id, n.title, n.link, n.description, n.source, n.pub_date,
                      COALESCE(bi.comment, '') as comment,
                      COALESCE(n.original_title, '') as original_title
               FROM news n
               JOIN briefing_items bi ON bi.news_id = n.id
               JOIN briefings b ON b.id = bi.briefing_id
               WHERE b.date = '{today}' AND b.status = 'published'
               GROUP BY n.id ORDER BY bi.sort_order ASC"""
    rows = d1_query(sql1)
    total_queried += len(rows)
    for r in rows:
        reasons = get_exclusion_reasons(r, posted)
        if reasons:
            total_excluded += 1
            for field in reasons:
                field_excludes[field] += 1
        else:
            r['priority'] = 1
            articles.append(r)
    log(f'  1순위 브리핑: {len(rows)}개 → 신규 {len([a for a in articles if a["priority"]==1])}개')

    # 2순위: 최근 7일 news (브리핑 제외)
    existing_ids = set(str(a['id']) for a in articles)
    sql2 = f"""SELECT id, title, link, description, source, pub_date, '' as comment,
                      COALESCE(original_title, '') as original_title
               FROM news
               WHERE 
                 CASE 
                   WHEN pub_date LIKE '____-__-__%' THEN substr(pub_date, 1, 10)
                   WHEN pub_date LIKE '___, __ %' THEN 
                     substr(pub_date, 13, 4) || '-' || 
                     CASE substr(pub_date, 9, 3)
                       WHEN 'Jan' THEN '01' WHEN 'Feb' THEN '02' WHEN 'Mar' THEN '03'
                       WHEN 'Apr' THEN '04' WHEN 'May' THEN '05' WHEN 'Jun' THEN '06'
                       WHEN 'Jul' THEN '07' WHEN 'Aug' THEN '08' WHEN 'Sep' THEN '09'
                       WHEN 'Oct' THEN '10' WHEN 'Nov' THEN '11' WHEN 'Dec' THEN '12'
                     END || '-' || 
                     CASE WHEN length(substr(pub_date, 6, 2)) = 1 THEN '0' || substr(pub_date, 6, 2) ELSE substr(pub_date, 6, 2) END
                   ELSE NULL
                 END >= date('now', '-7 days')
               ORDER BY pub_date DESC LIMIT 2000"""
    rows2 = d1_query(sql2)
    total_queried += len(rows2)
    for r in rows2:
        if str(r['id']) in existing_ids:
            total_excluded += 1
            field_excludes['posted_ids'] += 1
        else:
            reasons = get_exclusion_reasons(r, posted)
            if reasons:
                total_excluded += 1
                for field in reasons:
                    field_excludes[field] += 1
            else:
                r['priority'] = 2
                articles.append(r)
                existing_ids.add(str(r['id']))
    log(f'  2순위 최근7일: {len(rows2)}개 중 신규 {len([a for a in articles if a["priority"]==2])}개')

    # 3순위: 이전 기사
    if len(articles) < 50:
        remaining = 50 - len(articles)
        existing_ids = set(str(a['id']) for a in articles)
        sql3 = f"""SELECT id, title, link, description, source, pub_date, '' as comment,
                          COALESCE(original_title, '') as original_title
                   FROM news
                   WHERE 
                     CASE 
                       WHEN pub_date LIKE '____-__-__%' THEN substr(pub_date, 1, 10)
                       WHEN pub_date LIKE '___, __ %' THEN 
                         substr(pub_date, 13, 4) || '-' || 
                         CASE substr(pub_date, 9, 3)
                           WHEN 'Jan' THEN '01' WHEN 'Feb' THEN '02' WHEN 'Mar' THEN '03'
                           WHEN 'Apr' THEN '04' WHEN 'May' THEN '05' WHEN 'Jun' THEN '06'
                           WHEN 'Jul' THEN '07' WHEN 'Aug' THEN '08' WHEN 'Sep' THEN '09'
                           WHEN 'Oct' THEN '10' WHEN 'Nov' THEN '11' WHEN 'Dec' THEN '12'
                         END || '-' || 
                         CASE WHEN length(substr(pub_date, 6, 2)) = 1 THEN '0' || substr(pub_date, 6, 2) ELSE substr(pub_date, 6, 2) END
                       ELSE NULL
                     END < date('now', '-7 days')
                   ORDER BY pub_date DESC LIMIT {remaining + 20}"""
        rows3 = d1_query(sql3)
        total_queried += len(rows3)
        for r in rows3:
            if str(r['id']) in existing_ids:
                total_excluded += 1
                field_excludes['posted_ids'] += 1
            else:
                reasons = get_exclusion_reasons(r, posted)
                if reasons:
                    total_excluded += 1
                    for field in reasons:
                        field_excludes[field] += 1
                else:
                    r['priority'] = 3
                    articles.append(r)
                    existing_ids.add(str(r['id']))
        log(f'  3순위 이전: 신규 {len([a for a in articles if a["priority"]==3])}개')

    log(f'  총 기사 풀: {len(articles)}개')
    log(f'  [기사 풀 필터] 전체: {total_queried}개 → 제외: {total_excluded}개 → 최종: {len(articles)}개')
    log(f'    posted_ids 제외: {field_excludes["posted_ids"]}개 | posted_links 제외: {field_excludes["posted_links"]}개 | posted_titles 제외: {field_excludes["posted_titles"]}개 | posted_original_titles 제외: {field_excludes["posted_original_titles"]}개')
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
