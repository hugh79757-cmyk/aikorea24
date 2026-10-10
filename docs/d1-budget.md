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
| `get_daily_rows_read(day=None, force=False)` | 당일(UTC) 계정 rowsRead. **5분 캐시** — 매 `sql()` 마다 GraphQL 을 때리지 않는다 |
| `check_quota(threshold=0.8)` | 80% 초과 → `QuotaExceededError` 발생 / 95% 초과 → `{"readonly": True}` 반환 / 미만 → `{"readonly": False}` |
| `QuotaExceededError` | `sql()` 이 던지는 예외 |

로그 형식: `[D1-GUARD] 일일 읽기 {used:,}/{limit:,} ({pct:.1%}) — 작업 중단`

긴급 우회: `D1_GUARD=off` 환경변수를 설정하면 가드가 전체를 건너뛴다(복구 후 반드시 해제).

### 왜 조용히 실패했나
2026-10-10 저녁 `/news/` 와 `/briefing/<날짜>/` 가 깨졌다. 원인 = D1 이 `code 7500 exceeded daily row read limit` 을 반환하는데, 페이지 코드가 그 에러 dict 를 "결과 없음"으로 처리해 **빈 화면을 정상처럼 렌더**했다. 가드는 이 상황을 조용한 실패가 아니라 즉시 중단으로 바꾼다.

## 5. 모니터링

launchd 잡 `kr.aikorea24.d1-usage-report` — 매일 **08:30 KST**.

- `scripts/d1_usage_report.py` 가 직전 UTC 일의 rowsRead 를 조회
- 80% 초과 시에만 Telegram(`pipeline.infra.telegram.send_telegram`) 으로 대표님 보고
- 80% 미만이면 조용히 종료(EXIT 0)
- 로그: `scripts/d1_usage_report.log`

리셋이 KST 09:00 이라 08:30 은 "아직 초기화 전 마지막 버킷" = 어제 하루치를 정확히 본다.

## 6. 초과 시 대응

1. `D1_GUARD=off` 으로 강제 진행이 필요하면 임시 사용 후 해제
2. 원인 쿼리 특정 → `docs/state.md` 에 기록
3. 자정 UTC(KST 09:00) 지나면 자동 복구. 다음 날 같은 패턴이면 플랜 업그레이드 검토