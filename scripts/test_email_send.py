#!/usr/bin/env python3
"""
심층글 이메일 발송 테스트
- 오늘 브리핑 + 썸네일 연결 상태에서 실제 Brevo API 호출
- 테스트 수신자에게 발송
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR / "scripts"))

# Load env from project .env
env_path = PROJECT_DIR / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "source" not in line and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

# Also load ~/.env.common for BREVO keys
common_env = os.path.expanduser("~/.env.common")
if os.path.exists(common_env):
    with open(common_env) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

import requests


def load_env():
    """Reload env vars"""
    pass  # Already loaded above


def get_today_briefing():
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
        capture_output=True, text=True, cwd=str(PROJECT_DIR)
    )
    return _parse_d1_results(result.stdout)


def get_briefing_items(briefing_id):
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
        capture_output=True, text=True, cwd=str(PROJECT_DIR)
    )
    return _parse_d1_results(result.stdout)


def _parse_d1_results(stdout):
    m = re.search(r'"results"\s*:\s*(\[[\s\S]*?\])\s*,\s*"success"', stdout)
    if m:
        return json.loads(m.group(1))
    return []


def get_latest_deep_articles(limit=3):
    """최근 심층글 목록 조회 (R2 블로그 포스트)"""
    # Check blog content dir
    blog_dir = PROJECT_DIR / "src" / "content" / "blog"
    if not blog_dir.exists():
        return []

    md_files = sorted(blog_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)[:limit]
    articles = []
    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        # Extract frontmatter
        fm_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if fm_match:
            fm_text = fm_match.group(1)
            title_m = re.search(r'title:\s*["\']?(.*?)["\']?\s*$', fm_text, re.MULTILINE)
            img_m = re.search(r'image:\s*["\']?(.*?)["\']?\s*$', fm_text, re.MULTILINE)
            title = title_m.group(1) if title_m else md_file.stem
            image = img_m.group(1) if img_m else None
            articles.append({"title": title, "image": image, "file": md_file.name})
    return articles


def generate_email_html(briefing, items, deep_articles):
    """이메일 HTML 생성 - 썸네일 포함"""
    date = briefing.get("date", "")
    intro = briefing.get("intro", "")

    # 뉴스 아이템 HTML
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

    # 심층글 섹션 HTML (썸네일 포함)
    deep_html = ""
    if deep_articles:
        deep_html = '<div style="margin:24px 0;"><h2 style="font-size:18px;color:#111827;border-bottom:2px solid #2563eb;padding-bottom:8px;">심층분석</h2>'
        for art in deep_articles:
            title = art.get("title", "")
            image = art.get("image", "")
            # R2 public URL prefix
            if image and not image.startswith("http"):
                img_url = f"https://pub-2f5c7af1c303419a933069212bc25874.r2.dev{image}"
            else:
                img_url = image or ""

            slug = art.get("file", "").replace(".md", "")
            link = f"https://aikorea24.kr/blog/{slug}"

            img_tag = f'<img src="{img_url}" style="width:100%;max-width:560px;border-radius:8px;margin-bottom:12px;" alt="{title}">' if img_url else ""

            deep_html += f"""
            <div style="padding:16px 0;border-bottom:1px solid #e5e7eb;">
                {img_tag}
                <h3 style="font-size:16px;color:#111827;"><a href="{link}" style="color:#2563eb;text-decoration:none;">{title}</a></h3>
            </div>
            """
        deep_html += '</div>'

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

        <h2 style="font-size:18px;color:#111827;">오늘의 AI 뉴스</h2>
        {items_html}

        {deep_html}

        <p style="font-size:12px;color:#9ca3af;text-align:center;margin-top:24px;">
            <a href="https://aikorea24.kr/unsubscribe" style="color:#9ca3af;">구독 해지</a>
        </p>
    </body>
    </html>
    """
    return html


def main():
    print("=== 심층글 이메일 발송 테스트 ===\n")

    # 1. 오늘 브리핑 조회
    print("[1/4] 오늘 발행된 브리핑 조회...")
    rows = get_today_briefing()
    if not rows:
        print("  ERROR: 오늘 발행된 브리핑이 없습니다.")
        print("  먼저 auto_briefing.py로 브리핑을 발행하세요.")
        return False
    briefing = rows[0]
    print(f"  OK: 날짜={briefing.get('date')}, 상태={briefing.get('status')}, ID={briefing.get('id')}")

    # 2. 브리핑 아이템 조회
    print("\n[2/4] 브리핑 아이템 조회...")
    items = get_briefing_items(briefing["id"])
    print(f"  OK: {len(items)}건의 아이템")
    for i, item in enumerate(items[:3]):
        print(f"    [{i+1}] {item.get('news_title', '?')[:50]}")

    # 3. 심층글 + 썸네일 확인
    print("\n[3/4] 심층글 + 썸네일 상태 확인...")
    deep_articles = get_latest_deep_articles(3)
    if deep_articles:
        print(f"  OK: {len(deep_articles)}개의 심층글 발견")
        thumb_dir = PROJECT_DIR / "public" / "images" / "thumbnails"
        for art in deep_articles:
            slug = art["file"].replace(".md", "")
            thumb_file = thumb_dir / f"{slug}.jpg"
            has_thumb = thumb_file.exists()
            img_path = art.get("image", "없음")
            print(f"    - {art['title'][:40]}")
            print(f"      image: {img_path}")
            print(f"      thumbnail: {'존재' if has_thumb else '미생성'} ({thumb_file})")
    else:
        print("  WARNING: 심층글이 없습니다. 뉴스 아이템만으로 발송합니다.")

    # 4. Brevo API 실제 발송
    print("\n[4/4] Brevo API 실제 이메일 발송...")
    api_key = os.environ.get("BREVO_API_KEY")
    if not api_key:
        print("  ERROR: BREVO_API_KEY 미설정")
        return False

    print(f"  API Key: {api_key[:20]}...")

    html = generate_email_html(briefing, items, deep_articles)
    print(f"  HTML 길이: {len(html)} bytes")

    # 테스트 수신자 (자기 자신에게 발송)
    test_email = "newsletter@aikorea24.kr"  # 도메인 이메일로 발송 테스트

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "sender": {"name": "AI코리아24", "email": "newsletter@aikorea24.kr"},
        "to": [{"email": test_email}],
        "subject": f"[테스트] AI코리아24 뉴스레터 - {briefing.get('date', '')}",
        "htmlContent": html
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        print(f"  HTTP Status: {resp.status_code}")
        if resp.status_code in [200, 201]:
            print(f"  응답: {resp.json()}")
            print("\n=== 이메일 발송 성공 ===")
            return True
        else:
            print(f"  에러: {resp.text[:500]}")
            print("\n=== 이메일 발송 실패 ===")
            return False
    except Exception as e:
        print(f"  Exception: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
