"""
네이버 블로그 발행 (requests 방식) - aikorea24 브리핑용
"""
import json
import os
import sys
import uuid
import time
import requests
import logging

logger = logging.getLogger(__name__)

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "cookies.json")
BLOG_ID = "oksoon5705-"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
REFERER = f"https://blog.naver.com/PostWriteForm.naver?blogId={BLOG_ID}&Redirect=Write&categoryNo=1"


def load_cookies():
    if not os.path.exists(COOKIE_FILE):
        print("쿠키 파일 없음. 먼저 python login.py 실행하세요.")
        sys.exit(1)
    session = requests.Session()
    with open(COOKIE_FILE, "r") as f:
        cookies = json.load(f)
    for c in cookies:
        session.cookies.set(c["name"], c["value"], domain=c.get("domain", ".naver.com"), path=c.get("path", "/"))
    session.headers.update({"User-Agent": UA, "Referer": REFERER})
    return session


def get_token(session, category_no=1):
    resp = session.get("https://blog.naver.com/PostWriteFormSeOptions.naver", params={"blogId": BLOG_ID, "categoryNo": category_no})
    data = resp.json()
    token = data.get("result", {}).get("token")
    if not token:
        print(f"토큰 획득 실패: {resp.text[:200]}")
        return None
    return token


def get_document_id(session, token):
    resp = session.get("https://platform.editor.naver.com/api/blogpc001/v1/service_config", headers={"Se-Authorization": token})
    data = resp.json()
    return data.get("editorInfo", {}).get("id")


def get_editor_source(session, category_no=1):
    resp = session.get("https://blog.naver.com/PostWriteFormManagerOptions.naver", params={"blogId": BLOG_ID, "categoryNo": category_no})
    data = resp.json()
    return data.get("result", {}).get("formView", {}).get("editorSource")


def se_id():
    return f"SE-{uuid.uuid4()}"


def build_body_components(body_html):
    import re
    parts = re.split(r'<br\s*/?>|</p>\s*<p>|\n', body_html)
    paragraphs = [re.sub(r'<[^>]+>', '', p).strip() for p in parts if re.sub(r'<[^>]+>', '', p).strip()]
    if not paragraphs:
        paragraphs = [re.sub(r'<[^>]+>', '', body_html).strip()]
    return [{
        "id": se_id(),
        "nodes": [{"id": se_id(), "value": p, "@ctype": "textNode"}],
        "@ctype": "paragraph"
    } for p in paragraphs]


def publish(title, body_html, tags="", category_no=1):
    print(f"\n{'='*50}")
    print(f"발행 시작: {title}")
    print(f"{'='*50}\n")

    session = load_cookies()
    token = get_token(session, category_no)
    if not token:
        return None
    doc_id = get_document_id(session, token)
    editor_source = get_editor_source(session, category_no)

    doc_model = json.dumps({
        "documentId": "",
        "document": {
            "version": "2.9.0", "theme": "default", "language": "ko-KR", "id": doc_id,
            "components": [
                {
                    "id": se_id(), "layout": "default",
                    "title": [{"id": se_id(), "nodes": [{"id": se_id(), "value": title, "@ctype": "textNode"}], "@ctype": "paragraph"}],
                    "subTitle": None, "align": "left", "@ctype": "documentTitle"
                },
                {
                    "id": se_id(), "layout": "default",
                    "value": build_body_components(body_html),
                    "@ctype": "text"
                }
            ],
            "di": {"dif": False, "dio": [
                {"dis": "N", "dia": {"t": 0, "p": 0, "st": 18, "sk": 3}},
                {"dis": "N", "dia": {"t": 0, "p": 0, "st": 18, "sk": 3}}
            ]}
        }
    }, ensure_ascii=False)

    pop_params = json.dumps({
        "configuration": {
            "openType": 2, "commentYn": True, "searchYn": True, "sympathyYn": True,
            "scrapType": 2, "outSideAllowYn": True, "twitterPostingYn": False,
            "facebookPostingYn": False, "cclYn": False
        },
        "populationMeta": {
            "categoryId": category_no, "logNo": None, "directorySeq": 10,
            "directoryDetail": None, "mrBlogTalkCode": None, "postWriteTimeType": "now",
            "tags": tags, "moviePanelParticipation": False, "greenReviewBannerYn": False,
            "continueSaved": False, "noticePostYn": False, "autoByCategoryYn": False,
            "postLocationSupportYn": False, "postLocationJson": None, "prePostDate": None,
            "thisDayPostInfo": None, "scrapYn": False, "autoSaveNo": int(time.time() * 1000)
        },
        "editorSource": editor_source
    }, ensure_ascii=False)

    resp = session.post("https://blog.naver.com/RabbitWrite.naver", data={
        "blogId": BLOG_ID,
        "documentModel": doc_model,
        "mediaResources": json.dumps({"image": [], "video": [], "file": []}),
        "populationParams": pop_params,
        "productApiVersion": "v1"
    }, headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": REFERER})

    try:
        result = resp.json()
    except Exception:
        print(f"JSON 파싱 실패: {resp.text[:500]}")
        return None

    if result.get("isSuccess"):
        log_no = result.get("result", {}).get("logNo", "")
        post_url = f"https://blog.naver.com/{BLOG_ID}/{log_no}"
        print(f"발행 성공: {post_url}")
        return post_url
    else:
        print(f"발행 실패: {json.dumps(result, ensure_ascii=False, indent=2)}")
        return None


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        publish(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    elif len(sys.argv) == 2 and sys.argv[1] == "--test":
        publish("AI코리아24 네이버 블로그 자동 발행 테스트", "이 글은 aikorea24 브리핑 자동 발행 테스트입니다.<br><br>정상 동작 확인.", "AI,브리핑,테스트")
    else:
        print('사용법: python publish.py "제목" "본문HTML" ["태그"]')
        print('       python publish.py --test')


def publish_with_playwright(title, paragraphs, image_path=None, link_url=None, tags="", category_no=1):
    """Playwright 기반 네이버 블로그 발행 (OG링크 카드 지원)"""
    import re as _re
    import time
    from playwright.sync_api import sync_playwright

    cookie_file = os.path.join(os.path.dirname(__file__), 'cookies.json')
    with open(cookie_file) as f:
        raw_cookies = json.load(f)

    pw_cookies = []
    for c in raw_cookies:
        domain = c.get("domain", ".naver.com")
        if not domain.startswith("."):
            domain = "." + domain
        pc = {"name": c["name"], "value": c["value"], "domain": domain, "path": c.get("path", "/")}
        exp = c.get("expires") or c.get("expiry")
        if exp and exp > 0:
            pc["expires"] = exp
        if c.get("secure"):
            pc["secure"] = True
        if c.get("sameSite") and c["sameSite"] in ("Strict", "Lax", "None"):
            pc["sameSite"] = c["sameSite"]
        pw_cookies.append(pc)

    result_url = None
    state_file = os.path.join(os.path.dirname(__file__), 'storage_state.json')
    captured_log_no = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(user_agent=UA)
        context.add_cookies(pw_cookies)
        page = context.new_page()

        def _on_response(response):
            if 'RabbitWrite' in response.url and response.request.method == 'POST':
                try:
                    body = response.json()
                    if body.get('isSuccess'):
                        captured_log_no['logNo'] = body.get('result', {}).get('logNo', '')
                except Exception:
                    pass
        page.on("response", _on_response)

        try:
            editor_url = (
                f"https://blog.naver.com/PostWriteForm.naver?"
                f"blogId={BLOG_ID}&Redirect=Write&categoryNo={category_no}"
                f"&redirect=Write&widgetTypeCall=true&directAccess=false"
            )
            page.goto(editor_url, wait_until="networkidle", timeout=120000)
            time.sleep(2)

            # 팝업 닫기
            for sel in ['.se-popup-button-cancel', '.se-help-panel-close-button']:
                try:
                    loc = page.locator(sel)
                    if loc.count() > 0 and loc.is_visible():
                        loc.click()
                        time.sleep(0.5)
                except Exception:
                    pass

            # 제목 입력
            page.locator('.se-documentTitle .se-text-paragraph').click()
            time.sleep(0.3)
            page.keyboard.insert_text(title)
            page.keyboard.press("Enter")
            time.sleep(0.3)

            # 이미지 삽입
            if image_path and os.path.exists(image_path):
                try:
                    with page.expect_file_chooser(timeout=30000) as fc:
                        page.locator('.se-toolbar-item-image button').first.click()
                    fc.value.set_files(image_path)
                    time.sleep(3)
                    page.keyboard.press("Enter")
                    time.sleep(0.3)
                except Exception as e:
                    print(f"이미지 삽입 실패: {e}")

            # 본문 입력
            for para in paragraphs:
                if not para.strip():
                    page.keyboard.press("Enter")
                else:
                    page.keyboard.insert_text(para)
                    page.keyboard.press("Enter")
                time.sleep(0.1)
            page.keyboard.press("Enter")
            time.sleep(0.3)

            # OG 링크 삽입
            if link_url:
                page.keyboard.type(link_url)
                time.sleep(1)
                page.keyboard.press("Enter")
                time.sleep(5)

                # URL 텍스트 삭제 (OG 카드만 남김)
                try:
                    paragraphs_el = page.locator('.se-text-paragraph')
                    for i in range(paragraphs_el.count()):
                        try:
                            el = paragraphs_el.nth(i)
                            text = el.inner_text().strip()
                            if link_url in text or ('aikorea24.kr' in text and text.startswith('http')):
                                el.click(click_count=3)
                                time.sleep(0.2)
                                page.keyboard.press("Backspace")
                                time.sleep(0.3)
                                break
                        except Exception:
                            pass
                except Exception as e:
                    print(f"URL 텍스트 삭제 실패 (무시): {e}")

            # 태그 입력
            if tags:
                tag_list = [t.strip() for t in tags.split(',') if t.strip()]
                if tag_list:
                    page.keyboard.press("Enter")
                    page.keyboard.insert_text(' '.join(f'#{t}' for t in tag_list))
                    time.sleep(0.3)

            # 발행
            page.locator('button[data-click-area="tpb.publish"]').click()
            time.sleep(2)
            confirm = page.locator('button[data-click-area="tpb*i.publish"]')
            if confirm.count() > 0 and confirm.is_visible():
                confirm.click(force=True)
                time.sleep(8)

            # logNo 추출
            log_no = captured_log_no.get('logNo', '')
            if not log_no:
                m = _re.search(r'logNo=(\d+)', page.url)
                if m:
                    log_no = m.group(1)

            if log_no:
                result_url = f"https://blog.naver.com/{BLOG_ID}/{log_no}"
                print(f"발행 성공: {result_url}")
            else:
                result_url = f"https://blog.naver.com/{BLOG_ID}/"
                print(f"발행 완료 (logNo 미추출): {result_url}")

            # storage_state 저장
            context.storage_state(path=state_file)

        except Exception as e:
            print(f"Playwright 발행 에러: {e}")
        finally:
            browser.close()

    return result_url
