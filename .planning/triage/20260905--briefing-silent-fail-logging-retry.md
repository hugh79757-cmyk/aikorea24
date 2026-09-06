---
date: 2026-09-05
type: fix
status: resolved
---

# 아침 브리핑 0건 침묵 실패 — d1_client 로깅 + 이메일 게이트 + 1시간 재시도 플로우

## What
2026-09-05 아침 `📭 블로그 초안 생성 스킵: 브리핑 없음`. 06:00 파이프라인이 `D1 조회: 0건`으로 브리핑 건너뜀 → 06:15 초안 스킵. d1_query 실패가 빈 리스트로 위장해 원인 불명 상태였음.

## Why
- `pipeline/infra/d1_client.py` d1_query()가 실패 시 빈 리스트 반환, 에러 로그 없음 → '뉴스 없음'으로 위장 (침묵 실패)
- `run_pipeline_with_notify.py`가 rc=0이면 무조건 "완료" 보고 — 브리핑 없어도 성공으로 발송
- 실패 시 자동 재시도 부재 — 브리핑 놓치면 그날 아침 발행 전부 유실

## Files changed
- `pipeline/infra/d1_client.py` — 스크러빙 로거 추가, 실패/타임아웃/재시도 소진/파싱 실패 로그
- `scripts/run_pipeline.py` — Step 4 이메일 게이트 (뉴스 0건 + 자동모드 → 발송 스킵)
- `scripts/run_pipeline_with_notify.py` — 전면 재구성 (252행): 문제 감지 detect_problem, 1시간 후 재시도 schedule_retry/--retry, 재시도 성공 시 블로그 초안 보충, lock/무한재시도 방지

## How
- d1_client: `get_scrubbed_logger` 재사용, f-string 사용 (%-포맷+args가 ScrubLogFilter 결합 시 Logging error 유발 — person_gate 버그 전례 회피)
- 이메일 게이트: `--skip-news` 수동 모드는 기존대로 발송 (기능 보존), 2차 방어 auto_email_sender 브리핑 부재 return 기존 존재
- 재시도: `subprocess.Popen(자기 자신 --retry, start_new_session=True)` → 1시간 sleep → 재실행. FAILURE_MARKERS=['D1 조회: 0건', '브리핑 생성 실패'], dedup 스킵은 재시도 안 함. TMPDIR lock(4h stale) + reason 파일

## Verification
- py_compile OK (전부)
- d1_client: 정상 쿼리 로그 0건+결과 반환, 고장 쿼리 → 재시도 2회 warning + 최종 실패 error + 빈 리스트. 계정 ID [REDACTED] 확인
- detect_problem/run_pipeline_result 5케이스 assert, lock/reason 왕복, wait_and_retry 통합 시나리오 3개 (RETRY_DELAY=0 모킹)
- [부분검증] telegram mock 기반 — 실 launchd 1시간 재시도는 다음 실패 발생 시 실전 첫 검증
- 로깅 실전 효과: 저녁 수동 실행에서 즉시 `LIKE or GLOB pattern too complex [code: 7500]` 포착 — 아침 0건 원인 후보 부각 (단, get_recent_news엔 LIKE 없음 — 원인은 d1_query 침묵 실패 가설, 내일 06:00 로그로 확정 예정)
