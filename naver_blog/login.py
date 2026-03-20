"""
네이버 블로그 로그인 → 쿠키 저장 (Playwright)
사용법: python login.py
"""
import json
import os
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
    login()
