# 38-02-SUMMARY — Collector + Analyzer: insights 수집·집계·launchd

**Status:** ✅ Complete
**Completed:** 2026-09-02

## What was done

- `performance_log.py` 내 구현 (동일 파일):
  - `collect_insights(days=2)`: metrics==None + posted_at days일 내 필터 → `GET /v1.0/{root_id}/insights?metric=views,likes,replies,reposts,quotes` (urllib, publisher.load_env 토큰, timeout 30, 1회 재시도) → `metrics` 갱신. HTTP 에러 시 `metrics={'error': ...}` 기록 후 계속
  - **net_replies 보정 모델 정정 (라이브 검증으로 발견)**: insights의 `replies`(thread_replies)는 스레드 전체 답글 = 자기 카드 체인(카드2~5) + 🔗 링크 답글 포함. 18:00 포스트 replies=5 중 외부 0. 따라서 차감 모델 폐기 → `_external_reply_count()`: root 직접 답글 중 `username != aikorea24`만 직접 카운트. replies edge 실패(-1) 시 fallback `replies - 1`
  - `analyze(window_days=30, min_posts=30)`: metrics 완비 포스트 ≥30건 시만 `insights_report.json` 생성 (by_format/by_topic/by_slot + by_source fallback + top_topics 3). 미만 시 `분석 스킵` 로그, 파일 생성 없음
- `insights_collector.py` wrapper: collect → analyze 순, 각 단계 try/except (익일 재시도), 종료코드 항상 0
- launchd `~/Library/LaunchAgents/kr.aikorea24.threads-insights.plist` 등록 완료 — 일 06:10 (threads-publisher 06:00과 분리), `launchctl list` 확인: `kr.aikorea24.threads-insights` exit 0 대기 중

## Verification

- [검증됨] test 5/5 — net_replies 산출 (외부 직접 카운트), error 기록 후 계속, analyze 문턱 29건→없음/30건→생성, by_topic 집계. 근거: m0348 pytest 출력.
- [검증됨] 라이브 수집: 2026-09-01 발행 3건 (18:00/20:00/22:04) views 311/194/77 — 09-01 프로브 실측(311/194)과 일치. net_replies 0/0/0 — replies edge 실조회로 전부 자기 체인 답글 확인. 근거: m0343-0348 라이브 출력.
- [검증됨] 회귀 기준선: 전체 스위트 stash 전/후 동일 16 failed/473 passed — 회귀 0. 근거: m0360-0364.
- [부분검증] launchd 첫 자동 실행 — 06:10 다음 기동까지 미관찰. 수동 실행(insights_collector.py)으로 로직 자체는 검증 완료. 복구 계획: 09-03 06:10 후 insights_collector.log 확인.
