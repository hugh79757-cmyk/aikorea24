#!/usr/bin/env python3
"""aikorea24 썸네일 자동 생성기

뉴스 URL에서 og:image를 추출하고 800x800 WebP 썸네일을 생성합니다.

Usage:
    python3 scripts/auto_thumbnail.py <url> <output_slug>
    python3 scripts/auto_thumbnail.py --extract-only <url>
    python3 scripts/auto_thumbnail.py --help
"""

import argparse
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from PIL import Image

PROJECT_DIR = Path(__file__).resolve().parent.parent
PUBLIC_IMAGES_DIR = PROJECT_DIR / "public" / "images"

THUMBNAIL_SIZE = (800, 800)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


KST = timezone(timedelta(hours=9))


def log(msg):
    ts = datetime.now(KST).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def extract_og_image(url):
    """URL에서 og:image 메타 태그를 추출합니다.
    
    Returns:
        str or None: og:image URL (절대 경로)
    """
    try:
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Try og:image first
        meta = soup.find("meta", property="og:image")
        if meta and meta.get("content"):
            return urljoin(url, meta["content"])

        # Fallback to twitter:image
        meta = soup.find("meta", attrs={"name": "twitter:image"})
        if meta and meta.get("content"):
            return urljoin(url, meta["content"])

        # Fallback to twitter:image:src
        meta = soup.find("meta", attrs={"name": "twitter:image:src"})
        if meta and meta.get("content"):
            return urljoin(url, meta["content"])

        return None
    except Exception as e:
        log(f"  og:image 추출 에러: {e}")
        return None


def download_image(url):
    """이미지를 다운로드합니다.
    
    Returns:
        bytes or None
    """
    try:
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=15, stream=True)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        log(f"  이미지 다운로드 에러: {e}")
        return None


def create_thumbnail(image_data, output_path):
    """이미지를 800x800 WebP 썸네일로 리사이즈합니다.
    
    중앙 크롭으로 정사각형으로 만든 후 리사이즈합니다.
    """
    import io

    img = Image.open(io.BytesIO(image_data))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    w, h = img.size
    # Center crop to square
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))

    # Resize to target
    img = img.resize(THUMBNAIL_SIZE, Image.LANCZOS)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    img.save(output_path, "WEBP", quality=85)
    return output_path


def process_thumbnail(url, slug):
    """URL에서 썸네일을 생성합니다.
    
    Args:
        url: 뉴스 URL
        slug: 출력 슬러그 (public/images/{slug}/thumbnail.webp)
    
    Returns:
        str or None: 썸네일 상대 경로 (/images/{slug}/thumbnail.webp)
    """
    log(f"og:image 추출 중: {url}")
    og_url = extract_og_image(url)
    if not og_url:
        log("  og:image을 찾을 수 없습니다.")
        return None

    log(f"  og:image: {og_url}")

    log("이미지 다운로드 중...")
    image_data = download_image(og_url)
    if not image_data:
        log("  이미지 다운로드 실패")
        return None

    log(f"  다운로드 완료: {len(image_data):,} bytes")

    output_path = str(PUBLIC_IMAGES_DIR / slug / "thumbnail.webp")
    log(f"썸네일 생성 중: {output_path}")
    create_thumbnail(image_data, output_path)

    file_size = os.path.getsize(output_path)
    log(f"  생성 완료: {file_size:,} bytes")

    rel_path = f"/images/{slug}/thumbnail.webp"
    log(f"  경로: {rel_path}")
    return rel_path


def main():
    parser = argparse.ArgumentParser(
        description="aikorea24 썸네일 자동 생성기",
        epilog="예시: python3 scripts/auto_thumbnail.py https://techcrunch.com/... techcrunch-article",
    )
    parser.add_argument("url", help="뉴스 기사 URL")
    parser.add_argument("slug", nargs="?", help="출력 슬러그 (public/images/{slug}/thumbnail.webp)")
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="og:image URL만 추출하고 다운로드하지 않음",
    )
    args = parser.parse_args()

    if args.extract_only:
        og_url = extract_og_image(args.url)
        if og_url:
            print(og_url)
        else:
            print("None")
            sys.exit(1)
        return

    if not args.slug:
        parser.error("slug 인수가 필요합니다 (--extract-only 사용 시 제외)")

    result = process_thumbnail(args.url, args.slug)
    if result:
        print(f"\n✅ 썸네일 생성 완료: {result}")
    else:
        print("\n❌ 썸네일 생성 실패")
        sys.exit(1)


if __name__ == "__main__":
    main()
