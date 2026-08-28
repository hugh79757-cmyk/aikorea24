---
date: 2026-08-27
type: fix
status: resolved
---

# LLM fallback chain timeout + topic_finder + pipeline alert fix

## What
- `model_router.py` 타임아웃 180s→90s, global budget 300s, per-tier cooldown, persistent rotation 적용 (06:15 hang 해소)
- `thread_topic_finder.py` gpt-4o-mini 직호출 → `chat_completion` 폴백 체인 전환 + ```json 펜스 파싱 fix
- `run_pipeline.py` 항상 exit 0 → `sys.exit(1)` 추가로 실패 시 텔레그램 도달 보장
- `pitch.py` article_ids int/str normalize로 TypeError 방지

## Why
- 06:15 blog-draft hang: 6 tier × 3시도 × 180s = 최악 57분/call, 기사당 2회 호출로 수시간 대기, launchd Timeout 없음
- topic_finder 08-11부터 매일 429 `credit_balance_exhausted` (gpt-4o-mini)로 exit 1, 최근 팁: gemini 응답 펜스 감싸기로 JSON 파싱 실패 추가
- pipeline 배포 실패가 `except` 삼킴 + exit 0 → `run_pipeline_with_notify` 성공 알림만 발송, `PublishMonitor` 미배선

## Files changed
- scripts/threads/v3/model_router.py
- scripts/thread_topics/thread_topic_finder.py
- scripts/run_pipeline.py
- pipeline/threads/pitch.py

## How
- TIER_TIMEOUT 90.0/CONNECT 10.0/GLOBAL_BUDGET 300.0, _FallbackState file atomic (tmp+os.replace) quota 300s/struct 86400s, order() last_success 승격 + earliest-expiry fallback, _classify_error로 timeout/429/401 0재시도, 5xx만 5s 1회, 서킷브레이커 제거
- cluster_articles: `chat_completion(messages, system_prompt, response_format, max_tokens=4000)` + None 시 [] 반환 + fences strip via regex
- run_pipeline: `summary["errors"]` 있으면 `sys.exit(1)` (sys 이미 import)
- pitch get_pitches: `int|str → [x]`, non-list → `list()` guard

## Verification
- `py_compile` 4파일 통과, `_FallbackState` deterministic 5종 (promote/quota isolation/all-cooling/persistence/structural) PASS, classify PASS
- `chat_completion ping` → gemini-3.5-flash-lite 1.1s 성공, STATE_PATH `/tmp/aikorea24_llm_fallback_state.json`에 last_success/quota 영속 확인
- `blog_draft_generator --dry-run` EXIT 0, 6건 스킵, 검증 통과
- `thread_topic_finder.py` full run: D1 184건 → 5클러스터 아웃라인 1859/2334/3123/2525/1838자 생성, STEP6 텔레그램 완료
- `send_telegram` dry-run True + failure alert True, pytest 336 pass / 2 pre-existing fail 유지 (retention/STAR hook)
