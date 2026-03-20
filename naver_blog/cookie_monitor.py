"""
네이버 쿠키 만료 감지 + 텔레그램 알림
사용법: python cookie_monitor.py
       cron: 0 8 * * * cd /path/to/naver_blog && python cookie_monitor.py
"""
import json
import os
import sys
import requests

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "cookies.json")
BLOG_ID = "oksoon5705-"

TELEGRAM_BOT_TOKEN = "8511728557:AAGGDeNxyGFhjI5Y5fEGyzeZcxiG5yv05PE"
TELEGRAM_CHAT_ID = "8539779870"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)
        print(f"텔레그램 발송: {message}")
    except Exception as e:
        print(f"텔레그램 발송 실패: {e}")


def check_cookie():
    if not os.path.exists(COOKIE_FILE):
        send_telegram("🚨 <b>[AI코리아24] 네이버 쿠키 파일 없음</b>\n\n네이버 ID: oksoonkim5705\n쿠키 파일이 존재하지 않습니다.\nlogin.py를 실행하세요.")
        return False

    session = requests.Session()
    with open(COOKIE_FILE, "r") as f:
        cookies = json.load(f)

    for c in cookies:
        session.cookies.set(c["name"], c["value"], domain=c.get("domain", ".naver.com"), path=c.get("path", "/"))
    session.headers.update({"User-Agent": UA})

    # 토큰 획득 시도로 쿠키 유효성 확인
    try:
        resp = session.get(
            "https://blog.naver.com/PostWriteFormSeOptions.naver",
            params={"blogId": BLOG_ID, "categoryNo": 1},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("result", {}).get("token")
            if token:
                print(f"쿠키 정상: 토큰 획득 성공")
                return True
    except Exception:
        pass

    send_telegram(
        "🚨 <b>[AI코리아24] 네이버 블로그 쿠키 만료</b>\n\n"
        "네이버 ID: oksoonkim5705\n"
        "블로그 ID: oksoon5705-\n\n"
        "브리핑 자동 발행이 중단됩니다.\n"
        "아래 명령으로 쿠키를 갱신하세요:\n\n"
        "<code>cd ~/Projects/aikorea24/naver_blog\npython login.py</code>"
    )
    return False


if __name__ == "__main__":
    ok = check_cookie()
    sys.exit(0 if ok else 1)
