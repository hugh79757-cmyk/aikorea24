"""
aikorea24 브리핑 → 네이버 블로그 자동 발행
사용법: python publish_briefing.py              (오늘 브리핑)
       python publish_briefing.py 2026-03-20    (특정 날짜)
       python publish_briefing.py --dry-run     (발행 없이 미리보기)
"""
import sys
import os
import json
import requests
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(__file__))
from publish import publish

SITE_URL = "https://aikorea24.kr"
API_BASE = "https://aikorea24.kr/api"


def fetch_briefing(target_date):
    """aikorea24에서 브리핑 데이터 가져오기"""
    url = f"{SITE_URL}/briefing/{target_date}/"
    print(f"브리핑 페이지 확인: {url}")

    # 방법 1: API 엔드포인트가 있으면 사용
    api_url = f"{API_BASE}/briefing/{target_date}"
    try:
        resp = requests.get(api_url, timeout=10)
        resp.encoding = 'utf-8'
        if resp.status_code == 200:
            data = resp.json()
            if data.get("items"):
                return data
    except Exception:
        pass

    # 방법 2: 페이지 HTML에서 파싱
    try:
        resp = requests.get(url, timeout=10)
        resp.encoding = 'utf-8'
        if resp.status_code == 200:
            return parse_briefing_html(resp.text, target_date)
    except Exception as e:
        print(f"브리핑 가져오기 실패: {e}")

    return None


def parse_briefing_html(html, target_date):
    """브리핑 HTML에서 기사 추출"""
    import re
    items = []

    # article 블록 추출
    articles = re.findall(r'<article[^>]*class="article"[^>]*>(.*?)</article>', html, re.DOTALL)
    if not articles:
        # div 기반 추출
        articles = re.findall(r'class="article"[^>]*>(.*?)</(?:article|div)>', html, re.DOTALL)

    for art in articles:
        title_m = re.search(r'class="article-title"[^>]*>(.*?)</div>', art, re.DOTALL)
        comment_m = re.search(r'class="article-comment"[^>]*>(.*?)</div>', art, re.DOTALL)
        desc_m = re.search(r'class="article-desc"[^>]*>(.*?)</div>', art, re.DOTALL)
        source_m = re.search(r'class="source-link"[^>]*href="([^"]*)"', art)

        title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else ""
        comment = re.sub(r'<[^>]+>', '', comment_m.group(1)).strip() if comment_m else ""
        desc = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip() if desc_m else ""
        source = source_m.group(1) if source_m else ""

        if title:
            items.append({
                "title": title,
                "comment": comment,
                "description": desc,
                "source_link": source
            })

    return {"date": target_date, "items": items} if items else None


def format_blog_html(briefing_data):
    """브리핑 데이터를 네이버 블로그 HTML로 변환"""
    target_date = briefing_data["date"]
    items = briefing_data["items"]

    d = datetime.strptime(target_date, "%Y-%m-%d")
    weekday = ['월', '화', '수', '목', '금', '토', '일'][d.weekday()]
    display = f"{d.year}년 {d.month}월 {d.day}일 ({weekday})"

    lines = []
    lines.append(f"📋 {display} AI 브리핑")
    lines.append(f"AI코리아24에서 큐레이션한 오늘의 주요 AI 뉴스 {len(items)}건입니다.")
    lines.append("")

    for i, item in enumerate(items, 1):
        lines.append(f"━━━━━━━━━━━━━━━━━━")
        lines.append(f"📌 {i}. {item['title']}")
        lines.append("")
        if item.get("comment"):
            lines.append(f"💬 {item['comment']}")
            lines.append("")
        if item.get("description"):
            lines.append(item["description"])
            lines.append("")
        if item.get("source_link"):
            lines.append(f"🔗 원문: {item['source_link']}")
            lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append(f"✅ 전체 브리핑 보기: {SITE_URL}/briefing/{target_date}/")
    lines.append(f"✅ AI코리아24: {SITE_URL}")
    lines.append("")
    lines.append("#AI뉴스 #AI브리핑 #인공지능 #AI코리아24 #오늘의AI")

    body_html = "<br>".join(lines)
    # HTML 엔티티 디코딩
    import html as _html
    body_html = _html.unescape(body_html)
    return body_html


def main():
    dry_run = "--dry-run" in sys.argv

    if len(sys.argv) >= 2 and sys.argv[1] != "--dry-run":
        target_date = sys.argv[1]
    else:
        target_date = date.today().strftime("%Y-%m-%d")

    print(f"📅 대상 날짜: {target_date}")

    briefing = fetch_briefing(target_date)
    if not briefing or not briefing.get("items"):
        print(f"브리핑 데이터 없음: {target_date}")
        sys.exit(1)

    print(f"📰 기사 {len(briefing['items'])}건 수집")

    d = datetime.strptime(target_date, "%Y-%m-%d")
    title = f"[AI 브리핑] {d.month}월 {d.day}일 주요 AI 뉴스 {len(briefing['items'])}건"
    body_html = format_blog_html(briefing)
    tags = "AI,인공지능,AI뉴스,AI브리핑,AI코리아24"

    if dry_run:
        print(f"\n{'='*50}")
        print(f"[DRY RUN] 제목: {title}")
        print(f"[DRY RUN] 태그: {tags}")
        print(f"[DRY RUN] 본문 미리보기:")
        print(body_html[:500])
        print(f"{'='*50}")
    else:
        result = publish(title, body_html, tags=tags, category_no=1)
        if result:
            print(f"\n🎉 브리핑 발행 완료: {result}")
        else:
            print("\n❌ 브리핑 발행 실패")


if __name__ == "__main__":
    main()
