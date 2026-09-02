# Phase 38 Context — Threads 자가개선 (Self-Improvement) 루프

## Goal
Threads 발행 파이프라인이 자신의 발행 성과(views/likes/replies)를 **직접 측정**하고, 최근 30일 집계로 피치 생성 프롬프트에 피드백 주입하는 폐쇄 루프 구축. 목표: 발행 12회/일 × 30일 데이터 기반으로 평균 views 상향.

## Background
- 발행 파이프라인: `scripts/threads/main_v3.py` (launchd 2h 간격, 12슬롯/일). 발행 성공 시 `publish_thread_chain()`이 root_post_id 반환 (main_v3.py line 427-429). 포맷 라벨 `_fmt` (D/contrast) 로그에 존재.
- 중복 방지 자산: posted.json (posted_ids 965, pitch_history 154), Vectorize, 3단계 semantic dedup.
- **이전 분석 정정 완료**: "Threads API 조회수 미제공" → 틀림. 라이브 프로브(2026-09-01 22:5x KST, 실제 발행 포스트 2건)로 `insights` 엣지가 views 제공 확인. 18:00 root 18122058901870182: views 311/likes 2/replies 5. 20:00 root 18426508516181136: views 194/likes 1.
- 기존 유사 시도 없음: 성과 측정 코드 0건 (api_based_published.json은 매체 품질 모니터링용, 성과 아님).

## Scope
- 대상: `scripts/threads/` (main_v3.py, 신규 performance_log.py, insights_collector.py), `pipeline/threads/pitch.py` (프롬프트 주입), 신규 launchd plist 1개
- 비대상: publisher.py 발행 로직 변경 없음, 포맷 구조 변경 없음, blog 파이프라인 무관, 통계 모델/유의성 검정 제외 (YAGNI — 30일 데이터 쌓인 후 재평가)

## Constraints
- 기존 발행 흐름 append-only: 22:00 슬롯 등 예정 발행 회귀 0 (break nothing)
- 토큰 로딩: `publisher.load_env()` (EnvConfig) 경로만 — .env 수동 파싱은 quote 이슈로 code 190 재발 (라이브 프로브 검증)
- threads-publisher.plist 재사용 패턴: launchd 등록은 execute 단계에서, plist template 경로 `~/Library/LaunchAgents/kr.aikorea24.threads-publisher.plist`
- stdlib only (urllib), 신규 의존성 0
- 30 posts 미만 데이터 → 분석/주입 스킵 (부트스트랩 보호, graceful degradation)

## Decisions Already Made (라이브 프로브로 고정)
- 성과 지표: `GET /v1.0/{media_id}/insights?metric=views,likes,replies,reposts,quotes` — 5지표 전부 HTTP 200 확인
- `likes`는 media fields 아님 (code 100) → insights metric 전용
- `replies` metric에 자기 링크 답글 포함 → `net_replies` 보정 (replies edge에서 username==aikorea24 제외 카운트, 실패 시 replies-1)
- insights 수집 주기: 일 1회 06:00, 어제+그제 발행 건 (48h window — 반응 안정화 대기)
- 측정-기록: 발행 성공 직후 (API 추가 호출 0건), 측정-수집: 별도 launchd 일 1회
- 피드백: pitch.py 프롬프트에 최근 30일 상위 토픽 3개 주입 ("참고용, 강제 아님" — 주제 다양성 보호)

## Open Questions for Research
(없음 — 라이브 프로브 완료, quick PLAN.md 계획검증 10/10 PASS. execute 준비 완료)
