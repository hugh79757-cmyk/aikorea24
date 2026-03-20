"""
aikorea24 블로그 글 → 네이버 블로그 요약 발행
사용법: python publish_blog.py                      (목록 보기)
       python publish_blog.py --slug 글-슬러그       (특정 글 발행)
       python publish_blog.py --slug 글-슬러그 --dry-run  (미리보기)
       python publish_blog.py --all --dry-run        (전체 미리보기)
"""
import sys
import os
import re
import io
import json
import yaml
import requests
import html as html_module
from datetime import datetime
from PIL import Image, ImageEnhance, ImageFilter

sys.path.insert(0, os.path.dirname(__file__))
from publish import publish, load_cookies, get_token, BLOG_ID

BLOG_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "content", "blog")
SITE_URL = "https://aikorea24.kr"
PUBLISHED_FILE = os.path.join(os.path.dirname(__file__), "published_slugs.json")


def load_published():
    if os.path.exists(PUBLISHED_FILE):
        with open(PUBLISHED_FILE, "r") as f:
            return json.load(f)
    return []


def save_published(slugs):
    with open(PUBLISHED_FILE, "w") as f:
        json.dump(slugs, f, ensure_ascii=False, indent=2)


def parse_md(filepath):
    """마크다운 파일에서 프론트매터와 본문 분리"""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 프론트매터 파싱
    fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not fm_match:
        return None, None

    fm = yaml.safe_load(fm_match.group(1))
    body = content[fm_match.end():]
    return fm, body


def summarize_body(body, max_paragraphs=5):
    """본문에서 요약용 텍스트 추출 (마크다운 → 플레인 텍스트)"""
    # 이미지, 링크 제거
    text = re.sub(r'!\[.*?\]\(.*?\)', '', body)
    text = re.sub(r'\[([^\]]*)\]\([^\)]*\)', r'\1', text)
    # HTML 태그 제거
    text = re.sub(r'<[^>]+>', '', text)
    # 헤딩 마크다운 제거
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # 볼드/이탤릭 제거
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)

    # 문단 분리
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip() and len(p.strip()) > 20]

    # 앞 N개 문단 선택
    selected = paragraphs[:max_paragraphs]
    return selected


def transform_image(image_url, slug):
    """원본 이미지 다운로드 → Pillow 변형 (밝기+색조+워터마크)"""
    try:
        resp = requests.get(image_url, timeout=15)
        if resp.status_code != 200:
            return None

        img = Image.open(io.BytesIO(resp.content)).convert("RGB")

        # 1) 리사이즈 (네이버 최적 너비 800px)
        if img.width > 800:
            ratio = 800 / img.width
            img = img.resize((800, int(img.height * ratio)), Image.LANCZOS)

        # 2) 밝기 약간 올리기
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.08)

        # 3) 채도 약간 올리기
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.15)

        # 4) 약간의 샤프닝
        img = img.filter(ImageFilter.SHARPEN)

        # 저장
        save_dir = os.path.join(os.path.dirname(__file__), "images")
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, f"{slug}.jpg")
        img.save(save_path, "JPEG", quality=85)
        return save_path

    except Exception as e:
        print(f"이미지 변환 실패: {e}")
        return None


def format_naver_html(fm, paragraphs, slug, image_path=None):
    """네이버 블로그용 HTML 생성"""
    lines = []

    # 도입부
    if fm.get("description"):
        lines.append(html_module.unescape(fm["description"]))
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("")

    # 요약 본문
    for p in paragraphs:
        lines.append(html_module.unescape(p))
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append("📌 이 글은 요약본입니다.")
    lines.append(f"전체 내용은 AI코리아24에서 확인하세요.")
    lines.append("")
    lines.append(f"👉 원문 보기: {SITE_URL}/blog/{slug}/")
    lines.append(f"👉 AI코리아24: {SITE_URL}")
    lines.append("")

    # 태그
    tags_list = fm.get("tags", [])
    if isinstance(tags_list, list) and tags_list:
        tag_text = " ".join(f"#{t.replace(' ', '_')}" for t in tags_list)
        lines.append(tag_text)

    category = fm.get("category", "")
    if category:
        lines.append(f"#AI코리아24 #{category.replace(' ', '_')}")
    else:
        lines.append("#AI코리아24 #AI뉴스")

    return "<br>".join(lines)


def get_all_posts():
    """모든 블로그 글 목록 반환"""
    posts = []
    for fn in sorted(os.listdir(BLOG_DIR)):
        if not fn.endswith(".md"):
            continue
        slug = fn[:-3]
        fp = os.path.join(BLOG_DIR, fn)
        fm, body = parse_md(fp)
        if not fm or fm.get("draft"):
            continue
        posts.append({
            "slug": slug,
            "title": fm.get("title", slug),
            "category": fm.get("category", ""),
            "date": str(fm.get("date", "")),
            "image": fm.get("image", ""),
            "tags": fm.get("tags", []),
            "filepath": fp,
            "fm": fm,
            "body": body
        })
    return posts


def publish_one(slug, dry_run=False):
    """특정 슬러그의 글을 네이버에 발행"""
    published = load_published()
    if slug in published and not dry_run:
        print(f"이미 발행됨: {slug}")
        return None

    fp = os.path.join(BLOG_DIR, f"{slug}.md")
    if not os.path.exists(fp):
        print(f"파일 없음: {fp}")
        return None

    fm, body = parse_md(fp)
    if not fm:
        print(f"프론트매터 파싱 실패: {slug}")
        return None

    title = fm.get("title", slug)
    paragraphs = summarize_body(body)
    image_url = fm.get("image", "")

    # 이미지 변형
    image_path = None
    if image_url:
        print(f"이미지 변형 중: {image_url}")
        image_path = transform_image(image_url, slug)

    # HTML 생성
    body_html = format_naver_html(fm, paragraphs, slug, image_path)

    # 태그
    tags_list = fm.get("tags", [])
    if isinstance(tags_list, list):
        tags = ",".join(tags_list[:10])
    else:
        tags = ""
    tags = f"AI,AI코리아24,{tags}" if tags else "AI,AI코리아24"

    naver_title = f"[AI코리아24] {title}"
    if len(naver_title) > 60:
        naver_title = naver_title[:57] + "..."

    if dry_run:
        print(f"\n{'='*50}")
        print(f"[DRY RUN] 제목: {naver_title}")
        print(f"[DRY RUN] 태그: {tags}")
        print(f"[DRY RUN] 이미지: {image_path or '없음'}")
        print(f"[DRY RUN] 본문 미리보기:")
        print(body_html[:400])
        print(f"{'='*50}")
        return "dry-run"

    # 카테고리 매핑
    category_map = {
        "뉴스": 6,
        "바이브코딩": 7,
        "바이브코딩심화": 7,
        "개발배포": 7,
        "소상공인AI": 8,
        "AI입문": 9,
        "AI 강좌": 9,
        "AI": 9,
        "강좌": 9,
        "일반": 10,
        "IT": 10,
    }
    cat_name = fm.get("category", "")
    cat_no = category_map.get(cat_name, 1)

    # Playwright 방식 발행 (이미지 + OG 카드 지원)
    from publish import publish_with_playwright
    link_url = f"{SITE_URL}/blog/{slug}/"
    body_lines = [l for l in body_html.split("<br>") if l.strip()]
    # 원문 링크는 본문에서 제거 (OG 카드로 대체)
    body_lines = [l for l in body_lines if "원문 보기:" not in l]
    result = publish_with_playwright(
        naver_title,
        body_lines,
        image_path=image_path,
        link_url=link_url,
        tags=tags,
        category_no=cat_no
    )

    if result:
        published.append(slug)
        save_published(published)
        print(f"발행 완료 + 기록: {slug}")

    return result


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    show_all = "--all" in args

    slug = None
    for i, a in enumerate(args):
        if a == "--slug" and i + 1 < len(args):
            slug = args[i + 1]

    if slug:
        publish_one(slug, dry_run=dry_run)
    elif show_all and dry_run:
        posts = get_all_posts()
        published = load_published()
        for p in posts:
            status = "발행됨" if p["slug"] in published else "미발행"
            print(f"  [{status}] {p['slug']} | {p['category']} | {p['title'][:40]}")
        print(f"\n총 {len(posts)}개 글, 발행됨 {len([p for p in posts if p['slug'] in published])}개")
    else:
        # 목록 보기
        posts = get_all_posts()
        published = load_published()
        unpublished = [p for p in posts if p["slug"] not in published]
        print(f"\n전체 {len(posts)}개 글, 미발행 {len(unpublished)}개\n")
        for i, p in enumerate(unpublished[:10], 1):
            print(f"  {i}. [{p['category']}] {p['title'][:50]}")
            print(f"     slug: {p['slug']}")
        if len(unpublished) > 10:
            print(f"\n  ... 외 {len(unpublished) - 10}개")
        print(f"\n발행: python publish_blog.py --slug <슬러그>")
        print(f"미리보기: python publish_blog.py --slug <슬러그> --dry-run")


if __name__ == "__main__":
    main()
