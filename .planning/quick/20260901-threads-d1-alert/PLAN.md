---
slug: threads-d1-alert
date: 2026-09-01
status: completed
---

# Threads 파이프라인 — D1 장애 시 텔레그램 알림 누락 수정

## 문제
- 2026-09-01 12:00~16:00 Cloudflare D1 `aikorea24-db` 쿼리 엔드포인트가 HTTP 500 `internal error [code: 7500]` (Cloudflare 측 장애) → `get_articles()`가 `[]` 반환
- main_v3.py run_v3()의 기사 로드 재시도(5회) 소진 시 **조용히 return** — 2시간마다 알림 없이 스킵 → 사용자가 수 시간 뒤에야 인지
- 기존 텔레그램 알림(line 493-494)은 발행 실패 경로에만 존재, 빈 기사 경로에는 없음

## 근본 원인 (root cause)
main_v3.py line 159: 빈 기사 재시도 소진 경로에서 `return`만 수행, `send_telegram` 없음

## 작업
1. [root] main_v3.py 기사 없음 재시도 소진 시 `send_telegram` 추가 (기존 발행 실패 알림 포맷과 동일) — 커밋 84850ac

## 검증
- `.venv/bin/python3 -m py_compile scripts/threads/main_v3.py` 통과
- D1 장애 재확인 (16:03, 여전히 7500) — 18:00 실행부터 새 알림 경로 가동
