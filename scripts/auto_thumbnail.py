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
import random
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from PIL import Image
from pipeline.infra.logger import get_scrubbed_logger
logger = get_scrubbed_logger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent
PUBLIC_IMAGES_DIR = PROJECT_DIR / "public" / "images"
PEXELS_USED_FILE = PROJECT_DIR / "config" / "pexels_used_ids.json"

# model_router (무료 LLM 폴백 체인) import
sys.path.insert(0, os.path.join(PROJECT_DIR, 'scripts', 'threads', 'v3'))
from model_router import chat_completion

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
    """무료 LLM 폴백 체인으로 썸네일 키워드 추출"""
    try:
        keyword = chat_completion(
            messages=[
                {"role": "system", "content": f"Pick the best stock photo keyword for this news from: {', '.join(DEEPSEEK_POOL)}. Or create a 1-2 word similar visual keyword. Return ONLY the keyword, lowercase, max 3 words."},
                {"role": "user", "content": (description or "")[:400]},
            ],
            system_prompt=None,
            temperature=0.3,
            max_tokens=20,
            model_override=None,  # 무료 LLM 폴백 체인 사용
        )
        if keyword:
            kw = keyword.strip().lower()
            if kw:
                log(f"  LLM 키워드 추출 성공: '{kw}'")
                return kw
    except Exception as e:
        log(f"  LLM 키워드 추출 실패: {e}")
    # LLM 실패 시 랜덤 fallback
    fallback = random.choice(DEEPSEEK_POOL)
    log(f"  LLM 실패 → 랜덤 fallback: '{fallback}'")
    return fallback


def search_pexels(query, per_page=15, max_pages=3):
    """Pexels 검색 with pagination (default 3 pages = up to 45 candidates)"""
    api_key = _load_pexels_key()
    if not api_key:
        log("  Pexels API 키 없음")
        return []
    
    all_photos = []
    for page in range(1, max_pages + 1):
        try:
            url = "https://api.pexels.com/v1/search"
            resp = requests.get(
                url,
                headers={"Authorization": api_key},
                params={"query": query, "per_page": per_page, "page": page},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            photos = data.get("photos", [])
            if not photos:
                break
            all_photos.extend(photos)
            log(f"  Pexels 검색: '{query}' page={page} → {len(photos)}장 (누적 {len(all_photos)})")
        except Exception as e:
            log(f"  Pexels 검색 에러 (page={page}): {e}")
            break
    
    return all_photos


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


def validate_thumbnail_quality(filepath, min_size_kb=15):
    """Validate thumbnail quality: file size, dimensions, format, integrity.
    
    Args:
        filepath: Path to the thumbnail file
        min_size_kb: Minimum file size in KB (default 15KB)
        
    Returns:
        tuple: (is_valid: bool, reason: str)
    """
    try:
        # Check file exists
        if not os.path.exists(filepath):
            return False, "파일 없음"
        
        # Check file size
        file_size = os.path.getsize(filepath)
        if file_size < min_size_kb * 1024:
            return False, f"파일 크기 미달: {file_size//1024}KB < {min_size_kb}KB"
        
        # Check with PIL
        with Image.open(filepath) as img:
            # Verify it's a valid image
            img.verify()
            
        # Re-open for dimension check (verify() closes the file)
        with Image.open(filepath) as img:
            # Check dimensions
            if img.size != THUMBNAIL_SIZE:
                return False, f"해상도 불일치: {img.size} != {THUMBNAIL_SIZE}"
            
            # Check format
            if img.format != "WEBP":
                return False, f"포맷 불일치: {img.format} != WEBP"
        
        return True, "OK"
    except Exception as e:
        return False, f"검증 에러: {e}"


def _pick_unused_photo(photos, used_ids):
    if not photos:
        return None
    for photo in photos:
        pid = photo.get("id")
        if pid and pid not in used_ids:
            return photo
    return None


def check_thumbnail_duplicates(thumbnail_paths):
    """Check for duplicate thumbnails by MD5 hash.
    
    Args:
        thumbnail_paths: List of absolute paths to thumbnail files
        
    Returns:
        dict: {"duplicates": [(path1, path2, hash), ...], "unique_count": N, "hash_map": {hash: [paths]}}
    """
    import hashlib
    hash_map = {}
    duplicates = []
    
    for path in thumbnail_paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            if file_hash in hash_map:
                hash_map[file_hash].append(path)
                duplicates.append((hash_map[file_hash][0], path, file_hash))
            else:
                hash_map[file_hash] = [path]
        except Exception as e:
            log(f"  ⚠️ 해시 계산 실패 {path}: {e}")
    
    unique_count = len(hash_map)
    return {
        "duplicates": duplicates,
        "unique_count": unique_count,
        "hash_map": hash_map
    }


def _use_default_thumbnail(slug):
    src = PROJECT_DIR / "public" / "images" / "news-keyword-og.webp"
    dst = PUBLIC_IMAGES_DIR / slug / "thumbnail.webp"
    if not src.exists():
        log("  기본 placeholder 이미지 없음, 썸네일 생성 포기")
        return None
    try:
        os.makedirs(os.path.dirname(str(dst)), exist_ok=True)
        shutil.copy(str(src), str(dst))
        log(f"  기본 placeholder 사용: {dst}")
        return f"/images/{slug}/thumbnail.webp"
    except OSError as e:
        log(f"  기본 placeholder 복사 실패: {e}")
        return None


def process_thumbnail(url, slug, title="", description=""):
    text = description or title or ""
    if not text:
        log("  설명/제목 없음, 썸네일 생성 불가")
        return None

    log(f"  LLM 키워드 추출 중...")
    keyword = _extract_deepseek_keyword(text)
    # _extract_deepseek_keyword now always returns a keyword (random fallback if API fails)
    
    log(f"  키워드: '{keyword}'")

    used_ids = _load_used_ids()
    photos = search_pexels(keyword, max_pages=3)
    if not photos:
        log("  Pexels 결과 없음, fallback: artificial intelligence")
        photos = search_pexels("artificial intelligence", max_pages=3)

    chosen = _pick_unused_photo(photos, used_ids)
    fallback_reason = None
    
    if not chosen:
        # 미사용 사진이 없으면 대체 쿼리로 재시도 (원본 키워드 제외)
        alt_queries = [q for q in DEEPSEEK_POOL if q != keyword][:5]
        log(f"  미사용 사진 없음, 대체 쿼리 {len(alt_queries)}개 시도 (원본 '{keyword}' 제외)")
        
        for alt in alt_queries:
            alt_photos = search_pexels(alt, max_pages=3)
            chosen = _pick_unused_photo(alt_photos, used_ids)
            if chosen:
                fallback_reason = f"alt_query={alt}"
                log(f"  대체 쿼리 성공: '{alt}' → ID={chosen.get('id')}")
                break
    
    # 최종 폴백: placeholder 사용 (photos[0] 재사용 안 함)
    if not chosen:
        fallback_reason = "all_exhausted"
        log("  모든 Pexels 결과 소진 → placeholder 사용")
        return _use_default_thumbnail(slug)

    pid = chosen.get("id")
    log(f"  선택: ID={pid} | {chosen.get('alt', '')[:60]} | fallback={fallback_reason or 'none'}")

    img_url = chosen.get("src", {}).get("large")
    if not img_url:
        img_url = chosen.get("src", {}).get("medium")
    if not img_url:
        log("  이미지 URL 없음, 기본 placeholder 사용")
        return _use_default_thumbnail(slug)

    log("이미지 다운로드 중...")
    image_data = download_image(img_url)
    if not image_data:
        log("  이미지 다운로드 실패, 기본 placeholder 사용")
        return _use_default_thumbnail(slug)

    log(f"  다운로드 완료: {len(image_data):,} bytes")

    output_path = str(PUBLIC_IMAGES_DIR / slug / "thumbnail.webp")
    log(f"썸네일 생성 중: {output_path}")
    create_thumbnail(image_data, output_path)

    file_size = os.path.getsize(output_path)
    log(f"  생성 완료: {file_size:,} bytes")

    # 품질 검증 (Plan 28-03)
    is_valid, reason = validate_thumbnail_quality(output_path)
    if not is_valid:
        log(f"  ⚠️ 품질 검증 실패: {reason} → 재시도/placeholder")
        # 재시도: 다른 키워드로 다시 시도 (최대 2회)
        for retry in range(2):
            log(f"  🔄 품질 재시도 {retry+1}/2 (다른 키워드)")
            # 새로운 키워드로 다시 검색
            retry_keyword = random.choice([q for q in DEEPSEEK_POOL if q != keyword])
            retry_photos = search_pexels(retry_keyword, max_pages=3)
            retry_chosen = _pick_unused_photo(retry_photos, used_ids)
            if retry_chosen:
                retry_url = retry_chosen.get("src", {}).get("large") or retry_chosen.get("src", {}).get("medium")
                if retry_url:
                    retry_data = download_image(retry_url)
                    if retry_data:
                        create_thumbnail(retry_data, output_path)
                        is_valid, reason = validate_thumbnail_quality(output_path)
                        if is_valid:
                            log(f"  ✅ 재시도 성공: {retry_keyword}")
                            pid = retry_chosen.get("id")
                            break
                        else:
                            log(f"  ❌ 재시도 품질 실패: {reason}")
        
        if not is_valid:
            log("  ⚠️ 품질 재시도 모두 실패 → placeholder 사용")
            return _use_default_thumbnail(slug)

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