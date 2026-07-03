---
date: 2026-07-03
type: fix
status: resolved
---

# tools_collector: D1 tools 테이블 미갱신

## What
`tools_collector.py`가 `src/content/tools/*.md`만 생성하고 D1 `tools` 테이블을 갱신하지 않아, `auto_email_sender.py`의 `get_tools()`가 항상 2026-06-21 데이터(97개)만 반환. 이메일 발송 시 최신 AI 도구 누락.

## Why
`tools_collector.py` 파이프라인 설계 시 D1 동기화 단계 누락. 기존 `sync_tools_to_d1.mjs`는 수동 스크립트로만 존재.

## Files changed
- `scripts/tools_collector.py` — `sync_tools_to_d1()` 함수 신규 추가, `main()` deploy 후 자동 호출

## How
기존 `sync_tools_to_d1.mjs`(Node.js)를 subprocess로 실행 → SQL 생성 → `wrangler d1 execute --file`로 D1 업데이트. `wrangler`가 `BEGIN TRANSACTION`을 지원하지 않아 SQL에서 transaction wrapper 제거 후 execute.

## Verification
- D1 tools: 97 → 143 rows ✅
- last_update: 2026-06-21 → 2026-07-03 ✅
- 최신 툴 3개(Tempmail.bot, Spira AI, PDFtoword AI) 정상 반영 ✅
- Syntax check 통과 ✅
