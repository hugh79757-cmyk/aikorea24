---
date: 2026-08-18
type: fix
status: resolved
---

# Threads API 토큰 갱신 분기 로직 추가 + 스킬 문서 작성

## What
- `token_refresh.py`에 `run_refresh_classified()`, `renew_token()`, `cmd_renew()` 추가
- `run_daily()`를 `renew_token()` 호출하도록 리팩터링
- 갱신 URL에 `/v1.0/` 경로 추가 (`graph.threads.net/v1.0/refresh_access_token`)
- `threads-token-troubleshooting` 스킬 문서 신규 작성

## Why
- 장기 토큰으로 `th_exchange_token` 교환 시 code=100 (Invalid parameter) 반복 실패
- 근본 원인: 이미 장기 토큰인데 exchange를 시도하면 Meta가 거부
- 해결: 단기→exchange / 장기→refresh 자동 분기 필요
- 갱신 URL도 탐색기(Graph API Explorer)와 동일하게 `/v1.0/` 포함 필요 확인

## Files changed
- `scripts/threads/token_refresh.py` — `run_refresh_classified()`, `renew_token()`, `cmd_renew()` 추가, `run_daily()` 리팩터링, refresh URL `/v1.0/` 추가, `REFRESH_SUCCESS` 상수 추가
- `scripts/threads/test_token_pipeline.py` — `test_daily_records_validation_and_expiry_unknown_when_no_op` mock 갱신 (6개 GET 응답)
- `/Users/twinssn/.config/opencode/skills/threads-token-troubleshooting/SKILL.md` — 신규 작성 (230줄)

## How
1. `renew_token()`: `expiry_known` 또는 `last_successful_token_operation` ∈ {exchange, refresh} → known_long → `th_refresh_token` 직접
2. 종류 미상 → `th_exchange_token` 시도 → code=100/unknown → `th_refresh_token` 폴백
3. `run_daily()`: 만료 임박 시 `renew_token()` 호출 (분기 처리)
4. 27개 테스트 전부 통과
5. 실증: `renew` CLI → 갱신 성공 (만료 59일), 게시 테스트 → 루트 게시 1건 발행 성공

## Verification
- `python3 scripts/threads/test_token_pipeline.py` → 27/27 통과
- `python3 scripts/threads/token_refresh.py renew` → 갱신 성공, expires_at=2026-10-17
- `publish_thread_chain` → root_post_id=18107876516603566 발행 성공
