# Worklog: WL-20260929-dedup-entity-falsepositive

## Operation
semantic dedup EN-EN 분기 `entity_overlap >= 2` 오인 방지 (>= 4로 상향)

## Trigger
2026-09-29 18:00~18:05 스레드 발행 5회 연속 실패. 기사 풀 2건 → 크롤링 본문 부족 → 발행 0건.

## Root Cause
`scripts/threads/dedup.py:170` — AI 뉴스 기사 공통 고유명사 풀이 극소함(OpenAI, Meta, Anthropic, AI).
서로 다른 기사도 공통 entity 2개만으로 same-topic 으로 오인.
실측: EN-EN 쌍 38,941개 중 340개 오인 (99.4%가 entity_overlap==2, jaccard_en==0).
결과: 1,142개 기사 → 2개로 폭락.

## Change [PRODUCTION CODE]
- `scripts/threads/dedup.py:170` `>= 2` → `>= 4` (주석 추가)

## Test [TEST CODE]
- `tests/test_dedup_semantic.py` 신규 4건 (4/4 통과)

## Verification
- 기사 풀 2 → 164 (P1=3, P2=161)
- 크롤링 12/12 >=500자
- false-positive 0, true-positive lost 0

## Regression
- 59 passed. 2 failed는 사전 존재 버그 (git stash 후 동일 실패).