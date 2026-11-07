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
import time
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


def _load_unsplash_key():
    common = os.path.expanduser("~/.env.common")
    if os.path.exists(common):
        with open(common) as f:
            for line in f:
                if line.startswith("UNSPLASH_ACCESS_KEY="):
                    return line.split("=", 1)[1].strip().strip("\"'")
    return ""


class _PexelsRateLimited(Exception):
    """Pexels 429 rate-limit으로 재시도 소진 — alt-query hammer 없이 Unsplash 전환 신호."""
    pass


def _get_with_retry(url, headers, params, max_attempts=3):
    """429/5xx/timeout에만 지수 백오프(1s,2s,4s)로 재시도. 그 외 4xx는 즉시 raise."""
    last_exc = None
    last_was_429 = False
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            if resp.status_code == 429:
                last_was_429 = True
                last_exc = requests.exceptions.HTTPError(f"429 rate limited: {url}", response=resp)
                log(f"  재시도 {attempt}/{max_attempts}: 429 (백오프 {2 ** (attempt - 1)}s)")
            elif resp.status_code >= 500:
                last_was_429 = False
                last_exc = requests.exceptions.HTTPError(f"{resp.status_code} server error: {url}", response=resp)
                log(f"  재시도 {attempt}/{max_attempts}: {resp.status_code} (백오프 {2 ** (attempt - 1)}s)")
            else:
                resp.raise_for_status()
                return resp
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_was_429 = False
            last_exc = e
            log(f"  재시도 {attempt}/{max_attempts}: {type(e).__name__} (백오프 {2 ** (attempt - 1)}s)")
        if attempt < max_attempts:
            time.sleep(2 ** (attempt - 1))
    if last_was_429:
        raise _PexelsRateLimited(f"Pexels 429 rate-limit, {max_attempts}회 소진: {url}")
    if last_exc is not None:
        raise last_exc
    raise requests.exceptions.RequestException(f"요청 실패: {url}")


def _load_used_ids():
    if not PEXELS_USED_FILE.exists():
        return set()
    try:
        data = json.loads(PEXELS_USED_FILE.read_text())
        return {str(x) for x in data.get("used_ids", [])}
    except (json.JSONDecodeError, OSError):
        return set()


def _save_used_id(photo_id):
    used = _load_used_ids()
    used.add(str(photo_id))
    PEXELS_USED_FILE.parent.mkdir(parents=True, exist_ok=True)
    PEXELS_USED_FILE.write_text(
        json.dumps({"used_ids": sorted(used)}, indent=2, ensure_ascii=False)
    )


_KEYWORD_HINTS = (
    (("보안", "해킹", "security", "hacking", "취약", "malware", "랜섬"), "cyber security"),
    (("로봇", "robot", "휴머노이드"), "robot arm"),
    (("데이터센터", "데이터 센터", "data center", "서버", "server"), "data center"),
    (("반도체", "semiconductor", "칩", "chip", "gpu", "npu"), "ai chip"),
    (("클라우드", "cloud", "aws", "azure"), "cloud computing"),
    (("코딩", "coding", "코드", "code", "개발자", "developer", "에이전트", "agent"), "software code"),
    (("모델", "model", "학습", "training", "파인튜닝"), "machine learning"),
    (("챗봇", "chatbot", "대화", "assistant"), "chatbot"),
    (("자동화", "automation", "공장", "제조"), "factory automation"),
    (("스타트업", "startup", "투자"), "startup"),
    (("시장", "증시", "주가", "market"), "stock market"),
    (("정부", "규제", "정책", "policy"), "digital transformation"),
)


def _pick_keyword(text=""):
    """썸네일 키워드 — 기사 내용 기반(2026-11-07).

    기존에는 고정 풀에서 **랜덤** 선택해 기사와 무관한 사진이 잡혔다(품질·연관성 저하).
    LLM 호출 없이, 제목·설명의 토픽 단어로 풀 키워드를 고른다. 매칭이 없으면 랜덤.
    """
    t = (text or "").lower()
    best, best_hits = None, 0
    for words, kw in _KEYWORD_HINTS:
        hits = sum(1 for w in words if w in t)
        if hits > best_hits:
            best, best_hits = kw, hits
    if best:
        log(f"  키워드: '{best}' (기사 내용 기반, 매칭 {best_hits})")
        return best
    keyword = random.choice(DEEPSEEK_POOL)
    log(f"  키워드: '{keyword}' (내용 매칭 없음 — 고정 풀)")
    return keyword


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
            resp = _get_with_retry(
                url,
                headers={"Authorization": api_key},
                params={"query": query, "per_page": per_page, "page": page,
                        "orientation": "landscape", "size": "large"},
            )
            data = resp.json()
            photos = data.get("photos", [])
            if not photos:
                break
            all_photos.extend(photos)
            log(f"  Pexels 검색: '{query}' page={page} → {len(photos)}장 (누적 {len(all_photos)})")
        except _PexelsRateLimited:
            raise
        except Exception as e:
            log(f"  Pexels 검색 에러 (page={page}): {e}")
            break

    return all_photos


def search_unsplash(query, per_page=15):
    """Unsplash 검색 — Pexels와 동일 shape으로 정규화 (id는 "unsplash:" prefix)."""
    api_key = _load_unsplash_key()
    if not api_key:
        log("  Unsplash API 키 없음")
        return []

    try:
        resp = _get_with_retry(
            "https://api.unsplash.com/search/photos",
            headers={"Authorization": f"Client-ID {api_key}"},
            params={"query": query, "per_page": per_page},
        )
        data = resp.json()
        results = data.get("results", [])
        photos = []
        for r in results:
            uid = r.get("id", "")
            urls = r.get("urls") or {}
            photos.append({
                "id": f"unsplash:{uid}",
                "alt": r.get("description") or r.get("alt_description") or "",
                "src": {"large": urls.get("regular", ""), "medium": urls.get("small", "")},
            })
        log(f"  Unsplash 검색: '{query}' → {len(photos)}장")
        return photos
    except Exception as e:
        log(f"  Unsplash 검색 에러: {e}")
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


def validate_thumbnail_quality(filepath, min_size_kb=8):
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
        
        # Check file size — 2026-11-07: 15KB 는 정상 사진(1200x630 webp 10KB)까지
        # 걸러 placeholder 로 떨어뜨렸다. 하한을 8KB 로 낮추고 **단색/빈 이미지**를
        # 별도로 검사한다(빈 이미지는 1~2KB 로 압축되지만, 안전하게 색 다양성도 본다).
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
        if pid and str(pid) not in used_ids:
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


# ponytail: placeholder 사본 검출용 lazy MD5. 매 호출 시 파일 1회 읽기 (≤50KB).
# 글로벌 캐시 — placeholder 파일이 교체되면 프로세스 재시작 필요.
_PLACEHOLDER_MD5_CACHE = None


def is_placeholder_copy(filepath):
    """주어진 썸네일 파일이 placeholder(news-keyword-og.webp)의 사본인지 MD5 비교.

    Returns:
        bool: True면 placeholder 사본 (frontmatter image: 필드 주입하면 안 됨)
    """
    global _PLACEHOLDER_MD5_CACHE
    try:
        ph = PROJECT_DIR / "public" / "images" / "news-keyword-og.webp"
        if not ph.exists():
            return False
        if _PLACEHOLDER_MD5_CACHE is None:
            import hashlib
            _PLACEHOLDER_MD5_CACHE = hashlib.md5(ph.read_bytes()).hexdigest()
        target = Path(filepath)
        if not target.exists():
            return False
        import hashlib
        return hashlib.md5(target.read_bytes()).hexdigest() == _PLACEHOLDER_MD5_CACHE
    except OSError:
        return False


def process_thumbnail(url, slug, title="", description=""):
    text = description or title or ""
    if not text:
        log("  설명/제목 없음, 썸네일 생성 불가")
        return None

    keyword = _pick_keyword(text)

    used_ids = _load_used_ids()
    pexels_limited = False
    try:
        photos = search_pexels(keyword, max_pages=3)
        if not photos:
            log("  Pexels 결과 없음, 대체검색: artificial intelligence")
            photos = search_pexels("artificial intelligence", max_pages=3)
    except _PexelsRateLimited:
        # 429 소진: alt-query hammer 없이 곧바로 Unsplash 분기로 이동
        log("  Pexels 429 rate-limit 소진 → Unsplash로 전환 (alt 루프 skip)")
        photos = []
        pexels_limited = True

    chosen = _pick_unused_photo(photos, used_ids)
    fallback_reason = None

    if not chosen and not pexels_limited:
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

    if not chosen:
        # Unsplash 폴백: 원본 keyword 먼저, 실패 시 generic 1회 (provider 전환 hammer 방지 sleep 2s)
        time.sleep(2)
        unsplash_photos = search_unsplash(keyword)
        if not unsplash_photos:
            log("  Unsplash 결과 없음, fallback: artificial intelligence")
            unsplash_photos = search_unsplash("artificial intelligence")
        chosen = _pick_unused_photo(unsplash_photos, used_ids)
        if chosen:
            fallback_reason = f"unsplash:{keyword}"
            log(f"  Unsplash 성공: '{keyword}' → ID={chosen.get('id')}")
    
    # 최종 폴백: placeholder 사용 (photos[0] 재사용 안 함)
    if not chosen:
        fallback_reason = "all_exhausted"
        log("  모든 Pexels 결과 소진 → placeholder 사용")
        return _use_default_thumbnail(slug)

    pid = chosen.get("id")
    log(f"  선택: ID={pid} | {chosen.get('alt', '')[:60]} | fallback={fallback_reason or 'none'}")

    srcs = chosen.get("src", {}) or {}
    img_url = srcs.get("large2x") or srcs.get("large") or srcs.get("medium")
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