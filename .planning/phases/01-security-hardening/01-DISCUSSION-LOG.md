# Phase 1: Security Hardening — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-30
**Phase:** 1-Security Hardening
**Areas discussed:** Git history remediation, Env source priority, Log scrubbing scope, Telegram alert coverage

---

## Git History Remediation

| Option | Description | Selected |
|--------|-------------|----------|
| 키 교체 (Recommended) | 모든 API 키를 새로 발급. git history는 그대로 둠 | |
| BFG + 키 교체 | git history에서 키 제거(BFG) + 키 교체 | ✓ |
| 리스크 수용 | 이미 REDACTED, 개인 프로젝트이니 그냥 진행 | |

**User's choice:** BFG + 키 교체. But plist should fallback to `~/.env.common` instead.
**Notes:** User wants plist to delegate to `~/.env.common`. Future: manage all secrets from one place.

### Follow-up: Plist fix

| Option | Description | Selected |
|--------|-------------|----------|
| 네 (Recommended) | plist는 경로만, 시크릿은 ~/.env.common에서 로드 | ✓ |
| 아니요 | 다른 방식 | |

**User's choice:** 네

### Follow-up: Centralize

| Option | Description | Selected |
|--------|-------------|----------|
| ~/.env.common 유지 | 공통 시크릿은 홈디렉토리, .env는 프로젝트 설정만 | ✓ |
| 프로젝트 .env로 통일 | 모든 시크릿을 .env 하나로 | |
| 아직 미정 | 나중에 결정 | |

**User's choice:** ~/.env.common 유지

### Follow-up: Git history

| Option | Description | Selected |
|--------|-------------|----------|
| 키 교체만 | API 키만 교체, history 그대로 | |
| BFG cleanup | BFG로 history에서 제거 | ✓ |
| 지금은 skip | plist 정리 후 나중에 | |

**User's choice:** BFG cleanup

---

## Env Source Priority

| Option | Description | Selected |
|--------|-------------|----------|
| ~/.env.common 우선 | 공통 시크릿이 최우선 | |
| 프로젝트 .env 우선 (Recommended) | .env가 최우선, ~/.env.common은 fallback | ✓ |
| 자세히 설명 | 다른 구조 | |

**User's choice:** 프로젝트 .env 우선

### Follow-up: Shadow config

| Option | Description | Selected |
|--------|-------------|----------|
| 제거 (Recommended) | 통합 env_loader로 대체, .env.sh 삭제 | ✓ |
| 유지 | 당분간 호환성 유지 | |

**User's choice:** 제거

### Follow-up: Deploy

| Option | Description | Selected |
|--------|-------------|----------|
| 제거 (Recommended) | deploy.sh가 프로젝트 .env만 읽도록 | |
| 유지 | Phase 3에서 처리 | |

**User's choice:** 독립. 둘이 공유할 게 없음. 완전히 분리.

### Confirmation

| Option | Description | Selected |
|--------|-------------|----------|
| 맞음 (Recommended) | .env → ~/.env.common 순서, plist는 경로만 | ✓ |
| 수정 필요 | 조금 다름 | |

**User's choice:** 맞음

---

## Log Scrubbing Scope

| Option | Description | Selected |
|--------|-------------|----------|
| API 키만 | env 시크릿만 | |
| 포괄적 (Recommended) | API 키 + 토큰 + 이메일 + PII | ✓ |
| 일단 API 키 + 트러블슈팅 | 키 redact + 필요시 추가 | |

**User's choice:** 포괄적

### Follow-up: Method

| Option | Description | Selected |
|--------|-------------|----------|
| Logger 레벨 (Recommended) | 로거가 자동 scrub | ✓ |
| Env loader 레벨 | 로드 시 마스킹 | |

**User's choice:** Logger 레벨

### Follow-up: Pattern

| Option | Description | Selected |
|--------|-------------|----------|
| 정적 패턴 목록 (Recommended) | ScrubRegistry에 등록된 키 이름 기반 | ✓ |
| 정규식 탐지 | 'sk-', 'ghp_' 패턴 자동 탐지 | |
| 둘 다 | 정적 패턴 + 정규식 | |

**User's choice:** 정적 패턴 목록

---

## Telegram Alert Coverage

| Option | Description | Selected |
|--------|-------------|----------|
| 런처 레벨 | launchd 실행을 notify wrapper로 감싸기 | |
| 파이프라인 레벨 | orchestrator에 알림 내장 | |
| 둘 다 | 이중 알림 | |

**User's choice:** 파이프라인이 작동안했을때. 정상발행이면 메시지 불필요. 발행실패 때만 어떤 발행이 실패했는지와 원인을 함께.

### Follow-up: Trigger

| Option | Description | Selected |
|--------|-------------|----------|
| 실패만 (Recommended) | 실패 또는 예정 시간 miss 시만 | ✓ |
| 성공 + 실패 | 항상 알림 | |
| 실패 + 주간 요약 | 실패 즉시 + 주 1회 통계 | |

**User's choice:** 실패만

### Follow-up: Missed detection

| Option | Description | Selected |
|--------|-------------|----------|
| Cron heartbeat (Recommended) | 30분마다 로그 타임스탬프 확인, 3h 이상 갱신 없으면 알림 | ✓ |
| 스케줄 추적 | D1에 예상 시간표 저장, miss 감지 | |
| 수동 확인 | 로그 보고 직접 확인 | |

**User's choice:** Cron heartbeat

### Confirmation

| Option | Description | Selected |
|--------|-------------|----------|
| 맞음 (Recommended) | 실패 시에만 실패한 step + 에러 원인 포함 | ✓ |
| 조금 다름 | 설명해주세요 | |

**User's choice:** 맞음

---

## Deferred Ideas

- Web dashboard — deferred to separate dashboard project
- Full env consolidation into project `.env` — user prefers `~/.env.common` pattern
- Git filter-branch — rejected in favor of BFG
- Heartbeat monitor implementation — to be designed in Phase 3
