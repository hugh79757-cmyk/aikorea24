#!/usr/bin/env python3
"""노인복지 뉴스 수집 + 원문 크롤링 → 데이터 리스트 (v3: AI 없이 드라이하게)"""

import os, sys, json, subprocess, re, time
import httpx
from datetime import datetime
from html import unescape

PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'
OUTPUT_DIR = os.path.join(PROJECT_DIR, 'api_test', 'senior_briefing')


def get_senior_news():
    r = subprocess.run(
        ['npx', 'wrangler', 'd1', 'execute', 'aikorea24-db', '--remote', '--json',
         '--command', "SELECT title, description, link, pub_date FROM news WHERE category='senior' ORDER BY created_at DESC LIMIT 30"],
        capture_output=True, text=True, cwd=PROJECT_DIR, timeout=120)
    if r.returncode != 0:
        return []
    data = json.loads(r.stdout)
    return data[0].get('results', []) if data else []


def clean_html(text):
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def fetch_article(url, timeout=10):
    """원문 크롤링 → 본문 텍스트 추출"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            resp = client.get(url, headers=headers)
            html = resp.text

        patterns = [
            r'<article[^>]*id="dic_area"[^>]*>(.*?)</article>',
            r'<div[^>]*class="[^"]*article_body[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*id="articleBodyContents"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*newsct_article[^"]*"[^>]*>(.*?)</div>',
            r'<article[^>]*>(.*?)</article>',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.DOTALL)
            if m:
                return clean_html(m.group(1))[:1500]

        # 패턴 못 찾으면 meta description
        m = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html)
        if m:
            return unescape(m.group(1))

        return ''
    except Exception as e:
        return f'(크롤링 실패: {e})'


def generate_html(items, today):
    rows = ''
    for i, item in enumerate(items, 1):
        body_preview = item.get('body', '')[:300]
        if body_preview:
            body_preview = f'<div class="body">{body_preview}...</div>'

        rows += f'''
        <div class="card">
          <div class="num">{i}</div>
          <div class="info">
            <a href="{item['link']}" target="_blank" class="title">{item['title']}</a>
            <div class="desc">{item['description']}</div>
            {body_preview}
            <div class="meta">{item['pub_date']} | {item.get('source', '')}</div>
          </div>
        </div>'''

    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>노인복지 뉴스 - {today}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         background:#0f172a; color:#e2e8f0; padding:20px; line-height:1.6; }}
  .container {{ max-width:900px; margin:0 auto; }}
  .header {{ background:#1e293b; border:1px solid #334155; border-radius:12px;
             padding:24px; margin-bottom:24px; }}
  .header h1 {{ color:#fbbf24; font-size:22px; }}
  .header .meta {{ color:#94a3b8; font-size:13px; margin-top:4px; }}
  .card {{ background:#1e293b; border:1px solid #334155; border-radius:12px;
           padding:16px; margin-bottom:12px; display:flex; gap:14px;
           transition:border-color 0.2s; }}
  .card:hover {{ border-color:#475569; }}
  .num {{ color:#fbbf24; font-weight:700; font-size:18px; min-width:28px; padding-top:2px; }}
  .info {{ flex:1; }}
  .title {{ color:#38bdf8; font-weight:600; font-size:15px; text-decoration:none; }}
  .title:hover {{ text-decoration:underline; }}
  .desc {{ color:#94a3b8; font-size:13px; margin-top:6px; }}
  .body {{ color:#cbd5e1; font-size:13px; margin-top:8px; padding:10px;
           background:#0f172a; border-radius:8px; border:1px solid #1e293b; }}
  .meta {{ color:#64748b; font-size:11px; margin-top:8px; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>노인복지 뉴스 브리핑</h1>
    <div class="meta">{today} | {len(items)}건 | 클릭하면 원문으로 이동</div>
  </div>
  {rows}
</div>
</body>
</html>'''


def update_index():
    files = sorted(
        [f for f in os.listdir(OUTPUT_DIR) if f.endswith('.html') and f != 'index.html'],
        reverse=True
    )
    items_html = ''
    for f in files:
        date = f.replace('.html', '')
        items_html += f'''
        <a href="{f}" class="item">
          <span class="date">{date}</span>
          <span class="arrow">&rarr;</span>
        </a>'''

    html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>노인복지 브리핑 목록</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         background:#0f172a; color:#e2e8f0; padding:20px; }}
  .container {{ max-width:600px; margin:0 auto; }}
  h1 {{ color:#fbbf24; font-size:24px; margin-bottom:20px; }}
  .item {{ display:flex; justify-content:space-between; align-items:center;
           background:#1e293b; border:1px solid #334155; border-radius:12px;
           padding:16px 20px; margin-bottom:10px; text-decoration:none;
           color:#e2e8f0; transition:all 0.2s; }}
  .item:hover {{ background:#334155; transform:translateX(4px); }}
  .date {{ font-size:16px; font-weight:600; }}
  .arrow {{ color:#38bdf8; }}
  .count {{ color:#94a3b8; font-size:14px; margin-bottom:20px; }}
</style>
</head>
<body>
<div class="container">
  <h1>노인복지 브리핑 목록</h1>
  <p class="count">총 {len(files)}개</p>
  {items_html}
</div>
</body>
</html>'''

    with open(os.path.join(OUTPUT_DIR, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)


def main():
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"노인복지 뉴스 브리핑 ({today})")
    print("=" * 50)

    # 1. D1에서 뉴스 조회
    print("\n[1] D1 뉴스 조회...")
    news = get_senior_news()
    print(f"    {len(news)}건")
    if not news:
        print("    뉴스 없음. 먼저 수집 실행 필요.")
        return

    # 2. 각 뉴스 원문 크롤링
    print("\n[2] 원문 크롤링...")
    for i, item in enumerate(news):
        print(f"    {i+1}/{len(news)} {item['title'][:40]}...", end=' ')
        item['body'] = fetch_article(item['link'])
        status = f"{len(item['body'])}자" if item['body'] else "실패"
        print(status)
        time.sleep(0.5)

    # 3. HTML 저장
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    html = generate_html(news, today)
    html_path = os.path.join(OUTPUT_DIR, f'{today}.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"\n[3] 저장: {html_path}")

    update_index()
    print("    index.html 업데이트")
    print(f"\n웹에서 보기: file://{html_path}")


if __name__ == '__main__':
    main()
