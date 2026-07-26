# Phase 28.1 Research: Thumbnail Pipeline UnboundLocalError

## Problem Statement
**2026-07-26 22:15 실행**: 6개 블로그 포스트가 **전부 썸네일 없이 발행**됨.
`public/images/2026-07-26-*/` 디렉토리 자체가 존재하지 않으며, frontmatter에 `image:` 필드도 없음.

## Root Cause Analysis

### 결정적 증거 (blog_draft.log)
```
[22:15:37] ⚠️ '먼데이닷컴...' 썸네일 생성 실패:
  cannot access local variable 'process_thumbnail' where it is not associated with a value
```
동일 에러가 **6개 기사 전부**에서 발생. 모든 썸네일 생성이 skip됨.

### 코드 위치
**`scripts/blog_draft_generator.py`**, `main()` 함수:

#### 문제 코드 (라인 627 — Phase 28-02에서 추가)
```python
# inside main() function, duplicate retry section (line 626-627):
try:
    from auto_thumbnail import process_thumbnail, DEEPSEEK_POOL   # ← BUG: local import
    import random
    ...
```

#### 영향을 받은 코드 (라인 580 — Phase 28 이전 코드)
```python
# inside main() function, thumbnail generation section:
thumb_rel = process_thumbnail(         # ← UnboundLocalError 발생 위치
    link, slug,
    title=title,
    description=art.get("description", "")
)
```

### 메커니즘
Python **scoping rule**:
1. `main()` 함수 내에 `from auto_thumbnail import process_thumbnail` (라인 627)가 있음
2. Python은 이 할당(import)을 보고 `process_thumbnail`를 **local 변수**로 간주
3. 라인 580에서 `process_thumbnail()` 호출 시, Python은 **local 변수**를 찾음
4. 그러나 라인 627은 **아직 실행되지 않음** (duplicate retry section, 조건부)
5. → **`UnboundLocalError`**: local 변수가 아직 할당되지 않음

이는 Python의 `from X import Y`가 함수 내부에 있을 때 global 변수를 shadow하는 고전적인 함정.

### 영향 범위
| 항목 | 상태 |
|------|------|
| 6개 포스트 썸네일 | ❌ 전부 생성 안 됨 |
| 품질 체크리스트 | ⚠️ "파일 없음" 6건 — **로그만 남기고 계속 진행** |
| 중복 검증 | ✅ (0/0 = 통과 — 검증할 파일이 없었음) |
| 배포 | ✅ **썸네일 없이 배포됨** (차단 로직 없음) |
| 사이트 | ✅ HTTP 200 — 포스트는 라이브, 썸네일만 없음 |

### Phase 28 코드 검증 결과
Phase 28에서 추가된 모든 기능은 **코드 자체는 올바르게 구현**되었으나, import scoping 버그로 인해 **단 한 줄도 실행되지 않음**:

| Plan | 구현 상태 | 실행 여부 |
|------|----------|----------|
| 28-01: DeepSeek fallback + pagination | ✅ `auto_thumbnail.py`에 정상 구현 | ❌ 미실행 (process_thumbnail 호출 실패) |
| 28-02: 중복 검증 게이트 | ✅ `blog_draft_generator.py`에 정상 구현 | ❌ 미실행 (thumb_paths = [] → 0/0) |
| 28-03: 품질 검증 | ✅ `validate_thumbnail_quality()` 정상 구현 | ❌ 미실행 (thumbnails 없음) |
| 28-04: 모니터링/알림 | ❌ 폐기됨 | ❌ |

### 유사 위험: 동일 패턴
`main()` 함수 내 다른 곳에도 유사한 import 패턴 확인 필요:
- `import validate_blog_posts as vbp` (라인 698) — 함수 내 import
- `import subprocess` (라인 734, 754) — 함수 내 import
- `import random` (라인 628) — 함수 내 import

다행히 이들은 `from X import Y` 패턴이 아니거나, 사용 전에 import가 실행됨.

## Timeline
| 시간 | 이벤트 |
|------|--------|
| 2026-07-26 01:21 | Placeholder 재생성 완료 (45.6KB, quality=98) |
| 2026-07-26 01:19 | `blog_draft_generator.py` 최종 수정 (Phase 28 Fix) |
| 2026-07-26 08:15 | 오전 실행: 모든 기사 "이미 연결됨" 스킵 (오전 브리핑 미발행) |
| 2026-07-26 22:15 | **저녁 실행: 6개 신규 생성 → 썸네일 전부 실패** |
| 2026-07-26 22:18 | 썸네일 없는 6개 포스트 배포 완료 |

## 참조
- `scripts/blog_draft_generator.py` 라인 627 (버그 원인)
- `scripts/blog_draft_generator.py` 라인 45 (module-level import — 정상)
- `scripts/blog_draft.log` 라인 619-650 (6회 동일 에러)
- `scripts/blog_draft.log` 라인 667-674 (품질 체크리스트: 6건 파일 없음)
- Phase 28 docs: `.planning/phases/28-thumbnail-deepseek-fix/`
