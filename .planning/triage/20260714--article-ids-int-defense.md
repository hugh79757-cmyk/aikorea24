---
date: 2026-07-14
type: debug
status: resolved
---

# article_ids int 타입 방어 누락 수정 (TypeError crash)

## What
- `is_duplicate_pitch()`에서 `for x in pitch.get('article_ids', [])` 실행 시 LLM이 `article_ids`를 `int`로 반환 → `TypeError: 'int' object is not iterable`
- `main_v3.py` 4개 접근 경로에서도 동일한 방어 누락

## Why
- Phase 24-01에서 pitch.py의 get_pitches()와 writer.py에만 방어 추가
- `is_duplicate_pitch()`는 get_pitches() 처리 전에 호출되므로 방어가 적용되지 않은 상태에서 crash
- main_v3.py도 직접 article_ids를 읽는 4개 경로에서 방어 누락

## Files changed
- `pipeline/threads/pitch.py` — is_duplicate_pitch()에 raw_ids 정규화 추가
- `scripts/threads/main_v3.py` — _normalize_article_ids() 헬퍼 도입, 4개 접근 경로 방어

## How
- isinstance(article_ids, int) 체크 후 list로 변환하는 패턴을 모든 접근 경로에 추가
- _normalize_article_ids(), _get_first_article_id() 헬퍼 함수로 중복 방어 코드 제거

## Verification
- python3 -m py_compile 통과
- tests/test_pitch.py 38/38 통과
- git push 완료 (62fbe3d)
