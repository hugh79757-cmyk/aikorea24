#!/usr/bin/env python3
"""aikorea24 이메일 자동 발송기 — 브리핑 기사 + AI 도구 추천"""

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

    project_env = Path(__file__).resolve().parent.parent / ".env"
    if project_env.exists():
        with open(project_env) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()


def _d1_query(sql: str) -> list[dict]:
    """wrangler d1 execute JSON 출력에서 results 배열 추출"""
    root = Path(__file__).resolve().parent.parent
    try:
        r = subprocess.run(
            ["npx", "wrangler", "d1", "execute", "aikorea24-db", "--remote", "--command", sql],
            capture_output=True, text=True, timeout=60, cwd=str(root),
        )
        if r.returncode != 0:
            return []
        m = re.search(r'"results"\s*:\s*(\[[\s\S]*?\])\s*,\s*"success"', r.stdout)
        if m:
            return json.loads(m.group(1))
    except Exception:
        pass
    return []


def get_today_briefing():
    """D1에서 오늘 브리핑 조회 (최신 시퀀스)"""
    today = datetime.now().strftime("%Y-%m-%d")
    rows = _d1_query(
        f"SELECT b.id, b.date, b.intro, b.status, "
        f"GROUP_CONCAT(bi.news_id) as news_ids "
        f"FROM briefings b "
        f"LEFT JOIN briefing_items bi ON b.id = bi.briefing_id "
        f"WHERE b.date LIKE '{today}%' AND b.status = 'published' "
        f"GROUP BY b.id ORDER BY b.date DESC LIMIT 1"
    )
    return rows[0] if rows else None


def get_briefing_items(briefing_id):
    """브리핑 아이템 조회"""
    return _d1_query(
        f"SELECT bi.*, n.title as news_title, n.description as news_desc, "
        f"n.link as news_link, n.source as news_source "
        f"FROM briefing_items bi "
        f"LEFT JOIN news n ON bi.news_id = n.id "
        f"WHERE bi.briefing_id = {briefing_id} "
        f"ORDER BY bi.sort_order ASC"
    )


def get_tools():
    """D1에서 AI 도구 목록 조회 (최신 6개)"""
    return _d1_query(
        "SELECT name, slug, tagline, category, price, korean_support, difficulty "
        "FROM tools ORDER BY updated_at DESC LIMIT 6"
    )


def esc(s):
    if not s:
        return ""
    return (str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;"))


def generate_email_html(briefing, items):
    """이메일 HTML 생성 — 브리핑 기사 + AI 도구 추천"""
    today = datetime.now().strftime("%Y-%m-%d")
    date = briefing.get("date", "")
    intro = briefing.get("intro", "")

    # TOC
    toc_html = ""
    if items:
        toc_html = f"""
        <tr>
          <td style="padding:16px 24px;background:#eff6ff;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="font-size:13px;font-weight:700;color:#1e40af;padding-bottom:8px;">
                  📋 오늘의 브리핑
                </td>
              </tr>
              {''.join(f'''
              <tr>
                <td style="font-size:13px;color:#1f2937;line-height:1.8;">
                  {i + 1}. {esc(item.get("news_title", ""))}
                </td>
              </tr>''' for i, item in enumerate(items))}
            </table>
          </td>
        </tr>"""

    # Items (상위 3개만 상세 표시)
    display_items = items[:3] if len(items) > 3 else items
    total_count = len(items)

    items_html = ""
    for item in display_items:
        sort_order = item.get("sort_order") or ""
        title = item.get("news_title", "")
        comment = item.get("comment", "")
        desc = (item.get("news_desc") or "")[:150]
        briefing_url = f"https://aikorea24.kr/briefing/{date}{'#item-' + str(sort_order) if sort_order else ''}"

        items_html += f"""
        <tr>
          <td style="padding:16px 0;border-bottom:1px solid #e5e7eb;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="padding-bottom:8px;">
                  <span style="display:inline-block;width:20px;height:20px;background:#2563eb;color:#fff;border-radius:50%;font-size:11px;text-align:center;line-height:20px;margin-right:6px;vertical-align:middle;">{sort_order}</span>
                  <span style="font-size:15px;color:#111827;font-weight:700;vertical-align:middle;">{esc(title)}</span>
                </td>
              </tr>
              {f'<tr><td style="background:#f0f9ff;border-left:4px solid #3b82f6;padding:8px 12px;font-size:13px;color:#1e40af;line-height:1.5;margin-top:4px;">{esc(comment)}</td></tr>' if comment else ''}
              {f'<tr><td style="font-size:13px;color:#6b7280;line-height:1.5;padding-top:6px;">{esc(desc)}</td></tr>' if desc else ''}
              <tr><td style="padding-top:8px;">
                <a href="{briefing_url}" style="font-size:12px;color:#2563eb;text-decoration:underline;font-weight:600;">
                  AI코리아24에서 자세히 보기 →
                </a>
              </td></tr>
            </table>
          </td>
        </tr>"""

    if total_count > 3:
        items_html += f"""
        <tr>
          <td style="padding:16px 0;text-align:center;">
            <a href="https://aikorea24.kr/briefing/{date}"
               style="display:inline-block;padding:10px 24px;background:#2563eb;color:#ffffff;border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;">
              👉 오늘의 브리핑 {total_count}개 전체 보기 →
            </a>
          </td>
        </tr>"""

    # Tools
    tools = get_tools()
    tools_html = ""
    if tools:
        tool_rows = []
        for t in tools:
            name = esc(t.get("name", ""))
            slug = t.get("slug", "")
            tagline = esc(t.get("tagline", ""))
            category = esc(t.get("category", ""))
            price = esc(t.get("price", ""))
            difficulty = esc(t.get("difficulty", ""))
            kr_flag = "🇰🇷 " if t.get("korean_support") else ""
            price_color = "#059669" if price and ("무료" in price or "Free" in price) else "#6b7280"

            cat_tag = f'<span style="display:inline-block;background:#f3f4f6;color:#374151;font-size:11px;padding:2px 8px;border-radius:12px;margin-right:4px;">{category}</span>' if category else ""
            diff_line = f'<tr><td colspan="2" style="font-size:12px;color:#9ca3af;padding-top:2px;line-height:1.4;">⭐ 난이도: {difficulty}</td></tr>' if difficulty else ""

            tool_rows.append(f"""
              <tr>
                <td style="padding:8px 0;border-bottom:1px solid #f3f4f6;">
                  <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td style="font-size:14px;font-weight:600;color:#111827;">
                        {kr_flag}{name}
                      </td>
                      <td style="text-align:right;font-size:11px;">
                        {cat_tag}
                        <span style="color:{price_color};">{price}</span>
                      </td>
                    </tr>
                    <tr>
                      <td colspan="2" style="font-size:13px;color:#6b7280;padding-top:4px;line-height:1.4;">
                        {tagline}
                      </td>
                    </tr>
                    {diff_line}
                    <tr>
                      <td colspan="2" style="padding-top:6px;">
                        <a href="https://aikorea24.kr/tools/{slug}/"
                           style="font-size:12px;color:#2563eb;text-decoration:underline;">
                          AI코리아24에서 자세히 보기 →
                        </a>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>""")

        tools_html = f"""
        <tr>
          <td style="padding:24px 0 8px 0;">
            <table width="100%" cellpadding="0" cellspacing="0" style="border-top:2px solid #e5e7eb;padding-top:24px;">
              <tr>
                <td style="font-size:16px;font-weight:700;color:#1f2937;padding-bottom:16px;">
                  🛠️ 오늘의 신규 AI 도구
                </td>
              </tr>
              {''.join(tool_rows)}
              <tr>
                <td style="padding:12px 0;text-align:center;">
                  <a href="https://aikorea24.kr/tools/"
                     style="font-size:13px;color:#2563eb;text-decoration:underline;">
                    🔎 모든 AI 도구 보기 →
                  </a>
                </td>
              </tr>
            </table>
          </td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;">
    <tr>
      <td style="padding:32px 24px 16px 24px;background:#1e3a5f;text-align:center;">
        <div style="font-size:40px;line-height:1;margin-bottom:8px;">🤖</div>
        <h1 style="color:#fff;font-size:26px;margin:0;letter-spacing:2px;">AI코리아24</h1>
        <p style="color:#94a3b8;font-size:13px;margin:4px 0 0 0;">오늘의 AI 브리핑 — {date}</p>
        <p style="color:#64748b;font-size:12px;margin:6px 0 0 0;">매일 아침 7시, 국내외 AI 소식 큐레이션</p>
      </td>
    </tr>
    <tr>
      <td style="height:3px;background:linear-gradient(90deg,#3b82f6,#8b5cf6);padding:0;font-size:1px;line-height:3px;">&nbsp;</td>
    </tr>
    {toc_html}
    {f'''
    <tr>
      <td style="padding:20px 24px;background:#fff;border-bottom:1px solid #e5e7eb;">
        <p style="font-size:14px;color:#374151;line-height:1.6;margin:0;">{esc(intro)}</p>
      </td>
    </tr>''' if intro else ''}
    <tr>
      <td style="padding:0 24px;background:#fff;">
        <table width="100%" cellpadding="0" cellspacing="0">
          {items_html}
          {tools_html}
        </table>
      </td>
    </tr>
    <tr>
      <td style="padding:24px;text-align:center;color:#9ca3af;font-size:12px;">
        <p style="margin:0;">AI코리아24 · 매일 아침 AI 소식을 전해드립니다</p>
        <p style="margin:4px 0 0 0;">
          <a href="https://aikorea24.kr/community/" style="color:#3b82f6;text-decoration:underline;">💬 커뮤니티</a>에서 오늘의 브리핑에 대한 의견을 나눠보세요
        </p>
        <p style="margin:4px 0 0 0;">
          <a href="https://aikorea24.kr/unsubscribe" style="color:#9ca3af;text-decoration:underline;">구독 해지</a>
        </p>
      </td>
    </tr>
  </table>
</body>
</html>"""
    return html


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

    subscriber_email = os.environ.get("SUBSCRIBER_EMAIL", "twinssn@gmail.com")

    payload = {
        "sender": {"name": "AI코리아24", "email": "info@aikorea24.kr"},
        "subject": f"AI코리아24 뉴스레터 - {briefing.get('date', '')}",
        "htmlContent": html,
        "to": [{"email": subscriber_email}]
    }

    list_id = os.environ.get("BREVO_LIST_ID")
    if list_id:
        list_ids = [int(x.strip()) for x in list_id.split(",")]
        payload["listIds"] = list_ids
        print(f"  → 개별 발송: {subscriber_email} + 목록 발송: listIds={list_ids}")
    else:
        print(f"  → 개별 발송: {subscriber_email}")

    resp = requests.post(url, json=payload, headers=headers)

    if resp.status_code not in [200, 201]:
        print(f"❌ API 오류 ({resp.status_code}): {resp.text}")
        return False

    print(f"  ✅ 발송 성공 (HTTP {resp.status_code})")
    if resp.status_code == 201:
        try:
            msg_id = resp.json().get("messageId", "")
            print(f"  📧 Message ID: {msg_id}")
        except Exception:
            pass
    return True


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
    print("  도구 목록 조회 병행...")

    print("[3/3] 이메일 발송...")
    success = send_email_via_brevo(briefing, items)

    if success:
        print("\n=== 이메일 발송 완료 ===")
    else:
        print("\n=== 이메일 발송 실패 ===")


if __name__ == "__main__":
    main()
