---
date: 2026-07-15
type: feat
status: resolved
---

# Telegram Two-Stage Notify

## What
브리핑 발행과 블로그 발행을 구분하는 2단계 텔레그램 알림 구조화.

## Why
- 기존: "심층글 0건/썸네일 0건" 이라는 어색한 메시지
- 요구: 브리핑 완료 → 15분 후 블로그 완료 (2개의 별도 메시지)

## Files changed
- `scripts/run_pipeline_with_notify.py` — "브리핑 발행 완료" + "블로그는 15분 후" 안내
- `scripts/blog_draft_generator.py` — "블로그 발행 완료" + "딥링크 연결 완료" 명시

## How
1. `run_pipeline_with_notify.py`: 성공 시 "News selection + Briefing published" 강조
2. `blog_draft_generator.py`: 생성/스킵/없음 3가지 케이스 모두 "발행 완료/없음"으로 명확화
3. 딥링크 연결 완료 메시지 추가

## Verification
- Python syntax 통과
- 커밋: `93f7b5c`