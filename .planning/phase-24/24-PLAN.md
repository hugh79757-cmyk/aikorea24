# Phase 24: Threads Pipeline Batch 최적화

## GOAL
33개 기사 배치 → 5개 이하로 축소하여 LLM context 과부하 방지. JSON parsing 실패 및 crash 최소화.

## WHY NEEDED
- **현재 문제**: `get_pitches(batch_size=200)` → 33개 기사 한 번에 LLM에 전달
- **원인**: LLM context window 초과 → JSON schema 위반 → `article_ids: int` 타입 에러
- **결과**: TypeError crash 발생 (05:59 로그 확인)

## SCOPE
- `pipeline/threads/pitch.py` - `get_pitches()` 함수
- `pipeline/threads/writer.py` - 기사 후보 처리 로직

## SUCCESS CRITERIA
1. `batch_size` 기본값 200 → 5로 축소
2. 33개 기사 한 번에 처리 → 5개씩 7배치 또는 1개씩 순차
3. dry-run 테스트 통과: "배치 1/7 5개" 또는 "1개씩 33회"
4. crash 없음: `article_ids` 타입 에러 0건

## PLANS

### Plan 24-01: 배치 크기 축소
**File**: `pipeline/threads/pitch.py:500`
- `batch_size=200` → `batch_size=5` 변경
- 기존 API signature 유지 (`max_articles`, `batch_size` parameter)

### Plan 24-02: 순차 후보 선별 로직 추가 (옵션)
**File**: `pipeline/threads/pitch.py:570-580`
- 5개 배치 내에서 `filter_pitches()` 적용 후 즉시 반환하도록 옵션화
- "첫 번째 통과 피치만 사용" 로직 추가

### Plan 24-03: 테스트 및 검증
- `python3 scripts/threads/main_v3.py --dry-run` 실행
- 로그 확인: "배치 1/N 5개" 또는 유사 형태
- `article_ids` int 타입 에러 재발 방지 확인

## ROLLBACK
- `.bak` 파일 생성 후 변경
- 문제 시 `git checkout -- pipeline/threads/pitch.py`