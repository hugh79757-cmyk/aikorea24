# CAPTURES

### CAP-20260929-compass-llm-fix

**Text:** compass 발행 12회 연속 실패의 실제 원인은 LLM이 아니라 반환 계약 불일치였다. `pipeline/threads/writer.py` compass 분기가 `write_compass_article()`의 튜플 `(compass_dict, output)` 전체를 반환했고, 호출부 `main_v3.py:323`의 `result.get('cards')`가 `AttributeError: 'tuple' object has no attribute 'get'`로 죽었다. 카드는 매번 생성됐지만 발행 전에 크래시. 동시에 LLM 체인(`scripts/threads/v3/model_router.py` + `config/models.yaml`)을 순수 회전 큐로 정비했다. 기존 구현은 쿨다운 기반(429→300s, 401/403/404→86400s 배제)이었고, 상태 파일이 `tempfile.gettempdir()`에 있어 디스크 98% 상태에서 import 타임에 `FileNotFoundError: No usable temporary directory found`로 체인 전체가 죽을 수 있었다.

**Captured:** 2026-09-29T22:50:00+09:00
**Status:** resolved
**Classification:** quick-task

**Resolution:**

수정 파일 (백업: `*.bak_20260929_224216`):
- [PRODUCTION CODE] `pipeline/threads/writer.py` (compass 분기 444-450): None → `{"cards": [], "link": ""}`, 아니면 `result[1]` 반환.
- [CONFIG] `config/models.yaml`: 16 free + 1 paid → 7 free + 1 paid. 제거 9종(사유 주석 기록): gemini-2.5-flash(404 new-users), groq-llama(404 model_not_found), groq-qwen(404), cerebras-gemma(404 archived), cerebras-glm(404 archived), zen-deepseek-free(400 model unavailable), zen-mimo-free(403 FreeTierError), zen-bigpickle(403 FreeTierError), nvidia-step(410 EOL). 생존: gemini-3.1-flash-lite, gemini-3.5-flash-lite, gemini-3.5-flash, groq-gpt120b, groq-gpt20b, nvidia-nemotron, zhipu-glm.
- [PRODUCTION CODE] `scripts/threads/v3/model_router.py`: QUOTA_COOLDOWN_SEC/STRUCTURAL_COOLDOWN_SEC 제거, `tempfile` 의존 제거 + STATE_PATH를 `scripts/threads/logs/llm_fallback_state.json`로 이동, `_FallbackState`는 `last_success_tier`만 유지, `order()`는 순수 회전(마지막 성공 → yaml 순서 → 유료 맨 끝).
- [OPS] `launchctl load ~/Library/LaunchAgents/kr.aikorea24.threads-compass.plist` (이전 세션에서 unload된 채 방치 → 재로드).
- [TEST CODE] `tests/test_write_thread_validation.py`에 `TestCompassReturnShape` 2건 추가(tuple→dict, None→빈 dict).

검증:
- `pytest tests/test_write_thread_validation.py -q` → 12 passed, 1 failed. 실패 1건은 `TestHookBodyEntityConsistency::test_hook_entity_quote_marked_accepted` (`pipeline/threads/validator.py`, 손대지 않음). `git stash` 후 재실행해도 동일 실패 = pre-existing.
- 라이브 체인 스모크 (`PYTHONPATH=. .venv/bin/python3 scripts/threads/v3/model_router.py`) → tier1 gemini-3.1-flash-lite 429 → tier2 gemini-3.5-flash-lite 즉시 성공(무대기 회전 확인).
- `STATE_PATH` 기본값 parent 디렉터리 존재 확인. `launchctl list` → `kr.aikorea24.threads-compass` 로드됨(exit 0).
- AST parse OK, grep으로 쿨다운 잔재 0건 확인.

잔존 위험:
- 유료 floor 사망: `DEEPSEEK_API_TOKEN` 401 `****5f76 is invalid` (threadsp-do와 동일 키). 소유자 유효 키 발급 필요.
- zhipu-glm은 thinking 모델 → 실제 호출에서 content 빈 응답 가능(체인은 다음 tier로 회전).
- 디스크 98% (5.5Gi 여유) — 예전 import 타임 `No usable temporary directory` 장애의 원인. tempfile 의존은 제거했으나 근본 해소는 정리 필요.
- compass 실 발행 E2E는 미실행(계약 수정은 단위 테스트로 고정).
- `kr.aikorea24.threads-publisher`는 여전히 exit 1 (별개 이슈).
- `~/Library/LaunchAgents/kr.aikorea24.threads-compass.plist`에 CLOUDFLARE_API_TOKEN 평문 저장 → 로테이션 권장.
