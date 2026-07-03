# 크롤링 실패 시 RSS fallback 폐기 (crawl-fail-discard)

- **Type**: fix
- **Date**: 2026-07-03

## Problem
`get_pitches()`는 TOP 1 피치 선정 후 원문 크롤링을 시도하지만, 크롤링 실패 시에도 RSS description 기반 저품질 피치를 fallback으로 발행하고 있었다. 실제로 31개 pitch 중 크롤링이 수행된 건은 2건(6.4%)에 불과했으며, 나머지는 RSS 제목/설명만으로 생성된 질 낮은 글이었다.

## Solution
크롤링 실패 시 더 이상 fallback하지 않고 피치를 완전히 폐기한다:

- URL 부재: `return []`
- 크롤링 실패: `return []`  
- 재생성 실패: `return []`
- 크롤링 성공 시에만: `return [regenerated]`

## Files Changed
- `pipeline/threads/pitch.py` — 3개 지점의 `return [top]` → `return []`
- `tests/test_pitch.py` — `TestGetPitchesCrawlFail` 4개 테스트

## Impact
- Threads 발행 빈도 ↘ (크롤링 실패 시 skip)
- 발행글 품질 ↗ (크롤링 기반 피치만 발행)
- Tests: 196/197 통과
