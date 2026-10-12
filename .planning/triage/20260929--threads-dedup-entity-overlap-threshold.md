---
date: 2026-09-29
type: fix
status: resolved
---

# fix: semantic dedup EN-EN entity_overlap >=2 → >=4 (스레드 발행 실패)

## What
스레드 발행 5회 연속 실패 원인: `scripts/threads/dedup.py` EN-EN 분기 `entity_overlap >= 2`가 과도하게 민감해 AI 뉴스 기사 공통 고유명사 풀(OpenAI, Meta, Anthropic, AI)로 서로 다른 기사도 same-topic 오인 → 기사 풅 1142 → 2 폭락 → 크롤링 본문 부족 → 발행 차단. `>= 2` → `>= 4` 로 수정.

## Why
2026-09-29 18:00~18:05 v3 5회 재시도 모두 실패. `scripts/threads/logs/2026-09-29.log` 18:01~18:05 참조. 매 시도 기사 풅 2건 → 모두 본문 106자/441자 → 발행 0건. 5회 실패 후 "2시간 후 재시도"로 종료.

## Files changed
- `scripts/threads/dedup.py` (line 175 EN-EN `>= 4`; line 148 docstring 동기화)
- `tests/test_dedup_semantic.py` (신규 4건)
- `CHANGES.md`, `.planning/worklog/WL-20260929-dedup-entity-falsepositive.md`
- 커밋 `f719341e` (18:31), `bb447758` (doc sync)

## How
- `db_reader.get_articles()` 재실행으로 OLD(>=2)=2건/230제외 vs NEW(>=4)=164건/10제외 재현
- 60기사 × 1217 meta 재측정: eo==2 오인 422건, eo>=4로 1건 잔여

## Verification
- 풅 2 → 164 (P1=3, P2=161)
- test_dedup_semantic 4/4
- 회귀 59 passed / 2 failed (사전 존재 버그, pre-fix 로도 동일 실패)
- 주의: eo>=4에서 1쌍 잔여 오인 존재 (false-positive 0은 과장). eo==3 동일 스토리 미탐 가능 → Vectorize 레이어 의존.