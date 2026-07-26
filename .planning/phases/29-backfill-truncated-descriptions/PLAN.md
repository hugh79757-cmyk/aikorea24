# Phase 29: 기존 블로그 포스트 description 백필 — 문장 경계 기준 재생성

## Objective
기존 826개 블로그 포스트 중 **155개**가 250자 하드컷으로 문장 중간에서 잘린 `description` 필드를 가지고 있음. `_truncate_at_sentence_boundary()` 함수를 사용해 한국어 종결어미(`.`, `!`, `?`, `다`, `요`, `함`, `습니다`, `입니다`, `했습니다`, `임`, `음` 등) 기준으로 잘리도록 재생성.

## Problem Analysis
- **Total posts**: 826 (frontmatter에 description 있음)
- **OK (문장 완결)**: 671개
- **Truncated (문장 중간)**: 155개 (18.8%)
- **예시**: `"배경에는 디"` → `"배경에는 디지털 기술에 대한 피로감이 자리잡고 있습니다."`

## Root Cause
`scripts/blog_draft_generator.py`의 `_save_file()` 함수(라인 322-323)에서:
```python
desc_raw = re.sub(r"[#*>\n\s]+", " ", desc_raw)[:250].strip()  # 250자 하드컷
```
이후 `_truncate_at_sentence_boundary()` 함수 추가(2026-07-26)로 **신규 생성분은 해결**되었으나, 기존 155개는 미적용 상태.

## Files to Modify
| File | Purpose |
|------|---------|
| `scripts/backfill_descriptions.py` | **신규 생성** — 백필 전용 스크립트 |
| `scripts/blog_draft_generator.py` | 참조용 — `_truncate_at_sentence_boundary()` 함수 재사용 |

## Plan

### Task 1: 백필 스크립트 생성
- **File**: `scripts/backfill_descriptions.py` (신규)
- **Logic**:
  1. `src/content/blog/*.md` 전체 순회
  2. `description:` 필드 추출
  3. `_truncate_at_sentence_boundary(desc, 250)` 적용 → 결과가 원본과 다를 때만 업데이트
  4. Frontmatter에서 `description`만 치환 (본문 내용 보존)
  5. `--dry-run` / `--apply` 모드 지원
  6. 진행률 로그 + 변경된 파일 리스트 출력

### Task 2: `_truncate_at_sentence_boundary()` 재사용
- `blog_draft_generator.py`에서 함수 import 또는 복사
- 동일 로직 보장 (한국어 종결어미 패턴 동일 적용)

### Task 3: 실행 및 검증
```bash
# Dry-run 먼저
python3 scripts/backfill_descriptions.py --dry-run

# 적용
python3 scripts/backfill_descriptions.py --apply
```

### Task 4: 검증 기준
- [ ] 155개 truncated → 0개 (전부 문장 완결)
- [ ] 기존 671개 OK 항목은 변경되지 않음 (멱등성)
- [ ] Frontmatter YAML 파싱/직렬화 안전 (따옴표 이스케이프 유지)
- [ ] Git diff로 변경사항 확인 가능

## Acceptance Criteria
1. **All 155 truncated descriptions fixed** — 한국어 종결어미(`.`, `!`, `?`, `다`, `요`, `함`, `습니다`, `입니다`, `했습니다`, `임`, `음`, `이다`, `한다`, `했다` 등)로 끝남
2. **Zero regression** — 671개 정상 description 그대로 유지
3. **Idempotent** — 재실행 시 변경사항 없음
4. **Safe** — Frontmatter 외 본문 내용 절대 변경 안 함
5. **Testable** — `--dry-run`으로 변경 예정 내역 미리 확인 가능

## Implementation Details

### `backfill_descriptions.py` 구조
```python
#!/usr/bin/env python3
"""
기존 블로그 포스트 description 백필 — 문장 경계에서 자르기
Usage:
  python3 scripts/backfill_descriptions.py --dry-run   # 변경 예정만 출력
  python3 scripts/backfill_descriptions.py --apply     # 실제 적용
"""

import sys, os, re, argparse
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR / "scripts"))

from blog_draft_generator import _truncate_at_sentence_boundary

BLOG_DIR = PROJECT_DIR / "src" / "content" / "blog"

KOREAN_ENDINGS = re.compile(
    r'(다|요|함|습니다|입니다|했습니다|임|음|이다|한다|했다|이다|이다'
    r'|하옵니다|하옵니까|하시오|하시요|하쇼|하십시오|하십쇼)[\.\!\?]*\s*$'
)

def is_truncated(desc: str) -> bool:
    """한국어 종결어미로 안 끝나면 truncated로 판단"""
    return not KOREAN_ENDINGS.search(desc.strip())

def process_file(filepath: Path, dry_run: bool = True) -> tuple[bool, str]:
    content = filepath.read_text(encoding='utf-8')
    
    # description 필드 찾기
    m = re.search(r'description:\s*"([^"]*)"', content)
    if not m:
        return False, "no description"
    
    original = m.group(1)
    if not is_truncated(original):
        return False, "already ok"
    
    # 문장 경계에서 자르기
    fixed = _truncate_at_sentence_boundary(original, 250)
    
    if fixed == original:
        return False, "no change after truncate"
    
    # Frontmatter에서 description만 치환
    new_content = content.replace(
        f'description: "{original.replace('"', '\\"')}"',
        f'description: "{fixed.replace('"', '\\"')}"'
    )
    
    if not dry_run:
        filepath.write_text(new_content, encoding='utf-8')
    
    return True, f'"{original[-50:]}" -> "{fixed[-50:]}"'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='변경 사항만 출력')
    parser.add_argument('--apply', action='store_true', help='실제 적용')
    args = parser.parse_args()
    
    if not args.dry_run and not args.apply:
        parser.error('--dry-run 또는 --apply 중 하나는 필수')
    
    files = sorted(BLOG_DIR.glob("*.md"))
    changed = 0
    errors = 0
    
    print(f"총 {len(files)}개 파일 검사 중... (dry_run={args.dry_run})")
    
    for f in files:
        try:
            modified, msg = process_file(f, dry_run=args.dry_run)
            if modified:
                changed += 1
                print(f"  [{'DRY' if args.dry_run else 'FIX'}] {f.name}: {msg}")
        except Exception as e:
            errors += 1
            print(f"  [ERROR] {f.name}: {e}")
    
    print(f"\n완료: 변경 {changed}개, 오류 {errors}개, 전체 {len(files)}개")

if __name__ == '__main__':
    main()
```

## Dependencies
- `scripts/blog_draft_generator.py` — `_truncate_at_sentence_boundary()` 함수 (이미 구현됨)
- Python `re`, `argparse`, `pathlib` (stdlib only)

## Notes
- Phase 28-03(품질 체크리스트)에서 추가된 `validate_thumbnail_quality()`와 유사하게 description 품질도 검증 가능
- 향후 신규 포스트는 `blog_draft_generator.py`에서 자동으로 문장 경계 적용됨 (이미 완료)
- 이 백필은 **일회성** 작업으로, 완료 후 스크립트는 아카이브 또는 삭제