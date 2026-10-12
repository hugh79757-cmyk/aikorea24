"""
⛔ 수동로그인 전용 — 자동 실행 절대 금지 (AGENTS.md §0 위반 시 계정 잠금)
이 파일을 에이전트가 실행하면 안 됩니다. 반드시 사용자가 직접 수동으로 실행하세요.
위반 시: 네이버 보안 시스템 도용 의심 태그 → 블로그 저품질 → 트래픽 2000→100 급락

네이버 블로그 로그인 → 쿠키 저장 (Playwright)
사용법: MANUAL_CONFIRM=1 python login.py (사용자 직접 실행 필수)
"""
import json
import os
import sys
import time
from playwright.sync_api import sync_playwright

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "cookies.json")
BLOG_ID = "oksoon5705-"

def login():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto("https://nid.naver.com/nidlogin.login")
        print("=" * 50)
        print("브라우저에서 네이버 로그인을 완료하세요.")
        print("로그인 후 이 터미널에서 Enter를 누르세요...")
        print("=" * 50)
        input()

        page.goto("https://nid.naver.com")
        time.sleep(2)
        page.goto(f"https://blog.naver.com/{BLOG_ID}")
        time.sleep(2)
        page.goto(f"https://blog.naver.com/PostWriteForm.naver?blogId={BLOG_ID}&Redirect=Write&categoryNo=1")
        time.sleep(3)

        cookies = context.cookies()
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)

        state_file = os.path.join(os.path.dirname(__file__), "storage_state.json")
        context.storage_state(path=state_file)

        print(f"쿠키 저장 완료: {COOKIE_FILE} ({len(cookies)}개)")
        browser.close()

if __name__ == "__main__":
    if os.environ.get("MANUAL_CONFIRM") != "1":
        print("⛔ 수동로그인 전용 — 자동 실행 절대 금지 (AGENTS.md §0). MANUAL_CONFIRM=1 + 사용자 직접 확인 필요", file=sys.stderr)
        sys.exit(1)
    login()
