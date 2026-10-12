---
date: 2026-09-29
type: fix
status: resolved
---

# Compass 튜플 반환 버그 + LLM 체인 순수 회전 정비

## What
compass 발행이 12회 연속 실패한 실제 원인은 LLM이 아니라 반환 계약 불일치였다.
`pipeline/threads/writer.py` compass 분기가 `write_compass_article()`의 튜플
`(compass_dict, output)` 전체를 그대로 반환 → 호출부 `main_v3.py:323`의
`result.get('cards')`가 `AttributeError`로 죽었다. 카드는 매번 생성됐고 발행 직전
크래시. 동시에 LLM 체인을 쿨다운 기반에서 순수 회전 큐로 정비하고 죽은 tier 9종을
제거했다.

## Why
- compass 분기 반환: `write_compass_article` docstring은
  `mode="thread" → Returns (compass_dict, {"cards": [...], "link": "..."})`인데
  writer는 `result`를 그대로 반환. `write_thread`의 다른 경로는 dict 반환 → 계약 불일치.
- 체인 쿨다운: 429→300s, 401/403/404→86400s 동안 tier를 큐에서 **배제**하는 구조.
  `llm-fallback-chain-management` 계약(순수 회전, 배제 없음) 위반.
- 상태 파일이 `tempfile.gettempdir()` 경로 → 디스크 98% 상태에서 import 타임
  `FileNotFoundError: [Errno 2] No usable temporary directory found` 로 체인 전체가 죽음.
- launchd `kr.aikorea24.threads-compass`가 unload된 채 방치돼 compass 스케줄 자체가 정지.

## Files changed
- `pipeline/threads/writer.py` (compass 분기, PRODUCTION)
- `scripts/threads/v3/model_router.py` (PRODUCTION)
- `config/models.yaml` (CONFIG)
- `tests/test_write_thread_validation.py` (TEST — `TestCompassReturnShape` 2건 추가)
- `.gsd/CAPTURES.md` (신규, CAP-20260929-compass-llm-fix)
- 백업: `pipeline/threads/writer.py.bak_20260929_224216`,
  `config/models.yaml.bak_20260929_224216`,
  `scripts/threads/v3/model_router.py.bak_20260929_224216`

## How
1. compass 분기: `result is None → {"cards": [], "link": ""}`, 아니면 `result[1]`.
2. `model_router.py`: `QUOTA_COOLDOWN_SEC`/`STRUCTURAL_COOLDOWN_SEC` 삭제,
   `_FallbackState`를 `last_success_tier` 하나로 축소(`_clear_expired`,
   `is_quota`, `is_structural`, `record_quota`, `record_structural` 삭제),
   `order()` = `[마지막 성공] + [나머지 yaml 순서] + [유료 맨 끝]`,
   `_call_tier_with_retry`의 quota/structural 분기를 즉시 회전으로 통합,
   `tempfile` 의존 제거 + STATE_PATH를 `scripts/threads/logs/llm_fallback_state.json` 로 이동.
3. `config/models.yaml`: 16 free + 1 paid → 7 free + 1 paid. 라이브 curl 실측으로
   죽은 tier 9종 제거(사유 주석 기록): gemini-2.5-flash(404 new-users),
   groq-llama(404 model_not_found), groq-qwen(404), cerebras-gemma(404 archived),
   cerebras-glm(404 archived), zen-deepseek-free(400 model unavailable),
   zen-mimo-free(403 FreeTierError), zen-bigpickle(403 FreeTierError),
   nvidia-step(410 EOL).
4. launchd compass job 재로드.

## Verification
- `pytest tests/test_write_thread_validation.py -q` → **12 passed, 1 failed**.
  실패 1건 `TestHookBodyEntityConsistency::test_hook_entity_quote_marked_accepted`
  (`pipeline/threads/validator.py`, 손대지 않음)은 `git stash` 후 재실행해도
  동일 실패 = **pre-existing** (stash pop으로 편집 복원 확인).
- 라이브 체인 스모크 `PYTHONPATH=. .venv/bin/python3 scripts/threads/v3/model_router.py`
  → tier1 gemini-3.1-flash-lite 429 → tier2 gemini-3.5-flash-lite **즉시** 성공
  (무대기 회전 실증).
- `STATE_PATH` 기본값 parent 디렉터리 존재 확인. `launchctl list` →
  `kr.aikorea24.threads-compass` 로드됨(exit 0).
- AST parse OK, grep으로 쿨다운 잔재 0건.

## 잔존 위험
- 유료 floor 사망: `DEEPSEEK_API_TOKEN` 401 `****5f76 is invalid` → 소유자 유효 키 발급 필요.
- zhipu-glm은 thinking 모델 → 실 호출에서 content 빈 응답 가능(체인은 회전).
- 디스크 98% (5.5Gi 여유) — tempfile 의존은 제거했으나 근본 해소는 정리 필요.
- compass 실 발행 E2E 미실행(계약은 단위 테스트로 고정).
- `kr.aikorea24.threads-publisher` 여전히 exit 1 (별개 이슈).
- `kr.aikorea24.threads-compass.plist`에 CLOUDFLARE_API_TOKEN 평문 → 로테이션 권장.
