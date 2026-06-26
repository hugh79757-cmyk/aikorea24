#!/usr/bin/env python3
"""
aikorea24 심층글 썸네일 생성기 (1:1 템플릿 방식)

money-aikorea24/scripts/manual-publisher/thumbnail.py 를 참고하여 제작.

동작:
  - 1024x1024 JPG 썸네일 생성
  - 카테고리별 배경 이미지 풀에서 랜덤 선택 (public/bg_img/)
  - 배경 어둡게 처리 (Brightness 0.45)
  - 하단 그라디언트 오버레이
  - 상단 좌측: 카테고리 뱃지 (rounded_rectangle + white text)
  - 중앙 하단: 제목 (64pt, 3줄 제한)
  - 하단 중앙: 도메인 (28pt, 회색)

사용법:
  # 전체 빌드 (src/content/blog/*.md 스캔)
  python3 scripts/generate_thumbnails.py

  # 특정 파일만
  python3 scripts/generate_thumbnails.py --file src/content/blog/2026-06-23-001-anthropic-mythos.md

  # 특정 slug (public/images/thumbnails/{slug}.jpg 출력)
  python3 scripts/generate_thumbnails.py --slug "2026-06-23-001-anthropic-mythos" --title "제목" --category "뉴스"

  # 기존 썸네일 무시하고 전부 다시 생성
  python3 scripts/generate_thumbnails.py --force
"""

import os
import re
import sys
import glob
import random
import textwrap
import argparse
from pathlib import Path
from typing import Optional

try:
    from PIL import Image, ImageDraw, ImageFont, ImageEnhance
except ImportError:
    print("Pillow 미설치. 설치 필요: pip install Pillow")
    sys.exit(1)

# ── 경로 설정 ──────────────────────────────────────────────
PROJECT_DIR = Path(__file__).parent.parent
BLOG_DIR = PROJECT_DIR / "src" / "content" / "blog"
BG_DIR = PROJECT_DIR / "public" / "images"
THUMBNAIL_DIR = PROJECT_DIR / "public" / "images" / "thumbnails"

SIZE = 1024

# ── 카테고리 설정 ──────────────────────────────────────────
# 카테고리 키 → 배경 이미지 파일명 리스트
# 사용자가 public/bg_img/ 에 이미지를 넣으면 여기에 매핑 추가
CATEGORY_BG_POOL = {
    "뉴스":     [],   # bg_img/ 의 모든 이미지 사용
    "AI입문":   [],
    "AI 강좌":  [],
    "소상공인AI": [],
    "교육":     [],
    "심층분석":  [],
    "AI뉴스":   [],
    "AI리뷰":   [],
    "_default": [],   # 미매핑 카테고리용 (bg_img/ 전체)
}

# 카테고리 표시 라벨 (뱃지 텍스트)
CATEGORY_LABELS = {
    "뉴스":     "뉴스",
    "AI입문":   "AI입문",
    "AI 강좌":  "AI 강좌",
    "소상공인AI": "소상공인AI",
    "교육":     "교육",
    "심층분석":  "심층분석",
    "AI뉴스":   "AI뉴스",
    "AI리뷰":   "AI리뷰",
}

# 카테고리별 뱃지 색상 (RGB)
CATEGORY_ACCENT = {
    "뉴스":     (30,  58,  95),    # 남색
    "AI입문":   (6,   95,  70),    # 청록
    "AI 강좌":  (146, 64,  14),    # 갈색
    "소상공인AI": (76,  29,  149),  # 보라
    "교육":     (31,  41,  55),    # 짙은 회색
    "심층분석":  (180, 30,  30),    # 진홍
    "AI뉴스":   (30,  58,  95),    # 남색
    "AI리뷰":   (6,   95,  70),    # 청록
    "_default": (31,  41,  55),    # 짙은 회색
}

DOMAIN = "aikorea24.kr"


# ── 폰트 로더 ──────────────────────────────────────────────
def get_font(size: int):
    """macOS 한글 폰트 우선 로드"""
    candidates = [
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
        "/System/Library/Fonts/Supplemental/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
    ]
    for fpath in candidates:
        if os.path.exists(fpath):
            try:
                return ImageFont.truetype(fpath, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ── frontmatter 파서 ──────────────────────────────────────
def parse_frontmatter(filepath: str) -> dict:
    """간단한 YAML frontmatter 파서"""
    meta = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return meta

    # --- 블록 추출
    m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return meta

    for line in m.group(1).split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # key: "value" 또는 key: value
        kv = re.match(r'^(\w[\w\s]*?):\s*["\']?(.*?)["\']?\s*$', line)
        if kv:
            key = kv.group(1).strip()
            val = kv.group(2).strip()
            # 리스트 처리: ["a", "b"] 또는 ["a","b"]
            list_match = re.match(r"^\[(.*)\]$", val)
            if list_match:
                items = re.findall(r'"([^"]*)"', list_match.group(1))
                if not items:
                    items = [x.strip().strip("'") for x in list_match.group(1).split(",") if x.strip()]
                meta[key] = items
            elif val.lower() == "true":
                meta[key] = True
            elif val.lower() == "false":
                meta[key] = False
            else:
                meta[key] = val

    return meta


def filename_to_slug(filepath: str) -> str:
    """파일명에서 slug 추출 (확장자 제거)"""
    name = Path(filepath).stem
    return name


# ── 배경 이미지 로더 ──────────────────────────────────────
def get_bg_image(category: str) -> Optional[Image.Image]:
    """카테고리에 맞는 배경 이미지 로드 (없으면 None)"""
    if not BG_DIR.exists():
        return None

    # 카테고리별 풀 확인 → 없으면 _default → 있으면 전체 디렉토리
    pool = CATEGORY_BG_POOL.get(category, [])
    if not pool:
        pool = CATEGORY_BG_POOL.get("_default", [])

    if not pool:
        # 디렉토리의 모든 이미지 파일 사용
        exts = ("*.jpg", "*.jpeg", "*.png", "*.webp")
        all_imgs = []
        for ext in exts:
            all_imgs.extend(glob.glob(str(BG_DIR / ext)))
        if not all_imgs:
            return None
        # 랜덤 선택
        chosen = random.choice(all_imgs)
    else:
        chosen_file = random.choice(pool)
        chosen = str(BG_DIR / chosen_file)
        if not os.path.exists(chosen):
            # 파일 없으면 디렉토리 전체에서 랜덤
            exts = ("*.jpg", "*.jpeg", "*.png", "*.webp")
            all_imgs = []
            for ext in exts:
                all_imgs.extend(glob.glob(str(BG_DIR / ext)))
            if not all_imgs:
                return None
            chosen = random.choice(all_imgs)

    try:
        return Image.open(chosen).convert("RGB").resize((SIZE, SIZE))
    except Exception as e:
        print(f"  배경 이미지 로드 실패: {e}")
        return None


# ── 썸네일 생성 핵심 ──────────────────────────────────────
def generate_thumbnail(
    slug: str,
    title: str,
    category: str,
    output_path: Optional[str] = None,
    force: bool = False,
) -> str:
    """
    썸네일 생성 후 저장 경로 반환.

    Args:
        slug: 파일 slug (출력 파일명)
        title: 표시할 제목
        category: 카테고리명
        output_path: 출력 경로 (미지정 시 THUMBNAIL_DIR/{slug}.jpg)
        force: 기존 파일 덮어쓰기 여부

    Returns:
        저장된 파일 경로
    """
    THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        output_path = str(THUMBNAIL_DIR / f"{slug}.jpg")

    if os.path.exists(output_path) and not force:
        print(f"  [SKIP] 이미 존재: {output_path}")
        return output_path

    # ── 1. 배경 이미지 로드 ──
    img = get_bg_image(category)
    if img is None:
        # 배경 없으면 카테고리 악센트색으로 채우기
        accent = CATEGORY_ACCENT.get(category, CATEGORY_ACCENT["_default"])
        img = Image.new("RGB", (SIZE, SIZE), accent)

    # ── 2. 어둡게 처리 (텍스트 가독성) ──
    img = ImageEnhance.Brightness(img).enhance(0.45)

    draw = ImageDraw.Draw(img)

    # ── 3. 하단 그라디언트 오버레이 ──
    overlay = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    mask = Image.new("L", (SIZE, SIZE), 0)
    mask_draw = ImageDraw.Draw(mask)
    for y in range(SIZE // 2, SIZE):
        alpha = int(180 * (y - SIZE // 2) / (SIZE // 2))
        mask_draw.line([(0, y), (SIZE, y)], fill=alpha)
    img = Image.composite(overlay, img, mask)
    draw = ImageDraw.Draw(img)

    # ── 4. 카테고리 뱃지 (상단 좌측) ──
    badge_font = get_font(32)
    badge_text = CATEGORY_LABELS.get(category, category)
    accent = CATEGORY_ACCENT.get(category, CATEGORY_ACCENT["_default"])
    bx, by = 60, 60
    bbox = draw.textbbox((bx, by), badge_text, font=badge_font)
    pad = 14
    draw.rounded_rectangle(
        [bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad],
        radius=24,
        fill=(*accent, 220),
    )
    draw.text((bx, by), badge_text, font=badge_font, fill=(255, 255, 255))

    # ── 5. 제목 (중앙 하단 영역) ──
    title_font = get_font(64)
    # 한글은 1글자 ≈ 1width, 영문은 약간 작음 → width=14 정도면 3줄 64pt에서 적당
    wrapped = textwrap.wrap(title, width=14)[:3]
    line_gap = 80
    total_h = len(wrapped) * line_gap
    start_y = SIZE - total_h - 120

    for i, line in enumerate(wrapped):
        lbbox = draw.textbbox((0, 0), line, font=title_font)
        text_w = lbbox[2] - lbbox[0]
        x = (SIZE - text_w) // 2
        y = start_y + i * line_gap
        # 그림자
        draw.text((x + 2, y + 2), line, font=title_font, fill=(0, 0, 0, 160))
        # 본문
        draw.text((x, y), line, font=title_font, fill=(255, 255, 255))

    # ── 6. 도메인 (하단 중앙) ──
    domain_font = get_font(28)
    dbbox = draw.textbbox((0, 0), DOMAIN, font=domain_font)
    domain_w = dbbox[2] - dbbox[0]
    draw.text(
        ((SIZE - domain_w) // 2, SIZE - 54),
        DOMAIN,
        font=domain_font,
        fill=(200, 200, 200),
    )

    # ── 7. 저장 ──
    img.save(output_path, "JPEG", quality=90)
    return output_path


# ── 배치 모드: blog 디렉토리 스캔 → 썸네일 생성 ──────────
def build_all(force: bool = False):
    """src/content/blog/*.md 를 스캔하여 썸네일 일괄 생성"""
    md_files = sorted(glob.glob(str(BLOG_DIR / "*.md")))
    if not md_files:
        print(f"[ERROR] 블로그 파일 없음: {BLOG_DIR}")
        return

    print(f"[INFO] 스캔된 블로그 파일: {len(md_files)}개\n")

    created = 0
    skipped = 0
    errors = 0

    for md_path in md_files:
        slug = filename_to_slug(md_path)
        meta = parse_frontmatter(md_path)

        title = meta.get("title", slug)
        category = meta.get("category", "_default")

        # draft 스킵 (선택적)
        if meta.get("draft") is True and not force:
            skipped += 1
            continue

        out_path = str(THUMBNAIL_DIR / f"{slug}.jpg")
        if os.path.exists(out_path) and not force:
            skipped += 1
            continue

        try:
            result = generate_thumbnail(
                slug=slug,
                title=title,
                category=category,
                force=force,
            )
            created += 1
            print(f"  [OK] {slug} ({category})")
        except Exception as e:
            errors += 1
            print(f"  [ERR] {slug}: {e}")

    print(f"\n[DONE] 생성: {created} / 스킵: {skipped} / 에러: {errors}")


# ── 단일 파일 모드 ──────────────────────────────────────
def generate_single_file(filepath: str, force: bool = False):
    """단일 마크다운 파일의 썸네일 생성"""
    if not os.path.exists(filepath):
        print(f"[ERROR] 파일 없음: {filepath}")
        return

    slug = filename_to_slug(filepath)
    meta = parse_frontmatter(filepath)
    title = meta.get("title", slug)
    category = meta.get("category", "_default")

    print(f"파일: {filepath}")
    print(f"  slug: {slug}")
    print(f"  title: {title}")
    print(f"  category: {category}\n")

    result = generate_thumbnail(
        slug=slug,
        title=title,
        category=category,
        force=force,
    )
    print(f"  생성 완료: {result}")


# ── CLI ──────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="aikorea24 심층글 썸네일 생성기",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python3 scripts/generate_thumbnails.py                     # 전체 빌드
  python3 scripts/generate_thumbnails.py --force             # 전부 다시 생성
  python3 scripts/generate_thumbnails.py --file path/to.md   # 특정 파일
  python3 scripts/generate_thumbnails.py --slug my-slug --title "제목" --category "뉴스"
        """,
    )
    parser.add_argument("--file", help="특정 마크다운 파일 경로")
    parser.add_argument("--slug", help="출력 slug (단일 생성 모드)")
    parser.add_argument("--title", help="제목 (단일 생성 모드)")
    parser.add_argument("--category", default="뉴스", help="카테고리 (단일 생성 모드)")
    parser.add_argument("--output", help="출력 파일 경로 (단일 생성 모드)")
    parser.add_argument("--force", action="store_true", help="기존 썸네일 덮어쓰기")

    args = parser.parse_args()

    # bg_img 디렉토리 생성 안내
    if not BG_DIR.exists():
        print(f"[INFO] 배경 이미지 디렉토리 없음: {BG_DIR}")
        print(f"       카테고리 악센트색 배경으로 썸네일이 생성됩니다.")
        print(f"       썸네일 품질 향상을 위해 public/bg_img/ 에 이미지를 추가하세요.\n")

    if args.slug and args.title:
        # 단일 slug 모드
        result = generate_thumbnail(
            slug=args.slug,
            title=args.title,
            category=args.category,
            output_path=args.output,
            force=args.force,
        )
        print(f"생성 완료: {result}")
    elif args.file:
        # 단일 파일 모드
        generate_single_file(args.file, force=args.force)
    else:
        # 전체 배치 모드
        build_all(force=args.force)


if __name__ == "__main__":
    main()
