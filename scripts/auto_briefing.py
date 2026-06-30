#!/usr/bin/env python3
"""aikorea24 브리핑 자동 생성기"""

import subprocess
import sys
from datetime import datetime, timedelta, timezone
import os
import requests
from pathlib import Path

KST = timezone(timedelta(hours=9))
PROJECT_DIR = "/Users/twinssn/Projects/aikorea24"

# Load API key from .env.common
_env_path = os.path.expanduser("~/.env.common")
_mimo_key = ""
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            if line.startswith("MIMO_API_KEY="):
                _mimo_key = line.split("=", 1)[1].strip()
                break

MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"
MIMO_MODEL = "mimo-v2.5"

sys.path.insert(0, str(Path(__file__).parent))
from auto_news_selector import get_recent_news, cluster_by_topic, select_top_articles, d1_query

def log(msg):
    ts = datetime.now(KST).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def d1_execute(sql):
    """D1 INSERT/UPDATE/DELETE 실행"""
    cmd = ["npx", "wrangler", "d1", "execute", "aikorea24-db", "--remote", "--command", sql]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=PROJECT_DIR)
        if r.returncode != 0:
            log(f"  D1 실행 오류 (rc={r.returncode}): {r.stderr[:200]}")
            return False
        return True
    except Exception as e:
        log(f"  D1 예외: {e}")
        return False

def generate_comment(article):
    """MiMo API로 기사 코멘트 생성"""
    title = article.get("title", "")
    description = (article.get("description") or "")[:300]
    source = article.get("source", "")

    prompt = (
        f"다음 AI 뉴스에 대해 1~2문장의 간결한 한국어 코멘트를 작성해줘.\n\n"
        f"제목: {title}\n"
        f"출처: {source}\n"
        f"내용: {description}\n\n"
        f"코멘트:"
    )

    try:
        resp = requests.post(
            f"{MIMO_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {_mimo_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": MIMO_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
                "temperature": 0.5,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            log(f"  API 오류 ({resp.status_code}): {resp.text[:200]}")
            return None
        data = resp.json()
        comment = data["choices"][0]["message"]["content"].strip()
        if not comment:
            return None
        return comment
    except Exception as e:
        log(f"  API 예외: {e}")
        return None


def build_briefing(articles):
    """브리핑 데이터 구성 (intro + items)"""
    today = datetime.now(KST).strftime("%Y-%m-%d")

    intro = (
        f"오늘의 AI 뉴스 브리핑 ({today})\n\n"
        f"{len(articles)}건의 주요 AI 뉴스를 선정했습니다."
    )

    items = []
    for i, a in enumerate(articles):
        items.append({
            "news_id": a.get("id"),
            "sort_order": i + 1,
            "comment": a.get("comment", ""),
        })

    return {"date": today, "intro": intro, "status": "published", "items": items}


def save_briefing(data):
    """D1 DB에 브리핑 저장. 성공 시 briefing_id, 실패 시 None 반환."""
    today_base = data["date"][:10]
    intro_escaped = data["intro"].replace("'", "''")

    existing = d1_query(f"SELECT id, date FROM briefings WHERE date LIKE '{today_base}%' ORDER BY date DESC")
    if existing:
        last_date = existing[0]['date']
        last_seq = int(last_date.split('-')[-1]) if '-' in last_date[10:] else 0
        seq = last_seq + 1
    else:
        seq = 1

    date_with_seq = f"{today_base}-{seq}"
    data["date"] = date_with_seq

    sql_briefing = (
        f"INSERT INTO briefings (date, intro, status, published_at, created_at) "
        f"VALUES ('{date_with_seq}', '{intro_escaped}', 'published', datetime('now'), datetime('now'))"
    )
    if not d1_execute(sql_briefing):
        log("  브리핑 생성 실패")
        return None

    rows = d1_query(f"SELECT id FROM briefings WHERE date = '{date_with_seq}'")
    if not rows:
        log("  브리핑 ID 조회 실패")
        return None
    briefing_id = rows[0]["id"]
    log(f"  브리핑 id={briefing_id} 저장 (date={date_with_seq})")

    for item in data["items"]:
        comment_escaped = (item.get("comment") or "").replace("'", "''")
        news_id = item["news_id"]
        sort_order = item["sort_order"]
        sql_item = (
            f"INSERT INTO briefing_items (briefing_id, news_id, sort_order, comment) "
            f"VALUES ({briefing_id}, {news_id}, {sort_order}, '{comment_escaped}')"
        )
        if not d1_execute(sql_item):
            log(f"  sort_order={sort_order} 아이템 저장 실패")

    log(f"  {len(data['items'])}개 아이템 저장 완료")
    return briefing_id


def main(selected_articles=None):
    log("=== aikorea24 브리핑 자동 생성 ===")
    print()

    # 1. 뉴스 선정
    log("[1/4] 뉴스 조회 및 선정")
    from briefing_dedup import filter_duplicates, record_briefing

    if selected_articles is not None:
        selected = selected_articles
        log(f"  외부 선정 사용: {len(selected)}개 기사")
    else:
        articles = get_recent_news(hours=48)
        if not articles:
            log("  수집된 뉴스 없음")
            return

        clusters = cluster_by_topic(articles)
        for cluster_name, cluster_articles in clusters.items():
            for art in cluster_articles:
                art["cluster"] = cluster_name
        selected = select_top_articles(clusters, max_count=6)
        log(f"  선정: {len(selected)}개 기사")

        # Phase 2 중복 방어 (저장 전 재검증)
        cutoff, removed = filter_duplicates(selected, d1_query)
        if removed:
            log(f"  ⚠️ 중복 제거: {len(removed)}건")
            for art, reason in removed:
                title = (art.get("title") or "")[:50]
                log(f"    [{reason}] {title}")
        selected = cutoff

    if not selected:
        log("  ⚠️ 선정된 기사 없음")
        print()
        return

    print()

    # 2. 코멘트 생성
    log("[2/4] 코멘트 생성")
    for art in selected:
        title = (art.get("title") or "")[:50]
        log(f"  → {title}")
        comment = generate_comment(art)
        if comment:
            art["comment"] = comment
            log(f"    ✅ {comment[:60]}...")
        else:
            art["comment"] = ""
            log(f"    ❌ 코멘트 생성 실패")
    print()

    # 3. 브리핑 구성
    log("[3/4] 브리핑 데이터 구성")
    briefing_data = build_briefing(selected)
    log(f"  날짜: {briefing_data['date']}")
    log(f"  아이템: {len(briefing_data['items'])}개")
    print()

    # 4. D1 저장
    log("[4/4] D1 DB 저장")
    briefing_id = save_briefing(briefing_data)
    if briefing_id:
        record_briefing(briefing_id, selected, d1_query)
    print()

    log("=== 완료 ===")
    return briefing_id


if __name__ == "__main__":
    main()
