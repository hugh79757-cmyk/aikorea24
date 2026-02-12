#!/usr/bin/env python3
"""RSS 인코딩 수정 테스트"""

import requests
from bs4 import BeautifulSoup

rss_feeds = {
    "과기정통부": "https://www.korea.kr/rss/dept_msit.xml",
    "정책뉴스": "https://www.korea.kr/rss/policy.xml",
    "보도자료": "https://www.korea.kr/rss/pressrelease.xml",
}

ai_keywords = ['AI', '인공지능', '바우처', '데이터', '디지털', 'GPT', '생성형', 'ICT', '클라우드']

for name, url in rss_feeds.items():
    print(f"\n📡 [{name}] {url}")
    r = requests.get(url, timeout=10)
    r.encoding = 'utf-8'  # 핵심: 인코딩 강제 지정
    
    soup = BeautifulSoup(r.content, 'xml')
    items = soup.find_all('item')
    
    ai_items = []
    for item in items:
        title = item.find('title').get_text(strip=True) if item.find('title') else ""
        link = item.find('link').get_text(strip=True) if item.find('link') else ""
        desc = item.find('description').get_text(strip=True) if item.find('description') else ""
        pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""
        
        if any(kw in (title + desc) for kw in ai_keywords):
            ai_items.append({"title": title, "link": link, "date": pub})
    
    print(f"  전체: {len(items)}건 | AI관련: {len(ai_items)}건")
    for i, a in enumerate(ai_items[:5], 1):
        print(f"  {i}. {a['title'][:70]}")
        print(f"     {a['date']}")

print("\n" + "=" * 60)
print("위 제목이 한글로 정상 출력되면 인코딩 수정 완료!")
