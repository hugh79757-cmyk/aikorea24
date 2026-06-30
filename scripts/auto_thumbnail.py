#!/usr/bin/env python3
"""aikorea24 썸네일 자동 생성기

Pexels API로 검색어 기반 이미지를 가져와 800x800 WebP 썸네일을 생성합니다.

Usage:
    python3 scripts/auto_thumbnail.py <url> <slug> [--title <title>] [--description <desc>]
    python3 scripts/auto_thumbnail.py --help
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from PIL import Image
from openai import OpenAI

from pipeline.infra.logger import get_scrubbed_logger
logger = get_scrubbed_logger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent
PUBLIC_IMAGES_DIR = PROJECT_DIR / "public" / "images"
PEXELS_USED_FILE = PROJECT_DIR / "config" / "pexels_used_ids.json"

THUMBNAIL_SIZE = (800, 800)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

KST = timezone(timedelta(hours=9))

DEEPSEEK_POOL = [
    "abstract technology", "artificial intelligence", "big data", "binary code",
    "brain neuron", "business meeting", "chatbot", "circuit board",
    "cloud computing", "code programming", "cyber security", "data center",
    "deep learning", "digital brain", "digital transformation", "factory automation",
    "fiber optics", "global network", "hand robot", "internet things",
    "machine learning", "mobile device", "network server", "office technology",
    "robot arm", "saas", "semiconductor", "server room",
    "smart city", "social media", "software code", "startup",
    "stock market", "technology abstract", "virtual reality", "ai chip",
    "blockchain", "cloud server", "computer science",
]


def log(msg):
    ts = datetime.now(KST).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def _load_pexels_key():
    common = os.path.expanduser("~/.env.common")
    if os.path.exists(common):
        with open(common) as f:
            for line in f:
                if line.startswith("PEXELS_API_KEY="):
                    return line.split("=", 1)[1].strip().strip("\"'")
    return ""


def _load_used_ids():
    if not PEXELS_USED_FILE.exists():
        return set()
    try:
        data = json.loads(PEXELS_USED_FILE.read_text())
        return set(data.get("used_ids", []))
    except (json.JSONDecodeError, OSError):
        return set()


def _save_used_id(photo_id):
    used = _load_used_ids()
    used.add(photo_id)
    PEXELS_USED_FILE.parent.mkdir(parents=True, exist_ok=True)
    PEXELS_USED_FILE.write_text(
        json.dumps({"used_ids": sorted(used)}, indent=2, ensure_ascii=False)
    )


def _extract_deepseek_keyword(description):
    key = os.environ.get("DEEPSEEK_API_TOKEN", "")
    if not key:
        common = os.path.expanduser("~/.env.common")
        if os.path.exists(common):
            with open(common) as f:
                for line in f:
                    if line.startswith("DEEPSEEK_API_TOKEN="):
                        key = line.split("=", 1)[1].strip().strip("\"'")
                        break
    if not key:
        return None

    try:
        client = OpenAI(base_url="https://api.deepseek.com/v1", api_key=key)
        pool_str = ", ".join(DEEPSEEK_POOL)
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": f"Pick the best stock photo keyword for this news from: {pool_str}. Or create a 1-2 word similar visual keyword. Return ONLY the keyword, lowercase, max 3 words."},
                {"role": "user", "content": (description or "")[:400]}
            ],
            temperature=0.3,
            max_tokens=20,
        )
        kw = resp.choices[0].message.content.strip().lower()
        return kw if kw else None
    except Exception:
        return None


def search_pexels(query, per_page=15):
    api_key = _load_pexels_key()
    if not api_key:
        log("  Pexels API 키 없음")
        return []
    try:
        url = "https://api.pexels.com/v1/search"
        resp = requests.get(
            url,
            headers={"Authorization": api_key},
            params={"query": query, "per_page": per_page},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("photos", [])
    except Exception as e:
        log(f"  Pexels 검색 에러: {e}")
        return []


def download_image(url):
    try:
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=15, stream=True)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        log(f"  이미지 다운로드 에러: {e}")
        return None


def create_thumbnail(image_data, output_path):
    import io

    img = Image.open(io.BytesIO(image_data))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))

    img = img.resize(THUMBNAIL_SIZE, Image.LANCZOS)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    img.save(output_path, "WEBP", quality=85)
    return output_path


def process_thumbnail(url, slug, title="", description=""):
    text = description or title or ""
    if not text:
        log("  설명/제목 없음, 썸네일 생성 불가")
        return None

    log(f"DeepSeek 키워드 추출 중...")
    keyword = _extract_deepseek_keyword(text)
    if not keyword:
        log("  DeepSeek 실패, fallback: abstract technology")
        keyword = "abstract technology"

    log(f"  키워드: '{keyword}'")

    used_ids = _load_used_ids()
    photos = search_pexels(keyword)
    if not photos:
        log("  Pexels 결과 없음, fallback: artificial intelligence")
        photos = search_pexels("artificial intelligence")

    if not photos:
        log("  최종 fallback 실패")
        return None

    chosen = None
    for photo in photos:
        pid = photo.get("id")
        if pid and pid not in used_ids:
            chosen = photo
            break

    if not chosen:
        log("  모든 결과가 사용됨, 첫번째 이미지 재사용")
        chosen = photos[0]

    pid = chosen.get("id")
    log(f"  선택: ID={pid} | {chosen.get('alt', '')[:60]}")

    img_url = chosen.get("src", {}).get("large")
    if not img_url:
        img_url = chosen.get("src", {}).get("medium")
    if not img_url:
        log("  이미지 URL 없음")
        return None

    log("이미지 다운로드 중...")
    image_data = download_image(img_url)
    if not image_data:
        log("  이미지 다운로드 실패")
        return None

    log(f"  다운로드 완료: {len(image_data):,} bytes")

    output_path = str(PUBLIC_IMAGES_DIR / slug / "thumbnail.webp")
    log(f"썸네일 생성 중: {output_path}")
    create_thumbnail(image_data, output_path)

    file_size = os.path.getsize(output_path)
    log(f"  생성 완료: {file_size:,} bytes")

    _save_used_id(pid)

    rel_path = f"/images/{slug}/thumbnail.webp"
    log(f"  경로: {rel_path}")
    return rel_path


def main():
    parser = argparse.ArgumentParser(
        description="aikorea24 썸네일 자동 생성기 (Pexels)",
        epilog="예시: python3 scripts/auto_thumbnail.py https://... slug --description '...'",
    )
    parser.add_argument("url", help="뉴스 기사 URL (메타데이터 용도)")
    parser.add_argument("slug", nargs="?", help="출력 슬러그 (public/images/{slug}/thumbnail.webp)")
    parser.add_argument("--title", help="기사 제목")
    parser.add_argument("--description", help="기사 설명")
    args = parser.parse_args()

    if not args.slug:
        parser.error("slug 인수가 필요합니다")

    result = process_thumbnail(args.url, args.slug, title=args.title or "", description=args.description or "")
    if result:
        print(f"\n✅ 썸네일 생성 완료: {result}")
    else:
        print("\n❌ 썸네일 생성 실패")
        sys.exit(1)


if __name__ == "__main__":
    main()
