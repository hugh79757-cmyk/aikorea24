#!/usr/bin/env python3
"""
기존 블로그 포스트 description 백필 — 문장 경계에서 자르기
Usage:
  python3 scripts/backfill_descriptions.py --dry-run   # 변경 예정만 출력
  python3 scripts/backfill_descriptions.py --apply     # 실제 적용
"""

import sys
import re
import argparse
from pathlib import Path

# 프로젝트 루트 경로 추가
PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR / "scripts"))

# blog_draft_generator에서 첫 문장 추출 함수 import
from blog_draft_generator import _extract_first_sentence

BLOG_DIR = PROJECT_DIR / "src" / "content" / "blog"


def parse_frontmatter(content: str):
    """Parse frontmatter using PyYAML for safety"""
    if not content.startswith('---'):
        return None, None, None
    
    parts = content.split('---', 2)
    if len(parts) < 3:
        return None, None, None
    
    fm_text = parts[1]
    body = parts[2]
    
    try:
        import yaml
        fm = yaml.safe_load(fm_text)
        if fm is None:
            fm = {}
    except Exception:
        # If YAML parsing fails, return original
        return None, None, None
    
    return fm, body, parts[2]


def process_file(filepath: Path, dry_run: bool = True) -> tuple[bool, str]:
    """단일 파일 처리 — description 필드를 본문 첫 문장으로 교체"""
    content = filepath.read_text(encoding='utf-8')
    
    if not content.startswith('---'):
        return False, "no frontmatter"
    
    parts = content.split('---', 2)
    if len(parts) < 3:
        return False, "invalid frontmatter"
    
    fm_text = parts[1]
    body = parts[2].strip()
    
    if not body:
        return False, "empty body"
    
    # Parse frontmatter with PyYAML
    try:
        import yaml
        fm = yaml.safe_load(parts[1])
        if fm is None:
            fm = {}
    except Exception:
        return False, "yaml parse error"
    
    if not body:
        return False, "empty body"
    
    # 본문에서 첫 번째 완전한 문장 추출
    first_sentence = _extract_first_sentence(body, 300)
    if not first_sentence:
        return False, "no sentence found"
    
    # 기존 description 추출
    original_desc = fm.get('description', '')
    if not original_desc:
        return False, "no description"
    
    # 결과가 원본과 동일하면 skip (멱등성)
    if first_sentence == original_desc:
        return False, "already ok"
    
    # Update frontmatter with new description
    fm['description'] = first_sentence
    fm['category'] = fm.get('category', '뉴스')
    
    # Ensure date is string
    if 'date' in fm and not isinstance(fm['date'], str):
        fm['date'] = str(fm['date'])
    
    # Serialize frontmatter with PyYAML
    import yaml
    new_fm = yaml.dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False)
    
    # Reconstruct content
    body_part = parts[2]  # Keep original body unchanged
    new_content = f'---\n{new_fm}---{parts[2]}'
    
    if not dry_run:
        filepath.write_text(new_content, encoding='utf-8')
    
    return True, f'"{original_desc[-60:]}" -> "{first_sentence[-60:]}"'


def main():
    parser = argparse.ArgumentParser(
        description="블로그 description 백필 — 문장 경계에서 자르기"
    )
    parser.add_argument('--dry-run', action='store_true', help='변경 사항만 출력 (적용 안 함)')
    parser.add_argument('--apply', action='store_true', help='실제 적용')
    args = parser.parse_args()
    
    if not args.dry_run and not args.apply:
        parser.error('--dry-run 또는 --apply 중 하나는 필수')
    
    files = sorted(BLOG_DIR.glob("*.md"))
    changed = 0
    errors = 0
    skipped = 0
    
    print(f"총 {len(files)}개 파일 검사 중... (dry_run={args.dry_run})")
    
    for f in files:
        try:
            modified, msg = process_file(f, dry_run=args.dry_run)
            if modified:
                changed += 1
                print(f"  [{'DRY' if args.dry_run else 'FIX'}] {f.name}: {msg}")
            elif msg == "already ok":
                skipped += 1
        except Exception as e:
            errors += 1
            print(f"  [ERROR] {f.name}: {e}")
    
    print(f"\n완료: 변경 {changed}개, 정상(skip) {skipped}개, 오류 {errors}개, 전체 {len(files)}개")
    
    if args.dry_run and changed > 0:
        print("\n--apply 플래그로 실제 적용 가능")


if __name__ == '__main__':
    main()