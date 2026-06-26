#!/usr/bin/env python3
"""aikorea24 이메일 자동 발송기"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def load_env():
    """~/.env.common에서 환경변수 로드"""
    env_path = os.path.expanduser("~/.env.common")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    # 프로젝트 .env도 로드 (우선)
    project_env = Path(__file__).resolve().parent.parent / ".env"
    if project_env.exists():
        with open(project_env) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()


def get_today_briefing():
    """D1에서 오늘 브리핑 조회"""
    today = datetime.now().strftime("%Y-%m-%d")

    query = f"""
    SELECT b.id, b.date, b.intro, b.status,
           GROUP_CONCAT(bi.news_id) as news_ids
    FROM briefings b
    LEFT JOIN briefing_items bi ON b.id = bi.briefing_id
    WHERE b.date = '{today}' AND b.status = 'published'
    GROUP BY b.id
    """

    result = subprocess.run(
        ["wrangler", "d1", "execute", "aikorea24-db", "--remote", "--command", query],
        capture_output=True, text=True
    )

    rows = _parse_d1_results(result.stdout)
    return rows[0] if rows else None


def get_briefing_items(briefing_id):
    """브리핑 아이템 조회"""
    query = f"""
    SELECT bi.*, n.title as news_title, n.description as news_desc,
           n.link as news_link, n.source as news_source
    FROM briefing_items bi
    LEFT JOIN news n ON bi.news_id = n.id
    WHERE bi.briefing_id = {briefing_id}
    ORDER BY bi.sort_order ASC
    """

    result = subprocess.run(
        ["wrangler", "d1", "execute", "aikorea24-db", "--remote", "--command", query],
        capture_output=True, text=True
    )

    return _parse_d1_results(result.stdout)


def _parse_d1_results(stdout):
    """wrangler d1 execute JSON 출력에서 results 배열 추출"""
    m = re.search(r'"results"\s*:\s*(\[[\s\S]*?\])\s*,\s*"success"', stdout)
    if m:
        return json.loads(m.group(1))
    return []


def send_email_via_brevo(briefing, items):
    """Brevo API로 이메일 발송"""
    load_env()

    api_key = os.environ.get("BREVO_API_KEY")

    if not api_key:
        print("❌ BREVO_API_KEY not set")
        return False

    html = generate_email_html(briefing, items)

    import requests

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json"
    }

    # 수신자 설정: SUBSCRIBER_EMAIL > BREVO_LIST_ID > 기본 list ID 2
    subscriber_email = os.environ.get("SUBSCRIBER_EMAIL")
    list_id = os.environ.get("BREVO_LIST_ID", "2")
 
    payload = {
        "sender": {"name": "AI코리아24", "email": "info@aikorea24.kr"},
        "subject": f"AI코리아24 뉴스레터 - {briefing.get('date', '')}",
        "htmlContent": html
    }
 
    if subscriber_email:
        # 개별 이메일 발송
        payload["to"] = [{"email": subscriber_email}]
        print(f"  → 개별 발송: {subscriber_email}")
    else:
        # 연락처 목록 발송 (Brevo contact list)
        list_ids = [int(x.strip()) for x in list_id.split(",")]
        payload["listIds"] = list_ids
        # Brevo API requires 'to' field even for list-based sending
        # Use a placeholder email that will be overridden by listIds
        payload["to"] = [{"email": "placeholder@aikorea24.kr"}]
        print(f"  → 목록 발송: listIds={list_ids}")

    resp = requests.post(url, json=payload, headers=headers)
 
    if resp.status_code not in [200, 201]:
        print(f"❌ API 오류 ({resp.status_code}): {resp.text}")
        return False

    print(f"  ✅ 발송 성공 (HTTP {resp.status_code})")
    if resp.status_code == 201:
        try:
            msg_id = resp.json().get("messageId", "")
            print(f"  📧 Message ID: {msg_id}")
        except:
            pass
    return True


def generate_email_html(briefing, items):
    """이메일 HTML 생성"""
    date = briefing.get("date", "")
    intro = briefing.get("intro", "")

    items_html = ""
    for item in items:
        title = item.get("news_title", "")
        comment = item.get("comment", "")
        link = item.get("news_link", "#")

        items_html += f"""
        <div style="padding:16px 0;border-bottom:1px solid #e5e7eb;">
            <h3 style="font-size:15px;color:#111827;">{title}</h3>
            <p style="font-size:13px;color:#6b7280;">{comment}</p>
            <a href="{link}" style="font-size:12px;color:#2563eb;">자세히 보기 →</a>
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:-apple-system,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
        <h1 style="font-size:20px;color:#1f2937;">AI코리아24 뉴스레터</h1>
        <p style="font-size:14px;color:#6b7280;">{date}</p>
        <div style="background:#f0f9ff;padding:16px;border-radius:8px;margin:16px 0;">
            <p style="font-size:14px;color:#1e40af;">{intro}</p>
        </div>
        {items_html}
        <p style="font-size:12px;color:#9ca3af;text-align:center;margin-top:24px;">
            <a href="https://aikorea24.kr/unsubscribe" style="color:#9ca3af;">구독 해지</a>
        </p>
    </body>
    </html>
    """
    return html


def main():
    print("=== aikorea24 이메일 자동 발송 ===\n")

    print("[1/3] 오늘 브리핑 조회...")
    briefing = get_today_briefing()
    if not briefing:
        print("  오늘 발행된 브리핑 없음")
        return

    print(f"  브리핑 날짜: {briefing.get('date')}")
    print(f"  상태: {briefing.get('status')}\n")

    print("[2/3] 브리핑 아이템 조회...")
    items = get_briefing_items(briefing["id"])
    print(f"  아이템 수: {len(items)}건\n")

    print("[3/3] 이메일 발송...")
    success = send_email_via_brevo(briefing, items)

    if success:
        print("\n=== 이메일 발송 완료 ===")
    else:
        print("\n=== 이메일 발송 실패 ===")


if __name__ == "__main__":
    main()
