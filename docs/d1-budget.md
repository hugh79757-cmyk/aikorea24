# D1 일일 읽기 행 예산 (AIK24-D1-GUARD-01)

> 계정: `7eb1b8cd178de269758ec94b2e03330b` (stylefactory9ai@gmail.com)
> D1: `aikorea24-db` `3f4cedde-…` · `aikorea24-emdash-db` `bbbcbc34-…`
> **한도 = 계정 단위 5,000,000행/일** (무료 티어, 자정 UTC 초기화 = KST 09:00)
> 쓰기 한도 100,000행/일. 2026-10-10 실측 쓰기 93,279행 → 여유 6,721행. **쓰기가 더 위험하다.**

## 1. 행 예산 배분

| 용도 | 일일 예산 | 비고 |
|---|---|---|
| 정기 파이프라인 (09:00) | 150만 행 | 뉴스 수집·브리핑 생성 |
| 수동 백필·조사 | 100만 행 | **10만 행 초과 시 대표님 사전 승인** |
| 예비 버퍼 | 250만 행 | 예기치 못한 작업용 |
| **합계** | **500만 행** | = 일일 한도 |

정기 파이프라인 예산 150만 행은 2026-10-10 실제 파이프라인 실행 3회(선정·브리핑·썸네일·이메일, 각 26~100초) 기준이다.

## 2. 검증 쿼리 규칙

- **`LIMIT` 필수** — 무한정 SELECT 금지
- **풀스캔 금지** — `WHERE` 절에 날짜 범위 강제 (`created_at >= ? AND created_at < ?`)
- 인덱스가 없는 컬럼에 `WHERE` 를 걸지 않는다. 인덱스는 `EXPLAIN QUERY PLAN` 으로 먼저 확인
- 카운트 목적이라도 `COUNT(*)` 대신 `LIMIT n` + 세기. 카운트도 행을 읽는다
- 예: `SELECT id FROM news WHERE created_at >= '2026-10-10' LIMIT 20`

## 3. 백필 승인과격

- 1회 백필이 **10만 행을 초과**하면 실행 전에 대표님 승인
- 승인 없이는 `scripts/news_backfill_v2.py` 의 `--limit` 을 10만 이하로 유지

## 4. 가드 (구현됨)

`scripts/cfnew.py` 에 다음이 들어 있다. `sql()` 이 시작점에서 자동으로 가드를 건다.

| 함수 | 동작 |
|---|---|
| `get_daily_rows_read(day=None, tok=None, force=False)` | 당일(UTC) 계정 rowsRead. **5분 캐시** — 매 `sql()` 마다 GraphQL 을 때리지 않는다 |
| `get_daily_rows_written(...)` | **2026-10-17 신설** — 당일 rowsWritten. 읽기와 같은 조회·캐시 공유(GraphQL 1회에 둘 다), 추가 비용 없음 |
| `check_quota(threshold=0.8)` | 80% 초과(읽기) → `QuotaExceededError` / 95% 초과 → `{"readonly": True}` / 미만 → `{"readonly": False}`. 기존 차단 동작 그대로 유지 |
| `maybe_alert_tiers(pct_read, pct_write, ...)` | **3단계 경보(50/70/90%)** — 읽기·쓰기 각각 독립 판정 → muse-cli 기본채팅 알림. UTC 일·지표·임계당 1회만 발송(dedup `.d1_tier_alert_state.json`). muse 실패 시 미기록 → 다음 주기 재시도 |
| `QuotaExceededError` | `sql()` 이 던지는 예외 |

경보 단계 의미: **50%**=관측 시작(ℹ️, 정상일 기준이 43~61%라 자주 뜰 수 있음) · **70%**=확인 필요(⚠️, 진입 가드 `D1_HEADROOM=70%`와 동기) · **90%**=즉시 조치(🚨, 읽기는 80% 차단·95% readonly 진행 보다 뒤).

로그 형식: `[D1-GUARD] 일일 읽기 {used:,}/{limit:,} ({pct:.1%}) — 작업 중단`

긴급 우회: `D1_GUARD=off` 환경변수를 설정하면 가드가 전체를 건너뛴다(복구 후 반드시 해제).

### 왜 조용히 실패했나
2026-10-10 저녁 `/news/` 와 `/briefing/<날짜>/` 가 깨졌다. 원인 = D1 이 `code 7500 exceeded daily row read limit` 을 반환하는데, 페이지 코드가 그 에러 dict 를 "결과 없음"으로 처리해 **빈 화면을 정상처럼 렌더**했다. 가드는 이 상황을 조용한 실패가 아니라 즉시 중단으로 바꾼다.

## 5. 모니터링

launchd 잡 `kr.aikorea24.d1-usage-report` — **StartInterval 1800 = 30분 주기** (하루 48회).

- `scripts/d1_usage_report.py` 가 당일 UTC 일의 rowsRead + rowsWritten 를 조회 (계정 합산 — a24+emdash 합)
- cfnew 의 5분 캐시 덕에 GraphQL 조회는 하루 수회만 발화
- **3단계(50/70/90%)** 돌파 시 **muse-cli 기본채팅** 알림 (2026-10-17 대표님 지시 — 발송 주체 `cfnew.maybe_alert_tiers`): 임계당 하루 1회. 50%는 정상일 기준 확인용이므로 자주 뜰 수 있음(정상이 아님·기준선 43~61%).
- 읽기 80% 초과 시 기존 경로인 Telegram 도 병행 (하루 1회 마커 유지)
- 50%+ 70% 이하면 조용히 종료(EXIT 0) — 로그만 남긴다
- 로그: `scripts/d1_usage_report.log`
- 시각 표기: 2026-10-17 부터 KST (+09) — 이전 doc 표기 "방콕(+07)"은 TZ 고정으로 해소됨
- plist 수정 불필요 — launchd 가 같은 `scripts/d1_usage_report.py` 를 주기적으로 재실행하므로 코드만 바뀌면 즉시 적용된다

**계정 스코프 메모 (2026-10-17 실측):** 본 예산은 운영 계정(stylefactory9ai, `7eb1b8cd…`) 기준이다.
구계정(hugh79757, `fac9808c…`)의 옛 aikorea24-db(`bec650ce…`)는 하루 읽기 133~244행(휴면)으로
본 예산과 무관하다. 옛 계정의 핫 DB는 타 프로젝트 소속이다 — obsidian-db 약 45만/일,
certkorea-db 약 25만/일, blogdex_db 약 10만/일(+쓰기 2.8만). 단, 옛 Pages 프로젝트
"aikorea24" 의 deployment_configs 에 옛 D1 바인딩(`DB` → bec650ce)은 2026-10-17
PATCH(deployment_configs 전체 갱신 + DB:null 방식)로 제거했다 — 사후 GET `production.d1_databases: null` 확인.
롤백 DDL: 동일 PATCH로 `DB: {"id":"bec650ce-f732-46bc-87c0-bd76ed17e42a"}` 재설정.

## 6. Cloudflare 무료티어 사전경고 구조 (2026-10-17 감사, 상세 = docs/quota-warnings-audit.md)

- **사전(限 前) 경고는 CF 어느 항목에도 없음** — D1만 도달 시점에 이메일 + `code 7500` (2026-09-01 시행). Workers 요청(Error 1027)·KV·R2는 침묵-오류.
- 리셋 00:00 UTC = **KST 09:00** — 야간 파이프라인이 윈도우를 소진하면 아침 9시까지 정지.
- 최근 9일 초과 3건 실측: 10-09 쓰기 183% (백필) · 10-10 읽기 109% (7500 사건) · 10-14 읽기 106%.
- 본 가드(80%)가 유일한 사전 경고 계층. **갭 2건**: 쓰기 임계 미검사(읽기만), Workers 요청/기타 항목 무관측(여유 87%p라 리스크 낮음).

## 7. 초과 시 대응

1. `D1_GUARD=off` 으로 강제 진행이 필요하면 임시 사용 후 해제
2. 원인 쿼리 특정 → `docs/state.md` 에 기록
3. 자정 UTC(KST 09:00) 지나면 자동 복구. 다음 날 같은 패턴이면 플랜 업그레이드 검토