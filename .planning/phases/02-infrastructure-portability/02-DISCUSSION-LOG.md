# Phase 2: Infrastructure & Portability - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-30
**Phase:** 02-Infrastructure & Portability
**Areas discussed:** config.py scope, d1_client.py API, Wiring order & safety, retry.py design, models.py scope, OBS-01 structured logging

---

## config.py — 경로 관리

| Option | Description | Selected |
|--------|-------------|----------|
| 함수만 (Recommended) | `project_root()` 하나. 29개 경로 중 단순 PROJECT_DIR 교체는 이걸로 충분. | ✓ |
| ProjectPaths 클래스 | `project_root()`, `logs_dir()`, `data_dir()`, `config_dir()` 등 메서드 제공 | |

**User's choice:** 함수만
**Notes:** 복잡도가 낮아지는 기준. 같은 기능이면 적은 코드로.

---

## d1_client.py — DB 래퍼

| Option | Description | Selected |
|--------|-------------|----------|
| 함수만 (Recommended) | `d1_query(sql, params=None, retries=2)` 함수 형태. wrangler CLI 호출. | ✓ |
| D1Client 클래스 | `D1Client(db_name)` 인스턴스 생성 후 `.query()` 호출 | |

**User's choice:** 함수만
**Notes:** 세 가지 기존 버전 통일이 목적. 클래스 불필요.

---

## Wiring — 연결 전략

| Option | Description | Selected |
|--------|-------------|----------|
| 일괄 wiring (Recommended) | 하나의 plan에서 모든 파일 교체. Strangler Fig 방식. | ✓ |
| 단계별 wiring | 파일당 하나씩 20개 plan으로 분할. | |

**User's choice:** 일괄 wiring
**Notes:** Strangler Fig 방식이라 기존 함수는 그대로 두고 새 import만 추가.

---

## retry.py — 재시도 로직

| Option | Description | Selected |
|--------|-------------|----------|
| 범용 decorator (Recommended) | `@retry(max_retries, delay, backoff)` 모든 함수에 동일 적용 | ✓ |
| 프로필별 preset | `@api_retry`, `@db_retry` 등 목적별 데코레이터 별도 정의 | |

**User's choice:** 범용 decorator
**Notes:** max_retries 파라미터로 API/DB 구분.

---

## models.py — 데이터 타입

| Option | Description | Selected |
|--------|-------------|----------|
| Article만 | NewsArticle dataclass 하나만 정의 | |
| 전체 타입 | NewsArticle, BriefingItem, ThreadsPost 등 전반 타입 | ✓ |

**User's choice:** 전체 타입
**Notes:** 파이프라인 전반 모든 데이터 타입.

---

## OBS-01 — 구조화 로깅

| Option | Description | Selected |
|--------|-------------|----------|
| 포함 (Recommended) | run_id, step_name, duration 로그 추가 | ✓ |
| 기존 logger로 충분 | Phase 1 logger에 타임스탬프만 있으면 충분 | |

**User's choice:** 포함
**Notes:** 파이프라인 실행 추적 가능하도록.

---

## the agent's Discretion

None — user made explicit choices on all discussed areas.

## Deferred Ideas

None — discussion stayed within phase scope.
