# Phase 28.1: 썸네일 파이프라인 UnboundLocalError 핫픽스

## Objective
2026-07-26 저녁 6개 블로그 포스트 썸네일 전면 실패의 근본 원인(UnboundLocalError) 수정.
기존 6개 포스트 썸네일 백필 생성. 재발 방지 검증 추가.

## Incident Summary
| 항목 | 내용 |
|------|------|
| **발생** | 2026-07-26 22:15 KST, 저녁 blog-draft 실행 |
| **증상** | 6개 신규 포스트 전부 썸네일 없이 발행 |
| **원인** | `blog_draft_generator.py` `main()` 함수 내 라인 627의 `from auto_thumbnail import process_thumbnail`가 Python scoping shadowing 유발 → 라인 580의 `process_thumbnail()` 호출이 `UnboundLocalError`로 실패 |
| **영향** | Phase 28(28-01/02/03)의 **모든 썸네일 관련 코드가 단 한 줄도 실행 안 됨** |
| **탐지** | 사용자 보고 (포스트 확인 중 발견). 품질 체크리스트에 "파일 없음" 6건 기록되었으나 배포 차단 안 함 |

## Root Cause Detail
```python
# blog_draft_generator.py, main() function

# ... (중략) ...

# 라인 578-588: 썸네일 생성 (Phase 28 이전 코드)
try:
    slug = ...
    thumb_rel = process_thumbnail(...)    # ← UnboundLocalError!
    ...
except Exception as thumb_e:
    log(f"  ⚠️ ... {thumb_e}")            # ← 에러 로그만 남김, 계속 진행

# ... (중략 - generated 분류, 중복 검증 등) ...

# 라인 627: DUPLICATE IMPORT (Phase 28-02에서 추가)
from auto_thumbnail import process_thumbnail, DEEPSEEK_POOL  # ← 이 줄이 문제
```

Python은 함수 전체를 컴파일할 때 함수 내 `from X import Y`를 보고 `Y`를 local 변수로 선언. 라인 627이 아직 실행되지 않은 상태에서 라인 580의 `process_thumbnail`을 찾으면 local에 없어 `UnboundLocalError`.

## Tasks

### Task 1: 버그 수정 — 중복 import 제거
**File**: `scripts/blog_draft_generator.py`
**Location**: `main()` 함수, 라인 627

**변경**: `from auto_thumbnail import process_thumbnail, DEEPSEEK_POOL` 제거
- `process_thumbnail`는 이미 라인 45에서 module-level import 됨
- `DEEPSEEK_POOL`도 module-level import로 추가하거나, `alt_queries` 로직에서 `DEEPSEEK_POOL` 직접 참조하도록 변경
- `import random`은 라인 628에서 제거 (함수 시작 부분으로 이동 또는 유지)

**수정 후 코드**:
```python
# 라인 627 (기존):
#   from auto_thumbnail import process_thumbnail, DEEPSEEK_POOL
#   import random
#
# 수정:
#   (import 라인 완전 제거 — process_thumbnail는 module-level에서 이미 import됨)
#   DEEPSEEK_POOL 사용을 위해 'from auto_thumbnail import DEEPSEEK_POOL'를
#   module-level (라인 45 근처)로 이동
```

**Module-level import 변경** (라인 45):
```python
# 기존:
from auto_thumbnail import process_thumbnail, check_thumbnail_duplicates, validate_thumbnail_quality
# 수정:
from auto_thumbnail import process_thumbnail, check_thumbnail_duplicates, validate_thumbnail_quality, DEEPSEEK_POOL
```

### Task 2: 품질 체크리스트 실패 시 배포 차단 (또는 경고 강화)
**File**: `scripts/blog_draft_generator.py`
**Location**: `[5b]` 품질 체크리스트 섹션 (라인 706-728)

**현재 동작**: 품질 이슈가 있어도 로그만 남기고 배포 진행
**수정 방안**: 모든 썸네일이 실패한 경우(quality_passed == 0) 배포 차단 또는 사용자 명시적 경고

```python
# 라인 726-728 이후에 추가:
if quality_passed == 0 and len(quality_issues) > 0:
    log("  ❌ 모든 썸네일 품질 검증 실패 — 배포 차단")
    send_telegram(f"❌ [{today_str}] 썸네일 전면 실패: {len(quality_issues)}건 — 발행 차단")
    # generated는 유지하되 배포 skip (포스트는 생성되었으나 썸네일 없음)
    # 또는 generated 초기화
    return  # early exit
```

**주의**: 배포 차단 시:
- 블로그 포스트는 생성되었으나 라이브에는 반영 안 됨
- 다음 실행 시 `deep_dive_url` 중복 체크로 skip될 수 있음
- 사용자 판단 필요: **soft 차단(경고만)** vs **hard 차단(배포 중단)**

### Task 3: 7/26 포스트 6개 썸네일 백필 생성
**방법**: 수동 실행으로 `process_thumbnail()` 직접 호출

```bash
cd ~/Projects/aikorea24
python3 -c "
from scripts.blog_draft_generator import PROJECT_DIR
from scripts.auto_thumbnail import process_thumbnail
import os, glob

for fp in sorted(glob.glob('src/content/blog/2026-07-26-*.md')):
    slug = os.path.basename(fp).replace('.md', '').lower()
    print(f'Generating thumbnail for: {slug}')
    rel = process_thumbnail('', slug)
    if rel:
        print(f'  ✅ {rel}')
    else:
        print(f'  ❌ 실패')
"
```

**사전 확인**: 수정된 `blog_draft_generator.py`로 실행되어야 함 (import 버그 수정 후)

### Task 4: 테스트 추가
**File**: `tests/test_blog_draft_generator.py` (신규) 또는 `tests/test_auto_thumbnail.py`

**테스트 케이스**:
1. `test_process_thumbnail_import_scoping`: module-level import와 함수 내 동일 이름 import가 UnboundLocalError를 유발하지 않는지 검증
   - `main()` 함수에서 `process_thumbnail` 호출 전에 `from auto_thumbnail import process_thumbnail`가 있는 경우/없는 경우 비교
2. `test_quality_checklist_blocks_deploy_on_all_fail`: 모든 썸네일 실패 시 배포 차단 로직 검증

**검증 방법**: `python3 -m py_compile scripts/blog_draft_generator.py` + `python3 -m pytest tests/ -v -k "thumbnail"`

## Dependencies
- `scripts/blog_draft_generator.py` (Task 1, 2)
- `scripts/auto_thumbnail.py` (Task 3)
- Python module scope 이해 (Task 1)

## Risk Assessment
| 위험 | 확률 | 영향 | 대비 |
|------|------|------|------|
| 다른 함수 내 import도 shadowing 유발 | 낮음 | 중간 | `grep -rn "from.*import" scripts/blog_draft_generator.py \| grep -v "^.*:"`로 전수조사 |
| 백필 중 Pexels API 실패 | 중간 | 낮음 | placeholder fallback 보장됨 (45.6KB 확인) |
| 배포 차단 로직으로 인한 발행 누락 | 낮음 | 중간 | Telegram 알림 + 수동 재배포로 복구 가능 |

## Acceptance Criteria
1. [ ] **Task 1**: `blog_draft_generator.py`에서 `from auto_thumbnail import process_thumbnail` 함수 내 import 제거 (UnboundLocalError 해결)
2. [ ] **Task 1**: `DEEPSEEK_POOL`이 module-level import로 사용 가능 (`from auto_thumbnail import DEEPSEEK_POOL`)
3. [ ] **Task 2**: 모든 썸네일 실패 시 배포 차단 또는 명시적 경고 메시지
4. [ ] **Task 3**: 7/26 6개 포스트 썸네일 정상 생성 확인 (`public/images/2026-07-26-*/thumbnail.webp` 존재)
5. [ ] **Task 4**: `python3 -m py_compile scripts/blog_draft_generator.py` 통과
6. [ ] **Task 4**: 기존 테스트 전부 통과
7. [ ] **회귀 방지**: 동일 패턴의 함수 내 import가 다른 곳에 없는지 확인

## Appendix: 유사 패턴 전수조사
`main()` 함수 내 `from X import Y` 패턴 사용 현황:
| 라인 | 코드 | 위험 | 조치 |
|------|------|------|------|
| 627 | `from auto_thumbnail import process_thumbnail, DEEPSEEK_POOL` | 🔴 UnboundLocalError 발생 | 제거 (Task 1) |
| 698 | `import validate_blog_posts as vbp` | 🟡 `import X as Y` — Python 3.14에서 동일 shadowing 가능 | 확인 필요 |
| 734 | `import subprocess` | 🟢 `import X`는 `from X import Y`와 shadowing 규칙 다름 | 안전 |
| 754 | `import subprocess` | 🟢 동일 | 안전 |
