# Phase 38: threads-self-improvement — Research

**Researched:** 2026-09-01
**Domain:** Threads insights API 측정 + 성과 피드백 루프
**Confidence:** HIGH (API 라이브 프로브 완료 — 실제 발행 포스트 2건으로 200 확인, 추정 없음)

## User Constraints (from CONTEXT.md)

### Locked Decisions
- 성과 지표는 insights 엣지 5지표 (views,likes,replies,reposts,quotes) [VERIFIED: 라이브 프로브 2026-09-01]
- net_replies 보정: 자기 링크 답글 제외 [VERIFIED: 18:00 포스트 replies=5에 링크 답글 18109210742151438 포함 확인]
- 토큰은 publisher.load_env() (EnvConfig) 경로만 [VERIFIED: .env 수동 파싱 → code 190 "Cannot parse access token" 재현, EnvConfig → 200]
- append-only 수정 — 기존 발행 흐름 회귀 0 [VERIFIED: quick PLAN plan-checker 10/10]
- 30 posts 미만 → 주입 스킵 (부트스트랩 보호) [VERIFIED: PLAN.md 검증 계획]

### Agent's Discretion
- topic_tags 추출 시점 (발행 시 vs 분석 시) — 구현 단계 결정
- insights_report.json 스키마 상세 (평균 views 외 median/percentile 여부)
- launchd plist 상세 타이밍 (06:00 고정이지만 tools-collector 06:00과 충돌 시 1분 shift 여부)

### Deferred Ideas (OUT OF SCOPE)
- 통계 유의성 검정, 훅 문구 A/B, contrast 포맷 가중치, 시간대별 발행 슬롯 변경 — 30일 데이터 확보 후 별도 phase

## Findings

### A. Threads insights API (라이브 검증 — 핵심)
- 엔드포인트: `GET https://graph.threads.net/v1.0/{media_id}/insights?metric=views,likes,replies,reposts,quotes&access_token={token}`
- 실측 (2026-09-01 발행건, 22:5x KST 조회):
  - root 18122058901870182 (18:00): views **311**, likes 2, replies 5, reposts/quotes 0
  - root 18426508516181136 (20:00): views **194**, likes 1
- 응답 구조: `data[].values[0].value` (period: lifetime). 내부 이름 `thread_replies` → 반환 name "replies" 주의.
- 함정 3개 (전부 라이브 재현):
  1. media fields에 `likes` 넣으면 code 100 "Tried accessing nonexisting field (likes)" → insights 전용
  2. `metric` 파라미터 미지정 시 code 100 "The parameter metric is required"
  3. `.env` 수동 파싱 토큰 → code 190 (quote 처리 차이). EnvConfig만 사용
- 자기 답글: replies 5 = 실제 외부 4 + 우리 링크 답글 1. `GET /{media_id}/replies?fields=id,text` 로 식별 가능, username 필드 존재
- views metric에 "in development" 라벨 → Meta 지표 변경 가능성 → 수집 실패 시 error 기록 후 계속 (발행 중단 없음)

### B. 발행 시점 확보 가능한 메타 (코드 확인)
- `publish_thread_chain(cards, article, link_url)` → root_post_id 반환 (publisher.py line 285)
- main_v3.py 발행 성공 블록: line 427-429 `result = publish_thread_chain(...)` / `✅ 발행 완료: 루트 ID {result}` — record_publish 삽입점
- 가용 메타: `_fmt`(포맷), `pitch_id`(기사 ID), `publish_article`(title/source), `datetime.now()`
- 유사 패턴 선례: `_log_api_based_publish()` (main_v3.py line 56-79) — 별도 JSON append 로직 이미 존재 → 복제 패턴

### C. 기존 데이터 자산
- posted.json: `history` 배열 (id/link/title/posted_at) — 성과 미포함, 병합 불필요 (성과는 별도 파일)
- pitch_history 154건 (hook/but_line/question/article_ids/date) — 토픽 분석 보조 소스 가능
- 발행량: 성공 6건/일 (09-01 실측, D1 장애 3슬롯 제외 시 최대 12) → 30일 ~180-360 포인트

### D. API 호출량 산출
- 측정-수집: 일 12건 × 1 insights call = 12 calls/일 (Threads API 한도 여유)
- net_replies 보정: replies 응답 필요한 포스트만 1 call 추가 (링크 답글 단 건) → 최대 +12/일

### E. 위험
| 위험 | 영향 | 완화 |
|------|------|------|
| views "in development" 변경 | 지표 단절 | error 필드 기록 + 계속, 스키마 버전 필드 |
| 토큰 만료 (2026-10-17) | 수집 중단 | token-refresh launchd 일 00:30 갱신 (잠재 갭 잔존 — 별도 이슈) |
| launchd 06:00 tools-collector와 동시 | CPU/네트워크 경합 | 12 calls 경량, 무시 가능 (1분 shift 옵션) |

## Sources
- 라이브 프로브: 실제 발행 root 2건 insights/replies/media fields (2026-09-01 22:5x KST)
- 코드: scripts/threads/main_v3.py, publisher.py, pipeline/threads/pitch.py, .planning/quick/20260901-threads-self-improvement/PLAN.md
