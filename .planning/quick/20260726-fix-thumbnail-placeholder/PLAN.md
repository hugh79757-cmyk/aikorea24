# Quick Task: Fix Thumbnail Placeholder Not Applied

## Description
7/25 썸네일 5개(002~006)가 동일 MD5로 placeholder가 아닌 "abstract technology" 결과 사용 중. placeholder 복사 로직이 작동하지 않는 원인 파악 후 수정.

## Root Cause Analysis Needed
`auto_thumbnail.py`의 `_use_default_thumbnail()` 호출 경로 확인:
1. `process_thumbnail()`에서 모든 fallback 소진 시 `_use_default_thumbnail(slug)` 호출
2. 하지만 7/25 실행 로그상 placeholder 복사 로그 없음
3. 원인 후보:
   - `create_thumbnail()`이 예외 발생 전 반환 → placeholder 분기 미도달
   - `_use_default_thumbnail()`에서 `src.exists()` 실패 (파일 경로 불일치)
   - 품질 검증(`validate_thumbnail_quality`) 실패 후 재시도 로직에서 placeholder로 안 빠짐

## Files to Modify
- `scripts/auto_thumbnail.py` — placeholder 적용 로직 보강

## Acceptance Criteria
1. Pexels/DeepSeek 완전 실패 시 → `news-keyword-og.webp` placeholder 복사됨
2. 품질 검증 실패 2회 후 → placeholder 복사됨
3. 로그에 "기본 placeholder 사용" 명시 출력