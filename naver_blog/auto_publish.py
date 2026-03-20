"""
하루 3회 네이버 블로그 자동 발행
- 하루 최대 3건 (브리핑 1 + 블로그 2, 또는 블로그 3)
- 맥북 꺼져서 밀린 건 무시 (하루 3건 초과 방지)
- 발행 실패 시 텔레그램 알림
사용법: python auto_publish.py
       python auto_publish.py --dry-run
"""
import sys
import os
import json
import random
import time
import requests
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(__file__))
from publish_blog import get_all_posts, publish_one, load_published
from publish_briefing import fetch_briefing, format_blog_html
from publish import publish as publish_requests
from cookie_monitor import check_cookie, send_telegram

BRIEFING_PUBLISHED_FILE = os.path.join(os.path.dirname(__file__), "published_briefings.json")
DAILY_LOG_FILE = os.path.join(os.path.dirname(__file__), "daily_publish_log.json")
MAX_DAILY = 3


def load_briefing_published():
    if os.path.exists(BRIEFING_PUBLISHED_FILE):
        with open(BRIEFING_PUBLISHED_FILE, "r") as f:
            return json.load(f)
    return []


def save_briefing_published(dates):
    with open(BRIEFING_PUBLISHED_FILE, "w") as f:
        json.dump(dates, f, ensure_ascii=False, indent=2)


def get_today_count():
    """오늘 발행 건수 확인 (하루 3건 제한)"""
    today = date.today().strftime("%Y-%m-%d")
    if os.path.exists(DAILY_LOG_FILE):
        with open(DAILY_LOG_FILE, "r") as f:
            log = json.load(f)
    else:
        log = {}
    return log.get(today, 0), log, today


def increment_today_count(log, today):
    log[today] = log.get(today, 0) + 1
    # 7일 이전 기록 삭제
    keys = sorted(log.keys())
    while len(keys) > 7:
        del log[keys.pop(0)]
    with open(DAILY_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


def publish_today_briefing(dry_run=False):
    """오늘 브리핑 발행 (requests 방식)"""
    today = date.today().strftime("%Y-%m-%d")
    published = load_briefing_published()

    if today in published:
        print(f"[브리핑] 이미 발행됨: {today}")
        return None

    briefing = fetch_briefing(today)
    if not briefing or not briefing.get("items"):
        print(f"[브리핑] 데이터 없음: {today}")
        return None

    d = datetime.strptime(today, "%Y-%m-%d")
    title = f"[AI 브리핑] {d.month}월 {d.day}일 주요 AI 뉴스 {len(briefing['items'])}건"
    body_html = format_blog_html(briefing)
    import html as _html
    body_html = _html.unescape(body_html)
    tags = "AI,인공지능,AI뉴스,AI브리핑,AI코리아24"

    if dry_run:
        print(f"[브리핑 DRY RUN] {title}")
        return "dry-run"

    result = publish_requests(title, body_html, tags=tags, category_no=6)
    if result:
        published.append(today)
        save_briefing_published(published)
        print(f"[브리핑] 발행 완료: {today}")
        return result
    else:
        send_telegram(
            f"\u274c <b>[AI코리아24] 브리핑 발행 실패</b>\n\n"
            f"날짜: {today}\n"
            f"제목: {title}\n\n"
            f"수동 발행:\n"
            f"<code>cd ~/Projects/aikorea24/naver_blog\npython publish_briefing.py</code>"
        )
        return None


def publish_random_blog(dry_run=False):
    """미발행 블로그 글 중 무작위 1개 발행 (Playwright 방식)"""
    posts = get_all_posts()
    published = load_published()
    unpublished = [p for p in posts if p["slug"] not in published]

    if not unpublished:
        print("[블로그] 모든 글 발행 완료!")
        return None

    post = random.choice(unpublished)
    print(f"[블로그] 선택: [{post['category']}] {post['title'][:40]}...")

    if dry_run:
        print(f"[블로그 DRY RUN] slug: {post['slug']}")
        return "dry-run"

    try:
        result = publish_one(post["slug"])
        if result:
            return result
        else:
            send_telegram(
                f"\u274c <b>[AI코리아24] 블로그 글 발행 실패</b>\n\n"
                f"슬러그: {post['slug']}\n"
                f"제목: {post['title'][:40]}\n\n"
                f"수동 발행:\n"
                f"<code>cd ~/Projects/aikorea24/naver_blog\n"
                f"python publish_blog.py --slug {post['slug']}</code>"
            )
            return None
    except Exception as e:
        send_telegram(
            f"\u274c <b>[AI코리아24] 발행 에러</b>\n\n"
            f"슬러그: {post['slug']}\n"
            f"에러: {str(e)[:200]}"
        )
        return None


def main():
    dry_run = "--dry-run" in sys.argv
    print(f"\n{'='*50}")
    print(f"네이버 자동 발행: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}\n")

    # 하루 3건 제한 체크
    today_count, log, today = get_today_count()
    remaining = MAX_DAILY - today_count
    if remaining <= 0:
        print(f"오늘 이미 {today_count}건 발행 완료. 내일 다시 실행됩니다.")
        return
    print(f"오늘 발행: {today_count}/{MAX_DAILY}건, 남은 횟수: {remaining}건")

    # 쿠키 체크
    if not dry_run and not check_cookie():
        print("쿠키 만료! 발행 중단.")
        return

    published_count = 0

    # 1) 브리핑 발행 (있으면)
    if remaining > 0:
        print(f"\n--- 브리핑 ---")
        result = publish_today_briefing(dry_run)
        if result:
            published_count += 1
            remaining -= 1
            if not dry_run:
                increment_today_count(log, today)
                time.sleep(5)

    # 2) 블로그 글 발행 (남은 횟수만큼)
    for i in range(remaining):
        print(f"\n--- 블로그 글 ({i+1}/{remaining}) ---")
        result = publish_random_blog(dry_run)
        if result:
            published_count += 1
            if not dry_run:
                increment_today_count(log, today)
                if i < remaining - 1:
                    wait = random.randint(30, 60)
                    print(f"다음 발행까지 {wait}초 대기...")
                    time.sleep(wait)

    print(f"\n{'='*50}")
    print(f"완료: 오늘 {published_count}건 발행 (누적 {today_count + published_count}/{MAX_DAILY})")
    print(f"{'='*50}")

    # 텔레그램 완료 알림
    if not dry_run and published_count > 0:
        posts = get_all_posts()
        pub = load_published()
        remain_blog = len(posts) - len(pub)
        send_telegram(
            f"\u2705 <b>[AI코리아24] 네이버 자동 발행</b>\n\n"
            f"발행: {published_count}건 (오늘 누적 {today_count + published_count}/{MAX_DAILY})\n"
            f"남은 블로그 글: {remain_blog}개\n"
            f"시각: {datetime.now().strftime('%H:%M')}"
        )


if __name__ == "__main__":
    main()
